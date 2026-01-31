"""
Cacau Show - Weekly Report Transformation Script

This script:
1. Reads the source Excel file (Relatório semanal Centro)
2. Extracts pending orders from NF PDFs and pedidos PDFs
3. Calculates totals and generates the final report

Usage:
    python transformations.py
"""

import pandas as pd
import fitz  # PyMuPDF
import re
import os
from pathlib import Path


# Configuration
BASE_DIR = Path(__file__).parent
SOURCE_EXCEL = BASE_DIR / "/home/nicholas10/cacaushow/relatorio_nao_tratado/Relatorio Semanal URA - 26-01-2026.xlsx"
NF_PDF_DIR = BASE_DIR / "pdfs" / "NF"
PEDIDOS_PDF_DIR = BASE_DIR / "pdfs" / "pedidos"
OUTPUT_EXCEL = BASE_DIR / "relatorios_tratados/Relatorio_GAC_Semanal_Output.xlsx"


def extract_units_from_description(description: str) -> int:
    """
    Extract the number of units per package from a product description.

    Patterns:
    - "X 15" at the end (NF format) -> 15
    - "100GX15UN" -> 15
    - "100GX15U" -> 15
    - "1KGX5UN" -> 5
    """
    if not description:
        return 1

    desc_upper = description.upper()

    # Pattern 1: " X {number}" at the end (NF PDFs)
    match = re.search(r'\s+X\s+(\d+)\s*$', desc_upper)
    if match:
        return int(match.group(1))

    # Pattern 2: "{weight}GX{units}UN" or "{weight}KGX{units}UN" or "{weight}GX{units}U"
    match = re.search(r'\d+(?:G|KG)X(\d+)U(?:N)?', desc_upper)
    if match:
        return int(match.group(1))

    # Pattern 3: "X{units}UN" without weight prefix
    match = re.search(r'X(\d+)UN', desc_upper)
    if match:
        return int(match.group(1))

    return 1


def extract_product_code(text: str) -> str:
    """Extract product code (7 digit number starting with 1 or 2)."""
    match = re.search(r'\b([12]\d{6})\b', text)
    return match.group(1) if match else None


def normalize_description(description: str) -> str:
    """
    Normalize product description from PDF format to Excel format.

    Example: "TABLETE LACREME BRANCO ZA 100GX15UN X 15" -> "TAB 100 LACREME BRANCO ZA"
    """
    if not description:
        return ""

    # Remove the trailing " X {number}" part
    desc = re.sub(r'\s+X\s+\d+\s*$', '', description)

    # Remove the unit info like "100GX15UN" or "13,5GX150UN"
    desc = re.sub(r'\s*\d+(?:,\d+)?(?:G|KG)X\d+U(?:N)?\s*', ' ', desc)

    # Clean up extra spaces
    desc = ' '.join(desc.split())

    return desc


def parse_nf_pdf(pdf_path: str) -> tuple:
    """
    Parse NF (Nota Fiscal) PDF and extract product quantities.
    Column CÓD. PRODUTO contains the product code.

    Returns a tuple: (quantities_dict, descriptions_dict)
        - quantities_dict: {product_code: total_units}
        - descriptions_dict: {product_code: description}
    """
    quantities = {}
    descriptions = {}

    try:
        pdf = fitz.open(pdf_path)
        full_text = ""
        for page in pdf:
            full_text += page.get_text()
        pdf.close()

        # Find the data table section - look for lines with product codes
        lines = full_text.split('\n')

        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # Check if this line starts with a product code (7 digits starting with 1 or 2)
            code_match = re.match(r'^([12]\d{6})$', line)
            if code_match:
                product_code = code_match.group(1)

                # Next line should be the description
                if i + 1 < len(lines):
                    description = lines[i + 1].strip()

                    # Extract units from description
                    units_per_package = extract_units_from_description(description)

                    # Look for quantity in nearby lines (usually a few lines after)
                    # The QTDE value appears after NCM/SH, CST, CFOP, UND
                    # Typically as a decimal like "2,000" or "2.000"
                    qty = 0
                    for j in range(i + 2, min(i + 10, len(lines))):
                        qty_line = lines[j].strip()
                        # Look for quantity pattern (decimal number)
                        qty_match = re.match(r'^(\d+)[,.]0{3}$', qty_line)
                        if qty_match:
                            qty = int(qty_match.group(1))
                            break

                    if qty > 0:
                        total_units = qty * units_per_package
                        if product_code in quantities:
                            quantities[product_code] += total_units
                        else:
                            quantities[product_code] = total_units
                            # Store normalized description (only first occurrence)
                            descriptions[product_code] = normalize_description(description)

            i += 1

    except Exception as e:
        print(f"Error parsing NF PDF {pdf_path}: {e}")

    return quantities, descriptions


