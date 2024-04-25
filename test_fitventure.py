import pytest
from Fitventure import app
from flask import url_for

app.config['SERVER_NAME'] = 'localhost:5000'

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_register(client):
    """Test registration."""
    with app.app_context():
        response = client.post(url_for('register'), data=dict(
            username='test_user',
            email='test@example.com',
            password='test_password',
            confirm_password='test_password'
        ))


def test_login(client):
    """Test user login."""
    with app.app_context():
        response = client.post(url_for('login'), data=dict(
            username='test_user',
            password='test_password'
        ))

def test_reset_password(client):
    """Test password reset."""
    with app.app_context():
        response = client.post(url_for('reset_password'), json={
            'username': 'test_user',
            'new_password': 'new_password'
        })

def test_search(client):
    """Test search."""
    with app.app_context():
        response = client.get(url_for('search', query='France'))

def test_country_details(client):
    """Test country details."""
    with app.app_context():
        response = client.get(url_for('country_details', country_name='France'))

def test_add_review(client):
    """Test adding a review."""
    # Authenticate the user first
    with app.app_context():
        client.post(url_for('login'), data=dict(
            username='test_user',
            password='test_password'
        ))
        
