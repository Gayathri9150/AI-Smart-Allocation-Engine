"""Authentication helpers: password hashing wrappers and login-required
decorators for the three portals (student, company, admin)."""

from functools import wraps

from flask import flash, redirect, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

hash_password = generate_password_hash
verify_password = check_password_hash


def login_required(portal):
    """Build a decorator that guards a route behind a session flag.

    `portal` is one of "student", "company", "admin" and matches the
    session key set at login time (student_id / company_id / is_admin).
    """
    session_key = {
        "student": "student_id",
        "company": "company_id",
        "admin": "is_admin",
    }[portal]

    login_endpoint = {
        "student": "student_login",
        "company": "company_login",
        "admin": "admin_login",
    }[portal]

    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            if not session.get(session_key):
                flash("Please log in to continue.", "error")
                return redirect(url_for(login_endpoint))
            return view_func(*args, **kwargs)
        return wrapped
    return decorator
