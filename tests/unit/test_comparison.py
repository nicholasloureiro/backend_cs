"""Unit tests for ComparisonService."""

from io import BytesIO

import pandas as pd
import pytest

from app.services.comparison import ComparisonService


class TestReadInventory:
    """Tests for _read_inventory method."""

    def test_read_inventory_correct_columns(
        self, comparison_service: ComparisonService, sample_inventory_excel: BytesIO
    ):
        """Test that inventory Excel is read with correct columns."""
        df = comparison_service._read_inventory(sample_inventory_excel)

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

    def test_read_inventory_converts_types(
        self, comparison_service: ComparisonService, sample_inventory_excel: BytesIO
    ):
        """Test that types are converted properly."""
        df = comparison_service._read_inventory(sample_inventory_excel)

        assert df["Cód Produto"].dtype == object  # string
        assert df["Quantidade"].dtype in ["int64", "float64"]


class TestReadWeeklyReport:
    """Tests for _read_weekly_report method."""

    def test_read_weekly_report_correct_structure(
        self, comparison_service: ComparisonService, sample_transformed_excel: BytesIO
    ):
        """Test that weekly report is read correctly."""
        df = comparison_service._read_weekly_report(sample_transformed_excel)

        assert "Código do Produto" in df.columns
        assert df["Código do Produto"].dtype == object  # string


class TestCompare:
    """Tests for compare method."""

    def test_compare_updates_estoque(
        self,
        comparison_service: ComparisonService,
        sample_transformed_excel: BytesIO,
        sample_inventory_excel: BytesIO,
    ):
        """Test that Estoque is updated when inventory value differs."""
        result, store_name = comparison_service.compare(
            weekly_report=sample_transformed_excel,
            inventory_report=sample_inventory_excel,
        )

        assert store_name == "MG UBERLANDIA SH PATIO SABIA"
        result_df = pd.read_excel(result, sheet_name="Faturamento por Produtos")
        result_df["Código do Produto"] = result_df["Código do Produto"].astype(str)

        # Product 1234567: original Estoque=100, inventory Quantidade=150
        row = result_df[result_df["Código do Produto"] == "1234567"].iloc[0]
        assert row["Estoque"] == 150  # Updated from inventory

    def test_compare_sets_estoque_zero_when_not_in_inventory(
        self,
        comparison_service: ComparisonService,
        sample_transformed_excel: BytesIO,
        sample_inventory_excel: BytesIO,
    ):
        """Test that Estoque is set to 0 when product not in inventory."""
        result, _ = comparison_service.compare(
            weekly_report=sample_transformed_excel,
            inventory_report=sample_inventory_excel,
        )

        result_df = pd.read_excel(result, sheet_name="Faturamento por Produtos")
        result_df["Código do Produto"] = result_df["Código do Produto"].astype(str)

        # Product 2345678 is in weekly but not in inventory
        row = result_df[result_df["Código do Produto"] == "2345678"].iloc[0]
        assert row["Estoque"] == 0

    def test_compare_adds_new_products_from_inventory(
        self,
        comparison_service: ComparisonService,
        sample_transformed_excel: BytesIO,
        sample_inventory_excel: BytesIO,
    ):
        """Test that products from inventory not in weekly are added."""
        result, _ = comparison_service.compare(
            weekly_report=sample_transformed_excel,
            inventory_report=sample_inventory_excel,
        )

        result_df = pd.read_excel(result, sheet_name="Faturamento por Produtos")
        result_df["Código do Produto"] = result_df["Código do Produto"].astype(str)

        # Product 3456789 is only in inventory
        assert "3456789" in result_df["Código do Produto"].values

    def test_compare_recalculates_total(
        self,
        comparison_service: ComparisonService,
        sample_transformed_excel: BytesIO,
        sample_inventory_excel: BytesIO,
    ):
        """Test that Total is recalculated after Estoque update."""
        result, _ = comparison_service.compare(
            weekly_report=sample_transformed_excel,
            inventory_report=sample_inventory_excel,
        )

        result_df = pd.read_excel(result, sheet_name="Faturamento por Produtos")
        result_df["Código do Produto"] = result_df["Código do Produto"].astype(str)

        # Product 1234567: Estoque=150 (from inventory), Pedido=25
        row = result_df[result_df["Código do Produto"] == "1234567"].iloc[0]
        assert row["Total"] == 175  # 150 + 25


