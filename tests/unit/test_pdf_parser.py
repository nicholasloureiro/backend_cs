"""Unit tests for PDFParserService."""

import pytest

from app.services.pdf_parser import PDFParserService


class TestExtractUnitsFromDescription:
    """Tests for extract_units_from_description method."""

    def test_extract_units_pattern_x_number(self, pdf_parser_service: PDFParserService):
        """Test extraction of 'X 15' pattern at end of description."""
        description = "TABLETE LACREME BRANCO ZA 100GX15UN X 15"
        result = pdf_parser_service.extract_units_from_description(description)
        assert result == 15

    def test_extract_units_pattern_x_number_different_value(
        self, pdf_parser_service: PDFParserService
    ):
        """Test extraction of 'X 20' pattern."""
        description = "SOME PRODUCT X 20"
        result = pdf_parser_service.extract_units_from_description(description)
        assert result == 20

    def test_extract_units_pattern_gx_un(self, pdf_parser_service: PDFParserService):
        """Test extraction of '100GX15UN' pattern."""
        description = "TABLETE LACREME 100GX15UN"
        result = pdf_parser_service.extract_units_from_description(description)
        assert result == 15

    def test_extract_units_pattern_kgx_un(self, pdf_parser_service: PDFParserService):
        """Test extraction of '1KGX5UN' pattern."""
        description = "PRODUTO GRANDE 1KGX5UN"
        result = pdf_parser_service.extract_units_from_description(description)
        assert result == 5

    def test_extract_units_pattern_gx_u(self, pdf_parser_service: PDFParserService):
        """Test extraction of '100GX15U' pattern (without N)."""
        description = "TABLETE 100GX15U"
        result = pdf_parser_service.extract_units_from_description(description)
        assert result == 15

    def test_extract_units_pattern_x_un_no_weight(
        self, pdf_parser_service: PDFParserService
    ):
        """Test extraction of 'X15UN' pattern without weight prefix."""
        description = "PRODUTO X15UN"
        result = pdf_parser_service.extract_units_from_description(description)
        assert result == 15

    def test_extract_units_no_match(self, pdf_parser_service: PDFParserService):
        """Test that 1 is returned when no pattern matches."""
        description = "PRODUTO SEM UNIDADES"
        result = pdf_parser_service.extract_units_from_description(description)
        assert result == 1

    def test_extract_units_empty_string(self, pdf_parser_service: PDFParserService):
        """Test that empty input returns 1."""
        result = pdf_parser_service.extract_units_from_description("")
        assert result == 1

    def test_extract_units_none_input(self, pdf_parser_service: PDFParserService):
        """Test that None input returns 1."""
        result = pdf_parser_service.extract_units_from_description(None)
        assert result == 1

    def test_extract_units_lowercase(self, pdf_parser_service: PDFParserService):
        """Test that lowercase patterns are also matched."""
        description = "tablete 100gx15un x 15"
        result = pdf_parser_service.extract_units_from_description(description)
        assert result == 15


class TestNormalizeDescription:
    """Tests for normalize_description method."""

    def test_normalize_description_removes_trailing_x_number(
        self, pdf_parser_service: PDFParserService
    ):
        """Test removal of trailing 'X 15' suffix."""
        description = "TABLETE LACREME BRANCO ZA X 15"
        result = pdf_parser_service.normalize_description(description)
        assert result == "TABLETE LACREME BRANCO ZA"

    def test_normalize_description_removes_unit_info(
        self, pdf_parser_service: PDFParserService
    ):
        """Test removal of '100GX15UN' pattern."""
        description = "TABLETE LACREME 100GX15UN BRANCO"
        result = pdf_parser_service.normalize_description(description)
        assert result == "TABLETE LACREME BRANCO"

    def test_normalize_description_removes_both_patterns(
        self, pdf_parser_service: PDFParserService
    ):
        """Test removal of both patterns from description."""
        description = "TABLETE LACREME BRANCO ZA 100GX15UN X 15"
        result = pdf_parser_service.normalize_description(description)
        assert result == "TABLETE LACREME BRANCO ZA"

    def test_normalize_description_removes_decimal_weight(
        self, pdf_parser_service: PDFParserService
    ):
        """Test removal of decimal weight pattern like '13,5GX150UN'."""
        description = "BOMBOM 13,5GX150UN ESPECIAL"
        result = pdf_parser_service.normalize_description(description)
        assert result == "BOMBOM ESPECIAL"

    def test_normalize_description_empty_string(
        self, pdf_parser_service: PDFParserService
    ):
        """Test that empty input returns empty string."""
        result = pdf_parser_service.normalize_description("")
        assert result == ""

    def test_normalize_description_none_input(
        self, pdf_parser_service: PDFParserService
    ):
        """Test that None input returns empty string."""
        result = pdf_parser_service.normalize_description(None)
        assert result == ""

    def test_normalize_description_cleans_extra_spaces(
        self, pdf_parser_service: PDFParserService
    ):
        """Test that extra spaces are cleaned up."""
        description = "TABLETE   LACREME    BRANCO"
        result = pdf_parser_service.normalize_description(description)
        assert result == "TABLETE LACREME BRANCO"


class TestParseNfPdf:
    """Tests for parse_nf_pdf method."""

    def test_parse_nf_pdf_empty_content(self, pdf_parser_service: PDFParserService):
        """Test that empty/invalid PDF returns empty dicts."""
        quantities, descriptions = pdf_parser_service.parse_nf_pdf(b"")
        assert quantities == {}
        assert descriptions == {}

    def test_parse_nf_pdf_invalid_content(self, pdf_parser_service: PDFParserService):
        """Test that invalid PDF content returns empty dicts."""
        quantities, descriptions = pdf_parser_service.parse_nf_pdf(b"not a pdf")
        assert quantities == {}
        assert descriptions == {}


class TestParsePedidoPdf:
    """Tests for parse_pedido_pdf method."""

    def test_parse_pedido_pdf_empty_content(self, pdf_parser_service: PDFParserService):
        """Test that empty/invalid PDF returns empty dicts."""
        quantities, descriptions = pdf_parser_service.parse_pedido_pdf(b"")
        assert quantities == {}
        assert descriptions == {}

    def test_parse_pedido_pdf_invalid_content(
        self, pdf_parser_service: PDFParserService
    ):
        """Test that invalid PDF content returns empty dicts."""
        quantities, descriptions = pdf_parser_service.parse_pedido_pdf(b"not a pdf")
        assert quantities == {}
        assert descriptions == {}
