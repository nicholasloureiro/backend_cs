"""Unit tests for TransformationService."""

from io import BytesIO

import pandas as pd
import pytest

from app.services.transformation import TransformationService


class TestReadSourceExcel:
    """Tests for _read_source_excel method."""

    def test_read_source_excel_correct_columns(
        self, transformation_service: TransformationService, sample_weekly_excel: BytesIO
    ):
        """Test that source Excel is read with correct columns."""
        df = transformation_service._read_source_excel(sample_weekly_excel)

        expected_cols = [
            "Código do Produto",
            "Descrição",
            "Grupo",
            "Estoque",
            "Quantidade Líquida",
        ]
        assert list(df.columns) == expected_cols

    def test_read_source_excel_filters_totals(
        self, transformation_service: TransformationService, sample_weekly_excel: BytesIO
    ):
        """Test that 'Totais' row is filtered out."""
        df = transformation_service._read_source_excel(sample_weekly_excel)

        assert not df["Descrição"].str.contains("Totais", case=False, na=False).any()

    def test_read_source_excel_converts_types(
        self, transformation_service: TransformationService, sample_weekly_excel: BytesIO
    ):
        """Test that numeric columns are converted properly."""
        df = transformation_service._read_source_excel(sample_weekly_excel)

        assert df["Código do Produto"].dtype == object  # string
        assert df["Estoque"].dtype in ["int64", "float64"]
        assert df["Quantidade Líquida"].dtype in ["int64", "float64"]


class TestProcess:
    """Tests for process method."""

    def test_process_without_pdfs(
        self, transformation_service: TransformationService, sample_weekly_excel: BytesIO
    ):
        """Test processing with Excel only (no PDFs)."""
        result = transformation_service.process(
            weekly_excel=sample_weekly_excel,
            nf_pdfs=[],
            pedido_pdfs=[],
        )

        # Should return a valid Excel file
        assert isinstance(result, BytesIO)

        # Read the result and verify structure
        result_df = pd.read_excel(result, sheet_name="Faturamento por Produtos")
        expected_cols = [
            "Código do Produto",
            "Descrição",
            "Grupo",
            "Estoque",
            "Pedido",
            "Total",
            "Saídas",
            "Sugestão",
        ]
        assert list(result_df.columns) == expected_cols

    def test_process_adds_new_products_from_pdfs(
        self, transformation_service: TransformationService, sample_weekly_excel: BytesIO
    ):
        """Test that products from PDFs not in Excel are added."""
        # Mock the pdf_parser to return a new product
        original_process_pdfs = transformation_service._process_pdfs

        def mock_process_pdfs(nf_pdfs, pedido_pdfs):
            return (
                {"9999999": 50},  # New product not in Excel
                {"9999999": "PRODUTO NOVO PDF"},
            )

        transformation_service._process_pdfs = mock_process_pdfs

        result = transformation_service.process(
            weekly_excel=sample_weekly_excel,
            nf_pdfs=[b"fake pdf"],
            pedido_pdfs=[],
        )

        # Restore original method
        transformation_service._process_pdfs = original_process_pdfs

        result_df = pd.read_excel(result, sheet_name="Faturamento por Produtos")
        result_df["Código do Produto"] = result_df["Código do Produto"].astype(str)

        # Check new product was added
        assert "9999999" in result_df["Código do Produto"].values

    def test_total_calculation(
        self, transformation_service: TransformationService, sample_weekly_excel: BytesIO
    ):
        """Test that Total = Estoque + Pedido."""
        # Mock to return specific quantities for existing products
        original_process_pdfs = transformation_service._process_pdfs

        def mock_process_pdfs(nf_pdfs, pedido_pdfs):
            return (
                {"1234567": 25},  # Existing product
                {"1234567": "PRODUTO TESTE A"},
            )

        transformation_service._process_pdfs = mock_process_pdfs

        result = transformation_service.process(
            weekly_excel=sample_weekly_excel,
            nf_pdfs=[b"fake pdf"],
            pedido_pdfs=[],
        )

        # Restore original method
        transformation_service._process_pdfs = original_process_pdfs

        result_df = pd.read_excel(result, sheet_name="Faturamento por Produtos")
        result_df["Código do Produto"] = result_df["Código do Produto"].astype(str)

        # Find the row for product 1234567
        row = result_df[result_df["Código do Produto"] == "1234567"].iloc[0]

        # Estoque=100, Pedido=25, Total should be 125
        assert row["Estoque"] == 100
        assert row["Pedido"] == 25
        assert row["Total"] == 125

    def test_process_output_sorted_by_description(
        self, transformation_service: TransformationService, sample_weekly_excel: BytesIO
    ):
        """Test that output is sorted by Descrição."""
        result = transformation_service.process(
            weekly_excel=sample_weekly_excel,
            nf_pdfs=[],
            pedido_pdfs=[],
        )

        result_df = pd.read_excel(result, sheet_name="Faturamento por Produtos")

        # Check if sorted by Descrição
        descriptions = result_df["Descrição"].tolist()
        assert descriptions == sorted(descriptions)


class TestProcessPdfs:
    """Tests for _process_pdfs method."""

    def test_process_pdfs_aggregates_quantities(
        self, transformation_service: TransformationService
    ):
        """Test that PDF quantities are aggregated correctly."""
        # Mock the pdf_parser methods
        original_parse_nf = transformation_service.pdf_parser.parse_nf_pdf
        original_parse_pedido = transformation_service.pdf_parser.parse_pedido_pdf

        call_count = {"nf": 0}

        def mock_parse_nf(content):
            call_count["nf"] += 1
            if call_count["nf"] == 1:
                return ({"1234567": 10}, {"1234567": "PRODUTO A"})
            return ({"1234567": 15}, {"1234567": "PRODUTO A"})

        def mock_parse_pedido(content):
            return ({"1234567": 5}, {"1234567": "PRODUTO A"})

        transformation_service.pdf_parser.parse_nf_pdf = mock_parse_nf
        transformation_service.pdf_parser.parse_pedido_pdf = mock_parse_pedido

        quantities, descriptions = transformation_service._process_pdfs(
            nf_pdfs=[b"pdf1", b"pdf2"],
            pedido_pdfs=[b"pedido1"],
        )

        # Restore original methods
        transformation_service.pdf_parser.parse_nf_pdf = original_parse_nf
        transformation_service.pdf_parser.parse_pedido_pdf = original_parse_pedido

        # 10 + 15 + 5 = 30
        assert quantities["1234567"] == 30
        assert descriptions["1234567"] == "PRODUTO A"
