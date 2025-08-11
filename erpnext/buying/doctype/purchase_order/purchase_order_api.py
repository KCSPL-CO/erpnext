import base64

import frappe
from frappe.utils import cint
from frappe import _
import json


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

##################Create PO###########
@frappe.whitelist(allow_guest=True)
def create_purchase_order():
	if frappe.request.method != "POST":
		frappe.local.response["http_status_code"] = 405
		return {"error": "Only POST method allowed"}

	if not authenticate_user():
		return {"error": "Unauthorized"}

	try:
		data = json.loads(frappe.request.get_data(as_text=True))

		doc = frappe.new_doc("Purchase Order")
		doc.naming_series = data.get("naming_series", "PUR-ORD-.YYYY.-")
		doc.supplier = data["supplier"]
		doc.date = data.get("date")
		doc.company = data.get("company", "HMIS Demo")
		doc.currency = data.get("currency", "INR")
		doc.price_list = data.get("price_list", "Standard Buying")
		doc.set_warehouse = data.get("set_warehouse")
		doc.cost_center = data.get("cost_center")
		doc.project = data.get("project")

		# Items
		for item in data.get("items", []):
			doc.append("items", {
				"item_code": item.get("item_code"),
				"qty": item.get("qty"),
				"uom": item.get("uom"),
				"rate": item.get("rate"),
				"warehouse": item.get("warehouse")
			})

		# Taxes
		for tax in data.get("taxes", []):
			doc.append("taxes", {
				"charge_type": tax.get("type"),
				"account_head": tax.get("account_head"),
				"rate": tax.get("rate"),
				"description": tax.get("description")
			})

		# Additional discount
		doc.apply_discount_on = data.get("apply_discount_on", "Grand Total")
		doc.additional_discount_percentage = data.get("discount_percentage")
		doc.additional_discount_amount = data.get("discount_amount")

		doc.insert(ignore_permissions=True)
		return {"message": "Purchase Order created", "name": doc.name}

	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Create Purchase Order API")
		frappe.local.response["http_status_code"] = 500
		return {"error": str(e)}




################List PO###############
@frappe.whitelist(allow_guest=True)
def list_purchase_orders():
	if frappe.request.method != "GET":
		frappe.local.response["http_status_code"] = 405
		return {"error": "Only GET method allowed"}

	if not authenticate_user():
		return {"error": "Unauthorized"}

	try:
		fields = ["name", "supplier", "transaction_date", "status", "grand_total", "company","total_qty"]
		orders = frappe.get_all("Purchase Order", fields=fields)
		return {"message": orders}
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "List Purchase Orders API")
		frappe.local.response["http_status_code"] = 500
		return {"error": str(e)}
	
############Details PO################
@frappe.whitelist(allow_guest=True)
def get_purchase_order_details():
	if frappe.request.method != "POST":
		frappe.local.response["http_status_code"] = 405
		return {"error": "Only POST method allowed"}

	if not authenticate_user():
		return {"error": "Unauthorized"}

	data = frappe.request.get_json()
	if not data.get("name"):
		return {"error": "Missing Purchase Order ID"}

	try:
		doc = frappe.get_doc("Purchase Order", data["name"])
		return {"message": doc.as_dict()}
	except frappe.DoesNotExistError:
		frappe.local.response["http_status_code"] = 404
		return {"error": "Purchase Order not found"}
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Get Purchase Order Details API")
		return {"error": str(e)}



#####################Update PO###################
@frappe.whitelist(allow_guest=True)
def update_purchase_order():
	if frappe.request.method != "PUT":
		frappe.local.response["http_status_code"] = 405
		return {"error": "Only PUT method allowed"}

	if not authenticate_user():
		return {"error": "Unauthorized"}

	try:
		data = json.loads(frappe.request.get_data(as_text=True))
		doc = frappe.get_doc("Purchase Order", data["name"])

		if "status" in data:
			doc.status = data["status"]
		if "items" in data:
			doc.items = []
			for item in data["items"]:
				doc.append("items", item)

		doc.save(ignore_permissions=True)
		return {"message": "Purchase Order updated", "name": doc.name}
	except frappe.DoesNotExistError:
		frappe.local.response["http_status_code"] = 404
		return {"error": "Purchase Order not found"}
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Update Purchase Order API")
		return {"error": str(e)}












