import base64
import frappe

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


# 1. List Recent Items
@frappe.whitelist(allow_guest=True)
@frappe.whitelist(allow_guest=True)
def listItems():
	if frappe.request.method != "GET":
		frappe.local.response["http_status_code"] = 405
		return {"error": "Only GET method allowed"}

	if not authenticate_user():
		return {"error": "Unauthorized"}

	try:
		items = frappe.get_all(
			"Item",
			fields=[
				"name",
				"owner",
				"creation",
				"modified",
				"modified_by",
				"naming_series",
				"item_code",
				"item_name",
				"item_group",
				"end_of_life",
				"safety_stock",
				"standard_rate",
				"disabled as status"  # This maps "disabled" field as "status"
			],
			order_by="creation desc",
			# limit_page_length=20
		)

		# Convert 'disabled' (1/0) into readable 'Active' / 'Disabled' text
		for item in items:
			bin_data = frappe.db.get_value(
				"Bin",
				{"item_code": item["item_code"]},
				{"actual_qty", "stock_value"},
				as_dict=True
			)

			item["stock_qty"] = bin_data.actual_qty if bin_data else 0
			item["stock_value"] = bin_data.stock_value if bin_data else 0
			item["status"] = "Disabled" if item["status"] else "Active"

		return {"message": items}

	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "List Item API")
		frappe.local.response["http_status_code"] = 500
		return {"error": str(e)}

# 2. Create Item
@frappe.whitelist(allow_guest=True)
def createItem():
	if frappe.request.method != "POST":
		frappe.local.response["http_status_code"] = 405
		return {"error": "Only POST method allowed"}

	if not authenticate_user():
		return {"error": "Unauthorized"}

	data = frappe.request.get_json()
	try:
		doc = frappe.new_doc("Item")
		doc.update(data)
		doc.insert(ignore_permissions=True)
		frappe.db.commit()
		return {"message": "Item created successfully", "name": doc.name}
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Create Item API")
		return {"error": str(e)}


# 3. Filter Items
@frappe.whitelist(allow_guest=True)
def filterItems():
	if frappe.request.method != "POST":
		frappe.local.response["http_status_code"] = 405
		return {"error": "Only POST method allowed"}

	if not authenticate_user():
		return {"error": "Unauthorized"}

	data = frappe.request.get_json()
	filters = {}

	if data.get("item_group"):
		filters["item_group"] = data["item_group"]
	if data.get("item_code"):
		filters["item_code"] = data["item_code"]
	if data.get("item_name"):
		filters["item_name"] = ["like", f"%{data['item_name']}%"]

	try:
		items = frappe.get_all(
			"Item",
			filters=filters,
			fields=["name", "item_code", "item_name", "item_group", "stock_uom"],
			order_by="creation desc",
			# limit_page_length=20,
		)
		return {"message": items}
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Filter Items API")
		return {"error": str(e)}


# 4. Update Item
@frappe.whitelist(allow_guest=True)
def updateItem():
	if frappe.request.method != "POST":
		frappe.local.response["http_status_code"] = 405
		return {"error": "Only POST method allowed"}

	if not authenticate_user():
		return {"error": "Unauthorized"}

	data = frappe.request.get_json()
	id = data.get("name") or data.get("id")
	if not id:
		return {"error": "Missing Item ID"}

	try:
		doc = frappe.get_doc("Item", id)
		doc.update(data)
		doc.save(ignore_permissions=True)
		frappe.db.commit()
		return {"message": "Item updated successfully", "updated_data": doc.as_dict()}
	except frappe.DoesNotExistError:
		frappe.local.response["http_status_code"] = 404
		return {"error": "Item not found"}
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Update Item API")
		return {"error": str(e)}


# 5. Delete Item
@frappe.whitelist(allow_guest=True)
def deleteItem():
	if frappe.request.method != "POST":
		frappe.local.response["http_status_code"] = 405
		return {"error": "Only POST method allowed"}

	if not authenticate_user():
		return {"error": "Unauthorized"}

	data = frappe.request.get_json()
	id = data.get("name") or data.get("id")
	if not id:
		return {"error": "Missing Item ID"}

	try:
		frappe.delete_doc("Item", id, ignore_permissions=True)
		frappe.db.commit()
		return {"message": f"Item {id} deleted successfully"}
	except frappe.DoesNotExistError:
		frappe.local.response["http_status_code"] = 404
		return {"error": "Item not found"}
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Delete Item API")
		return {"error": str(e)}


