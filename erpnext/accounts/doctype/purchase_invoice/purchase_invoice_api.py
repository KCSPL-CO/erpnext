import frappe
from frappe import _
import base64

# Authentication helper
def authenticate_user():
    auth_header = frappe.get_request_header("Authorization")
    if not auth_header or not auth_header.startswith("Basic "):
        frappe.local.response["http_status_code"] = 401
        return None

    try:
        encoded_token = auth_header.split("Basic ")[1]
        decoded = base64.b64decode(encoded_token).decode("utf-8")
        api_key, api_secret = decoded.split(":")
    except Exception:
        frappe.local.response["http_status_code"] = 401
        return None

    user = frappe.db.get("User", {"api_key": api_key})
    if (
        not user
        or frappe.utils.password.get_decrypted_password("User", user.name, "api_secret") != api_secret
    ):
        frappe.local.response["http_status_code"] = 401
        return None

    return user

@frappe.whitelist(allow_guest=True)
def list_purchase_invoices():
    if frappe.request.method != "GET":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only GET method allowed"}

    if not authenticate_user():
        return {"error": "Unauthorized"}

    try:
        invoices = frappe.get_all(
            "Purchase Invoice",
            filters={"docstatus": 1},  # Only submitted
            fields=[
                "name", "supplier", "posting_date", "due_date", "is_paid",
                "grand_total", "currency", "status", "company"
            ],
            order_by="posting_date desc",
            limit_page_length=20
        )
        return {"message": invoices}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "List Purchase Invoice API")
        frappe.local.response["http_status_code"] = 500
        return {"error": str(e)}



@frappe.whitelist(allow_guest=True)
def filter_purchase_invoice():
    if not authenticate_user():
        return {"error": "Unauthorized"}

    try:
        today = frappe.utils.today()

        # Counts
        total_invoices = frappe.db.count("Purchase Invoice", {"docstatus": 1})
        total_paid = frappe.db.count("Purchase Invoice", {"docstatus": 1, "is_paid": 1})
        total_unpaid = frappe.db.count("Purchase Invoice", {"docstatus": 1, "is_paid": 0})

        today_paid = frappe.db.count("Purchase Invoice", {
            "docstatus": 1, "is_paid": 1, "posting_date": today
        })
        today_unpaid = frappe.db.count("Purchase Invoice", {
            "docstatus": 1, "is_paid": 0, "posting_date": today
        })

        # Today item count and value
        item_summary = frappe.db.sql("""
            SELECT COUNT(DISTINCT pii.item_code) AS item_count,
                   SUM(pii.amount) AS total_purchase_value
            FROM `tabPurchase Invoice Item` pii
            JOIN `tabPurchase Invoice` pi ON pi.name = pii.parent
            WHERE pi.docstatus = 1 AND pi.posting_date = %s
        """, (today,), as_dict=True)[0]

        return {
            "message": {
                "invoice_counts": {
                    "total": total_invoices,
                    "total_paid": total_paid,
                    "total_unpaid": total_unpaid,
                    "today_paid": today_paid,
                    "today_unpaid": today_unpaid
                },
                "today_item_purchases": {
                    "item_count": item_summary.item_count or 0,
                    "total_purchase_value": item_summary.total_purchase_value or 0.0
                }
            }
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Purchase Invoice Summary API")
        frappe.local.response["http_status_code"] = 500
        return {"error": str(e)}






@frappe.whitelist(allow_guest=False)
def create_purchase_invoice():
    if frappe.request.method != "POST":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only POST method allowed"}

    if not authenticate_user():
        return {"error": "Unauthorized"}

    try:
        data = frappe.parse_json(frappe.request.data)

        # Required fields
        supplier = data.get("supplier")
        posting_date = data.get("posting_date")
        items = data.get("items", [])

        if not supplier or not items:
            return {"error": "Missing supplier or items"}

        # Create the Purchase Invoice Doc
        doc = frappe.new_doc("Purchase Invoice")
        doc.supplier = supplier
        doc.posting_date = posting_date or frappe.utils.today()
        doc.company = data.get("company") or frappe.defaults.get_user_default("Company")

        # Add items
        for item in items:
            doc.append("items", {
                "item_code": item.get("item_code"),
                "qty": item.get("qty"),
                "rate": item.get("rate"),
                "uom": item.get("uom") or "Nos"
            })

        doc.insert()
        doc.submit()

        return {"message": f"Purchase Invoice {doc.name} created successfully"}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Create Purchase Invoice API")
        frappe.local.response["http_status_code"] = 500
        return {"error": str(e)}












@frappe.whitelist(allow_guest=False)
def get_purchase_invoice(invoice_id):
    if not authenticate_user():
        return {"error": "Unauthorized"}

    try:
        doc = frappe.get_doc("Purchase Invoice", invoice_id)

        return {
            "message": {
                "name": doc.name,
                "supplier": doc.supplier,
                "posting_date": doc.posting_date,
                "company": doc.company,
                "grand_total": doc.grand_total,
                "currency": doc.currency,
                "status": doc.status,
                "items": [
                    {
                        "item_code": item.item_code,
                        "item_name": item.item_name,
                        "qty": item.qty,
                        "rate": item.rate,
                        "amount": item.amount
                    } for item in doc.items
                ]
            }
        }

    except frappe.DoesNotExistError:
        frappe.local.response["http_status_code"] = 404
        return {"error": f"Purchase Invoice {invoice_id} not found"}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Purchase Invoice API")
        frappe.local.response["http_status_code"] = 500
        return {"error": str(e)}
