import json
import os
from datetime import datetime
from functools import wraps

import bcrypt
from flask import Blueprint, redirect, render_template, request, session, url_for

from . import config
from .logging_utils import get_client_ip, log_access, log_activity, log_failed_login

auth_bp = Blueprint("auth", __name__)


def load_users():
    if not os.path.exists(config.USERS_FILE):
        default_users = {
            "admin": {
                "password_hash": bcrypt.hashpw(b"admin123", bcrypt.gensalt()).decode(),
                "role": "admin",
                "created_at": datetime.now().isoformat(),
            }
        }
        save_users(default_users)
        return default_users
    try:
        with open(config.USERS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def save_users(users):
    with open(config.USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)


def verify_password(username, password):
    users = load_users()
    if username not in users:
        # Run a dummy hash to prevent timing attacks
        bcrypt.hashpw(b"dummy", bcrypt.gensalt())
        return False, None
    stored_hash = users[username]["password_hash"]
    if bcrypt.checkpw(password.encode(), stored_hash.encode()):
        return True, users[username]["role"]
    return False, None


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        client_ip = get_client_ip()
        if not session.get("logged_in"):
            log_access(client_ip, "ANONYMOUS", "ACCESS_DENIED",
                       f"Tried to access {request.path}", "DENIED")
            return redirect(url_for("auth.login", next=request.url))
        log_access(client_ip, session.get("username", "UNKNOWN"), "ACCESS_GRANTED",
                   f"Accessed {request.path}", "SUCCESS")
        return f(*args, **kwargs)
    return decorated


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    client_ip = get_client_ip()
    if session.get("logged_in"):
        return redirect(url_for("main.index"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        log_access(client_ip, username, "LOGIN_ATTEMPT")
        if not username or not password:
            log_failed_login(client_ip, username, "MISSING_CREDENTIALS")
            return render_template("login.html",
                                   error="Please enter both username and password",
                                   now=datetime.now())
        is_valid, role = verify_password(username, password)
        if is_valid:
            session["logged_in"] = True
            session["username"] = username
            session["role"] = role
            log_access(client_ip, username, "LOGIN_SUCCESS", f"Role: {role}", "SUCCESS")
            log_activity(client_ip, username, "USER_LOGIN")
            return redirect(request.args.get("next") or url_for("main.index"))
        log_failed_login(client_ip, username, "INVALID_CREDENTIALS")
        log_access(client_ip, username, "LOGIN_FAILED", "", "FAILED")
        return render_template("login.html",
                               error="Invalid username or password",
                               now=datetime.now())
    log_access(client_ip, "ANONYMOUS", "LOGIN_PAGE_VIEW")
    return render_template("login.html", error=None, now=datetime.now())


@auth_bp.route("/logout")
def logout():
    client_ip = get_client_ip()
    username = session.get("username", "UNKNOWN")
    log_access(client_ip, username, "LOGOUT", "", "SUCCESS")
    log_activity(client_ip, username, "USER_LOGOUT")
    session.clear()
    return redirect(url_for("auth.login"))
