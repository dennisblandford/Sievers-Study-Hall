"""Tests for recording and resetting per-question answer attempts."""

from pathlib import Path

import pytest
from flask import Flask
from flask_login import LoginManager, login_user

from users.progress.attempts import record_answer_attempt
from users.users.models import AnswerAttempt, User, UserExerciseState, db
from webapp.extensions import limiter
from webapp.routes import routes_bp

ROOT = Path(__file__).resolve().parents[1]
UNIT = "genus"


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


def make_user(account_id="attempts-user"):
    user = User(account_id=account_id)
    db.session.add(user)
    db.session.commit()
    return user


def make_state(user, unit, exercise, state):
    row = UserExerciseState(
        user_id=user.id, unit=unit, exercise=exercise, state=state
    )
    db.session.add(row)
    db.session.commit()
    return row


def login_client(client, user):
    with client.session_transaction() as web_session:
        web_session["_user_id"] = str(user.id)
        web_session["_fresh"] = True


def test_record_answer_attempt_marks_first_attempt(app):
    user = make_user()

    with app.test_request_context():
        login_user(user)
        record_answer_attempt({}, UNIT, 1, 1, "das", True)
        db.session.commit()

        attempt = AnswerAttempt.query.one()
        assert attempt.user_id == user.id
        assert attempt.unit == UNIT
        assert attempt.exercise == 1
        assert attempt.question_nr == 1
        assert attempt.is_correct is True
        assert attempt.is_first_attempt is True
        assert attempt.user_answer == "das"


def test_record_answer_attempt_marks_retry(app):
    user = make_user()
    make_state(user, UNIT, 1, {"correct_nrs": [1], "incorrect": {}})

    with app.test_request_context():
        login_user(user)
        record_answer_attempt({}, UNIT, 1, 1, "das", True)
        record_answer_attempt({}, UNIT, 1, 2, "der", False)
        db.session.commit()

        attempts = AnswerAttempt.query.order_by(AnswerAttempt.id).all()
        assert [a.is_first_attempt for a in attempts] == [False, True]


def test_record_answer_attempt_skips_anonymous_users(app):
    with app.test_request_context():
        record_answer_attempt({}, UNIT, 1, 1, "das", True)
        db.session.commit()

        assert AnswerAttempt.query.count() == 0


def test_empty_answer_is_recorded_for_authenticated_user(app, client):
    user = make_user()
    login_client(client, user)

    response = client.post(
        "/check/genus/exercise/1",
        data={"answer": "   ", "nr": "1"},
    )

    assert response.status_code == 302

    with app.app_context():
        attempt = AnswerAttempt.query.one()
        assert attempt.user_id == user.id
        assert attempt.question_nr == 1
        assert attempt.is_correct is False
        assert attempt.is_first_attempt is True


def test_reset_exercise_deletes_attempt_history(app, client):
    user = make_user()
    make_state(user, UNIT, 1, {"correct_nrs": [1]})

    with app.app_context():
        db.session.add_all([
            AnswerAttempt(
                user_id=user.id, unit=UNIT, exercise=1, question_nr=1,
                is_correct=True, is_first_attempt=True, user_answer="das",
            ),
            AnswerAttempt(
                user_id=user.id, unit=UNIT, exercise=1, question_nr=2,
                is_correct=False, is_first_attempt=True, user_answer="der",
            ),
            AnswerAttempt(
                user_id=user.id, unit=UNIT, exercise=2, question_nr=1,
                is_correct=True, is_first_attempt=True, user_answer="die",
            ),
        ])
        db.session.commit()

    login_client(client, user)

    response = client.post(f"/reset/{UNIT}/exercise/1")
    assert response.status_code == 302

    with app.app_context():
        assert UserExerciseState.query.filter_by(
            user_id=user.id, unit=UNIT, exercise=1
        ).count() == 0

        remaining = AnswerAttempt.query.order_by(AnswerAttempt.id).all()
        assert [(a.unit, a.exercise) for a in remaining] == [(UNIT, 2)]
