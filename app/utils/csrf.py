import secrets
from flask import session, request, abort, current_app

def generate_csrf_token():
    if '_csrf_token' not in session:
        session['_csrf_token'] = secrets.token_hex(16)
    return session['_csrf_token']

def validate_csrf_token():
    if request.method in ['POST', 'PUT', 'DELETE', 'PATCH']:
        # Allow excluding routes if needed, e.g. external APIs without session
        # For now, protect everything
        token = session.get('_csrf_token')
        if not token:
            current_app.logger.warning('CSRF validation failed: No token in session')
            abort(403)

        request_token = request.form.get('csrf_token')
        if not request_token:
            # Check headers for AJAX requests
            request_token = request.headers.get('X-CSRFToken')

        if not request_token or request_token != token:
            current_app.logger.warning('CSRF validation failed: Token mismatch')
            abort(403)
