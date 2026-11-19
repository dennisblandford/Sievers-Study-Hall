import os
import pandas as pd

from data.data_processing.data_loading import load_data_question

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SYNONYMS_PATH = os.path.join(BASE_DIR, "datasets/other", "synonyms.csv")
df_synonyms = pd.read_csv(SYNONYMS_PATH)

# (unit, output) -> [input, ...]
# The same lookup used to filter the whole synonyms CSV on every feedback
# render; it is now built once at import.
_SYNONYMS_BY_UNIT_AND_OUTPUT = {}
for _row in df_synonyms.itertuples(index=False):
    _SYNONYMS_BY_UNIT_AND_OUTPUT.setdefault((_row.unit, _row.output), []).append(_row.input)


def get_list_of_synonyms_for_feedback(correct_answer, unit, exercise, question_id, exercise_is_synonym=False, df=df_synonyms):
    """
    Retrieves the list of synonyms corresponding to a given main answer for a unit.

    Args:
        correct_answer (str): The main synonym to find associated variants for.
        unit (str): The unit used to filter the relevant entries.
        exercise: Current exercise id (used to exclude the prompt itself).
        question_id: Current question id (used to exclude the prompt itself).
        exercise_is_synonym (bool): Whether the exercise is a synonym exercise.
        df: Optional custom DataFrame (kept for backward compatibility).

    Returns:
        list: The matching synonym inputs.
    """
    if df is df_synonyms:
        filtered_inputs = list(_SYNONYMS_BY_UNIT_AND_OUTPUT.get((unit, correct_answer), []))

        if exercise_is_synonym:
            synonym_from_question = load_data_question(unit, exercise, question_id).get("question")
            filtered_inputs = [value for value in filtered_inputs if value != synonym_from_question]

        return filtered_inputs

    if exercise_is_synonym:
        synonym_from_question = load_data_question(unit, exercise, question_id).get("question")
        filtered = df[
            (df['unit'] == unit) &
            (df['output'] == correct_answer) &
            (df['input'] != synonym_from_question)
            ]
    else:
        filtered = df[
            (df['unit'] == unit) &
            (df['output'] == correct_answer)
            ]

    return filtered['input'].tolist()


def get_list_of_synonyms(correct_answer, unit, df=df_synonyms):
    """
    Retrieves the list of synonyms corresponding to a given main answer for a unit.

    Args:
        correct_answer (str): The main synonym to find associated variants for.
        unit (str): The unit used to filter the relevant entries.
        df: Optional custom DataFrame (kept for backward compatibility).

    Returns:
        list: ``[correct_answer]`` followed by the matching synonym inputs.
    """
    if df is df_synonyms:
        return [correct_answer] + list(_SYNONYMS_BY_UNIT_AND_OUTPUT.get((unit, correct_answer), []))

    filtered = df[(df['unit'] == unit) & (df['output'] == correct_answer)]
    return [correct_answer] + filtered['input'].to_list()
