# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import json
import frappe
from frappe import _, scrub, throw
from frappe.model.document import Document


class Tasks(Document):

    def validate(self):
        print(f"validate task {self.task_name} owner {self.owner}")
        self.validate_task_name()

    def validate_task_name(self):
        maintask_name = frappe.db.get_value(
            "MainTask", {"name": self.maintask}, "maintask_name"
        )
        self.maintask_name = maintask_name if maintask_name else ""
        self.created_by = frappe.db.get_value(
            "Employee", {"user_id": self.owner}, "employee_name"
        )
        if self.unit_target_time == "Hours":
            self.target_time_minutes = self.target_time * 60
        else:
            self.target_time_minutes = self.target_time


def before_save(doc, method):
    print(f"before save tasks {doc.task_name} owner {doc.owner}")
    if doc.get("__islocal"):
        doc.flags._previous_status = None
    else:
        doc.flags._previous_status = frappe.db.get_value("Tasks", doc.name, "status")


def after_delete(doc, method):
    print(f"after delete tasks {doc.task_name} owner {doc.owner}")
    subtasks = frappe.get_all("SubTask", {"tasks": doc.name})
    for subtask in subtasks:
        if subtask.status != "Done":
            frappe.delete_doc("SubTask", subtask.name, ignore_permissions=True)


def update_fields(doc, method):
    if frappe.flags.in_update:
        # frappe.msgprint(f"In update Tasks")
        return
    frappe.flags.in_update = True

    print(f"update tasks {doc.name} owner {doc.owner}")

    previous_status = doc.flags.get("_previous_status")
    now_status = doc.status
    if previous_status != now_status:
        subtasks = frappe.get_all("SubTask", filters={"tasks": doc.name}, pluck="name")
        for name in subtasks:
            subtask = frappe.get_doc("SubTask", name)
            if subtask.status not in ("Done", "Close", "In Progress", "Pause"):
                # beri tanda sumbernya dari Tasks
                subtask.flags.from_parent_propagation = True
                subtask.status = now_status

                # biar hooks & validate jalan => track_time aman
                subtask.save()
                frappe.msgprint(
                    f"Updated SubTask {subtask.subtask_name} status to {now_status}"
                )
            else:
                frappe.msgprint(
                    f"SubTask {subtask.subtask_name} status is {subtask.status}, not updated."
                )

    frappe.flags.in_update = False


def permission_query_conditions(doc, ptype=None, user=None, debug=False):
    user_id = user or frappe.session.user

    roles = frappe.get_all("Has Role", filters={"parent": user_id}, pluck="role")
    if "System Manager" in roles and user_id == "Administrator":
        return ""

    employee_id = frappe.get_value("Employee", {"user_id": user_id}, "name")

    parent_mteam = frappe.get_all(
        "MainTask Team", filters={"employee": employee_id}, pluck="parent"
    )

    parent_assign_by = frappe.get_all(
        "MainTask Assign By", filters={"employee": employee_id}, pluck="parent"
    )

    if not employee_id:
        return "1=0"

    maintask_ids = "', '".join(parent_mteam)

    assign_by_maintask_ids = "', '".join(parent_assign_by)

    parent_task_pic = frappe.get_all(
        "Task PIC", filters={"employee": employee_id}, pluck="parent"
    )

    task_ids = "', '".join(parent_task_pic) if parent_task_pic else ""

    return f"( tabTasks.owner = '{user_id}' OR tabTasks.maintask IN (SELECT name FROM tabMainTask WHERE owner = '{user_id}' OR assigned_by = '{employee_id}') OR tabTasks.name IN ('{task_ids}') OR tabTasks.maintask IN (SELECT name FROM tabMainTask WHERE name IN ('{maintask_ids}')) OR tabTasks.maintask IN (SELECT name FROM tabMainTask WHERE name IN ('{assign_by_maintask_ids}')))"