def parse_pedido_pdf(pdf_path: str) -> tuple:
    """
    Parse pedido (order) PDF and extract product quantities.
    Column MATERIAL contains the product code.

    Returns a tuple: (quantities_dict, descriptions_dict)
        - quantities_dict: {product_code: total_units}
        - descriptions_dict: {product_code: description}
    """
    quantities = {}
    descriptions = {}

    try:
        pdf = fitz.open(pdf_path)
        full_text = ""
        for page in pdf:
            full_text += page.get_text()
        pdf.close()

        lines = full_text.split('\n')

        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # In pedidos PDFs, the format is:
            # ITEM (10, 20, 30...)
            # MATERIAL (product code)
            # DENOMINACAO (description)
            # QUANTIDADE (quantity with decimals)

            # Check if this is an ITEM number (10, 20, 30, etc.)
            if re.match(r'^\d{2,3}$', line) and int(line) % 10 == 0:
                # Next should be product code (MATERIAL column)
                if i + 1 < len(lines):
                    code_line = lines[i + 1].strip()
                    code_match = re.match(r'^([12]\d{6})$', code_line)

                    if code_match:
                        product_code = code_match.group(1)

                        # Next is description (DENOMINACAO column)
                        if i + 2 < len(lines):
                            description = lines[i + 2].strip()
                            units_per_package = extract_units_from_description(description)

                            # Look for quantity (format: "1,000" or "3,000")
                            qty = 0
                            for j in range(i + 3, min(i + 8, len(lines))):
                                qty_line = lines[j].strip()
                                qty_match = re.match(r'^(\d+)[,.]0{3}\s*$', qty_line)
                                if qty_match:
                                    qty = int(qty_match.group(1))
                                    break

                            if qty > 0:
                                total_units = qty * units_per_package
                                if product_code in quantities:
                                    quantities[product_code] += total_units
                                else:
                                    quantities[product_code] = total_units
                                    # Store normalized description (only first occurrence)
                                    descriptions[product_code] = normalize_description(description)

            i += 1

    except Exception as e:
        print(f"Error parsing pedido PDF {pdf_path}: {e}")

    return quantities, descriptions


def read_source_excel(excel_path: str) -> pd.DataFrame:
    """
    Read the source Excel file and return a cleaned DataFrame.
    """
    df = pd.read_excel(excel_path, sheet_name='Faturamento por Produtos')

    # The first row contains actual column headers
    df_clean = df.iloc[1:].copy()
    df_clean.columns = df.iloc[0].values

    # Select required columns
    cols = ['Código do Produto', 'Descrição', 'Grupo', 'Estoque', 'Quantidade Líquida']
    df_clean = df_clean[cols].copy()

    # Convert numeric columns
    df_clean['Código do Produto'] = df_clean['Código do Produto'].astype(str)
    df_clean['Estoque'] = pd.to_numeric(df_clean['Estoque'], errors='coerce').fillna(0)
    df_clean['Quantidade Líquida'] = pd.to_numeric(df_clean['Quantidade Líquida'], errors='coerce').fillna(0)

    # Filter out totals row
    df_clean = df_clean[~df_clean['Descrição'].str.contains('Totais', case=False, na=False)]

    return df_clean


