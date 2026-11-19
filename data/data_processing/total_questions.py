from collections.abc import Mapping

import numpy as np

from data.data_processing.paths import df_units
from data.data_processing.units import units
from data.data_processing.data_loading import count_data_exercise


def compute_highest_exercise(unit):
    """
    Determines the highest exercise number for a given unit, excluding special exercises (>= 1000).

    Args:
        unit (str): The unit identifier.

    Returns:
        int: The highest valid exercise number for the unit.
    """
    data = df_units[unit]
    highest_exercise_unit = np.max(data[data["exercise"] < 1000]["exercise"])
    return int(highest_exercise_unit)


highest_exercise_per_unit = {unit: compute_highest_exercise(unit) for unit in units}


def compute_total_questions(unit, exercise=None):
    """
    Computes the total number of questions for a specific exercise or for the entire unit.

    Args:
        unit (str): The unit identifier.
        exercise (int or None): Optional exercise number. If None, totals all exercises.

    Returns:
        int: The total number of questions.
    """
    if exercise is not None:
        return count_data_exercise(unit, exercise)

    return sum(
        count_data_exercise(unit, exercise)
        for exercise in range(1, highest_exercise_per_unit[unit] + 1)
    )


class _ExerciseCounts(Mapping):
    """
    Lazily computed ``{exercise: question_count}`` mapping for one unit.

    Building every count at import time meant preprocessing every exercise in
    every unit before the app could serve its first request. Counts are now
    computed the first time an exercise is requested and then cached (the
    underlying exercise frame is cached too).
    """

    def __init__(self, unit, highest_exercise):
        self._unit = unit
        self._highest_exercise = highest_exercise
        self._counts = {}

    def __getitem__(self, exercise):
        exercise = int(exercise)

        if exercise not in self._counts:
            self._counts[exercise] = count_data_exercise(self._unit, exercise)

        return self._counts[exercise]

    def __iter__(self):
        return iter(range(1, self._highest_exercise + 1))

    def __len__(self):
        return self._highest_exercise


class _TotalQuestionExercises(Mapping):
    """``{unit: {exercise: question_count}}`` with lazy per-unit contents."""

    def __init__(self):
        self._units = {
            unit: _ExerciseCounts(unit, highest_exercise_per_unit[unit])
            for unit in units
        }

    def __getitem__(self, unit):
        return self._units[unit]

    def __iter__(self):
        return iter(self._units)

    def __len__(self):
        return len(self._units)


class _TotalQuestionUnits(Mapping):
    """``{unit: total_question_count}`` with lazy per-unit totals."""

    def __init__(self):
        self._unit_totals = {}

    def __getitem__(self, unit):
        if unit not in self._unit_totals:
            self._unit_totals[unit] = compute_total_questions(unit)
        return self._unit_totals[unit]

    def __iter__(self):
        return iter(units)

    def __len__(self):
        return len(units)


total_question_exercises = _TotalQuestionExercises()
total_question_units = _TotalQuestionUnits()
