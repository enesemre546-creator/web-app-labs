"""
Lab 03 — Library Management System (Flask + SQLAlchemy + Relationships)
Student: Enes Emre Hasturk
Student ID: 7949

Description:
    A library management API demonstrating:
    - Persistent SQLite database via Flask-SQLAlchemy
    - One-to-many relationships (Author → Books)
    - Many-to-many relationships (Books ↔ Tags)
    - Dependency injection pattern via Flask's application context
    - Blueprint-based route organisation

Models:
    Author   — has many Books
    Tag      — can be on many Books (M:N via association table)
    Book     — belongs to an Author, has many Tags

Graded Tasks implemented:
    Task 1 — Author CRUD with cascading delete (deletes their books)
    Task 2 — Book CRUD with author_id foreign key (validated against DB)
    Task 3 — Tag management and assigning tags to books (M:N relationship)
    Task 4 — GET /authors/<id>/books — list books by a specific author
    Task 5 — GET /books/<id>/tags and POST /books/<id>/tags — manage book tags
"""

from flask import Flask, request, jsonify, abort
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///library.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# ─────────────────────────────────────────────────────────────
# Association table (Books ↔ Tags — many-to-many)
# ─────────────────────────────────────────────────────────────
book_tags = db.Table(
    "book_tags",
    db.Column("book_id", db.Integer, db.ForeignKey("books.id"), primary_key=True),
    db.Column("tag_id",  db.Integer, db.ForeignKey("tags.id"),  primary_key=True),
)


# ─────────────────────────────────────────────────────────────
# Models
# ─────────────────────────────────────────────────────────────

class Author(db.Model):
    __tablename__ = "authors"

    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(200), nullable=False, unique=True)
    bio        = db.Column(db.Text, default="")
    birth_year = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # one-to-many: cascade deletes books when author is deleted
    books = db.relationship("Book", backref="author", lazy=True, cascade="all, delete-orphan")

    def to_dict(self, include_books: bool = False):
        data = {
            "id":         self.id,
            "name":       self.name,
            "bio":        self.bio,
            "birth_year": self.birth_year,
            "book_count": len(self.books),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_books:
            data["books"] = [b.to_dict() for b in self.books]
        return data


class Tag(db.Model):
    __tablename__ = "tags"

    id   = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)

    def to_dict(self):
        return {"id": self.id, "name": self.name}


