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
            fields=["name", "customer", "posting_date", "due_date", "status", "grand_total", "currency"],
            order_by="posting_date desc",
            limit_page_length=20
        )
        return {"message": sales_invoices}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "List Sales Invoice API")
        frappe.local.response["http_status_code"] = 500
        return {"error": str(e)}

# 2. Create Sales Invoice
@frappe.whitelist(allow_guest=True)
def createSalesInvoice():
    if frappe.request.method != "POST":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only POST method allowed"}

    if not authenticate_user():
        return {"error": "Unauthorized"}

    data = frappe.request.get_json()
    try:
        doc = frappe.new_doc("Sales Invoice")
        doc.update(data)
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
        return {"message": "Sales Invoice created successfully", "name": doc.name}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Create Sales Invoice API")
        return {"error": str(e)}

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
        frappe.db.commit()
        return {"message": "Sales Invoice updated successfully", "updated_data": doc.as_dict()}
    except frappe.DoesNotExistError:
        frappe.local.response["http_status_code"] = 404
        return {"error": "Sales Invoice not found"}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Update Sales Invoice API")
        return {"error": str(e)}

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
@frappe.whitelist(allow_guest=True)
def filterSalesInvoices():
    if frappe.request.method != "POST":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only POST method allowed"}

    if not authenticate_user():
        return {"error": "Unauthorized"}

    data = frappe.request.get_json()
    filters = {}

    if data.get("customer"):
        filters["customer"] = data["customer"]
    if data.get("status"):
        filters["status"] = data["status"]

    # Filter by date range if provided
    if data.get("from_date") and data.get("to_date"):
        filters["posting_date"] = ["between", [data["from_date"], data["to_date"]]]
    elif data.get("posting_date"):
        filters["posting_date"] = data["posting_date"]

    try:
        sales_invoices = frappe.get_all(
            "Sales Invoice",
            filters=filters,
            fields=["name", "customer", "posting_date", "due_date", "status", "grand_total", "currency"],
            order_by="posting_date desc",
            limit_page_length=20
        )

        return {
            "count": len(sales_invoices),
            "message": sales_invoices
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
        return frappe.call(
            'healthcare.healthcare.utils.get_healthcare_services_to_invoice',
            patient=patient, customer=customer, company=company, link_customer=1
        )

    elif item_type == "prescription":
        return frappe.call(
            'healthcare.healthcare.utils.get_drugs_to_invoice',
            patient=patient, customer=customer, company=company, encounter=encounter, link_customer=1
        )

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
