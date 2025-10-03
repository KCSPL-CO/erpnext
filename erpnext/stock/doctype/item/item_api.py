import base64
import frappe
import json

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
def listItems():
    if frappe.request.method != "GET":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only GET method allowed"}

    if not authenticate_user():
        return {"error": "Unauthorized"}

    try:
        total_inventory_value = 0.0  # 🔹 Total of all inventory values

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
                "standard_rate",
                "valuation_rate AS default_valuation_rate",
                "safety_stock",
                "disabled AS status",
				"parent_item_group"
            ],
            order_by="creation desc",
        )

        for item in items:
            # 🔹 Get stock by warehouse
            stock_entries = frappe.db.sql("""
                SELECT
                    warehouse,
                    SUM(actual_qty) AS stock_qty,
                    SUM(stock_value) AS stock_value
                FROM `tabStock Ledger Entry`
                WHERE item_code = %s
                GROUP BY warehouse
            """, item["item_code"], as_dict=True)

            item["stock_by_warehouse"] = stock_entries
            item["total_stock_qty"] = sum(entry["stock_qty"] or 0 for entry in stock_entries)
            item["total_stock_value"] = sum(entry["stock_value"] or 0 for entry in stock_entries)

            # 🔹 Get latest valuation rate from stock ledger
            valuation_data = frappe.db.sql("""
                SELECT valuation_rate
                FROM `tabStock Ledger Entry`
                WHERE item_code = %s AND valuation_rate IS NOT NULL
                ORDER BY posting_date DESC, posting_time DESC
                LIMIT 1
            """, (item["item_code"],), as_dict=True)

            latest_valuation_rate = valuation_data[0].valuation_rate if valuation_data else 0.0
            item["valuation_rate"] = float(latest_valuation_rate or 0.0)

            # 🔹 Calculate inventory value
            item["inventory_value"] = round(item["total_stock_qty"] * item["valuation_rate"], 2)

            # 🔹 Add to total inventory value
            total_inventory_value += item["inventory_value"]

            # 🔹 Human-readable status
            item["status"] = "Disabled" if item["status"] else "Active"

        return {
            "message": items,
            "total_inventory_value": round(total_inventory_value, 2)  # ✅ Return the grand total
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "List Item API with Valuation Rate")
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
			fields=["name","title", "material_request_type","schedule_date", "set_warehouse","status", "transaction_date", "company"],
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

# @frappe.whitelist(allow_guest=True)
# def listStockEntries():
# 	if frappe.request.method != "GET":
# 		frappe.local.response["http_status_code"] = 405
# 		return {"error": "Only GET method allowed"}
# 	if not authenticate_user():
# 		return {"error": "Unauthorized"}

# 	try:
# 		se_list = frappe.get_all(
# 			"Stock Entry",
# 			fields=["name", "purpose", "stock_entry_type", "posting_date", "company","status","from_warehouse","to_warehouse","Supplier"],
# 			order_by="creation desc",
# 			# limit_page_length=20
# 		)
# 		return {"message": se_list}
# 	except Exception as e:
# 		frappe.log_error(frappe.get_traceback(), "List Stock Entry API")
# 		return {"error": str(e)}

@frappe.whitelist(allow_guest=True)
def listStockEntries():
    if frappe.request.method != "GET":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only GET method allowed"}
    
    if not authenticate_user():
        return {"error": "Unauthorized"}

    try:
        entries = frappe.get_all(
            "Stock Entry",
            fields=["name"],
            order_by="creation desc",
            limit_page_length=20
        )

        stock_entries = []
        for e in entries:
            doc = frappe.get_doc("Stock Entry", e.name)
            stock_entries.append({
                "name": doc.name,
                "purpose": doc.purpose,
                "stock_entry_type": doc.stock_entry_type,
                "posting_date": doc.posting_date,
                "company": doc.company,
                "status": (
                    "Draft" if doc.docstatus == 0 else
                    "Submitted" if doc.docstatus == 1 else
                    "Cancelled"
                ),
                "from_warehouse": doc.from_warehouse,
                "to_warehouse": doc.to_warehouse,
                "supplier": doc.supplier
            })

        return {"message": stock_entries}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "List Stock Entry API")
        return {"error": str(e)}


