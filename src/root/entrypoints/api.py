import os
from pathlib import Path
from apiflask import APIFlask
from flask import send_from_directory, redirect, render_template
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from jinja2 import ChoiceLoader, FileSystemLoader
import logging
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session
from werkzeug.security import generate_password_hash
from dotenv import load_dotenv
from dishka.integrations.flask import setup_dishka

# Composition Root
from root.container import build_container

# Configs
from root.config import RootConfig
from shared.config import InfraConfig
from catalog.config import CatalogConfig
from access.config import AccessConfig

from shared.adapters.driving.middleware import init_middleware
from shared.adapters.driving.error_handlers import init_error_handlers

# Import all ORM model modules to register them with the shared Base
import catalog.adapters.driven.db.models  # noqa: F401
import ordering.adapters.driven.db.models  # noqa: F401

from shared.adapters.driven.db.base import Base
from access.adapters.driven.db.models import UserModel
from system.adapters.driven.db.models import SettingsModel

logger = logging.getLogger("app.bootstrap")


def _ensure_defaults(engine, access_config: AccessConfig) -> None:
    with Session(engine) as session:
        admin_count = session.execute(
            select(func.count(UserModel.id))
        ).scalar()
        if admin_count == 0:
            admin = UserModel(
                login=access_config.default_login,
                password_hash=generate_password_hash(access_config.default_password),
            )
            session.add(admin)
            session.commit()
            logger.info(
                "Created default admin: %s / %s",
                access_config.default_login,
                access_config.default_password,
            )

        settings = session.execute(
            select(SettingsModel).where(SettingsModel.id == 1)
        ).scalar()
        if not settings:
            session.add(SettingsModel(id=1))
            session.commit()
            logger.info("Created default system settings")

# Blueprints (imported directly — no init functions needed, Dishka injects facades)
from catalog.adapters.driving.api import catalog_bp
from ordering.adapters.driving.api import ordering_bp
from access.adapters.driving.api import access_bp
from system.adapters.driving.api import system_bp

# Admin blueprints
from catalog.adapters.driving.admin import catalog_admin_bp
from ordering.adapters.driving.admin import ordering_admin_bp
from access.adapters.driving.admin import access_admin_bp
from system.adapters.driving.admin import system_admin_bp


def create_app() -> APIFlask:
    root_config = RootConfig()
    base_dir = Path(__file__).resolve().parent.parent.parent.parent

    load_dotenv()

    docs_path = "/api/docs" if root_config.app_env == "dev" else None

    app = APIFlask(
        __name__,
        title=root_config.app_name + " API",
        version="1.0.0",
        template_folder=str(base_dir / "static" / "templates"),
        static_folder=str(base_dir / "static"),
        docs_path=docs_path,
    )
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

    app.security_schemes = {
        "JWTAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
    }

    container = build_container()

    infra_config = container.get(InfraConfig)
    access_config = container.get(AccessConfig)
    catalog_config = container.get(CatalogConfig)

    os.makedirs("media", exist_ok=True)
    engine = create_engine(infra_config.database_url, echo=False)

    # All models share one Base — a single create_all covers everything
    Base.metadata.create_all(engine)
    _ensure_defaults(engine, access_config)

    app.jinja_env.globals["app_name"] = root_config.app_name

    init_middleware(app, access_config.jwt_secret)
    init_error_handlers(app)

    # ChoiceLoader for context templates
    app.jinja_loader = ChoiceLoader([
        FileSystemLoader(str(base_dir / "static" / "templates" / "admin")),
        FileSystemLoader(str(base_dir / "src" / "catalog" / "templates")),
        FileSystemLoader(str(base_dir / "src" / "ordering" / "templates")),
        FileSystemLoader(str(base_dir / "src" / "access" / "templates")),
        FileSystemLoader(str(base_dir / "src" / "system" / "templates")),
    ])

    if root_config.app_env == "dev":
        CORS(app)
        limiter = Limiter(
            get_remote_address,
            app=app,
            default_limits=["10000 per minute"],
            storage_uri="memory://",
        )
    else:
        admin_origins = root_config.admin_cors_origins
        public_origins = root_config.public_cors_origins + root_config.admin_cors_origins

        CORS(
            app,
            resources={
                r"/auth/*": {"origins": admin_origins},
                r"/system/settings*": {"origins": admin_origins},
                r"/catalog/admin/*": {"origins": admin_origins},

                r"/catalog*": {"origins": public_origins},
                r"/orders*": {"origins": public_origins},
                r"/system/info": {"origins": public_origins},
            },
        )
        limiter = Limiter(
            get_remote_address,
            app=app,
            default_limits=[root_config.rate_limit_default],
            storage_uri="memory://",
        )

    @app.after_request
    def add_developer_header(response):
        response.headers["X-Developer"] = "S1T"
        return response

    # Register blueprints directly
    app.register_blueprint(catalog_bp)
    app.register_blueprint(ordering_bp)
    app.register_blueprint(access_bp)
    app.register_blueprint(system_bp)

    # Admin blueprints
    app.register_blueprint(catalog_admin_bp)
    app.register_blueprint(ordering_admin_bp)
    app.register_blueprint(access_admin_bp)
    app.register_blueprint(system_admin_bp)

    # Dishka wiring — AFTER all blueprints
    setup_dishka(container, app)

    if root_config.app_env == "prod":
        limiter.limit(root_config.rate_limit_login)(app.view_functions["access.login"])
        limiter.limit(root_config.rate_limit_order)(
            app.view_functions["ordering.place_order"]
        )
        limiter.limit(root_config.rate_limit_recovery)(
            app.view_functions["system.recover_password"]
        )

    @app.route("/media/products/<path:filename>")
    @app.doc(hide=True)
    def serve_upload(filename: str):
        upload_dir = str(base_dir / catalog_config.upload_dir)
        return send_from_directory(upload_dir, filename)

    @app.route("/")
    @app.doc(hide=True)
    def index():
        return redirect("/admin/products")

    @app.route("/admin/")
    @app.doc(hide=True)
    def admin_index():
        return redirect("/admin/products")

    @app.route("/admin/help")
    @app.doc(hide=True)
    def admin_help():
        return render_template("help.html")

    return app


def run() -> None:
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app = create_app()
    app.run(host="0.0.0.0", port=port, debug=debug)


if __name__ == "__main__":
    run()
