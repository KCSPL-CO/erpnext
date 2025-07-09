import frappe
import json
import base64
from frappe.utils.password import get_decrypted_password
from frappe.utils import flt
from frappe.utils import today

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
def get_payment_summary_by_mode():
    if frappe.request.method != "GET":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only GET method allowed"}

    user = authenticate_user()
    if not user:
        return {"error": "Unauthorized"}

    try:
        # Define expected modes
        expected_modes = ["Cash", "Cheque", "Bank Draft", "Credit Card", "Debit Card", "UPI"]

        # Fetch Payment Entries created today by this user
        payments = frappe.get_all(
            "Payment Entry",
            filters={
                "owner": user.name,
                "docstatus": 1,
                "posting_date": today()
            },
            fields=["name", "posting_date", "paid_amount", "mode_of_payment", "party"]
        )

        # Initialize summary with 0 for all expected modes
        summary = {mode: 0.0 for mode in expected_modes}
        payment_list = []

        for entry in payments:
            mop = entry.mode_of_payment
            if mop in summary:
                summary[mop] += entry.paid_amount
            else:
                summary[mop] = entry.paid_amount  # Optional: handle unexpected modes too

            payment_list.append({
                "name": entry.name,
                "posting_date": entry.posting_date,
                "paid_amount": entry.paid_amount,
                "mode_of_payment": entry.mode_of_payment,
                "party": entry.party
            })

        summary["payment_list"] = payment_list

        return {
            "message": f"Payment summary for user {user.name}",
            "data": [summary]
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "get_payment_summary_by_mode API")
        return {"error": str(e)}

# ------------------ CREATE (POST) ------------------
@frappe.whitelist()
def get_party_and_account_balance(
	 date, paid_from=None, paid_to=None, ptype=None, pty=None, cost_center=None
):
	return frappe._dict(
		{
			"party_balance": get_balance_on(party_type=ptype, party=pty, cost_center=cost_center),
			"paid_from_account_balance": get_balance_on(paid_from, date, cost_center=cost_center),
			"paid_to_account_balance": get_balance_on(paid_to, date=date, cost_center=cost_center),
		}
	)
@frappe.whitelist()
def fetch_customer_advances(sales_invoice_name):
    doc = frappe.get_doc("Sales Invoice", sales_invoice_name)
    doc.set_advances()
    return {"advances": doc.advances}

@frappe.whitelist()
def get_customer_advances(customer):
    """Return all unallocated advances (Payment Entries) for the given customer."""

    if not customer:
        frappe.throw("Customer is required")

    payment_entries = frappe.db.get_all(
        "Payment Entry",
        filters={
            "party_type": "Customer",
            "party": customer,
            "docstatus": 1,
            "unallocated_amount": [">", 0],
            "payment_type": ["in", ["Receive", "Internal Transfer"]],
        },
        fields=[
            "name as reference_name",
            "'Payment Entry' as reference_type",
            "paid_amount as advance_amount",
            "0 as allocated_amount",
            "posting_date as difference_posting_date",
            "remarks"
        ]
    )

    for entry in payment_entries:
        entry["idx"] = payment_entries.index(entry) + 1
        entry["doctype"] = "Sales Invoice Advance"
        entry["exchange_gain_loss"] = 0
        entry["ref_exchange_rate"] = 1
        entry["__islocal"] = 1

    return payment_entries


@frappe.whitelist(allow_guest=False)
def get_advances_for_customer(customer, company=None):
    if not customer:
        frappe.throw("Parameter `customer` is required.")

    filters = {
        "party": customer,
        "docstatus": 0
    }
    if company:
        filters["company"] = company

    entries = frappe.get_all(
        "Sales Invoice Advance",
        fields=[
            "docstatus", "idx", "reference_type", "reference_name",
            "advance_amount", "allocated_amount", "exchange_gain_loss",
            "difference_posting_date", "remarks"
        ],
        filters=filters,
        order_by="idx asc"
    )

    # Ensure numeric types are correct
    for entry in entries:
        entry["advance_amount"] = flt(entry["advance_amount"])
        entry["allocated_amount"] = flt(entry["allocated_amount"])
        entry["exchange_gain_loss"] = flt(entry["exchange_gain_loss"])

    return {"advances": entries}
