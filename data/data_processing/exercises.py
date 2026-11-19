import os

import pandas as pd

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
EXERCISES_PATH = os.path.join(BASE_DIR, "datasets/other", "exercises.csv")
df_exercises = pd.read_csv(EXERCISES_PATH)

levels = ["A1", "A2", "B1", "B2", "C1", "C2",]

isolation = 'isolation'
context = 'context'
synonym = 'synonym'
antonym = 'antonym'

word_order = 'word_order'
prompt = 'prompt'

# (unit, exercise) -> {"level", "category", "subcategory"}
# Built once so the very common per-page lookups below avoid re-filtering the
# full 1.5k-row DataFrame on every call.
_EXERCISE_META = {}
for _row in df_exercises.itertuples(index=False):
    try:
        _exercise = int(_row.exercise)
    except (TypeError, ValueError):
        _exercise = _row.exercise
    _EXERCISE_META[(_row.unit, _exercise)] = {
        "level": _row.level,
        "category": _row.category,
        "subcategory": _row.subcategory,
    }


def _get_meta(unit, exercise):
    try:
        exercise = int(exercise)
    except (TypeError, ValueError):
        pass
    return _EXERCISE_META.get((unit, exercise))


def get_level_from_exercise(unit, exercise, df=df_exercises):
    if df is df_exercises:
        meta = _get_meta(unit, exercise)
        return meta["level"] if meta else "N/A"

    result = df[(df['unit'] == unit) & (df['exercise'] == exercise)]
    if not result.empty:
        return result.iloc[0]['level']
    return "N/A"


def get_exercises_by_level(level, df_level=df_exercises):
    """
    Returns a dataframe filtered by unit and level.
    If no rows match, returns None.
    """

    df_filtered = df_level[(df_level["level"] == level)]

    if df_filtered.empty:
        return None

    return df_filtered


def get_exercises_by_unit_and_level(unit, level, df_level=df_exercises):
    """
    Returns a dataframe filtered by unit and level.
    If no rows match, returns None.
    """

    df_filtered = df_level[
        (df_level["unit"] == unit) &
        (df_level["level"] == level)
    ]

    if df_filtered.empty:
        return None

    return df_filtered


def is_exercise_input(unit, exercise):
    meta = _get_meta(unit, exercise)
    return bool(meta and meta["category"] == 'input')


def is_exercise_synonym(unit, exercise):
    meta = _get_meta(unit, exercise)
    return bool(meta and meta["subcategory"] == 'synonym')


def is_exercise_word_order(unit, exercise):
    meta = _get_meta(unit, exercise)
    return bool(meta and meta["category"] == 'word_order')


def is_exercise_prompt(unit, exercise):
    meta = _get_meta(unit, exercise)
    return bool(meta and meta["category"] == 'prompt')


def does_unit_exercise_exist(unit, exercise, df=df_exercises):
    """
    Returns True if (unit, exercise) exists in df_exercises.
    """
    if df is df_exercises:
        return _get_meta(unit, exercise) is not None

    return (
        ((df["unit"] == unit) &
         (df["exercise"] == int(exercise)))
        .any()
    )


def get_category_from_exercise(unit, exercise, df=df_exercises):
    if df is df_exercises:
        meta = _get_meta(unit, exercise)
        return meta["category"] if meta else "N/A"

    result = df[(df['unit'] == unit) & (df['exercise'] == exercise)]
    if not result.empty:
        return result.iloc[0]['category']
    return "N/A"


def get_subcategory_from_exercise(unit, exercise, df=df_exercises):
    if df is df_exercises:
        meta = _get_meta(unit, exercise)
        return meta["subcategory"] if meta else "N/A"

    result = df[(df['unit'] == unit) & (df['exercise'] == exercise)]
    if not result.empty:
        return result.iloc[0]['subcategory']
    return "N/A"