############################################Purchase Receipt###########################################

@frappe.whitelist(allow_guest=True)
def create_purchase_receipt():
	if frappe.request.method != "POST":
		frappe.local.response["http_status_code"] = 405
		return {"error": "Only POST method allowed"}

	if not authenticate_user():
		return {"error": "Unauthorized"}

	try:
		data = frappe.request.get_json()

		doc = frappe.new_doc("Purchase Receipt")
		doc.supplier = data.get("supplier")
		doc.posting_date = data.get("posting_date")
		doc.posting_time = data.get("posting_time")
		doc.company = data.get("company")
		doc.currency = data.get("currency")
		doc.price_list = data.get("price_list")
		doc.set_warehouse = data.get("set_warehouse")

		# Child table: items
		for item in data.get("items", []):
			doc.append("items", {
				"item_code": item.get("item_code"),
				"qty": item.get("qty"),
				"rate": item.get("rate"),
				"accepted_qty": item.get("accepted_qty"),
				"rejected_qty": item.get("rejected_qty"),
				"warehouse": item.get("warehouse")
			})

		doc.insert(ignore_permissions=True)
		return {"message": "Purchase Receipt created", "name": doc.name}

	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Create Purchase Receipt API")
		frappe.local.response["http_status_code"] = 500
		return {"error": str(e)}



#####List####
@frappe.whitelist(allow_guest=True)
def list_purchase_receipts():
	if frappe.request.method != "GET":
		frappe.local.response["http_status_code"] = 405
		return {"error": "Only GET method allowed"}

	if not authenticate_user():
		return {"error": "Unauthorized"}

	try:
		fields = [
			"name", "supplier", "posting_date", "posting_time", "company",
			"currency", "total_qty", "total", "status"
		]

		receipts = frappe.get_all("Purchase Receipt", fields=fields, order_by="creation desc")

		return {"message": receipts}

	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "List Purchase Receipts API")
		frappe.local.response["http_status_code"] = 500
		return {"error": str(e)}

############DEtails############


@frappe.whitelist(allow_guest=True)
def get_purchase_receipt_details():
	if frappe.request.method != "POST":
		frappe.local.response["http_status_code"] = 405
		return {"error": "Only POST method allowed"}

	if not authenticate_user():
		return {"error": "Unauthorized"}

	data = frappe.request.get_json()
	receipt_id = data.get("name") or data.get("id")

	if not receipt_id:
		return {"error": "Missing Purchase Receipt ID"}

	try:
		doc = frappe.get_doc("Purchase Receipt", receipt_id)
		return {"message": doc.as_dict()}

	except frappe.DoesNotExistError:
		frappe.local.response["http_status_code"] = 404
		return {"error": "Purchase Receipt not found"}

	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Get Purchase Receipt Details API")
		frappe.local.response["http_status_code"] = 500
		return {"error": str(e)}









##############################Purchase Order And Reciept#################################
@frappe.whitelist(allow_guest=True)
def list_purchase_order_receipt_summary():
	if frappe.request.method != "GET":
		frappe.local.response["http_status_code"] = 405
		return {"error": "Only GET method allowed"}

	if not authenticate_user():
		return {"error": "Unauthorized"}

	try:
		purchase_orders = frappe.get_all("Purchase Order", fields=[
			"name", "supplier", "transaction_date", "status", "grand_total", "company", "total_qty"
		])

		result = []

		for po in purchase_orders:
			# Fetch all Purchase Receipts related to this PO
			receipts = frappe.db.sql("""
				SELECT
					pr.parent AS receipt_id,
					SUM(pr.qty) AS total_qty,
					SUM(pr.amount) AS total
				FROM
					`tabPurchase Receipt Item` pr
				WHERE
					pr.purchase_order = %s
				GROUP BY
					pr.parent
			""", po.name, as_dict=True)

			if receipts:
				for r in receipts:
					result.append({
						"purchase_order": po.name,
						"supplier": po.supplier,
						"company": po.company,
						"po_total_qty": po.total_qty,
						"po_grand_total": po.grand_total,
						"purchase_receipt": r.receipt_id,
						"pr_total_qty": r.total_qty,
						"pr_total": r.total
					})
			else:
				# Add PO even if no receipts are found
				result.append({
					"purchase_order": po.name,
					"supplier": po.supplier,
					"company": po.company,
					"po_total_qty": po.total_qty,
					"po_grand_total": po.grand_total,
					"purchase_receipt": None,
					"pr_total_qty": 0,
					"pr_total": 0
				})

		return {"message": result}

	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Combined PO-PR Summary API")
		frappe.local.response["http_status_code"] = 500
		return {"error": str(e)}


