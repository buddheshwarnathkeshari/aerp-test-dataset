import pytest
import hashlib
import jwt
import datetime
from unittest.mock import patch, MagicMock
from django.urls import reverse
from django.conf import settings
from rest_framework import status
from users.models import User

# Ensure settings are configured for JWT_SECRET and ALGORITHM
# In a real project, these would be in settings.py
if not hasattr(settings, 'JWT_SECRET'):
    settings.JWT_SECRET = "shopcore-super-secret-jwt-key-123"
if not hasattr(settings, 'JWT_ALGORITHM'):
    settings.JWT_ALGORITHM = "HS256"
if not hasattr(settings, 'TOKEN_EXPIRY_HOURS'):
    settings.TOKEN_EXPIRY_HOURS = 24

# Constants from views.py
JWT_SECRET = settings.JWT_SECRET
JWT_ALGORITHM = settings.JWT_ALGORITHM
TOKEN_EXPIRY_HOURS = settings.TOKEN_EXPIRY_HOURS


@pytest.fixture
def api_client():
    from rest_framework.test import APIClient
    return APIClient()


@pytest.fixture
def create_user_in_db():
    """Fixture to create a user directly in the database with MD5 hashed password."""
    def _create_user(email, password, username=None, phone=None, is_verified=False):
        hashed_password = hashlib.md5(password.encode()).hexdigest()
        user = User.objects.create(
            email=email,
            username=username or email.split('@')[0],
            password=hashed_password,
            phone=phone,
            is_verified=is_verified
        )
        return user
    return _create_user


@pytest.fixture
def authenticated_client(api_client, create_user_in_db):
    """Fixture to return an APIClient authenticated with a JWT token."""
    user = create_user_in_db("test@example.com", "password123")
    payload = {
        'user_id': user.id,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=TOKEN_EXPIRY_HOURS),
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    api_client.user = user  # Attach user to client for convenience in tests
    return api_client


@pytest.fixture
def mock_datetime_utcnow():
    """Mocks datetime.datetime.utcnow to return a fixed time."""
    with patch('datetime.datetime') as mock_dt:
        mock_dt.utcnow.return_value = datetime.datetime(2023, 1, 1, 12, 0, 0)
        mock_dt.timedelta = datetime.timedelta
        mock_dt.side_effect = lambda *args, **kw: datetime.datetime(*args, **kw)
        yield mock_dt


# --- RegisterView Tests ---

@pytest.mark.django_db
def test_register_success_with_username(api_client):
    url = reverse('register')
    data = {
        'email': 'newuser@example.com',
        'password': 'securepassword',
        'username': 'newuser_name'
    }
    response = api_client.post(url, data, format='json')
    assert response.status_code == status.HTTP_201_CREATED
    assert 'message' in response.data
    assert 'user_id' in response.data
    user = User.objects.get(id=response.data['user_id'])
    assert user.email == data['email']
    assert user.username == data['username']
    assert user.password == hashlib.md5(data['password'].encode()).hexdigest()


@pytest.mark.django_db
def test_register_success_without_username(api_client):
    url = reverse('register')
    data = {
        'email': 'another@example.com',
        'password': 'anotherpassword',
    }
    response = api_client.post(url, data, format='json')
    assert response.status_code == status.HTTP_201_CREATED
    user = User.objects.get(id=response.data['user_id'])
    assert user.email == data['email']
    assert user.username == data['email'].split('@')[0]  # Default username
    assert user.password == hashlib.md5(data['password'].encode()).hexdigest()


@pytest.mark.django_db
def test_register_missing_email(api_client):
    url = reverse('register')
    data = {
        'password': 'testpassword',
        'username': 'testuser'
    }
    response = api_client.post(url, data, format='json')
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data == {'error': 'Email and password are required.'}


@pytest.mark.django_db
def test_register_missing_password(api_client):
    url = reverse('register')
    data = {
        'email': 'missingpass@example.com',
        'username': 'testuser'
    }
    response = api_client.post(url, data, format='json')
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data == {'error': 'Email and password are required.'}


