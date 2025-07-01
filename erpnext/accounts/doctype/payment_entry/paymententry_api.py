import frappe
from frappe import _
import base64
from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
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

# List 
@frappe.whitelist(allow_guest=True)
def listSalesInvoices():
    if frappe.request.method != "GET":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only GET method allowed"}

    if not authenticate_user():
        return {"error": "Unauthorized"}

    try:
        sales_invoices = frappe.get_all(
            "Sales Invoice",
            fields=[
                "name", "customer", "patient", "patient_name", "modified",
                "posting_date", "due_date", "status", "grand_total", "currency"
            ],
            order_by="posting_date desc",
            # limit_page_length=20
        )
        return {"message": sales_invoices}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "List Sales Invoice API")
        frappe.local.response["http_status_code"] = 500
        return {"error": str(e)}
# List with Filters 
@frappe.whitelist(allow_guest=True)
def list_payment_entries():
    if frappe.request.method != "GET":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only GET method allowed"}

    user = authenticate_user()
    if not user:
        return {"error": "Unauthorized"}

    filters = {}
    series_filters = frappe.local.form_dict.get('series')
    mode_filters = frappe.local.form_dict.get('mode_of_payment')

    if series_filters:
        series_list = series_filters.split(',')
        filters['naming_series'] = ['in', series_list]

    if mode_filters:
        modes = mode_filters.split(',')
        filters['mode_of_payment'] = ['in', modes]

    payment_entries = frappe.get_all(
        "Payment Entry",
        filters=filters,
        fields=[
            "name", "posting_date", "mode_of_payment", "paid_amount",
            "naming_series", "party", "party_type"
        ],
        order_by="posting_date desc",
        # limit_page_length=100
    )

    # Aggregation
    summary = {}
    total_income = 0.0
    for pe in payment_entries:
        series = pe.naming_series
        mode = pe.mode_of_payment
        amt = pe.paid_amount or 0.0

        total_income += amt
        summary.setdefault(series, {"count": 0, "modes": {}})
        summary[series]["count"] += 1
        summary[series]["modes"].setdefault(mode, {"count": 0, "sum": 0.0})
        summary[series]["modes"][mode]["count"] += 1
        summary[series]["modes"][mode]["sum"] += amt

    return {
        "payment_entries": payment_entries,
        "summary": summary,
        "total_income": total_income,
        "entry_count": len(payment_entries)
    }

# Details 
@frappe.whitelist(allow_guest=True)
def getPaymentEntryDetails(payment_id=None):
    if frappe.request.method != "GET":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only GET method allowed"}

    if not authenticate_user():
        return {"error": "Unauthorized"}

    if not payment_id:
        frappe.local.response["http_status_code"] = 400
        return {"error": "Missing 'payment_id' parameter"}

    try:
        payment = frappe.get_doc("Payment Entry", payment_id)
        return {"payment_entry": payment.as_dict()}
    except frappe.DoesNotExistError:
        frappe.local.response["http_status_code"] = 404
        return {"error": f"Payment Entry '{payment_id}' not found"}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Payment Entry Details API")
        frappe.local.response["http_status_code"] = 500
        return {"error": str(e)}


# Create
# @frappe.whitelist(allow_guest=True)
# def createPaymentEntry():
#     if frappe.request.method != "POST":
#         frappe.local.response["http_status_code"] = 405
#         return {"error": "Only POST method allowed"}

#     user = authenticate_user()
#     if not user:
#         return {"error": "Unauthorized"}

#     try:
#         data = frappe.local.form_dict

#         # Validate required fields
#         required_fields = ["party", "payment_type", "paid_amount", "mode_of_payment", "posting_date", "reference_type", "reference_name"]
#         for field in required_fields:
#             if not data.get(field):
#                 frappe.local.response["http_status_code"] = 400
#                 return {"error": f"Missing field: {field}"}

#         # Create the Payment Entry document
#         pe = frappe.new_doc("Payment Entry")
#         pe.payment_type = data.get("payment_type")                   # "Receive" or "Pay"
#         pe.party_type = "Customer" if data.get("payment_type") == "Receive" else "Supplier"
#         pe.party = data.get("party")                                 # Customer/Supplier name
#         pe.posting_date = data.get("posting_date")                   # e.g. "2025-06-13"
#         pe.mode_of_payment = data.get("mode_of_payment")             # e.g. "Cash", "Bank"
#         pe.paid_amount = float(data.get("paid_amount"))
#         pe.received_amount = float(data.get("paid_amount"))
#         pe.company = data.get("company", frappe.defaults.get_user_default("Company"))
#         pe.paid_from = data.get("paid_from") if pe.payment_type == "Receive" else None
#         pe.paid_to = data.get("paid_to") if pe.payment_type == "Pay" else None