@frappe.whitelist(allow_guest=False)
def create_stock_entry_from_material_request():
    user = authenticate_user()
    if not user:
        return {"status": "error", "message": "Unauthorized"}
 
    try:
        data = frappe.local.form_dict
        material_request_id = data.get("material_request_id")
 
        if not material_request_id:
            frappe.throw(_("Material Request ID is required"))
 
        material_request = frappe.get_doc("Material Request", material_request_id)
 
        if material_request.docstatus != 1:
            return {"status": "error", "message": "Material Request must be submitted"}
 
        # Use the purpose from the Material Request (it becomes stock_entry_type)
        stock_entry_type = material_request.material_request_type
 
    
        # Safely extract from and to warehouse from first item
        first_item = material_request.items[0]
        from_warehouse = first_item.from_warehouse
        to_warehouse = first_item.warehouse
 
        if not from_warehouse or not to_warehouse:
            return {"status": "error", "message": "Both from_warehouse and to_warehouse are required on Material Request items"}
 
        # Create Stock Entry
        stock_entry = frappe.new_doc("Stock Entry")
        stock_entry.stock_entry_type = stock_entry_type
        stock_entry.from_warehouse = from_warehouse
        stock_entry.to_warehouse = to_warehouse
        stock_entry.material_request = material_request.name
 
        for item in material_request.items:
            stock_entry.append("items", {
                "item_code": item.item_code,
                "qty": item.qty,
                "uom": item.uom,
                "s_warehouse": item.from_warehouse,
                "t_warehouse": item.warehouse,
                "material_request": material_request.name,
                "material_request_item": item.name
            })
 
        stock_entry.insert(ignore_permissions=True)
        frappe.db.commit()
 
        return {
            "status": "success",
            "message": f"Stock Entry {stock_entry.name} created",
            "stock_entry": stock_entry.name
        }
 
    except frappe.DoesNotExistError:
        return {"status": "error", "message": "Material Request not found"}
 
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "create_stock_entry_from_material_request")
        return {"status": "error", "message": str(e)} 

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
def changeStockEntryStatus():
    if frappe.request.method != "POST":
        frappe.local.response["http_status_code"] = 405   
        return {"error": "Only POST method allowed"}
    
    if not authenticate_user():
        return {"error": "Unauthorized"}
    
    data = frappe.request.get_json()
    stock_entry_id = data.get("name") or data.get("id")
    action = data.get("action")  # expected: "submit" or "cancel"
    
    if not stock_entry_id:
        return {"error": "Missing Stock Entry ID"}
    if not action:
        return {"error": "Missing action (submit / cancel)"}
    
    try:
        doc = frappe.get_doc("Stock Entry", stock_entry_id)
        
        if action.lower() == "submit":
            if doc.docstatus == 0:  # Draft
                doc.submit()
                frappe.db.commit()
                return {"message": f"Stock Entry {doc.name} submitted successfully"}
            else:
                return {"error": f"Stock Entry {doc.name} is already submitted or cancelled"}
        
        elif action.lower() == "cancel":
            if doc.docstatus == 1:  # Submitted
                doc.cancel()
                frappe.db.commit()
                return {"message": f"Stock Entry {doc.name} cancelled successfully"}
            else:
                return {"error": f"Stock Entry {doc.name} is not in submitted state"}
        
        else:
            return {"error": "Invalid action. Use 'submit' or 'cancel'"}
    
    except frappe.DoesNotExistError:
        frappe.local.response["http_status_code"] = 404
        return {"error": "Stock Entry not found"}
    
    except frappe.ValidationError as ve:
        frappe.local.response["http_status_code"] = 400
        frappe.db.rollback()
        return {"error": f"Validation Error: {str(ve)}"}
    
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Change Stock Entry Status API")
        frappe.local.response["http_status_code"] = 500
        frappe.db.rollback()
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
        # Fetch the doc
        doc = frappe.get_doc("Stock Entry", id)
        doc.update(data)
 
        if data.get("docstatus") == 1:
            # Try to submit directly, will trigger validation
            doc.submit()
        else:
            doc.save(ignore_permissions=True)
 
        frappe.db.commit()
        return {
            "message": "Stock Entry updated successfully",
            "updated_data": doc.as_dict()
        }
 
    except frappe.DoesNotExistError:
        frappe.local.response["http_status_code"] = 404
        return {"error": "Stock Entry not found"}
 
    except frappe.ValidationError as ve:
        frappe.local.response["http_status_code"] = 400
        frappe.db.rollback()  # VERY IMPORTANT: rollback if error occurs
        return {"error": f"Validation Error: {str(ve)}"}
 
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Update Stock Entry API")
        frappe.local.response["http_status_code"] = 500
        frappe.db.rollback()
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