@frappe.whitelist(allow_guest=False)
def create_payment_entry():
    if frappe.request.method != "POST":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Use POST"}
    if not authenticate_user():
        return {"success": False, "message": "Unauthorized"}

    data = json.loads(frappe.request.data or "{}")
    doc = frappe.new_doc("Payment Entry")
    _set_fields(doc, data)

    doc.insert()
    doc.submit()
    frappe.db.commit()
    return {"success": True, "name": doc.name, "message": "Created"}

# ------------------ READ ALL (GET) ------------------
@frappe.whitelist(allow_guest=False)
def get_all_payment_entries():
    if frappe.request.method != "GET":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Use GET"}
    if not authenticate_user():
        return {"success": False, "message": "Unauthorized"}

    entries = frappe.db.get_all("Payment Entry", fields=["name", "posting_date", "payment_type", "paid_amount", "party"])
    return {"success": True, "data": entries}

# ------------------ READ BY ID (GET) ------------------
@frappe.whitelist(allow_guest=False)
def get_payment_entry_by_id(name):
    if frappe.request.method != "GET":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Use GET"}
    if not authenticate_user():
        return {"success": False, "message": "Unauthorized"}

    doc = frappe.get_doc("Payment Entry", name)
    return {"success": True, "data": doc.as_dict()}

# ------------------ UPDATE (PUT) ------------------
@frappe.whitelist(allow_guest=False)
def update_payment_entry(name):
    if frappe.request.method not in ("PUT", "POST"):
        frappe.local.response["http_status_code"] = 405
        return {"error": "Use PUT/POST"}
    if not authenticate_user():
        return {"success": False, "message": "Unauthorized"}

    data = json.loads(frappe.request.data or "{}")
    doc = frappe.get_doc("Payment Entry", name)
    if doc.docstatus != 0:
        frappe.local.response["http_status_code"] = 400
        return {"success": False, "message": "Can only update Draft"}
    _set_fields(doc, data)
    doc.save()
    frappe.db.commit()
    return {"success": True, "message": "Updated"}

# ------------------ DELETE (DELETE) ------------------
@frappe.whitelist(allow_guest=False)
def delete_payment_entry(name):
    if frappe.request.method != "DELETE":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Use DELETE"}
    if not authenticate_user():
        return {"success": False, "message": "Unauthorized"}

    doc = frappe.get_doc("Payment Entry", name)
    if doc.docstatus != 0:
        frappe.local.response["http_status_code"] = 400
        return {"success": False, "message": "Can only delete Draft"}
    doc.delete()
    frappe.db.commit()
    return {"success": True, "message": "Deleted"}

# ------------------ CANCEL (POST) ------------------
@frappe.whitelist(allow_guest=False)
def cancel_payment_entry(name):
    if frappe.request.method != "POST":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Use POST"}
    if not authenticate_user():
        return {"success": False, "message": "Unauthorized"}

    doc = frappe.get_doc("Payment Entry", name)
    if doc.docstatus != 1:
        frappe.local.response["http_status_code"] = 400
        return {"success": False, "message": "Only Submitted entries can be cancelled"}
    doc.cancel()
    frappe.db.commit()
    return {"success": True, "message": "Cancelled"}

# --------------- UTILITY -----------------
def _set_fields(doc, data):
    for field in ("payment_type", "posting_date", "company", "paid_from", "paid_to", "paid_amount",
                  "received_amount", "party_type", "party", "mode_of_payment", "reference_no",
                  "reference_date", "remarks", "cost_center", "project"):
        if data.get(field) is not None:
            setattr(doc, field, data.get(field))
    if data.get("references"):
        doc.set("references", [])
        for r in data["references"]:
            doc.append("references", {
                "reference_doctype": r.get("reference_doctype"),
                "reference_name": r.get("reference_name"),
                "due_date": r.get("due_date"),
                "total_amount": r.get("total_amount"),
                "outstanding_amount": r.get("outstanding_amount"),
                "allocated_amount": r.get("allocated_amount"),
                "exchange_rate": r.get("exchange_rate"),
                "account": r.get("account"),
            })