# ################################################ created by Vaishnavi #######################################

@frappe.whitelist(allow_guest=True)
def submit_purchase_order():
    if frappe.request.method != "POST":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only POST method allowed"}
 
    user = authenticate_user()
    if not user:
        return {"error": "Unauthorized"}
 
    try:
        data = json.loads(frappe.request.get_data(as_text=True))
        po_name = data.get("name")
        if not po_name:
            return {"error": "Missing Purchase Order name"}
 
        doc = frappe.get_doc("Purchase Order", po_name)
 
        if doc.docstatus == 0:
            doc.submit()
            frappe.db.commit()
            return {"message": "Purchase Order submitted", "name": doc.name}
        else:
            return {
                "message": "Purchase Order already submitted or cancelled",
                "docstatus": doc.docstatus
            }
 
    except frappe.DoesNotExistError:
        frappe.local.response["http_status_code"] = 404
        return {"error": "Purchase Order not found"}
 
    except frappe.ValidationError as ve:
        frappe.local.response["http_status_code"] = 400
        return {"error": f"Validation Error: {str(ve)}"}
 
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Submit Purchase Order API")
        frappe.local.response["http_status_code"] = 500
        return {"error": str(e)}
 
 
 
 
 
@frappe.whitelist()
def cancel_purchase_order():
    if frappe.request.method != "POST":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only POST method allowed"}
 
    if not authenticate_user():
        frappe.local.response["http_status_code"] = 401
        return {"error": "Unauthorized"}
 
    try:
        data = frappe.request.get_json()
        po_name = data.get("name") or data.get("id")
        if not po_name:
            return {"error": "Missing Purchase Order ID"}
 
        doc = frappe.get_doc("Purchase Order", po_name)
 
        if doc.docstatus != 1:
            return {"error": f"Cannot cancel Purchase Order '{po_name}' as it is not submitted."}
 
        doc.cancel()
        frappe.db.commit()
 
        return {"message": f"Purchase Order {po_name} has been cancelled successfully"}
 
    except frappe.DoesNotExistError:
        frappe.local.response["http_status_code"] = 404
        return {"error": "Purchase Order not found"}
 
    except frappe.ValidationError as ve:
        frappe.local.response["http_status_code"] = 400
        return {"error": f"Validation Error: {str(ve)}"}
 
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Cancel Purchase Order API")
        frappe.local.response["http_status_code"] = 500
        return {"error": str(e)}
	
@frappe.whitelist()
def create_purchase_order_from_material_request():
    if frappe.request.method != "POST":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only POST method allowed"}
 
    if not authenticate_user():
        return {"error": "Unauthorized"}
 
    try:
        data = frappe.request.get_json()
        mr_name = data.get("id")
        supplier = data.get("supplier")
 
        if not mr_name or not supplier:
            return {"error": "Missing Material Request ID or Supplier"}
 
        mr_doc = frappe.get_doc("Material Request", mr_name)
 
        if mr_doc.docstatus != 1:
            return {"error": f"Material Request {mr_name} must be submitted"}
 
        po = frappe.new_doc("Purchase Order")
        po.supplier = supplier
        po.schedule_date = frappe.utils.nowdate()
        po.material_request = mr_name
        po.set_warehouse = mr_doc.set_warehouse
 
        # Manually copy items with target_warehouse
        for item in mr_doc.items:
            po.append("items", {
                "item_code": item.item_code,
                "item_name": item.item_name,
                "description": item.description,
                "qty": item.qty,
                "uom": item.uom,
                "stock_uom": item.stock_uom,
                "conversion_factor": item.conversion_factor,
                "rate": item.rate,
                "warehouse": item.warehouse,  # This is target warehouse in MR
                "schedule_date": frappe.utils.nowdate(),
                "material_request": mr_name,
                "material_request_item": item.name,
            })
 
        po.insert()
        # frappe.db.commit()
 
        return {
            "message": f"Purchase Order {po.name} created from Material Request {mr_name}",
            "purchase_order": po.name
        }
 
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Create PO from MR API")
        frappe.local.response["http_status_code"] = 500
        return {"error": str(e)}
	