# 6. Get Item Details
@frappe.whitelist(allow_guest=True)
def getItemDetails():
	if frappe.request.method != "POST":
		frappe.local.response["http_status_code"] = 405
		return {"error": "Only POST method allowed"}

	if not authenticate_user():
		return {"error": "Unauthorized"}

	data = frappe.request.get_json()
	id = data.get("name") or data.get("id")
	if not id:
		return {"error": "Missing Item ID"}

	try:
		doc = frappe.get_doc("Item", id)
		return {"message": doc.as_dict()}
	except frappe.DoesNotExistError:
		frappe.local.response["http_status_code"] = 404
		return {"error": "Item not found"}
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Get Item Details API")
		return {"error": str(e)}

# ITEM GROUP
# 1. List Item Groups
@frappe.whitelist(allow_guest=True)
def listItemGroups():
    if frappe.request.method != "GET":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only GET method allowed"}

    if not authenticate_user():
        return {"error": "Unauthorized"}

    try:
        item_groups = frappe.get_all(
            "Item Group",
            fields=["name", "parent_item_group", "is_group"],
            order_by="creation desc",
            # limit_page_length=20
        )
        return {"message": item_groups}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "List Item Group API")
        frappe.local.response["http_status_code"] = 500
        return {"error": str(e)}

# 2. Create Item Group
@frappe.whitelist(allow_guest=True)
def createItemGroup():
    if frappe.request.method != "POST":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only POST method allowed"}

    if not authenticate_user():
        return {"error": "Unauthorized"}

    data = frappe.request.get_json()
    try:
        doc = frappe.new_doc("Item Group")
        doc.update(data)
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
        return {"message": "Item Group created successfully", "name": doc.name}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Create Item Group API")
        return {"error": str(e)}

# 3. Get Item Group Details
@frappe.whitelist(allow_guest=True)
def getItemGroupDetails():
    if frappe.request.method != "POST":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only POST method allowed"}

    if not authenticate_user():
        return {"error": "Unauthorized"}

    data = frappe.request.get_json()
    id = data.get("name") or data.get("id")
    if not id:
        return {"error": "Missing Item Group ID"}

    try:
        doc = frappe.get_doc("Item Group", id)
        return {"message": doc.as_dict()}
    except frappe.DoesNotExistError:
        frappe.local.response["http_status_code"] = 404
        return {"error": "Item Group not found"}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Item Group Details API")
        return {"error": str(e)}

# 4. Update Item Group
@frappe.whitelist(allow_guest=True)
def updateItemGroup():
    if frappe.request.method != "POST":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only POST method allowed"}

    if not authenticate_user():
        return {"error": "Unauthorized"}

    data = frappe.request.get_json()
    id = data.get("name") or data.get("id")
    if not id:
        return {"error": "Missing Item Group ID"}

    try:
        doc = frappe.get_doc("Item Group", id)
        doc.update(data)
        doc.save(ignore_permissions=True)
        frappe.db.commit()
        return {"message": "Item Group updated successfully", "updated_data": doc.as_dict()}
    except frappe.DoesNotExistError:
        frappe.local.response["http_status_code"] = 404
        return {"error": "Item Group not found"}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Update Item Group API")
        return {"error": str(e)}

# 5. Delete Item Group
@frappe.whitelist(allow_guest=True)
def deleteItemGroup():
    if frappe.request.method != "POST":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only POST method allowed"}

    if not authenticate_user():
        return {"error": "Unauthorized"}

    data = frappe.request.get_json()
    id = data.get("name") or data.get("id")
    if not id:
        return {"error": "Missing Item Group ID"}

    try:
        frappe.delete_doc("Item Group", id, ignore_permissions=True)
        frappe.db.commit()
        return {"message": f"Item Group {id} deleted successfully"}
    except frappe.DoesNotExistError:
        frappe.local.response["http_status_code"] = 404
        return {"error": "Item Group not found"}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Delete Item Group API")
        return {"error": str(e)}


# -------------------- Material Request APIs --------------------

