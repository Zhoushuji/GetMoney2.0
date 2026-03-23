from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import contacts, leads, outreach, tasks
from app.config import get_settings

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
app.include_router(tasks.router, prefix="/api/v1")
app.include_router(contacts.router, prefix="/api/v1")
app.include_router(outreach.router, prefix="/api/v1")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": settings.app_name}
