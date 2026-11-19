import datetime

from flask import session, request, Response, render_template, url_for, current_app
from flask_login import current_user, login_required
from werkzeug.routing import BuildError

from typing import cast

from data.content.unit.stars import STARS
from data.content.unit.unit_url_path import UNIT_URL_PATH
from data.content.unit.unit_content_by_language import HOME_DESCRIPTION, INTRODUCTION, UNIT_NAME
from data.content.application.text import YOUR_ANSWER, META_DESCRIPTION, SECTION_PREPOSITION, SECTION_ARTICLES, \
    SECTION_SENTENCE_STRUCTURE, SECTION_ADJECTIVES, SECTION_VERBS, SECTION_NOUNS, SECTION_CONJUGATION, \
    SECTION_ETYMOLOGY, SECTION_OTHER
from data.content.application.buttons import HOMEPAGE, UNIT_PARTICULARLY_LIKE_BY_USERS

from data.data_processing.units import units, units_without_alpha
from data.data_processing.exercises import get_exercises_by_unit_and_level, levels, get_level_from_exercise, \
    is_exercise_prompt, get_category_from_exercise
from data.data_processing.separations import separations
from data.data_processing.total_questions import total_question_exercises, highest_exercise_per_unit

from users.users.models import Bookmark
from users.users.settings import get_filename_empty_bookmark, get_filename_full_bookmark, get_filename_flag
from users.progress.analytics import get_accuracy_trend, get_error_rate_by_unit, \
    get_error_rate_by_exercise, get_most_missed_questions, get_first_attempt_accuracy
from users.progress.score import write_score, get_lowest_scored_exercises
from users.progress.progress import compute_answered_questions, update_progress_in_home_page, is_exercise_started, \
    get_fraction_exercises_finished_by_level, get_random_unit_and_lowest_unfinished_exercise, get_unfinished_exercises, \
    get_progress_home_page
from users.questions.content_format import format_correction, format_description

from . import routes_bp

from webapp.i18n import get_language
from webapp.style.icons import STAR_GOLD

session = cast(dict, session)


@routes_bp.route('/', endpoint='home')
def home():

    language = get_language(request, session)

    home_description = HOME_DESCRIPTION[language]
    meta_description = META_DESCRIPTION[language]

    completed_exercises = {unit: get_progress_home_page(session, unit) for unit in units}

    return render_template('home.html',
                           unit_name=UNIT_NAME[language],
                           title_button=UNIT_NAME[language],
                           unit_url_path=UNIT_URL_PATH,
                           unit_stars=STARS,
                           STAR_GOLD=STAR_GOLD,
                           home_description=home_description,
                           completed_exercises=completed_exercises,
                           highest_exercise=highest_exercise_per_unit,
                           UNIT_PARTICULARLY_LIKE_BY_USERS=UNIT_PARTICULARLY_LIKE_BY_USERS[language],
                           meta_description=meta_description,
                           user_is_connected=current_user.is_authenticated,
                           prepositions=SECTION_PREPOSITION[language],
                           articles=SECTION_ARTICLES[language],
                           sentence_structure=SECTION_SENTENCE_STRUCTURE[language],
                           adjectives=SECTION_ADJECTIVES[language],
                           verbs=SECTION_VERBS[language],
                           nouns=SECTION_NOUNS[language],
                           conjugation=SECTION_CONJUGATION[language],
                           etymology=SECTION_ETYMOLOGY[language],
                           other=SECTION_OTHER[language],
                           )


for unit in units:
    route_path = UNIT_URL_PATH[unit]
    template = 'unit.html'

    def make_route(unit=unit):
        endpoint_name = f'dynamic_route_{unit}'
        @routes_bp.route(route_path, endpoint=endpoint_name)
        def dynamic_route():
            language = get_language(request, session)
            introduction = INTRODUCTION[language].get(unit, {})
            meta_description = META_DESCRIPTION[language]

            exercises_by_level = {
                level: get_exercises_by_unit_and_level(unit, level)
                for level in levels
            }

            update_progress_in_home_page(session, unit)

            return render_template(template,
                                   unit_name=UNIT_NAME[language][unit],
                                   answered_questions=compute_answered_questions,
                                   total_questions=total_question_exercises,
                                   score=write_score,
                                   introduction=introduction,
                                   format_description=format_description,
                                   homepage=HOMEPAGE[language],
                                   meta_description=meta_description,
                                   is_exercise_started=is_exercise_started,
                                   exercises_by_level=exercises_by_level,
                                   levels=levels,
                                   separations=separations,
                                   is_exercise_prompt=is_exercise_prompt,
                                   )
        return dynamic_route

    make_route()


@routes_bp.route('/settings', endpoint='settings')
def settings():

    language = get_language(request, session)

    page = {
        'english': 'menu/settings_en.html',
        'french': 'menu/settings_fr.html',
    }

    account_id = current_user.account_id if current_user.is_authenticated else None
    email = current_user.email if current_user.is_authenticated else None

    return render_template(page[language],
                           account_id=account_id,
                           email=email,
                           homepage=HOMEPAGE[language],
                           is_authenticated=current_user.is_authenticated,
                           )


@routes_bp.route('/about', endpoint='about')
def about():

    language = get_language(request, session)

    page = {
        'english': 'menu/about_en.html',
        'french': 'menu/about_fr.html',
    }

    return render_template(page[language],
                           homepage=HOMEPAGE[language],
                           )


@routes_bp.route('/privacy', endpoint='privacy')
def privacy():

    language = get_language(request, session)

    page = {
        'english': 'menu/privacy_en.html',
        'french': 'menu/privacy_fr.html',
    }

    return render_template(page[language],
                           homepage=HOMEPAGE[language],
                           )


