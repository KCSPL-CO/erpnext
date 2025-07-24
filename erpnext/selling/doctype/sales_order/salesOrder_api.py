import base64
import frappe
from frappe.utils.password import get_decrypted_password
from frappe.utils import flt


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
	if not user or get_decrypted_password("User", user.name, "api_secret") != api_secret:
		frappe.local.response["http_status_code"] = 401
		return None

	return user

@frappe.whitelist(allow_guest=True)
def filter_get_sales_order_details():
    # ✅ Change method check to POST
    if frappe.request.method != "POST":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only POST method allowed"}

    # ✅ Authenticate
    user = authenticate_user()
    if not user:
        return {"error": "Unauthorized"}

    # ✅ Get JSON body instead of query params
    data = frappe.request.get_json()
    order_id = data.get("id") or data.get("name")

    if not order_id:
        frappe.local.response["http_status_code"] = 400
        return {"error": "Missing Sales Order ID"}

    try:
        sales_order = frappe.get_doc("Sales Order", order_id)
    except frappe.DoesNotExistError:
        frappe.local.response["http_status_code"] = 404
        return {"error": f"Sales Order {order_id} not found"}

    return {
        "message": {
            "name": sales_order.name,
            "parent_doctype": sales_order.doctype,
            "items": sales_order.items
        }
    }



@frappe.whitelist(allow_guest=True)
def get_sales_order_list():
	if frappe.request.method != "GET":
		frappe.local.response["http_status_code"] = 405
		return {"error": "Only GET method allowed"}

	user = authenticate_user()
	if not user:
		return {"error": "Unauthorized"}

	user_roles = frappe.get_roles(user.name)
	if "Sales User" not in user_roles and "System Manager" not in user_roles:
		frappe.local.response["http_status_code"] = 403
		return {"error": "Access denied"}

	limit_start = int(frappe.form_dict.get("limit_start", 0))
	limit_page_length = int(frappe.form_dict.get("limit_page_length", 10))
	filters = {}

	# Optional filter by customer or status
	if frappe.form_dict.get("customer"):
		filters["customer"] = frappe.form_dict.get("customer")
	if frappe.form_dict.get("status"):
		filters["status"] = frappe.form_dict.get("status")

	try:
		total = frappe.db.count("Sales Order", filters=filters)

		sales_orders = frappe.get_all(
			"Sales Order",
			fields=["name", "customer", "transaction_date", "status", "grand_total"],
			filters=filters,
			order_by="creation DESC",
			limit_start=limit_start,
			limit_page_length=limit_page_length,
		)

		for order in sales_orders:
			order["items"] = frappe.get_all(
				"Sales Order Item",
				filters={"parent": order.name},
				fields=["item_code", "item_name", "qty", "rate", "amount"]
			)

			# Optional: Linked documents
			order["delivery_notes"] = frappe.get_all("Delivery Note Item", filters={"against_sales_order": order.name}, fields=["parent"])
			order["invoices"] = frappe.get_all("Sales Order Item", filters={"sales_order": order.name}, fields=["parent"])
			order["payments"] = frappe.get_all("Payment Entry Reference", filters={"reference_name": order.name}, fields=["parent"])

		return {
			"total": total,
			"limit_start": limit_start,
			"limit_page_length": limit_page_length,
			"sales_orders": sales_orders,
		}

	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Sales Order List API Error")
		frappe.local.response["http_status_code"] = 500
		return {"error": str(e)}




@frappe.whitelist(allow_guest=True)
def create_sales_order():
	if frappe.request.method != "POST":
		frappe.local.response["http_status_code"] = 405
		return {"error": "Only POST method allowed"}

	if not authenticate_user():
		return {"error": "Unauthorized"}

	data = frappe.request.get_json()
	required_fields = ["customer", "transaction_date", "items"]
	for field in required_fields:
		if not data.get(field):
			return {"error": f"Missing required field: {field}"}

	try:
		doc = frappe.get_doc({
			"doctype": "Sales Order",
			**data
		})
		doc.insert(ignore_permissions=True)
		frappe.db.commit()
		return {"message": "Sales Order created", "id": doc.name, "grand_total":doc.grand_total}
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Create Sales Order API Error")
		return {"error": str(e)}
	
@frappe.whitelist(allow_guest=True)
def get_sales_order_details():
	if frappe.request.method != "POST":
		frappe.local.response["http_status_code"] = 405
		return {"error": "Only POST method allowed"}

	if not authenticate_user():
		return {"error": "Unauthorized"}

	data = frappe.request.get_json()
	order_id = data.get("name") or data.get("id")
	if not order_id:
		return {"error": "Missing Sales Order ID"}

	try:
		doc = frappe.get_doc("Sales Order", order_id)
		response = doc.as_dict()

		# Attachments, Comments, Communication
		response["attachments"] = frappe.get_all("File", filters={"attached_to_doctype": "Sales Order", "attached_to_name": order_id}, fields=["file_url", "file_name"])
		response["comments"] = frappe.get_all("Comment", filters={"comment_type": "Comment", "reference_name": order_id}, fields=["comment_by", "content", "creation"])
		response["communications"] = frappe.get_all("Communication", filters={"reference_name": order_id}, fields=["subject", "content", "communication_date"])

		# Customer Address
		response["customer_address"] = frappe.db.get_value("Dynamic Link", {"link_name": doc.customer, "link_doctype": "Customer", "parenttype": "Address"}, "parent")

		return response
	except frappe.DoesNotExistError:
		frappe.local.response["http_status_code"] = 404
		return {"error": "Sales Order not found"}
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Get Sales Order Details API")
		return {"error": str(e)}



