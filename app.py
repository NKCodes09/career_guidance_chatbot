from flask import Flask, render_template, request, jsonify
import pandas as pd
import random

app = Flask(__name__)

# Load career dataset
careers = pd.read_csv("careers.csv")

# Basic keyword matching recommendation
def recommend_careers(user_input):
    input_lower = user_input.lower()
    matched = []

    for _, row in careers.iterrows():
        skills = row["Skills"].lower()
        if any(skill in input_lower for skill in skills.split(",")):
            matched.append(row)

    if not matched:
        return [{"Career": "No strong match found", "Description": "Try adding more skills or interests."}]
    else:
        return matched[:3]  # return top 3 matches


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    user_message = request.json["message"]
    recommendations = recommend_careers(user_message)

    # Format chatbot response
    reply = "Here are some career paths you might like:\n\n"
    for rec in recommendations:
        reply += f"🎯 {rec['Career']} — {rec['Description']}\n"

    return jsonify({"reply": reply})


if __name__ == "__main__":
    app.run(debug=True)
