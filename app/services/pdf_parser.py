"""PDF parsing service for NF and Pedido documents."""

import re
from io import BytesIO

import fitz  # PyMuPDF


class PDFParserService:
    """Service for parsing NF and Pedido PDF documents."""

    def extract_units_from_description(self, description: str) -> int:
        """
        Extract the number of units per package from a product description.

        Patterns (in priority order):
        - "100GX15UN" or "13,5GX150UN" -> 15, 150 (most explicit)
        - "X15UN" -> 15 (explicit UN suffix with X prefix)
        - "X 15" at the end (NF format) -> 15
        - "72UN" -> 72 (standalone UN suffix)
        """
        if not description:
            return 1

        desc_upper = description.upper()

        # Priority 1: "{weight}GX{units}UN" - most explicit unit indicator
        # Handles decimal weights like "13,5G" in "TRUFA LACREME GIANDUIA 13,5GX150UN"
        match = re.search(r"\d+(?:[,\.]\d+)?(?:G|KG)X(\d+)U(?:N)?", desc_upper)
        if match:
            return int(match.group(1))

        # Priority 2: "X{units}UN" without weight prefix
        match = re.search(r"X(\d+)UN", desc_upper)
        if match:
            return int(match.group(1))

        # Priority 3: " X {number}" at the end (fallback for NF PDFs without UN)
        match = re.search(r"\s+X\s+(\d+)\s*$", desc_upper)
        if match:
            return int(match.group(1))

        # Priority 4: "{number}UN" standalone (e.g., "72UN")
        match = re.search(r"(\d+)UN", desc_upper)
        if match:
            return int(match.group(1))

        return 1

    def normalize_description(self, description: str) -> str:
        """
        Normalize product description from PDF format to Excel format.

        Example: "TABLETE LACREME BRANCO ZA 100GX15UN X 15" -> "TAB 100 LACREME BRANCO ZA"
        """
        if not description:
            return ""

        # Remove the trailing " X {number}" part
        desc = re.sub(r"\s+X\s+\d+\s*$", "", description)

        # Remove the unit info like "100GX15UN" or "13,5GX150UN"
        desc = re.sub(r"\s*\d+(?:,\d+)?(?:G|KG)X\d+U(?:N)?\s*", " ", desc)

        # Clean up extra spaces
        desc = " ".join(desc.split())

        return desc

    def parse_nf_pdf(self, pdf_content: bytes) -> tuple[dict, dict]:
        """
        Parse NF (Nota Fiscal) PDF and extract product quantities.
        Column CÓD. PRODUTO contains the product code.

        Returns a tuple: (quantities_dict, descriptions_dict)
            - quantities_dict: {product_code: total_units}
            - descriptions_dict: {product_code: description}
        """
        quantities: dict[str, int] = {}
        descriptions: dict[str, str] = {}

        try:
            pdf = fitz.open(stream=pdf_content, filetype="pdf")
            full_text = ""
            for page in pdf:
                full_text += page.get_text()
            pdf.close()

            lines = full_text.split("\n")

            i = 0
            while i < len(lines):
                line = lines[i].strip()

                # Check if this line starts with a product code (7 digits starting with 1 or 2)
                code_match = re.match(r"^([12]\d{6})$", line)
                if code_match:
                    product_code = code_match.group(1)

                    # Next line should be the description
                    if i + 1 < len(lines):
                        description = lines[i + 1].strip()

                        # Extract units from description
                        units_per_package = self.extract_units_from_description(
                            description
                        )

                        # Look for quantity in nearby lines
                        qty = 0
                        for j in range(i + 2, min(i + 10, len(lines))):
                            qty_line = lines[j].strip()
                            qty_match = re.match(r"^(\d+)[,.]0{3}$", qty_line)
                            if qty_match:
                                qty = int(qty_match.group(1))
                                break

                        if qty > 0:
                            total_units = qty * units_per_package
                            if product_code in quantities:
                                quantities[product_code] += total_units
                            else:
                                quantities[product_code] = total_units
                                descriptions[product_code] = self.normalize_description(
                                    description
                                )

                i += 1

        except Exception:
            pass

        return quantities, descriptions

    def parse_pedido_pdf(self, pdf_content: bytes) -> tuple[dict, dict]:
        """
        Parse pedido (order) PDF and extract product quantities.
        Column MATERIAL contains the product code.

        Returns a tuple: (quantities_dict, descriptions_dict)
            - quantities_dict: {product_code: total_units}
            - descriptions_dict: {product_code: description}
        """
        quantities: dict[str, int] = {}
        descriptions: dict[str, str] = {}

        try:
            pdf = fitz.open(stream=pdf_content, filetype="pdf")
            full_text = ""
            for page in pdf:
                full_text += page.get_text()
            pdf.close()

            lines = full_text.split("\n")

            i = 0
            while i < len(lines):
                line = lines[i].strip()

                # In pedidos PDFs, the format is:
                # ITEM (10, 20, 30...)
                # MATERIAL (product code)
                # DENOMINACAO (description)
                # QUANTIDADE (quantity with decimals)

                # Check if this is an ITEM number (10, 20, 30, etc.)
                if re.match(r"^\d{2,3}$", line) and int(line) % 10 == 0:
                    # Next should be product code (MATERIAL column)
                    if i + 1 < len(lines):
                        code_line = lines[i + 1].strip()
                        code_match = re.match(r"^([12]\d{6})$", code_line)

                        if code_match:
                            product_code = code_match.group(1)

                            # Next is description (DENOMINACAO column)
                            if i + 2 < len(lines):
                                description = lines[i + 2].strip()
                                units_per_package = (
                                    self.extract_units_from_description(description)
                                )

                                # Look for quantity (format: "1,000" or "3,000")
                                qty = 0
                                for j in range(i + 3, min(i + 8, len(lines))):
                                    qty_line = lines[j].strip()
                                    qty_match = re.match(
                                        r"^(\d+)[,.]0{3}\s*$", qty_line
                                    )
                                    if qty_match:
                                        qty = int(qty_match.group(1))
                                        break

                                if qty > 0:
                                    total_units = qty * units_per_package
                                    if product_code in quantities:
                                        quantities[product_code] += total_units
                                    else:
                                        quantities[product_code] = total_units
                                        descriptions[product_code] = (
                                            self.normalize_description(description)
                                        )

                i += 1

        except Exception:
            pass

        return quantities, descriptions
