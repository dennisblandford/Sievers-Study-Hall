from data.data_processing.units import praesens, praeteritum, imperativ, konjunktiv_II, konjunktiv_I

PERSONS = ['ich', 'du', 'er/sie/es', 'wir', 'ihr', 'Sie']
IMPERATIVE_PERSONS = ['du', 'ihr', 'Sie']


def get_person_columns(unit, exercise):
    """
    Returns the person columns that ``pre_processing`` expands into rows.

    ``None`` means the unit/exercise is not expanded (one row in, one row out).
    Keeping this in one place lets the preprocessing step and the fast question
    counter below agree on how many rows an exercise produces.
    """
    if unit == praesens:
        return PERSONS

    if unit == praeteritum:
        return PERSONS if int(exercise) == 1 else None

    if unit == imperativ:
        return IMPERATIVE_PERSONS

    if unit == konjunktiv_II:
        return PERSONS

    if unit == konjunktiv_I:
        return PERSONS

    return None


def pre_processing(data, unit, exercise):
    persons = get_person_columns(unit, exercise)

    if persons is not None:
        return expand_persons(data, persons)

    if unit == praeteritum:
        return pre_processing_praeteritum(data, exercise)

    return data


def expand_persons(data, persons):
    """
    Turns wide conjugation rows (one column per person) into long rows
    (one row per person), preserving the exact original ordering:

    for each source row, in order, for each person, in order.

    The previous implementation used ``DataFrame.iterrows()`` to build this
    long form row by row, which is extremely slow in pandas. ``melt`` does the
    same work in C; the stable sort by the (positional) index restores the
    original row-major ordering that the rest of the app relies on for ``Nr``.
    """
    if data.empty:
        return data

    present_persons = [person for person in persons if person in data.columns]
    if not present_persons:
        return data

    data = data.reset_index(drop=True)

    # ``answer`` already exists in the source (the infinitive); the long form
    # overwrites it with the conjugated form, matching the previous behaviour,
    # so drop the source column first to avoid a name clash in melt().
    data = data.drop(columns=["answer"], errors="ignore")
    id_vars = [column for column in data.columns if column not in persons]

    long = data.melt(
        id_vars=id_vars,
        value_vars=present_persons,
        var_name="person",
        value_name="answer",
        ignore_index=False,
    )

    # melt is column-major (all rows of "ich", then all rows of "du", ...).
    # Sort by the original positional index to get row-major order while the
    # stable sort keeps the person order within each source row.
    long = long.sort_index(kind="stable").reset_index(drop=True)
    long["Nr"] = range(1, len(long) + 1)
    return long


def pre_processing_praesens(data):
    return expand_persons(data, PERSONS)


def pre_processing_praeteritum(data, exercise):
    # The expanding case (exercise == 1) is handled by get_person_columns /
    # pre_processing above; this branch applies to the other exercises.
    data = data.copy()
    data['answer'] = data['er/sie/es'].copy()
    data['person'] = 'er/sie/es'
    return data


def pre_processing_imperativ(data):
    return expand_persons(data, IMPERATIVE_PERSONS)


def pre_processing_konjunktiv_ii(data):
    return expand_persons(data, PERSONS)


def pre_processing_konjunktiv_i(data):
    return expand_persons(data, PERSONS)
