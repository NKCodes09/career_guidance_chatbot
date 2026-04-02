"""
test_app.py — Pytest suite for AI Career Coach
Covers: authentication routes, login_required decorator,
        chat input validation, quiz JSON parser, interview save,
        cover letter validation, and CV improve validation.
"""

import json
import os
import pytest
import tempfile

# ── Patch Gemini and dotenv before importing app ───────────────

import unittest.mock as mock

# Prevent real API calls and missing .env from breaking tests
os.environ["GOOGLE_API_KEY"] = "test-key-not-real"

with mock.patch("google.genai.Client"):
    with mock.patch("dotenv.load_dotenv"):
        import app as flask_app


# ── Fixtures ───────────────────────────────────────────────────

@pytest.fixture
def app():
    """Create a fresh app instance backed by a temporary SQLite database."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    flask_app.app.config.update({
        "TESTING": True,
        "SECRET_KEY": "test-secret",
        "WTF_CSRF_ENABLED": False,
    })
    flask_app.DB_NAME = db_path
    flask_app.init_db()

    yield flask_app.app

    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(app):
    """Return a Flask test client."""
    return app.test_client()


@pytest.fixture
def registered_user(client):
    """Register a test user and return their credentials."""
    email, password = "test@example.com", "password123"
    client.post("/signup", data={"email": email, "password": password})
    return {"email": email, "password": password}


@pytest.fixture
def logged_in_client(client, registered_user):
    """Return a test client that is already logged in."""
    client.post("/login", data=registered_user)
    return client


# ── Authentication Tests ───────────────────────────────────────

class TestSignup:
    def test_signup_valid_creates_account_and_redirects(self, client):
        """Valid signup should redirect to /login."""
        r = client.post("/signup",
                        data={"email": "new@example.com", "password": "secure99"},
                        follow_redirects=False)
        assert r.status_code == 302
        assert "login" in r.headers["Location"]

    def test_signup_valid_creates_user_in_database(self, app, client):
        """After valid signup the user record should exist in the database."""
        client.post("/signup", data={"email": "new@example.com", "password": "secure99"})
        with app.app_context():
            with flask_app.get_db() as db:
                user = db.execute("SELECT * FROM users WHERE email = 'new@example.com'").fetchone()
        assert user is not None

    def test_signup_duplicate_email_shows_error(self, client, registered_user):
        """Registering with an already-used email should redirect back to /signup."""
        r = client.post("/signup", data=registered_user, follow_redirects=False)
        assert r.status_code == 302
        assert "signup" in r.headers["Location"]

    def test_signup_short_password_rejected(self, client):
        """Passwords shorter than 6 characters should redirect back to /signup."""
        r = client.post("/signup",
                        data={"email": "short@example.com", "password": "abc"},
                        follow_redirects=False)
        assert r.status_code == 302
        assert "signup" in r.headers["Location"]

    def test_signup_short_password_does_not_create_user(self, app, client):
        """A rejected short password must not insert a record into the database."""
        client.post("/signup", data={"email": "short@example.com", "password": "abc"})
        with app.app_context():
            with flask_app.get_db() as db:
                user = db.execute("SELECT * FROM users WHERE email = 'short@example.com'").fetchone()
        assert user is None

    def test_signup_get_renders_form(self, client):
        """GET /signup should return 200."""
        r = client.get("/signup")
        assert r.status_code == 200


class TestLogin:
    def test_login_valid_credentials_redirects_to_dashboard(self, client, registered_user):
        """Valid login should redirect to /dashboard."""
        r = client.post("/login", data=registered_user, follow_redirects=False)
        assert r.status_code == 302
        assert "dashboard" in r.headers["Location"]

    def test_login_valid_sets_session(self, client, registered_user):
        """Valid login should write user_id into the session."""
        with client.session_transaction() as sess:
            assert "user_id" not in sess
        client.post("/login", data=registered_user)
        with client.session_transaction() as sess:
            assert "user_id" in sess

    def test_login_wrong_password_redirects_to_login(self, client, registered_user):
        """Wrong password should redirect back to /login, not to dashboard."""
        r = client.post("/login",
                        data={"email": registered_user["email"], "password": "wrongpass"},
                        follow_redirects=False)
        assert r.status_code == 302
        assert "login" in r.headers["Location"]

    def test_login_wrong_password_does_not_set_session(self, client, registered_user):
        """Failed login must not write user_id into the session."""
        client.post("/login",
                    data={"email": registered_user["email"], "password": "wrongpass"})
        with client.session_transaction() as sess:
            assert "user_id" not in sess

    def test_login_unknown_email_redirects_to_login(self, client):
        """Unknown email should redirect back to /login."""
        r = client.post("/login",
                        data={"email": "nobody@example.com", "password": "anything"},
                        follow_redirects=False)
        assert r.status_code == 302
        assert "login" in r.headers["Location"]

    def test_login_get_renders_form(self, client):
        """GET /login should return 200."""
        r = client.get("/login")
        assert r.status_code == 200


class TestLogout:
    def test_logout_redirects_to_landing(self, logged_in_client):
        """Logout should redirect to /."""
        r = logged_in_client.get("/logout", follow_redirects=False)
        assert r.status_code == 302
        assert r.headers["Location"] in ("/", "http://localhost/")

    def test_logout_clears_session(self, logged_in_client):
        """After logout, user_id must not remain in the session."""
        with logged_in_client.session_transaction() as sess:
            assert "user_id" in sess
        logged_in_client.get("/logout")
        with logged_in_client.session_transaction() as sess:
            assert "user_id" not in sess

    def test_dashboard_redirects_after_logout(self, logged_in_client):
        """After logout, /dashboard should redirect to /login."""
        logged_in_client.get("/logout")
        r = logged_in_client.get("/dashboard", follow_redirects=False)
        assert r.status_code == 302
        assert "login" in r.headers["Location"]


# ── login_required Decorator Tests ────────────────────────────

class TestLoginRequired:
    """All protected routes must redirect unauthenticated users to /login."""

    protected_routes = [
        "/dashboard",
        "/chat",
        "/cv",
        "/interview",
        "/cover-letter",
    ]

    def test_protected_routes_redirect_when_not_logged_in(self, client):
        for route in self.protected_routes:
            r = client.get(route, follow_redirects=False)
            assert r.status_code == 302, f"{route} should redirect unauthenticated users"
            assert "login" in r.headers["Location"], f"{route} should redirect to /login"

    def test_protected_routes_accessible_when_logged_in(self, logged_in_client):
        for route in self.protected_routes:
            r = logged_in_client.get(route)
            assert r.status_code == 200, f"{route} should be accessible when logged in"


# ── Chat Input Validation Tests ────────────────────────────────

class TestChatSend:
    def test_empty_message_returns_error_json(self, logged_in_client):
        """Empty message should return a JSON error, not call Gemini."""
        r = logged_in_client.post("/chat/send", data={"message": ""})
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "reply" in data
        assert "Please type" in data["reply"]

    def test_message_over_2000_chars_returns_error_json(self, logged_in_client):
        """Messages over 2000 characters should be rejected with a JSON error."""
        long_msg = "x" * 2001
        r = logged_in_client.post("/chat/send", data={"message": long_msg})
        data = json.loads(r.data)
        assert "too long" in data["reply"].lower()

    def test_chat_send_requires_login(self, client):
        """Unauthenticated POST to /chat/send should redirect."""
        r = client.post("/chat/send", data={"message": "hello"})
        assert r.status_code == 302


# ── Quiz JSON Parser Tests ─────────────────────────────────────

class TestQuizJSONParser:
    """
    The quiz prompt handler strips code fences before parsing.
    These tests exercise that logic directly via gemini_generate_quiz,
    with Gemini mocked to return controlled output.
    """

    def _mock_response(self, text):
        """Helper: build a mock Gemini response object."""
        m = mock.MagicMock()
        m.text = text
        return m

    def _valid_json(self):
        return json.dumps({
            "questions": [{
                "question": "What is Flask?",
                "options": ["A", "B", "C", "D"],
                "correctAnswer": "A",
                "explanation": "Flask is a Python web framework."
            }] * 10
        })

    def test_clean_json_parses_correctly(self):
        """Clean JSON with no fences should parse and return 10 questions."""
        with mock.patch.object(flask_app.client.models, "generate_content") as m:
            m.return_value = self._mock_response(self._valid_json())
            questions = flask_app.gemini_generate_quiz("Software Engineer")
        assert questions is not None
        assert len(questions) == 10

    def test_json_wrapped_in_code_fences_parses_correctly(self):
        """JSON wrapped in ```json ... ``` fences should still parse."""
        fenced = f"```json\n{self._valid_json()}\n```"
        with mock.patch.object(flask_app.client.models, "generate_content") as m:
            m.return_value = self._mock_response(fenced)
            questions = flask_app.gemini_generate_quiz("Software Engineer")
        assert questions is not None
        assert len(questions) == 10

    def test_malformed_json_returns_none(self):
        """Malformed JSON should return None so the route can handle it gracefully."""
        with mock.patch.object(flask_app.client.models, "generate_content") as m:
            m.return_value = self._mock_response("This is not JSON at all.")
            questions = flask_app.gemini_generate_quiz("Software Engineer")
        assert questions is None

    def test_interview_generate_returns_error_on_empty_topic(self, logged_in_client):
        """Empty topic should return a JSON error without calling Gemini."""
        r = logged_in_client.post("/interview/generate", data={"topic": ""})
        data = json.loads(r.data)
        assert "error" in data

    def test_interview_generate_returns_error_when_gemini_fails(self, logged_in_client):
        """When quiz generation returns None, route should return a JSON error."""
        with mock.patch.object(flask_app, "gemini_generate_quiz", return_value=None):
            r = logged_in_client.post("/interview/generate", data={"topic": "Python Developer"})
        data = json.loads(r.data)
        assert "error" in data


# ── Interview Save Tests ───────────────────────────────────────

class TestInterviewSave:
    def test_save_valid_score_inserts_to_db(self, logged_in_client):
        """Valid score submission should insert a record and return ok: true."""
        r = logged_in_client.post("/interview/save",
                                  data={"topic": "Python", "score": "8", "total": "10"})
        data = json.loads(r.data)
        assert data["ok"] is True

    def test_save_score_persists_to_database(self, app, logged_in_client):
        """After saving, the record should appear in quiz_results."""
        logged_in_client.post("/interview/save",
                              data={"topic": "Flask", "score": "7", "total": "10"})
        with app.app_context():
            with flask_app.get_db() as db:
                row = db.execute("SELECT * FROM quiz_results WHERE topic = 'Flask'").fetchone()
        assert row is not None
        assert row["score"] == 7.0

    def test_save_requires_login(self, client):
        """Unauthenticated save should redirect, not insert."""
        r = client.post("/interview/save",
                        data={"topic": "Python", "score": "5", "total": "10"})
        assert r.status_code == 302


# ── CV Improve Validation Tests ────────────────────────────────

class TestCVImprove:
    def test_empty_text_returns_error_json(self, logged_in_client):
        """Empty CV text should return an error without calling Gemini."""
        r = logged_in_client.post("/cv/improve", data={"text": "", "type": "summary"})
        data = json.loads(r.data)
        assert "Please write" in data["improved"]

    def test_valid_text_calls_gemini_and_returns_improved(self, logged_in_client):
        """Valid text should call Gemini and return the improved version."""
        with mock.patch.object(flask_app, "gemini_improve_cv_text", return_value="Improved text."):
            r = logged_in_client.post("/cv/improve",
                                      data={"text": "I did some stuff.", "type": "summary"})
        data = json.loads(r.data)
        assert data["improved"] == "Improved text."

    def test_cv_improve_requires_login(self, client):
        """Unauthenticated request should redirect."""
        r = client.post("/cv/improve", data={"text": "hello", "type": "summary"})
        assert r.status_code == 302


# ── Cover Letter Validation Tests ─────────────────────────────

class TestCoverLetter:
    def test_missing_required_fields_returns_error_json(self, logged_in_client):
        """Missing job title, company, or JD should return a JSON error."""
        r = logged_in_client.post("/cover-letter/generate",
                                  data={"name": "John", "jobtitle": "", "company": "", "jd": "", "skills": ""})
        data = json.loads(r.data)
        assert "fill in" in data["letter"].lower()

    def test_valid_fields_calls_gemini(self, logged_in_client):
        """All required fields present should call Gemini and return a letter."""
        with mock.patch.object(flask_app, "gemini_cover_letter", return_value="Dear Hiring Manager..."):
            r = logged_in_client.post("/cover-letter/generate",
                                      data={"name": "Jane", "jobtitle": "Engineer",
                                            "company": "Acme", "jd": "Build things.", "skills": "Python"})
        data = json.loads(r.data)
        assert "Dear Hiring Manager" in data["letter"]

    def test_cover_letter_requires_login(self, client):
        """Unauthenticated request should redirect."""
        r = client.post("/cover-letter/generate",
                        data={"jobtitle": "Dev", "company": "X", "jd": "stuff"})
        assert r.status_code == 302