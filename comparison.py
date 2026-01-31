"""
Cacau Show - Inventory Comparison Script

This script compares inventory data against the weekly report:
1. Matches products by Cód Produto (inventory) vs Código do Produto (weekly)
2. If match: updates Estoque with Quantidade if different
3. If no match: adds new product from inventory to output

Usage:
    python comparison.py
"""

import pandas as pd
from pathlib import Path


# Configuration
BASE_DIR = Path(__file__).parent
INVENTORY_EXCEL = BASE_DIR / "/home/nicholas10/cacaushow/relatorio_inv_nao_tratado/Inv URA 26-01.xlsx"
WEEKLY_REPORT = BASE_DIR / "relatorios_tratados/Relatorio_GAC_Semanal_Output.xlsx"
OUTPUT_DIR = BASE_DIR / "relatorio_tratado_comparado"
OUTPUT_EXCEL = OUTPUT_DIR / "Relatorio_Comparado_Output.xlsx"


def read_inventory(excel_path: str) -> pd.DataFrame:
    """
    Read the inventory Excel file and return a cleaned DataFrame.
    """
    df = pd.read_excel(excel_path, sheet_name='Estoque Produtos com Valor')

    # First row contains actual column headers
    df_clean = df.iloc[1:].copy()
    df_clean.columns = df.iloc[0].values

    # Select and rename columns we need
    cols_to_keep = ['Cód Produto', 'Desc Produto', 'Cod Grupo', 'Desc GRUPO', 'Quantidade',
                    'R$ CUSTO UN', 'R$ CUSTO TOTAL ITEM', 'R$ VENDA UN', 'R$ VENDA TOTAL ITEM']
    df_clean = df_clean[cols_to_keep].copy()

    # Convert types
    df_clean['Cód Produto'] = df_clean['Cód Produto'].astype(str)
    df_clean['Quantidade'] = pd.to_numeric(df_clean['Quantidade'], errors='coerce').fillna(0)

    return df_clean


def read_weekly_report(excel_path: str) -> pd.DataFrame:
    """
    Read the weekly report Excel file.
    """
    df = pd.read_excel(excel_path, sheet_name='Faturamento por Produtos')

    # Convert product code to string for matching
    df['Código do Produto'] = df['Código do Produto'].astype(str)

    return df


def compare_and_merge(weekly_df: pd.DataFrame, inventory_df: pd.DataFrame) -> pd.DataFrame:
    """
    Compare inventory against weekly report and merge data.

    - If product exists in both: update Estoque with Quantidade if different
    - If product only in inventory: add to output with Quantidade as Estoque
    """
    # Create a copy to avoid modifying original
    result_df = weekly_df.copy()

    # Create inventory lookup dict: {product_code: quantidade}
    inventory_lookup = dict(zip(inventory_df['Cód Produto'], inventory_df['Quantidade']))

    # Track statistics
    matches = 0
    updates = 0
    new_products = 0
    zeroed = 0

    # Get existing product codes in weekly report
    existing_codes = set(result_df['Código do Produto'].tolist())

    # Update existing products
    for idx, row in result_df.iterrows():
        product_code = str(row['Código do Produto'])
        if product_code in inventory_lookup:
            matches += 1
            inv_qty = inventory_lookup[product_code]
            current_estoque = row['Estoque']

            if current_estoque != inv_qty:
                result_df.at[idx, 'Estoque'] = inv_qty
                # Recalculate Total
                pedido = row['Pedido'] if pd.notna(row['Pedido']) else 0
                result_df.at[idx, 'Total'] = inv_qty + pedido
                updates += 1
        else:
            # Product exists in weekly but not in inventory -> set Estoque to 0
            if row['Estoque'] != 0:
                result_df.at[idx, 'Estoque'] = 0
                # Recalculate Total
                pedido = row['Pedido'] if pd.notna(row['Pedido']) else 0
                result_df.at[idx, 'Total'] = pedido
                zeroed += 1

    # Find products in inventory but not in weekly report
    inventory_codes = set(inventory_df['Cód Produto'].tolist())
    new_codes = inventory_codes - existing_codes

    if new_codes:
        new_rows = []
        for _, inv_row in inventory_df[inventory_df['Cód Produto'].isin(new_codes)].iterrows():
            new_rows.append({
                'Código do Produto': inv_row['Cód Produto'],
                'Descrição': inv_row['Desc Produto'],
                'Grupo': f"{inv_row['Cod Grupo']} - {inv_row['Desc GRUPO']}".strip(' -'),
                'Estoque': inv_row['Quantidade'],
                'Pedido': None,
                'Total': inv_row['Quantidade'],
                'Saídas': 0,
                'Sugestão': None
            })
            new_products += 1

        if new_rows:
            df_new = pd.DataFrame(new_rows)
            result_df = pd.concat([result_df, df_new], ignore_index=True)

    print(f"   Products matched: {matches}")
    print(f"   Estoque values updated: {updates}")
    print(f"   Estoque set to 0 (not in inventory): {zeroed}")
    print(f"   New products added: {new_products}")

    return result_df


def create_output(df: pd.DataFrame, output_path: str):
    """
    Write the final comparison output to Excel.
    Sorted by Grupo (1014 - Funcionais first, 1013 - Pascoa last), then by Descrição.
    """
    # Custom sort: 1014-Funcionais first, 1013-Pascoa last, middle sorted by Descrição ASC
    def grupo_priority(grupo):
        if pd.isna(grupo) or grupo == '':
            return 1  # Middle
        grupo_str = str(grupo)
        if '1014' in grupo_str and 'Funcionais' in grupo_str:
            return 0  # First
        if '1013' in grupo_str and 'Pascoa' in grupo_str:
            return 2  # Last
        return 1  # Middle

    df_output = df.copy()
    df_output['_priority'] = df_output['Grupo'].apply(grupo_priority)
    df_output = df_output.sort_values(['_priority', 'Descrição'])
    df_output = df_output.drop(columns=['_priority'])

    # Write to Excel
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        df_output.to_excel(writer, sheet_name='Faturamento por Produtos', index=False)

    print(f"\nOutput saved to: {output_path}")
    return df_output


def main():
    print("=" * 60)
    print("Cacau Show - Inventory Comparison")
    print("=" * 60)

    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Step 1: Read inventory
    print("\n1. Reading inventory report...")
    inventory_df = read_inventory(str(INVENTORY_EXCEL))
    print(f"   Loaded {len(inventory_df)} products from inventory")

    # Step 2: Read weekly report
    print("\n2. Reading weekly report...")
    weekly_df = read_weekly_report(str(WEEKLY_REPORT))
    print(f"   Loaded {len(weekly_df)} products from weekly report")

    # Step 3: Compare and merge
    print("\n3. Comparing and merging...")
    result_df = compare_and_merge(weekly_df, inventory_df)

    # Step 4: Create output
    print("\n4. Creating output report...")
    df_output = create_output(result_df, str(OUTPUT_EXCEL))

    # Summary
    print("\n" + "=" * 60)
    print("Summary:")
    print(f"  Total products in output: {len(df_output)}")
    print(f"  Total Estoque: {df_output['Estoque'].sum():,.0f}")
    print(f"  Total Pedido: {df_output['Pedido'].sum():,.0f}")
    print(f"  Total (Estoque + Pedido): {df_output['Total'].sum():,.0f}")
    print("=" * 60)


if __name__ == "__main__":
    main()
