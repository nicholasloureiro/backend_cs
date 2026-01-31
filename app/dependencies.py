"""Dependency injection setup."""

from functools import lru_cache

from app.services.pdf_parser import PDFParserService
from app.services.transformation import TransformationService
from app.services.comparison import ComparisonService


@lru_cache
def get_pdf_parser_service() -> PDFParserService:
    """Get PDF parser service instance."""
    return PDFParserService()


def get_transformation_service() -> TransformationService:
    """Get transformation service instance."""
    pdf_parser = get_pdf_parser_service()
    return TransformationService(pdf_parser=pdf_parser)


def get_comparison_service() -> ComparisonService:
    """Get comparison service instance."""
    return ComparisonService()
