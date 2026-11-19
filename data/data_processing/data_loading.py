from data.data_processing.paths import df_units
from data.data_processing.pre_processing import pre_processing, get_person_columns

# ---------------------------------------------------------------------------
# In-process data caches
#
# Loading an exercise used to re-filter the unit DataFrame, copy it, run the
# (previously row-by-row) preprocessing and fill NaNs on *every* call. A single
# exercise page render fans out into several of these calls, and the completed
# exercise page could trigger dozens of them. The parsed CSVs never change at
# runtime, so the results can be computed once and reused for the lifetime of
# the worker.
#
# IMPORTANT: the objects returned from these helpers are shared. Treat them as
# read-only. Callers that need to mutate should filter/copy first (which is
# what the existing code already does).
# ---------------------------------------------------------------------------

_UNIT_CACHE = {}
_EXERCISE_CACHE = {}
# (unit, exercise) -> {Nr(int): {column: value}}
_QUESTION_CACHE = {}


def _normalize_exercise(exercise):
    try:
        return int(exercise)
    except (TypeError, ValueError):
        return exercise


def load_data_unit(unit):
    data = _UNIT_CACHE.get(unit)

    if data is None:
        data = df_units[unit].fillna("")
        data = data[data["exercise"] < 1000].copy()
        _UNIT_CACHE[unit] = data

    return data


def load_data_exercise(unit, exercise):
    """
    Loads and preprocesses exercise data for a given unit and exercise.

    The result is cached per (unit, exercise) for the lifetime of the process,
    so repeated calls (which happen several times per request) are O(1) instead
    of re-filtering and re-preprocessing the whole unit DataFrame.
    """
    exercise = _normalize_exercise(exercise)
    key = (unit, exercise)

    data = _EXERCISE_CACHE.get(key)

    if data is None:
        raw = df_units[unit]
        data = raw[raw['exercise'] == exercise].copy()
        data = pre_processing(data, unit, exercise)
        data = data.fillna("")
        _EXERCISE_CACHE[key] = data

    return data


def count_data_exercise(unit, exercise):
    """
    Returns the number of questions an exercise produces *without* building the
    long-form DataFrame.

    This mirrors ``pre_processing`` (which multiplies each source row by the
    number of person columns for conjugation units) so counts can be derived
    from the raw unit frame in O(rows) instead of preprocessing every exercise
    just to measure it.
    """
    exercise = _normalize_exercise(exercise)
    raw = df_units[unit]
    count = int((raw['exercise'] == exercise).sum())

    persons = get_person_columns(unit, exercise)
    if persons is not None:
        present_persons = [person for person in persons if person in raw.columns]
        count *= len(present_persons)

    return count


def load_data_question(unit, exercise, question_id):
    """
    Returns a single question as a plain ``{column: value}`` dict, or ``None``.

    The old implementation filtered the fully loaded exercise DataFrame on every
    call. We now build an ``Nr -> row`` index once per (unit, exercise) so the
    lookup is O(1) and doesn't allocate a pandas Series.
    """
    try:
        question_id = int(question_id)
    except (ValueError, TypeError):
        return None

    exercise = _normalize_exercise(exercise)
    key = (unit, exercise)

    index = _QUESTION_CACHE.get(key)

    if index is None:
        df = load_data_exercise(unit, exercise)
        index = {
            int(nr): row
            for nr, row in zip(df["Nr"], df.to_dict(orient="records"))
        }
        _QUESTION_CACHE[key] = index

    return index.get(question_id)


def load_question_text(unit, exercise, question_id):
    question_data = load_data_question(unit, exercise, question_id)

    if question_data is None:
        return None

    else:
        return question_data["question"]
