"""Integration tests for API endpoints."""

import re
from datetime import datetime
from io import BytesIO

import pandas as pd
import pytest
from fastapi.testclient import TestClient


class TestHealthEndpoint:
    """Tests for /health endpoint."""

    def test_health_check(self, client: TestClient):
        """Test GET /health returns healthy status."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data


class TestRootEndpoint:
    """Tests for / endpoint."""

    def test_root_endpoint(self, client: TestClient):
        """Test GET / returns app info."""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "app" in data
        assert "version" in data
        assert data["docs"] == "/docs"


class TestTransformEndpoint:
    """Tests for /api/reports/transform endpoint."""

    def test_transform_endpoint_success(
        self, client: TestClient, sample_weekly_excel: BytesIO
    ):
        """Test POST /api/reports/transform with valid data."""
        sample_weekly_excel.seek(0)

        response = client.post(
            "/api/reports/transform",
            files={"weekly_report": ("weekly.xlsx", sample_weekly_excel)},
        )

        assert response.status_code == 200
        assert (
            response.headers["content-type"]
            == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        # Verify it's a valid Excel file
        result = BytesIO(response.content)
        df = pd.read_excel(result, sheet_name="Faturamento por Produtos")
        assert "Código do Produto" in df.columns
        assert "Pedido" in df.columns
        assert "Total" in df.columns

    def test_transform_endpoint_no_file(self, client: TestClient):
        """Test POST /api/reports/transform without file returns error."""
        response = client.post("/api/reports/transform")

        assert response.status_code == 422  # Validation error


class TestCompareEndpoint:
    """Tests for /api/reports/compare endpoint."""

    def test_compare_endpoint_success(
        self,
        client: TestClient,
        sample_transformed_excel: BytesIO,
        sample_inventory_excel: BytesIO,
    ):
        """Test POST /api/reports/compare with valid data."""
        sample_transformed_excel.seek(0)
        sample_inventory_excel.seek(0)

        response = client.post(
            "/api/reports/compare",
            files={
                "weekly_report": ("weekly.xlsx", sample_transformed_excel),
                "inventory_report": ("inventory.xlsx", sample_inventory_excel),
            },
        )

        assert response.status_code == 200
        assert (
            response.headers["content-type"]
            == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        # Verify it's a valid Excel file
        result = BytesIO(response.content)
        df = pd.read_excel(result, sheet_name="Faturamento por Produtos")
        assert "Código do Produto" in df.columns

    def test_compare_endpoint_missing_inventory(
        self, client: TestClient, sample_transformed_excel: BytesIO
    ):
        """Test POST /api/reports/compare without inventory file."""
        sample_transformed_excel.seek(0)

        response = client.post(
            "/api/reports/compare",
            files={"weekly_report": ("weekly.xlsx", sample_transformed_excel)},
        )

        assert response.status_code == 422  # Validation error


class TestProcessEndpoint:
    """Tests for /api/reports/process endpoint (full pipeline)."""

    def test_process_endpoint_success(
        self,
        client: TestClient,
        sample_weekly_excel: BytesIO,
        sample_inventory_excel: BytesIO,
    ):
        """Test POST /api/reports/process with valid data."""
        sample_weekly_excel.seek(0)
        sample_inventory_excel.seek(0)

        response = client.post(
            "/api/reports/process",
            files={
                "weekly_report": ("weekly.xlsx", sample_weekly_excel),
                "inventory_report": ("inventory.xlsx", sample_inventory_excel),
            },
        )

        assert response.status_code == 200
        assert (
            response.headers["content-type"]
            == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        # Verify the full pipeline output
        result = BytesIO(response.content)
        df = pd.read_excel(result, sheet_name="Faturamento por Produtos")

        # Should have all expected columns with Cód. Loja first
        expected_cols = [
            "Cód. Loja",
            "Código do Produto",
            "Descrição",
            "Grupo",
            "Estoque",
            "Pedido",
            "Total",
            "Saídas",
            "Sugestão",
        ]
        assert list(df.columns) == expected_cols

    def test_process_endpoint_missing_weekly(
        self, client: TestClient, sample_inventory_excel: BytesIO
    ):
        """Test POST /api/reports/process without weekly report."""
        sample_inventory_excel.seek(0)

        response = client.post(
            "/api/reports/process",
            files={"inventory_report": ("inventory.xlsx", sample_inventory_excel)},
        )

        assert response.status_code == 422  # Validation error

    def test_process_endpoint_with_content_disposition(
        self,
        client: TestClient,
        sample_weekly_excel: BytesIO,
        sample_inventory_excel: BytesIO,
    ):
        """Test that response includes correct Content-Disposition header."""
        sample_weekly_excel.seek(0)
        sample_inventory_excel.seek(0)

        response = client.post(
            "/api/reports/process",
            files={
                "weekly_report": ("weekly.xlsx", sample_weekly_excel),
                "inventory_report": ("inventory.xlsx", sample_inventory_excel),
            },
        )

        assert response.status_code == 200
        assert "content-disposition" in response.headers
        assert "attachment" in response.headers["content-disposition"]
        assert ".xlsx" in response.headers["content-disposition"]

    def test_process_endpoint_filename_contains_date_and_store(
        self,
        client: TestClient,
        sample_weekly_excel: BytesIO,
        sample_inventory_excel: BytesIO,
    ):
        """Test that Content-Disposition includes date and store name."""
        sample_weekly_excel.seek(0)
        sample_inventory_excel.seek(0)

        response = client.post(
            "/api/reports/process",
            files={
                "weekly_report": ("weekly.xlsx", sample_weekly_excel),
                "inventory_report": ("inventory.xlsx", sample_inventory_excel),
            },
        )

        assert response.status_code == 200
        content_disposition = response.headers["content-disposition"]

        # Verify filename format: relatorio_processado_DATE_LOJA.xlsx
        assert "relatorio_processado_" in content_disposition

        # Verify date format YYYY-MM-DD is present
        today = datetime.now().strftime("%Y-%m-%d")
        assert today in content_disposition

        # Verify store name is present (sanitized version of "MG UBERLANDIA SH PATIO SABIA")
        assert "MG_UBERLANDIA_SH_PATIO_SABIA" in content_disposition

    def test_process_endpoint_with_mazza_report(
        self,
        client: TestClient,
        sample_weekly_excel: BytesIO,
        sample_inventory_excel_1225: BytesIO,
        sample_mazza_excel: BytesIO,
    ):
        """Test POST /api/reports/process with mazza_report for store 1225."""
        sample_weekly_excel.seek(0)
        sample_inventory_excel_1225.seek(0)
        sample_mazza_excel.seek(0)

        response = client.post(
            "/api/reports/process",
            files={
                "weekly_report": ("weekly.xlsx", sample_weekly_excel),
                "inventory_report": ("inventory.xlsx", sample_inventory_excel_1225),
                "mazza_report": ("mazza.xlsx", sample_mazza_excel),
            },
        )

        assert response.status_code == 200
        assert (
            response.headers["content-type"]
            == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        # Verify Mazza data was merged
        result = BytesIO(response.content)
        df = pd.read_excel(result, sheet_name="Faturamento por Produtos")
        df["Código do Produto"] = df["Código do Produto"].astype(str)

        # Check that Mazza-only product was added
        assert "9999999" in df["Código do Produto"].values

        # Check that existing product got Mazza QUANTIDADE added to Saídas
        row = df[df["Código do Produto"] == "1234567"].iloc[0]
        # Original Saídas from weekly was 20, Mazza adds 50 -> 70
        assert row["Saídas"] == 70


class TestCompareEndpointFilename:
    """Tests for /api/reports/compare endpoint filename format."""

    def test_compare_endpoint_filename_contains_date_and_store(
        self,
        client: TestClient,
        sample_transformed_excel: BytesIO,
        sample_inventory_excel: BytesIO,
    ):
        """Test that Content-Disposition includes date and store name."""
        sample_transformed_excel.seek(0)
        sample_inventory_excel.seek(0)

        response = client.post(
            "/api/reports/compare",
            files={
                "weekly_report": ("weekly.xlsx", sample_transformed_excel),
                "inventory_report": ("inventory.xlsx", sample_inventory_excel),
            },
        )

        assert response.status_code == 200
        content_disposition = response.headers["content-disposition"]

        # Verify filename format: relatorio_processado_DATE_LOJA.xlsx
        assert "relatorio_processado_" in content_disposition

        # Verify date format YYYY-MM-DD is present
        today = datetime.now().strftime("%Y-%m-%d")
        assert today in content_disposition

        # Verify store name is present (sanitized)
        assert "MG_UBERLANDIA_SH_PATIO_SABIA" in content_disposition


class TestCompareEndpointWithMazza:
    """Tests for /api/reports/compare endpoint with Mazza report."""

    def test_compare_endpoint_with_mazza_report(
        self,
        client: TestClient,
        sample_transformed_excel: BytesIO,
        sample_inventory_excel_1225: BytesIO,
        sample_mazza_excel: BytesIO,
    ):
        """Test POST /api/reports/compare with mazza_report for store 1225."""
        sample_transformed_excel.seek(0)
        sample_inventory_excel_1225.seek(0)
        sample_mazza_excel.seek(0)

        response = client.post(
            "/api/reports/compare",
            files={
                "weekly_report": ("weekly.xlsx", sample_transformed_excel),
                "inventory_report": ("inventory.xlsx", sample_inventory_excel_1225),
                "mazza_report": ("mazza.xlsx", sample_mazza_excel),
            },
        )

        assert response.status_code == 200

        # Verify Mazza data was merged
        result = BytesIO(response.content)
        df = pd.read_excel(result, sheet_name="Faturamento por Produtos")
        df["Código do Produto"] = df["Código do Produto"].astype(str)

        # Check that Mazza-only product was added
        assert "9999999" in df["Código do Produto"].values
