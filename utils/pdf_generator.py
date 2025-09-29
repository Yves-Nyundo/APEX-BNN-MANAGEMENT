# # utils/pdf_generator.py
# from reportlab.pdfgen import canvas
# from reportlab.lib.pagesizes import A4
# from reportlab.lib.utils import ImageReader
# from reportlab.lib.colors import black
# from io import BytesIO
# from decimal import Decimal
# import os

# # Add this at top-level or pass via config
# # You'll need access to the Flask app or its static_folder
# from flask import current_app as app  # ✅ Use application context


# def to_decimal(value, default='0.00'):
#     """Safely convert a value to Decimal."""
#     if value is None or value == '':
#         return Decimal(default)
#     if isinstance(value, Decimal):
#         return value
#     try:
#         return Decimal(str(value))
#     except Exception:
#         return Decimal(default)


# def get_static_file_path(relative_path):
#     """
#     Build correct OS path inside /static/uploads/
#     Example: 'company/company_signature.png' → full path
#     """
#     try:
#         # ✅ Full path: /project/static/uploads/company/...
#         return os.path.join(app.static_folder, 'uploads', relative_path)
#     except RuntimeError:
#         # Fallback during testing (no app context)
#         base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
#         return os.path.join(base_dir, 'static', 'uploads', relative_path)


# def generate_invoice_pdf(form_data, preview=False, document_type='invoice'):
#     """
#     Generate PDF for Invoice, Proforma, or Delivery Note.
#     Includes:
#       - Company logo watermark
#       - Signature & stamp (stamp overlays signature)
#       - Signing person name and function
#       - DRAFT watermark (if preview)
#     """
#     print(f"🖨️ PDF Generator: document_type = '{document_type}'")
#     print("\n🖨️  generate_invoice_pdf called with:")
#     import pprint
#     pprint.pprint(form_data)

#     buffer = BytesIO()
#     c = canvas.Canvas(buffer, pagesize=A4)
#     width, height = A4
#     margin = 20 * 2.83  # ~20mm in points
#     y = height - margin

#     # Import settings safely
#     try:
#         from models_core.models import get_or_create_company_settings
#         settings = get_or_create_company_settings()
#     except Exception as e:
#         print(f"⚠️ Could not load company settings: {e}")
#         settings = None

#     # --- Watermark Logo ---
#     if settings and settings.logo_image_path:
#         # ✅ Use get_static_file_path
#         logo_path = get_static_file_path(settings.logo_image_path)
#         if os.path.exists(logo_path):
#             c.saveState()
#             c.setFillAlpha(0.30)  # Very light watermark
#             try:
#                 img = ImageReader(logo_path)
#                 w, h = width * 0.4, (width * 0.4) / (img.getSize()[0] / img.getSize()[1])
#                 # x = (width - w) / 2
#                 # y = height - h - 250  # ← Adjust this value to move up/down

#                 c.drawImage(img, (width - w) / 2, (height - h) / 2,
#                         width=w, height=h, mask='auto', preserveAspectRatio=True)
#             except Exception as img_err:
#                 print(f"❌ Failed to draw watermark logo: {img_err}")
#             c.restoreState()
#         else:
#             print(f"🟡 Watermark logo not found at: {logo_path}")

#     # --- Header ---
#     c.setFont("Helvetica-Bold", 16)
#     c.drawString(margin, y, "APEX BNN SERVICES")
#     y -= 20

#     # --- Document Title ---
#     c.setFont("Helvetica-Bold", 18)
#     title_map = {
#         "delivery_note": "DELIVERY NOTE",
#         "proforma": "PROFORMA INVOICE",
#         "invoice": "INVOICE"
#     }
#     title = title_map.get(document_type, "DOCUMENT")
#     c.drawRightString(width - margin, y, title)

#     po_number = form_data.get('po_number', 'N/A')
#     c.setFont("Helvetica", 10)
#     doc_number = form_data.get('doc_number', 'N/A')
#     c.drawRightString(width - margin, y - 15, f"No: {doc_number}")
#     y -= 50

#     # --- Client Info ---
#     client_name = form_data.get('client_name', 'Unknown Client')
#     client_address = form_data.get('client_address', 'N/A')

#     c.setFont("Helvetica-Bold", 11)
#     c.drawString(margin, y, "Client:")
#     c.drawString(width / 2 + 10, y, "Document Info:")
#     y -= 15

