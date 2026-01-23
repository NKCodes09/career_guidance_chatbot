from flask import Flask, render_template, request, jsonify
import pandas as pd
import re

app = Flask(__name__)

# Load career dataset
careers = pd.read_csv("careers.csv")

# Career knowledge base
CAREER_INFO = {
    "Data Analyst": {
        "Responsibilities": [
            "Collect and clean data",
            "Analyse data to identify trends",
            "Create reports and dashboards",
            "Support business decision-making",
        ],
        "Progression": [
            "Junior Data Analyst",
            "Data Analyst",
            "Senior Data Analyst",
            "Data Scientist / Analytics Manager",
        ],
    },
    "Software Developer": {
        "Responsibilities": [
            "Design and develop software applications",
            "Write and maintain code",
            "Debug and fix issues",
            "Collaborate using version control",
        ],
        "Progression": [
            "Junior Developer",
            "Software Developer",
            "Senior Developer",
            "Lead Engineer / Architect",
        ],
    },
    "Cyber Security Analyst": {
        "Responsibilities": [
            "Monitor systems for security threats",
            "Conduct vulnerability assessments",
            "Respond to security incidents",
            "Implement security controls",
        ],
        "Progression": [
            "Security Analyst",
            "Senior Security Analyst",
            "Security Engineer",
            "Security Architect / CISO",
        ],
    },
}

# -----------------------------
# Helper Functions
# -----------------------------


def tokenize_text(text):
    """
    Convert free text into a set of lowercase words.
    """
    return set(re.findall(r"\b[a-zA-Z]+\b", text.lower()))


def generate_learning_roadmap(missing_skills):
    roadmap = []
    week = 1

    for skill in missing_skills:
        roadmap.append(f"Week {week}: Learn basics of {skill.capitalize()}")
        week += 1
        roadmap.append(
            f"Week {week}: Practice {skill.capitalize()} with small projects"
        )
        week += 1

    if not roadmap:
        roadmap.append(
            "You already have all required skills. Focus on advanced projects."
        )

    return roadmap


def analyse_cv_text(cv_text, target_career_skills):
    feedback = []
    cv_words = tokenize_text(cv_text)

    # Required CV sections
    sections = ["education", "experience", "skills", "projects"]
    missing_sections = [s for s in sections if s not in cv_words]

    if missing_sections:
        feedback.append(
            f"Your CV is missing important sections: {', '.join(missing_sections)}."
        )

    # Skill alignment
    missing_skills = target_career_skills - cv_words
    if missing_skills:
        feedback.append(
            f"Consider adding or highlighting these skills: {', '.join(missing_skills)}."
        )

    # Action verbs
    action_verbs = {
        "developed",
        "designed",
        "implemented",
        "analysed",
        "built",
        "created",
    }
    used_verbs = action_verbs & cv_words

    if len(used_verbs) < 2:
        feedback.append(
            "Use stronger action verbs such as developed, implemented, analysed, or designed."
        )

    if not feedback:
        feedback.append(
            "Your CV is well-structured and aligned with the selected career."
        )

    return feedback


def recommend_careers(user_input, cv_text=None):
    user_words = tokenize_text(user_input)
    recommendations = []

    for _, row in careers.iterrows():
        career_skills = set(skill.strip().lower() for skill in row["Skills"].split(","))

        matched_skills = career_skills & user_words
        missing_skills = career_skills - user_words
        score = len(matched_skills)

        if score > 0:
            career_name = row["Career"]
            info = CAREER_INFO.get(career_name, {})

            cv_feedback = []
            if cv_text:
                cv_feedback = analyse_cv_text(cv_text, career_skills)

            recommendations.append(
                {
                    "Career": career_name,
                    "Description": row["Description"],
                    "Score": score,
                    "MatchedSkills": list(matched_skills),
                    "MissingSkills": list(missing_skills),
                    "Roadmap": generate_learning_roadmap(missing_skills),
                    "Responsibilities": info.get("Responsibilities", []),
                    "Progression": info.get("Progression", []),
                    "CVFeedback": cv_feedback,
                }
            )

    recommendations.sort(key=lambda x: x["Score"], reverse=True)

    if not recommendations:
        return [
            {
                "Career": "No strong match found",
                "Description": "Try adding more skills or interests.",
                "Score": 0,
                "MatchedSkills": [],
                "MissingSkills": [],
                "Roadmap": [],
                "Responsibilities": [],
                "Progression": [],
                "CVFeedback": [],
            }
        ]

    return recommendations[:3]


# -----------------------------
# Routes
# -----------------------------


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    user_message = data.get("message", "")
    cv_text = data.get("cv", "")

    recommendations = recommend_careers(user_message, cv_text)

    reply = "Here is your personalised career guidance and CV feedback:\n\n"

    for rec in recommendations:
        reply += (
            f"🎯 {rec['Career']} (Match Score: {rec['Score']})\n"
            f"📄 {rec['Description']}\n"
            f"🧠 Matched Skills: {', '.join(rec['MatchedSkills']) if rec['MatchedSkills'] else 'None'}\n"
        )

        if rec["MissingSkills"]:
            reply += f"📌 Skills to Learn: {', '.join(rec['MissingSkills'])}\n"

        if rec["CVFeedback"]:
            reply += "📄 CV Feedback:\n"
            for f in rec["CVFeedback"]:
                reply += f"   - {f}\n"

        reply += "\n"

    return jsonify({"reply": reply})


# -----------------------------
# App Runner
# -----------------------------

if __name__ == "__main__":
    app.run(debug=True)
