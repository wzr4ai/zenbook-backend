"""FastAPI application entrypoint."""

from fastapi import FastAPI

from src.core.config import settings
from src.core.exceptions import register_exception_handlers
from src.modules.appointments.router import admin_router as admin_appointments_router
from src.modules.appointments.router import router as appointments_router
from src.modules.auth.router import router as auth_router
from src.modules.catalog.router import router as catalog_router
from src.modules.catalog.admin_router import router as admin_catalog_router
from src.modules.schedule.router import router as schedule_router
from src.modules.schedule.admin_router import router as admin_schedule_router
from src.modules.users.router import router as users_router
from src.modules.users.admin_router import router as admin_users_router


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        version="0.1.0",
    )
    register_exception_handlers(app)

    @app.get("/health", tags=["system"])
    async def health_check() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(auth_router)
    app.include_router(users_router)
    app.include_router(catalog_router)
    app.include_router(schedule_router)
    app.include_router(appointments_router)
    app.include_router(admin_appointments_router)
    app.include_router(admin_catalog_router)
    app.include_router(admin_schedule_router)
    app.include_router(admin_users_router)

    return app


app = create_app()
