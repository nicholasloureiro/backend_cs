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


def find_columns(df: pd.DataFrame, expected_names: list[str]) -> dict[str, str]:
    """Map expected column names to actual column names in a DataFrame.

    Returns a dict mapping expected_name -> actual_column_name.
    """
    columns = list(df.columns)
    return {name: find_column(columns, name) for name in expected_names}


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

    # Fallback: single sheet in workbook
    if len(sheet_names) == 1:
        return sheet_names[0]

    raise ValueError(
        f"Planilha '{expected_name}' não encontrada. "
        f"Planilhas disponíveis: {sheet_names}"
    )
