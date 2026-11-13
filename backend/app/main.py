"""Construct the FastAPI service and own MongoDB for its lifespan."""

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pymongo import AsyncMongoClient

from app.core.config import settings
from app.core.database import MongoRepositories, create_indexes, get_database, verify_database
from app.core.seed import seed_database
from app.routers.auth import router as auth_router
from app.routers.health import router as health_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize one asynchronous Mongo client and close it on shutdown."""
    settings.require_jwt_secret()
    client: AsyncMongoClient[dict[str, Any]] = AsyncMongoClient(settings.MONGODB_URI)
    app.state.mongo_client = client
    try:
        database = get_database(client)
        app.state.mongo_database = database
        await verify_database(client)
        await create_indexes(database)
        app.state.repositories = MongoRepositories(database)
        if settings.SEED_ON_STARTUP:
            try:
                await seed_database(database)
            except Exception:
                logger.exception("MongoDB seed failed; continuing startup")
        yield
    finally:
        await client.close()


app = FastAPI(title="KP ETSIP API", version="1.0.0", description="Platform foundation REST API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)
app.include_router(health_router)
app.include_router(auth_router)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Map request validation issues to the shared public error envelope."""
    errors = [
        {"field": ".".join(str(part) for part in error["loc"] if part != "body"), "message": error["msg"]}
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "validation_error", "message": "Request validation failed", "field_errors": errors}, "request_id": request.headers.get("X-Request-ID", "unassigned")},
    )
