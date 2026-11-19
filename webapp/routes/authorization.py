from datetime import datetime, timezone
from urllib.parse import urlparse

from flask import current_app
from flask import render_template, request, redirect, url_for, flash, session
from flask_login import login_user, current_user, logout_user, login_required
from flask_mail import Message

from data.content.application.buttons import HOMEPAGE
from data.data_processing.units import units
from data.data_processing.data_loading import load_data_exercise
from data.data_processing.total_questions import total_question_exercises

from users.users.models import db, User, UserExerciseState
from users.users.service import make_qid
from users.users.settings import invalidate_user_settings
from users.session_management.logging import log_new_signup

from webapp.extensions import limiter
from webapp.i18n import get_language
from webapp.routes.settings_api import get_or_create_settings

from . import routes_bp


def normalize_account_id(raw):
    """Return a canonical UUID string, or None when the input is malformed."""
    if not raw:
        return None

    s = raw.strip().lower().replace("-", "").replace(" ", "")

    if len(s) != 32:
        return None

    return f"{s[0:8]}-{s[8:12]}-{s[12:16]}-{s[16:20]}-{s[20:32]}"


def _is_safe_next(target):
    """Only allow redirects back to this site (relative or same-host URLs)."""
    if not target:
        return False

    # Backslashes and protocol-relative URLs are treated as another host by
    # browsers even when urlparse does not report a netloc.
    if "\\" in target or target.startswith("//"):
        return False

    parsed = urlparse(target)

    if parsed.scheme:
        if parsed.scheme not in ("http", "https"):
            return False
        if parsed.netloc != request.host:
            return False
    elif parsed.netloc and parsed.netloc != request.host:
        return False

    return True


def send_account_id_email(to_email, account_id):
    """Send the user's account code to their recovery email address."""
    mail = current_app.extensions.get("mail")
    sender = current_app.config.get("MAIL_USERNAME")

    if mail is None or not sender:
        # No SMTP credentials configured (e.g. local development).
        current_app.logger.info(
            "[account-code] would send %s to %s", account_id, to_email
        )
        return

    message = Message(
        subject="Your Sievers Study Hall account code",
        sender=sender,
        recipients=[to_email],
    )
    message.body = (
        "Hello,\n\n"
        "Your Sievers Study Hall account code is:\n\n"
        f"{account_id}\n\n"
        "Keep it somewhere safe. It is the only way to sign in to your account.\n\n"
        "— Sievers Study Hall"
    )
    mail.send(message)


@routes_bp.route("/signin", methods=["GET", "POST"])
@limiter.limit("10/minute", methods=["POST"])
def signin():

    language = get_language(request, session)

    # Already logged in? Go to settings.
    if current_user.is_authenticated:
        return redirect(url_for("routes.settings"))

    if request.method == "POST":
        account_id = normalize_account_id(request.form.get("account_id"))
        remember = bool(request.form.get("remember"))

        user = (
            User.query.filter_by(account_id=account_id).first()
            if account_id
            else None
        )

        if not user:
            flash("Invalid account code.", "error")
            return redirect(url_for("routes.signin"))

        login_user(user, remember=remember)

        try:
            get_or_create_settings(current_user.id)
        except Exception:
            pass

        merge_anonymous_progress_in_database()

        next_url = request.args.get("next")
        if not _is_safe_next(next_url):
            next_url = url_for("routes.home")

        return redirect(next_url)

    page = {
        'english': 'authorization/signin_en.html',
        'french': 'authorization/signin_fr.html',
    }

    return render_template(page[language],
                           homepage=HOMEPAGE[language],
                           )


@routes_bp.route("/signup", methods=["GET", "POST"])
@limiter.limit("10/minute", methods=["POST"])
def signup():

    language = get_language(request, session)

    if current_user.is_authenticated:
        return redirect(url_for("routes.settings"))

    if request.method == "POST":
        user = User()
        db.session.add(user)
        db.session.commit()

        login_user(user)

        log_new_signup(user)
        merge_anonymous_progress_in_database()
        clean_session_after_signing_up()

        try:
            get_or_create_settings(current_user.id)
        except Exception:
            pass

        return redirect(url_for("routes.account_created"))

    page = {
        'english': 'authorization/signup_en.html',
        'french': 'authorization/signup_fr.html',
    }

    return render_template(page[language],
                           homepage=HOMEPAGE[language],
                           )


@routes_bp.route("/account/created", methods=["GET", "POST"])
@login_required
def account_created():

    language = get_language(request, session)

    if request.method == "POST":
        row = get_or_create_settings(current_user.id)
        row.settings = {
            **(row.settings or {}),
            "account_code_acknowledged": True,
        }
        db.session.commit()
        invalidate_user_settings()
        return redirect(url_for("routes.home"))

    page = {
        'english': 'authorization/account_created_en.html',
        'french': 'authorization/account_created_fr.html',
    }

    return render_template(page[language],
                           account_id=current_user.account_id,
                           homepage=HOMEPAGE[language],
                           )


