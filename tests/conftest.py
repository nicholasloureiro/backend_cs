"""Shared pytest fixtures for Cacau Show API tests."""

from io import BytesIO

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.pdf_parser import PDFParserService
from app.services.transformation import TransformationService
from app.services.comparison import ComparisonService


@pytest.fixture
def pdf_parser_service() -> PDFParserService:
    """Fixture for PDFParserService instance."""
    return PDFParserService()


@pytest.fixture
def transformation_service(pdf_parser_service: PDFParserService) -> TransformationService:
    """Fixture for TransformationService instance."""
    return TransformationService(pdf_parser=pdf_parser_service)


@pytest.fixture
def comparison_service() -> ComparisonService:
    """Fixture for ComparisonService instance."""
    return ComparisonService()


@pytest.fixture
def client() -> TestClient:
    """Fixture for FastAPI TestClient."""
    return TestClient(app)


@pytest.fixture
def sample_weekly_excel() -> BytesIO:
    """Create a sample weekly report Excel file in memory."""
    # Create a DataFrame that mimics the weekly report structure
    # First row is metadata, second row is headers, then data
    df = pd.DataFrame(
        {
            0: ["Header Row", "Código do Produto", "1234567", "2345678", "Totais"],
            1: ["Header Row", "Descrição", "PRODUTO TESTE A", "PRODUTO TESTE B", "Totais"],
            2: ["Header Row", "Grupo", "1014 - Funcionais", "1010 - Outros", ""],
            3: ["Header Row", "Estoque", 100, 50, 150],
            4: ["Header Row", "Quantidade Líquida", 20, 10, 30],
        }
    )

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Faturamento por Produtos", index=False, header=False)
    output.seek(0)
    return output


@pytest.fixture
def sample_inventory_excel() -> BytesIO:
    """Create a sample inventory Excel file in memory."""
    # Create a DataFrame that mimics the inventory structure
    df = pd.DataFrame(
        {
            0: ["Header Row", "Cód. Loja", "6835", "6835"],
            1: ["Header Row", "Loja", "MG UBERLANDIA SH PATIO SABIA", "MG UBERLANDIA SH PATIO SABIA"],
            2: ["Header Row", "Cód Produto", "1234567", "3456789"],
            3: ["Header Row", "Desc Produto", "PRODUTO TESTE A", "PRODUTO NOVO C"],
            4: ["Header Row", "Cod Grupo", "1014", "1013"],
            5: ["Header Row", "Desc GRUPO", "Funcionais", "Pascoa"],
            6: ["Header Row", "Quantidade", 150, 30],
            7: ["Header Row", "R$ CUSTO UN", 10.0, 15.0],
            8: ["Header Row", "R$ CUSTO TOTAL ITEM", 1500.0, 450.0],
            9: ["Header Row", "R$ VENDA UN", 20.0, 30.0],
            10: ["Header Row", "R$ VENDA TOTAL ITEM", 3000.0, 900.0],
        }
    )

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Estoque Produtos com Valor", index=False, header=False)
    output.seek(0)
    return output


@pytest.fixture
def sample_transformed_excel() -> BytesIO:
    """Create a sample transformed weekly report Excel file."""
    df = pd.DataFrame(
        {
            "Código do Produto": ["1234567", "2345678", "4567890"],
            "Descrição": ["PRODUTO TESTE A", "PRODUTO TESTE B", "PDF PRODUTO DESC"],
            "Grupo": ["1014 - Funcionais", "1010 - Outros", ""],
            "Estoque": [100, 50, 20],
            "Pedido": [25, 10, 5],
            "Total": [125, 60, 25],
            "Saídas": [20, 10, 3],
            "Sugestão": [None, None, None],
        }
    )

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Faturamento por Produtos", index=False)
    output.seek(0)
    return output


@pytest.fixture
def sample_mazza_excel() -> BytesIO:
    """Create a sample Mazza report Excel file."""
    df = pd.DataFrame(
        {
            "CODIGO": ["1234567", "9999999"],
            "NOME PRODUTO": ["PRODUTO EXISTENTE", "PRODUTO NOVO MAZZA"],
            "QUANTIDADE": [50, 100],
            "VALOR TOTAL CATÁLOGO": [1000.0, 2000.0],
            "VALOR TOTAL FATURADO": [500.0, 1000.0],
        }
    )

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="RankingFaturamento", index=False)
    output.seek(0)
    return output


@pytest.fixture
def sample_inventory_excel_1225() -> BytesIO:
    """Create a sample inventory Excel file for store 1225."""
    df = pd.DataFrame(
        {
            0: ["Header Row", "Cód. Loja", "1225", "1225"],
            1: ["Header Row", "Loja", "LOJA STORE 1225", "LOJA STORE 1225"],
            2: ["Header Row", "Cód Produto", "1234567", "3456789"],
            3: ["Header Row", "Desc Produto", "PRODUTO TESTE A", "PRODUTO NOVO C"],
            4: ["Header Row", "Cod Grupo", "1014", "1013"],
            5: ["Header Row", "Desc GRUPO", "Funcionais", "Pascoa"],
            6: ["Header Row", "Quantidade", 150, 30],
            7: ["Header Row", "R$ CUSTO UN", 10.0, 15.0],
            8: ["Header Row", "R$ CUSTO TOTAL ITEM", 1500.0, 450.0],
            9: ["Header Row", "R$ VENDA UN", 20.0, 30.0],
            10: ["Header Row", "R$ VENDA TOTAL ITEM", 3000.0, 900.0],
        }
    )

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Estoque Produtos com Valor", index=False, header=False)
    output.seek(0)
    return output