# ------------------ CREATE MANUFACTURER ------------------
@frappe.whitelist(allow_guest=False)
def create_manufacturer():
    if frappe.request.method != "POST":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Method Not Allowed"}

    if not authenticate_user():
        return {"message": "Unauthorized", "success": False}

    data = json.loads(frappe.request.data or "{}")

    doc = frappe.new_doc("Manufacturer")
    for field in [
        "short_name", "full_name", "website", "country", "logo",
         "notes"
    ]:
        doc.set(field, data.get(field))

    doc.insert(ignore_permissions=True)
    frappe.db.commit()

    return {"message": "Manufacturer created", "name": doc.name, "success": True}


# ------------------ GET ALL MANUFACTURERS ------------------
@frappe.whitelist(allow_guest=False)
def get_all_manufacturers():
    if frappe.request.method != "GET":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Method Not Allowed"}

    if not authenticate_user():
        return {"message": "Unauthorized", "success": False}

    manufacturers = frappe.get_all(
        "Manufacturer",
        fields=[
            "name", "short_name", "full_name", "website", "country",
            "logo","notes"
        ],
        order_by="modified desc"
    )
    return {"success": True, "data": manufacturers}


# ------------------ GET MANUFACTURER BY ID ------------------
@frappe.whitelist(allow_guest=False)
def get_manufacturer(manufacturer_id):
    if frappe.request.method != "GET":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Method Not Allowed"}

    if not authenticate_user():
        return {"message": "Unauthorized", "success": False}

    doc = frappe.get_doc("Manufacturer", manufacturer_id)
    return {
        "success": True,
        "data": {
            "name": doc.name,
            "short_name": doc.short_name,
            "full_name": doc.full_name,
            "website": doc.website,
            "country": doc.country,
            "logo": doc.logo,
            
            "notes": doc.notes
        }
    }


# ------------------ UPDATE MANUFACTURER ------------------
@frappe.whitelist(allow_guest=False)
def update_manufacturer(manufacturer_id):
    if frappe.request.method != "PUT":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Method Not Allowed"}

    if not authenticate_user():
        return {"message": "Unauthorized", "success": False}

    data = json.loads(frappe.request.data or "{}")

    doc = frappe.get_doc("Manufacturer", manufacturer_id)
    for field in [
        "short_name", "full_name", "website", "country", "logo",
         "notes"
    ]:
        if field in data:
            doc.set(field, data.get(field))

    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"message": "Manufacturer updated", "name": doc.name, "success": True}



