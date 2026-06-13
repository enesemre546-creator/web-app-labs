"""
Lab 01 — Basic To-Do API (Flask)
Student: Enes Emre Hasturk
Student ID: 7949

Description:
    An in-memory CRUD REST API for managing To-Do items built with Flask.
    Data is stored in a Python list (resets on server restart).

Endpoints:
    GET    /todos               — list all to-dos (Task 1: with optional filtering)
    GET    /todos/<id>          — get a single to-do
    POST   /todos               — create a new to-do
    PUT    /todos/<id>          — update a to-do
    DELETE /todos/<id>          — delete a to-do
    GET    /todos/stats         — summary statistics (Task 3)
    POST   /todos/<id>/done     — mark a to-do as completed (Task 4)
    GET    /todos/search        — search by keyword in title (Task 5)

Graded Tasks implemented:
    Task 1 — Filter GET /todos by ?completed=true/false query param
    Task 2 — Add a 'priority' field (low / medium / high) with validation
    Task 3 — GET /todos/stats endpoint returning summary counts
    Task 4 — POST /todos/<id>/done convenience endpoint to mark done
    Task 5 — GET /todos/search?q=<keyword> full-text search in title+description
"""

from flask import Flask, request, jsonify, abort

app = Flask(__name__)

# ─────────────────────────────────────────────────────────────
# In-memory data store
# ─────────────────────────────────────────────────────────────
todos = []
next_id = 1

VALID_PRIORITIES = {"low", "medium", "high"}


# ─────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────
def find_todo(todo_id: int):
    """Return the todo dict for the given id or abort 404."""
    todo = next((t for t in todos if t["id"] == todo_id), None)
    if todo is None:
        abort(404, description=f"Todo with id {todo_id} not found")
    return todo


# ─────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────

@app.route("/todos", methods=["GET"])
def list_todos():
    """
    List all to-do items.

    Task 1 — Optional query-parameter filtering:
        ?completed=true   → only completed items
        ?completed=false  → only pending items
        (no param)        → all items

    Task 2 — Optional filter by priority:
        ?priority=high / medium / low
    """
    result = list(todos)

    # Task 1: filter by completion status
    completed_param = request.args.get("completed")
    if completed_param is not None:
        if completed_param.lower() == "true":
            result = [t for t in result if t["completed"]]
        elif completed_param.lower() == "false":
            result = [t for t in result if not t["completed"]]
        else:
            abort(400, description="'completed' must be 'true' or 'false'")

    # Task 2: filter by priority
    priority_param = request.args.get("priority")
    if priority_param is not None:
        if priority_param.lower() not in VALID_PRIORITIES:
            abort(400, description=f"'priority' must be one of: {', '.join(VALID_PRIORITIES)}")
        result = [t for t in result if t["priority"] == priority_param.lower()]

    return jsonify(result)


@app.route("/todos/stats", methods=["GET"])
def get_stats():
    """
    Task 3 — Return summary statistics about all to-dos.
    Response includes total count, completed count, pending count,
    and a breakdown by priority.
    """
    total = len(todos)
    completed = sum(1 for t in todos if t["completed"])
    pending = total - completed

    priority_counts = {"low": 0, "medium": 0, "high": 0}
    for t in todos:
        priority_counts[t["priority"]] += 1

    return jsonify({
        "total": total,
        "completed": completed,
        "pending": pending,
        "by_priority": priority_counts
    })


@app.route("/todos/search", methods=["GET"])
def search_todos():
    """
    Task 5 — Search for to-dos by keyword in title or description.
    Usage: GET /todos/search?q=<keyword>
    The search is case-insensitive.
    """
    keyword = request.args.get("q", "").strip()
    if not keyword:
        abort(400, description="Query parameter 'q' is required")

    keyword_lower = keyword.lower()
    matches = [
        t for t in todos
        if keyword_lower in t["title"].lower()
        or keyword_lower in t["description"].lower()
    ]
    return jsonify(matches)


@app.route("/todos/<int:todo_id>", methods=["GET"])
def get_todo(todo_id):
    """Retrieve a single to-do item by ID."""
    return jsonify(find_todo(todo_id))


@app.route("/todos", methods=["POST"])
def create_todo():
    """
    Create a new to-do item.

    Required fields: title
    Optional fields: description (str), completed (bool), priority (low/medium/high)
    Task 2 — priority field added with validation.
    """
    global next_id
    data = request.get_json()
    if not data or "title" not in data:
        abort(400, description="'title' is required")

    # Task 2: validate priority
    priority = data.get("priority", "medium")
    if priority not in VALID_PRIORITIES:
        abort(400, description=f"'priority' must be one of: {', '.join(VALID_PRIORITIES)}")

    new_todo = {
        "id": next_id,
        "title": str(data["title"]).strip(),
        "description": str(data.get("description", "")).strip(),
        "completed": bool(data.get("completed", False)),
        "priority": priority,
    }
    todos.append(new_todo)
    next_id += 1
    return jsonify(new_todo), 201


@app.route("/todos/<int:todo_id>", methods=["PUT"])
def update_todo(todo_id):
    """Update an existing to-do item (full or partial update)."""
    todo = find_todo(todo_id)
    data = request.get_json()
    if not data:
        abort(400, description="Request body must be JSON")

    # Task 2: validate priority if provided
    if "priority" in data and data["priority"] not in VALID_PRIORITIES:
        abort(400, description=f"'priority' must be one of: {', '.join(VALID_PRIORITIES)}")

    todo["title"]       = str(data.get("title", todo["title"])).strip()
    todo["description"] = str(data.get("description", todo["description"])).strip()
    todo["completed"]   = bool(data.get("completed", todo["completed"]))
    todo["priority"]    = data.get("priority", todo["priority"])

    return jsonify(todo)


@app.route("/todos/<int:todo_id>", methods=["DELETE"])
def delete_todo(todo_id):
    """Delete a to-do item."""
    global todos
    find_todo(todo_id)   # will 404 if not found
    todos = [t for t in todos if t["id"] != todo_id]
    return "", 204


@app.route("/todos/<int:todo_id>/done", methods=["POST"])
def mark_done(todo_id):
    """
    Task 4 — Convenience endpoint: mark a to-do as completed.
    POST /todos/<id>/done
    Returns the updated to-do.
    """
    todo = find_todo(todo_id)
    todo["completed"] = True
    return jsonify(todo)


# ─────────────────────────────────────────────────────────────
# Error handlers
# ─────────────────────────────────────────────────────────────
@app.errorhandler(400)
def bad_request(e):
    return jsonify({"error": "Bad Request", "message": str(e.description)}), 400

@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Not Found", "message": str(e.description)}), 404

@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({"error": "Method Not Allowed"}), 405


# ─────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True, port=5000)
