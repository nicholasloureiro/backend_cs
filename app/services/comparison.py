"""Comparison service for inventory reports."""

from io import BytesIO

import pandas as pd


class ComparisonService:
    """Service for comparing weekly reports with inventory data."""

    def _read_inventory(self, inventory_content: BytesIO) -> pd.DataFrame:
        """Read the inventory Excel file and return a cleaned DataFrame."""
        df = pd.read_excel(inventory_content, sheet_name="Estoque Produtos com Valor")

        # First row contains actual column headers
        df_clean = df.iloc[1:].copy()
        df_clean.columns = df.iloc[0].values

        # Select columns we need
        cols_to_keep = [
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
        df_clean = df_clean[cols_to_keep].copy()

        # Convert types
        df_clean["Cód Produto"] = df_clean["Cód Produto"].astype(str)
        df_clean["Quantidade"] = pd.to_numeric(
            df_clean["Quantidade"], errors="coerce"
        ).fillna(0)

        return df_clean

    def _read_weekly_report(self, weekly_content: BytesIO) -> pd.DataFrame:
        """Read the weekly report Excel file."""
        df = pd.read_excel(weekly_content, sheet_name="Faturamento por Produtos")

        # Convert product code to string for matching
        df["Código do Produto"] = df["Código do Produto"].astype(str)

        return df

    def _compare_and_merge(
        self, weekly_df: pd.DataFrame, inventory_df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Compare inventory against weekly report and merge data.

        - If product exists in both: update Estoque with Quantidade if different
        - If product only in inventory: add to output with Quantidade as Estoque
        - If product only in weekly: set Estoque to 0
        """
        result_df = weekly_df.copy()

        # Get store code from inventory (applies to ALL products since inventory is per-store)
        store_code = inventory_df["Cód. Loja"].iloc[0] if len(inventory_df) > 0 else None

        # Create inventory lookup dicts
        inventory_lookup = dict(
            zip(inventory_df["Cód Produto"], inventory_df["Quantidade"])
        )
        inventory_cod_grupo = dict(
            zip(inventory_df["Cód Produto"], inventory_df["Cod Grupo"])
        )
        inventory_desc_grupo = dict(
            zip(inventory_df["Cód Produto"], inventory_df["Desc GRUPO"])
        )
        inventory_desc_produto = dict(
            zip(inventory_df["Cód Produto"], inventory_df["Desc Produto"])
        )

        # Get existing product codes in weekly report
        existing_codes = set(result_df["Código do Produto"].tolist())

        # Update existing products
        for idx, row in result_df.iterrows():
            product_code = str(row["Código do Produto"])
            if product_code in inventory_lookup:
                inv_qty = inventory_lookup[product_code]
                current_estoque = row["Estoque"]

                if current_estoque != inv_qty:
                    result_df.at[idx, "Estoque"] = inv_qty
                    pedido = row["Pedido"] if pd.notna(row["Pedido"]) else 0
                    result_df.at[idx, "Total"] = inv_qty + pedido

                # Enrich products with empty Grupo (PDF-sourced products)
                current_grupo = row["Grupo"]
                if pd.isna(current_grupo) or current_grupo == "":
                    cod_grupo = inventory_cod_grupo.get(product_code, "")
                    desc_grupo = inventory_desc_grupo.get(product_code, "")
                    if cod_grupo or desc_grupo:
                        result_df.at[idx, "Grupo"] = f"{cod_grupo} - {desc_grupo}".strip(" -")
                    result_df.at[idx, "Descrição"] = inventory_desc_produto.get(product_code, row["Descrição"])
            else:
                # Product exists in weekly but not in inventory -> set Estoque to 0
                if row["Estoque"] != 0:
                    result_df.at[idx, "Estoque"] = 0
                    pedido = row["Pedido"] if pd.notna(row["Pedido"]) else 0
                    result_df.at[idx, "Total"] = pedido

        # Set Cód. Loja for ALL products (store code from inventory applies to all)
        result_df["Cód. Loja"] = store_code

        # Find products in inventory but not in weekly report
        inventory_codes = set(inventory_df["Cód Produto"].tolist())
        new_codes = inventory_codes - existing_codes

        if new_codes:
            new_rows = []
            for _, inv_row in inventory_df[
                inventory_df["Cód Produto"].isin(new_codes)
            ].iterrows():
                new_rows.append(
                    {
                        "Código do Produto": inv_row["Cód Produto"],
                        "Descrição": inv_row["Desc Produto"],
                        "Grupo": f"{inv_row['Cod Grupo']} - {inv_row['Desc GRUPO']}".strip(
                            " -"
                        ),
                        "Estoque": inv_row["Quantidade"],
                        "Pedido": None,
                        "Total": inv_row["Quantidade"],
                        "Saídas": 0,
                        "Sugestão": None,
                        "Cód. Loja": inv_row["Cód. Loja"],
                    }
                )

            if new_rows:
                df_new = pd.DataFrame(new_rows)
                result_df = pd.concat([result_df, df_new], ignore_index=True)

        return result_df

    def _apply_sorting(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Apply custom sorting: 1014-Funcionais first, 1013-Pascoa last,
        middle sorted by Descrição ASC.
        """

        def grupo_priority(grupo):
            if pd.isna(grupo) or grupo == "":
                return 1  # Middle
            grupo_str = str(grupo)
            if "1014" in grupo_str and "Funcionais" in grupo_str:
                return 0  # First
            if "1013" in grupo_str and "Pascoa" in grupo_str:
                return 2  # Last
            return 1  # Middle

        df_output = df.copy()
        df_output["_priority"] = df_output["Grupo"].apply(grupo_priority)
        df_output = df_output.sort_values(["_priority", "Descrição"])
        df_output = df_output.drop(columns=["_priority"])

        return df_output

    def _read_mazza_report(self, mazza_content: BytesIO) -> pd.DataFrame:
        """Read the Mazza report Excel file."""
        df = pd.read_excel(mazza_content, sheet_name="RankingFaturamento")
        df["CODIGO"] = df["CODIGO"].astype(str)
        return df[["CODIGO", "NOME PRODUTO", "QUANTIDADE"]]

    def _merge_mazza_report(
        self, result_df: pd.DataFrame, mazza_df: pd.DataFrame, store_code: str
    ) -> pd.DataFrame:
        """Merge Mazza report data into the result (only for store 1225)."""
        # Initialize new columns
        result_df["Saídas VD"] = None
        result_df["Saídas Total"] = None

        # Create lookup for existing products
        existing_codes = set(result_df["Código do Produto"].astype(str).tolist())

        for _, mazza_row in mazza_df.iterrows():
            codigo = str(mazza_row["CODIGO"])
            quantidade = mazza_row["QUANTIDADE"]

            if codigo in existing_codes:
                # Match: Set Saídas VD and calculate Saídas Total
                mask = result_df["Código do Produto"].astype(str) == codigo
                current_saidas = result_df.loc[mask, "Saídas"].iloc[0]
                current_saidas = current_saidas if pd.notna(current_saidas) else 0
                current_saidas_vd = result_df.loc[mask, "Saídas VD"].iloc[0]
                current_saidas_vd = current_saidas_vd if pd.notna(current_saidas_vd) else 0

                result_df.loc[mask, "Saídas VD"] = current_saidas_vd + quantidade
                result_df.loc[mask, "Saídas Total"] = current_saidas + current_saidas_vd + quantidade
            else:
                # No match: Add new row
                new_row = {
                    "Cód. Loja": store_code,
                    "Código do Produto": codigo,
                    "Descrição": mazza_row["NOME PRODUTO"],
                    "Grupo": None,
                    "Estoque": None,
                    "Pedido": None,
                    "Total": None,
                    "Saídas": None,
                    "Saídas VD": quantidade,
                    "Saídas Total": quantidade,
                    "Sugestão": None,
                }
                result_df = pd.concat(
                    [result_df, pd.DataFrame([new_row])], ignore_index=True
                )
                existing_codes.add(codigo)

        # Reorder columns: ensure Saídas VD and Saídas Total come after Saídas, before Sugestão
        cols = result_df.columns.tolist()
        if "Sugestão" in cols and "Saídas" in cols:
            cols.remove("Saídas VD")
            cols.remove("Saídas Total")
            sugestao_idx = cols.index("Sugestão")
            cols.insert(sugestao_idx, "Saídas Total")
            cols.insert(sugestao_idx, "Saídas VD")
            result_df = result_df[cols]

        return result_df

    def compare(
        self,
        weekly_report: BytesIO,
        inventory_report: BytesIO,
        mazza_report: BytesIO = None,
    ) -> tuple[BytesIO, str, str]:
        """
        Compare weekly report with inventory and produce final report.

        Args:
            weekly_report: Transformed weekly report Excel content
            inventory_report: Inventory Excel file content
            mazza_report: Optional Mazza report Excel content (only for store 1225)

        Returns:
            Tuple of (BytesIO containing the compared Excel file, store_code, store_name)
        """
        # Read both files
        inventory_df = self._read_inventory(inventory_report)
        weekly_df = self._read_weekly_report(weekly_report)

        # Extract store name from inventory
        store_name = str(inventory_df["Loja"].iloc[0]) if len(inventory_df) > 0 else "Unknown"

        # Compare and merge
        result_df = self._compare_and_merge(weekly_df, inventory_df)

        # Get store code for Mazza check
        store_code = str(inventory_df["Cód. Loja"].iloc[0]) if len(inventory_df) > 0 else None

        # Apply custom sorting
        df_output = self._apply_sorting(result_df)

        # Merge Mazza report if provided and store is 1225
        if mazza_report is not None and store_code == "1225":
            mazza_df = self._read_mazza_report(mazza_report)
            df_output = self._merge_mazza_report(df_output, mazza_df, store_code)

        # Reorder columns so Cód. Loja is first
        cols = df_output.columns.tolist()
        if "Cód. Loja" in cols:
            cols.remove("Cód. Loja")
            cols = ["Cód. Loja"] + cols
            df_output = df_output[cols]

        # Write to BytesIO
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df_output.to_excel(
                writer, sheet_name="Faturamento por Produtos", index=False
            )

        output.seek(0)
        return output, store_code, store_name
