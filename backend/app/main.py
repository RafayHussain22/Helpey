import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

logging.basicConfig(level=logging.DEBUG)

from app.config import settings
from app.api.auth import router as auth_router
from app.api.chats import router as chats_router
from app.api.documents import router as documents_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="Helpey", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(chats_router)
app.include_router(documents_router)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logging.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": str(exc)})


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "helpey"}
