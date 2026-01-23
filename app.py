# =============================
# Imports & Environment Setup
# =============================

import os
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv
from google import genai
from google.genai.errors import ClientError

# =============================
# Load Environment Variables
# =============================

load_dotenv()

API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    raise RuntimeError("GOOGLE_API_KEY not set")

# =============================
# Gemini Configuration
# =============================

client = genai.Client(api_key=API_KEY)

# ✅ Free-tier friendly model
MODEL_NAME = "models/gemini-flash-latest"

# =============================
# Flask App Setup
# =============================

app = Flask(__name__)

# =============================
# Gemini Career Assistant
# =============================


def gemini_career_guidance(user_input):
    prompt = f"""
You are an AI career guidance assistant for Computer Science students.

Based on the user's input:
1. Suggest 2–3 suitable career paths
2. Explain briefly why each career fits
3. List key technical skills to focus on next

User input:
{user_input}

Respond in this format:

Career Suggestions:
- Career 1: explanation
- Career 2: explanation

Key Skills to Learn:
- skill 1
- skill 2
- skill 3
"""

    try:
        response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
        return response.text

    except ClientError as e:
        # Graceful quota handling
        if "RESOURCE_EXHAUSTED" in str(e):
            return (
                "⚠️ AI service is temporarily busy (free-tier limit reached).\n\n"
                "Please try again in a few seconds, or refine your input.\n\n"
                "💡 Tip: Shorter inputs use fewer tokens."
            )
        return f"❌ Gemini error: {e}"

    except Exception as e:
        return "❌ Unexpected AI error. Please try again later."


# =============================
# Routes
# =============================


@app.route("/")
def index():
    return render_template("landing.html")


@app.route("/chat", methods=["POST"])
def chat():
    user_message = request.form.get("message", "")
    reply = gemini_career_guidance(user_message)
    return jsonify({"reply": reply})


# =============================
# Run App
# =============================

if __name__ == "__main__":
    app.run(debug=True)
