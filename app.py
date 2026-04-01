import os
import json
import sqlite3
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from google import genai
from google.genai.errors import ClientError

# ── App Setup ──────────────────────────────────────────────────

load_dotenv()  # Load environment variables from .env file

API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    raise RuntimeError("GOOGLE_API_KEY not set")

# Initialise the Gemini AI client
client     = genai.Client(api_key=API_KEY)
MODEL_NAME = "models/gemini-2.5-flash"

app = Flask(__name__)
app.secret_key = "replace_this_with_random_secret"  # Used to sign/encrypt session cookies

DB_NAME = "database.db"

# ── Auth Decorator ─────────────────────────────────────────────

def login_required(view):
    """Wraps a route so unauthenticated users are redirected to login."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to access this page.", "error")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped

# ── Database ───────────────────────────────────────────────────

def get_db():
    """Open a SQLite connection with dict-like row access."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row  # Allows row["column"] instead of row[0]
    return conn

def init_db():
    """Create tables on first run if they don't exist yet."""
    with get_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                email    TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS quiz_results (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER NOT NULL,
                topic      TEXT NOT NULL,
                score      REAL NOT NULL,
                total      INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

init_db()

# ── Gemini AI Helpers ──────────────────────────────────────────

def call_gemini(prompt):
    """Send a prompt to Gemini and return the text response."""
    try:
        response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
        return response.text
    except ClientError:
        return "⚠️ AI service busy. Please try again shortly."


def gemini_career_chat(history):
    """Build a career guidance prompt from the conversation history and call Gemini."""
    # Format the chat history into a readable transcript for the AI
    convo = "\n".join([f"{m['role'].upper()}: {m['text']}" for m in history])
    prompt = f"""
You are an AI career guidance assistant for people from ANY background.
You are NOT limited to tech careers.

Rules:
- Use conversation history to stay consistent.
- If key info is missing (education, interests, strengths, location, salary goals), ask up to 3 short clarifying questions.
- Otherwise provide 3–6 relevant career paths. For each include:
  1) Why it fits
  2) Typical entry roles
  3) Core skills (technical + soft)
  4) A 30/60/90-day action plan
- Include learning resource ideas and 1–2 portfolio/project ideas where relevant.
- Use Markdown: ## headings, - bullet points, **bold** for emphasis.
- Be clear, practical, and friendly.

Conversation:
{convo}
"""
    return call_gemini(prompt)


def gemini_improve_cv_text(text, field_type):
    """Ask Gemini to rewrite a CV field in a more professional tone."""
    # Map field type to a human-readable description used in the prompt
    context = {
        'summary':    'a professional summary for a CV',
        'experience': 'a work experience description for a CV',
        'education':  'an education entry description for a CV',
        'project':    'a project description for a CV',
    }.get(field_type, 'a section of a CV')

    prompt = f"""
You are a professional CV writer. Improve the following text which is {context}.

Original text:
{text}

Instructions:
- Make it more professional, specific, and impactful
- Use strong action verbs (e.g. developed, led, built, improved, achieved)
- Be concise but specific — quantify achievements where possible
- Do NOT change the core facts — only improve the language and structure
- Keep it to a similar length as the original
- Return ONLY the improved text, nothing else — no explanations, no labels
"""
    return call_gemini(prompt)


def gemini_generate_quiz(topic):
    """Generate 10 multiple-choice questions for a given job role and return them as a list."""
    prompt = f"""
Generate 10 multiple-choice interview questions for someone applying for: {topic}

Return ONLY a valid JSON object in this exact format, no extra text:
{{
  "questions": [
    {{
      "question": "Question text here?",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "correctAnswer": "Option A",
      "explanation": "Brief explanation of why this is correct."
    }}
  ]
}}
"""
    try:
        response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
        text = response.text.strip()

        # Strip markdown code fences if Gemini wraps the JSON in ```json ... ```
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]

        data = json.loads(text.strip())
        return data["questions"]
    except Exception:
        return None  # Caller handles the None case


def gemini_cover_letter(name, jobtitle, company, jd, skills):
    """Generate a tailored cover letter based on the applicant's details."""
    prompt = f"""
Write a professional, compelling cover letter for the following:

Applicant Name: {name if name else 'the applicant'}
Job Title: {jobtitle}
Company: {company}
Job Description: {jd[:2000]}
Applicant's Skills/Experience: {skills[:1000]}

Instructions:
- Write in a professional but warm, human tone
- 3–4 paragraphs
- Opening: express enthusiasm for the role and company
- Middle: match their key skills to the job requirements
- Closing: confident call to action
- Do NOT use generic filler phrases like "I am writing to apply"
- Make it feel personal and tailored to this specific job
- Output plain text only — no markdown formatting
"""
    return call_gemini(prompt)

