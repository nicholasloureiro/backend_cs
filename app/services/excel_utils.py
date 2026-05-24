"""Utility functions for Excel file processing."""

import unicodedata
from io import BytesIO

import pandas as pd


def _normalize(text: str) -> str:
    """Normalize text for fuzzy comparison: lowercase, strip accents/punctuation, collapse whitespace."""
    text = str(text).strip().lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    # Remove punctuation (dots, commas, etc.) to handle variants like "Cód. Produto" vs "Cód Produto"
    text = "".join(c for c in text if c.isalnum() or c.isspace())
    text = " ".join(text.split())
    return text


def find_column(columns: list, expected_name: str) -> str:
    """Find the best matching column name from a list, tolerating accent/case/whitespace differences.

    Returns the actual column name from the list.
    Raises KeyError if no match found.
    """
    # Exact match
    if expected_name in columns:
        return expected_name

    # Normalized match
    norm_expected = _normalize(expected_name)
    for col in columns:
        if _normalize(str(col)) == norm_expected:
            return col

    # Partial match: column contains expected or vice versa
    for col in columns:
        norm_col = _normalize(str(col))
        if norm_expected in norm_col or norm_col in norm_expected:
            return col

    raise KeyError(
        f"Coluna '{expected_name}' não encontrada. "
        f"Colunas disponíveis: {columns}"
    )


def has_column(columns: list, expected_name: str) -> bool:
    """Return True if a column matching expected_name exists (fuzzy match)."""
    try:
        find_column(columns, expected_name)
        return True
    except KeyError:
        return False


def find_columns(df: pd.DataFrame, expected_names: list[str]) -> dict[str, str]:
    """Map expected column names to actual column names in a DataFrame.

    Returns a dict mapping expected_name -> actual_column_name.
    """
    columns = list(df.columns)
    return {name: find_column(columns, name) for name in expected_names}


def normalize_product_code(series: pd.Series) -> pd.Series:
    """Convert product codes to clean strings without '.0' suffix.

    Handles numeric codes stored as floats (e.g., 1000024.0 -> '1000024').
    """
    return pd.to_numeric(series, errors="coerce").fillna(0).astype(int).astype(str)


# Column names that identify a real header row in a weekly report sheet.
_HEADER_MARKERS = (
    "Código do Produto",
    "Código",
    "Loja",
    "Produto",
    "Descrição",
    "Qtde vendida",
)


def _columns_are_header(columns: list) -> bool:
    """True if the given columns already look like a real header row.

    Uses normalized equality (not partial matching) so a title like
    "Faturamento produtos por Multloja" is not mistaken for a "Loja" header.
    """
    norm_cols = {_normalize(str(c)) for c in columns}
    return any(_normalize(m) in norm_cols for m in _HEADER_MARKERS)


def read_report_sheet(file_content: BytesIO, expected_sheet: str) -> pd.DataFrame:
    """Read a weekly report sheet, tolerating an optional leading title row.

    Some exports put a title in the first sheet row (so the real column names
    land on the second row); others put the column names on the first row.
    Returns a DataFrame whose columns are the real header.
    """
    sheet = find_sheet_name(file_content, expected_sheet)
    df = pd.read_excel(file_content, sheet_name=sheet)

    # When a title row precedes the header, pandas reads the title as the
    # column index, so the real header sits in the first data row.
    if _columns_are_header(df.columns):
        return df.copy()

    df_clean = df.iloc[1:].copy()
    df_clean.columns = df.iloc[0].values
    return df_clean


def find_sheet_name(file_content: BytesIO, expected_name: str) -> str:
    """Find the best matching sheet name, allowing for variants like '(2)' suffixes.

    Matching order:
    1. Exact match
    2. Sheet name starts with the expected name (single match only)
    3. Single sheet in workbook (fallback)
    4. Raises ValueError if no match found
    """
    file_content.seek(0)
    xl = pd.ExcelFile(file_content)
    sheet_names = xl.sheet_names
    file_content.seek(0)

    # Exact match
    if expected_name in sheet_names:
        return expected_name

    # Partial match: sheet starts with expected name
    matches = [s for s in sheet_names if s.strip().startswith(expected_name)]
    if len(matches) == 1:
        return matches[0]

    # Normalized match: compare without accents/punctuation
    norm_expected = _normalize(expected_name)
    for s in sheet_names:
        if _normalize(s) == norm_expected:
            return s

    # Word overlap match: find sheets sharing significant words
    expected_words = set(norm_expected.split())
    best_match = None
    best_overlap = 0
    for s in sheet_names:
        sheet_words = set(_normalize(s).split())
        overlap = len(expected_words & sheet_words)
        if overlap >= 2 and overlap > best_overlap:
            best_overlap = overlap
            best_match = s
    if best_match:
        return best_match

    # Fallback: single sheet in workbook
    if len(sheet_names) == 1:
        return sheet_names[0]

    raise ValueError(
        f"Planilha '{expected_name}' não encontrada. "
        f"Planilhas disponíveis: {sheet_names}"
    )
