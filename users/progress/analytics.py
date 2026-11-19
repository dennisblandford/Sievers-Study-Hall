"""Aggregate answer-attempt analytics for the ``/stats`` page.

Each metric is computed with a single aggregate query and cached on ``flask.g``
for the rest of the request, mirroring ``exercise_state_cache``. Anonymous
visitors get no database-backed analytics (ET1).
"""

from datetime import datetime, timedelta, timezone

from flask import g
from flask_login import current_user
from sqlalchemy import case, func

from data.data_processing.data_loading import load_data_question
from users.users.models import AnswerAttempt, db

# ET4: keep attempt history indefinitely for now. Set this to an int (days) in
# the future if a pruning job is introduced.
RETENTION_DAYS = None


def _cutoff(days):
    return datetime.now(timezone.utc) - timedelta(days=int(days))


def _cache():
    cache = getattr(g, "_analytics_cache", None)

    if cache is None:
        cache = {}
        g._analytics_cache = cache

    return cache


def _cached(name, params, compute):
    key = (current_user.id, name, params)
    cache = _cache()

    if key not in cache:
        cache[key] = compute()

    return cache[key]


def _accuracy_expression():
    return func.sum(
        case((AnswerAttempt.is_correct.is_(True), 1), else_=0)
    )


def get_accuracy_trend(days=30):
    """Return ``[{day, total, correct}]`` accuracy buckets for the period."""
    if not current_user.is_authenticated:
        return []

    days = int(days)

    def compute():
        # Daily buckets for short windows, weekly buckets for long ones.
        if days >= 90:
            bucket = func.strftime("%Y-%W", AnswerAttempt.created_at)
        else:
            bucket = func.date(AnswerAttempt.created_at)

        rows = (
            db.session.query(
                bucket.label("day"),
                func.count(AnswerAttempt.id).label("total"),
                _accuracy_expression().label("correct"),
            )
            .filter(
                AnswerAttempt.user_id == current_user.id,
                AnswerAttempt.created_at >= _cutoff(days),
            )
            .group_by(bucket)
            .order_by(bucket)
            .all()
        )

        return [
            {
                "day": str(row.day),
                "total": int(row.total or 0),
                "correct": int(row.correct or 0),
            }
            for row in rows
        ]

    return _cached("accuracy_trend", (days,), compute)


def _error_rate_rows(days, min_attempts, by_exercise):
    days = int(days)
    min_attempts = int(min_attempts)

    def compute():
        group_columns = [AnswerAttempt.unit]
        if by_exercise:
            group_columns.append(AnswerAttempt.exercise)

        attempts = func.count(AnswerAttempt.id)
        errors = func.sum(
            case((AnswerAttempt.is_correct.is_(False), 1), else_=0)
        )

        rows = (
            db.session.query(
                *group_columns,
                attempts.label("attempts"),
                errors.label("errors"),
            )
            .filter(
                AnswerAttempt.user_id == current_user.id,
                AnswerAttempt.created_at >= _cutoff(days),
            )
            .group_by(*group_columns)
            .having(attempts >= min_attempts)
            .all()
        )

        result = []
        for row in rows:
            attempt_count = int(row.attempts or 0)
            error_count = int(row.errors or 0)
            item = {
                "unit": row.unit,
                "attempts": attempt_count,
                "errors": error_count,
                "error_rate": (error_count / attempt_count) if attempt_count else 0.0,
            }
            if by_exercise:
                item["exercise"] = int(row.exercise)
            result.append(item)

        result.sort(
            key=lambda item: (-item["error_rate"], -item["attempts"], item["unit"])
        )
        return result

    name = "error_rate_exercise" if by_exercise else "error_rate_unit"
    return _cached(name, (days, min_attempts), compute)


def get_error_rate_by_unit(days=30, min_attempts=5):
    """Return per-unit ``{unit, attempts, errors, error_rate}`` rows."""
    if not current_user.is_authenticated:
        return []

    return _error_rate_rows(days, min_attempts, by_exercise=False)


def get_error_rate_by_exercise(days=30, min_attempts=5):
    """Return the per-exercise variant of :func:`get_error_rate_by_unit`."""
    if not current_user.is_authenticated:
        return []

    return _error_rate_rows(days, min_attempts, by_exercise=True)


def get_most_missed_questions(days=90, limit=10):
    """Return the most frequently missed questions, with their text."""
    if not current_user.is_authenticated:
        return []

    days = int(days)
    limit = int(limit)

    def compute():
        errors = func.count(AnswerAttempt.id)
        rows = (
            db.session.query(
                AnswerAttempt.unit,
                AnswerAttempt.exercise,
                AnswerAttempt.question_nr,
                errors.label("errors"),
            )
            .filter(
                AnswerAttempt.user_id == current_user.id,
                AnswerAttempt.is_correct.is_(False),
                AnswerAttempt.created_at >= _cutoff(days),
            )
            .group_by(
                AnswerAttempt.unit,
                AnswerAttempt.exercise,
                AnswerAttempt.question_nr,
            )
            .order_by(
                errors.desc(),
                AnswerAttempt.unit,
                AnswerAttempt.exercise,
                AnswerAttempt.question_nr,
            )
            .limit(limit)
            .all()
        )

        result = []
        for row in rows:
            try:
                question = load_data_question(
                    row.unit, row.exercise, row.question_nr
                ) or {}
            except Exception:
                question = {}

            result.append({
                "unit": row.unit,
                "exercise": int(row.exercise),
                "question_nr": int(row.question_nr),
                "errors": int(row.errors or 0),
                "question": question.get("question", ""),
                "answer": question.get("answer", ""),
            })

        return result

    return _cached("most_missed", (days, limit), compute)


def get_first_attempt_accuracy(days=30):
    """Return first-attempt ``{total, correct, accuracy, by_unit}`` stats."""
    if not current_user.is_authenticated:
        return None

    days = int(days)

    def compute():
        total = func.count(AnswerAttempt.id)
        correct = _accuracy_expression()

        rows = (
            db.session.query(
                AnswerAttempt.unit,
                total.label("total"),
                correct.label("correct"),
            )
            .filter(
                AnswerAttempt.user_id == current_user.id,
                AnswerAttempt.is_first_attempt.is_(True),
                AnswerAttempt.created_at >= _cutoff(days),
            )
            .group_by(AnswerAttempt.unit)
            .all()
        )

        by_unit = []
        total_all = 0
        correct_all = 0

        for row in rows:
            unit_total = int(row.total or 0)
            unit_correct = int(row.correct or 0)
            total_all += unit_total
            correct_all += unit_correct
            by_unit.append({
                "unit": row.unit,
                "total": unit_total,
                "correct": unit_correct,
                "accuracy": (unit_correct / unit_total) if unit_total else 0.0,
            })

        by_unit.sort(key=lambda item: (item["accuracy"], -item["total"]))

        return {
            "total": total_all,
            "correct": correct_all,
            "accuracy": (correct_all / total_all) if total_all else 0.0,
            "by_unit": by_unit,
        }

    return _cached("first_attempt", (days,), compute)