class Book(db.Model):
    __tablename__ = "books"

    id          = db.Column(db.Integer, primary_key=True)
    title       = db.Column(db.String(300), nullable=False)
    year        = db.Column(db.Integer, nullable=False)
    isbn        = db.Column(db.String(20), unique=True, nullable=True)
    synopsis    = db.Column(db.Text, default="")
    author_id   = db.Column(db.Integer, db.ForeignKey("authors.id"), nullable=False)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    # many-to-many with tags
    tags = db.relationship("Tag", secondary=book_tags, lazy="subquery", backref=db.backref("books", lazy=True))

    def to_dict(self, include_author: bool = True, include_tags: bool = True):
        data = {
            "id":         self.id,
            "title":      self.title,
            "year":       self.year,
            "isbn":       self.isbn,
            "synopsis":   self.synopsis,
            "author_id":  self.author_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_author and self.author:
            data["author_name"] = self.author.name
        if include_tags:
            data["tags"] = [t.to_dict() for t in self.tags]
        return data


with app.app_context():
    db.create_all()


# ─────────────────────────────────────────────────────────────
# Dependency injection helpers (Flask app context pattern)
# ─────────────────────────────────────────────────────────────

def get_author_or_404(author_id: int) -> Author:
    author = db.session.get(Author, author_id)
    if author is None:
        abort(404, description=f"Author with id {author_id} not found")
    return author

def get_book_or_404(book_id: int) -> Book:
    book = db.session.get(Book, book_id)
    if book is None:
        abort(404, description=f"Book with id {book_id} not found")
    return book

def get_tag_or_404(tag_id: int) -> Tag:
    tag = db.session.get(Tag, tag_id)
    if tag is None:
        abort(404, description=f"Tag with id {tag_id} not found")
    return tag


# ─────────────────────────────────────────────────────────────
# Author routes (Task 1)
# ─────────────────────────────────────────────────────────────

@app.route("/authors", methods=["GET"])
def list_authors():
    """List all authors."""
    authors = Author.query.order_by(Author.name).all()
    return jsonify([a.to_dict() for a in authors])


@app.route("/authors/<int:author_id>", methods=["GET"])
def get_author(author_id):
    """Get a single author, including their books."""
    author = get_author_or_404(author_id)
    return jsonify(author.to_dict(include_books=True))


@app.route("/authors", methods=["POST"])
def create_author():
    """Create a new author. Required: name."""
    data = request.get_json()
    if not data or not data.get("name", "").strip():
        abort(400, description="'name' is required")

    if Author.query.filter_by(name=data["name"].strip()).first():
        abort(409, description=f"Author '{data['name'].strip()}' already exists")

    author = Author(
        name       = data["name"].strip(),
        bio        = str(data.get("bio", "")).strip(),
        birth_year = int(data["birth_year"]) if data.get("birth_year") else None,
    )
    db.session.add(author)
    db.session.commit()
    return jsonify(author.to_dict()), 201


@app.route("/authors/<int:author_id>", methods=["PUT"])
def update_author(author_id):
    """Update an author."""
    author = get_author_or_404(author_id)
    data = request.get_json()
    if not data:
        abort(400, description="Request body must be JSON")

    if "name" in data:
        if not data["name"].strip():
            abort(400, description="'name' cannot be empty")
        # Check uniqueness if name is changing
        existing = Author.query.filter_by(name=data["name"].strip()).first()
        if existing and existing.id != author_id:
            abort(409, description=f"Author '{data['name'].strip()}' already exists")
        author.name = data["name"].strip()

    if "bio"        in data: author.bio        = str(data["bio"]).strip()
    if "birth_year" in data: author.birth_year = int(data["birth_year"]) if data["birth_year"] else None

    db.session.commit()
    return jsonify(author.to_dict())


@app.route("/authors/<int:author_id>", methods=["DELETE"])
def delete_author(author_id):
    """
    Task 1 — Delete an author and all their books (cascading delete).
    """
    author = get_author_or_404(author_id)
    db.session.delete(author)
    db.session.commit()
    return "", 204


# ─────────────────────────────────────────────────────────────
# Author → Books (Task 4)
# ─────────────────────────────────────────────────────────────

@app.route("/authors/<int:author_id>/books", methods=["GET"])
def list_books_by_author(author_id):
    """
    Task 4 — List all books written by a specific author.
    """
    author = get_author_or_404(author_id)
    return jsonify({
        "author": author.to_dict(),
        "books": [b.to_dict() for b in author.books],
    })


# ─────────────────────────────────────────────────────────────
# Book routes (Task 2)
# ─────────────────────────────────────────────────────────────

@app.route("/books", methods=["GET"])
def list_books():
    """List all books with optional author_id filter."""
    query = Book.query
    author_id = request.args.get("author_id")
    if author_id:
        try:
            query = query.filter(Book.author_id == int(author_id))
        except ValueError:
            abort(400, description="'author_id' must be an integer")
    books = query.order_by(Book.id).all()
    return jsonify([b.to_dict() for b in books])


@app.route("/books/<int:book_id>", methods=["GET"])
def get_book(book_id):
    """Get a single book with author info and tags."""
    return jsonify(get_book_or_404(book_id).to_dict())


@app.route("/books", methods=["POST"])
def create_book():
    """
    Task 2 — Create a book with author_id validation.
    Required: title, year, author_id
    Optional: isbn, synopsis
    """
    data = request.get_json()
    if not data:
        abort(400, description="Request body must be JSON")

    errors = {}
    if not data.get("title", "").strip():
        errors["title"] = "Required"
    if "year" not in data:
        errors["year"] = "Required"
    if "author_id" not in data:
        errors["author_id"] = "Required"

    if errors:
        return jsonify({"error": "Validation failed", "details": errors}), 422

    # Validate author exists
    get_author_or_404(data["author_id"])

    # Validate ISBN uniqueness if provided
    isbn = data.get("isbn")
    if isbn and Book.query.filter_by(isbn=isbn).first():
        abort(409, description=f"ISBN '{isbn}' is already in use")

    book = Book(
        title     = data["title"].strip(),
        year      = int(data["year"]),
        author_id = int(data["author_id"]),
        isbn      = isbn,
        synopsis  = str(data.get("synopsis", "")).strip(),
    )
    db.session.add(book)
    db.session.commit()
    return jsonify(book.to_dict()), 201


@app.route("/books/<int:book_id>", methods=["PUT"])
def update_book(book_id):
    """Update a book (full update)."""
    book = get_book_or_404(book_id)
    data = request.get_json()
    if not data:
        abort(400, description="Request body must be JSON")

    if "author_id" in data:
        get_author_or_404(data["author_id"])
        book.author_id = int(data["author_id"])

    if "title"    in data: book.title    = data["title"].strip()
    if "year"     in data: book.year     = int(data["year"])
    if "isbn"     in data: book.isbn     = data["isbn"]
    if "synopsis" in data: book.synopsis = str(data["synopsis"]).strip()

    db.session.commit()
    return jsonify(book.to_dict())


@app.route("/books/<int:book_id>", methods=["DELETE"])
def delete_book(book_id):
    """Delete a book."""
    book = get_book_or_404(book_id)
    db.session.delete(book)
    db.session.commit()
    return "", 204


# ─────────────────────────────────────────────────────────────
# Tag routes (Task 3)
# ─────────────────────────────────────────────────────────────

@app.route("/tags", methods=["GET"])
def list_tags():
    """List all tags."""
    tags = Tag.query.order_by(Tag.name).all()
    return jsonify([t.to_dict() for t in tags])


@app.route("/tags", methods=["POST"])
def create_tag():
    """Task 3 — Create a new tag. Required: name."""
    data = request.get_json()
    if not data or not data.get("name", "").strip():
        abort(400, description="'name' is required")

    name = data["name"].strip().lower()
    if Tag.query.filter_by(name=name).first():
        abort(409, description=f"Tag '{name}' already exists")

    tag = Tag(name=name)
    db.session.add(tag)
    db.session.commit()
    return jsonify(tag.to_dict()), 201


@app.route("/tags/<int:tag_id>", methods=["DELETE"])
def delete_tag(tag_id):
    """Delete a tag (removes it from all books too)."""
    tag = get_tag_or_404(tag_id)
    db.session.delete(tag)
    db.session.commit()
    return "", 204


# ─────────────────────────────────────────────────────────────
# Book ↔ Tag management (Task 5)
# ─────────────────────────────────────────────────────────────

@app.route("/books/<int:book_id>/tags", methods=["GET"])
def get_book_tags(book_id):
    """Task 5 — List all tags assigned to a book."""
    book = get_book_or_404(book_id)
    return jsonify({"book_id": book_id, "tags": [t.to_dict() for t in book.tags]})


@app.route("/books/<int:book_id>/tags", methods=["POST"])
def add_tag_to_book(book_id):
    """
    Task 5 — Assign a tag to a book.
    Body: {"tag_id": 3}
    Returns 200 if already assigned (idempotent), 201 if newly added.
    """
    book = get_book_or_404(book_id)
    data = request.get_json()
    if not data or "tag_id" not in data:
        abort(400, description="'tag_id' is required")

    tag = get_tag_or_404(data["tag_id"])

    if tag in book.tags:
        return jsonify({"message": "Tag already assigned", "book_id": book_id, "tag": tag.to_dict()}), 200

    book.tags.append(tag)
    db.session.commit()
    return jsonify({"message": "Tag assigned", "book_id": book_id, "tag": tag.to_dict()}), 201


@app.route("/books/<int:book_id>/tags/<int:tag_id>", methods=["DELETE"])
def remove_tag_from_book(book_id, tag_id):
    """Remove a tag from a book."""
    book = get_book_or_404(book_id)
    tag  = get_tag_or_404(tag_id)
    if tag not in book.tags:
        abort(404, description=f"Tag {tag_id} is not assigned to book {book_id}")
    book.tags.remove(tag)
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
    app.run(debug=True, port=5002)
