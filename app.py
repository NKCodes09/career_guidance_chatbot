from flask import Flask, render_template, request, jsonify
import pandas as pd

app = Flask(__name__)

# Load career dataset
careers = pd.read_csv("careers.csv")


# -----------------------------
# Helper Functions
# -----------------------------


def extract_user_skills(user_input):
    """
    Extract skills from user input.
    Example: "python, sql, problem solving"
    """
    return [skill.strip().lower() for skill in user_input.split(",") if skill.strip()]


def generate_learning_roadmap(missing_skills):
    """
    Generate a simple week-by-week learning roadmap
    based on missing skills.
    """
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
            "You already have all the required skills. Focus on advanced projects."
        )

    return roadmap


def recommend_careers_with_roadmap(user_input):
    """
    Recommend careers using a scoring algorithm,
    calculate skill gaps, and generate learning roadmaps.
    """
    user_skills = set(extract_user_skills(user_input))
    recommendations = []

    for _, row in careers.iterrows():
        career_skills = set(skill.strip().lower() for skill in row["Skills"].split(","))

        matched_skills = user_skills & career_skills
        missing_skills = career_skills - user_skills
        score = len(matched_skills)

        if score > 0:
            roadmap = generate_learning_roadmap(missing_skills)

            recommendations.append(
                {
                    "Career": row["Career"],
                    "Description": row["Description"],
                    "Score": score,
                    "MatchedSkills": list(matched_skills),
                    "MissingSkills": list(missing_skills),
                    "Roadmap": roadmap,
                }
            )

    # Sort by highest score
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
    user_message = request.json.get("message", "")
    recommendations = recommend_careers_with_roadmap(user_message)

    reply = (
        "Here are the best career matches and learning plans based on your skills:\n\n"
    )

    for rec in recommendations:
        reply += (
            f"🎯 {rec['Career']} (Match Score: {rec['Score']})\n"
            f"🧠 Matched Skills: {', '.join(rec['MatchedSkills']) if rec['MatchedSkills'] else 'None'}\n"
            f"📄 {rec['Description']}\n"
        )

        if rec["MissingSkills"]:
            reply += f"📌 Skills to Learn: {', '.join(rec['MissingSkills'])}\n"

        if rec["Roadmap"]:
            reply += "🗺️ Learning Roadmap:\n"
            for step in rec["Roadmap"]:
                reply += f"   - {step}\n"

        reply += "\n"

    return jsonify({"reply": reply})


# -----------------------------
# App Runner
# -----------------------------

if __name__ == "__main__":
    app.run(debug=True)
