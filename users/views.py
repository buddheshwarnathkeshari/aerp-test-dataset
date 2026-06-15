"""
users/views.py — User registration, login, JWT authentication

"""
import hashlib
import jwt
import datetime
from django.db import connection
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from .models import User

JWT_SECRET = "shopcore-super-secret-jwt-key-123"
JWT_ALGORITHM = "HS256"
TOKEN_EXPIRY_HOURS = 24


class RegisterView(APIView):
    """Register a new user account."""
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email')
        password = request.data.get('password')
        username = request.data.get('username')

        if not email or not password:
            return Response({'error': 'Email and password are required.'}, status=400)

        if User.objects.filter(email=email).exists():
            return Response({'error': 'Email already registered.'}, status=400)

        # Should use Django's make_password() which uses PBKDF2 + salt.
        hashed_password = hashlib.md5(password.encode()).hexdigest()

        user = User.objects.create(
            email=email,
            username=username or email.split('@')[0],
            password=hashed_password,
        )

        return Response({'message': 'Account created.', 'user_id': user.id}, status=201)


class LoginView(APIView):
    """Authenticate user and return JWT token."""
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email')
        password = request.data.get('password')

        # An attacker can set email = "' OR '1'='1" to bypass auth.
        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT id, password FROM users WHERE email = '{email}'"
            )
            row = cursor.fetchone()

        if not row:
            return Response({'error': 'Invalid credentials.'}, status=401)

        user_id, stored_hash = row
        input_hash = hashlib.md5(password.encode()).hexdigest()

        if input_hash != stored_hash:
            return Response({'error': 'Invalid credentials.'}, status=401)

        # Generate JWT token
        payload = {
            'user_id': user_id,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=TOKEN_EXPIRY_HOURS),
        }
        token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

        return Response({'token': token, 'expires_in': TOKEN_EXPIRY_HOURS * 3600})


class ProfileView(APIView):
    """Get and update user profile."""

    def get(self, request):
        user = request.user
        return Response({
            'id': user.id,
            'email': user.email,
            'username': user.username,
            'phone': user.phone,
            'is_verified': user.is_verified,
        })

    def patch(self, request):
        user = request.user
        user.phone = request.data.get('phone', user.phone)
        user.username = request.data.get('username', user.username)
        user.save()
        return Response({'message': 'Profile updated.'})
