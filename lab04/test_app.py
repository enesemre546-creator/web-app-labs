"""
Lab 04 — Automated Tests (Task 5)
Student: Enes Emre Hasturk
Student ID: 7949

Run tests with:
    pip install pytest
    pytest test_app.py -v

These tests cover:
    - User registration (success, duplicate, missing fields)
    - User login (success, wrong password)
    - Accessing protected route without token (401)
    - Creating a note (auth required)
    - Listing own notes (user sees only their own)
    - Admin getting list of all users
    - Forbidden access (user trying admin route)
"""

import pytest
import json
from app import app, db, User, Note


# ─────────────────────────────────────────────────────────────
# Test configuration
# ─────────────────────────────────────────────────────────────

@pytest.fixture
def client():
    """
    Set up a Flask test client with an in-memory SQLite database.
    Each test gets a clean database state.
    """
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["JWT_SECRET"] = "test-secret-key"

    with app.test_client() as client:
        with app.app_context():
            db.create_all()
            yield client
            db.session.remove()
            db.drop_all()


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def register_user(client, username="testuser", email="test@example.com", password="password123"):
    """Helper: register a user and return response JSON."""
    return client.post(
        "/auth/register",
        data=json.dumps({"username": username, "email": email, "password": password}),
        content_type="application/json",
    )

def login_user(client, username="testuser", password="password123"):
    """Helper: login and return token string."""
    resp = client.post(
        "/auth/login",
        data=json.dumps({"username": username, "password": password}),
        content_type="application/json",
    )
    assert resp.status_code == 200, f"Login failed: {resp.get_json()}"
    return resp.get_json()["token"]

def auth_headers(token: str) -> dict:
    """Return Authorization headers for a JWT token."""
    return {"Authorization": f"Bearer {token}"}


# ─────────────────────────────────────────────────────────────
# Task 5 — Tests: Registration
# ─────────────────────────────────────────────────────────────

class TestRegistration:

    def test_register_success(self, client):
        """A valid registration returns 201 and user data."""
        resp = register_user(client)
        assert resp.status_code == 201
        data = resp.get_json()
        assert "user" in data
        assert data["user"]["username"] == "testuser"
        assert data["user"]["role"] == "admin"   # first user is admin

    def test_register_second_user_is_regular(self, client):
        """Second registered user has role 'user'."""
        register_user(client, username="admin", email="admin@example.com")
        resp = register_user(client, username="bob", email="bob@example.com")
        assert resp.status_code == 201
        assert resp.get_json()["user"]["role"] == "user"

    def test_register_duplicate_username(self, client):
        """Registering with a duplicate username returns 409."""
        register_user(client)
        resp = register_user(client)  # same username
        assert resp.status_code == 409

    def test_register_missing_fields(self, client):
        """Registration without required fields returns 422."""
        resp = client.post(
            "/auth/register",
            data=json.dumps({"username": "nobody"}),
            content_type="application/json",
        )
        assert resp.status_code == 422
        details = resp.get_json()["details"]
        assert "email" in details
        assert "password" in details

    def test_register_short_password(self, client):
        """Password shorter than 6 characters is rejected."""
        resp = register_user(client, password="abc")
        assert resp.status_code == 422
        assert "password" in resp.get_json()["details"]


# ─────────────────────────────────────────────────────────────
# Tests: Login
# ─────────────────────────────────────────────────────────────

