import base64
import frappe
from frappe.utils.password import get_decrypted_password

# ------------------- Authentication ---------------------
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
        frappe.log_error(frappe.get_traceback(), "Auth Decode Error")
        frappe.local.response["http_status_code"] = 401
        return None

    user = frappe.db.get("User", {"api_key": api_key})
    if not user:
        frappe.local.response["http_status_code"] = 401
        return None

    real_secret = get_decrypted_password("User", user.name, "api_secret")
    if real_secret != api_secret:
        frappe.local.response["http_status_code"] = 401
        return None

    return user

# ------------------- CREATE ---------------------
# import frappe
# from frappe.utils.response import build_response

@frappe.whitelist(allow_guest=True)
def create_sales_invoice():
    if frappe.request.method != "POST":
        frappe.local.response["http_status_code"] = 405
        return {"message": "Only POST allowed", "success": False}

    if not authenticate_user():
        return {"message": "Unauthorized", "success": False}

    try:
        data = frappe.request.get_json()

        doc = frappe.new_doc("Sales Invoice")
        doc.customer = data.get("customer")
        doc.customer_name = data.get("customer_name")
        doc.tax_id = data.get("tax_id")
        doc.company = data.get("company")
        doc.posting_date = data.get("posting_date")
        doc.posting_time = data.get("posting_time")
        doc.set_posting_time = data.get("set_posting_time", 0)
        doc.due_date = data.get("due_date")
        doc.patient = data.get("patient")
        doc.patient_name = data.get("patient_name")
        doc.ref_practitioner = data.get("ref_practitioner")

        doc.total_qty = data.get("total_qty", 0)
        doc.total = data.get("total", 0)
        doc.net_total = data.get("net_total", 0)
        doc.tax_category = data.get("tax_category")
        doc.taxes_and_charges = data.get("taxes_and_charges")
        doc.total_taxes_and_charges = data.get("total_taxes_and_charges", 0)
        doc.grand_total = data.get("grand_total", 0)
        doc.rounded_total = data.get("rounded_total", 0)
        doc.outstanding_amount = data.get("outstanding_amount", 0)

        doc.apply_discount_on = data.get("apply_discount_on", "")
        doc.additional_discount_percentage = data.get("additional_discount_percentage", 0)
        doc.discount_amount = data.get("discount_amount", 0)

        doc.is_pos = data.get("is_pos", False)
        doc.is_return = data.get("is_return", False)
        doc.is_debit_note = data.get("is_debit_note", False)
        doc.update_billed_amount_in_sales_order = data.get("update_billed_amount_in_sales_order", True)
        doc.update_billed_amount_in_delivery_note = data.get("update_billed_amount_in_delivery_note", True)
        doc.pos_profile = data.get("pos_profile", "")
        doc.reason_for_issuing_document = data.get("reason_for_issuing_document", "")
        doc.return_against = data.get("return_against", "")

        # Add items
        for item in data.get("items", []):
            doc.append("items", {
                "item_name": item.get("item"),
                "item_code": item.get("item"),
                "qty": item.get("quantity"),
                "rate": item.get("rate"),
                "amount": item.get("amount"),
                "uom": "Nos"
            })

        # Add taxes/charges
        for charge in data.get("charges", []):
            doc.append("taxes", {
                "charge_type": charge.get("type"),
                "account_head": charge.get("account_head"),
                "rate": charge.get("tax_rate"),
                "tax_amount": charge.get("amount"),
                "total": charge.get("total")
            })

        doc.insert(ignore_permissions=True)
        # doc.submit()
        frappe.db.commit()

        return {
            "message": "Sales Invoice created",
            "success": True,
            "data": doc.as_dict()
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Create Sales Invoice")
        return {"message": str(e), "success": False}

# ------------------- GET ALL ---------------------
@frappe.whitelist(allow_guest=True)
def get_all_sales_invoices():
    if frappe.request.method != "GET":
        frappe.local.response["http_status_code"] = 405
        return {"message": "Only GET allowed", "success": False}

    if not authenticate_user():
        return {"message": "Unauthorized", "success": False}

    try:
        data = frappe.get_all("Sales Invoice", fields=["*", ])
        return {"message": "Fetched successfully", "success": True, "data": data}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get All Sales Invoices")
        return {"message": str(e), "success": False}

# ------------------- GET BY ID ---------------------
@frappe.whitelist(allow_guest=True)
def get_sales_invoice_by_id(name):
    if frappe.request.method != "GET":
        frappe.local.response["http_status_code"] = 405
        return {"message": "Only GET allowed", "success": False}

    if not authenticate_user():
        return {"message": "Unauthorized", "success": False}

    try:
        doc = frappe.get_doc("Sales Invoice", name)
        return {"message": "Fetched successfully", "success": True, "data": doc.as_dict()}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Sales Invoice By ID")
        return {"message": str(e), "success": False}

# ------------------- UPDATE ---------------------
@frappe.whitelist(allow_guest=True)
def update_sales_invoice():
    if frappe.request.method != "PUT":
        frappe.local.response["http_status_code"] = 405
        return {"message": "Only PUT allowed", "success": False}

    if not authenticate_user():
        return {"message": "Unauthorized", "success": False}

    try:
        data = frappe.request.get_json()
        name = data.get("name")
        if not name:
            return {"message": "Missing Sales Invoice name", "success": False}

        doc = frappe.get_doc("Sales Invoice", name)
        doc.update(data)
        doc.save(ignore_permissions=True)

        # Submit the invoice if not already
        if doc.docstatus < 1:
            doc.submit()

        # Only proceed if the invoice is paid
        if doc.status == "Paid":
            items = data.get("items", [])
            for item in items:
                ref_name = item.get("reference_name")
                ref_type = item.get("reference_type")

                if ref_type and ref_name and frappe.db.exists(ref_type, ref_name):
                    updates = {}
                    meta = frappe.get_meta(ref_type)

                    if "invoiced" in [d.fieldname for d in meta.fields]:
                        updates["invoiced"] = 1

                    if "billing_status" in [d.fieldname for d in meta.fields]:
                        updates["billing_status"] = "Completed"

                    if updates:
                        frappe.db.set_value(ref_type, ref_name, updates)

        frappe.db.commit()

        return {
            "message": "Sales Invoice updated successfully",
            "success": True,
            "data": doc.as_dict()
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Update Sales Invoice")
        return {"message": str(e), "success": False}

