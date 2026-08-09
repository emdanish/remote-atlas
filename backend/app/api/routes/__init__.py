from fastapi import APIRouter

from app.api.routes import (
    auth,
    companies,
    health,
    jobs,
    phase3,
    resume_tailor,
    saved_jobs,
    saved_searches,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(jobs.router)
api_router.include_router(auth.router)
api_router.include_router(saved_jobs.router)
api_router.include_router(saved_searches.router)
api_router.include_router(phase3.router)
api_router.include_router(resume_tailor.router)
api_router.include_router(companies.router)