class TestApplySorting:
    """Tests for _apply_sorting method."""

    def test_sorting_funcionais_first(self, comparison_service: ComparisonService):
        """Test that 1014-Funcionais products come first."""
        df = pd.DataFrame(
            {
                "Código do Produto": ["1", "2", "3"],
                "Descrição": ["B Product", "A Product", "C Product"],
                "Grupo": ["1010 - Outros", "1014 - Funcionais", "1010 - Outros"],
            }
        )

        result = comparison_service._apply_sorting(df)

        # First row should be Funcionais
        assert "1014" in str(result.iloc[0]["Grupo"])

    def test_sorting_pascoa_last(self, comparison_service: ComparisonService):
        """Test that 1013-Pascoa products come last."""
        df = pd.DataFrame(
            {
                "Código do Produto": ["1", "2", "3"],
                "Descrição": ["A Product", "B Product", "C Product"],
                "Grupo": ["1010 - Outros", "1013 - Pascoa", "1014 - Funcionais"],
            }
        )

        result = comparison_service._apply_sorting(df)

        # Last row should be Pascoa
        assert "1013" in str(result.iloc[-1]["Grupo"])

    def test_sorting_middle_by_description(self, comparison_service: ComparisonService):
        """Test that middle products are sorted by Descrição."""
        df = pd.DataFrame(
            {
                "Código do Produto": ["1", "2", "3", "4"],
                "Descrição": ["Z Product", "A Product", "M Product", "B Product"],
                "Grupo": ["1010 - Outros", "1010 - Outros", "1010 - Outros", "1010 - Outros"],
            }
        )

        result = comparison_service._apply_sorting(df)
        descriptions = result["Descrição"].tolist()

        # Should be sorted alphabetically
        assert descriptions == sorted(descriptions)

    def test_sorting_preserves_all_rows(self, comparison_service: ComparisonService):
        """Test that sorting preserves all rows."""
        df = pd.DataFrame(
            {
                "Código do Produto": ["1", "2", "3"],
                "Descrição": ["C", "A", "B"],
                "Grupo": ["1013 - Pascoa", "1014 - Funcionais", "1010 - Outros"],
            }
        )

        result = comparison_service._apply_sorting(df)

        assert len(result) == 3