@frappe.whitelist(allow_guest=True)
def listMaterialRequests():
	if frappe.request.method != "GET":
		frappe.local.response["http_status_code"] = 405
		return {"error": "Only GET method allowed"}
	if not authenticate_user():
		return {"error": "Unauthorized"}

	try:
		mr_list = frappe.get_all(
			"Material Request",
			fields=["name", "material_request_type", "status", "transaction_date", "company"],
			order_by="creation desc",
			# limit_page_length=20
		)
		return {"message": mr_list}
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "List Material Request API")
		return {"error": str(e)}

@frappe.whitelist(allow_guest=True)
def createMaterialRequest():
	if frappe.request.method != "POST":
		frappe.local.response["http_status_code"] = 405
		return {"error": "Only POST method allowed"}
	if not authenticate_user():
		return {"error": "Unauthorized"}

	data = frappe.request.get_json()
	try:
		doc = frappe.new_doc("Material Request")
		doc.update(data)
		doc.insert(ignore_permissions=True)
		frappe.db.commit()
		return {"message": "Material Request created successfully", "name": doc.name}
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Create Material Request API")
		return {"error": str(e)}

@frappe.whitelist(allow_guest=True)
def filterMaterialRequests():
	if frappe.request.method != "POST":
		frappe.local.response["http_status_code"] = 405
		return {"error": "Only POST method allowed"}
	if not authenticate_user():
		return {"error": "Unauthorized"}

	data = frappe.request.get_json()
	filters = {}
	if data.get("material_request_type"):
		filters["material_request_type"] = data["material_request_type"]
	if data.get("status"):
		filters["status"] = data["status"]

	try:
		mr_list = frappe.get_all(
			"Material Request",
			filters=filters,
			fields=["name", "material_request_type", "status", "transaction_date"],
			order_by="creation desc",
			# limit_page_length=20,
		)
		return {"message": mr_list}
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Filter Material Request API")
		return {"error": str(e)}

@frappe.whitelist(allow_guest=True)
def updateMaterialRequest():
	if frappe.request.method != "POST":
		frappe.local.response["http_status_code"] = 405
		return {"error": "Only POST method allowed"}
	if not authenticate_user():
		return {"error": "Unauthorized"}

	data = frappe.request.get_json()
	id = data.get("name") or data.get("id")
	if not id:
		return {"error": "Missing Material Request ID"}

	try:
		doc = frappe.get_doc("Material Request", id)
		doc.update(data)
		doc.save(ignore_permissions=True)
		frappe.db.commit()
		return {"message": "Material Request updated successfully", "updated_data": doc.as_dict()}
	except frappe.DoesNotExistError:
		frappe.local.response["http_status_code"] = 404
		return {"error": "Material Request not found"}
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Update Material Request API")
		return {"error": str(e)}

@frappe.whitelist(allow_guest=True)
def deleteMaterialRequest():
	if frappe.request.method != "POST":
		frappe.local.response["http_status_code"] = 405
		return {"error": "Only POST method allowed"}
	if not authenticate_user():
		return {"error": "Unauthorized"}

	data = frappe.request.get_json()
	id = data.get("name") or data.get("id")
	if not id:
		return {"error": "Missing Material Request ID"}

	try:
		frappe.delete_doc("Material Request", id, ignore_permissions=True)
		frappe.db.commit()
		return {"message": f"Material Request {id} deleted successfully"}
	except frappe.DoesNotExistError:
		frappe.local.response["http_status_code"] = 404
		return {"error": "Material Request not found"}
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Delete Material Request API")
		return {"error": str(e)}

@frappe.whitelist(allow_guest=True)
def getMaterialRequestDetails():
	if frappe.request.method != "POST":
		frappe.local.response["http_status_code"] = 405
		return {"error": "Only POST method allowed"}
	if not authenticate_user():
		return {"error": "Unauthorized"}

	data = frappe.request.get_json()
	id = data.get("name") or data.get("id")
	if not id:
		return {"error": "Missing Material Request ID"}

	try:
		doc = frappe.get_doc("Material Request", id)
		return {"message": doc.as_dict()}
	except frappe.DoesNotExistError:
		frappe.local.response["http_status_code"] = 404
		return {"error": "Material Request not found"}
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Get Material Request Details API")
		return {"error": str(e)}

# -------------------- Stock Entry APIs --------------------