# updateAndSubmitSalesInvoice
@frappe.whitelist(allow_guest=True)
def update_and_submit_sales_order():
    if frappe.request.method != "POST":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only POST method allowed"}

    if not authenticate_user():
        return {"error": "Unauthorized"}

    data = frappe.request.get_json()
    invoice_name = data.get("name") or data.get("id")

    if not invoice_name:
        return {"error": "Missing Sales Order ID"}

    try:
        # Get the Sales Order document
        doc = frappe.get_doc("Sales Order", invoice_name)

        # Optional: update fields if provided
        doc.update(data)

        # Submit the invoice
        doc.save(ignore_permissions=True)
        doc.submit()

        frappe.db.commit()

        return {
            "message": "Sales Order  updated successfully",
            "updated_data": doc.as_dict()
        }

    except frappe.DoesNotExistError:
        frappe.local.response["http_status_code"] = 404
        return {"error": "Sales Order not found"}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Update Sales Order API")
        return {"error": str(e)}





import frappe
from frappe.utils import flt

@frappe.whitelist(allow_guest=True)
def update_sales_order():
	if frappe.request.method != "POST":
		frappe.local.response["http_status_code"] = 405
		return {"error": "Only POST method allowed"}

	if not authenticate_user():
		return {"error": "Unauthorized"}

	data = frappe.request.get_json()
	sales_order_name = data.get("name") or data.get("id")
	incoming_items = data.get("items")

	if not sales_order_name:
		return {"error": "Missing Sales Order ID"}

	

	try:
		# Get the Sales Order document
		doc = frappe.get_doc("Sales Order", sales_order_name)

		# Get company abbreviation
		company_abbr = frappe.db.get_value("Company", doc.company, "abbr") or "HIMS"

		for item in incoming_items:
			item_code = item.get("item_code")
			if not item_code:
				continue

			# Fetch Item Doc
			try:
				item_doc = frappe.get_doc("Item", item_code)
			except frappe.DoesNotExistError:
				frappe.log_error(f"Item {item_code} not found", "Sales Order Item Update")
				continue

			# Get default values from item_defaults for this company
			default_warehouse = ""
			income_account = ""
			expense_account = ""
			for default in item_doc.get("item_defaults", []):
				if default.company == doc.company:
					default_warehouse = default.default_warehouse or ""
					income_account = default.income_account or ""
					expense_account = default.expense_account or ""
					break

			# Fallback values
			if not income_account:
				income_account = f"Sales - {company_abbr}"
			if not expense_account:
				expense_account = f"Cost of Goods Sold - {company_abbr}"
			if not default_warehouse:
				default_warehouse = f"Stores - {company_abbr}"

			# Get price_list_rate from Item Price
			price_list_rate = frappe.db.get_value(
				"Item Price",
				{
					"item_code": item_code,
					"selling": 1,
					"price_list": doc.selling_price_list
				},
				"price_list_rate"
			)

			# Use flt() to ensure valid numeric values
			qty = flt(item.get("qty"), 1)
			rate = flt(price_list_rate, 0)
			amount = flt(qty * rate, 0)

			# Build merged item with safe numeric values
			merged_item = {
				"item_code": item_code,
				"item_name": item_doc.item_name,
				"description": item_doc.description or item_doc.item_name,
				"uom": item_doc.stock_uom,
				"stock_uom": item_doc.stock_uom,
				"warehouse": default_warehouse,
				"income_account": income_account,
				"expense_account": expense_account,
				"qty": qty,
				"rate": rate,
				"price_list_rate": rate,
				"amount": amount,
				"base_rate": rate,
				"base_amount": amount,
				"net_rate": rate,
				"net_amount": amount,
				"conversion_factor": 1,
				"cost_center": f"Main - {company_abbr}",
				"reference_dt": item.get("reference_dt", ""),
				"reference_dn": item.get("reference_dn", "")
			}

			# Append the new item
			doc.append("items", merged_item)

		# Save and commit changes
		doc.save(ignore_permissions=True)
		frappe.db.commit()

		return {
			"message": "Sales Order updated successfully",
			"updated_data": doc.as_dict()
		}

	except frappe.DoesNotExistError:
		frappe.local.response["http_status_code"] = 404
		return {"error": "Sales Order not found"}

	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Update Sales Order API")
		return {"error": str(e)}




@frappe.whitelist(allow_guest=True)
def delete_sales_order():
	if frappe.request.method != "DELETE":
		frappe.local.response["http_status_code"] = 405
		return {"error": "Only DELETE method allowed"}

	if not authenticate_user():
		return {"error": "Unauthorized"}

	data = frappe.request.get_json()
	order_id = data.get("name") or data.get("id")
	if not order_id:
		return {"error": "Missing Sales Order ID"}

	try:
		frappe.delete_doc("Sales Order", order_id, ignore_permissions=True)
		frappe.db.commit()
		return {"message": "Sales Order deleted", "id": order_id}
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Delete Sales Order API Error")
		return {"error": str(e)}
