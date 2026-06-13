"""
Lab 02 — Books API with Full CRUD and Data Validation (Flask + SQLAlchemy)
Student: Enes Emre Hasturk
Student ID: 7949

Description:
    A persistent book collection API backed by SQLite via Flask-SQLAlchemy.
    Demonstrates proper request body validation, HTTP status codes, and
    structured error responses.

Endpoints:
    GET    /books              — list all books (with optional filters)
    GET    /books/<id>         — get a single book
    POST   /books              — create a new book (with validation)
    PUT    /books/<id>         — update a book (with validation)
    PATCH  /books/<id>         — partially update a book
    DELETE /books/<id>         — delete a book
    GET    /books/genres       — list all distinct genres (Task 3)
    GET    /books/stats        — statistics about the collection (Task 4)
    GET    /books/search       — search by title/author/genre (Task 5)

Graded Tasks implemented:
    Task 1 — POST /books with full validation (title, author, year, genre required)
    Task 2 — PATCH /books/<id> for partial updates
    Task 3 — GET /books/genres listing all unique genres stored
    Task 4 — GET /books/stats with count, avg rating, newest/oldest year
    Task 5 — GET /books/search?q=keyword searching title, author, genre
"""

from flask import Flask, request, jsonify, abort
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///books.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# ─────────────────────────────────────────────────────────────
# Model
# ─────────────────────────────────────────────────────────────

class Book(db.Model):
    __tablename__ = "books"

    id          = db.Column(db.Integer, primary_key=True)
    title       = db.Column(db.String(255), nullable=False)
    author      = db.Column(db.String(255), nullable=False)
    year        = db.Column(db.Integer, nullable=False)
    genre       = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, default="")
    rating      = db.Column(db.Float, nullable=True)   # 1.0 – 10.0
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id":          self.id,
            "title":       self.title,
            "author":      self.author,
            "year":        self.year,
            "genre":       self.genre,
            "description": self.description,
            "rating":      self.rating,
            "created_at":  self.created_at.isoformat() if self.created_at else None,
        }


with app.app_context():
    db.create_all()


# ─────────────────────────────────────────────────────────────
# Validation helper
# ─────────────────────────────────────────────────────────────

CURRENT_YEAR = datetime.utcnow().year

def validate_book_data(data: dict, require_all: bool = True) -> dict:
    """
    Validate book fields.
    - require_all=True  → all required fields must be present (POST)
    - require_all=False → only validate fields that are present (PATCH)
    Returns a dict of errors (empty means valid).
    """
    errors = {}

    if require_all:
        for field in ("title", "author", "year", "genre"):
            if field not in data:
                errors[field] = f"'{field}' is required"

    if "title" in data:
        if not isinstance(data["title"], str) or not data["title"].strip():
            errors["title"] = "Title must be a non-empty string"

    if "author" in data:
        if not isinstance(data["author"], str) or not data["author"].strip():
            errors["author"] = "Author must be a non-empty string"

    if "year" in data:
        try:
            year = int(data["year"])
            if year < 1000 or year > CURRENT_YEAR:
                errors["year"] = f"Year must be between 1000 and {CURRENT_YEAR}"
        except (TypeError, ValueError):
            errors["year"] = "Year must be an integer"

    if "genre" in data:
        if not isinstance(data["genre"], str) or not data["genre"].strip():
            errors["genre"] = "Genre must be a non-empty string"

    if "rating" in data and data["rating"] is not None:
        try:
            rating = float(data["rating"])
            if not (1.0 <= rating <= 10.0):
                errors["rating"] = "Rating must be between 1.0 and 10.0"
        except (TypeError, ValueError):
            errors["rating"] = "Rating must be a number between 1.0 and 10.0"

    return errors


# ─────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────

@app.route("/books", methods=["GET"])
def list_books():
    """
    List all books.
    Optional query params:
        ?genre=Fiction    — filter by genre (case-insensitive)
        ?author=Tolkien   — filter by author name (partial match)
        ?year=1954        — filter by publication year
    """
    query = Book.query

    genre = request.args.get("genre")
    if genre:
        query = query.filter(Book.genre.ilike(f"%{genre}%"))

    author = request.args.get("author")
    if author:
        query = query.filter(Book.author.ilike(f"%{author}%"))

    year_param = request.args.get("year")
    if year_param:
        try:
            query = query.filter(Book.year == int(year_param))
        except ValueError:
            abort(400, description="'year' must be an integer")

    books = query.order_by(Book.id).all()
    return jsonify([b.to_dict() for b in books])


@app.route("/books/genres", methods=["GET"])
def list_genres():
    """
    Task 3 — Return a list of all distinct genres in the database.
    """
    genres = db.session.query(Book.genre).distinct().order_by(Book.genre).all()
    return jsonify([g[0] for g in genres])


