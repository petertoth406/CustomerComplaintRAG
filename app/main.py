"""Entry point."""

from fastapi import FastAPI

from app.api.routers import preprocessing, statistics


app = FastAPI(title="Customer Complaint RAG API")

app.include_router(preprocessing.router, prefix="/api/v1")
app.include_router(statistics.router, prefix="/api/v1")
