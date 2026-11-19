"""Tests for UUID account-code signup, sign-in and recovery."""

from pathlib import Path

import pytest
from flask import Flask
from flask_login import LoginManager

from users.users.models import db, User, UserExerciseState
from webapp.extensions import limiter
from webapp.routes import routes_bp
from webapp.routes.authorization import normalize_account_id

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = "12345678-1234-5678-9abc-def012345678"


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

    limiter.init_app(app)
    app.register_blueprint(routes_bp)

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def make_user(account_id=CANONICAL, email=None):
    user = User(account_id=account_id, email=email)
    db.session.add(user)
    db.session.commit()
    return user


@pytest.mark.parametrize(
    "raw",
    [
        CANONICAL,
        CANONICAL.upper(),
        CANONICAL.replace("-", ""),
        "  " + CANONICAL.replace("-", " ") + "  ",
    ],
)
def test_normalize_account_id_accepts_common_formats(raw):
    assert normalize_account_id(raw) == CANONICAL


@pytest.mark.parametrize("raw", [None, "", "   ", "abc", "12345678-1234"])
def test_normalize_account_id_rejects_invalid_values(raw):
    assert normalize_account_id(raw) is None


def test_signup_creates_uuid_account_and_redirects_to_acknowledgement(client, app):
    response = client.post("/signup")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/account/created")

    with app.app_context():
        user = User.query.one()
        assert len(user.account_id) == 36
        assert normalize_account_id(user.account_id) == user.account_id
        assert user.email is None

    page = client.get("/account/created")
    assert page.status_code == 200
    assert b"account code" in page.data.lower()

    acknowledged = client.post("/account/created")
    assert acknowledged.status_code == 302

    with app.app_context():
        from users.users.models import UserSettings

        settings = db.session.get(UserSettings, User.query.one().id)
        assert settings.settings["account_code_acknowledged"] is True


def test_signin_with_valid_code_logs_user_in(client, app):
    make_user()

    response = client.post(
        "/signin",
        data={"account_id": CANONICAL.replace("-", "").upper()},
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")


def test_signin_with_invalid_code_shows_error(client):
    response = client.post(
        "/signin",
        data={"account_id": "not-a-real-code"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Invalid account code." in response.data


def test_signin_merges_anonymous_progress(client, app):
    user = make_user()

    with client.session_transaction() as web_session:
        web_session["genus"] = {"1": {"progress": [1], "falses": []}}

    response = client.post("/signin", data={"account_id": CANONICAL})
    assert response.status_code == 302

    with app.app_context():
        state = UserExerciseState.query.filter_by(
            user_id=user.id, unit="genus", exercise=1
        ).one()
        assert state.state["correct_nrs"] == [1]


def test_recovery_email_sends_account_code(client, app, monkeypatch):
    user = make_user(email="recover@example.com")
    sent = []

    import webapp.routes.authorization as authorization

    def fake_send(to_email, account_id):
        sent.append((to_email, account_id))

    monkeypatch.setattr(authorization, "send_account_id_email", fake_send)

    response = client.post(
        "/recover-account",
        data={"email": "recover@example.com"},
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/signin")
    assert sent == [("recover@example.com", user.account_id)]


def test_recovery_without_email_is_non_revealing(client):
    make_user(email=None)

    response = client.post(
        "/recover-account",
        data={"email": "missing@example.com"},
    )

    # Same redirect as the success case; the endpoint must not reveal whether
    # an email address is on file.
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/signin")

    followed = client.post(
        "/recover-account",
        data={"email": "missing@example.com"},
        follow_redirects=True,
    )

    assert b"If that email is on file" in followed.data
    assert b"No recovery email on file" not in followed.data
