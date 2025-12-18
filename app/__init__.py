import os
from flask import Flask, current_app, request, session
from app.extensions import db, login_manager, babel
from config import Config

def get_locale():
    # Check if user has explicitly set a language
    if 'locale' in session:
        return session['locale']
    # Otherwise try to match browser preference
    return request.accept_languages.best_match(['zh', 'en']) or 'zh'

def create_app(config_class=Config):
    app = Flask(__name__, 
                template_folder='../templates',
                static_folder='../static')
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    
    # Updated Babel initialization for Flask-Babel v3+
    babel.init_app(app, locale_selector=get_locale)
    
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'info'

    # Register blueprints
    from app.routes.main import bp as main_bp
    app.register_blueprint(main_bp)

    from app.routes.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from app.routes.api import bp as api_bp
    app.register_blueprint(api_bp, url_prefix='/api')
    
    from app.routes.admin import bp as admin_bp
    app.register_blueprint(admin_bp, url_prefix='/admin')
    
    # Context processor for templates
    @app.context_processor
    def utility_processor():
        def thumbnail_url(path):
            return f"/thumbs/{path}"
        return dict(thumbnail_url=thumbnail_url)

    return app