class TestEnrichNullGrupo:
    """Tests for enriching products with empty Grupo from inventory."""

    def test_enriches_grupo_from_inventory(self, comparison_service: ComparisonService):
        """Test that empty Grupo gets populated from inventory."""
        weekly_df = pd.DataFrame(
            {
                "Código do Produto": ["1234567"],
                "Descrição": ["PDF EXTRACTED DESC"],
                "Grupo": [""],  # Empty Grupo (PDF-sourced product)
                "Estoque": [100],
                "Pedido": [10],
                "Total": [110],
                "Saídas": [5],
                "Sugestão": [None],
            }
        )

        inventory_df = pd.DataFrame(
            {
                "Cód. Loja": ["6835"],
                "Loja": ["MG UBERLANDIA"],
                "Cód Produto": ["1234567"],
                "Desc Produto": ["PRODUTO INVENTARIO"],
                "Cod Grupo": ["1014"],
                "Desc GRUPO": ["Funcionais"],
                "Quantidade": [150],
            }
        )

        result = comparison_service._compare_and_merge(weekly_df, inventory_df)

        row = result[result["Código do Produto"] == "1234567"].iloc[0]
        assert row["Grupo"] == "1014 - Funcionais"

    def test_enriches_description_from_inventory(self, comparison_service: ComparisonService):
        """Test that Descricao is updated from inventory for empty Grupo products."""
        weekly_df = pd.DataFrame(
            {
                "Código do Produto": ["1234567"],
                "Descrição": ["PDF EXTRACTED DESC"],
                "Grupo": [""],  # Empty Grupo (PDF-sourced product)
                "Estoque": [100],
                "Pedido": [10],
                "Total": [110],
                "Saídas": [5],
                "Sugestão": [None],
            }
        )

        inventory_df = pd.DataFrame(
            {
                "Cód. Loja": ["6835"],
                "Loja": ["MG UBERLANDIA"],
                "Cód Produto": ["1234567"],
                "Desc Produto": ["PRODUTO INVENTARIO CORRETO"],
                "Cod Grupo": ["1014"],
                "Desc GRUPO": ["Funcionais"],
                "Quantidade": [150],
            }
        )

        result = comparison_service._compare_and_merge(weekly_df, inventory_df)

        row = result[result["Código do Produto"] == "1234567"].iloc[0]
        assert row["Descrição"] == "PRODUTO INVENTARIO CORRETO"

    def test_adds_cod_loja_column(self, comparison_service: ComparisonService):
        """Test that Cód. Loja appears in output for all products."""
        weekly_df = pd.DataFrame(
            {
                "Código do Produto": ["1234567", "9999999"],
                "Descrição": ["PRODUTO A", "PRODUTO B NOT IN INV"],
                "Grupo": ["1010 - Outros", "1010 - Outros"],
                "Estoque": [100, 50],
                "Pedido": [10, 5],
                "Total": [110, 55],
                "Saídas": [5, 2],
                "Sugestão": [None, None],
            }
        )

        inventory_df = pd.DataFrame(
            {
                "Cód. Loja": ["6835"],
                "Loja": ["MG UBERLANDIA"],
                "Cód Produto": ["1234567"],
                "Desc Produto": ["PRODUTO A"],
                "Cod Grupo": ["1010"],
                "Desc GRUPO": ["Outros"],
                "Quantidade": [150],
            }
        )

        result = comparison_service._compare_and_merge(weekly_df, inventory_df)

        assert "Cód. Loja" in result.columns
        # Product in inventory gets store code
        row_in_inv = result[result["Código do Produto"] == "1234567"].iloc[0]
        assert row_in_inv["Cód. Loja"] == "6835"
        # Product NOT in inventory also gets store code
        row_not_in_inv = result[result["Código do Produto"] == "9999999"].iloc[0]
        assert row_not_in_inv["Cód. Loja"] == "6835"

    def test_cod_loja_is_first_column(
        self,
        comparison_service: ComparisonService,
        sample_transformed_excel: BytesIO,
        sample_inventory_excel: BytesIO,
    ):
        """Test that Cód. Loja is the first column in the output."""
        result, _ = comparison_service.compare(
            weekly_report=sample_transformed_excel,
            inventory_report=sample_inventory_excel,
        )

        result_df = pd.read_excel(result, sheet_name="Faturamento por Produtos")
        assert result_df.columns[0] == "Cód. Loja"

    def test_does_not_enrich_non_empty_grupo(self, comparison_service: ComparisonService):
        """Test that products with existing Grupo are not modified."""
        weekly_df = pd.DataFrame(
            {
                "Código do Produto": ["1234567"],
                "Descrição": ["ORIGINAL DESC"],
                "Grupo": ["1010 - Outros"],  # Non-empty Grupo
                "Estoque": [100],
                "Pedido": [10],
                "Total": [110],
                "Saídas": [5],
                "Sugestão": [None],
            }
        )

        inventory_df = pd.DataFrame(
            {
                "Cód. Loja": ["6835"],
                "Loja": ["MG UBERLANDIA"],
                "Cód Produto": ["1234567"],
                "Desc Produto": ["DIFFERENT INVENTORY DESC"],
                "Cod Grupo": ["1014"],
                "Desc GRUPO": ["Funcionais"],
                "Quantidade": [150],
            }
        )

        result = comparison_service._compare_and_merge(weekly_df, inventory_df)

        row = result[result["Código do Produto"] == "1234567"].iloc[0]
        # Grupo should remain unchanged
        assert row["Grupo"] == "1010 - Outros"
        # Description should remain unchanged
        assert row["Descrição"] == "ORIGINAL DESC"