# ── Public Routes (no login needed) ───────────────────────────

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email    = request.form["email"]
        password = request.form["password"]

        if len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
            return redirect(url_for("signup"))

        # Hash the password before storing — never store plain text passwords
        hashed = generate_password_hash(password, method="pbkdf2:sha256")
        try:
            with get_db() as db:
                db.execute("INSERT INTO users (email, password) VALUES (?, ?)", (email, hashed))
            flash("Account created. Please log in.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            # Triggered when the email already exists (UNIQUE constraint)
            flash("Email already registered.", "error")
            return redirect(url_for("signup"))

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email    = request.form["email"]
        password = request.form["password"]

        with get_db() as db:
            user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

        # Fail if user not found or password doesn't match the stored hash
        if not user or not check_password_hash(user["password"], password):
            flash("Invalid email or password.", "error")
            return redirect(url_for("login"))

        # Store user info in the session so other routes can identify them
        session.clear()
        session["user_id"]    = user["id"]
        session["user_email"] = user["email"]
        session["history"]    = []  # Fresh chat history on each login
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))

# ── Protected Routes (login required) ─────────────────────────

@app.route("/dashboard")
@login_required
def dashboard():
    # Fetch the user's 10 most recent quiz results to display in the history table
    with get_db() as db:
        results = db.execute(
            "SELECT * FROM quiz_results WHERE user_id = ? ORDER BY created_at DESC LIMIT 10",
            (session["user_id"],)
        ).fetchall()
    return render_template("dashboard.html", results=results, email=session.get("user_email", ""))


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
    if len(message) > 2000:
        return jsonify({"reply": "Message too long — please keep it under 2000 characters."})

    # Keep only the last 10 messages so the session doesn't grow too large
    history = session.get("history", [])
    history.append({"role": "user", "text": message})
    history = history[-10:]
    session["history"] = history

    reply = gemini_career_chat(history)

    history.append({"role": "assistant", "text": reply})
    history = history[-10:]
    session["history"] = history

    return jsonify({"reply": reply})


@app.route("/cv")
@login_required
def cv():
    return render_template("cv.html")


@app.route("/cv/improve", methods=["POST"])
@login_required
def cv_improve():
    text       = request.form.get("text", "").strip()
    field_type = request.form.get("type", "summary").strip()
    if not text:
        return jsonify({"improved": "Please write some content first."})
    improved = gemini_improve_cv_text(text, field_type)
    return jsonify({"improved": improved})


@app.route("/interview")
@login_required
def interview():
    return render_template("interview.html")


@app.route("/interview/generate", methods=["POST"])
@login_required
def interview_generate():
    topic = request.form.get("topic", "").strip()
    if not topic:
        return jsonify({"error": "Please provide a job role or topic."})
    questions = gemini_generate_quiz(topic)
    if not questions:
        return jsonify({"error": "Failed to generate questions. Please try again."})
    return jsonify({"questions": questions})


@app.route("/interview/save", methods=["POST"])
@login_required
def interview_save():
    """Save the user's quiz score to the database after completing a quiz."""
    topic = request.form.get("topic", "General").strip()
    score = request.form.get("score", 0)
    total = request.form.get("total", 10)
    try:
        with get_db() as db:
            db.execute(
                "INSERT INTO quiz_results (user_id, topic, score, total) VALUES (?, ?, ?, ?)",
                (session["user_id"], topic, float(score), int(total))
            )
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.route("/cover-letter")
@login_required
def cover_letter():
    return render_template("cover_letter.html")


@app.route("/cover-letter/generate", methods=["POST"])
@login_required
def cover_letter_generate():
    name     = request.form.get("name", "").strip()
    jobtitle = request.form.get("jobtitle", "").strip()
    company  = request.form.get("company", "").strip()
    jd       = request.form.get("jd", "").strip()
    skills   = request.form.get("skills", "").strip()

    if not jobtitle or not company or not jd:
        return jsonify({"letter": "Please fill in the job title, company, and job description."})

    return jsonify({"letter": gemini_cover_letter(name, jobtitle, company, jd, skills)})

# ── Run ────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True)

