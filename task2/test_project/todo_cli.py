#!/usr/bin/env python3
"""
Simple TODO CLI App
Usage:
    python todo_cli.py add "Task description"
    python todo_cli.py list
    python todo_cli.py done <id>
    python todo_cli.py remove <id>
"""

import sys
import json
import os

TODO_FILE = "todos.json"


def load_todos():
    """Load todos from file"""
    if not os.path.exists(TODO_FILE):
        return []
    with open(TODO_FILE) as f:
        return json.load(f)


def save_todos(todos):
    """Save todos to file"""
    with open(TODO_FILE, "w") as f:
        json.dump(todos, f)


def add_todo(description):
    """Add a new todo"""
    todos = load_todos()
    new_id = max([t["id"] for t in todos]) + 1 if todos else 1
    todos.append({
        "id": new_id,
        "description": description,
        "done": False
    })
    save_todos(todos)
    print(f"Added todo #{new_id}: {description}")


def list_todos():
    """List all todos"""
    todos = load_todos()
    if not todos:
        print("No todos yet!")
        return

    print("\n TODO List:")
    print("-" * 40)
    for todo in todos:
        status = "x" if todo["done"] else " "
        print(f"  [{status}] #{todo['id']}: {todo['description']}")
    print()


def mark_done(todo_id):
    """Mark todo as done"""
    todos = load_todos()
    for todo in todos:
        if todo["id"] == todo_id:
            todo["done"] = True
            save_todos(todos)
            print(f"Marked #{todo_id} as done!")
            return
    print(f"Todo #{todo_id} not found")


def remove_todo(todo_id):
    """Remove a todo"""
    todos = load_todos()
    todos = [t for t in todos if t["id"] != todo_id]
    save_todos(todos)
    print(f"Removed todo #{todo_id}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]

    if command == "add":
        if len(sys.argv) < 3:
            print("Usage: todo_cli.py add <description>")
            sys.exit(1)
        add_todo(sys.argv[2])

    elif command == "list":
        list_todos()

    elif command == "done":
        if len(sys.argv) < 3:
            print("Usage: todo_cli.py done <id>")
            sys.exit(1)
        mark_done(sys.argv[2])  # BUG: should be int(sys.argv[2])

    elif command == "remove":
        if len(sys.argv) < 3:
            print("Usage: todo_cli.py remove <id>")
            sys.exit(1)
        remove_todo(sys.argv[2])  # BUG: should be int(sys.argv[2])

    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
