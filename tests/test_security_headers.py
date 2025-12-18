
import pytest
from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test_key'
    with app.test_client() as client:
        yield client

def test_security_headers(client):
    response = client.get('/')
    assert response.headers['X-Content-Type-Options'] == 'nosniff'
    assert response.headers['X-Frame-Options'] == 'SAMEORIGIN'
    assert response.headers['Referrer-Policy'] == 'strict-origin-when-cross-origin'

def test_cookie_samesite(client):
    # Force session creation
    with client.session_transaction() as sess:
        sess['a'] = 'b'

    response = client.get('/')
    set_cookie = response.headers.getlist('Set-Cookie')
    session_cookie = next((c for c in set_cookie if 'session=' in c), None)

    assert session_cookie is not None
    assert 'SameSite=Lax' in session_cookie