@routes_bp.route("/recover-account", methods=["GET", "POST"])
@limiter.limit("10/minute", methods=["POST"])
def recover_account():

    language = get_language(request, session)

    if current_user.is_authenticated:
        return redirect(url_for("routes.settings"))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        user = User.query.filter_by(email=email).first() if email else None

        if user and user.email:
            send_account_id_email(user.email, user.account_id)

        # Always show the same message and redirect, so the endpoint does not
        # reveal whether an email address is on file.
        flash("If that email is on file, we have sent your account code.", "info")
        return redirect(url_for("routes.signin"))

    page = {
        'english': 'authorization/recover_account_en.html',
        'french': 'authorization/recover_account_fr.html',
    }

    return render_template(page[language],
                           homepage=HOMEPAGE[language],
                           )


@routes_bp.route("/signout", methods=["POST"])
@login_required
def signout():
    logout_user()
    flash("Signed out.", "info")
    return redirect(url_for("routes.signin"))


def merge_anonymous_progress_in_database():
    if not current_user.is_authenticated:
        return

    for unit in units:
        unit_data = session.get(unit)
        if not isinstance(unit_data, dict):
            continue

        for exercise_str, ex_data in list(unit_data.items()):
            if not isinstance(ex_data, dict):
                continue
            try:
                ex = int(exercise_str)
            except (TypeError, ValueError):
                continue

            # ---- Load current exercise data (MUST exist) ----
            try:
                df = load_data_exercise(unit, ex)  # <-- pass INT, not str
            except Exception as e:
                print(f"[merge] skip {unit}/{ex}: load_data_exercise failed: {e}")
                continue
            if df is None or len(df) == 0:
                print(f"[merge] skip {unit}/{ex}: empty dataset")
                continue
            for col in ("Nr", "question", "answer"):
                if col not in df.columns:
                    print(f"[merge] skip {unit}/{ex}: missing column {col}")
                    df = None
                    break
            if df is None:
                continue

            # ---- Build Nr -> qid mapping ----
            nr_to_qid = {}
            for _, row in df.iterrows():
                try:
                    nr = int(row["Nr"])
                except Exception:
                    continue
                qid = make_qid(
                    unit, ex,
                    str(row.get("question", "")),
                    str(row.get("answer", "")),
                    str(row.get("type", "")),
                )
                nr_to_qid[nr] = qid

            progress_nrs = [int(n) for n in (ex_data.get("progress") or []) if str(n).isdigit()]
            falses_nrs   = [int(n) for n in (ex_data.get("falses")   or []) if str(n).isdigit()]
            wrong_texts  = list(ex_data.get("incorrect_answer", [])) or []

            has_detail  = bool(progress_nrs or falses_nrs)
            has_summary = "result" in ex_data
            if not has_detail and not has_summary:
                continue

            row = UserExerciseState.query.filter_by(user_id=current_user.id, unit=unit, exercise=ex).first()
            if not row:
                row = UserExerciseState(user_id=current_user.id, unit=unit, exercise=ex, state={})
                db.session.add(row)

            if has_summary:
                score = float(ex_data["result"])
                total_questions = total_question_exercises[unit][ex]
                row.state = {"score": score, "total_questions": int(total_questions)}
            else:
                correct = sorted(set(progress_nrs) - set(falses_nrs))
                inc_map = {}
                for i, nr in enumerate(falses_nrs):
                    if nr in correct or nr in inc_map: continue
                    inc_map[nr] = wrong_texts[i] if i < len(wrong_texts) else ""
                # merge with any existing counts/nrs
                s_old = row.state or {}
                old_correct = set(int(n) for n in s_old.get("correct_nrs", []))
                old_incorrect = {int(k): v for k, v in (s_old.get("incorrect") or {}).items()}
                # promote if needed
                for n in correct: old_incorrect.pop(n, None)
                row.state = {
                    "correct_nrs": sorted(old_correct | set(correct)),
                    "incorrect": {str(k): v for k, v in {**old_incorrect, **inc_map}.items()},
                }

            row.updated_at = datetime.now(timezone.utc)
            db.session.commit()
            # then trim session keys
            for key in ("progress", "falses", "incorrect_answer"):
                ex_data.pop(key, None)


def clean_session_after_signing_up():
    for unit in units:
        if unit in session:
            del session[unit]

    if 'unfinished_exercise' in session:
        del session['unfinished_exercise']

    return
