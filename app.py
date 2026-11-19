import os
from datetime import timedelta
from flask import Flask
from flask_mail import Mail
from flask_login import LoginManager
from werkzeug.middleware.proxy_fix import ProxyFix

from webapp.extensions import limiter
from webapp.routes import routes_bp
from users.users.models import db, User

app = Flask(__name__,
            static_url_path='/webapp/static',
            static_folder='webapp/static',
            template_folder='webapp/templates')
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'secret_key_for_development_environment')

app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///prod.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Trust the reverse proxy (nginx / Cloudflare Tunnel) for scheme, host and IP.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("SESSION_COOKIE_SECURE", "0") == "1"

app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = os.environ.get("MAIL_USERNAME")
app.config["MAIL_PASSWORD"] = os.environ.get("MAIL_PASSWORD")

mail = Mail()
mail.init_app(app)

limiter.init_app(app)

db.init_app(app)

# Minimal Flask-Login setup (needed for login_user/logout_user)
login_manager = LoginManager(app)
login_manager.login_view = "routes.signin"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

app.register_blueprint(routes_bp)

app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)

with app.app_context():
    db.create_all()
    from webapp.migration_account_ids import migrate_account_ids
    migrate_account_ids()