def has_permission(doc, ptype, user):
    if user == "Administrator":
        return True

    print(f"has_permission tasks for user: {user}, ptype: {ptype}, doc: {doc.name}")
    employee_id = frappe.get_value("Employee", {"user_id": user}, "name")
    if not employee_id:
        return False

    parent_mteam = frappe.get_all(
        "MainTask Team", filters={"employee": employee_id}, pluck="parent"
    )

    parent_task_pic = frappe.get_all(
        "Task PIC", filters={"employee": employee_id}, pluck="parent"
    )

    parent_assign_by = frappe.get_all(
        "MainTask Assign By", filters={"employee": employee_id}, pluck="parent"
    )

    employee = frappe.get_doc("Employee", employee_id)
    maintask = frappe.get_doc("MainTask", doc.maintask)

    is_owner = doc.owner == user
    is_maintask_owner = maintask.owner == user
    is_task_pic = doc.name in parent_task_pic
    in_team = doc.maintask in parent_mteam
    in_assign_by_list = doc.maintask in parent_assign_by

    if ptype in ("read", None) and (in_team or in_assign_by_list):
        return True

    if ptype == "delete":
        if is_task_pic and not (is_maintask_owner or in_assign_by_list):
            frappe.throw(
                f"{employee.employee_name} is the pic task only and not allowed to deleting {doc.task_name} task.",
                frappe.PermissionError,
            )
            return False

        check_finished_subtask = frappe.get_all(
            "SubTask", {"tasks": doc.name}, pluck="status"
        )
        if ("Done", "Close") in check_finished_subtask:
            frappe.throw(
                f"Sorry {employee.employee_name} one of the subtasks in this task is finished, you can't delete it.",
                frappe.PermissionError,
            )
            return False
    elif ptype == "write":
        if is_owner or is_task_pic or is_maintask_owner:
            return True
        else:
            frappe.throw(
                f"{employee.employee_name} is not allowed to edit {doc.task_name} task",
                frappe.PermissionError,
            )
            return False
    elif ptype == "create":
        if in_assign_by_list or is_maintask_owner:
            return True
        else:
            frappe.throw(
                f"{employee.employee_name} is not allowed to create task in {maintask.maintask_name} maintask.",
                frappe.PermissionError,
            )
            return False

    if is_owner or is_maintask_owner:
        return True

    frappe.throw(
        f"{employee.employee_name} is not allowed to accessing {doc.task_name} task.",
        frappe.PermissionError,
    )
    return False


@frappe.whitelist()
def user_edit_tasks(task_name):
    user = frappe.session.user

    doc = frappe.get_doc("Tasks", task_name)
    maintask = frappe.get_doc("MainTask", doc.maintask)
    employee_id = frappe.get_value("Employee", {"user_id": user}, "name")

    if not employee_id:
        return "none"

    parent_mteam = frappe.get_all(
        "MainTask Team", filters={"employee": employee_id}, pluck="parent"
    )

    parent_task_pic = frappe.get_all(
        "Task PIC", filters={"employee": employee_id}, pluck="parent"
    )

    parent_assign_by = frappe.get_all(
        "MainTask Assign By", filters={"employee": employee_id}, pluck="parent"
    )

    is_owner = doc.owner == user
    is_maintask_owner = maintask.owner == user
    is_task_pic = doc.name in parent_task_pic
    in_team = doc.maintask in parent_mteam
    in_assign_by_list = doc.maintask in parent_assign_by

    privileges = []

    if user == "Administrator":
        privileges.append("admin")

    if is_owner:
        privileges.append("owner_tasks")

    if is_maintask_owner:
        privileges.append("pic_maintask")

    if is_task_pic:
        privileges.append("task_pics")

    return privileges if privileges else ["none"]


@frappe.whitelist()
def get_employees_by_role_and_team(doctype, txt, searchfield, start, page_len, filters):
    maintask = filters.get("maintask")
    if not maintask:
        return []

    txt = txt or ""

    employees = frappe.db.sql(
        """
							  SELECT e.name, e.employee_name
							  FROM `tabEmployee` e
									   JOIN `tabUser` u ON u.name = e.user_id
									   JOIN `tabHas Role` hr ON hr.parent = u.name
									   JOIN `tabMainTask Team` mteam ON mteam.employee = e.name
									   JOIN `tabMainTask` mt ON mt.name = mteam.parent
							  WHERE mt.name = %(maintask)s
								AND e.status = 'Active'
								AND (e.name LIKE %(txt)s OR e.employee_name LIKE %(txt)s)
							  GROUP BY e.name
							  ORDER BY e.employee_name
								  LIMIT %(page_len)s
							  OFFSET %(start)s
							  """,
        {"maintask": maintask, "txt": f"%{txt}%", "start": start, "page_len": page_len},
    )

    return [(emp[0], emp[1]) for emp in employees]


