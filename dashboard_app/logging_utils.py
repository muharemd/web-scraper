from datetime import datetime

from flask import request

from . import config


def get_client_ip():
    if request.headers.get("X-Forwarded-For"):
        ip = request.headers.get("X-Forwarded-For").split(",")[0].strip()
    else:
        ip = request.remote_addr
    return ip if ip and len(ip) < 50 else "0.0.0.0"


def log_access(ip, username, action, details="", status="SUCCESS"):
    timestamp = datetime.now().isoformat()
    entry = f"{timestamp} | {ip} | {username} | {action} | {details} | {status}\n"
    try:
        with open(config.ACCESS_LOG, "a") as f:
            f.write(entry)
    except Exception:
        pass


def log_activity(ip, username, action, details=""):
    timestamp = datetime.now().isoformat()
    entry = f"{timestamp} | {ip} | {username} | {action} | {details}\n"
    try:
        with open(config.ACTIVITY_LOG, "a") as f:
            f.write(entry)
    except Exception:
        pass


def log_failed_login(ip, username, reason):
    timestamp = datetime.now().isoformat()
    entry = f"{timestamp} | {ip} | {username} | {reason}\n"
    try:
        with open(config.FAILED_LOGIN_LOG, "a") as f:
            f.write(entry)
    except Exception:
        pass
