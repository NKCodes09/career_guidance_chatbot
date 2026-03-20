import os
import sqlite3
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

from google import genai
from google.genai.errors import ClientError

# =============================
# Setup
# =============================

load_dotenv()

API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    raise RuntimeError("GOOGLE_API_KEY not set")

client = genai.Client(api_key=API_KEY)
MODEL_NAME = "models/gemini-2.5-flash"

app = Flask(__name__)
app.secret_key = "replace_this_with_random_secret"

DB_NAME = "database.db"


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to access this page.", "error")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped_view


# =============================
# Database
# =============================

def get_db():
    conn = sqlite3.connect(DB_NAME)
    return conn


def init_db():
    with get_db() as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
            """
        )


init_db()

# =============================
# Gemini Logic – Career Chat
# =============================

def gemini_career_guidance_with_history(history):
    convo = "\n".join([f"{m['role'].upper()}: {m['text']}" for m in history])

    prompt = f"""
You are an AI career guidance assistant for people from ANY background (students, career changers, professionals).
You are NOT limited to Computer Science or tech careers.

Your job: give practical, tailored career suggestions.

Rules:
- Use the conversation history to stay consistent.
- If key info is missing (education, interests, strengths, constraints, location, salary goals), ask up to 3 short clarifying questions.
- Otherwise provide 3–6 relevant career paths (including non-tech where appropriate). For each path include:
  1) Why it fits
  2) Typical entry roles
  3) Core skills (technical + soft skills)
  4) A simple 30/60/90-day plan
- Include learning resource ideas (no links needed) and 1–2 project/portfolio ideas if applicable.
- Use Markdown formatting: ## headings, - bullet points, **bold** for emphasis.
- Keep it clear, structured, and friendly.

Conversation:
{convo}
"""

    try:
        response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
        return response.text
    except ClientError:
        return "⚠️ AI service busy. Please try again shortly."


# =============================
# Gemini Logic – CV Analyser
# =============================

def gemini_analyse_cv(cv_text):
    prompt = f"""
You are a professional career advisor and CV expert.

A user has shared their CV below. Analyse it and provide:

## 1. CV Summary
A short 2–3 sentence summary of who this person is.

## 2. Key Strengths
Their top 4–6 strengths from their CV (skills, experience, education).

## 3. Skill Gaps
What skills or experience are they missing that would make them more employable?

## 4. Best Career Matches
3–5 careers that suit them. For each:
- Why it fits their background
- What entry-level role they could apply for right now
- One thing they should do to strengthen their application

## 5. Immediate Next Steps
3 specific actions they can take this week to improve their career prospects.

Be honest, practical, and encouraging. Use Markdown formatting throughout.

CV:
{cv_text[:4000]}
"""

    try:
        response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
        return response.text
    except ClientError:
        return "⚠️ AI service busy. Please try again shortly."


# =============================
# Routes – Public
# =============================

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email    = request.form["email"]
        password = request.form["password"]

        if len(password) < 6:
            flash("Password must be at least 6 characters long.", "error")
            return redirect(url_for("signup"))

        hashed_password = generate_password_hash(password, method="pbkdf2:sha256")

        try:
            with get_db() as db:
                db.execute(
                    "INSERT INTO users (email, password) VALUES (?, ?)",
                    (email, hashed_password),
                )
            flash("Account created successfully. Please log in.", "success")
            return redirect(url_for("login"))

        except sqlite3.IntegrityError:
            flash("Email is already registered.", "error")
            return redirect(url_for("signup"))

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email    = request.form["email"]
        password = request.form["password"]

        with get_db() as db:
            user = db.execute(
                "SELECT * FROM users WHERE email = ?", (email,)
            ).fetchone()

        if not user or not check_password_hash(user[2], password):
            flash("Invalid email or password.", "error")
            return redirect(url_for("login"))

        session.clear()
        session["user_id"] = user[0]
        session["history"] = []
        return redirect(url_for("chat"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


# =============================
# Routes – Protected
# =============================

@app.route("/chat")
@login_required
def chat():
    return render_template("chat.html")


@app.route("/chat/send", methods=["POST"])
@login_required
def chat_send():
    message = request.form.get("message", "").strip()
    if not message:
        return jsonify({"reply": "Please type a message."})

    history = session.get("history", [])
    history.append({"role": "user", "text": message})
    history = history[-8:]
    session["history"] = history

    reply = gemini_career_guidance_with_history(history)

    history.append({"role": "assistant", "text": reply})
    history = history[-8:]
    session["history"] = history

    return jsonify({"reply": reply})


# NEW: CV Analyser route
@app.route("/cv/analyse", methods=["POST"])
@login_required
def cv_analyse():
    cv_text = request.form.get("cv_text", "").strip()
    if not cv_text:
        return jsonify({"analysis": "Please provide your CV text."})
    if len(cv_text) < 50:
        return jsonify({"analysis": "Your CV seems too short. Please paste the full content."})

    analysis = gemini_analyse_cv(cv_text)
    return jsonify({"analysis": analysis})


# =============================
# Run
# =============================

if __name__ == "__main__":
    app.run(debug=True)
    