@frappe.whitelist()
def get_open_maintask_as_the_owner(doctype, txt, searchfield, start, page_len, filters):
    user = frappe.session.user

    employee_id = frappe.get_value("Employee", {"user_id": user}, "name")

    conditions = []
    if user != "Administrator":
        conditions.append(
            """(
			mt.owner = %(user)s
			OR mt.name IN (
				SELECT mt2.name
				FROM `tabMainTask` mt2
				LEFT JOIN `tabMainTask Assign By` m2 ON mt2.name = m2.parent
				WHERE m2.employee = %(employee_id)s
			)
		)"""
        )

    conditions.append("(mt.status IN ('Open','In Progress'))")

    conditions.append("(mt.name LIKE %(txt)s OR mt.maintask_name LIKE %(txt)s)")

    where_sql = "WHERE " + " AND ".join(conditions)

    params = {
        "user": user,
        "employee_id": employee_id,
        "txt": f"%{txt}%" if txt else "%",
        "start": start,
        "page_len": page_len,
    }

    maintasks = frappe.db.sql(
        f"""
		SELECT DISTINCT mt.name, mt.maintask_name
		FROM `tabMainTask` mt
		{where_sql}
		ORDER BY mt.creation DESC, mt.name
		LIMIT %(page_len)s OFFSET %(start)s
	""",
        params,
    )

    return maintasks


@frappe.whitelist()
def get_subtask_template_list():
    return frappe.get_all("SubTask Template", fields=["name", "template_name"])


@frappe.whitelist()
def get_template_details(template_name):
    return frappe.get_all(
        "SubTask Template Detail",
        filters={"parent": template_name},
        fields=[
            "subtask_name_template",
            "value_template",
            "description_template",
            "target_time_template",
            "unit_target_time_template",
            "status_template",
            "type_template",
            "priority_template",
        ],
    )


@frappe.whitelist()
def create_subtask_from_template(tasks, values, count):
    print(
        f"create_subtask_from_template called with values: {values} and count: {count}"
    )
    # values = frappe._dict(values)
    if isinstance(values, str):
        values = json.loads(values)
    for i in range(int(count)):
        subtask = frappe.new_doc("SubTask")
        subtask.tasks = tasks
        subtask.subtask_name = values[f"subtask_name_template_{i}"]
        subtask.value = values[f"value_template_{i}"]
        subtask.description = values[f"description_template_{i}"]
        subtask.pic_subtask = values[f"pic_subtask_template_{i}"]
        subtask.target_time = values[f"target_time_template_{i}"]
        subtask.unit_target_time = values[f"unit_target_time_template_{i}"]
        subtask.status = values[f"status_template_{i}"]

        type_list = frappe.parse_json(values[f"subtask_type_{i}"])
        for type in type_list:
            if type.get("type"):
                subtask.append("type", {"subtask_type": type.get("type")})

        print(f"SubTask values: {subtask.as_dict()}")
        subtask.insert()


@frappe.whitelist()
def get_subtask(task_id: str):
    """Fetch SubTask linked to a Tasks doc with pagination."""
    if not task_id:
        frappe.throw("task_id is required")

    page = frappe.form_dict.get("page") or 1
    page_size = frappe.form_dict.get("page_size") or 50
    try:
        page = int(page)
        page_size = int(page_size)
    except ValueError:
        page = 1
        page_size = 50
    page = max(page, 1)
    page_size = max(1, min(page_size, 200))

    filters = {"tasks": task_id}

    fields = [
        "name",
        "tasks",
        "subtask_name",
        "description",
        "priority",
        "value",
        "pic_subtask_name",
        "target_time",
        "unit_target_time",
        "status",
        "created_by",
    ]

    total = frappe.db.count("SubTask", filters=filters)
    offset = (page - 1) * page_size
    rows = frappe.get_all(
        "SubTask",
        filters=filters,
        fields=fields,
        order_by="creation desc",
        limit=page_size,
        start=offset,
    )

    if rows:
        parent_names = [r["name"] for r in rows]
        type_entries = frappe.get_all(
            "SubTask Type",
            filters={"parent": ("in", parent_names)},
            fields=["parent", "subtask_type"],
        )
        type_map = {}
        for pe in type_entries:
            type_map.setdefault(pe["parent"], []).append(pe.get("subtask_type"))
        for r in rows:
            types = type_map.get(r["name"], [])
            r["type"] = ", ".join(types) if types else ""

    return {"rows": rows, "total": total, "page": page, "page_size": page_size}
