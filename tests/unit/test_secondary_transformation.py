"""Unit tests for SecondaryTransformationService."""

from io import BytesIO

import pandas as pd
import pytest

from app.services.pdf_parser import PDFParserService
from app.services.secondary_transformation import SecondaryTransformationService

STANDARD_COLS = [
    "Código do Produto",
    "Descrição",
    "Grupo",
    "Estoque",
    "Quantidade Líquida",
]


@pytest.fixture
def secondary_service() -> SecondaryTransformationService:
    return SecondaryTransformationService(pdf_parser=PDFParserService())


@pytest.fixture
def multiloja_excel() -> BytesIO:
    """Original Multiloja secondary layout (no Estoque, sales as 'Qtde vendida')."""
    df = pd.DataFrame(
        {
            0: ["Faturamento produtos por Multloja", "Loja", "2676", "2676", ""],
            1: ["", "Código", "1234567", "2345678", ""],
            2: ["", "Produto", "PRODUTO A", "PRODUTO B", "Totais =>"],
            3: ["", "CÓD. GRUPO", "1014", "1010", ""],
            4: ["", "DESC. GRUPO", "Funcionais", "Outros", ""],
            5: ["", "Qtde vendida", 9, 48, ""],
        }
    )
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(
            writer, sheet_name="Faturamento produtos por Multlo", index=False, header=False
        )
    output.seek(0)
    return output


@pytest.fixture
def standard_format_excel() -> BytesIO:
    """Newer secondary layout that mirrors the primary report (has real Estoque)."""
    df = pd.DataFrame(
        {
            0: ["Faturamento por Produtos", "Código do Produto", "1234567", "2345678", ""],
            1: ["", "Descrição", "PRODUTO A", "PRODUTO B", "Totais =>"],
            2: ["", "Grupo", "1014 - Funcionais", "1010 - Outros", ""],
            3: ["", "Estoque", 100, 50, 150],
            4: ["", "Quantidade Líquida", 20, 10, 30],
        }
    )
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(
            writer, sheet_name="Faturamento por Produtos", index=False, header=False
        )
    output.seek(0)
    return output


class TestReadMultilojaFormat:
    def test_columns_and_no_estoque(self, secondary_service, multiloja_excel):
        df = secondary_service._read_source_excel(multiloja_excel)
        assert list(df.columns) == STANDARD_COLS
        # Multiloja layout carries no stock data
        assert (df["Estoque"] == 0).all()
        # Sales come from "Qtde vendida"
        assert df["Quantidade Líquida"].tolist() == [9, 48]

    def test_totais_filtered(self, secondary_service, multiloja_excel):
        df = secondary_service._read_source_excel(multiloja_excel)
        assert not df["Descrição"].astype(str).str.contains("Totais", case=False).any()


@pytest.fixture
def standard_format_no_title_excel() -> BytesIO:
    """Newer layout where the header sits on the first row (no leading title row)."""
    df = pd.DataFrame(
        {
            "Código do Produto": ["1234567", "2345678", ""],
            "Descrição": ["PRODUTO A", "PRODUTO B", "Totais =>"],
            "Grupo": ["1014 - Funcionais", "1010 - Outros", ""],
            "Estoque": [100, 50, 150],
            "Quantidade Líquida": [20, 10, 30],
        }
    )
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Faturamento por Produtos", index=False)
    output.seek(0)
    return output


class TestReadStandardFormat:
    def test_columns_and_real_estoque(self, secondary_service, standard_format_excel):
        df = secondary_service._read_source_excel(standard_format_excel)
        assert list(df.columns) == STANDARD_COLS
        # Newer layout provides real stock values directly
        assert df["Estoque"].tolist() == [100.0, 50.0]
        assert df["Quantidade Líquida"].tolist() == [20, 10]

    def test_totais_filtered(self, secondary_service, standard_format_excel):
        df = secondary_service._read_source_excel(standard_format_excel)
        assert not df["Descrição"].astype(str).str.contains("Totais", case=False).any()

    def test_process_produces_output(self, secondary_service, standard_format_excel):
        result = secondary_service.process(
            weekly_excel=standard_format_excel, nf_pdfs=[], pedido_pdfs=[]
        )
        df = pd.read_excel(result)
        assert "Saídas" in df.columns
        assert len(df) == 2

    def test_no_title_row_variant(self, secondary_service, standard_format_no_title_excel):
        """Header on the first row (no title row) is still parsed correctly."""
        df = secondary_service._read_source_excel(standard_format_no_title_excel)
        assert list(df.columns) == STANDARD_COLS
        assert df["Estoque"].tolist() == [100.0, 50.0]
        assert not df["Descrição"].astype(str).str.contains("Totais", case=False).any()
