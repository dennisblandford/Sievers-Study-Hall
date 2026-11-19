"""
Query-count regression tests for the per-request exercise-state cache.

These guard the N+1 fixes: progress/score/finished lookups for authenticated
users must reuse a single cached query per request instead of issuing one query
per exercise.
"""

import pytest
from flask import Flask
from flask_login import LoginManager, login_user

from users.users.models import db, User, UserExerciseState, UserUnitHomeProgress
from users.progress.progress import compute_answered_questions_exercise, get_progress_home_page
from users.progress.score import compute_score_exercise
from users.progress.is_exercise_finished import is_exercise_finished
from data.data_processing.total_questions import total_question_exercises
from data.data_processing.units import units

UNIT = "genus"


@pytest.fixture
def app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.secret_key = "test-secret"

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


def make_user(email):
    user = User(email=email)
    user.set_password("password")
    db.session.add(user)
    db.session.commit()
    return user


def make_state(user, unit, exercise, state, completed_at=None):
    row = UserExerciseState(
        user_id=user.id,
        unit=unit,
        exercise=exercise,
        state=state,
        completed_at=completed_at,
    )
    db.session.add(row)
    db.session.commit()
    return row


def count_state_queries(app):
    """Counts SELECT statements against the progress tables while in scope."""
    counter = {"n": 0}

    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        selects_progress = "user_exercise_state" in statement or "user_unit_home_progress" in statement
        if selects_progress and statement.strip().upper().startswith("SELECT"):
            counter["n"] += 1

    from sqlalchemy import event

    engine = db.engine
    event.listen(engine, "before_cursor_execute", before_cursor_execute)
    try:
        yield counter
    finally:
        event.remove(engine, "before_cursor_execute", before_cursor_execute)


def test_progress_score_and_finished_reuse_one_query(app):
    user = make_user("queries@example.com")
    for exercise in range(1, 6):
        make_state(user, UNIT, exercise, {"correct_nrs": [1]})

    gen = count_state_queries(app)
    counter = next(gen)

    with app.test_request_context():
        login_user(user)
        for exercise in range(1, 6):
            compute_answered_questions_exercise({}, UNIT, exercise)
            compute_score_exercise({}, UNIT, exercise)
            is_exercise_finished({}, UNIT, exercise)

    next(gen, None)

    # One query to populate the cache, then all lookups are in-memory.
    assert counter["n"] == 1


def test_is_exercise_finished_uses_completed_at(app):
    user = make_user("done@example.com")
    make_state(user, UNIT, 1, {}, completed_at=__import__("datetime").datetime.now())

    with app.test_request_context():
        login_user(user)
        assert is_exercise_finished({}, UNIT, 1) is True


def test_is_exercise_finished_when_all_questions_answered(app):
    user = make_user("all@example.com")
    total = total_question_exercises[UNIT][1]
    make_state(user, UNIT, 1, {"correct_nrs": list(range(1, total + 1))})

    with app.test_request_context():
        login_user(user)
        assert is_exercise_finished({}, UNIT, 1) is True


def test_is_exercise_finished_partial_progress(app):
    user = make_user("partial@example.com")
    make_state(user, UNIT, 1, {"correct_nrs": [1]})

    with app.test_request_context():
        login_user(user)
        assert is_exercise_finished({}, UNIT, 1) is False


def test_is_exercise_finished_without_state(app):
    user = make_user("empty@example.com")

    with app.test_request_context():
        login_user(user)
        assert is_exercise_finished({}, UNIT, 1) is False


def test_home_progress_reuses_one_query_for_all_units(app):
    user = make_user("home@example.com")
    row = UserUnitHomeProgress(user_id=user.id, unit=UNIT, completed_exercises=3)
    db.session.add(row)
    db.session.commit()

    gen = count_state_queries(app)
    counter = next(gen)

    with app.test_request_context():
        login_user(user)
        for unit in units:
            get_progress_home_page({}, unit)

    next(gen, None)

    # The home page asks for every unit; the cache answers all but the first.
    assert counter["n"] == 1

