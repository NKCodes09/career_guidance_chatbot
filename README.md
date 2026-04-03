# AI Career Coach

An AI-powered career guidance web application built with Flask and Google Gemini 2.5 Flash. Delivers four distinct tools — career chat, CV builder, mock interview quiz, and cover letter generator — within a single authenticated platform.

**Live demo:** https://career-guidance-chatbot-oo4u.onrender.com

> The server runs on Render's free tier and may take 30–60 seconds to wake from sleep on first visit.

---

## Features

- **Career Chat** — conversational guidance with 30/60/90-day action planning
- **CV Builder** — section-by-section form with live preview, AI-assisted field improvement, and client-side PDF export
- **Mock Interview Quiz** — AI-generated 10-question quiz with database-persisted scoring history
- **Cover Letter Generator** — personalised letters from job description and skills input

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3, Flask |
| AI | Google Gemini 2.5 Flash API |
| Database | SQLite (2 tables: users, quiz_results) |
| Auth | Flask sessions + Werkzeug pbkdf2:sha256 |
| Templating | Jinja2 |
| Frontend | Vanilla JS, Marked.js, html2pdf.js |

---

## Running Locally

### 1. Clone the repository

```bash
git clone https://github.com/NKCodes09/career_guidance_chatbot.git
cd career_guidance_chatbot
```

### 2. Create and activate a virtual environment

```bash
python -m venv venv

# macOS / Linux
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set up environment variables

Create a `.env` file in the project root:

```
GOOGLE_API_KEY=your_gemini_api_key_here
SECRET_KEY=your_secret_key_here
```

- Get a free Gemini API key at https://aistudio.google.com
- `SECRET_KEY` can be any long random string

### 5. Run the application

```bash
python app.py
```

Visit http://127.0.0.1:5000 in your browser.

---

## Running Tests

```bash
pytest
```

Runs a 34-test suite covering authentication routes, the `login_required` decorator, chat input validation, quiz JSON parsing, and database persistence. The suite uses a temporary SQLite database and mocks the Gemini API — no live network calls are made.

---

## Project Structure

```
career_guidance_chatbot/
├── app.py              # Application logic and all 14 route handlers (~374 lines)
├── requirements.txt    # Python dependencies
├── .env                # API keys — not committed to version control
├── .gitignore
├── templates/          # Jinja2 HTML templates
└── static/             # CSS, JavaScript, images
```

---

## Final Year Project

Built as a BSc Computer Science final year project at the University of Hertfordshire (2025–26).

- **Student:** Nithushan Kulasingam (SRN: 25001300)
- **Supervisor:** Raghubir Singh
- 