@routes_bp.route('/legal', endpoint='legal')
def legal():

    language = get_language(request, session)

    page = {
        'english': 'menu/legal_en.html',
        'french': 'menu/legal_fr.html',
    }

    return render_template(page[language],
                           homepage=HOMEPAGE[language],
                           )


@routes_bp.route("/bookmarks")
@login_required
def bookmarks():

    language = get_language(request, session)

    bookmark = (
        Bookmark.query
        .filter_by(user_id=current_user.id)
        .order_by(Bookmark.created_at.desc())
        .all()
    )

    page = {
        'english': 'menu/bookmarks_en.html',
        'french': 'menu/bookmarks_fr.html',
    }

    return render_template(page[language],
                           unit_name=UNIT_NAME[language],
                           bookmarks=bookmark,
                           is_feedback_box=True,
                           your_answer=YOUR_ANSWER[language],
                           force_full_bookmark=True,
                           format_correction=format_correction,
                           icon_empty=get_filename_empty_bookmark(),
                           icon_full=get_filename_full_bookmark(),
                           icon_flag=get_filename_flag(),
                           language=language,
                           homepage=HOMEPAGE[language],
                           )


@routes_bp.route("/progress")
def progress():

    language = get_language(request, session)

    page = {
        'english': 'menu/progress_en.html',
        'french': 'menu/progress_fr.html',
    }

    fraction_level_finished = {level: get_fraction_exercises_finished_by_level(session, level) for level in levels}
    random_unit_exercise = {level: get_random_unit_and_lowest_unfinished_exercise(session, level) for level in levels}

    unfinished_exercises = get_unfinished_exercises(session)

    lowest_score_exercises = get_lowest_scored_exercises()

    print(UNIT_NAME[language])

    return render_template(
        page[language],
        unit_name=UNIT_NAME[language],
        levels=levels,
        fractions=fraction_level_finished,
        random_unit_exercise=random_unit_exercise,
        unfinished_exercises=unfinished_exercises,
        answered_questions=compute_answered_questions,
        total_questions=total_question_exercises,
        score=write_score,
        is_exercise_started=is_exercise_started,
        lowest_score_exercises=lowest_score_exercises,
        get_level_from_exercise=get_level_from_exercise,
        homepage=HOMEPAGE[language],
    )


def _anonymous_stats(web_session):
    """Build a small, ephemeral statistics view from session progress."""
    rows = []

    for unit in units:
        unit_data = web_session.get(unit)
        if not isinstance(unit_data, dict):
            continue

        for exercise_str, data in unit_data.items():
            if not isinstance(data, dict):
                continue

            try:
                exercise = int(exercise_str)
                total = int(total_question_exercises[unit][exercise])
            except (TypeError, ValueError, KeyError, IndexError):
                continue

            progress = set(data.get("progress") or [])
            falses = set(data.get("falses") or [])
            summary = data.get("result")

            if summary is None and not progress and not falses:
                continue

            if summary is not None:
                try:
                    score = float(summary)
                except (TypeError, ValueError):
                    score = 0.0
            else:
                correct = len(progress - falses)
                score = (correct / total) if total else 0.0

            rows.append({
                "unit": unit,
                "exercise": exercise,
                "total": total,
                "score": score,
                "errors": len(falses),
            })

    rows.sort(key=lambda row: (row["score"], -row["errors"]))
    return rows


@routes_bp.route("/stats", endpoint="stats")
def stats():

    language = get_language(request, session)

    try:
        days = int(request.args.get("days", 30))
    except (TypeError, ValueError):
        days = 30

    days = max(1, min(days, 365))

    page = {
        'english': 'menu/stats_en.html',
        'french': 'menu/stats_fr.html',
    }

    is_authenticated = current_user.is_authenticated

    trend = []
    unit_errors = []
    exercise_errors = []
    missed = []
    first_attempt = None
    categories = {}
    anonymous_rows = []

    if is_authenticated:
        trend = get_accuracy_trend(days)
        unit_errors = get_error_rate_by_unit(days)
        exercise_errors = get_error_rate_by_exercise(days)
        missed = get_most_missed_questions(days=max(days, 90), limit=10)
        first_attempt = get_first_attempt_accuracy(days)
        categories = {
            row["unit"]: get_category_from_exercise(row["unit"], 1)
            for row in unit_errors
        }
    else:
        anonymous_rows = _anonymous_stats(session)

    return render_template(
        page[language],
        days=days,
        is_authenticated=is_authenticated,
        trend=trend,
        unit_errors=unit_errors,
        exercise_errors=exercise_errors,
        missed=missed,
        first_attempt=first_attempt,
        categories=categories,
        anonymous_rows=anonymous_rows,
        unit_name=UNIT_NAME[language],
        homepage=HOMEPAGE[language],
    )


@routes_bp.route("/robots.txt")
def robots_txt():
    sitemap_url = url_for("routes.sitemap", _external=True)
    content = (
        "User-agent: *\n"
        "Disallow:\n"
        f"Sitemap: {sitemap_url}\n"
    )
    return Response(content, mimetype="text/plain")


@routes_bp.route("/sitemap.xml")
def sitemap():
    pages = []
    today = datetime.date.today().isoformat()

    def add(endpoint: str):
        try:
            pages.append({
                "loc": url_for(endpoint, _external=True),
                "lastmod": today
            })
        except BuildError:
            current_app.logger.warning(
                f"Could not build sitemap URL for endpoint: {endpoint}"
            )

    add("routes.home")

    for unit in units_without_alpha:
        add(f"routes.dynamic_route_{unit}")

    sitemap_xml = render_template("sitemap_template.xml", pages=pages)
    return Response(sitemap_xml, mimetype="application/xml")