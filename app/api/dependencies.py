"""Shared FastAPI dependencies."""

from app.services.semantic_search_service import SemanticSearchService


def get_semantic_service() -> SemanticSearchService:
    return SemanticSearchService()
