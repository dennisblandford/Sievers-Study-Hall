"""Tests for the aggregate analytics used by the ``/stats`` page."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from flask import Flask
from flask_login import LoginManager, login_user

from users.progress.analytics import (
    get_accuracy_trend,
    get_error_rate_by_exercise,
    get_error_rate_by_unit,
    get_first_attempt_accuracy,
    get_most_missed_questions,
)
from users.users.models import AnswerAttempt, User, db

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

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def make_user(account_id="analytics-user"):
    user = User(account_id=account_id)
    db.session.add(user)
    db.session.commit()
    return user


def make_attempt(user, *, unit=UNIT, exercise=1, question_nr=1,
                 is_correct=True, is_first_attempt=True, created_at=None,
                 user_answer="answer"):
    attempt = AnswerAttempt(
        user_id=user.id,
        unit=unit,
        exercise=exercise,
        question_nr=question_nr,
        is_correct=is_correct,
        is_first_attempt=is_first_attempt,
        user_answer=user_answer,
        created_at=created_at or datetime.now(timezone.utc),
    )
    db.session.add(attempt)
    db.session.commit()
    return attempt


def test_accuracy_trend_buckets_by_day(app):
    user = make_user()
    now = datetime.now(timezone.utc)

    make_attempt(user, is_correct=True, created_at=now)
    make_attempt(user, is_correct=True, created_at=now)
    make_attempt(user, is_correct=False, created_at=now)
    make_attempt(user, is_correct=True, created_at=now - timedelta(days=60))

    with app.test_request_context():
        login_user(user)
        trend = get_accuracy_trend(days=30)

    assert trend == [
        {"day": now.date().isoformat(), "total": 3, "correct": 2},
    ]


def test_error_rate_by_unit_filters_small_samples(app):
    user = make_user()

    for index in range(6):
        make_attempt(user, exercise=1, is_correct=index >= 2)

    for _index in range(4):
        make_attempt(user, unit="artikel", exercise=1, is_correct=True)

    with app.test_request_context():
        login_user(user)
        rows = get_error_rate_by_unit(days=30, min_attempts=5)

    assert len(rows) == 1
    assert rows[0]["unit"] == UNIT
    assert rows[0]["attempts"] == 6
    assert rows[0]["errors"] == 2
    assert rows[0]["error_rate"] == pytest.approx(1 / 3)


def test_error_rate_by_exercise_variant(app):
    user = make_user()

    for index in range(5):
        make_attempt(user, exercise=1, is_correct=index >= 2)
    for _index in range(5):
        make_attempt(user, exercise=2, is_correct=True)

    with app.test_request_context():
        login_user(user)
        rows = get_error_rate_by_exercise(days=30, min_attempts=5)

    assert [row["exercise"] for row in rows] == [1, 2]
    assert rows[0]["errors"] == 2
    assert rows[0]["error_rate"] == pytest.approx(0.4)
    assert rows[1]["error_rate"] == 0.0


def test_most_missed_questions_sorted_and_decorated(app):
    user = make_user()

    make_attempt(user, question_nr=2, is_correct=False)
    make_attempt(user, question_nr=2, is_correct=False)
    make_attempt(user, question_nr=1, is_correct=False)
    make_attempt(user, question_nr=3, is_correct=True)

    with app.test_request_context():
        login_user(user)
        rows = get_most_missed_questions(days=90, limit=10)

    assert [row["question_nr"] for row in rows] == [2, 1]
    assert [row["errors"] for row in rows] == [2, 1]
    assert rows[0]["exercise"] == 1
    assert "question" in rows[0]


def test_first_attempt_accuracy(app):
    user = make_user()

    make_attempt(user, is_correct=True, is_first_attempt=True)
    make_attempt(user, is_correct=False, is_first_attempt=True)
    make_attempt(user, is_correct=True, is_first_attempt=False)

    with app.test_request_context():
        login_user(user)
        stats = get_first_attempt_accuracy(days=30)

    assert stats["total"] == 2
    assert stats["correct"] == 1
    assert stats["accuracy"] == pytest.approx(0.5)
    assert stats["by_unit"] == [{
        "unit": UNIT,
        "total": 2,
        "correct": 1,
        "accuracy": pytest.approx(0.5),
    }]


def test_analytics_are_cached_per_request(app):
    user = make_user()
    make_attempt(user, is_correct=True)

    counter = {"n": 0}

    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        if "answer_attempt" in statement and statement.strip().upper().startswith("SELECT"):
            counter["n"] += 1

    from sqlalchemy import event

    engine = db.engine
    event.listen(engine, "before_cursor_execute", before_cursor_execute)
    try:
        with app.test_request_context():
            login_user(user)
            for _ in range(2):
                get_accuracy_trend(30)
                get_error_rate_by_unit(30)
                get_most_missed_questions(90)
                get_first_attempt_accuracy(30)
    finally:
        event.remove(engine, "before_cursor_execute", before_cursor_execute)

    # One aggregate query per metric, no matter how often the page asks.
    assert counter["n"] == 4


def test_anonymous_analytics_are_empty(app):
    with app.test_request_context():
        assert get_accuracy_trend() == []
        assert get_error_rate_by_unit() == []
        assert get_error_rate_by_exercise() == []
        assert get_most_missed_questions() == []
        assert get_first_attempt_accuracy() is None
