"""API routes for report processing."""

from datetime import datetime
from io import BytesIO

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import StreamingResponse

from app.dependencies import get_transformation_service, get_comparison_service
from app.services.transformation import TransformationService
from app.services.comparison import ComparisonService


def _generate_filename(store_code: str, store_name: str) -> str:
    """Generate dynamic filename with date, store code and sanitized store name."""
    today = datetime.now().strftime("%Y-%m-%d")
    safe_store_name = "".join(
        c if c.isalnum() or c in " _-" else "" for c in store_name
    ).replace(" ", "_")
    return f"relatorio_processado_{today}_loja_{store_code}_{safe_store_name}.xlsx"

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("/process")
async def process_reports(
    weekly_report: UploadFile = File(..., description="Weekly report Excel file"),
    inventory_report: UploadFile = File(..., description="Inventory Excel file"),
    nf_pdfs: list[UploadFile] = File(default=[], description="NF PDF files"),
    pedido_pdfs: list[UploadFile] = File(default=[], description="Pedido PDF files"),
    mazza_report: UploadFile = File(default=None, description="Mazza report Excel file (optional, only for store 1225)"),
    transformation_service: TransformationService = Depends(get_transformation_service),
    comparison_service: ComparisonService = Depends(get_comparison_service),
) -> StreamingResponse:
    """
    Process weekly report with inventory comparison.

    Uploads files, runs transformation (with PDF data), then comparison
    against inventory, and returns the final Excel report.

    Optionally accepts a Mazza report for store 1225 to merge additional sales data.
    """
    # Read file contents
    weekly_content = BytesIO(await weekly_report.read())
    inventory_content = BytesIO(await inventory_report.read())

    nf_pdf_contents = [await pdf.read() for pdf in nf_pdfs]
    pedido_pdf_contents = [await pdf.read() for pdf in pedido_pdfs]

    mazza_content = None
    if mazza_report:
        mazza_content = BytesIO(await mazza_report.read())

    # Step 1: Transform weekly report with PDF data
    transformed = transformation_service.process(
        weekly_excel=weekly_content,
        nf_pdfs=nf_pdf_contents,
        pedido_pdfs=pedido_pdf_contents,
    )

    # Step 2: Compare with inventory (and merge Mazza if provided)
    final_output, store_code, store_name = comparison_service.compare(
        weekly_report=transformed,
        inventory_report=inventory_content,
        mazza_report=mazza_content,
    )

    # Generate dynamic filename
    filename = _generate_filename(store_code, store_name)

    # Return the Excel file
    return StreamingResponse(
        final_output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/transform")
async def transform_report(
    weekly_report: UploadFile = File(..., description="Weekly report Excel file"),
    nf_pdfs: list[UploadFile] = File(default=[], description="NF PDF files"),
    pedido_pdfs: list[UploadFile] = File(default=[], description="Pedido PDF files"),
    transformation_service: TransformationService = Depends(get_transformation_service),
) -> StreamingResponse:
    """
    Transform weekly report with PDF data (partial processing).

    Uploads weekly report and optional PDFs, runs transformation,
    and returns the transformed Excel file.
    """
    # Read file contents
    weekly_content = BytesIO(await weekly_report.read())

    nf_pdf_contents = [await pdf.read() for pdf in nf_pdfs]
    pedido_pdf_contents = [await pdf.read() for pdf in pedido_pdfs]

    # Transform
    transformed = transformation_service.process(
        weekly_excel=weekly_content,
        nf_pdfs=nf_pdf_contents,
        pedido_pdfs=pedido_pdf_contents,
    )

    return StreamingResponse(
        transformed,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": "attachment; filename=Relatorio_GAC_Semanal_Output.xlsx"
        },
    )


@router.post("/compare")
async def compare_reports(
    weekly_report: UploadFile = File(
        ..., description="Transformed weekly report Excel file"
    ),
    inventory_report: UploadFile = File(..., description="Inventory Excel file"),
    mazza_report: UploadFile = File(default=None, description="Mazza report Excel file (optional, only for store 1225)"),
    comparison_service: ComparisonService = Depends(get_comparison_service),
) -> StreamingResponse:
    """
    Compare transformed weekly report with inventory (partial processing).

    Uploads already-transformed weekly report and inventory,
    runs comparison, and returns the compared Excel file.

    Optionally accepts a Mazza report for store 1225 to merge additional sales data.
    """
    # Read file contents
    weekly_content = BytesIO(await weekly_report.read())
    inventory_content = BytesIO(await inventory_report.read())

    mazza_content = None
    if mazza_report:
        mazza_content = BytesIO(await mazza_report.read())

    # Compare (and merge Mazza if provided)
    final_output, store_code, store_name = comparison_service.compare(
        weekly_report=weekly_content,
        inventory_report=inventory_content,
        mazza_report=mazza_content,
    )

    # Generate dynamic filename
    filename = _generate_filename(store_code, store_name)

    return StreamingResponse(
        final_output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
