import frappe
import json
import base64
from frappe.utils.password import get_decrypted_password
from frappe.utils import flt
from frappe.utils import today

from frappe import _
from frappe.utils import cint
from frappe.exceptions import DoesNotExistError, ValidationError

# ------------------ AUTH ------------------
def authenticate_user():
    auth = frappe.get_request_header("Authorization")
    if not auth or not auth.startswith("Basic "):
        frappe.local.response["http_status_code"] = 401
        return None
    try:
        decoded = base64.b64decode(auth.split("Basic ")[1]).decode()
        api_key, api_secret = decoded.split(":")
        user = frappe.db.get("User", {"api_key": api_key})
        if not user:
            raise
        real = get_decrypted_password("User", user.name, "api_secret")
        if real != api_secret:
            raise
        return user
    except:
        frappe.local.response["http_status_code"] = 401
        return None
    
# -----------------------------------------------------------------------------------------


@frappe.whitelist(allow_guest=True)
def createPurchaseReceipt():
    if frappe.request.method != "POST":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only POST method allowed"}

    if not authenticate_user():
        return {"error": "Unauthorized"}

    data = frappe.request.get_json()
    try:
        doc = frappe.new_doc("Purchase Receipt")
        doc.update(data)
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
        return {"message": "Purchase Receipt created successfully", "name": doc.name}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Create Purchase Receipt API")
        return {"error": str(e)}
    

# ✅ GET all Purchase Receipts
@frappe.whitelist(allow_guest=False)
def get_all_purchase_receipts():
    """Fetch all Purchase Receipts"""
    if not authenticate_user():
        return {"message": "Unauthorized", "success": False}

    try:
        receipts = frappe.get_all(
            "Purchase Receipt",
            fields=[
                "name",
                "supplier",
                "posting_date",
                "status",
                "company",
                "total",
                "total_taxes_and_charges",
                "grand_total",
                "rounded_total",
                "in_words",
                "currency",
                "docstatus"
            ],
            order_by="creation desc"
        )

        return {
            "status": "success",
            "count": len(receipts),
            "data": receipts
        }

    except Exception as e:
        frappe.log_error(message=str(e), title="Purchase Receipt API Error")
        frappe.local.response["http_status_code"] = 500
        return {"error": str(e)}


# ✅ GET Purchase Receipt by ID
@frappe.whitelist(allow_guest=False)
def get_purchase_receipt_by_id(name=None):

    """Fetch Purchase Receipt by name (ID)"""
    if not authenticate_user():
        return {"message": "Unauthorized", "success": False}

    if not name:
        frappe.local.response["http_status_code"] = 400
        return {"error": "Missing required parameter: name"}

    try:
        doc = frappe.get_doc("Purchase Receipt", name)
        data = doc.as_dict()

        return {
            "status": "success",
            "data": data
        }

    except frappe.DoesNotExistError:
        frappe.local.response["http_status_code"] = 404
        return {"error": f"Purchase Receipt {name} not found"}
    except Exception as e:
        frappe.log_error(message=str(e), title="Purchase Receipt Get By ID API Error")
        frappe.local.response["http_status_code"] = 500
        return {"error": str(e)}
    


@frappe.whitelist(allow_guest=False, methods=["POST"])
def submit_purchase_receipt():
    """Submit a Purchase Receipt by its name (ID) — via POST"""
    # ✅ Authenticate user
    if not authenticate_user():
        frappe.local.response["http_status_code"] = 401
        return {"success": False, "message": "Unauthorized access"}

    try:
        # ✅ Parse request JSON body
        data = frappe.request.get_json()
        if not data:
            frappe.local.response["http_status_code"] = 400
            return {"success": False, "message": "Missing request body"}

        name = data.get("name")

        # ✅ Validate required field
        if not name:
            frappe.local.response["http_status_code"] = 400
            return {"success": False, "message": "Missing required field: name"}

        # ✅ Fetch document
        if not frappe.db.exists("Purchase Receipt", name):
            frappe.local.response["http_status_code"] = 404
            return {"success": False, "message": f"Purchase Receipt {name} not found"}

        doc = frappe.get_doc("Purchase Receipt", name)

        # ✅ Check if already submitted
        if cint(doc.docstatus) == 1:
            return {"success": False, "message": f"Purchase Receipt {name} is already submitted"}

        # ✅ Submit document
        doc.submit()
        frappe.db.commit()

        return {
            "success": True,
            "message": f"Purchase Receipt {name} has been successfully submitted",
            "data": {"name": doc.name, "docstatus": doc.docstatus}
        }

    except ValidationError as ve:
        frappe.local.response["http_status_code"] = 422
        return {"success": False, "message": f"Validation Error: {str(ve)}"}

    except DoesNotExistError:
        frappe.local.response["http_status_code"] = 404
        return {"success": False, "message": f"Purchase Receipt {name} not found"}

    except Exception as e:
        frappe.log_error(message=str(e), title="Purchase Receipt Submit API Error")
        frappe.local.response["http_status_code"] = 500
        return {"success": False, "message": str(e)}


