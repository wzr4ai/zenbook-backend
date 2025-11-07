"""Custom exception classes and handlers."""

from fastapi import FastAPI, status
from fastapi.responses import JSONResponse


class BusinessLogicError(Exception):
    """Raised for domain-specific validation errors."""

    def __init__(self, detail: str, status_code: int = status.HTTP_422_UNPROCESSABLE_ENTITY):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def register_exception_handlers(app: FastAPI) -> None:
    """Attach shared exception handlers to the FastAPI app."""

    @app.exception_handler(BusinessLogicError)
    async def _business_error_handler(_: FastAPI, exc: BusinessLogicError):
        return JSONResponse(
            {"success": False, "message": exc.detail},
            status_code=exc.status_code,
        )
