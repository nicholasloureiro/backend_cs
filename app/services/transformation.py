"""Transformation service for weekly reports."""

from io import BytesIO

import pandas as pd

from app.services.pdf_parser import PDFParserService


class TransformationService:
    """Service for transforming weekly reports with PDF data."""

    def __init__(self, pdf_parser: PDFParserService):
        self.pdf_parser = pdf_parser

    def _read_source_excel(self, excel_content: BytesIO) -> pd.DataFrame:
        """Read the source Excel file and return a cleaned DataFrame."""
        df = pd.read_excel(excel_content, sheet_name="Faturamento por Produtos")

        # The first row contains actual column headers
        df_clean = df.iloc[1:].copy()
        df_clean.columns = df.iloc[0].values

        # Select required columns
        cols = [
            "Código do Produto",
            "Descrição",
            "Grupo",
            "Estoque",
            "Quantidade Líquida",
        ]
        df_clean = df_clean[cols].copy()

        # Convert numeric columns
        df_clean["Código do Produto"] = df_clean["Código do Produto"].astype(str)
        df_clean["Estoque"] = pd.to_numeric(
            df_clean["Estoque"], errors="coerce"
        ).fillna(0)
        df_clean["Quantidade Líquida"] = pd.to_numeric(
            df_clean["Quantidade Líquida"], errors="coerce"
        ).fillna(0)

        # Filter out totals row
        df_clean = df_clean[
            ~df_clean["Descrição"].str.contains("Totais", case=False, na=False)
        ]

        return df_clean

    def _process_pdfs(
        self, nf_pdfs: list[bytes], pedido_pdfs: list[bytes]
    ) -> tuple[dict, dict]:
        """
        Process all PDFs and aggregate quantities.

        Returns a tuple: (quantities_dict, descriptions_dict)
        """
        all_quantities: dict[str, int] = {}
        all_descriptions: dict[str, str] = {}

        # Process NF PDFs
        for pdf_content in nf_pdfs:
            quantities, descriptions = self.pdf_parser.parse_nf_pdf(pdf_content)
            for code, qty in quantities.items():
                if code in all_quantities:
                    all_quantities[code] += qty
                else:
                    all_quantities[code] = qty
                if code not in all_descriptions and code in descriptions:
                    all_descriptions[code] = descriptions[code]

        # Process Pedido PDFs
        for pdf_content in pedido_pdfs:
            quantities, descriptions = self.pdf_parser.parse_pedido_pdf(pdf_content)
            for code, qty in quantities.items():
                if code in all_quantities:
                    all_quantities[code] += qty
                else:
                    all_quantities[code] = qty
                if code not in all_descriptions and code in descriptions:
                    all_descriptions[code] = descriptions[code]

        return all_quantities, all_descriptions

    def _create_final_report(
        self,
        df: pd.DataFrame,
        pending_quantities: dict,
        pending_descriptions: dict,
    ) -> pd.DataFrame:
        """Create the final report DataFrame with all calculated fields."""
        # Get existing product codes from Excel
        existing_codes = set(df["Código do Produto"].tolist())

        # Find new products from PDFs (not in Excel)
        new_codes = set(pending_quantities.keys()) - existing_codes

        if new_codes:
            # Create rows for new products
            new_rows = []
            for code in new_codes:
                new_rows.append(
                    {
                        "Código do Produto": code,
                        "Descrição": pending_descriptions.get(code, f"Produto {code}"),
                        "Grupo": "",
                        "Estoque": 0,
                        "Quantidade Líquida": 0,
                    }
                )
            df_new = pd.DataFrame(new_rows)
            df = pd.concat([df, df_new], ignore_index=True)

        # Add pending orders column
        df["Pedido"] = df["Código do Produto"].map(pending_quantities)

        # Calculate Total = Estoque + Pedido
        df["Total"] = df["Estoque"].fillna(0) + df["Pedido"].fillna(0)
        df["Sugestão"] = None

        # Rename columns to match expected output
        df_output = df[
            [
                "Código do Produto",
                "Descrição",
                "Grupo",
                "Estoque",
                "Pedido",
                "Total",
                "Quantidade Líquida",
                "Sugestão",
            ]
        ].copy()
        df_output.columns = [
            "Código do Produto",
            "Descrição",
            "Grupo",
            "Estoque",
            "Pedido",
            "Total",
            "Saídas",
            "Sugestão",
        ]

        # Sort by Descrição ascending
        df_output = df_output.sort_values("Descrição")

        return df_output

    def process(
        self,
        weekly_excel: BytesIO,
        nf_pdfs: list[bytes],
        pedido_pdfs: list[bytes],
    ) -> BytesIO:
        """
        Process the weekly report with PDF data.

        Args:
            weekly_excel: Weekly report Excel file content
            nf_pdfs: List of NF PDF file contents
            pedido_pdfs: List of Pedido PDF file contents

        Returns:
            BytesIO containing the transformed Excel file
        """
        # Read source Excel
        df = self._read_source_excel(weekly_excel)

        # Process all PDFs
        pending_quantities, pending_descriptions = self._process_pdfs(
            nf_pdfs, pedido_pdfs
        )

        # Create final report
        df_output = self._create_final_report(df, pending_quantities, pending_descriptions)

        # Write to BytesIO
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df_output.to_excel(writer, sheet_name="Faturamento por Produtos", index=False)

        output.seek(0)
        return output
