import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
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
MODEL_NAME = "models/gemini-flash-latest"

app = Flask(__name__)
app.secret_key = "replace_this_with_random_secret"

DB_NAME = "database.db"

# =============================
# Database
# =============================


def get_db():
    return sqlite3.connect(DB_NAME)


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
# Gemini Logic
# =============================


def gemini_career_guidance(user_input):
    prompt = f"""
You are an AI career guidance assistant for Computer Science students.

Suggest suitable career paths and skills based on the input.

User input:
{user_input}
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
        email = request.form["email"]
        password = generate_password_hash(request.form["password"])

        try:
            with get_db() as db:
                db.execute(
                    "INSERT INTO users (email, password) VALUES (?, ?)",
                    (email, password),
                )
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            return "Account already exists"

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        user = (
            get_db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        )

        if user and check_password_hash(user[2], password):
            session["user_id"] = user[0]
            return redirect(url_for("chat"))

        return "Invalid email or password"

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


# =============================
# Routes – Protected
# =============================


@app.route("/chat")
def chat():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return render_template("chat.html")


@app.route("/chat/send", methods=["POST"])
def chat_send():
    if "user_id" not in session:
        return jsonify({"reply": "Unauthorized"})

    message = request.form.get("message", "")
    reply = gemini_career_guidance(message)
    return jsonify({"reply": reply})


# =============================
# Run
# =============================

if __name__ == "__main__":
    app.run(debug=True)
