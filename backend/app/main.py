from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import auth, contacts, leads, outreach, reviews, tasks, users
from app.config import get_settings
from app.services.user_bootstrap import ensure_initial_admin

settings = get_settings()
app = FastAPI(title=settings.app_name, version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.backend_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(leads.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(tasks.router, prefix="/api/v1")
app.include_router(contacts.router, prefix="/api/v1")
app.include_router(outreach.router, prefix="/api/v1")
app.include_router(reviews.router, prefix="/api/v1")


@app.on_event("startup")
async def bootstrap_users() -> None:
    await ensure_initial_admin()


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": settings.app_name}
