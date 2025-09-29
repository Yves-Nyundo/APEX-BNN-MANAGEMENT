from flask import Flask, render_template
import os
from datetime import datetime
app = Flask(__name__, template_folder="/Users/macbookpro/Desktop/APEX_MANAGEMENT_app/templates")

with app.app_context():
    html = render_template(
        "document_template.html",
        signature_path="file:///Users/macbookpro/Desktop/APEX_MANAGEMENT_app/static/images/signature.png",
        stamp_path="file:///Users/macbookpro/Desktop/APEX_MANAGEMENT_app/static/images/stamp.png",
        logo_path="file:///Users/macbookpro/Desktop/APEX_MANAGEMENT_app/static/images/logo.png",
        invoice={  # dummy data for testing
            "document_type": "invoice",
            "invoice_number": "INVOICE-20250809-001",
            "po_number": "000",
            "date_created": datetime.strptime("2025-08-09", "%Y-%m-%d"),
            "client": {
                "name": "Yves Nyundo Ngoy",
                "address": "Miami 2506",
                "email": "yvan.nyundo@gmail.com"
            },
            "items": [
                {"description": "iPhone 15 Pro Max", "quantity": 23, "unit_price": 1870.00, "total_price": 43010.00}
            ],
            "total_amount": 49891.60,
            "vat_amount": 6881.60,
            "vat_rate": 16.0
        },
        company_settings={
            "phone": "123-456-7890",
            "email": "info@apexbnn.com",
            "signing_person_name": "Authorized Signatory",
            "signing_person_function": "Finance Manager"
        }
    )

    output_path = "/Users/macbookpro/Desktop/rendered_invoice.html"
    with open(output_path, "w") as f:
        f.write(html)

    print(f"Rendered HTML saved to: {output_path}")
