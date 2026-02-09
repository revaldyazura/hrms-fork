
import json

import frappe
from frappe import _


def _ensure_evaluator_access():
	"""Allow only Leader/Supervisor/Manager (or Administrator)."""
	user = frappe.session.user
	if user == "Administrator":
		return

	roles = set(frappe.get_roles(user) or [])
	allowed = {"Leader", "Supervisor", "Manager", "System Manager"}
	if not (roles & allowed):
		frappe.throw(
			_("You are not allowed to evaluate SubTasks."),
			frappe.PermissionError,
		)


def _get_current_employee_id(user: str) -> str | None:
	return frappe.db.get_value("Employee", {"user_id": user}, "name")


@frappe.whitelist()
def get_done_subtasks(txt: str | None = None, limit: int = 200):
	"""Return Done SubTasks eligible to be evaluated by current user.

	Eligibility:
	- SubTask.status == 'Done'
	- Current user has role in {Leader, Supervisor, Manager} (or Administrator)
	- Current user's Employee is listed in MainTask Assign By of the SubTask's MainTask
	- SubTask is not already evaluated (no Evaluation row for that subtask)
	"""
	_ensure_evaluator_access()

	user = frappe.session.user
	employee_id = _get_current_employee_id(user)
	if user != "Administrator" and not employee_id:
		return []

	# limit = min(int(limit or 200), 500)
	txt = (txt or "").strip()
	like_txt = f"%{txt}%" if txt else None

	params = {
		"employee_id": employee_id,
		"user_id": user,
		"limit": limit,
	}

	search_cond = ""
	if like_txt:
		params["txt"] = like_txt
		search_cond = " AND (st.name LIKE %(txt)s OR st.subtask_name LIKE %(txt)s)"
	
	joins = [
		"JOIN `tabMainTask` mt ON mt.name = st.maintask"
	]
 
	where_clauses = [
    "st.status = 'Done'",
    # "NOT EXISTS (SELECT 1 FROM `tabEvaluation` ev WHERE ev.subtask = st.name)"
	]
 
	# Admin can view all eligible Done subtasks (still excludes already evaluated)
	if user != "Administrator":
		joins.append("JOIN `tabMainTask Assign By` mab ON mab.parent = mt.name")
		where_clauses.append("(mab.employee = %(employee_id)s OR mt.owner = %(user_id)s)")

	rows = frappe.db.sql(
		f"""
		SELECT
			st.pic_subtask_name AS pic_subtask_name,
			st.name AS subtask,
			st.subtask_name AS subtask_title,
			st.tasks_name AS task_title,
			st.maintask_name AS maintask_title,
			st.value AS value,
			st.priority AS priority,
			st.target_time_minutes AS target_time_minutes,
			st.attachment AS attachment,
			st.submission_text AS submission_text,
			st.tasks AS tasks,
			st.maintask AS maintask
		FROM `tabSubTask` st
		{' '.join(joins)}
		WHERE
			{' AND '.join(where_clauses)}
			{search_cond}
		GROUP BY st.name
		ORDER BY st.creation DESC, st.name DESC
	""",
		params,
		as_dict=True,
	)

	return rows


@frappe.whitelist()
def bulk_create_evaluations(items):
	"""Create Evaluation docs for multiple subtasks.

	`items` can be a JSON string or list of dicts: [{subtask, performance}, ...]
	Returns: {success: [...], failure: [...]}.
	"""
	_ensure_evaluator_access()

	user = frappe.session.user
	employee_id = _get_current_employee_id(user)

	if isinstance(items, str):
		items = json.loads(items)

	if not isinstance(items, list) or not items:
		frappe.throw(_("No SubTasks selected."))

	success = []
	failure = []

	frappe.flags.bulk_evaluation_creation = True
	try:
		for row in items:
			subtask = (row or {}).get("subtask")
			performance = (row or {}).get("performance")
			try:
				if not subtask:
					raise frappe.ValidationError(_("Missing SubTask."))
 
				subtask_doc = frappe.get_doc("SubTask", subtask)
				subtask_title = subtask_doc.subtask_name
    
				performance = int(performance)
				if performance < 1 or performance > 120:
					raise frappe.ValidationError(_("Performance must be between 1 and 120."))

				# Prevent duplicate eval
				if frappe.db.exists("Evaluation", {"subtask": subtask}):
					raise frappe.ValidationError(
						_("Evaluation already exists for SubTask {0}.").format(subtask)
					)

				

				if subtask_doc.status != "Done":
					raise frappe.ValidationError(
						_("You cannot evaluate SubTask {0} because its status is not Done.").format(
							subtask
						)
					)

				# Authorization: user must be in assign_by of the maintask (admin bypass)
				if user != "Administrator":
					if not employee_id:
						raise frappe.PermissionError(_("Employee is not linked to this user."))

					in_assign_by = frappe.db.exists(
						"MainTask Assign By",
						{"parent": subtask_doc.maintask, "employee": employee_id},
					)
     
					is_maintask_owner = frappe.db.get_value(
						"MainTask", subtask_doc.maintask, "owner"
					) == user
					
					if not in_assign_by and not is_maintask_owner:
						raise frappe.PermissionError(
							_("You are not allowed to evaluate SubTask {0}.").format(subtask)
						)

				eval_doc = frappe.get_doc(
					{
						"doctype": "Evaluation",
						"subtask": subtask,
						"performance": performance,
					}
				)
				eval_doc.insert()
				success.append({"subtask": subtask, "evaluation": eval_doc.name, "subtask_title": subtask_title})
			except Exception as exc:
				failure.append({"subtask": subtask, "error": str(exc), "subtask_title": subtask_title})
	finally:
		frappe.flags.bulk_evaluation_creation = False

	return {"success": success, "failure": failure}