#     c.setFont("Helvetica", 10)
#     c.drawString(margin, y, f"Name: {client_name}")
#     c.drawString(margin, y - 12, f"Address: {client_address}")

#     issue_date = form_data.get('issue_date', 'N/A')
#     due_date = form_data.get('due_date', 'N/A') if document_type != 'delivery_note' else 'N/A'

#     c.drawString(width / 2 + 10, y, f"Issue Date: {issue_date}")
#     c.drawString(width / 2 + 10, y - 12, f"Due Date: {due_date}")
#     c.drawString(width / 2 + 10, y - 24, f"PO #: {po_number}")
#     y -= 50

#     # --- Table Header ---
#     c.setFont("Helvetica-Bold", 11)
#     if document_type == "delivery_note":
#         headers = ["Description", "Qty", "Comment"]
#         col_widths = [0.6, 0.15, 0.25]
#         columns = [
#             margin,
#             margin + width * col_widths[0],
#             margin + width * (col_widths[0] + col_widths[1])
#         ]
#     else:
#         headers = ["Description", "Qty", "Unit Price", "Total"]
#         col_widths = [0.5, 0.15, 0.15, 0.2]
#         columns = [
#             margin,
#             margin + width * col_widths[0],
#             margin + width * (col_widths[0] + col_widths[1]),
#             margin + width * (col_widths[0] + col_widths[1] + col_widths[2])
#         ]

#     for i, head in enumerate(headers):
#         c.drawString(columns[i], y, head)
#     y -= 15
#     c.line(margin, y, width - margin, y)

#     # --- Line Items ---
#     c.setFont("Helvetica", 10)
#     subtotal = Decimal('0.00')

#     items = form_data.get('items', [])
#     if not items:
#         c.drawString(margin, y - 20, "No items listed.")
#         y -= 40
#     else:
#         for item in items:
#             desc = str(item.get('description', '') or '')
#             qty = to_decimal(item.get('quantity'))
#             comment = str(item.get('comment', '') or '')

#             if document_type != "delivery_note" and 'unit_price' in item:
#                 price = to_decimal(item.get('unit_price'))
#                 total = qty * price
#                 subtotal += total
#             else:
#                 price = Decimal('0.00')
#                 total = Decimal('0.00')

#             # Wrap long description
#             max_chars = 60
#             desc_lines = [desc[i:i + max_chars] for i in range(0, len(desc), max_chars)] or [""]

#             for line in desc_lines:
#                 if y < 100:
#                     c.showPage()
#                     y = height - margin
#                     # Redraw header if new page
#                     for i, head in enumerate(headers):
#                         c.drawString(columns[i], y, head)
#                     y -= 15
#                     c.line(margin, y, width - margin, y)
#                     c.setFont("Helvetica", 10)

#                 c.drawString(columns[0], y - 15, line)
#                 y -= 15

#             # Qty
#             c.drawString(columns[1], y + 15 - 15, str(qty))

#             if document_type == "delivery_note":
#                 if len(comment) > 30:
#                     comment = comment[:27] + "..."
#                 c.drawString(columns[2], y + 15 - 15, comment)
#             else:
#                 c.drawString(columns[2], y + 15 - 15, f"{price:.2f}")
#                 c.drawString(columns[3], y + 15 - 15, f"{total:.2f}")

#             y -= 10

#     # --- Totals (Invoices Only) ---
#     if document_type != "delivery_note":
#         vat_rate = to_decimal(form_data.get('vat_rate', 0)) / Decimal('100')
#         vat_amount = (subtotal * vat_rate).quantize(Decimal('0.00'))
#         total_amount = (subtotal + vat_amount).quantize(Decimal('0.00'))

#         y -= 30
#         if y < 100:
#             c.showPage()
#             y = height - margin

#         c.setFont("Helvetica-Bold", 11)
#         c.drawRightString(width - margin - 80, y, "Subtotal:")
#         c.drawRightString(width - margin, y, f"{subtotal:.2f}")
#         y -= 15
#         c.drawRightString(width - margin - 80, y, "VAT:")
#         c.drawRightString(width - margin, y, f"{vat_amount:.2f}")
#         y -= 15
#         c.drawRightString(width - margin - 80, y, "Total:")
#         c.drawRightString(width - margin, y, f"{total_amount:.2f}")

#         y -= 60
#     else:
#         y -= 60

#     # --- Signature & Stamp Overlay Section ---
#     sig_x = margin
#     sig_y = y

