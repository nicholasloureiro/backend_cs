"""Unit tests for fuzzy sheet name matching."""

from io import BytesIO

import pandas as pd
import pytest

from app.services.excel_utils import find_sheet_name
from app.services.comparison import ComparisonService


class TestFindSheetName:
    """Tests for the find_sheet_name utility function."""

    def _make_excel(self, sheet_names: list[str]) -> BytesIO:
        """Helper to create an Excel file with given sheet names."""
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            for name in sheet_names:
                pd.DataFrame({"A": [1]}).to_excel(writer, sheet_name=name, index=False)
        output.seek(0)
        return output

    def test_exact_match(self):
        """Test that exact sheet name is returned directly."""
        buf = self._make_excel(["RankingFaturamento", "Other"])
        assert find_sheet_name(buf, "RankingFaturamento") == "RankingFaturamento"

    def test_startswith_match(self):
        """Test that a sheet starting with the expected name is matched."""
        buf = self._make_excel(["RankingFaturamento (2)", "Other"])
        assert find_sheet_name(buf, "RankingFaturamento") == "RankingFaturamento (2)"

    def test_single_sheet_fallback(self):
        """Test that a single-sheet workbook returns that sheet."""
        buf = self._make_excel(["CompletelyDifferent"])
        assert find_sheet_name(buf, "RankingFaturamento") == "CompletelyDifferent"

    def test_no_match_raises(self):
        """Test that ValueError is raised when no match is found."""
        buf = self._make_excel(["SheetA", "SheetB"])
        with pytest.raises(ValueError, match="Planilha 'RankingFaturamento' não encontrada"):
            find_sheet_name(buf, "RankingFaturamento")

    def test_multiple_startswith_matches_raises(self):
        """Test that multiple startswith matches raise an error (ambiguous)."""
        buf = self._make_excel(["RankingFaturamento (2)", "RankingFaturamento (3)", "Other"])
        with pytest.raises(ValueError, match="Planilha 'RankingFaturamento' não encontrada"):
            find_sheet_name(buf, "RankingFaturamento")

    def test_file_content_is_rewound(self):
        """Test that file position is reset after calling find_sheet_name."""
        buf = self._make_excel(["RankingFaturamento"])
        find_sheet_name(buf, "RankingFaturamento")
        assert buf.tell() == 0


class TestFuzzyMatchingInComparison:
    """Tests that fuzzy matching works end-to-end in ComparisonService."""

    def test_read_mazza_report_variant_sheet(
        self, comparison_service: ComparisonService, sample_mazza_excel_variant_sheet: BytesIO
    ):
        """Test that _read_mazza_report works with 'RankingFaturamento (2)' sheet name."""
        df = comparison_service._read_mazza_report(sample_mazza_excel_variant_sheet)

        assert list(df.columns) == ["CODIGO", "NOME PRODUTO", "QUANTIDADE"]
        assert len(df) == 2
        assert df["CODIGO"].dtype == object

    def test_read_mazza_report_exact_sheet(
        self, comparison_service: ComparisonService, sample_mazza_excel: BytesIO
    ):
        """Regression: exact sheet name still works."""
        df = comparison_service._read_mazza_report(sample_mazza_excel)

        assert list(df.columns) == ["CODIGO", "NOME PRODUTO", "QUANTIDADE"]
        assert len(df) == 2

    def test_read_inventory_variant_sheet(
        self, comparison_service: ComparisonService, sample_inventory_excel_variant_sheet: BytesIO
    ):
        """Test that _read_inventory works with 'Estoque Produtos com Valor (2)' sheet name."""
        df = comparison_service._read_inventory(sample_inventory_excel_variant_sheet)

        expected_cols = [
            "Cód. Loja",
            "Loja",
            "Cód Produto",
            "Desc Produto",
            "Cod Grupo",
            "Desc GRUPO",
            "Quantidade",
            "R$ CUSTO UN",
            "R$ CUSTO TOTAL ITEM",
            "R$ VENDA UN",
            "R$ VENDA TOTAL ITEM",
        ]
        assert list(df.columns) == expected_cols

    def test_read_inventory_exact_sheet(
        self, comparison_service: ComparisonService, sample_inventory_excel: BytesIO
    ):
        """Regression: exact inventory sheet name still works."""
        df = comparison_service._read_inventory(sample_inventory_excel)

        assert "Cód. Loja" in df.columns
        assert len(df) > 0