class TestCompareAndMerge:
    """Tests for _compare_and_merge method."""

    def test_merge_creates_correct_structure(self, comparison_service: ComparisonService):
        """Test that merged output has correct structure for new products."""
        weekly_df = pd.DataFrame(
            {
                "Código do Produto": ["1234567"],
                "Descrição": ["PRODUTO A"],
                "Grupo": ["1010 - Outros"],
                "Estoque": [100],
                "Pedido": [10],
                "Total": [110],
                "Saídas": [5],
                "Sugestão": [None],
            }
        )

        inventory_df = pd.DataFrame(
            {
                "Cód. Loja": ["6835", "6835"],
                "Loja": ["MG UBERLANDIA", "MG UBERLANDIA"],
                "Cód Produto": ["1234567", "9999999"],
                "Desc Produto": ["PRODUTO A", "PRODUTO NOVO"],
                "Cod Grupo": ["1010", "1013"],
                "Desc GRUPO": ["Outros", "Pascoa"],
                "Quantidade": [150, 30],
            }
        )

        result = comparison_service._compare_and_merge(weekly_df, inventory_df)

        # Check new product was added with correct structure
        new_row = result[result["Código do Produto"] == "9999999"].iloc[0]
        assert new_row["Descrição"] == "PRODUTO NOVO"
        assert new_row["Grupo"] == "1013 - Pascoa"
        assert new_row["Estoque"] == 30
        assert new_row["Total"] == 30
        assert pd.isna(new_row["Pedido"]) or new_row["Pedido"] is None
        assert new_row["Cód. Loja"] == "6835"


