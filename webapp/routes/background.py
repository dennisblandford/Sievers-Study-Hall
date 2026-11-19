from flask import session, g
from flask_login import current_user
from typing import cast

from . import routes_bp

from data.data_processing.units import units

from users.session_management.logging import log_progress_deleted_from_session
from users.session_management.print_session import session_size
from users.session_management.print_session import print_complete_session, print_session_size, print_user_info_from_db
from users.session_management.verification_session import is_key_in_session

session = cast(dict, session)


def _current_session_size():
    """
    Returns the serialized session size for this request, computing it once.

    ``session_size`` json-dumps the whole session; the cleanup hooks below all
    need the same value, so we reuse one measurement per request instead of
    serializing the session three times.
    """
    size = getattr(g, "_session_size_bytes", None)
    if size is None:
        size = session_size(session)
        g._session_size_bytes = size
    return size


@routes_bp.before_request
def ensure_session_keys_exist_and_make_session_permanent():
    session.permanent = True

    if 'unfinished_exercise' not in session:
        session['unfinished_exercise'] = []

    # print_complete_session(session)
    # print_session_size(session)
    # print_user_info_from_db()
    # session.clear()


@routes_bp.before_request
def clear_progress_for_unconnected_users():
    if not current_user.is_authenticated:
        if _current_session_size() > 3000:
            if is_key_in_session(session, 'progress'):
                session.pop('progress')
                # The session changed; let the next hook measure it again.
                g.pop('_session_size_bytes', None)


@routes_bp.before_request
def delete_old_unfinished_exercise():
    if _current_session_size() > 3500:
        if not session['unfinished_exercise']:
            keys_to_keep = {"_user_id", "_fresh", "_id", "csrf_token"}
            for key in list(session.keys()):
                if key not in keys_to_keep:
                    session.pop(key, None)
            # session.clear()
        else:
            unit, exercise = session['unfinished_exercise'][0]
            if unit in session and str(exercise) in session[unit]:
                log_progress_deleted_from_session(unit, exercise)
                del session[unit][str(exercise)]

            session['unfinished_exercise'].remove((unit, exercise))
            session['popup'] = {'unit': unit, 'exercise': exercise}

        # print(f"Progress deleted for {unit} {exercise}")


@routes_bp.app_context_processor
def inject_popup():
    return {"popup": session.pop("popup", None)}


@routes_bp.after_request
def clear_empty_unit_dictionary(response):
    if session_size(session) > 3000:
        # Iterate only the units/exercises actually present in the session
        # instead of scanning all units × 100 possible exercises.
        for unit in list(session.keys()):
            if unit not in units:
                continue

            unit_dict = session.get(unit)
            if not isinstance(unit_dict, dict):
                continue

            for exercise_key in list(unit_dict.keys()):
                try:
                    exercise_int = int(exercise_key)
                except (TypeError, ValueError):
                    continue

                # Preserve the previous behaviour of only cleaning 0..99.
                if exercise_int >= 100:
                    continue

                exercise_data = unit_dict.get(exercise_key)
                if not isinstance(exercise_data, dict):
                    continue

                if ('progress' in exercise_data
                        and len(exercise_data['progress']) == 0
                        and 'result' not in exercise_data):
                    unit_dict.pop(exercise_key, None)

            if not unit_dict:
                session.pop(unit, None)
    return response