#     # Signing Person Info
#     signing_name = (settings.signing_person_name if settings and settings.signing_person_name
#                     else form_data.get('signing_person_name', 'Authorized Signatory'))
#     signing_function = (settings.signing_person_function if settings and settings.signing_person_function
#                         else form_data.get('signing_person_function', 'Finance Manager'))

#     c.setFont("Helvetica", 10)
#     c.drawString(sig_x, sig_y, f"Prepared By: {signing_name}")
#     c.drawString(sig_x, sig_y - 12, f"Function: {signing_function}")

#     # ✅ Load Signature Image
#     signature_img_path = None
#     if settings and settings.signature_image_path:
#         signature_img_path = get_static_file_path(settings.signature_image_path)

#     # Draw Signature
#     signature_width = 110
#     signature_height = 40
#     stamp_size = 100
#     sig_bottom_y = sig_y - 30
#     signature_x = sig_x + 50
#     if signature_img_path and os.path.exists(signature_img_path):
#         try:
#             c.drawImage(
#                 signature_img_path,
#                 # x=sig_x,
#                 x=signature_x,
#                 y=sig_bottom_y,
#                 width=signature_width,
#                 height=signature_height,
#                 mask='auto'
#             )
#             print(f"✅ Successfully drew signature from: {signature_img_path}")
#         except Exception as e:
#             print(f"❌ Error drawing signature: {e}")
#     else:
#         print(f"🟡 Signature not found at: {signature_img_path}")

#     # Draw Stamp Over Signature
#     stamp_img_path = None
#     if settings and settings.stamp_image_path:
#         stamp_img_path = get_static_file_path(settings.stamp_image_path)

#     if stamp_img_path and os.path.exists(stamp_img_path):
#         try:
#             c.saveState()
#             c.translate(sig_x + signature_width - 5, sig_bottom_y + signature_height + 15)
#             c.rotate(8)
#             c.drawImage(
#                 stamp_img_path,
#                 x=-stamp_size // 2,
#                 y=-stamp_size // 2,
#                 width=stamp_size,
#                 height=stamp_size,
#                 mask='auto'
#             )
#             c.restoreState()
#             print(f"✅ Successfully drew stamp from: {stamp_img_path}")
#         except Exception as e:
#             print(f"❌ Error drawing stamp: {e}")
#     else:
#         print(f"🟡 Stamp not found at: {stamp_img_path}")

#     # --- DRAFT Watermark (Preview Only) ---
#     if preview:
#         c.saveState()
#         c.setFont("Helvetica-Bold", 80)
#         c.setFillColor(black)
#         c.setFillAlpha(0.1)
#         c.translate(width / 2, height / 2)
#         c.rotate(45)
#         c.drawCentredString(0, 0, "DRAFT")
#         c.restoreState()

#     # Finalize
#     c.showPage()
#     c.save()
#     buffer.seek(0)
#     return buffer.read()
# utils/pdf_generator.py

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.lib.colors import black
from decimal import Decimal
import os
from io import BytesIO
from flask import current_app as app


def to_decimal(value, default='0.00'):
    if value is None or value == '':
        return Decimal(default)
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal(default)


def get_static_file_path(relative_path):
    try:
        return os.path.join(app.static_folder, 'uploads', relative_path)
    except RuntimeError:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base_dir, 'static', 'uploads', relative_path)


