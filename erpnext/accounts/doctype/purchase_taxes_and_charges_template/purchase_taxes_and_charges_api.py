import frappe
import json
import base64
from frappe.utils.password import get_decrypted_password


# --------------------------
# ✅ Authentication Method
# --------------------------
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
    if not user:
        frappe.local.response["http_status_code"] = 401
        return None

    real_secret = get_decrypted_password("User", user.name, "api_secret")
    if real_secret != api_secret:
        frappe.local.response["http_status_code"] = 401
        return None

    return user


# --------------------------
# ✅ Create Purchase Tax (POST)
# --------------------------
@frappe.whitelist(allow_guest=True)
def create_purchase_tax_template():
    if frappe.request.method != "POST":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Method Not Allowed. Use POST."}

    if not authenticate_user():
        return {"message": "Unauthorized", "success": False}

    try:
        data = json.loads(frappe.request.data)
    except Exception:
        frappe.local.response["http_status_code"] = 400
        return {"error": "Invalid JSON payload"}

    # Create main document
    doc = frappe.new_doc("Purchase Taxes and Charges Template")

    # Allowed fields for the parent
    allowed_fields = ["title", "tax_category", "company", "is_default", "disabled"]

    for key, value in data.items():
        if key in allowed_fields:
            doc.set(key, value)

    # ✅ Add child table records (Purchase Taxes and Charges)
    if "taxes" in data and isinstance(data["taxes"], list):
        for tax in data["taxes"]:
            child = doc.append("taxes", {})

            allowed_child_fields = [
                "category",
                "add_deduct_tax",
                "charge_type",
                "row_id",
                "included_in_print_rate",
                "included_in_paid_amount",
                "account_head",
                "description",
                "is_tax_withholding_account",
                "rate",
                "cost_center",
                "account_currency",
                "tax_amount",
                "tax_amount_after_discount_amount",
                "total",
                "base_tax_amount",
                "base_total",
                "base_tax_amount_after_discount_amount",
                "item_wise_tax_detail"
            ]

            for key, value in tax.items():
                if key in allowed_child_fields:
                    child.set(key, value)

    doc.insert()
    frappe.db.commit()

    return {
        "status": "success",
        "message": "Purchase Tax record created successfully",
        "name": doc.name,
        "taxes_count": len(doc.taxes)
    }


# --------------------------
# ✅ Get All Purchase Taxes (GET)
# --------------------------
@frappe.whitelist(allow_guest=True)
def get_all_purchase_tax_templatees():
    if frappe.request.method != "GET":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Method Not Allowed. Use GET."}

    if not authenticate_user():
        return {"message": "Unauthorized", "success": False}

    taxes = frappe.get_all("Purchase Taxes and Charges Template", fields=["*"])
    return taxes


# --------------------------
# ✅ Get Purchase Tax by ID (GET)
# --------------------------
@frappe.whitelist(allow_guest=True)
def get_purchase_tax_template_by_id(name):
    if frappe.request.method != "GET":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Method Not Allowed. Use GET."}

    if not authenticate_user():
        return {"message": "Unauthorized", "success": False}

    if not frappe.db.exists("Purchase Taxes and Charges Template", name):
        frappe.local.response["http_status_code"] = 404
        return {"error": "Purchase Tax record not found"}

    doc = frappe.get_doc("Purchase Taxes and Charges Template", name)
    return doc
