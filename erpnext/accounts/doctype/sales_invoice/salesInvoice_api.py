import frappe
from frappe import _
import base64
from frappe.utils import add_days, cint, cstr, flt, formatdate, get_link_to_form, getdate, nowdate

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

from frappe.utils import today

@frappe.whitelist(allow_guest=True)
def get_sales_invoice_summary():
    if frappe.request.method != "GET":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only GET method allowed"}

    user = authenticate_user()
    if not user:
        return {"error": "Unauthorized"}

    try:
        # Fetch Sales Invoices created today with docstatus 1
        invoices = frappe.get_all(
            "Sales Invoice",
            filters={
                "docstatus": 1,
                "posting_date": today()
            },
            fields=["name", "customer", "grand_total", "posting_date"]
        )

        total_amount = sum(inv.grand_total for inv in invoices)
        invoice_count = len(invoices)

        return {
            "message": f"Sales Invoice summary for {today()}",
            "data": {
                "total_sales_invoices": invoice_count,
                "grand_total": total_amount,
                "invoice_list": invoices
            }
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "get_sales_invoice_summary API")
        return {"error": str(e)}


# 1. List Sales Invoices
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
            fields=["name", "customer","patient","patient_name","modified", "posting_date","paid_date", "due_date", "status", "grand_total", "currency"],
            order_by="posting_date desc",
            # limit_page_length=20
        )
        return {"message": sales_invoices}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "List Sales Invoice API")
        frappe.local.response["http_status_code"] = 500
        return {"error": str(e)}

# 2. Create Sales Invoice
# @frappe.whitelist(allow_guest=True)
# def createSalesInvoice():
#     if frappe.request.method != "POST":
#         frappe.local.response["http_status_code"] = 405
#         return {"error": "Only POST method allowed"}

#     if not authenticate_user():
#         return {"error": "Unauthorized"}

#     data = frappe.request.get_json()
#     try:
#         doc = frappe.new_doc("Sales Invoice")
#         doc.update(data)
#         doc.insert(ignore_permissions=True)
#         frappe.db.commit()
#         return {"message": "Sales Invoice created successfully", "name": doc.name}
#     except Exception as e:
#         frappe.log_error(frappe.get_traceback(), "Create Sales Invoice API")
#         return {"error": str(e)}

