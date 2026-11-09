from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.api import admin, applications, auth, documents
from app.core.config import settings
from app.core.security import hash_password
from app.db.session import Base, SessionLocal, engine
from app.models import User


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)
    if settings.admin_email and settings.admin_password:
        with SessionLocal() as db:
            email = settings.admin_email.lower()
            if not db.scalar(select(User).where(User.email == email)):
                db.add(User(email=email, full_name="Administrator", role="admin",
                            hashed_password=hash_password(settings.admin_password)))
                db.commit()
    yield


app = FastAPI(title="Edu Sahaya API", version="0.3.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(documents.router)
app.include_router(applications.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "edu-sahaya"}
