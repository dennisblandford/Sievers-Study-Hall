"""
Regression tests for empty answer submissions.

Pressing Enter in an empty answer field must not silently advance to a new
question. The submission is treated as "unknown": the answer is revealed on the
feedback page and the question is recorded as incorrect.
"""

from pathlib import Path

import pytest
from flask import Flask
from flask_login import LoginManager

from users.users.models import User, db
from webapp.routes import routes_bp

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def app():
    app = Flask(
        __name__,
        template_folder=str(ROOT / "webapp/templates"),
        static_folder=str(ROOT / "webapp/static"),
    )
    app.config.update(
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SECRET_KEY="test-secret",
        TESTING=True,
    )

    db.init_app(app)

    login_manager = LoginManager(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    app.register_blueprint(routes_bp)

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def test_empty_answer_is_incorrect_even_when_expected_answer_is_empty(client):
    # praepositionen 5, Nr 186 has an empty expected answer ("no preposition").
    # An empty submission used to match it and silently register the question
    # as correct, advancing to a new question.
    response = client.post(
        "/check/praepositionen/exercise/5",
        data={"answer": "", "nr": "186"},
    )

    assert response.status_code == 302
    assert "/feedback/unit/praepositionen/exercise/5" in response.headers["Location"]

    with client.session_transaction() as session:
        assert "186" in session["praepositionen"]["5"]["falses"]
        assert "186" not in session["praepositionen"]["5"]["progress"]
        assert session["feedback"]["result"] == "incorrect"


def test_empty_answer_shows_feedback_when_feedback_is_disabled(client):
    with client.session_transaction() as session:
        session["settings"] = {"feedback_enabled": False}

    response = client.post(
        "/check/genus/exercise/1",
        data={"answer": "   ", "nr": "1"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Incorrect" in response.data
    assert b"das Jahr" in response.data  # the correct answer for Nr 1 is revealed

    with client.session_transaction() as session:
        assert "1" in session["genus"]["1"]["falses"]
        assert "1" not in session["genus"]["1"]["progress"]


def test_empty_prompt_is_not_sent_to_the_model(client, monkeypatch):
    import webapp.routes.exercises as exercises_routes

    def fail_if_called(*args, **kwargs):
        raise AssertionError("the grading model must not be called for an empty answer")

    monkeypatch.setattr(exercises_routes, "get_response_from_prompt", fail_if_called)

    # praepositionen 6, Nr 196 is a prompt exercise.
    response = client.post(
        "/check/praepositionen/exercise/6",
        data={"answer": "  ", "nr": "196"},
    )

    assert response.status_code == 302
    assert "/feedback/unit/praepositionen/exercise/6" in response.headers["Location"]

    with client.session_transaction() as session:
        assert "196" in session["praepositionen"]["6"]["falses"]
        assert "196" not in session["praepositionen"]["6"]["progress"]
        assert session["feedback"]["result"] == "incorrect"
