# Web Application Development — Lab Assignments

**Student:** Enes Emre Hasturk  
**Student ID:** 7949  
**Framework:** Flask (Python)

---

## Lab Overview

| Lab | Topic | File | Port |
|-----|-------|------|------|
| Lab 01 | Basic To-Do API (in-memory CRUD) | `lab01/app.py` | 5000 |
| Lab 02 | Books API (validation + SQLite) | `lab02/app.py` | 5001 |
| Lab 03 | Library System (relationships) | `lab03/app.py` | 5002 |
| Lab 04 | Notes API (JWT auth + testing) | `lab04/app.py` | 5003 |

---

## How to Run

### Setup (do once)
```bash
pip install Flask Flask-SQLAlchemy bcrypt PyJWT pytest
```

### Run each lab
```bash
# Lab 01
python lab01/app.py

# Lab 02
python lab02/app.py

# Lab 03
python lab03/app.py

# Lab 04
python lab04/app.py
```

### Run Lab 04 tests
```bash
cd lab04
pytest test_app.py -v
```

---

## Lab 01 — Basic To-Do API

**Concept:** First web server, routes, JSON responses (in-memory data)

**Graded Tasks:**
1. **Filter todos** — `GET /todos?completed=true` and `?priority=high`
2. **Priority field** — tasks have `low/medium/high` priority with validation
3. **Stats endpoint** — `GET /todos/stats` returns counts by completion and priority
4. **Mark done shortcut** — `POST /todos/<id>/done` marks a task complete
5. **Search** — `GET /todos/search?q=keyword` searches title and description

**Quick test:**
```bash
# Create a todo
curl -X POST http://localhost:5000/todos \
  -H "Content-Type: application/json" \
  -d '{"title": "Buy groceries", "priority": "high"}'

# Get stats
curl http://localhost:5000/todos/stats
```

---

## Lab 02 — Books API with Validation

**Concept:** Data validation, request bodies, full CRUD with SQLite

**Graded Tasks:**
1. **Full validation** — `POST /books` requires title, author, year, genre with type checks
2. **PATCH support** — `PATCH /books/<id>` for partial updates (only changed fields)
3. **Genres list** — `GET /books/genres` returns all distinct genres
4. **Statistics** — `GET /books/stats` returns totals, average rating, year range
5. **Search** — `GET /books/search?q=keyword` searches title, author, genre

**Quick test:**
```bash
# Create a book
curl -X POST http://localhost:5001/books \
  -H "Content-Type: application/json" \
  -d '{"title":"The Hobbit","author":"Tolkien","year":1937,"genre":"Fantasy","rating":9.5}'
```

---

## Lab 03 — Library Management (Relationships)

**Concept:** Persistent database, dependency injection, model relationships

**Models:**
- `Author` → has many `Book`s (cascade delete)
- `Tag` → many-to-many with `Book`s
- `Book` → belongs to `Author`, has many `Tag`s

**Graded Tasks:**
1. **Author CRUD** — create/read/update/delete authors, cascading to books
2. **Book CRUD** — books require a valid `author_id` (FK validated)
3. **Tag system** — create tags and assign them to books (M:N)
4. **Author's books** — `GET /authors/<id>/books` with nested data
5. **Book tag management** — `GET/POST /books/<id>/tags` and `DELETE /books/<id>/tags/<tag_id>`

**Quick test:**
```bash
# Create author
curl -X POST http://localhost:5002/authors \
  -H "Content-Type: application/json" \
  -d '{"name":"J.R.R. Tolkien","birth_year":1892}'

# Create book for that author
curl -X POST http://localhost:5002/books \
  -H "Content-Type: application/json" \
  -d '{"title":"The Hobbit","year":1937,"author_id":1}'
```

---

## Lab 04 — JWT Authentication + Testing

**Concept:** Authentication, middleware, automated testing

**Security features:**
- Passwords hashed with **bcrypt** (never stored in plaintext)
- **JWT tokens** (PyJWT) with expiry
- `@require_auth` decorator protects routes
- `@require_admin` decorator restricts to admin role
- First registered user automatically gets `admin` role

**Middleware:**
- Every request is logged: `[timestamp] METHOD /path → STATUS (XXms)`

**Graded Tasks:**
1. **Registration** — `POST /auth/register` with password hashing
2. **Login + JWT** — `POST /auth/login` returns token; protected routes need `Authorization: Bearer <token>`
3. **Request logging** — `before_request` / `after_request` middleware logs all requests
4. **Admin route** — `GET /admin/users` (403 for regular users)
5. **Automated tests** — 15 tests covering registration, login, auth, notes, and admin

**Quick test:**
```bash
# Register
curl -X POST http://localhost:5003/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"enes","email":"enes@example.com","password":"mypassword"}'

# Login and save token
TOKEN=$(curl -s -X POST http://localhost:5003/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"enes","password":"mypassword"}' | python -c "import sys,json; print(json.load(sys.stdin)['token'])")

# Create a note
curl -X POST http://localhost:5003/notes \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"title":"My note","content":"Hello Flask!"}'
```

**Run tests:**
```bash
cd lab04
pytest test_app.py -v
```
