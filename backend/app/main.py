from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import agencies, auth, billing, bookings, search

app = FastAPI(
    title="WanderLink Travel API",
    version="1.0.0",
    description="Search travel options, authenticate users, and reserve available inventory.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth.router)
app.include_router(search.router)
app.include_router(bookings.router)
app.include_router(agencies.router)
app.include_router(billing.router)


@app.get("/health/", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}