@frappe.whitelist(allow_guest=True)
def listStockEntries():
	if frappe.request.method != "GET":
		frappe.local.response["http_status_code"] = 405
		return {"error": "Only GET method allowed"}
	if not authenticate_user():
		return {"error": "Unauthorized"}

	try:
		se_list = frappe.get_all(
			"Stock Entry",
			fields=["name", "purpose", "stock_entry_type", "posting_date", "company"],
			order_by="creation desc",
			# limit_page_length=20
		)
		return {"message": se_list}
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "List Stock Entry API")
		return {"error": str(e)}

@frappe.whitelist(allow_guest=True)
def createStockEntry():
	if frappe.request.method != "POST":
		frappe.local.response["http_status_code"] = 405
		return {"error": "Only POST method allowed"}
	if not authenticate_user():
		return {"error": "Unauthorized"}

	data = frappe.request.get_json()
	try:
		doc = frappe.new_doc("Stock Entry")
		doc.update(data)
		doc.insert(ignore_permissions=True)
		frappe.db.commit()
		return {"message": "Stock Entry created successfully", "name": doc.name}
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Create Stock Entry API")
		return {"error": str(e)}

@frappe.whitelist(allow_guest=True)
def filterStockEntries():
	if frappe.request.method != "POST":
		frappe.local.response["http_status_code"] = 405
		return {"error": "Only POST method allowed"}
	if not authenticate_user():
		return {"error": "Unauthorized"}

	data = frappe.request.get_json()
	filters = {}
	if data.get("purpose"):
		filters["purpose"] = data["purpose"]
	if data.get("stock_entry_type"):
		filters["stock_entry_type"] = data["stock_entry_type"]

	try:
		se_list = frappe.get_all(
			"Stock Entry",
			filters=filters,
			fields=["name", "purpose", "stock_entry_type", "posting_date"],
			order_by="creation desc",
			# limit_page_length=20,
		)
		return {"message": se_list}
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Filter Stock Entry API")
		return {"error": str(e)}

@frappe.whitelist(allow_guest=True)
def updateStockEntry():
	if frappe.request.method != "POST":
		frappe.local.response["http_status_code"] = 405
		return {"error": "Only POST method allowed"}
	if not authenticate_user():
		return {"error": "Unauthorized"}

	data = frappe.request.get_json()
	id = data.get("name") or data.get("id")
	if not id:
		return {"error": "Missing Stock Entry ID"}

	try:
		doc = frappe.get_doc("Stock Entry", id)
		doc.update(data)
		doc.save(ignore_permissions=True)
		frappe.db.commit()
		return {"message": "Stock Entry updated successfully", "updated_data": doc.as_dict()}
	except frappe.DoesNotExistError:
		frappe.local.response["http_status_code"] = 404
		return {"error": "Stock Entry not found"}
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Update Stock Entry API")
		return {"error": str(e)}

@frappe.whitelist(allow_guest=True)
def deleteStockEntry():
	if frappe.request.method != "POST":
		frappe.local.response["http_status_code"] = 405
		return {"error": "Only POST method allowed"}
	if not authenticate_user():
		return {"error": "Unauthorized"}

	data = frappe.request.get_json()
	id = data.get("name") or data.get("id")
	if not id:
		return {"error": "Missing Stock Entry ID"}

	try:
		frappe.delete_doc("Stock Entry", id, ignore_permissions=True)
		frappe.db.commit()
		return {"message": f"Stock Entry {id} deleted successfully"}
	except frappe.DoesNotExistError:
		frappe.local.response["http_status_code"] = 404
		return {"error": "Stock Entry not found"}
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Delete Stock Entry API")
		return {"error": str(e)}

@frappe.whitelist(allow_guest=True)
def getStockEntryDetails():
	if frappe.request.method != "POST":
		frappe.local.response["http_status_code"] = 405
		return {"error": "Only POST method allowed"}
	if not authenticate_user():
		return {"error": "Unauthorized"}

	data = frappe.request.get_json()
	id = data.get("name") or data.get("id")
	if not id:
		return {"error": "Missing Stock Entry ID"}

	try:
		doc = frappe.get_doc("Stock Entry", id)
		return {"message": doc.as_dict()}
	except frappe.DoesNotExistError:
		frappe.local.response["http_status_code"] = 404
		return {"error": "Stock Entry not found"}
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Get Stock Entry Details API")
		return {"error": str(e)}