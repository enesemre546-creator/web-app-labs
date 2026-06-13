"""
Lab 04 — Notes API with JWT Authentication, Middleware & Testing (Flask)
Student: Enes Emre Hasturk
Student ID: 7949

Description:
    A secure notes API with:
    - User registration and login with hashed passwords
    - JWT (JSON Web Token) authentication
    - Role-based access: regular users see only their own notes,
      admins can see and manage all notes
    - Request logging middleware (before/after request hooks)
    - Automated tests (run with pytest)

Endpoints:
    POST   /auth/register         — register a new user
    POST   /auth/login            — login and get JWT token
    GET    /auth/me               — get current user info (auth required)

    GET    /notes                 — list notes (own notes, or all for admin)
    GET    /notes/<id>            — get a single note (own or admin)
    POST   /notes                 — create a note (auth required)
    PUT    /notes/<id>            — update a note (own or admin)
    DELETE /notes/<id>            — delete a note (own or admin)

    GET    /admin/users           — list all users (admin only) [Task 4]

Graded Tasks implemented:
    Task 1 — User registration with hashed password (bcrypt)
    Task 2 — JWT login: return token, protect routes via @require_auth decorator
    Task 3 — Middleware: log every request method+path+status+response time
    Task 4 — Admin-only route: GET /admin/users (role-based access control)
    Task 5 — Automated pytest tests covering register, login, create/read note
"""

from flask import Flask, request, jsonify, g, abort
from flask_sqlalchemy import SQLAlchemy
from functools import wraps
from datetime import datetime, timezone, timedelta
import bcrypt
import jwt
import time

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///notes.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["JWT_SECRET"] = "super-secret-key-change-in-production"
app.config["JWT_EXPIRY_HOURS"] = 12

db = SQLAlchemy(app)


# ─────────────────────────────────────────────────────────────
# Models
# ─────────────────────────────────────────────────────────────