class TestMazzaIntegration:
    """Tests for Mazza report integration."""

    def test_mazza_adds_to_existing_saidas(
        self,
        comparison_service: ComparisonService,
        sample_transformed_excel: BytesIO,
        sample_inventory_excel_1225: BytesIO,
        sample_mazza_excel: BytesIO,
    ):
        """Test that matching products get QUANTIDADE added to Saídas."""
        result, store_name = comparison_service.compare(
            weekly_report=sample_transformed_excel,
            inventory_report=sample_inventory_excel_1225,
            mazza_report=sample_mazza_excel,
        )

        assert store_name == "LOJA STORE 1225"
        result_df = pd.read_excel(result, sheet_name="Faturamento por Produtos")
        result_df["Código do Produto"] = result_df["Código do Produto"].astype(str)

        # Product 1234567: original Saídas=20, Mazza QUANTIDADE=50 -> 70
        row = result_df[result_df["Código do Produto"] == "1234567"].iloc[0]
        assert row["Saídas"] == 70  # 20 + 50

    def test_mazza_adds_new_products(
        self,
        comparison_service: ComparisonService,
        sample_transformed_excel: BytesIO,
        sample_inventory_excel_1225: BytesIO,
        sample_mazza_excel: BytesIO,
    ):
        """Test that non-matching products are added with NULL columns."""
        result, _ = comparison_service.compare(
            weekly_report=sample_transformed_excel,
            inventory_report=sample_inventory_excel_1225,
            mazza_report=sample_mazza_excel,
        )

        result_df = pd.read_excel(result, sheet_name="Faturamento por Produtos")
        result_df["Código do Produto"] = result_df["Código do Produto"].astype(str)

        # Product 9999999 is only in Mazza, should be added
        assert "9999999" in result_df["Código do Produto"].values

        row = result_df[result_df["Código do Produto"] == "9999999"].iloc[0]
        assert str(row["Cód. Loja"]) == "1225"
        assert row["Descrição"] == "PRODUTO NOVO MAZZA"
        assert row["Saídas"] == 100
        assert pd.isna(row["Grupo"])
        assert pd.isna(row["Estoque"])
        assert pd.isna(row["Pedido"])
        assert pd.isna(row["Total"])
        assert pd.isna(row["Sugestão"])

    def test_mazza_ignored_for_non_1225_store(
        self,
        comparison_service: ComparisonService,
        sample_transformed_excel: BytesIO,
        sample_inventory_excel: BytesIO,
        sample_mazza_excel: BytesIO,
    ):
        """Test that Mazza data is ignored for stores other than 1225."""
        result, _ = comparison_service.compare(
            weekly_report=sample_transformed_excel,
            inventory_report=sample_inventory_excel,  # Store 6835, not 1225
            mazza_report=sample_mazza_excel,
        )

        result_df = pd.read_excel(result, sheet_name="Faturamento por Produtos")
        result_df["Código do Produto"] = result_df["Código do Produto"].astype(str)

        # Product 1234567: original Saídas=20, should NOT have Mazza added
        row = result_df[result_df["Código do Produto"] == "1234567"].iloc[0]
        assert row["Saídas"] == 20  # Unchanged

        # Product 9999999 from Mazza should NOT be added
        assert "9999999" not in result_df["Código do Produto"].values

    def test_mazza_report_none_is_ignored(
        self,
        comparison_service: ComparisonService,
        sample_transformed_excel: BytesIO,
        sample_inventory_excel_1225: BytesIO,
    ):
        """Test that None mazza_report doesn't break processing."""
        result, _ = comparison_service.compare(
            weekly_report=sample_transformed_excel,
            inventory_report=sample_inventory_excel_1225,
            mazza_report=None,
        )

        result_df = pd.read_excel(result, sheet_name="Faturamento por Produtos")
        result_df["Código do Produto"] = result_df["Código do Produto"].astype(str)

        # Product 1234567: original Saídas=20, should be unchanged
        row = result_df[result_df["Código do Produto"] == "1234567"].iloc[0]
        assert row["Saídas"] == 20  # Unchanged

    def test_read_mazza_report(
        self, comparison_service: ComparisonService, sample_mazza_excel: BytesIO
    ):
        """Test that Mazza report is read correctly."""
        df = comparison_service._read_mazza_report(sample_mazza_excel)

        assert list(df.columns) == ["CODIGO", "NOME PRODUTO", "QUANTIDADE"]
        assert len(df) == 2
        assert df["CODIGO"].dtype == object  # string

    def test_merge_mazza_report_adds_quantity(self, comparison_service: ComparisonService):
        """Test _merge_mazza_report adds QUANTIDADE to existing Saídas."""
        result_df = pd.DataFrame(
            {
                "Cód. Loja": ["1225"],
                "Código do Produto": ["1234567"],
                "Descrição": ["PRODUTO A"],
                "Grupo": ["1010 - Outros"],
                "Estoque": [100],
                "Pedido": [10],
                "Total": [110],
                "Saídas": [20],
                "Sugestão": [None],
            }
        )

        mazza_df = pd.DataFrame(
            {
                "CODIGO": ["1234567"],
                "NOME PRODUTO": ["PRODUTO A"],
                "QUANTIDADE": [50],
            }
        )

        merged = comparison_service._merge_mazza_report(result_df, mazza_df, "1225")

        row = merged[merged["Código do Produto"] == "1234567"].iloc[0]
        assert row["Saídas"] == 70  # 20 + 50

    def test_merge_mazza_report_handles_nan_saidas(self, comparison_service: ComparisonService):
        """Test _merge_mazza_report handles NaN Saídas correctly."""
        result_df = pd.DataFrame(
            {
                "Cód. Loja": ["1225"],
                "Código do Produto": ["1234567"],
                "Descrição": ["PRODUTO A"],
                "Grupo": ["1010 - Outros"],
                "Estoque": [100],
                "Pedido": [10],
                "Total": [110],
                "Saídas": [None],  # NaN value
                "Sugestão": [None],
            }
        )

        mazza_df = pd.DataFrame(
            {
                "CODIGO": ["1234567"],
                "NOME PRODUTO": ["PRODUTO A"],
                "QUANTIDADE": [50],
            }
        )

        merged = comparison_service._merge_mazza_report(result_df, mazza_df, "1225")

        row = merged[merged["Código do Produto"] == "1234567"].iloc[0]
        assert row["Saídas"] == 50  # 0 + 50
