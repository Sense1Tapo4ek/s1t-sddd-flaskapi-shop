from flask import request, render_template

HX_REQUEST_HEADER = "HX-Request"


def is_htmx() -> bool:
    return request.headers.get(HX_REQUEST_HEADER) == "true"


def render_partial_or_full(partial: str, full: str, **ctx):
    template = partial if is_htmx() else full
    return render_template(template, **ctx)
