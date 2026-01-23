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
    Example input: "python, sql, problem solving"
    """
    return [skill.strip().lower() for skill in user_input.split(",")]


def recommend_careers(user_input):
    """
    Recommend careers based on a scoring algorithm.
    Score = number of matched skills
    """
    user_skills = extract_user_skills(user_input)
    recommendations = []

    for _, row in careers.iterrows():
        career_skills = [s.strip().lower() for s in row["Skills"].split(",")]

        matched_skills = set(user_skills) & set(career_skills)
        score = len(matched_skills)

        if score > 0:
            recommendations.append(
                {
                    "Career": row["Career"],
                    "Description": row["Description"],
                    "Score": score,
                    "MatchedSkills": list(matched_skills),
                }
            )

    # Sort careers by score (highest first)
    recommendations.sort(key=lambda x: x["Score"], reverse=True)

    if not recommendations:
        return [
            {
                "Career": "No strong match found",
                "Description": "Try adding more skills or interests.",
                "Score": 0,
                "MatchedSkills": [],
            }
        ]

    return recommendations[:3]  # Top 3 careers


# -----------------------------
# Routes
# -----------------------------


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    user_message = request.json.get("message", "")
    recommendations = recommend_careers(user_message)

    reply = "Here are the best career matches based on your skills:\n\n"

    for rec in recommendations:
        reply += (
            f"🎯 {rec['Career']} (Match Score: {rec['Score']})\n"
            f"🧠 Matched Skills: {', '.join(rec['MatchedSkills']) if rec['MatchedSkills'] else 'None'}\n"
            f"📄 {rec['Description']}\n\n"
        )

    return jsonify({"reply": reply})


# -----------------------------
# App Runner
# -----------------------------

if __name__ == "__main__":
    app.run(debug=True)