@pytest.mark.django_db
def test_register_email_already_registered(api_client, create_user_in_db):
    create_user_in_db('existing@example.com', 'password123')
    url = reverse('register')
    data = {
        'email': 'existing@example.com',
        'password': 'newpassword',
        'username': 'someuser'
    }
    response = api_client.post(url, data, format='json')
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data == {'error': 'Email already registered.'}


# --- LoginView Tests ---

@pytest.mark.django_db
def test_login_success(api_client, create_user_in_db, mock_datetime_utcnow):
    user = create_user_in_db('login@example.com', 'loginpassword')
    url = reverse('login')
    data = {
        'email': 'login@example.com',
        'password': 'loginpassword'
    }
    response = api_client.post(url, data, format='json')
    assert response.status_code == status.HTTP_200_OK
    assert 'token' in response.data
    assert 'expires_in' in response.data
    assert response.data['expires_in'] == TOKEN_EXPIRY_HOURS * 3600

    # Verify JWT token content
    decoded_token = jwt.decode(response.data['token'], JWT_SECRET, algorithms=[JWT_ALGORITHM])
    assert decoded_token['user_id'] == user.id
    expected_exp = (datetime.datetime(2023, 1, 1, 12, 0, 0) + datetime.timedelta(hours=TOKEN_EXPIRY_HOURS)).timestamp()
    assert decoded_token['exp'] == int(expected_exp)


@pytest.mark.django_db
def test_login_invalid_email(api_client, create_user_in_db):
    create_user_in_db('valid@example.com', 'password123')
    url = reverse('login')
    data = {
        'email': 'nonexistent@example.com',
        'password': 'password123'
    }
    response = api_client.post(url, data, format='json')
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.data == {'error': 'Invalid credentials.'}


@pytest.mark.django_db
def test_login_invalid_password(api_client, create_user_in_db):
    create_user_in_db('testuser@example.com', 'correctpassword')
    url = reverse('login')
    data = {
        'email': 'testuser@example.com',
        'password': 'wrongpassword'
    }
    response = api_client.post(url, data, format='json')
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.data == {'error': 'Invalid credentials.'}


@pytest.mark.django_db
def test_login_missing_email(api_client):
    url = reverse('login')
    data = {
        'password': 'somepassword'
    }
    response = api_client.post(url, data, format='json')
    assert response.status_code == status.HTTP_401_UNAUTHORIZED # The current implementation will return 401 because `row` will be None
    assert response.data == {'error': 'Invalid credentials.'}


@pytest.mark.django_db
def test_login_missing_password(api_client):
    url = reverse('login')
    data = {
        'email': 'some@example.com'
    }
    response = api_client.post(url, data, format='json')
    assert response.status_code == status.HTTP_401_UNAUTHORIZED # The current implementation will return 401 because `input_hash` will be md5 of empty string
    assert response.data == {'error': 'Invalid credentials.'}


