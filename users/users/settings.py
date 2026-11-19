from flask import session, g, has_request_context
from flask_login import current_user

from users.users.models import UserSettings

DEFAULT_SETTINGS = {
    "account_code_acknowledged": False,
    "feedback_enabled": True,
    "theme": "night",
    "special_characters_enabled": True,
    "instruction_page_enabled": True,
    "hide_options_word_order": False,
}


def _get_user_settings_row():
    """
    Returns the authenticated user's UserSettings row, cached on flask.g.

    The settings helpers below are called several times per rendered page (theme
    alone is read by every bookmark/flag icon plus two context processors), so
    caching the row avoids repeating the same query for the duration of the
    request.
    """
    user_id = current_user.id
    cache = getattr(g, "_user_settings_cache", None)

    if cache is None or cache.get("user_id") != user_id:
        row = UserSettings.query.get(user_id)
        cache = {"user_id": user_id, "row": row}
        g._user_settings_cache = cache

    return cache["row"]


def invalidate_user_settings():
    """Drops the per-request settings cache after a write."""
    if has_request_context() and hasattr(g, "_user_settings_cache"):
        del g._user_settings_cache


def is_feedback_enabled():
    if current_user.is_authenticated:
        row = _get_user_settings_row()
        if row and row.settings:
            return row.settings.get("feedback_enabled", DEFAULT_SETTINGS["feedback_enabled"])
        return DEFAULT_SETTINGS["feedback_enabled"]

    anon_settings = session.get("settings", {})
    return anon_settings.get("feedback_enabled", DEFAULT_SETTINGS["feedback_enabled"])


def get_theme():
    if current_user.is_authenticated:
        row = _get_user_settings_row()
        if row and row.settings:
            return row.settings.get("theme", DEFAULT_SETTINGS["theme"])
        return DEFAULT_SETTINGS["theme"]

    anon_settings = session.get("settings", {})
    return anon_settings.get("theme", DEFAULT_SETTINGS["theme"])


def are_special_characters_enabled():
    if current_user.is_authenticated:
        row = _get_user_settings_row()
        if row and row.settings:
            return row.settings.get(
                "special_characters_enabled",
                DEFAULT_SETTINGS["special_characters_enabled"]
            )
        return DEFAULT_SETTINGS["special_characters_enabled"]

    anon_settings = session.get("settings", {})
    return anon_settings.get(
        "special_characters_enabled",
        DEFAULT_SETTINGS["special_characters_enabled"]
    )


def is_instruction_page_enabled():
    if current_user.is_authenticated:
        row = _get_user_settings_row()
        if row and row.settings:
            return row.settings.get(
                "instruction_page_enabled",
                DEFAULT_SETTINGS["instruction_page_enabled"]
            )
        return DEFAULT_SETTINGS["instruction_page_enabled"]

    anon_settings = session.get("settings", {})
    return anon_settings.get(
        "instruction_page_enabled",
        DEFAULT_SETTINGS["instruction_page_enabled"]
    )


def get_filename_empty_bookmark():
    if get_theme() == 'day':
        return "icons/bookmark/empty_day.png"
    else:
        return "icons/bookmark/empty.png"


def get_filename_full_bookmark():
    if get_theme() == 'day':
        return "icons/bookmark/full_day.png"
    else:
        return "icons/bookmark/full.png"


def get_filename_flag():
    if get_theme() == 'day':
        return "icons/flag/flag_black.png"
    else:
        return "icons/flag/flag_white.png"


def are_options_in_word_order_exercises_hidden():
    if current_user.is_authenticated:
        row = _get_user_settings_row()
        if row and row.settings:
            return row.settings.get(
                "hide_options_word_order",
                DEFAULT_SETTINGS["hide_options_word_order"]
            )
        return DEFAULT_SETTINGS["hide_options_word_order"]

    anon_settings = session.get("settings", {})
    return anon_settings.get(
        "hide_options_word_order",
        DEFAULT_SETTINGS["hide_options_word_order"]
    )