# ------------------ CREATE BRAND ------------------
@frappe.whitelist(allow_guest=False)
def create_brand():
    import json

    if frappe.request.method != "POST":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Method Not Allowed"}

    if not authenticate_user():
        return {"message": "Unauthorized", "success": False}

    content_type = frappe.get_request_header("Content-Type", "")
    doc = frappe.new_doc("Brand")

    try:
        # Multipart request
        if "multipart/form-data" in content_type:
            doc.brand = frappe.form_dict.get("brand")
            doc.description = frappe.form_dict.get("description")

            # Handle child table
            if frappe.form_dict.get("brand_defaults"):
                brand_defaults_list = json.loads(frappe.form_dict.get("brand_defaults"))
                for row in brand_defaults_list:
                    doc.append("brand_defaults", row)

            # Save Brand first
            doc.insert(ignore_permissions=True)
            frappe.db.commit()

            # File upload
            if "image" in frappe.request.files:
                file = frappe.request.files["image"]
                file_content = file.read()   # <-- raw bytes, no base64

                _file = frappe.get_doc({
                    "doctype": "File",
                    "file_name": file.filename,
                    "attached_to_doctype": "Brand",
                    "attached_to_name": doc.name,
                    "is_private": 0,
                    "content": file_content,   # <-- raw bytes here
                })
                _file.insert(ignore_permissions=True)
                frappe.db.commit()

                # Save file URL into Brand
                doc.image = _file.file_url
                doc.save(ignore_permissions=True)

        else:
            # JSON fallback
            data = json.loads(frappe.request.data or "{}")
            doc.brand = data.get("brand")
            doc.description = data.get("description")

            for row in data.get("brand_defaults", []):
                doc.append("brand_defaults", row)

            doc.insert(ignore_permissions=True)
            frappe.db.commit()

            if data.get("image"):
                doc.image = data.get("image")
                doc.save(ignore_permissions=True)

        return {
            "message": f"Brand '{doc.brand}' created successfully",
            "name": doc.name,
            "success": True,
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Create Brand API Error")
        return {"message": str(e), "success": False}

# ------------------ GET ALL BRANDS ------------------
@frappe.whitelist(allow_guest=False)
def get_all_brands():
    if frappe.request.method != "GET":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Method Not Allowed"}

    if not authenticate_user():
        return {"message": "Unauthorized", "success": False}

    brands = frappe.get_all(
        "Brand",
        fields=["name", "brand","description"],
        order_by="modified desc"
    )
    return {"success": True, "data": brands}


# ------------------ GET BRAND BY ID ------------------
@frappe.whitelist(allow_guest=False)
def get_brand(brand_id):
    if frappe.request.method != "GET":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Method Not Allowed"}

    if not authenticate_user():
        return {"message": "Unauthorized", "success": False}

    doc = frappe.get_doc("Brand", brand_id)
    return {
        "success": True,
        "data": doc.as_dict()
    }


# ------------------ UPDATE BRAND ------------------
@frappe.whitelist(allow_guest=False)
def update_brand(brand_id):
    if frappe.request.method != "PUT":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Method Not Allowed"}

    if not authenticate_user():
        return {"message": "Unauthorized", "success": False}

    data = json.loads(frappe.request.data or "{}")

    doc = frappe.get_doc("Brand", brand_id)
    if "brand" in data:
        doc.brand = data.get("brand")

    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"message": "Brand updated", "name": doc.name, "success": True}



# ------------------ CREATE UOM ------------------
@frappe.whitelist(allow_guest=False)
def create_uom():
    if frappe.request.method != "POST":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Method Not Allowed"}

    if not authenticate_user():
        return {"message": "Unauthorized", "success": False}

    data = json.loads(frappe.request.data or "{}")

    doc = frappe.new_doc("UOM")
    doc.uom_name = data.get("uom_name")
    doc.must_be_whole_number = data.get("must_be_whole_number")
    doc.enabled = data.get("enabled", 1)

    doc.insert(ignore_permissions=True)
    frappe.db.commit()

    return {"message": "UOM created", "name": doc.name, "success": True}


# ------------------ GET ALL UOMs ------------------
@frappe.whitelist(allow_guest=False)
def get_all_uoms():
    if frappe.request.method != "GET":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Method Not Allowed"}

    if not authenticate_user():
        return {"message": "Unauthorized", "success": False}

    uoms = frappe.get_all(
        "UOM",
        fields=["name", "uom_name", "enabled"],
        order_by="modified desc"
    )
    return {"success": True, "data": uoms}


