from __future__ import annotations

import json
import logging
from flask import Flask, jsonify, make_response, redirect, request
from werkzeug.exceptions import HTTPException

from shared.generics.errors import (
    LayerError, DomainError, ApplicationError,
    DrivingPortError, DrivenPortError,
    DrivingAdapterError, DrivenAdapterError,
)
from shared.adapters.driving.htmx import is_htmx

logger = logging.getLogger("api.errors")


def _json_response(error: LayerError, status: int):
    return jsonify(
        {"error": error.code, "message": error.message, "success": False}
    ), status


def _htmx_toast(message: str, status_code: int):
    response = make_response("", status_code)
    response.headers["HX-Trigger"] = json.dumps({
        "showToast": {"message": message, "type": "error"}
    })
    return response


def init_error_handlers(app: Flask) -> None:

    @app.errorhandler(DomainError)
    def handle_domain_error(e: DomainError):
        logger.warning("Domain Rule Violation: %s - %s", e.code, e.message)
        if is_htmx():
            return _htmx_toast(e.message, 422)
        return _json_response(e, 422)

    @app.errorhandler(ApplicationError)
    def handle_app_error(e: ApplicationError):
        status = 404 if "NOT_FOUND" in e.code else 400
        logger.info("App Error: %s - %s", e.code, e.message)
        if is_htmx():
            return _htmx_toast(e.message, status)
        return _json_response(e, status)

    @app.errorhandler(DrivingPortError)
    def handle_driving_port_error(e: DrivingPortError):
        logger.info("Validation Error: %s", e.message)
        if is_htmx():
            return _htmx_toast(e.message, 400)
        return _json_response(e, 400)

    @app.errorhandler(DrivenPortError)
    def handle_driven_port_error(e: DrivenPortError):
        logger.error("Port Failure: %s", e.message, exc_info=True)
        if is_htmx():
            return _htmx_toast(e.message, 500)
        return _json_response(e, 500)

    @app.errorhandler(DrivingAdapterError)
    def handle_driving_adapter_error(e: DrivingAdapterError):
        logger.info("Auth Failure: %s", e.message)
        if is_htmx():
            response = make_response("")
            response.headers["HX-Redirect"] = "/admin/login"
            return response
        if request.path.startswith("/admin"):
            return redirect("/admin/login")
        return _json_response(e, 401)

    @app.errorhandler(DrivenAdapterError)
    def handle_driven_adapter_error(e: DrivenAdapterError):
        logger.critical("Infra Failure: %s", e.message, exc_info=True)
        if is_htmx():
            return _htmx_toast(e.message, 503)
        return _json_response(e, 503)

    @app.errorhandler(Exception)
    def handle_generic_error(e: Exception):
        if isinstance(e, HTTPException):
            if is_htmx():
                return _htmx_toast(e.description, e.code)
            return jsonify({"error": "HTTP_ERROR", "message": e.description}), e.code
        logger.exception("Unhandled Exception")
        if is_htmx():
            return _htmx_toast("Unexpected server error", 500)
        return jsonify(
            {"error": "INTERNAL_ERROR", "message": "Unexpected server error"}
        ), 500
