"""Kodli xatolar: `{"detail": <lokalizatsiya qilingan matn>, "code": <barqaror kod>}`.

`detail` doim STRING (frontend shuni o'qiydi); 422 validatsiyada FastAPI'ning `detail` ro'yxati saqlanadi.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.i18n import current_lang, lang_from_header, t


class ApiError(HTTPException):
    """HTTPException + barqaror `code` va katalog parametrlari."""

    def __init__(
        self, status_code: int, code: str, headers: dict[str, str] | None = None, **params: Any
    ) -> None:
        super().__init__(status_code=status_code, detail=t(code, "uz", **params), headers=headers)
        self.code = code
        self.params = params


def api_error(status_code: int, code: str, **params: Any) -> ApiError:
    """`raise api_error(404, "source_not_found")`."""
    return ApiError(status_code, code, **params)


def _lang(request: Request) -> str:
    return lang_from_header(request.headers.get("accept-language")) if request else current_lang()


async def _api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(
        {"detail": t(exc.code, _lang(request), **exc.params), "code": exc.code},
        status_code=exc.status_code,
        headers=exc.headers,
    )


async def _http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    # Kodsiz HTTP xatolar (404 yo'l topilmadi, 405 va h.k.): matn o'zgarmaydi, kod — http_<status>
    return JSONResponse(
        {"detail": exc.detail, "code": f"http_{exc.status_code}"},
        status_code=exc.status_code,
        headers=getattr(exc, "headers", None),
    )


async def _validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        {
            "detail": jsonable_encoder(exc.errors()),
            "code": "validation_error",
            "message": t("validation_error", _lang(request)),
        },
        status_code=422,
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, _api_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, _http_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, _validation_handler)  # type: ignore[arg-type]
