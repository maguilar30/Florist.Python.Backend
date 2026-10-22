from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def problem(status: int, title: str, detail: str | None = None, errors: dict | None = None) -> HTTPException:
    return HTTPException(
        status_code=status,
        detail={"title": title, "detail": detail or title, "status": status, "errors": errors or {}},
    )


def problem_response(status: int, title: str, detail: str | None = None, errors: dict | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"title": title, "detail": detail or title, "status": status, "errors": errors or {}},
    )


async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict) and "title" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return problem_response(exc.status_code, "Error", str(exc.detail))


async def validation_exception_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    field_errors: dict[str, list[str]] = {}
    for err in exc.errors():
        loc = ".".join(str(part) for part in err.get("loc", []) if part != "body")
        field_errors.setdefault(loc or "body", []).append(err.get("msg", "Invalid value"))
    return problem_response(422, "Validation error", "One or more fields are invalid.", field_errors)
