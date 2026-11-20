import os

from flask import Flask

from . import config


def create_app():
    """Application factory — creates and wires up the Flask app."""
    app = Flask(
        __name__,
        template_folder=os.path.join(config.BASE_DIR, "templates"),
    )

    # Load secret key: env var → file → hardcoded fallback
    secret_key = os.environ.get("DASHBOARD_SECRET_KEY")
    if not secret_key:
        key_file = os.path.join(config.BASE_DIR, ".dashboard_secret_key")
        if os.path.exists(key_file):
            try:
                with open(key_file, "r") as f:
                    secret_key = f.read().strip()
            except Exception:
                pass
    if not secret_key:
        raise RuntimeError(
            "DASHBOARD_SECRET_KEY or .dashboard_secret_key must be configured"
        )

    app.secret_key = secret_key
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = False
    app.config["SESSION_COOKIE_DOMAIN"] = None

    # Register blueprints
    from .auth import auth_bp
    from .routes.main import main_bp
    from .routes.articles import articles_bp
    from .routes.wordpress import wp_bp
    from .routes.scrapers import scrapers_bp
    from .routes.facebook_api import fb_api_bp
    from .routes.ai_routes import ai_bp
    from .routes.inoreader_webhook import webhook_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(articles_bp)
    app.register_blueprint(wp_bp)
    app.register_blueprint(scrapers_bp)
    app.register_blueprint(fb_api_bp)
    app.register_blueprint(ai_bp)
    app.register_blueprint(webhook_bp)

    # Ensure article output directory exists
    os.makedirs(config.JSON_DIR, exist_ok=True)

    from .auth import load_users
    users = load_users()
    print(f"Loaded {len(users)} users")

    return app
