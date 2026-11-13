"""LEXSECURE - Secure Digital Document Management System"""

from contextlib import asynccontextmanager, suppress
import asyncio

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database.session import SessionLocal
from app.database.migrations import ensure_schema
from app.blockchain.ledger_service import ensure_genesis_block
from app.services.integrity_monitor import integrity_monitor_loop, monitor_status
from app.services.malware import scanner_available

from app.api.auth import router as auth_router
from app.api.cases import router as cases_router
from app.api.documents import router as documents_router
from app.api.approvals import router as approvals_router
from app.api.integrity import router as integrity_router
from app.api.ai import router as ai_router
from app.api.audit import router as audit_router
from app.api.workflow import router as workflow_router
from app.api.admin import router as admin_router
from app.api.reports import router as reports_router
from app.api.ws import router as ws_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_schema()
    with SessionLocal() as db:
        ensure_genesis_block(db)
    from app.api.ws import ws_manager
    ws_manager.bind_loop(asyncio.get_running_loop())

    stop_event = asyncio.Event()
    monitor_task = asyncio.create_task(integrity_monitor_loop(stop_event))

    yield

    stop_event.set()
    monitor_task.cancel()
    with suppress(asyncio.CancelledError, Exception):
        await monitor_task
    ws_manager.unbind_loop()

app = FastAPI(
    title="LEXSECURE API",
    description="Secure Digital Document Management System for Legal & Investigation Documents (NCRB/MHA)",
    version=settings.VERSION,
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "X-Export-SHA256", "X-Export-Count"],
)

@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    """Adds browser security headers to every response so rendered content can't be clickjacked, MIME-sniffed, or leaked via Referer."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response

app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(cases_router, prefix=settings.API_V1_STR)
app.include_router(documents_router, prefix=settings.API_V1_STR)
app.include_router(approvals_router, prefix=settings.API_V1_STR)
app.include_router(integrity_router, prefix=settings.API_V1_STR)
app.include_router(ai_router, prefix=settings.API_V1_STR)
app.include_router(audit_router, prefix=settings.API_V1_STR)
app.include_router(workflow_router, prefix=settings.API_V1_STR)
app.include_router(admin_router, prefix=settings.API_V1_STR)
app.include_router(reports_router, prefix=settings.API_V1_STR)
app.include_router(ws_router, prefix=settings.API_V1_STR)

@app.get("/health", tags=["Health"])
def health_check():
    db_backend = "postgresql" if settings.DATABASE_URL.startswith("postgres") else "sqlite"
    return {
        "status": "ONLINE",
        "system": "LEXSECURE",
        "version": settings.VERSION,
        "database": db_backend,
        "security_controls": "ACTIVE",
        "mfa": "TOTP (RFC 6238)",
        "document_integrity": "AES-256-GCM + SHA-256 + RSA-PSS + hash-chain ledger",
        "malware_scanner": scanner_available()["engine"],
        "integrity_monitor": monitor_status(),
    }

@app.get("/", tags=["Root"])
def root():
    return {
        "message": "LEXSECURE API Server Active",
        "documentation": "/docs",
        "health": "/health"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