@frappe.whitelist(allow_guest=True)
def create_receipt_from_order():
    """Create a Purchase Receipt automatically from a given Purchase Order"""
    if frappe.request.method != "POST":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only POST method allowed"}

    # ✅ Authentication check
    if not authenticate_user():
        frappe.local.response["http_status_code"] = 401
        return {"error": "Unauthorized"}

    # ✅ Parse JSON body
    data = frappe.request.get_json()
    order_name = data.get("name")

    if not order_name:
        frappe.local.response["http_status_code"] = 400
        return {"error": "Missing required parameter: 'name'"}

    try:
        # ✅ Check if Purchase Order exists
        if not frappe.db.exists("Purchase Order", order_name):
            frappe.local.response["http_status_code"] = 404
            return {"error": f"Purchase Order '{order_name}' not found"}

        # ✅ Load Purchase Order
        po = frappe.get_doc("Purchase Order", order_name)

        # ✅ Create new Purchase Receipt
        pr = frappe.new_doc("Purchase Receipt")

        # --- Copy header fields ---
        pr.company = po.company
        pr.supplier = po.supplier
        pr.supplier_name = po.supplier_name
        pr.supplier_address = getattr(po, "supplier_address", None)
        pr.buying_price_list = getattr(po, "buying_price_list", None)
        pr.currency = po.currency
        pr.conversion_rate = po.conversion_rate
        pr.posting_date = frappe.utils.nowdate()
        pr.schedule_date = frappe.utils.nowdate()
        pr.taxes_and_charges = getattr(po, "taxes_and_charges", None)
        pr.shipping_rule = getattr(po, "shipping_rule", None)

        # --- Copy contact & address info ---
        pr.address_display = getattr(po, "address_display", None)
        pr.contact_display = getattr(po, "contact_display", None)
        pr.contact_email = getattr(po, "contact_email", None)
        pr.contact_mobile = getattr(po, "contact_mobile", None)
        pr.tax_category = getattr(po, "tax_category", None)
        pr.tax_id = getattr(po, "tax_id", None)

        # ✅ Copy items from Purchase Order
        for item in po.items:
            pr.append("items", {
                "item_code": item.item_code,
                "item_name": item.item_name,
                "description": item.description,
                "qty": item.qty - item.received_qty if item.received_qty else item.qty,
                "uom": item.uom,
                "rate": item.rate,
                "amount": item.amount,
                "warehouse": item.warehouse,
                "purchase_order": po.name,
                "po_detail": item.name,
                "cost_center": item.cost_center,
                "expense_account": item.expense_account or "Stock Received But Not Billed - " + po.company_abbr
            })

        # ✅ Copy taxes (if any)
        if getattr(po, "taxes", None):
            for tax in po.taxes:
                pr.append("taxes", {
                    "charge_type": tax.charge_type,
                    "account_head": tax.account_head,
                    "description": tax.description,
                    "rate": tax.rate,
                    "tax_amount": tax.tax_amount,
                    "cost_center": tax.cost_center,
                    "add_deduct_tax": tax.add_deduct_tax,
                    "category": tax.category,
                })

        # ✅ Calculate totals automatically
        pr.run_method("set_missing_values")
        pr.run_method("calculate_taxes_and_totals")

        # ✅ Save document
        pr.insert(ignore_permissions=True)
        frappe.db.commit()

        return {
            "message": f"Purchase Receipt created successfully from Purchase Order {order_name}",
            "purchase_receipt": pr.name
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Create Purchase Receipt from Order API")
        frappe.local.response["http_status_code"] = 500
        return {"error": str(e)}



