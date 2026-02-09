import frappe
from frappe import _
import base64
from frappe.utils import today
from frappe.exceptions import DoesNotExistError, ValidationError
from frappe.utils import cint

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
        current_date = frappe.utils.today()

        # 🔹 Total (all-time) status-wise counts with amount
        total_status_counts = frappe.db.sql("""
            SELECT status, COUNT(*) AS count, SUM(grand_total) AS amount
            FROM `tabPurchase Invoice`
            WHERE docstatus = 1
            GROUP BY status
        """, as_dict=True)

        total_summary = {}
        for row in total_status_counts:
            total_summary[row.status] = {
                "count": row.count,
                "amount": float(row.amount or 0.0)
            }

        # 🔹 Today's status-wise counts with amount
        today_status_counts = frappe.db.sql("""
            SELECT status, COUNT(*) AS count, SUM(grand_total) AS amount
            FROM `tabPurchase Invoice`
            WHERE docstatus = 1 AND posting_date = %s
            GROUP BY status
        """, (current_date,), as_dict=True)

        today_summary = {}
        for row in today_status_counts:
            today_summary[row.status] = {
                "count": row.count,
                "amount": float(row.amount or 0.0)
            }

        # 🔹 Today item purchases
        item_summary = frappe.db.sql("""
            SELECT COUNT(DISTINCT pii.item_code) AS item_count,
                   SUM(pii.amount) AS total_purchase_value
            FROM `tabPurchase Invoice Item` pii
            JOIN `tabPurchase Invoice` pi ON pi.name = pii.parent
            WHERE pi.docstatus = 1 AND pi.posting_date = %s
        """, (current_date,), as_dict=True)[0]

        # 🔹 Invoice details (last 10 modified invoices)
        invoice_details = frappe.db.sql("""
            SELECT name, supplier, status, posting_date, grand_total
            FROM `tabPurchase Invoice`
            WHERE docstatus = 1
            ORDER BY modified DESC
            LIMIT 10
        """, as_dict=True)

        return {
            "message": {
                "invoice_status_summary": {
                    "total": total_summary,
                    "today": today_summary
                },
                "today_item_purchases": {
                    "item_count": item_summary.item_count or 0,
                    "total_purchase_value": float(item_summary.total_purchase_value or 0.0)
                },
                "invoice_details": invoice_details
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
    

@frappe.whitelist(allow_guest=True)
def createPurchaseInvoice():
    if frappe.request.method != "POST":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only POST method allowed"}

    if not authenticate_user():
        return {"error": "Unauthorized"}

    data = frappe.request.get_json()

    try:
        # Create a new Purchase Invoice
        doc = frappe.new_doc("Purchase Invoice")
        doc.update(data)

        # --- Auto fetch taxes and charges from Purchase Taxes and Charges Template ---
        if data.get("taxes_and_charges"):
            template_name = data["taxes_and_charges"]
            if frappe.db.exists("Purchase Taxes and Charges Template", template_name):
                template = frappe.get_doc("Purchase Taxes and Charges Template", template_name)
                doc.taxes = []
                for t in template.taxes:
                    doc.append("taxes", {
                        "charge_type": t.charge_type,
                        "account_head": t.account_head,
                        "description": t.description,
                        "rate": t.rate,
                        "tax_amount": t.tax_amount,
                        "cost_center": t.cost_center
                    })
            else:
                frappe.log_error(f"Template {template_name} not found", "Purchase Invoice Tax Fetch Error")

        # --- Apply Shipping Rule automatically ---
        if data.get("shipping_rule"):
            shipping_rule_name = data["shipping_rule"]
            if frappe.db.exists("Shipping Rule", shipping_rule_name):
                shipping_rule = frappe.get_doc("Shipping Rule", shipping_rule_name)
                doc.shipping_rule = shipping_rule_name
               
                
                shipping_amount = 0
                if not shipping_amount and hasattr(shipping_rule, "shipping_amount"):
                    shipping_amount = shipping_rule.shipping_amount

                if shipping_amount:
                    doc.append("taxes", {
                        "charge_type": "Actual",
                        "description": "Shipping Charges",
                        "account_head": shipping_rule.account,
                        "tax_amount": shipping_amount
                    })
            else:
                frappe.log_error(f"Shipping Rule {shipping_rule_name} not found", "Purchase Invoice Shipping Rule Error")

        # Insert and commit
        doc.insert(ignore_permissions=True)
        frappe.db.commit()

        return {"message": "Purchase Invoice created successfully", "name": doc.name}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Create Purchase Invoice API")
        return {"error": str(e)}


@frappe.whitelist(allow_guest=True)
def create_invoice_from_receipt():
    """Create Purchase Invoice automatically from a given Purchase Receipt"""
    if frappe.request.method != "POST":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only POST method allowed"}

    # Authentication check (you already have this helper)
    if not authenticate_user():
        return {"error": "Unauthorized"}

    data = frappe.request.get_json()
    receipt_id = data.get("purchase_receipt")

    if not receipt_id:
        return {"error": "Missing 'purchase_receipt' parameter"}

    try:
        # Check if receipt exists
        if not frappe.db.exists("Purchase Receipt", receipt_id):
            return {"error": f"Purchase Receipt '{receipt_id}' not found"}

        # Load the Purchase Receipt document
        pr = frappe.get_doc("Purchase Receipt", receipt_id)

        # Create Purchase Invoice from it
        pi = frappe.new_doc("Purchase Invoice")

        # Copy relevant fields
        pi.company = pr.company
        pi.supplier = pr.supplier
        pi.supplier_name = pr.supplier_name
        pi.supplier_address = pr.supplier_address
        pi.buying_price_list = pr.buying_price_list
        pi.currency = pr.currency
        pi.conversion_rate = pr.conversion_rate
        pi.credit_to = frappe.db.get_value("Company", pr.company, "default_payable_account")
        pi.posting_date = frappe.utils.nowdate()
        pi.due_date = frappe.utils.nowdate()
        pi.taxes_and_charges = pr.get("taxes_and_charges")
        pi.shipping_rule = pr.get("shipping_rule")

        # Copy address & contact info if available
        pi.address_display = pr.get("address_display")
        pi.contact_display = pr.get("contact_display")
        pi.contact_email = pr.get("contact_email")
        pi.contact_mobile = pr.get("contact_mobile")
        pi.tax_category = pr.get("tax_category")
        pi.tax_id = pr.get("tax_id")

        # Copy items from Purchase Receipt
        for item in pr.items:
            pi.append("items", {
                "item_code": item.item_code,
                "item_name": item.item_name,
                "description": item.description,
                "qty": item.qty,
                "uom": item.uom,
                "rate": item.rate,
                "amount": item.amount,
                "warehouse": item.warehouse,
                "expense_account": item.expense_account or "Stock Received But Not Billed - " + pr.company_abbr,
                "cost_center": item.cost_center,
                "purchase_receipt": pr.name,
                "pr_detail": item.name,
            })

        # Copy taxes (if Purchase Receipt has any)
        for tax in pr.taxes:
            pi.append("taxes", {
                "charge_type": tax.charge_type,
                "account_head": tax.account_head,
                "description": tax.description,
                "rate": tax.rate,
                "tax_amount": tax.tax_amount,
                "cost_center": tax.cost_center,
                "add_deduct_tax": tax.add_deduct_tax,
                "category": tax.category,
            })

        # Auto calculate totals
        pi.run_method("set_missing_values")
        pi.run_method("calculate_taxes_and_totals")

        # Insert and commit
        pi.insert(ignore_permissions=True)
        frappe.db.commit()

        return {
            "message": f"Purchase Invoice created successfully from {receipt_id}",
            "purchase_invoice": pi.name
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Create Purchase Invoice from Receipt API")
        return {"error": str(e)}




# ✅ GET Purchase Invoice by ID
@frappe.whitelist(allow_guest=False)
def get_purchase_invoice_by_id(name=None):
    """Fetch Purchase Invoice by name (ID)"""
    if not authenticate_user():
        return {"message": "Unauthorized", "success": False}

    if not name:
        frappe.local.response["http_status_code"] = 400
        return {"error": "Missing required parameter: name"}

    try:
        doc = frappe.get_doc("Purchase Invoice", name)
        data = doc.as_dict()

        return {
            "status": "success",
            "data": data
        }

    except frappe.DoesNotExistError:
        frappe.local.response["http_status_code"] = 404
        return {"error": f"Purchase Invoice {name} not found"}

    except Exception as e:
        frappe.log_error(message=str(e), title="Purchase Invoice Get By ID API Error")
        frappe.local.response["http_status_code"] = 500
        return {"error": str(e)}


# ✅ POST — Submit Purchase Invoice
@frappe.whitelist(allow_guest=False, methods=["POST"])
def submit_purchase_invoice():
    """Submit a Purchase Invoice by its name (ID) — via POST"""
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
        if not frappe.db.exists("Purchase Invoice", name):
            frappe.local.response["http_status_code"] = 404
            return {"success": False, "message": f"Purchase Invoice {name} not found"}

        doc = frappe.get_doc("Purchase Invoice", name)

        # ✅ Check if already submitted
        if cint(doc.docstatus) == 1:
            return {"success": False, "message": f"Purchase Invoice {name} is already submitted"}

        # ✅ Submit document
        doc.submit()
        frappe.db.commit()

        return {
            "success": True,
            "message": f"Purchase Invoice {name} has been successfully submitted",
            "data": {"name": doc.name, "docstatus": doc.docstatus}
        }

    except ValidationError as ve:
        frappe.local.response["http_status_code"] = 422
        return {"success": False, "message": f"Validation Error: {str(ve)}"}

    except DoesNotExistError:
        frappe.local.response["http_status_code"] = 404
        return {"success": False, "message": f"Purchase Invoice {name} not found"}

    except Exception as e:
        frappe.log_error(message=str(e), title="Purchase Invoice Submit API Error")
        frappe.local.response["http_status_code"] = 500
        return {"success": False, "message": str(e)}


@frappe.whitelist(allow_guest=True)
def create_invoice_from_source():
    """Create Purchase Invoice automatically from a given Purchase Receipt or Purchase Order"""
    if frappe.request.method != "POST":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only POST method allowed"}

    # ✅ Authentication check
    if not authenticate_user():
        return {"error": "Unauthorized"}

    data = frappe.request.get_json()
    source_name = data.get("name")
    source_doctype = data.get("doctype")

    if not source_name or not source_doctype:
        frappe.local.response["http_status_code"] = 400
        return {"error": "Missing required fields: 'name' and 'doctype'"}

    if source_doctype not in ["Purchase Receipt", "Purchase Order"]:
        frappe.local.response["http_status_code"] = 400
        return {"error": "Invalid doctype. Only 'Purchase Receipt' or 'Purchase Order' allowed."}

    try:
        # ✅ Check if source document exists
        if not frappe.db.exists(source_doctype, source_name):
            return {"error": f"{source_doctype} '{source_name}' not found"}

        # ✅ Load the source document
        source_doc = frappe.get_doc(source_doctype, source_name)

        # ✅ Create a new Purchase Invoice
        pi = frappe.new_doc("Purchase Invoice")

        # --- Copy header details ---
        pi.company = source_doc.company
        pi.supplier = source_doc.supplier
        pi.supplier_name = source_doc.supplier_name
        pi.supplier_address = source_doc.supplier_address
        pi.buying_price_list = getattr(source_doc, "buying_price_list", None)
        pi.currency = source_doc.currency
        pi.conversion_rate = source_doc.conversion_rate
        pi.credit_to = frappe.db.get_value("Company", source_doc.company, "default_payable_account")
        pi.posting_date = frappe.utils.nowdate()
        pi.due_date = frappe.utils.nowdate()
        pi.taxes_and_charges = getattr(source_doc, "taxes_and_charges", None)
        pi.shipping_rule = getattr(source_doc, "shipping_rule", None)

        # --- Copy contact info ---
        pi.address_display = getattr(source_doc, "address_display", None)
        pi.contact_display = getattr(source_doc, "contact_display", None)
        pi.contact_email = getattr(source_doc, "contact_email", None)
        pi.contact_mobile = getattr(source_doc, "contact_mobile", None)
        pi.tax_category = getattr(source_doc, "tax_category", None)
        pi.tax_id = getattr(source_doc, "tax_id", None)

        # ✅ Copy items depending on source doctype
        if source_doctype == "Purchase Receipt":
            for item in source_doc.items:
                pi.append("items", {
                    "item_code": item.item_code,
                    "item_name": item.item_name,
                    "description": item.description,
                    "qty": item.qty,
                    "uom": item.uom,
                    "rate": item.rate,
                    "amount": item.amount,
                    "warehouse": item.warehouse,
                    "expense_account": item.expense_account or "Stock Received But Not Billed - " + source_doc.company_abbr,
                    "cost_center": item.cost_center,
                    "purchase_receipt": source_doc.name,
                    "pr_detail": item.name,
                })

        elif source_doctype == "Purchase Order":
            for item in source_doc.items:
                pi.append("items", {
                    "item_code": item.item_code,
                    "item_name": item.item_name,
                    "description": item.description,
                    "qty": item.qty,
                    "uom": item.uom,
                    "rate": item.rate,
                    "amount": item.amount,
                    "warehouse": item.warehouse,
                    "expense_account": item.expense_account or "Stock Received But Not Billed - " + source_doc.company_abbr,
                    "cost_center": item.cost_center,
                    "purchase_order": source_doc.name,
                    "po_detail": item.name,
                })

        # ✅ Copy taxes (if any)
        if getattr(source_doc, "taxes", None):
            for tax in source_doc.taxes:
                pi.append("taxes", {
                    "charge_type": tax.charge_type,
                    "account_head": tax.account_head,
                    "description": tax.description,
                    "rate": tax.rate,
                    "tax_amount": tax.tax_amount,
                    "cost_center": tax.cost_center,
                    "add_deduct_tax": tax.add_deduct_tax,
                    "category": tax.category,
                })

        # ✅ Auto calculate totals & taxes
        pi.run_method("set_missing_values")
        pi.run_method("calculate_taxes_and_totals")

        # ✅ Save & commit
        pi.insert(ignore_permissions=True)
        frappe.db.commit()

        return {
            "message": f"Purchase Invoice created successfully from {source_doctype} {source_name}",
            "purchase_invoice": pi.name
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Create Purchase Invoice from Source API")
        frappe.local.response["http_status_code"] = 500
        return {"error": str(e)}

@frappe.whitelist(allow_guest=True)
def purchase_invoices_list():
    if frappe.request.method != "GET":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only GET method allowed"}

    if not authenticate_user():
        return {"error": "Unauthorized"}

    try:
        invoices = frappe.get_all(
            "Purchase Invoice",
            fields=[
                "title","name", "supplier", "posting_date", "due_date", "is_paid",
                "grand_total", "currency", "status", "company"
            ],
            order_by="posting_date desc",
        )
        return {"message": invoices}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "List Purchase Invoice API")
        frappe.local.response["http_status_code"] = 500
        return {"error": str(e)}
