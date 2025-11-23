import frappe

def setup():
    roles = ["IP Manager", "IP Staff"]
    for role in roles:
        if not frappe.db.exists("Role", role):
            new_role = frappe.get_doc({
                "doctype": "Role",
                "role_name": role,
                "desk_access": 1
            })
            new_role.insert(ignore_permissions=True)
            frappe.db.commit()
            print(f"Created Role: {role}")
        else:
            print(f"Role {role} already exists")
