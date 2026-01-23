from flask import Flask, render_template, request, jsonify

app = Flask(__name__)


@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    message = data.get("message", "")
    return jsonify(
        {"reply": f"You entered: {message}\n(Chatbot logic will respond here)"}
    )


if __name__ == "__main__":
    app.run(debug=True)
