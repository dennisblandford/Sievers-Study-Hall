"""Persistence helpers for per-question answer attempts."""

from flask_login import current_user

from users.progress.exercise_state_cache import get_user_exercise_states
from users.users.models import AnswerAttempt, db


def _is_first_attempt(state, nr):
    """Return True when ``nr`` has not been answered before in this exercise."""
    state = state or {}
    correct_nrs = state.get("correct_nrs") or []
    incorrect = state.get("incorrect") or {}

    return (
        nr not in correct_nrs
        and str(nr) not in correct_nrs
        and nr not in incorrect
        and str(nr) not in incorrect
    )


def record_answer_attempt(session, unit, exercise, nr, user_answer, is_correct):
    """Queue an :class:`AnswerAttempt` for every authenticated submission.

    Anonymous visitors are deliberately not persisted (ET1); their reduced
    statistics live only in the session. The caller owns the transaction, so no
    commit happens here.
    """
    if not current_user.is_authenticated:
        return

    exercise = int(exercise)
    nr = int(nr)

    row = get_user_exercise_states(current_user.id).get((unit, exercise))
    state = (row.state if row and row.state else {}) or {}

    db.session.add(AnswerAttempt(
        user_id=current_user.id,
        unit=unit,
        exercise=exercise,
        question_nr=nr,
        is_correct=bool(is_correct),
        is_first_attempt=_is_first_attempt(state, nr),
        user_answer=user_answer,
    ))