# ------------------ GET UOM BY ID ------------------
@frappe.whitelist(allow_guest=False)
def get_uom(uom_id):
    if frappe.request.method != "GET":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Method Not Allowed"}

    if not authenticate_user():
        return {"message": "Unauthorized", "success": False}

    doc = frappe.get_doc("UOM", uom_id)
    return {
        "success": True,
        "data": {
            "message":doc
        }
    }


# ------------------ UPDATE UOM ------------------
@frappe.whitelist(allow_guest=False)
def update_uom(uom_id):
    if frappe.request.method != "PUT":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Method Not Allowed"}

    if not authenticate_user():
        return {"message": "Unauthorized", "success": False}

    data = json.loads(frappe.request.data or "{}")

    doc = frappe.get_doc("UOM", uom_id)
    if "uom_name" in data:
        doc.uom_name = data.get("uom_name")
    if "enabled" in data:
        doc.enabled = data.get("enabled")

    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"message": "UOM updated", "name": doc.name, "success": True}



# ------------------ Generic List API ------------------
def get_list_api(doctype):
    """Generic list API with pagination and auth"""
    if frappe.request.method != "GET":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only GET method allowed"}
 
    if not authenticate_user():
        frappe.local.response["http_status_code"] = 401
        return {"error": "Unauthorized"}
 
    try:
        # Pagination
        limit_start = int(frappe.form_dict.get("limit_start", 0))
        raw_limit = frappe.form_dict.get("limit_page_length", 10)
 
        total = frappe.db.count(doctype)
        if str(raw_limit).lower() in ("0", "all"):
            limit_page_length = total
        else:
            try:
                limit_page_length = int(raw_limit)
            except ValueError:
                limit_page_length = 10
 
        MAX_LIMIT = 1000
        if limit_page_length > MAX_LIMIT:
            limit_page_length = MAX_LIMIT
 
        data = frappe.get_all(
            doctype,
            fields=["*"],
            order_by="creation desc",
            limit_start=limit_start,
            limit_page_length=limit_page_length,
        )
 
        return {
            "total": total,
            "limit_start": limit_start,
            "applied_limit": limit_page_length,
            "returned_count": len(data),
            "data": data,
        }
 
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"List API for {doctype}")
        frappe.local.response["http_status_code"] = 500
        return {"error": str(e)}
 
@frappe.whitelist(allow_guest=True)
def listItemTaxTemplate():
    return get_list_api("Item Tax Template")
 