@frappe.whitelist()
def get_all_suppliers(search_text=None):
 
    if not authenticate_user():
        frappe.local.response["http_status_code"] = 401
        return {"error": "Unauthorized"}
    filters = {}
    if search_text:
        filters["supplier_name"] = ["like", f"%{search_text}%"]
 
    suppliers = frappe.get_all(
        "Supplier",
        fields=["name", "supplier_name"],
        filters=filters,
        limit_page_length=50,
        order_by="modified desc"
    )
 
    return suppliers

@frappe.whitelist(allow_guest=False)  # set True only if guests can access
def get_purchase_receipt_by_id():
 
    if frappe.request.method != "POST":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only POST method allowed"}
 
    if not authenticate_user():
        frappe.local.response["http_status_code"] = 401
        return {"error": "Unauthorized"}
    """
    Fetch Purchase Receipt document by ID from POST body.
    """
    data = frappe.form_dict  # Works for both GET and POST JSON form data
    pr_id = data.get("pr_id")
 
    if not pr_id:
        frappe.throw(_("Purchase Receipt ID is required"))
 
    # get_doc ensures child tables are also fetched
    doc = frappe.get_doc("Purchase Receipt", pr_id)
    return doc


@frappe.whitelist()
def make_purchase_receipt_from_po():
    if frappe.request.method != "POST":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only POST method allowed"}

    if not authenticate_user():
        frappe.local.response["http_status_code"] = 401
        return {"error": "Unauthorized"}
    data = frappe.request.get_json()
    source_name = data.get("source_name")

    if not source_name:
        frappe.throw("Missing source_name in request body")

    from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_receipt

    pr_doc = make_purchase_receipt(source_name)
    pr_doc.insert(ignore_permissions=True)
    frappe.db.commit()

    return {"name": pr_doc.name}

import json
from frappe import _
@frappe.whitelist(allow_guest=False)
def update_purchase_receipt():
    if frappe.request.method != "POST":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only POST method allowed"}

    if not authenticate_user():
        frappe.local.response["http_status_code"] = 401
        return {"error": "Unauthorized"}
    data = frappe.request.get_json()  # ✅ THIS reads raw JSON body

    if not data:
        frappe.throw("No JSON data provided.")

    purchase_receipt_name = data.get("purchase_receipt_name")
    items_data = data.get("items", [])
    set_warehouse = data.get("set_warehouse")
    rejected_warehouse = data.get("rejected_warehouse")

    if not purchase_receipt_name or not items_data:
        frappe.throw("Missing purchase_receipt_name or items")

    pr = frappe.get_doc("Purchase Receipt", purchase_receipt_name)

    if set_warehouse:
        pr.set_warehouse = set_warehouse

    if rejected_warehouse:
        pr.rejected_warehouse = rejected_warehouse

    for item in items_data:
        item_code = item.get("item_code")
        if not item_code:
            continue

        received_qty = item.get("received_qty")
        accepted_qty = item.get("accepted_qty")
        rejected_qty = item.get("rejected_qty")

        for pr_item in pr.items:
            if pr_item.item_code == item_code:
                pr_item.received_qty = received_qty
                pr_item.qty = accepted_qty
                pr_item.rejected_qty = rejected_qty
                break

    pr.save(ignore_permissions=True)
    frappe.db.commit()

    return {"message": "Purchase Receipt updated", "doc": pr}

@frappe.whitelist()
def submit_purchase_receipt():
    if frappe.request.method != "POST":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only POST method allowed"}

    if not authenticate_user():
        frappe.local.response["http_status_code"] = 401
        return {"error": "Unauthorized"}

    data = frappe.request.get_json()

    if not data:
        frappe.throw("No input data received")

    receipt_id = data.get("id")
    if not receipt_id:
        frappe.throw("Missing purchase_receipt_name")

    # Make sure it's a Purchase Receipt
    pr = frappe.get_doc("Purchase Receipt", receipt_id)

    if pr.docstatus != 0:
        frappe.throw("Purchase Receipt is already submitted or cancelled")

    pr.submit()
    frappe.db.commit()

    return {
        "message": f"Purchase Receipt {receipt_id} submitted successfully",
        "docstatus": pr.docstatus
    }


