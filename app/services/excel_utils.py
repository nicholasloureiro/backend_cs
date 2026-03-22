"""Utility functions for Excel file processing."""

from io import BytesIO

import pandas as pd


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
