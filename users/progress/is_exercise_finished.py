from flask_login import current_user

from data.data_processing.data_loading import load_data_exercise
from data.data_processing.total_questions import total_question_exercises

from users.progress.exercise_state_cache import get_user_exercise_states
from users.session_management.verification_session import is_key_in_exercise


def is_exercise_finished(session, unit, exercise):
    """
    Determines whether a given exercise has been completed by the user.

    The exercise is considered finished if:
    - All question IDs in the data match those stored in session['progress'].
    - OR no more questions are available to pick.
    - OR a 'result' key exists in the session for that unit and exercise.

    Args:
        session (dict): The session dictionary tracking user progress.
        unit (str): The unit identifier.
        exercise (str or int): The exercise identifier (converted to string for lookup).

    Returns:
        bool: True if the exercise is complete, False otherwise.
    """
    ex_int = int(exercise) if not isinstance(exercise, int) else exercise
    total = total_question_exercises[unit][ex_int]

    # An exercise with no questions is trivially "finished" (equivalent to
    # pick_a_question returning None).
    if total == 0:
        return True

    if current_user.is_authenticated:
        row = get_user_exercise_states(current_user.id).get((unit, ex_int))
        if row and row.completed_at:
            return True

        # No stored state means nothing has been answered yet.
        if not row or not row.state:
            return False

        # Equivalent to "pick_a_question would return None": every Nr has
        # already been answered. Uses the cheap count instead of loading the
        # exercise data for every exercise in the unit.
        correct_nrs = row.state.get("correct_nrs") or []
        return len(set(correct_nrs)) >= total

    # Anonymous users: nothing stored for this exercise -> not finished.
    if is_key_in_exercise(session, unit, exercise, 'result'):
        return True

    if not is_key_in_exercise(session, unit, exercise, 'progress'):
        return False

    data = load_data_exercise(unit, exercise)

    answered_nrs = set(session[unit][str(exercise)]['progress'])

    return set(data["Nr"].astype(str)) == answered_nrs