class TestLogin:

    def test_login_success(self, client):
        """Valid login returns a JWT token."""
        register_user(client)
        resp = client.post(
            "/auth/login",
            data=json.dumps({"username": "testuser", "password": "password123"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "token" in data
        assert data["token_type"] == "Bearer"

    def test_login_wrong_password(self, client):
        """Wrong password returns 401."""
        register_user(client)
        resp = client.post(
            "/auth/login",
            data=json.dumps({"username": "testuser", "password": "wrongpassword"}),
            content_type="application/json",
        )
        assert resp.status_code == 401

    def test_login_unknown_user(self, client):
        """Login for non-existent user returns 401."""
        resp = client.post(
            "/auth/login",
            data=json.dumps({"username": "ghost", "password": "password123"}),
            content_type="application/json",
        )
        assert resp.status_code == 401


# ─────────────────────────────────────────────────────────────
# Tests: Auth middleware
# ─────────────────────────────────────────────────────────────

class TestAuthMiddleware:

    def test_protected_route_without_token(self, client):
        """Accessing a protected route without a token returns 401."""
        resp = client.get("/notes")
        assert resp.status_code == 401

    def test_protected_route_with_invalid_token(self, client):
        """Accessing a protected route with a bad token returns 401."""
        resp = client.get("/notes", headers={"Authorization": "Bearer invalid.token.here"})
        assert resp.status_code == 401

    def test_get_me_returns_current_user(self, client):
        """GET /auth/me returns the authenticated user's info."""
        register_user(client)
        token = login_user(client)
        resp = client.get("/auth/me", headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.get_json()["username"] == "testuser"


# ─────────────────────────────────────────────────────────────
# Tests: Notes
# ─────────────────────────────────────────────────────────────

class TestNotes:

    def test_create_note(self, client):
        """Authenticated user can create a note."""
        register_user(client)
        token = login_user(client)
        resp = client.post(
            "/notes",
            data=json.dumps({"title": "My First Note", "content": "Hello, world!"}),
            content_type="application/json",
            headers=auth_headers(token),
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["title"] == "My First Note"
        assert data["content"] == "Hello, world!"

    def test_create_note_missing_title(self, client):
        """Creating a note without a title returns 422."""
        register_user(client)
        token = login_user(client)
        resp = client.post(
            "/notes",
            data=json.dumps({"content": "No title here"}),
            content_type="application/json",
            headers=auth_headers(token),
        )
        assert resp.status_code == 422

    def test_list_notes_only_own(self, client):
        """Users only see their own notes."""
        # Create user 1 (admin) and their note
        register_user(client, "alice", "alice@example.com")
        token1 = login_user(client, "alice")
        client.post(
            "/notes",
            data=json.dumps({"title": "Alice note", "content": "Private"}),
            content_type="application/json",
            headers=auth_headers(token1),
        )

        # Create user 2 (regular) and their note
        register_user(client, "bob", "bob@example.com")
        token2 = login_user(client, "bob")
        client.post(
            "/notes",
            data=json.dumps({"title": "Bob note", "content": "Also private"}),
            content_type="application/json",
            headers=auth_headers(token2),
        )

        # Bob should only see his own note
        resp = client.get("/notes", headers=auth_headers(token2))
        notes = resp.get_json()
        assert len(notes) == 1
        assert notes[0]["title"] == "Bob note"

    def test_delete_own_note(self, client):
        """User can delete their own note."""
        register_user(client)
        token = login_user(client)

        create_resp = client.post(
            "/notes",
            data=json.dumps({"title": "To delete", "content": "Bye!"}),
            content_type="application/json",
            headers=auth_headers(token),
        )
        note_id = create_resp.get_json()["id"]

        del_resp = client.delete(f"/notes/{note_id}", headers=auth_headers(token))
        assert del_resp.status_code == 204

    def test_cannot_access_other_users_note(self, client):
        """User cannot read another user's private note."""
        # Alice registers first → admin
        register_user(client, "alice", "alice@example.com")
        token_alice = login_user(client, "alice")
        note_resp = client.post(
            "/notes",
            data=json.dumps({"title": "Secret", "content": "Top secret"}),
            content_type="application/json",
            headers=auth_headers(token_alice),
        )
        note_id = note_resp.get_json()["id"]

        # Bob is regular user
        register_user(client, "bob", "bob@example.com")
        token_bob = login_user(client, "bob")

        resp = client.get(f"/notes/{note_id}", headers=auth_headers(token_bob))
        assert resp.status_code == 403


# ─────────────────────────────────────────────────────────────
# Tests: Admin routes (Task 4)
# ─────────────────────────────────────────────────────────────

class TestAdminRoutes:

    def test_admin_can_list_users(self, client):
        """Admin can call GET /admin/users and see all users."""
        # First user → admin
        register_user(client, "admin", "admin@example.com")
        token = login_user(client, "admin")
        register_user(client, "bob", "bob@example.com")

        resp = client.get("/admin/users", headers=auth_headers(token))
        assert resp.status_code == 200
        users = resp.get_json()
        assert len(users) == 2

    def test_regular_user_cannot_list_users(self, client):
        """A regular user receives 403 when calling GET /admin/users."""
        register_user(client, "admin", "admin@example.com")   # becomes admin
        register_user(client, "bob", "bob@example.com")       # regular user
        token_bob = login_user(client, "bob")

        resp = client.get("/admin/users", headers=auth_headers(token_bob))
        assert resp.status_code == 403