def process_all_pdfs() -> tuple:
    """
    Process all PDFs in NF and pedidos directories.

    Returns a tuple: (quantities_dict, descriptions_dict)
        - quantities_dict: {product_code: total_pending_units}
        - descriptions_dict: {product_code: description}
    """
    all_quantities = {}
    all_descriptions = {}

    # Process NF PDFs (CÓD. PRODUTO column)
    if NF_PDF_DIR.exists():
        for pdf_file in NF_PDF_DIR.glob("*.pdf"):
            print(f"Processing NF: {pdf_file.name}")
            quantities, descriptions = parse_nf_pdf(str(pdf_file))
            for code, qty in quantities.items():
                if code in all_quantities:
                    all_quantities[code] += qty
                else:
                    all_quantities[code] = qty
                # Store description if not already present
                if code not in all_descriptions and code in descriptions:
                    all_descriptions[code] = descriptions[code]
            print(f"  Found {len(quantities)} products")

    # Process pedidos PDFs (MATERIAL column)
    if PEDIDOS_PDF_DIR.exists():
        for pdf_file in PEDIDOS_PDF_DIR.glob("*.pdf"):
            print(f"Processing pedido: {pdf_file.name}")
            quantities, descriptions = parse_pedido_pdf(str(pdf_file))
            for code, qty in quantities.items():
                if code in all_quantities:
                    all_quantities[code] += qty
                else:
                    all_quantities[code] = qty
                # Store description if not already present
                if code not in all_descriptions and code in descriptions:
                    all_descriptions[code] = descriptions[code]
            print(f"  Found {len(quantities)} products")

    return all_quantities, all_descriptions


def create_final_report(df: pd.DataFrame, pending_quantities: dict, pending_descriptions: dict, output_path: str):
    """
    Create the final Excel report with all calculated fields.
    Adds products from PDFs that don't exist in the source Excel.
    """
    # Get existing product codes from Excel
    existing_codes = set(df['Código do Produto'].tolist())

    # Find new products from PDFs (not in Excel)
    new_codes = set(pending_quantities.keys()) - existing_codes

    if new_codes:
        print(f"   Adding {len(new_codes)} new products from PDFs...")
        # Create rows for new products
        new_rows = []
        for code in new_codes:
            new_rows.append({
                'Código do Produto': code,
                'Descrição': pending_descriptions.get(code, f'Produto {code}'),
                'Grupo': '',  # No group info from PDFs
                'Estoque': 0,
                'Quantidade Líquida': 0
            })
        df_new = pd.DataFrame(new_rows)
        df = pd.concat([df, df_new], ignore_index=True)

    # Add pending orders column (keep NaN for products without pending orders)
    df['Pedido'] = df['Código do Produto'].map(pending_quantities)

    # Calculate Total = Estoque + Pedido (treat NaN as 0 for calculation)
    df['Total'] = df['Estoque'].fillna(0) + df['Pedido'].fillna(0)
    df['Sugestão'] = None

    # Rename columns to match expected output
    df_output = df[['Código do Produto', 'Descrição', 'Grupo', 'Estoque', 'Pedido', 'Total', 'Quantidade Líquida','Sugestão']].copy()
    df_output.columns = ['Código do Produto', 'Descrição', 'Grupo', 'Estoque', 'Pedido', 'Total', 'Saídas','Sugestão']

    # Sort by Descrição ascending
    df_output = df_output.sort_values('Descrição')

    # Write to Excel
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        df_output.to_excel(writer, sheet_name='Faturamento por Produtos', index=False)

    print(f"\nOutput saved to: {output_path}")
    return df_output


def main():
    print("=" * 60)
    print("Cacau Show - Weekly Report Transformation")
    print("=" * 60)

    # Step 1: Read source Excel
    print("\n1. Reading source Excel...")
    df = read_source_excel(str(SOURCE_EXCEL))
    print(f"   Loaded {len(df)} products")

    # Step 2: Process all PDFs
    print("\n2. Processing PDFs...")
    pending_quantities, pending_descriptions = process_all_pdfs()
    print(f"   Total products with pending orders: {len(pending_quantities)}")

    # Step 3: Create final report
    print("\n3. Creating final report...")
    df_output = create_final_report(df, pending_quantities, pending_descriptions, str(OUTPUT_EXCEL))

    # Summary
    print("\n" + "=" * 60)
    print("Summary:")
    print(f"  Total products: {len(df_output)}")
    print(f"  Products with pending orders: {(df_output['Pedido'] > 0).sum()}")
    print(f"  Total Estoque: {df_output['Estoque'].sum():,.0f}")
    print(f"  Total Pedido: {df_output['Pedido'].sum():,.0f}")
    print(f"  Total (Estoque + Pedido): {df_output['Total'].sum():,.0f}")
    print("=" * 60)


if __name__ == "__main__":
    main()
