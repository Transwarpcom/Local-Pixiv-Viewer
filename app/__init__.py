from flask import Flask, request, session
from .extensions import db, login_manager, babel
from .models import User
import config
import os

def create_app(test_config=None):
    # Set template and static folders relative to the root, as app is in app/
    app = Flask(__name__,
                template_folder='../templates',
                static_folder='../static')

    # Load config from config.py
    for key in dir(config):
        if key.isupper():
            app.config[key] = getattr(config, key)

    app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{config.DB_PATH}"
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Additional config from app.py
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['BABEL_DEFAULT_LOCALE'] = 'en'
    app.config['BABEL_TRANSLATION_DIRECTORIES'] = '../translations'

    if test_config:
        app.config.update(test_config)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    babel.init_app(app, locale_selector=get_locale)

    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'info' # Flash category

    # Register blueprints
    from .routes import main, auth, api, admin
    app.register_blueprint(main.bp)
    app.register_blueprint(auth.bp)
    app.register_blueprint(api.bp)
    app.register_blueprint(admin.bp)

    # Register filters and context processors
    from .utils import register_filters
    register_filters(app)

    @app.after_request
    def add_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        return response

    return app

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

def get_locale():
    if session.get('lang'): return session.get('lang')
    return request.accept_languages.best_match(['en', 'zh'])
