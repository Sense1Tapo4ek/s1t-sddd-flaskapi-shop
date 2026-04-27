import os
from pathlib import Path
from typing import Callable

from apiflask import APIFlask
from flask import send_from_directory, redirect, render_template
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from jinja2 import ChoiceLoader, FileSystemLoader
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from dotenv import load_dotenv
from dishka.integrations.flask import setup_dishka

# Composition Root
from root.container import build_container

# Configs
from root.config import RootConfig
from catalog.config import CatalogConfig
from access.config import AccessConfig
from access.app.runtime_permissions import RuntimePermissionProvider
from access.permissions import RUNTIME_CATALOG_PERMISSIONS
from access.ports.driven.bootstrap import bootstrap_access_defaults
from system.ports.driven.bootstrap import bootstrap_system_defaults
from system.ports.driving.facade import SystemFacade
from system.ports.driving.runtime_template import runtime_template_settings

from shared.adapters.driving.middleware import (
    current_admin_payload,
    has_permission,
    init_middleware,
    jwt_required,
)
from shared.adapters.driving.error_handlers import init_error_handlers

# Import all ORM model modules to register them with the shared Base
import access.adapters.driven.db.models  # noqa: F401
import catalog.adapters.driven.db.models  # noqa: F401
import ordering.adapters.driven.db.models  # noqa: F401
import system.adapters.driven.db.models  # noqa: F401

from shared.adapters.driven.db.base import Base
from shared.adapters.driven.db.compat import ensure_sqlite_compatibility


def _first_admin_path() -> str:
    payload = current_admin_payload()
    if (
        payload.get("role") == "superadmin"
        or has_permission("view_products")
        or has_permission("view_category_tree")
        or has_permission("edit_taxonomy")
    ):
        return "/admin/catalog/"
    if has_permission("view_orders"):
        return "/admin/orders/"
    if has_permission("manage_settings"):
        return "/admin/settings/store"
    return "/admin/account"

# Blueprints (imported directly — no init functions needed, Dishka injects facades)
from catalog.adapters.driving.api import catalog_bp
from ordering.adapters.driving.api import ordering_bp
from access.adapters.driving.api import access_bp
from system.adapters.driving.api import system_bp

# Admin blueprints
from catalog.adapters.driving.admin import catalog_admin_bp, taxonomy_admin_bp
from ordering.adapters.driving.admin import ordering_admin_bp
from access.adapters.driving.admin import access_admin_bp
from system.adapters.driving.admin import account_admin_bp, system_admin_bp


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

    access_config = container.get(AccessConfig)
    catalog_config = container.get(CatalogConfig)
    engine = container.get(Engine)
    session_factory = container.get(Callable[[], Session])
    permission_provider = container.get(RuntimePermissionProvider)
    system_facade = container.get(SystemFacade)

    os.makedirs("media", exist_ok=True)

    # All models share one Base — a single create_all covers everything
    Base.metadata.create_all(engine)
    ensure_sqlite_compatibility(engine)
    bootstrap_access_defaults(
        session_factory,
        access_config=access_config,
        root_config=root_config,
    )
    bootstrap_system_defaults(
        session_factory,
        access_config=access_config,
        root_config=root_config,
    )

    app.jinja_env.globals["app_name"] = root_config.app_name
    app.jinja_env.globals["admin_panel_title"] = "Админ панель"
    app.jinja_env.globals["has_perm"] = has_permission
    app.config["PERMISSION_PROVIDER"] = permission_provider
    app.config["RUNTIME_PERMISSION_KEYS"] = RUNTIME_CATALOG_PERMISSIONS

    @app.context_processor
    def inject_runtime_template_settings():
        return runtime_template_settings(system_facade, root_config)

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
    app.register_blueprint(taxonomy_admin_bp)
    app.register_blueprint(ordering_admin_bp)
    app.register_blueprint(access_admin_bp)
    app.register_blueprint(system_admin_bp)
    app.register_blueprint(account_admin_bp)

    # Dishka wiring — AFTER all blueprints
    setup_dishka(container, app)

    if root_config.app_env == "prod":
        for endpoint in (
            "access.login",
            "access_admin.login",
            "access_admin.request_telegram_code",
            "access_admin.verify_recovery_code",
            "system_admin.request_password_confirmation_code",
        ):
            if endpoint in app.view_functions:
                limiter.limit(root_config.rate_limit_login)(app.view_functions[endpoint])
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
        return redirect("/admin/")

    @app.route("/admin/")
    @jwt_required
    @app.doc(hide=True)
    def admin_index():
        return redirect(_first_admin_path())

    @app.route("/admin/help")
    @jwt_required
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