class User(db.Model):
    __tablename__ = "users"

    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(80), unique=True, nullable=False)
    email         = db.Column(db.String(200), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role          = db.Column(db.String(20), default="user")  # "user" or "admin"
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

    notes = db.relationship("Note", backref="owner", lazy=True, cascade="all, delete-orphan")

    def set_password(self, password: str):
        """Hash and store the password using bcrypt."""
        self.password_hash = bcrypt.hashpw(
            password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")

    def check_password(self, password: str) -> bool:
        """Verify a plaintext password against the stored hash."""
        return bcrypt.checkpw(password.encode("utf-8"), self.password_hash.encode("utf-8"))

    def generate_token(self) -> str:
        """Generate a JWT token valid for JWT_EXPIRY_HOURS hours."""
        payload = {
            "user_id":  self.id,
            "username": self.username,
            "role":     self.role,
            "exp":      datetime.now(tz=timezone.utc) + timedelta(hours=app.config["JWT_EXPIRY_HOURS"]),
        }
        return jwt.encode(payload, app.config["JWT_SECRET"], algorithm="HS256")

    def to_dict(self):
        return {
            "id":         self.id,
            "username":   self.username,
            "email":      self.email,
            "role":       self.role,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Note(db.Model):
    __tablename__ = "notes"

    id         = db.Column(db.Integer, primary_key=True)
    title      = db.Column(db.String(200), nullable=False)
    content    = db.Column(db.Text, nullable=False)
    is_private = db.Column(db.Boolean, default=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id":         self.id,
            "title":      self.title,
            "content":    self.content,
            "is_private": self.is_private,
            "user_id":    self.user_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


with app.app_context():
    db.create_all()


# ─────────────────────────────────────────────────────────────
# Task 3 — Middleware: request logging
# ─────────────────────────────────────────────────────────────

@app.before_request
def start_timer():
    """Record the request start time."""
    g.start_time = time.perf_counter()


@app.after_request
def log_request(response):
    """Log each request: method, path, status code, and duration."""
    duration_ms = (time.perf_counter() - g.start_time) * 1000
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(
        f"[{timestamp}] {request.method} {request.path} "
        f"→ {response.status_code} ({duration_ms:.1f}ms)"
    )
    return response


# ─────────────────────────────────────────────────────────────
# Task 2 — Auth decorators
# ─────────────────────────────────────────────────────────────

def decode_token(token: str) -> dict:
    """Decode a JWT token; abort 401 on failure."""
    try:
        return jwt.decode(token, app.config["JWT_SECRET"], algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        abort(401, description="Token has expired")
    except jwt.InvalidTokenError:
        abort(401, description="Invalid token")


def get_token_from_header() -> str:
    """Extract Bearer token from Authorization header."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        abort(401, description="Authorization header missing or malformed. Use: Bearer <token>")
    return auth_header.split(" ", 1)[1]


def require_auth(f):
    """Decorator: require a valid JWT. Sets g.current_user."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = get_token_from_header()
        payload = decode_token(token)
        user = db.session.get(User, payload["user_id"])
        if user is None:
            abort(401, description="User no longer exists")
        g.current_user = user
        return f(*args, **kwargs)
    return decorated


def require_admin(f):
    """
    Task 4 — Decorator: require admin role.
    Must be used after @require_auth.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if g.current_user.role != "admin":
            abort(403, description="Admin access required")
        return f(*args, **kwargs)
    return decorated


# ─────────────────────────────────────────────────────────────
# Auth routes
# ─────────────────────────────────────────────────────────────

@app.route("/auth/register", methods=["POST"])
def register():
    """
    Task 1 — Register a new user.
    Required: username, email, password
    Optional: role (default 'user'; only first user automatically becomes 'admin')
    """
    data = request.get_json()
    if not data:
        abort(400, description="Request body must be JSON")

    errors = {}
    if not data.get("username", "").strip():
        errors["username"] = "Required"
    if not data.get("email", "").strip():
        errors["email"] = "Required"
    if not data.get("password", ""):
        errors["password"] = "Required"
    elif len(data["password"]) < 6:
        errors["password"] = "Must be at least 6 characters"

    if errors:
        return jsonify({"error": "Validation failed", "details": errors}), 422

    username = data["username"].strip()
    email    = data["email"].strip().lower()

    if User.query.filter_by(username=username).first():
        abort(409, description=f"Username '{username}' is already taken")
    if User.query.filter_by(email=email).first():
        abort(409, description=f"Email '{email}' is already registered")

    # First user ever becomes admin automatically
    role = "admin" if User.query.count() == 0 else "user"

    user = User(username=username, email=email, role=role)
    user.set_password(data["password"])
    db.session.add(user)
    db.session.commit()

    return jsonify({
        "message": "Registration successful",
        "user":    user.to_dict(),
    }), 201


@app.route("/auth/login", methods=["POST"])
def login():
    """
    Task 2 — Login and receive a JWT.
    Required: username, password
    """
    data = request.get_json()
    if not data:
        abort(400, description="Request body must be JSON")

    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        abort(400, description="'username' and 'password' are required")

    user = User.query.filter_by(username=username).first()
    if user is None or not user.check_password(password):
        abort(401, description="Invalid username or password")

    token = user.generate_token()
    return jsonify({
        "message":    "Login successful",
        "token":      token,
        "token_type": "Bearer",
        "expires_in": f"{app.config['JWT_EXPIRY_HOURS']} hours",
        "user":       user.to_dict(),
    })


@app.route("/auth/me", methods=["GET"])
@require_auth
def get_me():
    """Return information about the currently authenticated user."""
    return jsonify(g.current_user.to_dict())


# ─────────────────────────────────────────────────────────────
# Notes routes (auth required)
# ─────────────────────────────────────────────────────────────

@app.route("/notes", methods=["GET"])
@require_auth
def list_notes():
    """
    List notes.
    - Regular users see only their own notes.
    - Admins see all notes (can filter by ?user_id=).
    """
    user = g.current_user
    if user.role == "admin":
        user_id_filter = request.args.get("user_id")
        query = Note.query
        if user_id_filter:
            try:
                query = query.filter(Note.user_id == int(user_id_filter))
            except ValueError:
                abort(400, description="'user_id' must be an integer")
    else:
        query = Note.query.filter_by(user_id=user.id)

    notes = query.order_by(Note.created_at.desc()).all()
    return jsonify([n.to_dict() for n in notes])


@app.route("/notes/<int:note_id>", methods=["GET"])
@require_auth
def get_note(note_id):
    """Get a single note. Users can only access their own notes; admins can access any."""
    note = db.session.get(Note, note_id)
    if note is None:
        abort(404, description=f"Note with id {note_id} not found")
    if g.current_user.role != "admin" and note.user_id != g.current_user.id:
        abort(403, description="You do not have permission to access this note")
    return jsonify(note.to_dict())


@app.route("/notes", methods=["POST"])
@require_auth
def create_note():
    """Create a new note (automatically assigned to the authenticated user)."""
    data = request.get_json()
    if not data:
        abort(400, description="Request body must be JSON")

    errors = {}
    if not data.get("title", "").strip():
        errors["title"] = "Required"
    if not data.get("content", "").strip():
        errors["content"] = "Required"
    if errors:
        return jsonify({"error": "Validation failed", "details": errors}), 422

    note = Note(
        title      = data["title"].strip(),
        content    = data["content"].strip(),
        is_private = bool(data.get("is_private", True)),
        user_id    = g.current_user.id,
    )
    db.session.add(note)
    db.session.commit()
    return jsonify(note.to_dict()), 201


@app.route("/notes/<int:note_id>", methods=["PUT"])
@require_auth
def update_note(note_id):
    """Update a note. Users can only update their own; admins can update any."""
    note = db.session.get(Note, note_id)
    if note is None:
        abort(404, description=f"Note with id {note_id} not found")
    if g.current_user.role != "admin" and note.user_id != g.current_user.id:
        abort(403, description="You do not have permission to edit this note")

    data = request.get_json()
    if not data:
        abort(400, description="Request body must be JSON")

    if "title"      in data: note.title      = data["title"].strip()
    if "content"    in data: note.content    = data["content"].strip()
    if "is_private" in data: note.is_private = bool(data["is_private"])
    note.updated_at = datetime.utcnow()

    db.session.commit()
    return jsonify(note.to_dict())


@app.route("/notes/<int:note_id>", methods=["DELETE"])
@require_auth
def delete_note(note_id):
    """Delete a note. Users can only delete their own; admins can delete any."""
    note = db.session.get(Note, note_id)
    if note is None:
        abort(404, description=f"Note with id {note_id} not found")
    if g.current_user.role != "admin" and note.user_id != g.current_user.id:
        abort(403, description="You do not have permission to delete this note")

    db.session.delete(note)
    db.session.commit()
    return "", 204


# ─────────────────────────────────────────────────────────────
# Task 4 — Admin-only routes
# ─────────────────────────────────────────────────────────────

@app.route("/admin/users", methods=["GET"])
@require_auth
@require_admin
def list_users():
    """
    Task 4 — List all registered users (admin only).
    """
    users = User.query.order_by(User.id).all()
    return jsonify([u.to_dict() for u in users])


@app.route("/admin/users/<int:user_id>", methods=["DELETE"])
@require_auth
@require_admin
def delete_user(user_id):
    """Task 4 — Admin can delete any user account."""
    user = db.session.get(User, user_id)
    if user is None:
        abort(404, description=f"User with id {user_id} not found")
    if user.id == g.current_user.id:
        abort(400, description="You cannot delete your own account")
    db.session.delete(user)
    db.session.commit()
    return "", 204


# ─────────────────────────────────────────────────────────────
# Error handlers
# ─────────────────────────────────────────────────────────────
@app.errorhandler(400)
def bad_request(e):
    return jsonify({"error": "Bad Request", "message": str(e.description)}), 400

@app.errorhandler(401)
def unauthorized(e):
    return jsonify({"error": "Unauthorized", "message": str(e.description)}), 401

@app.errorhandler(403)
def forbidden(e):
    return jsonify({"error": "Forbidden", "message": str(e.description)}), 403

@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Not Found", "message": str(e.description)}), 404

@app.errorhandler(409)
def conflict(e):
    return jsonify({"error": "Conflict", "message": str(e.description)}), 409

@app.errorhandler(422)
def unprocessable(e):
    return jsonify({"error": "Unprocessable Entity", "message": str(e.description)}), 422


# ─────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True, port=5003)