@pytest.mark.django_db
def test_login_sql_injection_attempt(api_client, create_user_in_db):
    """
    Tests the SQL injection vulnerability in LoginView.
    The current implementation is vulnerable to SQL injection.
    This test demonstrates that an attacker can bypass authentication
    if a user with ID 1 exists and the query returns a row.
    """
    # Create a dummy user with ID 1 (or any ID that might be returned by the injection)
    # In a real scenario, user IDs are usually auto-incremented.
    # For this test, we'll ensure a user exists.
    user = create_user_in_db('admin@example.com', 'adminpass')
    # The vulnerability is in `f"SELECT id, password FROM users WHERE email = '{email}'"`
    # If email is "' OR '1'='1", the query becomes:
    # SELECT id, password FROM users WHERE email = '' OR '1'='1'
    # This will return the first user in the table.
    # If the first user's password hash doesn't match md5('') (which is d41d8cd98f00b204e9800998ecf8427e),
    # it will still fail.
    # To demonstrate bypass, we need to match the password hash.
    # Let's assume the attacker knows the MD5 hash of an empty string.
    empty_password_md5 = hashlib.md5(b'').hexdigest()

    # Create a user whose password hash matches an empty string's MD5 hash
    # This is highly unlikely in a real scenario, but demonstrates the logic.
    # A more realistic exploit would involve guessing a password for the first user returned.
    user_for_injection = User.objects.create(
        email='injection_target@example.com',
        username='injection_target',
        password=empty_password_md5 # Set password to MD5 of empty string
    )

    url = reverse('login')
    data = {
        'email': f"' OR id = {user_for_injection.id} --", # SQL injection payload
        'password': '' # Empty password, its MD5 hash matches user_for_injection's password
    }
    response = api_client.post(url, data, format='json')

    # If the injection works and the password matches, it should return 200 OK.
    # This test confirms the vulnerability by showing a successful login with an injected email.
    assert response.status_code == status.HTTP_200_OK
    assert 'token' in response.data
    decoded_token = jwt.decode(response.data['token'], JWT_SECRET, algorithms=[JWT_ALGORITHM])
    assert decoded_token['user_id'] == user_for_injection.id

    # IMPORTANT: This test highlights a critical security vulnerability.
    # The `LoginView` should use parameterized queries to prevent SQL injection.
    # Example: `cursor.execute("SELECT id, password FROM users WHERE email = %s", [email])`


# --- ProfileView Tests ---

@pytest.mark.django_db
def test_profile_get_unauthenticated(api_client):
    url = reverse('profile')
    response = api_client.get(url)
    assert response.status_code == status.HTTP_403_FORBIDDEN # Default DRF permission is IsAuthenticated


@pytest.mark.django_db
def test_profile_get_authenticated(authenticated_client):
    url = reverse('profile')
    response = authenticated_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    user = authenticated_client.user
    assert response.data['id'] == user.id
    assert response.data['email'] == user.email
    assert response.data['username'] == user.username
    assert response.data['phone'] == user.phone
    assert response.data['is_verified'] == user.is_verified


@pytest.mark.django_db
def test_profile_patch_unauthenticated(api_client):
    url = reverse('profile')
    data = {'username': 'new_unauth_user'}
    response = api_client.patch(url, data, format='json')
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_profile_patch_update_username(authenticated_client):
    url = reverse('profile')
    new_username = 'updated_username'
    data = {'username': new_username}
    response = authenticated_client.patch(url, data, format='json')
    assert response.status_code == status.HTTP_200_OK
    assert response.data == {'message': 'Profile updated.'}

    authenticated_client.user.refresh_from_db()
    assert authenticated_client.user.username == new_username


@pytest.mark.django_db
def test_profile_patch_update_phone(authenticated_client):
    url = reverse('profile')
    new_phone = '123-456-7890'
    data = {'phone': new_phone}
    response = authenticated_client.patch(url, data, format='json')
    assert response.status_code == status.HTTP_200_OK
    assert response.data == {'message': 'Profile updated.'}

    authenticated_client.user.refresh_from_db()
    assert authenticated_client.user.phone == new_phone


@pytest.mark.django_db
def test_profile_patch_update_both(authenticated_client):
    url = reverse('profile')
    new_username = 'another_username'
    new_phone = '987-654-3210'
    data = {
        'username': new_username,
        'phone': new_phone
    }
    response = authenticated_client.patch(url, data, format='json')
    assert response.status_code == status.HTTP_200_OK
    assert response.data == {'message': 'Profile updated.'}

    authenticated_client.user.refresh_from_db()
    assert authenticated_client.user.username == new_username
    assert authenticated_client.user.phone == new_phone


@pytest.mark.django_db
def test_profile_patch_no_change(authenticated_client):
    url = reverse('profile')
    original_username = authenticated_client.user.username
    original_phone = authenticated_client.user.phone
    data = {} # Empty data, should not change anything
    response = authenticated_client.patch(url, data, format='json')
    assert response.status_code == status.HTTP_200_OK
    assert response.data == {'message': 'Profile updated.'}

    authenticated_client.user.refresh_from_db()
    assert authenticated_client.user.username == original_username
    assert authenticated_client.user.phone == original_phone