@frappe.whitelist()
def create_item_tax_template():
    """API to create Item Tax Template with child rows (Tax Rates)"""
    if frappe.request.method != "POST":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only POST method allowed"}

    # --- Authentication check ---
    if not authenticate_user():
        frappe.local.response["http_status_code"] = 401
        return {"error": "Unauthorized"}

    try:
        data = frappe.form_dict  # request payload

        # Required fields
        title = data.get("title")
        company = data.get("company")
        tax_rates = data.get("tax_rates")  # expecting JSON array

        if not title or not company:
            return {"error": "Missing required fields: title or company"}

        # Create new Doc
        doc = frappe.new_doc("Item Tax Template")
        doc.title = title
        doc.company = company
        doc.disabled = data.get("disabled", 0)

        # Handle child table: tax_rates
        # Expecting: [{"tax_type": "GST 18%", "tax_rate": 18}, ...]
        if tax_rates:
            if isinstance(tax_rates, str):
                import json
                tax_rates = json.loads(tax_rates)

            for tr in tax_rates:
                doc.append("taxes", {
                    "tax_type": tr.get("tax_type"),
                    "tax_rate": tr.get("tax_rate")
                })

        doc.insert(ignore_permissions=True)
        frappe.db.commit()

        return {
            "success": True,
            "message":("Item Tax Template created successfully"),
            "id": doc.name
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Create Item Tax Template API")
        frappe.local.response["http_status_code"] = 500
        return {"error": str(e)}




@frappe.whitelist()
def get_item_tax_template():
    """API to fetch Item Tax Template by ID (via POST body)"""
    if frappe.request.method != "POST":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only POST method allowed"}

    # --- Authentication check ---
    if not authenticate_user():
        frappe.local.response["http_status_code"] = 401
        return {"error": "Unauthorized"}

    try:
        data = frappe.form_dict  # request payload
        doc_id = data.get("id")

        if not doc_id:
            return {"error": "Missing required field: id"}

        # Fetch document
        doc = frappe.get_doc("Item Tax Template", doc_id)

        # Serialize doc with children
        result = {
            "id": doc.name,
            "title": doc.title,
            "company": doc.company,
            "disabled": doc.disabled,
            "tax_rates": [
                {
                    "tax_type": tr.tax_type,
                    "tax_rate": tr.tax_rate
                } for tr in doc.taxes
            ]
        }

        return {"success": True, "data": result}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Item Tax Template API")
        frappe.local.response["http_status_code"] = 500
        return {"error": str(e)}


@frappe.whitelist(allow_guest=True)
def listSalesTaxAndChargesTemplate():
    return get_list_api("Sales Taxes and Charges Template")
 



# -------------------------------
# CREATE API
# -------------------------------
@frappe.whitelist()
def create_sales_taxes_template():
    """API to create Sales Taxes and Charges Template with child rows"""
    if frappe.request.method != "POST":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only POST method allowed"}
 
    # --- Authentication check ---
    if not authenticate_user():
        frappe.local.response["http_status_code"] = 401
        return {"error": "Unauthorized"}
 
    try:
        # Get JSON payload
        data = frappe.request.get_json(force=True)
 
        # Required fields
        title = data.get("title")
        company = data.get("company")
        if not title or not company:
            return {"error": "Missing required fields: title or company"}
 
        # Create new Doc
        doc = frappe.new_doc("Sales Taxes and Charges Template")
        doc.title = title
        doc.company = company
        doc.state = data.get("state_category")
        doc.is_default = data.get("is_default", 0)
        doc.disabled = data.get("disabled", 0)
        doc.tax_category = data.get("tax_category")
 
        # Handle child table: Sales Taxes and Charges
        taxes = data.get("taxes")
        if taxes:
            for row in taxes:
                doc.append("taxes", row)  # row should be dict with all fields
 
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
 
        return {
            "success": True,
            "message": f"Sales Taxes and Charges Template {doc.name} created successfully",
            "id": doc.name
        }
 
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Create Sales Taxes Template API")
        frappe.local.response["http_status_code"] = 500
        return {"error": str(e)}
 
# -------------------------------
# DETAILS API
# -------------------------------
@frappe.whitelist(allow_guest=False)
def get_sales_taxes_template(name=None):
    """Get details of a Sales Taxes and Charges Template including child rows"""
    if not name:
        return {"error": "Template name is required"}
 
    try:
        doc = frappe.get_doc("Sales Taxes and Charges Template", name)
 
        # Convert doc + children to dict with all fields
        data = doc.as_dict()
        data["taxes"] = [t.as_dict() for t in doc.taxes]
 
        return {"success": True, "data": data}
 
    except frappe.DoesNotExistError:
        frappe.local.response["http_status_code"] = 404
        return {"error": f"Sales Taxes Template {name} does not exist"}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Sales Taxes Template API")
        frappe.local.response["http_status_code"] = 500
        return {"error": str(e)}
 
 
# Update API
@frappe.whitelist()
def update_sales_taxes_template():
    """API to update Sales Taxes and Charges Template and its child rows"""
    if frappe.request.method not in ["PUT", "POST"]:  # allow POST for clients that don't support PUT
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only PUT/POST method allowed"}
 
    # --- Authentication check ---
    if not authenticate_user():
        frappe.local.response["http_status_code"] = 401
        return {"error": "Unauthorized"}
 
    try:
        # Get JSON payload
        data = frappe.request.get_json(force=True)
        name = data.get("name")
 
        if not name:
            return {"error": "Template name is required for update"}
 
        # Load existing doc
        doc = frappe.get_doc("Sales Taxes and Charges Template", name)
 
        # Update parent fields (if provided)
        if "title" in data:
            doc.title = data["title"]
        if "company" in data:
            doc.company = data["company"]
        if "state_category" in data:
            doc.state = data["state_category"]
        if "is_default" in data:
            doc.is_default = data["is_default"]
        if "disabled" in data:
            doc.disabled = data["disabled"]
        if "tax_category" in data:
            doc.tax_category = data["tax_category"]
 
        # Handle child table updates (replace all rows if provided)
        if "taxes" in data:
            # Clear existing rows
            doc.set("taxes", [])
 
            # Append new rows
            for row in data["taxes"]:
                doc.append("taxes", row)
 
        # Save doc
        doc.save(ignore_permissions=True)
        frappe.db.commit()
 
        return {
            "success": True,
            "message": f"Sales Taxes and Charges Template {doc.name} updated successfully",
            "data": doc.as_dict()
        }
 
    except frappe.DoesNotExistError:
        frappe.local.response["http_status_code"] = 404
        return {"error": f"Sales Taxes Template {name} does not exist"}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Update Sales Taxes Template API")
        frappe.local.response["http_status_code"] = 500
        return {"error": str(e)}
 





# -------------------------------
# Tax Category API
# -------------------------------

@frappe.whitelist(allow_guest=True)
def list_tax_category():
    return get_list_api("Tax Category")
 


 # -------------------------------
# Create Tax Category API
# -------------------------------
 
@frappe.whitelist()
def create_tax_category():
    """API to create Tax Category"""
    if frappe.request.method != "POST":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only POST method allowed"}
 
    if not authenticate_user():
        frappe.local.response["http_status_code"] = 401
        return {"error": "Unauthorized"}
 
    try:
        data = frappe.request.get_json(force=True)
 
        title = data.get("title")
        if not title:
            return {"error": "Missing required field: title"}
 
        doc = frappe.new_doc("Tax Category")
        doc.title = title
        doc.disabled = data.get("disabled", 0)
 
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
 
        return {
            "success": True,
            "message": f"Tax Category {doc.name} created successfully",
            "id": doc.name,
            # "data": doc.as_dict()
        }
 
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Create Tax Category API")
        frappe.local.response["http_status_code"] = 500
        return {"error": str(e)}
 
# -------------------------------
# DETAILS TAX CATEGORY
# -------------------------------
@frappe.whitelist(allow_guest=False)
def get_tax_category(name=None):
    """Get details of a single Tax Category"""
    if not name:
        return {"error": "Tax Category name is required"}
 
    try:
        doc = frappe.get_doc("Tax Category", name)
        return {
            "success": True,
            "data": doc.as_dict()
        }
 
    except frappe.DoesNotExistError:
        frappe.local.response["http_status_code"] = 404
        return {"error": f"Tax Category {name} does not exist"}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Tax Category API")
        frappe.local.response["http_status_code"] = 500
        return {"error": str(e)}
 
 
# -------------------------------
# UPDATE TAX CATEGORY
# -------------------------------
@frappe.whitelist()
def update_tax_category():
    """API to update Tax Category"""
    if frappe.request.method not in ["PUT", "POST"]:
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only PUT/POST method allowed"}
 
    if not authenticate_user():
        frappe.local.response["http_status_code"] = 401
        return {"error": "Unauthorized"}
 
    try:
        data = frappe.request.get_json(force=True)
 
        name = data.get("name")
        if not name:
            return {"error": "Tax Category name is required for update"}
 
        doc = frappe.get_doc("Tax Category", name)
 
        if "title" in data:
            doc.title = data["title"]
        if "disabled" in data:
            doc.disabled = data["disabled"]
 
        doc.save(ignore_permissions=True)
        frappe.db.commit()
 
        return {
            "success": True,
            "message": f"Tax Category {doc.name} updated successfully",
            # "data": doc.as_dict()
        }
 
    except frappe.DoesNotExistError:
        frappe.local.response["http_status_code"] = 404
        return {"error": f"Tax Category {name} does not exist"}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Update Tax Category API")
        frappe.local.response["http_status_code"] = 500
        return {"error": str(e)}
 