@app.route("/books/stats", methods=["GET"])
def get_stats():
    """
    Task 4 — Return statistics about the book collection.
    """
    total = Book.query.count()
    if total == 0:
        return jsonify({
            "total": 0,
            "average_rating": None,
            "oldest_year": None,
            "newest_year": None,
            "genres_count": 0,
        })

    avg_rating = db.session.query(
        db.func.avg(Book.rating)
    ).filter(Book.rating.isnot(None)).scalar()

    oldest = db.session.query(db.func.min(Book.year)).scalar()
    newest = db.session.query(db.func.max(Book.year)).scalar()
    genres_count = db.session.query(db.func.count(Book.genre.distinct())).scalar()

    return jsonify({
        "total": total,
        "average_rating": round(avg_rating, 2) if avg_rating else None,
        "oldest_year": oldest,
        "newest_year": newest,
        "genres_count": genres_count,
    })


@app.route("/books/search", methods=["GET"])
def search_books():
    """
    Task 5 — Full-text search across title, author, and genre.
    Usage: GET /books/search?q=<keyword>
    """
    keyword = request.args.get("q", "").strip()
    if not keyword:
        abort(400, description="Query parameter 'q' is required")

    pattern = f"%{keyword}%"
    books = Book.query.filter(
        db.or_(
            Book.title.ilike(pattern),
            Book.author.ilike(pattern),
            Book.genre.ilike(pattern),
        )
    ).all()
    return jsonify([b.to_dict() for b in books])


@app.route("/books/<int:book_id>", methods=["GET"])
def get_book(book_id):
    """Retrieve a single book by ID."""
    book = Book.query.get_or_404(book_id, description=f"Book with id {book_id} not found")
    return jsonify(book.to_dict())


@app.route("/books", methods=["POST"])
def create_book():
    """
    Task 1 — Create a new book with full validation.
    Required: title, author, year, genre
    Optional: description, rating (1.0–10.0)
    """
    data = request.get_json()
    if not data:
        abort(400, description="Request body must be JSON")

    errors = validate_book_data(data, require_all=True)
    if errors:
        return jsonify({"error": "Validation failed", "details": errors}), 422

    book = Book(
        title       = data["title"].strip(),
        author      = data["author"].strip(),
        year        = int(data["year"]),
        genre       = data["genre"].strip(),
        description = str(data.get("description", "")).strip(),
        rating      = float(data["rating"]) if data.get("rating") is not None else None,
    )
    db.session.add(book)
    db.session.commit()
    return jsonify(book.to_dict()), 201


@app.route("/books/<int:book_id>", methods=["PUT"])
def update_book(book_id):
    """Full update — all required fields must be supplied."""
    book = Book.query.get_or_404(book_id, description=f"Book with id {book_id} not found")
    data = request.get_json()
    if not data:
        abort(400, description="Request body must be JSON")

    errors = validate_book_data(data, require_all=True)
    if errors:
        return jsonify({"error": "Validation failed", "details": errors}), 422

    book.title       = data["title"].strip()
    book.author      = data["author"].strip()
    book.year        = int(data["year"])
    book.genre       = data["genre"].strip()
    book.description = str(data.get("description", "")).strip()
    book.rating      = float(data["rating"]) if data.get("rating") is not None else book.rating

    db.session.commit()
    return jsonify(book.to_dict())


@app.route("/books/<int:book_id>", methods=["PATCH"])
def partial_update_book(book_id):
    """
    Task 2 — Partial update: only supplied fields are modified.
    """
    book = Book.query.get_or_404(book_id, description=f"Book with id {book_id} not found")
    data = request.get_json()
    if not data:
        abort(400, description="Request body must be JSON")

    errors = validate_book_data(data, require_all=False)
    if errors:
        return jsonify({"error": "Validation failed", "details": errors}), 422

    if "title"       in data: book.title       = data["title"].strip()
    if "author"      in data: book.author      = data["author"].strip()
    if "year"        in data: book.year        = int(data["year"])
    if "genre"       in data: book.genre       = data["genre"].strip()
    if "description" in data: book.description = str(data["description"]).strip()
    if "rating"      in data: book.rating      = float(data["rating"]) if data["rating"] is not None else None

    db.session.commit()
    return jsonify(book.to_dict())


@app.route("/books/<int:book_id>", methods=["DELETE"])
def delete_book(book_id):
    """Delete a book by ID."""
    book = Book.query.get_or_404(book_id, description=f"Book with id {book_id} not found")
    db.session.delete(book)
    db.session.commit()
    return "", 204


# ─────────────────────────────────────────────────────────────
# Error handlers
# ─────────────────────────────────────────────────────────────
@app.errorhandler(400)
def bad_request(e):
    return jsonify({"error": "Bad Request", "message": str(e.description)}), 400

@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Not Found", "message": str(e.description)}), 404

@app.errorhandler(422)
def unprocessable(e):
    return jsonify({"error": "Unprocessable Entity", "message": str(e.description)}), 422


# ─────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True, port=5001)