@frappe.whitelist(allow_guest=True)
def createSalesInvoice():
    if frappe.request.method != "POST":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only POST method allowed"}
 
    if not authenticate_user():
        return {"error": "Unauthorized"}
 
    try:
        data = frappe.request.get_json()

        item_codes = [
            item.get("item_code") or item.get("item")
            for item in data.get("items", [])
        ]
        item_groups = []

        for item_code in item_codes:
            if item_code:
                group = frappe.db.get_value("Item", item_code, "item_group")
                if group:
                    item_groups.append(group)

        unique_groups = set(item_groups)
        year = frappe.utils.now_datetime().year

        # Define mapping from item_group to naming series
        series_map = {
            "Drug": f"DRUG-SINV-{year}-",
            "Laboratory": f"LAB-SINV-{year}-",
            "Services": f"SERV-SINV-{year}-",
            "Consumable": f"CONS-SINV-{year}-",
            "Raw Material": f"RAW-SINV-{year}-",
            "Products": f"PROD-SINV-{year}-",
            "Sub Assemblies": f"SUB-SINV-{year}-",
            "Demo Item Group": f"DEMO-SINV-{year}-",
        }

        # Determine final series
        if len(unique_groups) == 1:
            group = list(unique_groups)[0]
            naming_series = series_map.get(group, f"ACC-SINV-.YYYY.-")
        else:
            naming_series = f"ACC-SINV-.YYYY.-"  # fallback for multiple/missing groups

        # Remove naming_series from incoming data if exists
        data.pop("naming_series", None)

        # Create Sales Invoice
        doc = frappe.new_doc("Sales Invoice")
        doc.update(data)

        # Set naming series after update
        doc.naming_series = naming_series
        # Apply taxes_and_charges and fetch taxes from template
        if data.get("taxes_and_charges"):
            doc.taxes_and_charges = data["taxes_and_charges"]

        # This will trigger tax template fetch
        doc.set_missing_values()


        doc.insert(ignore_permissions=True)
        frappe.db.commit()

        return {
            "message": "Sales Invoice created successfully",
            "name": doc.name,
            "series_used": naming_series
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Create Sales Invoice API")
        return {"error": str(e)}


@frappe.whitelist(allow_guest=True)
def create_sales_invoice():
    if frappe.request.method != "POST":
        frappe.local.response["http_status_code"] = 405
        return {"message": "Only POST allowed", "success": False}
 
    if not authenticate_user():
        return {"message": "Unauthorized", "success": False}
 
    try:
        data = frappe.request.get_json()
 
        # Default series
        naming_series = "ACC-SINV-.YYYY.-"
 
        # Determine series from first item's item_group
        first_item_code = data.get("items", [{}])[0].get("item")
        if first_item_code:
            item_group = frappe.db.get_value("Item", {"item_code": first_item_code}, "item_group")
 
            year = frappe.utils.now_datetime().year
            series_map = {
                "Drug": f"DRUG-SINV-{year}-",
                "Laboratory": f"LAB-SINV-{year}-",
                "Services": f"SERV-SINV-{year}-",
                "Consumable": f"CONS-SINV-{year}-",
                "Raw Material": f"RAW-SINV-{year}-",
                "Products": f"PROD-SINV-{year}-",
                "Sub Assemblies": f"SUB-SINV-{year}-",
                "Demo Item Group": f"DEMO-SINV-{year}-",
            }
 
            if item_group in series_map:
                naming_series = series_map[item_group]
 
        doc = frappe.new_doc("Sales Invoice")
        doc.naming_series = naming_series
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
                "item_name": item.get("item_name"),
                "item_code": item.get("item_code"),
                "qty": item.get("qty"),
                "rate": item.get("rate"),
                "amount": item.get("amount"),
                "income_account": item.get("income_account"),
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
        # doc.submit()  # Uncomment if you want auto-submission
        frappe.db.commit()
 
        return {
            "message": "Sales Invoice created",
            "success": True,
            "data": doc.as_dict()
        }
 
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Create Sales Invoice")
        return {"message": str(e), "success": False}

# 3. Update Sales Invoice
@frappe.whitelist(allow_guest=True)
def updateSalesInvoice():
    if frappe.request.method != "POST":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only POST method allowed"}

    if not authenticate_user():
        return {"error": "Unauthorized"}

    data = frappe.request.get_json()
    id = data.get("name") or data.get("id")
    if not id:
        return {"error": "Missing Sales Invoice ID"}

    try:
        doc = frappe.get_doc("Sales Invoice", id)
        doc.update(data)
        doc.save(ignore_permissions=True)
        # doc.submit()
        frappe.db.commit()
        return {"message": "Sales Invoice Submitted successfully", "updated_data": doc.as_dict()}
    except frappe.DoesNotExistError:
        frappe.local.response["http_status_code"] = 404
        return {"error": "Sales Invoice not found"}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Update Sales Invoice API")
        return {"error": str(e)}
    
# updateAndSubmitSalesInvoice
@frappe.whitelist(allow_guest=True)
def updateAndSubmitSalesInvoice():
    if frappe.request.method != "POST":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only POST method allowed"}

    if not authenticate_user():
        return {"error": "Unauthorized"}

    data = frappe.request.get_json()
    invoice_name = data.get("name") or data.get("id")

    if not invoice_name:
        return {"error": "Missing Sales Invoice ID"}

    try:
        doc = frappe.get_doc("Sales Invoice", invoice_name)
        doc.update(data)
        
        # Handle POS specific updates
        if cint(doc.get("is_pos")) == 1 and not doc.is_return:
            # Ensure payments are properly set for POS
            if not doc.get("payments"):
                if doc.pos_profile:
                    update_multi_mode_option(doc, frappe.get_doc("POS Profile", doc.pos_profile))
                else:
                    # Fallback to default POS profile if not specified
                    from erpnext.stock.get_item_details import get_pos_profile
                    pos_profile = get_pos_profile(doc.company) or {}
                    if pos_profile:
                        doc.pos_profile = pos_profile.get("name")
                        update_multi_mode_option(doc, frappe.get_doc("POS Profile", doc.pos_profile))
            
            # Calculate total payments safely
            total_payments = sum(flt(payment.amount) for payment in doc.payments if payment.amount is not None)
            
            # If payments cover the full amount, mark as paid
            if abs(total_payments) >= abs(flt(doc.grand_total)):
                doc.paid_amount = flt(doc.grand_total)
                doc.base_paid_amount = flt(doc.base_grand_total)
                doc.outstanding_amount = 0
                doc.status = "Paid"  # Explicitly set status
            else:
                # If payments don't cover full amount, calculate outstanding
                doc.outstanding_amount = flt(doc.grand_total) - flt(total_payments)
                doc.status = "Partly Paid" if doc.outstanding_amount > 0 else "Paid"

        doc.save(ignore_permissions=True)
        doc.submit()

        # Force status update for POS invoices if still not marked as Paid
        if cint(doc.get("is_pos")) == 1 and not doc.is_return and doc.status != "Paid":
            frappe.db.set_value("Sales Invoice", doc.name, {
                "status": "Paid",
                "outstanding_amount": 0,
                "paid_amount": doc.grand_total,
                "base_paid_amount": doc.base_grand_total
            }, update_modified=False)
            doc.reload()

        # Update referenced documents
        for item in doc.items:
            ref_dt = item.get("reference_dt")
            ref_dn = item.get("reference_dn")

            if ref_dt and ref_dn:
                if ref_dt in ["Patient Appointment", "Patient Encounter"]:
                    frappe.db.set_value(ref_dt, ref_dn, "invoiced", 1)

                elif ref_dt == "Service Request":
                    frappe.db.set_value(ref_dt, ref_dn, "billing_status", "Invoiced")
                    if doc.get("customer_token"):
                        frappe.db.set_value(ref_dt, ref_dn, "token", doc.customer_token)

                elif ref_dt == "Medication Request":
                    med_req = frappe.get_doc("Medication Request", ref_dn)
                    qty = flt(item.get("qty")) or 0
                    qty_invoiced = (flt(med_req.qty_invoiced) or 0) + qty

                    if qty_invoiced == 0:
                        status = "Pending"
                    elif med_req.number_of_repeats_allowed and med_req.total_dispensable_quantity:
                        status = "Partly Invoiced" if qty_invoiced < flt(med_req.total_dispensable_quantity) else "Invoiced"
                    else:
                        status = "Partly Invoiced" if qty_invoiced < flt(med_req.quantity) else "Invoiced"

                    med_req.qty_invoiced = qty_invoiced
                    med_req.billing_status = status
                    med_req.save(ignore_permissions=True)

        frappe.db.commit()

        return {
            "message": "Sales Invoice submitted and references updated successfully",
            "updated_data": doc.as_dict(),
            "is_pos": doc.get("is_pos"),
            "status": doc.status,
            "outstanding_amount": doc.outstanding_amount,
            "paid_amount": doc.paid_amount,
            "grand_total": doc.grand_total,
            "total_payments": total_payments if cint(doc.get("is_pos")) == 1 else None
        }

    except frappe.DoesNotExistError:
        frappe.local.response["http_status_code"] = 404
        return {"error": "Sales Invoice not found"}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Update Sales Invoice API")
        return {"error": str(e)}  

def update_multi_mode_option(doc, pos_profile):
	def append_payment(payment_mode):
		payment = doc.append("payments", {})
		payment.default = payment_mode.default
		payment.mode_of_payment = payment_mode.mop
		payment.account = payment_mode.default_account
		payment.type = payment_mode.type

	doc.set("payments", [])
	invalid_modes = []
	mode_of_payments = [d.mode_of_payment for d in pos_profile.get("payments")]
	mode_of_payments_info = get_mode_of_payments_info(mode_of_payments, doc.company)

	for row in pos_profile.get("payments"):
		payment_mode = mode_of_payments_info.get(row.mode_of_payment)
		if not payment_mode:
			invalid_modes.append(get_link_to_form("Mode of Payment", row.mode_of_payment))
			continue

		payment_mode.default = row.default
		append_payment(payment_mode)

	if invalid_modes:
		if invalid_modes == 1:
			msg = _("Please set default Cash or Bank account in Mode of Payment {}")
		else:
			msg = _("Please set default Cash or Bank account in Mode of Payments {}")
		frappe.throw(msg.format(", ".join(invalid_modes)), title=_("Missing Account"))

def get_mode_of_payments_info(mode_of_payments, company):
	data = frappe.db.sql(
		"""
		select
			mpa.default_account, mpa.parent as mop, mp.type as type
		from
			`tabMode of Payment Account` mpa,`tabMode of Payment` mp
		where
			mpa.parent = mp.name and
			mpa.company = %s and
			mp.enabled = 1 and
			mp.name in %s
		group by
			mp.name
		""",
		(company, mode_of_payments),
		as_dict=1,
	)

	return {row.get("mop"): row for row in data}


# 4. Delete Sales Invoice
@frappe.whitelist(allow_guest=True)
def deleteSalesInvoice():
    if frappe.request.method != "POST":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only POST method allowed"}

    if not authenticate_user():
        return {"error": "Unauthorized"}

    data = frappe.request.get_json()
    id = data.get("name") or data.get("id")
    if not id:
        return {"error": "Missing Sales Invoice ID"}

    try:
        frappe.delete_doc("Sales Invoice", id, ignore_permissions=True)
        frappe.db.commit()
        return {"message": f"Sales Invoice {id} deleted successfully"}
    except frappe.DoesNotExistError:
        frappe.local.response["http_status_code"] = 404
        return {"error": "Sales Invoice not found"}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Delete Sales Invoice API")
        return {"error": str(e)}

# 5. Get Sales Invoice Details
@frappe.whitelist(allow_guest=True)
def getSalesInvoiceDetails():
    if frappe.request.method != "POST":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only POST method allowed"}

    if not authenticate_user():
        return {"error": "Unauthorized"}

    data = frappe.request.get_json()
    id = data.get("name") or data.get("id")
    if not id:
        return {"error": "Missing Sales Invoice ID"}

    try:
        doc = frappe.get_doc("Sales Invoice", id)
        return {"message": doc.as_dict()}
    except frappe.DoesNotExistError:
        frappe.local.response["http_status_code"] = 404
        return {"error": "Sales Invoice not found"}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Sales Invoice Details API")
        return {"error": str(e)}

# 6. Filter Sales Invoices
# @frappe.whitelist(allow_guest=True)
# def filterSalesInvoices():
#     if frappe.request.method != "POST":
#         frappe.local.response["http_status_code"] = 405
#         return {"error": "Only POST method allowed"}

#     if not authenticate_user():
#         return {"error": "Unauthorized"}

#     data = frappe.request.get_json()
#     filters = {}

#     if data.get("customer"):
#         filters["customer"] = data["customer"]
#     if data.get("status"):
#         filters["status"] = data["status"]

#     # Filter by date range
#     if data.get("from_date") and data.get("to_date"):
#         filters["posting_date"] = ["between", [data["from_date"], data["to_date"]]]
#     elif data.get("posting_date"):
#         filters["posting_date"] = data["posting_date"]

#     try:
#         # Fetch all invoices with filters
#         sales_invoices = frappe.get_all(
#             "Sales Invoice",
#             filters=filters,
#             fields=["name", "customer", "posting_date", "due_date", "status", "grand_total", "currency"],
#             order_by="posting_date desc",
#         )

#         # Initialize counters and totals
#         status_summary = {
#             "Paid": {"count": 0, "total": 0.0},
#             "Unpaid": {"count": 0, "total": 0.0},
#             "Cancelled": {"count": 0, "total": 0.0},
#             "Draft": {"count": 0, "total": 0.0},
#             "Others": {"count": 0, "total": 0.0}
#         }

#         for invoice in sales_invoices:
#             status = invoice.get("status", "Others")
#             grand_total = invoice.get("grand_total", 0.0)

#             if status in status_summary:
#                 status_summary[status]["count"] += 1
#                 status_summary[status]["total"] += grand_total
#             else:
#                 status_summary["Others"]["count"] += 1
#                 status_summary["Others"]["total"] += grand_total

#         return {
#             "count": len(sales_invoices),
#             "summary": status_summary,
#             "message": sales_invoices
#         }

#     except Exception as e:
#         frappe.log_error(frappe.get_traceback(), "Filter Sales Invoices API")
#         return {"error": str(e)}

@frappe.whitelist(allow_guest=True)
def filterSalesInvoices():
    if frappe.request.method != "POST":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only POST method allowed"}

    if not authenticate_user():
        return {"error": "Unauthorized"}

    import datetime

    # Fix: Ensure data is always a dictionary
    data = frappe.request.get_json() or {}
    filters = {}

    if data.get("customer"):
        filters["customer"] = data["customer"]
    if data.get("status"):
        filters["status"] = data["status"]

    # Date range
    if data.get("from_date") and data.get("to_date"):
        filters["posting_date"] = ["between", [data["from_date"], data["to_date"]]]
    elif data.get("posting_date"):
        filters["posting_date"] = data["posting_date"]

    try:
        # Fetch all matching sales invoices
        sales_invoices = frappe.get_all(
            "Sales Invoice",
            filters=filters,
            fields=["name", "customer", "posting_date", "due_date", "status", "grand_total", "currency"],
            order_by="posting_date desc",
        )

        # Define known series categories
        categories = [
            "ACC-SINV", "ACC-SINV-RET", "DRUG-SINV", "LAB-SINV", "SERV-SINV",
            "CONS-SINV", "RAW-SINV", "PROD-SINV", "SUB-SINV", "DEMO-SINV"
        ]

        # Define all known statuses
        status_summary_keys = [
            "Unpaid", "Paid", "Draft", "Credit Note Issued",
            "Return", "Cancelled", "Overdue"
        ]

        # Initialize status summary structure
        def init_summary():
            return {
                "Unpaid": {"count": 0, "total": 0.0},
                "Paid": {"count": 0, "total": 0.0},
                "Draft": {"count": 0, "total": 0.0},
                "Credit Note Issued": {"count": 0, "total": 0.0},
                "Return": {"count": 0, "total": 0.0},
                "Cancelled": {"count": 0, "total": 0.0},
                "Overdue": {"count": 0, "total": 0.0},
                "Others": {"count": 0, "total": 0.0}
            }

        # Prepare summaries
        overall_category_summary = {cat: init_summary() for cat in categories}
        today_category_summary = {cat: init_summary() for cat in categories}

        today = frappe.utils.today()

        for invoice in sales_invoices:
            name = invoice.get("name", "")
            status = str(invoice.get("status", "Others")).strip()
            grand_total = float(invoice.get("grand_total", 0.0))
            posting_date = str(invoice.get("posting_date"))

            matched = False
            for cat in categories:
                if name.startswith(cat):
                    matched = True

                    # Use "Others" if status is unexpected
                    if status not in status_summary_keys:
                        summary_status = "Others"
                    else:
                        summary_status = status

                    # All-time summary
                    overall_category_summary[cat][summary_status]["count"] += 1
                    overall_category_summary[cat][summary_status]["total"] += grand_total

                    # Today's summary
                    if posting_date == today:
                        today_category_summary[cat][summary_status]["count"] += 1
                        today_category_summary[cat][summary_status]["total"] += grand_total

                    break

            # Optionally handle unmatched categories (skipped)

        return {
            "count": len(sales_invoices),
            "all_invoices": sales_invoices,
            "summary_all_time": overall_category_summary,
            "summary_today": today_category_summary
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Filter Sales Invoices API")
        return {"error": str(e)}


# GET ITEMS
@frappe.whitelist(allow_guest=False)  # set allow_guest=True if you want to allow public access
def get_healthcare_services_to_invoice_api(patient, customer=None, company=None, link_customer=False):
    """
    Fetch Healthcare Services (Healthcare Service Orders) eligible to be invoiced for a Patient.
    Similar to ERPNext Healthcare -> Get Healthcare Services.
    """
    if not patient:
        frappe.throw(_("Patient is required"))

    filters = {
        "patient": patient,
        "docstatus": 1,   # Submitted documents only
        "invoiced": 0,    # Not yet invoiced
    }

    if company:
        filters["company"] = company

    service_orders = frappe.get_all(
        "Healthcare Service Order",
        filters=filters,
        fields=[
            "name", 
            "service_unit", 
            "department", 
            "reference_type", 
            "reference_name",
            "grand_total",
            "company",
            "status"
        ],
        order_by="creation desc"
    )

    services = []

    for service in service_orders:
        services.append({
            "service_name": service.name,
            "reference_type": service.reference_type,
            "reference_name": service.reference_name,
            "service_unit": service.service_unit,
            "department": service.department,
            "grand_total": service.grand_total,
            "company": service.company,
            "status": service.status
        })

    return {
        "patient": patient,
        "services": services
    }


@frappe.whitelist()
def get_items_from_healthcare1(patient, customer, company, item_type):
    """
    item_type can be 'healthcare_service' or 'prescription'
    """
    if item_type == "healthcare_service":
        return frappe.call('healthcare.healthcare.utils.get_healthcare_services_to_invoice',
                            patient=patient, customer=customer, company=company, link_customer=1)
    elif item_type == "prescription":
        return frappe.call('healthcare.healthcare.utils.get_drugs_to_invoice',
                            patient=patient, customer=customer, company=company, link_customer=1)
    else:
        frappe.throw("Invalid item type")



@frappe.whitelist()
def get_items_from_healthcare(patient=None, customer=None, company=None, item_type=None, encounter=None, source_name=None):
    """
    Fetch items for Sales Invoice from different sources.
    item_type:
      - healthcare_service
      - prescription
      - sales_order
      - timesheet
      - delivery_note
      - quotation
    """
    if item_type == "healthcare_service":
        items = frappe.call(
            'healthcare.healthcare.utils.get_healthcare_services_to_invoice',
            patient=patient, customer=customer, company=company, link_customer=1
        )

        # Enhance items based on reference_type
        for item in items:
            reference_type = item.get("reference_type")
            reference_name = item.get("reference_name")
            service = item.get("service")


            if not reference_type or not reference_name:
                continue

            try:
                if reference_type == "Service Request":
                    doc = frappe.get_doc("Service Request", reference_name)
                    doc = frappe.get_doc("Service Request", reference_name)

                    item["service_type"] = doc.template_dt
                    item["order_group"] = doc.order_group
                    item["order_date"] = doc.order_date
                    item["practitioner"] = doc.practitioner
                    item["practitioner_name"] = doc.practitioner_name
                    item["department"] = doc.medical_department
                    

                    # ✅ Fetch token from Patient Encounter using order_group
                    token = frappe.db.get_value("Patient Encounter", {"name": doc.order_group}, "token")

                    if token:
                        item["token"] = token
                    else:
                        item["token"] = "-"

                    # Fetch rate based on service_type
                    service_name = service
                    if doc.template_dt == "Clinical Procedure Template":
                        template = frappe.get_value(
                            "Clinical Procedure Template",
                            service_name,
                            "rate"
                        )
                        item["rate"] = template or 0

                    elif doc.template_dt == "Therapy Type":
                        template = frappe.get_value(
                            "Therapy Type",
                            service_name,
                            "rate"
                        )
                        item["rate"] = template or 0

                    elif doc.template_dt == "Observation Template":
                        template = frappe.get_value(
                            "Observation Template",
                            service_name,
                            "rate"
                        )
                        item["rate"] = template or 0

                    else:
                        item["rate"] = 0  # fallback rate


                elif reference_type == "Patient Encounter":
                    doc = frappe.get_doc("Patient Encounter", reference_name)
                    item["practitioner"] = doc.practitioner
                    item["practitioner_name"] = doc.practitioner_name

                elif reference_type == "Patient Appointment":
                    doc = frappe.get_doc("Patient Appointment", reference_name)
                    item["practitioner"] = doc.practitioner
                    item["practitioner_name"] = doc.practitioner_name

                elif reference_type == "Inpatient Occupancy":
                    doc = frappe.get_doc("Healthcare Service Unit Type", service)
                    item["rate"] = doc.rate
            

            except frappe.DoesNotExistError:
                frappe.log_error(f"{reference_type} {reference_name} not found.")
                item["practitioner"] = None
                item["practitioner_name"] = None
                if reference_type == "Service Request":
                    item["service_type"] = None

        return items
    elif item_type == "prescription":
        drugs = frappe.call(
            'healthcare.healthcare.utils.get_drugs_to_invoice',
            patient=patient, customer=customer, company=company, encounter=encounter, link_customer=1
        )

        for drug in drugs:
            price = frappe.db.get_value(
                "Item Price",
                {
                    "item_code": drug["drug_code"],
                    "price_list": "Standard Selling"  # or your desired price list
                },
                "price_list_rate"
            )
            drug["price_list_rate"] = price or 0.0  # Add to response

        return drugs


    elif item_type == "sales_order":
        return frappe.call(
            'erpnext.selling.doctype.sales_order.sales_order.make_sales_invoice',
            source_name=source_name
        )

    elif item_type == "delivery_note":
        return frappe.call(
            'erpnext.controllers.queries.get_delivery_notes_to_be_billed',
            customer=customer, company=company
        )

    elif item_type == "quotation":
        return frappe.call(
            'erpnext.selling.doctype.quotation.quotation.make_sales_invoice',
            source_name=source_name
        )

    elif item_type == "timesheet":
        return frappe.call(
            'erpnext.controllers.queries.item_query',
            customer=customer, company=company
        )

    else:
        frappe.throw(_("Invalid item type"))


# ----------------------------------------PHARMA NUMBER COUNT-----------------------------------------------------------------------------------------------------

@frappe.whitelist(allow_guest=False)
def get_pharmastore_numbercards():
    if not authenticate_user():
        return {"error": "Unauthorized"}

    try:
        today = frappe.utils.today()
        damaged_warehouse = "Damaged Item Warehouse - HIMSD"

        # ✅ Existing counts
        total_indent = frappe.db.count("Material Request")
        out_of_stock = frappe.db.count("Bin", {"actual_qty": 0})
        in_stock = frappe.db.count("Bin", {"actual_qty": [">", 0]})

        expired_items_batch = frappe.db.sql("""
            SELECT COUNT(*)
            FROM `tabBatch`
            WHERE expiry_date < %s
              AND disabled = 0
              AND batch_qty > 0
        """, (today,))[0][0]

        low_stock_items = frappe.db.sql("""
            SELECT COUNT(*)
            FROM `tabBin`
            WHERE actual_qty < reserved_qty
        """)[0][0]

        transfer_out = frappe.db.sql("""
            SELECT COUNT(*)
            FROM `tabStock Entry Detail` sed
            JOIN `tabStock Entry` se ON se.name = sed.parent
            WHERE se.purpose = 'Material Transfer'
              AND se.docstatus = 1
              AND se.posting_date = %s
              AND sed.s_warehouse IS NOT NULL
        """, (today,))[0][0]

        transfer_in = frappe.db.sql("""
            SELECT COUNT(*)
            FROM `tabStock Entry Detail` sed
            JOIN `tabStock Entry` se ON se.name = sed.parent
            WHERE se.purpose = 'Material Transfer'
              AND se.docstatus = 1
              AND se.posting_date = %s
              AND sed.t_warehouse IS NOT NULL
        """, (today,))[0][0]

        stock_issued_today = frappe.db.sql("""
            SELECT ABS(SUM(actual_qty * valuation_rate))
            FROM `tabStock Ledger Entry`
            WHERE posting_date = %s
              AND actual_qty < 0
        """, (today,))[0][0] or 0.0

        damaged_items_count_today = frappe.db.sql("""
            SELECT COUNT(DISTINCT item_code)
            FROM `tabStock Ledger Entry`
            WHERE posting_date = %s
              AND warehouse = %s
        """, (today, damaged_warehouse))[0][0]

        # ✅ Expired Items (based on end_of_life)
        expired_items = frappe.db.sql("""
            SELECT 
                i.name AS item_code,
                i.item_name,
                i.end_of_life,
                b.warehouse,
                b.actual_qty,
                b.valuation_rate,
                (b.actual_qty * b.valuation_rate) AS stock_value
            FROM `tabItem` i
            JOIN `tabBin` b ON i.name = b.item_code
            WHERE i.end_of_life IS NOT NULL
              AND i.end_of_life < %s
              AND b.actual_qty > 0
        """, (today,), as_dict=True)
        expired_count = len(expired_items)

        # ✅ Damaged Items
        damaged_items = frappe.db.sql("""
            SELECT 
                sle.item_code,
                i.item_name,
                i.stock_uom,
                SUM(sle.actual_qty) AS quantity,
                sle.valuation_rate,
                SUM(sle.actual_qty * sle.valuation_rate) AS stock_value
            FROM `tabStock Ledger Entry` sle
            JOIN `tabItem` i ON sle.item_code = i.name
            WHERE sle.warehouse = %s
              AND sle.actual_qty > 0
            GROUP BY sle.item_code, i.item_name, i.stock_uom, sle.valuation_rate
        """, (damaged_warehouse,), as_dict=True)
        damaged_count = len(damaged_items)

        return {
            "message": {
                "total_indent": total_indent,
                "out_of_stock": out_of_stock,
                "in_stock": in_stock,
                "expired_items_batch": expired_items_batch,
                "low_stock_items": low_stock_items,
                "transfer_out": transfer_out,
                "transfer_in": transfer_in,
                "stock_issued_today": stock_issued_today,
                "damaged_items_today": damaged_items_count_today,
                "expired_items": {
                    "count": expired_count,
                    "details": expired_items
                },
                "damaged_items": {
                    "count": damaged_count,
                    "details": damaged_items
                }
            }
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Pharmacy Dashboard API")
        frappe.local.response["http_status_code"] = 500
        return {"error": str(e)}



########################################## IP pharma ####################################

@frappe.whitelist(allow_guest=False)
def get_ip_pharmacy_dashboard():
    if not authenticate_user():
        return {"error": "Unauthorized"}

    try:
        today = frappe.utils.today()
        damaged_warehouse = "Damaged Item Warehouse - HIMSD"

        # 1. Total Indents
        total_indent = frappe.db.count("Material Request")

        # 2. Today's Indents
        todays_indent = frappe.db.count("Material Request", {"transaction_date": today})

        # 3. Pending Items
        pending_items = frappe.db.count("Material Request", {"status": "Pending"})

        # 4. Delivered Items
        delivered_items = frappe.db.sql("""
            SELECT COUNT(*)
            FROM `tabMaterial Request`
            WHERE status IN ('Stopped', 'Completed')
        """)[0][0]

        # 5. Critical Items (stock below safety stock)
        critical_items = frappe.db.sql("""
            SELECT COUNT(*)
            FROM `tabItem` i
            JOIN `tabBin` b ON b.item_code = i.name
            WHERE i.safety_stock > 0 AND b.actual_qty < i.safety_stock
        """)[0][0]

        # ✅ 6. Expired Items: count + data
        expired_items = frappe.db.sql("""
            SELECT 
                i.name AS item_code,
                i.item_name,
                i.end_of_life,
                b.warehouse,
                b.actual_qty,
                b.valuation_rate,
                (b.actual_qty * b.valuation_rate) AS stock_value
            FROM `tabItem` i
            JOIN `tabBin` b ON i.name = b.item_code
            WHERE i.end_of_life IS NOT NULL
              AND i.end_of_life < %s
              AND b.actual_qty > 0
        """, (today,), as_dict=True)
        expired_count = len(expired_items)

        # ✅ 7. Damaged Items: count + data
        damaged_items = frappe.db.sql("""
            SELECT 
                sle.item_code,
                i.item_name,
                i.stock_uom,
                SUM(sle.actual_qty) AS quantity,
                sle.valuation_rate,
                SUM(sle.actual_qty * sle.valuation_rate) AS stock_value
            FROM `tabStock Ledger Entry` sle
            JOIN `tabItem` i ON sle.item_code = i.name
            WHERE sle.warehouse = %s
              AND sle.actual_qty > 0
            GROUP BY sle.item_code, i.item_name, i.stock_uom, sle.valuation_rate
        """, (damaged_warehouse,), as_dict=True)
        damaged_count = len(damaged_items)

        # ✅ 8. Total Sales (today)
        total_sales = frappe.db.sql("""
            SELECT SUM(grand_total)
            FROM `tabSales Invoice`
            WHERE posting_date = %s AND docstatus = 1
        """, (today,))[0][0] or 0.0

        # ✅ 9. Sales by Payment Type
        def get_payment_total(mode):
            return frappe.db.sql("""
                SELECT SUM(sip.amount)
                FROM `tabSales Invoice Payment` sip
                JOIN `tabSales Invoice` si ON si.name = sip.parent
                WHERE sip.mode_of_payment = %s
                  AND si.posting_date = %s
                  AND si.docstatus = 1
            """, (mode, today))[0][0] or 0.0

        cash_total = get_payment_total("Cash")
        cc_dc_total = get_payment_total("Credit Card") + get_payment_total("Debit Card")
        upi_total = get_payment_total("UPI")

        return {
            "message": {
                "total_indent": total_indent,
                "todays_indent": todays_indent,
                "pending_items": pending_items,
                "delivered_items": delivered_items,
                "critical_items": critical_items,

                "expired_items": {
                    "count": expired_count,
                    "items": expired_items
                },
                "damaged_items": {
                    "count": damaged_count,
                    "items": damaged_items
                },

                "total_sales": total_sales,
                "cash_sales": cash_total,
                "cc_dc_sales": cc_dc_total,
                "upi_sales": upi_total
            }
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "IP Pharmacy Dashboard API")
        frappe.local.response["http_status_code"] = 500
        return {"error": str(e)}



####################################### OP Pharma #########################################
@frappe.whitelist(allow_guest=False)
def get_op_pharmacy_dashboard():
    if not authenticate_user():
        return {"error": "Unauthorized"}

    try:
        today = frappe.utils.today()

        # 1. Total Sales (Today)
        total_sales = frappe.db.sql("""
            SELECT SUM(grand_total)
            FROM `tabSales Invoice`
            WHERE posting_date = %s AND docstatus = 1
        """, (today,))[0][0] or 0.0

        # 2. Payment Totals by Mode
        def get_payment_total(mode):
            return frappe.db.sql("""
                SELECT SUM(sip.amount)
                FROM `tabSales Invoice Payment` sip
                JOIN `tabSales Invoice` si ON sip.parent = si.name
                WHERE sip.mode_of_payment = %s
                  AND si.posting_date = %s
                  AND si.docstatus = 1
            """, (mode, today))[0][0] or 0.0

        cash_total = get_payment_total("Cash")
        upi_total = get_payment_total("UPI")
        cc_dc_total = get_payment_total("Credit Card") + get_payment_total("Debit Card")

        # 3. Patient Visited (via Encounter)
        patient_visited = frappe.db.count("Patient Encounter", {"encounter_date": today})

        # 4. Inventory: Available
        inventory_available = frappe.db.count("Bin", {"actual_qty": [">", 0]})

        # 5. Inventory: Expired
        inventory_expired = frappe.db.sql("""
            SELECT COUNT(*)
            FROM `tabBatch`
            WHERE expiry_date < %s
              AND disabled = 0
              AND batch_qty > 0
        """, (today,))[0][0]

        # 6. Collection Summary: OPD/IPD (from Patient Appointment)
        opd_count = frappe.db.count("Patient Appointment", {
            "appointment_type": "OPD",
            "appointment_date": today
        })

        ipd_count = frappe.db.count("Patient Appointment", {
            "appointment_type": "Inpatient",  # or "IPD" if that's your label
            "appointment_date": today
        })

        return {
            "message": {
                "sales": total_sales,
                "cash": cash_total,
                "upi": upi_total,
                "cc_dc": cc_dc_total,
                "patient_visited": patient_visited,
                "inventory": {
                    "available": inventory_available,
                    "expired": inventory_expired
                },
                "collection_summary": {
                    "opd": opd_count,
                    "ipd": ipd_count
                }
            }
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Hospital Dashboard API")
        frappe.local.response["http_status_code"] = 500
        return {"error": str(e)}


###################################Account Payable/Recievable################################
@frappe.whitelist(allow_guest=False)
def count_account_types():
    if not authenticate_user():
        return {"error": "Unauthorized"}

    try:
        # Count of Receivable Accounts
        receivable_count = frappe.db.count("Account", {"account_type": "Receivable"})

        # Count of Payable Accounts
        payable_count = frappe.db.count("Account", {"account_type": "Payable"})

        return {
            "message": {
                "receivable_accounts": receivable_count,
                "payable_accounts": payable_count
            }
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Account Type Count API")
        frappe.local.response["http_status_code"] = 500
        return {"error": str(e)}



# print 

@frappe.whitelist(allow_guest=True)
def get_sales_details_with_patient_info():
    if frappe.request.method != "POST":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only POST method allowed"}

    user = authenticate_user()
    if not user:
        return {"error": "Unauthorized"}

    data = frappe.request.get_json()
    name = data.get("name") or data.get("id")
    doctype = data.get("doctype", "Sales Order")  # Default to Sales Order

    if not name:
        frappe.local.response["http_status_code"] = 400
        return {"error": "Missing Sales Order or Invoice name"}

    if doctype not in ["Sales Order", "Sales Invoice"]:
        frappe.local.response["http_status_code"] = 400
        return {"error": "Invalid doctype. Must be 'Sales Order' or 'Sales Invoice'"}

    try:
        doc = frappe.get_doc(doctype, name)
    except frappe.DoesNotExistError:
        frappe.local.response["http_status_code"] = 404
        return {"error": f"{doctype} {name} not found"}

    patient_info, inpatient_info, address_list = {}, {}, []

    # Patient details
    if doc.patient:
        try:
            patient = frappe.get_doc("Patient", doc.patient)
            patient_info = {
                "name": patient.name,
                "patient_name": patient.patient_name,
                "sex": patient.sex,
                "dob": patient.dob,
                "customer": patient.customer,
                "email": patient.email,
                "mobile": patient.mobile,
                "marital_status": patient.marital_status,
            }
            address_list = frappe.get_all("Address", filters={"link_name": patient.name}, fields=["*"])
        except frappe.DoesNotExistError:
            patient_info = {"error": f"Patient {doc.patient} not found"}

    # Inpatient Record
    if doc.inpatient_record:
        try:
            inpatient = frappe.get_doc("Inpatient Record", doc.inpatient_record)
            inpatient_info = {
                "name":doc.inpatient_record,
                "scheduled_date": inpatient.scheduled_date,
                "service_unit__ward": inpatient.service_unit__ward,
                "primary_practitioner": inpatient.primary_practitioner,
                "primary_healthcare_practitioner_name": inpatient.primary_healthcare_practitioner_name,
                "medical_department": inpatient.medical_department,
                "ip_status": inpatient.ip_status,
                "expected_discharge": inpatient.expected_discharge,
                "admission_service_unit_type": inpatient.admission_service_unit_type,
                "admitted_datetime": inpatient.admitted_datetime,
                "billing_type": inpatient.billing_type,
                "mode_of_payment": inpatient.mode_of_payment,
                "mou": inpatient.mou,
                "insurance_company": inpatient.insurance_company,
                "tpa": inpatient.tpa,
                "claim_stage": inpatient.claim_stage,
                "preauth_status": inpatient.preauth_status,
                "claim_id": inpatient.claim_id,
                "discharge_ordered_date": inpatient.discharge_ordered_date,
                "discharge_practitioner": inpatient.discharge_practitioner,
                "discharge_datetime": inpatient.discharge_datetime,
            }
        except frappe.DoesNotExistError:
            inpatient_info = {"error": f"Inpatient Record {doc.inpatient_record} not found"}

    # Sales/Invoice Items
    items = []
    for item in doc.items:
        item_data = {
            "item_code": item.item_code,
            "item_group": item.item_group,
            "item_name": item.item_name,
            "qty": item.qty,
            "rate": item.rate,
            "reference_dn": item.reference_dn,
            "reference_dt": item.reference_dt,
            "creation": item.creation,
        }

        # Correct delivery field per Doctype
        if doctype == "Sales Order":
            item_data["delivery_date"] = item.delivery_date
        elif doctype == "Sales Invoice":
            item_data["delivered_date"] = item.delivered_date

        # Handle Patient Encounter
        if item.reference_dt == "Patient Encounter" and item.reference_dn:
            try:
                encounter = frappe.get_doc("Patient Encounter", item.reference_dn)
                practitioner_name = encounter.practitioner_name or ""
                item_data["item_name"] = f"Inpatient Visit Charge ({practitioner_name})"
            except frappe.DoesNotExistError:
                item_data["item_name"] = "Inpatient Visit Charge (Unknown Practitioner)"

        # items.append(item_data)

                # Handle Patient Appointment
        if item.reference_dt == "Patient Appointment" and item.reference_dn:
            try:
                encounter = frappe.get_doc("Patient Appointment", item.reference_dn)
                practitioner_name = encounter.practitioner_name or ""
                item_data["item_name"] = f"Outpatient Visit ({practitioner_name})"
            except frappe.DoesNotExistError:
                item_data["item_name"] = "Inpatient Visit Charge (Unknown Practitioner)"

        items.append(item_data)


    # Taxes (child table)
    taxes = []
    for tax in doc.taxes:
        taxes.append({
            "charge_type": tax.charge_type,
            "account_head": tax.account_head,
            "description": tax.description,
            "rate": tax.rate,
            "tax_amount": tax.tax_amount,
            "total": tax.total,
            "tax_amount_after_discount_amount": tax.tax_amount_after_discount_amount,
        })

    # Totals and common financials
    financial_info = {
        "total_qty": doc.total_qty,
        "total": doc.total,
        "tax_category": doc.tax_category,
        "taxes_and_charges": doc.taxes_and_charges,
        "taxes": taxes,
        "total_taxes_and_charges": doc.total_taxes_and_charges,
        "grand_total": doc.grand_total,
        "rounding_adjustment": doc.rounding_adjustment,
        "rounded_total": doc.rounded_total,
        "in_words": doc.in_words,
        "apply_discount_on": doc.apply_discount_on,
        "additional_discount_percentage": doc.additional_discount_percentage,
        "discount_amount": doc.discount_amount,
    }

    # Additional per-doctype fields
    if doctype == "Sales Order":
        financial_info["advance_paid"] = doc.advance_paid
    elif doctype == "Sales Invoice":
        financial_info["total_advance"] = doc.total_advance
        financial_info["outstanding_amount"] = doc.outstanding_amount
        financial_info["paid_date"] = doc.paid_date


    return {
        "message": {
            "doctype": doctype,
            "name": doc.name,
            "patient": patient_info,
            "inpatient_record": inpatient_info,
            "address": address_list,
            "items": items,
            "financials": financial_info
        }
    }