def generate_invoice_pdf(form_data, preview=False, document_type='invoice', save_to_disk=True):
    """
    Generate PDF invoice.
    
    Args:
        form_data (dict): Invoice data
        preview (bool): Add DRAFT watermark
        document_type (str): 'invoice', 'proforma', 'delivery_note'
        save_to_disk (bool): If True, saves to static/generated_pdfs/ and returns path
                            If False, returns PDF as bytes
    
    Returns:
        str (path) if save_to_disk=True
        bytes if save_to_disk=False
    """
    print(f"🖨️ PDF Generator: {document_type}, preview={preview}, save_to_disk={save_to_disk}")
    print("\n📊 FINAL ITEMS BEING DRAWN IN PDF:")
    for i, item in enumerate(form_data['items']):
        desc = item['description'][:30] + "..." if len(item['description']) > 30 else item['description']
        unit_price = float(item.get('unit_price') or 0.0)
        total_price = float(item.get('total_price') or 0.0)
        quantity = item['quantity']
        print(f" {i+1}. '{desc}' x{quantity} @ ${unit_price:.2f} = ${total_price:.2f}")
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    margin = 20 * 2.83
    y = height - margin

    try:
        from models_core.models import get_or_create_company_settings
        settings = get_or_create_company_settings()
    except Exception as e:
        print(f"⚠️ Could not load company settings: {e}")
        settings = None

    # --- Watermark Logo ---
    if settings and settings.logo_image_path:
        logo_path = get_static_file_path(settings.logo_image_path)
        if os.path.exists(logo_path):
            c.saveState()
            c.setFillAlpha(0.15)
            try:
                img = ImageReader(logo_path)
                w, h = width * 0.4, (width * 0.4) / (img.getSize()[0] / img.getSize()[1])
                c.drawImage(img, (width - w) / 2, (height - h) / 2,
                            width=w, height=h, mask='auto', preserveAspectRatio=True)
            except Exception as err:
                print(f"❌ Failed to draw logo: {err}")
            c.restoreState()

    # --- Header & Title ---
    c.setFont("Helvetica-Bold", 16)
    c.drawString(margin, y, "APEX BNN SERVICES")
    y -= 20

    title_map = {
        "delivery_note": "DELIVERY NOTE",
        "proforma": "PROFORMA INVOICE",
        "invoice": "INVOICE"
    }
    title = title_map.get(document_type, "DOCUMENT")
    c.setFont("Helvetica-Bold", 18)
    c.drawRightString(width - margin, y, title)

    doc_number = form_data.get('doc_number', 'N/A')
    c.setFont("Helvetica", 10)
    c.drawRightString(width - margin, y - 15, f"No: {doc_number}")
    y -= 50

    # --- Client Info ---
    client_name = form_data.get('client_name', 'Unknown Client')
    client_address = form_data.get('client_address', 'N/A')

    c.setFont("Helvetica-Bold", 11)
    c.drawString(margin, y, "Client:")
    c.drawString(width / 2 + 10, y, "Document Info:")
    y -= 15

    c.setFont("Helvetica", 10)
    c.drawString(margin, y, f"Name: {client_name}")
    c.drawString(margin, y - 12, f"Address: {client_address}")

    issue_date = form_data.get('issue_date', 'N/A')
    due_date = form_data.get('due_date', 'N/A') if document_type != 'delivery_note' else 'N/A'
    po_number = form_data.get('po_number', 'N/A')

    c.drawString(width / 2 + 10, y, f"Issue Date: {issue_date}")
    c.drawString(width / 2 + 10, y - 12, f"Due Date: {due_date}")
    c.drawString(width / 2 + 10, y - 24, f"PO #: {po_number}")
    y -= 50

    # --- Table Headers ---
    c.setFont("Helvetica-Bold", 11)
    if document_type == "delivery_note":
        headers = ["Description", "Qty", "Comment"]
        col_widths = [0.6, 0.15, 0.25]
        columns = [
            margin,
            margin + width * col_widths[0],
            margin + width * sum(col_widths[:2])
        ]
    else:
        headers = ["Description", "Qty", "Unit Price", "Total"]
        col_widths = [0.5, 0.15, 0.15, 0.2]
        columns = [
            margin,
            margin + width * col_widths[0],
            margin + width * sum(col_widths[:2]),
            margin + width * sum(col_widths[:3])
        ]

    for i, head in enumerate(headers):
        c.drawString(columns[i], y, head)
    y -= 15
    c.line(margin, y, width - margin, y)

    # --- Items ---
    c.setFont("Helvetica", 10)
    subtotal = Decimal('0.00')

    items = form_data.get('items', [])
    if not items:
        c.drawString(margin, y - 20, "No items listed.")
        y -= 40
    else:
        for item in items:
            desc = str(item.get('description', '') or '')
            qty = to_decimal(item.get('quantity'))
            comment = str(item.get('comment', '') or '')

            if document_type != "delivery_note" and 'unit_price' in item:
                price = to_decimal(item.get('unit_price'))
                total = qty * price
                subtotal += total
            else:
                price = Decimal('0.00')
                total = Decimal('0.00')

            max_chars = 60
            desc_lines = [desc[i:i + max_chars] for i in range(0, len(desc), max_chars)] or [""]

            for line in desc_lines:
                if y < 100:
                    c.showPage()
                    y = height - margin
                    for i, head in enumerate(headers):
                        c.drawString(columns[i], y, head)
                    y -= 15
                    c.line(margin, y, width - margin, y)
                    c.setFont("Helvetica", 10)

                c.drawString(columns[0], y - 15, line)
                y -= 15

            c.drawString(columns[1], y + 15 - 15, str(qty))

            if document_type == "delivery_note":
                c.drawString(columns[2], y + 15 - 15, comment[:30] + "..." if len(comment) > 30 else comment)
            else:
                c.drawString(columns[2], y + 15 - 15, f"{price:.2f}")
                c.drawString(columns[3], y + 15 - 15, f"{total:.2f}")

            y -= 10

    # --- Totals ---
    if document_type != "delivery_note":
        vat_rate = to_decimal(form_data.get('vat_rate', 0)) / Decimal('100')
        vat_amount = (subtotal * vat_rate).quantize(Decimal('0.00'))
        total_amount = (subtotal + vat_amount).quantize(Decimal('0.00'))

        y -= 30
        if y < 100:
            c.showPage()
            y = height - margin

        c.setFont("Helvetica-Bold", 11)
        c.drawRightString(width - margin - 80, y, "Subtotal:")
        c.drawRightString(width - margin, y, f"{subtotal:.2f}")
        y -= 15
        c.drawRightString(width - margin - 80, y, "VAT:")
        c.drawRightString(width - margin, y, f"{vat_amount:.2f}")
        y -= 15
        c.drawRightString(width - margin - 80, y, "Total:")
        c.drawRightString(width - margin, y, f"{total_amount:.2f}")
        y -= 60
    else:
        y -= 60

    # --- Signature & Stamp ---
    sig_x = margin
    sig_y = y
    signing_name = (settings.signing_person_name if settings and settings.signing_person_name
                    else form_data.get('signing_person_name', 'Authorized Signatory'))
    signing_function = (settings.signing_person_function if settings and settings.signing_person_function
                        else form_data.get('signing_person_function', 'Finance Manager'))

    c.setFont("Helvetica", 10)
    c.drawString(sig_x, sig_y, f"Prepared By: {signing_name}")
    c.drawString(sig_x, sig_y - 12, f"Function: {signing_function}")

    signature_width = 110
    signature_height = 40
    stamp_size = 100
    sig_bottom_y = sig_y - 30
    signature_x = sig_x + 50

    if settings and settings.signature_image_path:
        sig_path = get_static_file_path(settings.signature_image_path)
        if os.path.exists(sig_path):
            try:
                c.drawImage(sig_path, x=signature_x, y=sig_bottom_y,
                            width=signature_width, height=signature_height, mask='auto')
                print(f"✅ Signature drawn: {sig_path}")
            except Exception as e:
                print(f"❌ Error drawing signature: {e}")

    if settings and settings.stamp_image_path:
        stamp_path = get_static_file_path(settings.stamp_image_path)
        if os.path.exists(stamp_path):
            try:
                c.saveState()
                c.translate(sig_x + signature_width - 5, sig_bottom_y + signature_height + 15)
                c.rotate(8)
                c.drawImage(stamp_path, x=-stamp_size // 2, y=-stamp_size // 2,
                            width=stamp_size, height=stamp_size, mask='auto')
                c.restoreState()
                print(f"✅ Stamp drawn: {stamp_path}")
            except Exception as e:
                print(f"❌ Error drawing stamp: {e}")

    # --- DRAFT Watermark ---
    if preview:
        c.saveState()
        c.setFont("Helvetica-Bold", 80)
        c.setFillColor(black)
        c.setFillAlpha(0.1)
        c.translate(width / 2, height / 2)
        c.rotate(45)
        c.drawCentredString(0, 0, "DRAFT")
        c.restoreState()

    # Finalize
    c.save()
    buffer.seek(0)
    pdf_bytes = buffer.getvalue()

    # Optionally save to disk
    if save_to_disk:
        pdf_dir = os.path.join(app.static_folder, 'generated_pdfs')
        os.makedirs(pdf_dir, exist_ok=True)
        filename = f"{form_data['doc_number']}.pdf"
        filepath = os.path.join(pdf_dir, filename)

        with open(filepath, 'wb') as f:
            f.write(pdf_bytes)

        rel_path = f"generated_pdfs/{filename}"
        print(f"📄 PDF saved to: {rel_path}")
        return rel_path  # Return path for DB storage

    # Otherwise return bytes
    return pdf_bytes  # For preview/download without saving