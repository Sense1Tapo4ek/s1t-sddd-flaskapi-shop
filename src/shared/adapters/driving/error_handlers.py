from __future__ import annotations

import json
import logging
from flask import Flask, jsonify, make_response, redirect, request
from werkzeug.exceptions import HTTPException

from pydantic import ValidationError as PydanticValidationError

from shared.generics.errors import (
    LayerError, DomainError, ApplicationError,
    DrivenPortError,
    DrivingAdapterError, DrivenAdapterError,
)
from shared.adapters.driving.htmx import is_htmx


def _bulk_target_code(errors: list[dict]) -> str | None:
    """Map Pydantic ValidationError details for BulkTargetIds.ids to stable codes."""
    for err in errors:
        loc = err.get("loc") or ()
        if "ids" not in loc:
            continue
        err_type = err.get("type", "")
        if err_type in {"too_short", "list_too_short"}:
            return "bulk_target_empty"
        if err_type in {"too_long", "list_too_long"}:
            return "bulk_target_too_large"
    return None

logger = logging.getLogger("api.errors")
GENERIC_OPERATION_FAILED = "Не удалось выполнить операцию. Попробуйте позже."
GENERIC_SERVICE_FAILED = "Сервис временно недоступен. Попробуйте позже."
GENERIC_SERVER_ERROR = "Непредвиденная ошибка сервера"
VALIDATION_ERROR_MESSAGE = "Проверьте данные запроса"

_HTTP_DESCRIPTIONS = {
    400: "Некорректный запрос",
    401: "Требуется аутентификация",
    403: "Доступ запрещён",
    404: "Страница не найдена",
    405: "Метод не поддерживается",
    408: "Время ожидания запроса истекло",
    409: "Конфликт",
    410: "Ресурс удалён",
    413: "Слишком большой запрос",
    414: "Слишком длинный URI",
    415: "Неподдерживаемый тип данных",
    429: "Слишком много запросов",
    500: "Внутренняя ошибка сервера",
    502: "Ошибка шлюза",
    503: "Сервис временно недоступен",
    504: "Время ожидания шлюза истекло",
}


def _http_description(status_code: int | None) -> str:
    if status_code is None:
        return "Ошибка HTTP"
    return _HTTP_DESCRIPTIONS.get(status_code, "Ошибка HTTP")


def json_error_response(
    *,
    code: str,
    message: str,
    status: int,
    detail: dict | list | None = None,
):
    body = {"error": code, "message": message, "success": False}
    if detail is not None:
        body["detail"] = detail
    return jsonify(body), status


def _json_response(error: LayerError, status: int):
    return json_error_response(
        code=error.code,
        message=error.message,
        status=status,
    )


def _htmx_toast(message: str, status_code: int):
    response = make_response("", status_code)
    response.headers["HX-Trigger"] = json.dumps({
        "showToast": {"message": message, "type": "error"}
    })
    return response


def init_error_handlers(app: Flask) -> None:
    if hasattr(app, "error_processor"):
        @app.error_processor
        def handle_apiflask_error(error):
            detail = error.detail or None
            is_validation_error = bool(detail)
            message = (
                VALIDATION_ERROR_MESSAGE
                if is_validation_error
                else error.message or "Ошибка HTTP"
            )
            code = "VALIDATION_ERROR" if is_validation_error else "HTTP_ERROR"
            if is_htmx():
                return _htmx_toast(message, error.status_code)
            return json_error_response(
                code=code,
                message=message,
                status=error.status_code,
                detail=detail,
            )

    @app.errorhandler(PydanticValidationError)
    def handle_pydantic_validation_error(e: PydanticValidationError):
        errors = e.errors()
        # Surface stable codes for the well-known bulk-target limits.
        bulk_code = _bulk_target_code(errors)
        if bulk_code is not None:
            logger.info("Bulk target rejected: %s", bulk_code)
            if is_htmx():
                return _htmx_toast(VALIDATION_ERROR_MESSAGE, 422)
            return json_error_response(
                code=bulk_code,
                message=VALIDATION_ERROR_MESSAGE,
                status=422,
                detail=errors,
            )
        logger.info("Pydantic validation failed: %s errors", len(errors))
        if is_htmx():
            return _htmx_toast(VALIDATION_ERROR_MESSAGE, 422)
        return json_error_response(
            code="VALIDATION_ERROR",
            message=VALIDATION_ERROR_MESSAGE,
            status=422,
            detail=errors,
        )

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

    @app.errorhandler(DrivenPortError)
    def handle_driven_port_error(e: DrivenPortError):
        logger.error("Port Failure: %s", e.message)
        if is_htmx():
            return _htmx_toast(GENERIC_OPERATION_FAILED, 500)
        return json_error_response(
            code=e.code,
            message=GENERIC_OPERATION_FAILED,
            status=500,
        )

    @app.errorhandler(DrivingAdapterError)
    def handle_driving_adapter_error(e: DrivingAdapterError):
        logger.info("Auth Failure: %s", e.message)
        status = 403 if e.code in {"FORBIDDEN", "CSRF_INVALID"} else 401
        if is_htmx():
            if e.code == "CSRF_INVALID":
                return _htmx_toast("Сессия устарела. Обновите страницу.", 403)
            if status == 403:
                return _htmx_toast("Недостаточно прав", 403)
            response = make_response("")
            response.headers["HX-Redirect"] = "/admin/login"
            return response
        if request.path.startswith("/admin") and status == 401:
            return redirect("/admin/login")
        return _json_response(e, status)

    @app.errorhandler(DrivenAdapterError)
    def handle_driven_adapter_error(e: DrivenAdapterError):
        logger.critical("Infra Failure: %s", e.message, exc_info=True)
        if is_htmx():
            return _htmx_toast(GENERIC_SERVICE_FAILED, 503)
        return json_error_response(
            code=e.code,
            message=GENERIC_SERVICE_FAILED,
            status=503,
        )

    @app.errorhandler(Exception)
    def handle_generic_error(e: Exception):
        if isinstance(e, HTTPException):
            description = _http_description(e.code)
            if is_htmx():
                return _htmx_toast(description, e.code)
            return json_error_response(
                code="HTTP_ERROR",
                message=description,
                status=e.code,
            )
        logger.exception("Unhandled Exception")
        if is_htmx():
            return _htmx_toast(GENERIC_SERVER_ERROR, 500)
        return json_error_response(
            code="INTERNAL_ERROR",
            message=GENERIC_SERVER_ERROR,
            status=500,
        )