#         # Add reference if provided
#         reference_type = data.get("reference_type")  # e.g. "Sales Invoice"
#         reference_name = data.get("reference_name")  # e.g. "SINV-0001"
#         if reference_type and reference_name:
#             pe.append("references", {
#                 "reference_doctype": reference_type,
#                 "reference_name": reference_name,
#                 "allocated_amount": float(data.get("paid_amount"))
#             })

#         # Optional: remarks
#         if data.get("remarks"):
#             pe.remarks = data.get("remarks")

#         # Save and submit
#         pe.insert(ignore_permissions=True)
#         pe.submit()

#         return {"message": "Payment Entry created successfully", "payment_entry": pe.name}

#     except Exception as e:
#         frappe.log_error(frappe.get_traceback(), "Create Payment Entry API")
#         frappe.local.response["http_status_code"] = 500
#         return {"error": str(e)}

# --- Create Payment Entry API ---
@frappe.whitelist(allow_guest=True)
def createPaymentEntry():
    if frappe.request.method != "POST":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only POST method allowed"}

    if not authenticate_user():
        return {"error": "Unauthorized"}

    try:
        data = frappe.request.get_json()

        party = data.get("party")
        payment_type = data.get("payment_type")
        paid_amount = data.get("paid_amount")
        posting_date = data.get("posting_date")
        mode_of_payment = data.get("mode_of_payment")
        reference_type = data.get("reference_type")
        reference_name = data.get("reference_name")
        remarks = data.get("remarks")

        if not all([party, payment_type, paid_amount, posting_date, mode_of_payment]):
            frappe.local.response["http_status_code"] = 400
            return {"error": "Missing required fields"}

        # Get customer details
        party_name = frappe.db.get_value("Customer", {"name": party}, "customer_name")
        if not party_name:
            frappe.throw(_("Customer not found"))

        # Set default naming series
        naming_series = "ACC-PAY-.YYYY.-"
        if reference_type == "Sales Invoice" and reference_name:
            if reference_name.startswith("LAB-SINV-"):
                naming_series = "ACC-LAB-PAY-.YYYY.-"
            elif reference_name.startswith("DRUG-SINV-"):
                naming_series = "ACC-DRUG-PAY-.YYYY.-"
            elif reference_name.startswith("SERV-SINV-"):
                naming_series = "ACC-SERV-PAY-.YYYY.-"
            elif reference_name.startswith("CONS-SINV-"):
                naming_series = "ACC-CONS-PAY-.YYYY.-"
            elif reference_name.startswith("RAW-SINV-"):
                naming_series = "ACC-RAW-PAY-.YYYY.-"
            elif reference_name.startswith("PROD-SINV-"):
                naming_series = "ACC-PROD-PAY-.YYYY.-"
            elif reference_name.startswith("SUB-SINV-"):
                naming_series = "ACC-SUB-PAY-.YYYY.-"
            elif reference_name.startswith("DEMO-SINV-"):
                naming_series = "ACC-DEMO-PAY-.YYYY.-"

        # Create payment entry
        pe = frappe.new_doc("Payment Entry")
        pe.naming_series = naming_series
        pe.payment_type = payment_type
        pe.posting_date = posting_date
        pe.mode_of_payment = mode_of_payment
        pe.party_type = "Customer"
        pe.party = party
        pe.party_name = party_name
        pe.paid_amount = paid_amount
        pe.received_amount = paid_amount
        pe.remarks = remarks
        pe.company = frappe.defaults.get_user_default("Company") or "HIMS (Demo)"

        # Get default accounts
        pe.paid_from = frappe.db.get_value("Account", {"account_type": "Receivable", "company": pe.company}, "name")
        pe.paid_to = frappe.db.get_value("Account", {"account_type": "Cash", "company": pe.company}, "name")

        if not pe.paid_from or not pe.paid_to:
            frappe.throw(_("Default Cash or Receivable account not found."))

        # Link reference (if any)
        if reference_type and reference_name:
            pe.append("references", {
                "reference_doctype": reference_type,
                "reference_name": reference_name,
                "allocated_amount": paid_amount
            })

        pe.insert(ignore_permissions=True)
        pe.submit()

        return {"message": "Payment Entry created", "payment_entry": pe.name}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Create Payment Entry API")
        frappe.local.response["http_status_code"] = 500
        return {"error": str(e)}
