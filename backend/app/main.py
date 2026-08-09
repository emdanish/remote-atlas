from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import api_router
from app.config import get_settings


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield


settings = get_settings()

app = FastAPI(
    title="Remote Atlas",
    description="Intelligent job discovery engine for developers",
    version="0.2.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router)


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    """Reject cross-origin cookie mutations and attach baseline browser headers."""
    unsafe = request.method in {"POST", "PUT", "PATCH", "DELETE"}
    cookie_auth = settings.auth_cookie_name in request.cookies and not request.headers.get(
        "authorization"
    )
    origin = (request.headers.get("origin") or "").rstrip("/")
    allowed = {value.rstrip("/") for value in settings.cors_origin_list}
    if unsafe and cookie_auth and origin and origin not in allowed:
        return JSONResponse(status_code=403, content={"detail": "Cross-origin request rejected"})

    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if "application/json" in response.headers.get("content-type", ""):
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    return response


@app.get("/")
async def root():
    return {
        "name": "Remote Atlas",
        "docs": "/docs",
        "health": "/health",
        "search": "/jobs/search",
        "auth": "/auth/register",
    }
