from functools import wraps
from flask import redirect, session

def login_required(f):
    """
    Decorate routes to require login.
    If a user doesn't have a session badge, send them to /login.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function