from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Image,
    Table,
    TableStyle,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from smart_label import SmartLabelManager


def create_sticker_preview(product_code, output_filename="sticker_preview.pdf"):
    # 1. Initialize Manager
    base_dir = "/home/quimicab/Base_datos/original_data"
    manager = SmartLabelManager(base_dir)

    # 2. Get Data
    product = manager.get_product_data(product_code)
    if not product:
        print(f"Product {product_code} not found!")
        return

    print(f"Generating label for: {product['name']}")

    # 3. Setup PDF
    doc = SimpleDocTemplate(
        output_filename,
        pagesize=landscape(letter),
        rightMargin=0.5 * inch,
        leftMargin=0.5 * inch,
        topMargin=0.5 * inch,
        bottomMargin=0.5 * inch,
    )

    styles = getSampleStyleSheet()
    # Custom Styles
    style_title = ParagraphStyle(
        "StickerTitle",
        parent=styles["Heading1"],
        fontSize=24,
        alignment=1,  # Center
        spaceAfter=20,
        textColor=colors.black,
    )

    style_signal = ParagraphStyle(
        "SignalWord",
        parent=styles["Heading2"],
        fontSize=18,
        alignment=1,  # Center
        textColor=colors.red,
        spaceAfter=20,
        fontName="Helvetica-Bold",
    )

    style_h = ParagraphStyle(
        "Hazard",
        parent=styles["Normal"],
        fontSize=10,
        leading=12,
        textColor=colors.black,
    )

    style_p = ParagraphStyle(
        "Precaution",
        parent=styles["Normal"],
        fontSize=8,
        leading=10,
        textColor=colors.darkblue,
    )

    elements = []

    # --- Header Section (Name + CAS + Internal Code) ---
    header_data = [
        [Paragraph(f"<b>{product['name']}</b>", style_title)],
        [f"CAS: {product['cas']} | Code: {product['internal_code']}"],
    ]
    t_header = Table(header_data, colWidths=[9 * inch])
    t_header.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    elements.append(t_header)
    elements.append(Spacer(1, 0.2 * inch))

    # --- Pictograms Section ---
    picto_images = []
    for picto_name in product["pictograms"]:
        path = manager.get_pictogram_path(picto_name)
        if path:
            # Scale image to icon size
            img = Image(path, width=1.2 * inch, height=1.2 * inch)
            picto_images.append(img)

    if picto_images:
        # Arrange pictograms in a row centered
        t_picto = Table([picto_images], colWidths=[1.3 * inch] * len(picto_images))
        t_picto.setStyle(
            TableStyle(
                [
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        elements.append(t_picto)

    elements.append(Spacer(1, 0.1 * inch))

    # --- Signal Word ---
    if product["signal_word"] and str(product["signal_word"]).lower() != "no aplicable":
        elements.append(Paragraph(product["signal_word"].upper(), style_signal))
    elements.append(Spacer(1, 0.2 * inch))

    # --- Content Columns (Hazards vs Precautions) ---

    # Prepare H-Statements Content
    h_content = [Paragraph("<b>HAZARD STATEMENTS (H):</b>", style_h)]
    for h in product["h_statements"]:
        h_content.append(Paragraph(f"• {h}", style_h))

    # Prepare P-Statements Content
    p_content = [Paragraph("<b>PRECAUTIONARY STATEMENTS (P):</b>", style_p)]
    for p in product["p_statements"][:15]:  # Limit to avoid overflow in preview
        p_content.append(Paragraph(f"• {p}", style_p))
    if len(product["p_statements"]) > 15:
        p_content.append(
            Paragraph(f"• ... ({len(product['p_statements'])-15} more)", style_p)
        )

    # Layout using a Table for two columns
    data_table = [[h_content, p_content]]

    t_content = Table(data_table, colWidths=[4.5 * inch, 4.5 * inch])
    t_content.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("padding", (0, 0), (-1, -1), 10),
            ]
        )
    )
    elements.append(t_content)

    # --- Footer (Emergency) ---
    elements.append(Spacer(1, 0.3 * inch))
    elements.append(
        Paragraph(
            f"<b>EMERGENCY CONTACT: {product['emergency_phone']}</b>", style_title
        )
    )

    # Build
    doc.build(elements)
    print(f"PDF generated: {output_filename}")


if __name__ == "__main__":
    # Test with the product "IFF-QB00122" (MENTA)
    create_sticker_preview(
        "IFF-QB00122", "/home/quimicab/Base_datos/sticker_preview_MENTA.pdf"
    )
