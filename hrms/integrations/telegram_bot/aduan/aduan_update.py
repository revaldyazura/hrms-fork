
import re
from typing import Optional, Tuple

import frappe

from hrms.integrations.telegram_bot import utils as telegram_utils


DEFAULT_UPDATE_STATUS_COMMAND = "/aduan_update_status"
DEFAULT_UPDATE_ISSUES_COMMAND = "/aduan_update_issues"


def _command_is_update_status(command_token: str) -> bool:
	name = telegram_utils.command_for_menu(command_token)
	return bool(name) and "update_status" in name


def _command_is_update_issues(command_token: str) -> bool:
	name = telegram_utils.command_for_menu(command_token)
	return bool(name) and "update_issues" in name


def _parse_update_issues_payload(payload: str) -> Tuple[str, str]:
	"""Parse: <ST-ID> <issues label...>"""

	parts = (payload or "").strip().split()
	if len(parts) < 2:
		raise frappe.ValidationError("Format belum lengkap")

	subtask_id = (parts[0] or "").strip().upper()
	issues_label = " ".join([p for p in parts[1:] if p is not None]).strip()
	if not subtask_id:
		raise frappe.ValidationError("SubTask ID tidak boleh kosong")
	if not re.match(r"^ST-\d{6}-\d{7}$", subtask_id):
		raise frappe.ValidationError("Format SubTask ID belum valid")
	if not issues_label:
		raise frappe.ValidationError("Issue Type tidak boleh kosong")
	return subtask_id, issues_label


def _parse_update_status_payload(payload: str) -> Tuple[str, str]:
	"""Parse: <ST-ID> <status> [free text...]"""

	parts = (payload or "").strip().split()
	if len(parts) < 2:
		raise frappe.ValidationError("Format belum lengkap")

	subtask_id = (parts[0] or "").strip().upper()
	status_raw = (parts[1] or "").strip()
	if not subtask_id:
		raise frappe.ValidationError("SubTask ID is required")
	if not re.match(r"^ST-\d{6}-\d{7}$", subtask_id):
		raise frappe.ValidationError("Format SubTask ID belum valid")
	if not status_raw:
		raise frappe.ValidationError("Status is required")
	return subtask_id, status_raw


def _normalize_allowed_status(status_raw: str) -> str:
	s = (status_raw or "").strip().lower()
	if s not in ("resolved", "done"):
		raise frappe.ValidationError("Hanya boleh update status ke 'resolved'/'done'")
	return s.title()


def _normalize_doc_status(value: object) -> str:
	"""Normalize status labels to canonical title case used by the DocType."""
	s = ("" if value in (None, "") else str(value)).strip()
	if not s:
		return "-"
	key = re.sub(r"\s+", " ", s).strip().lower()
	mapping = {
		"open": "Open",
		"in progress": "In Progress",
		"pause": "Pause",
		"resolved": "Resolved",
		"done": "Done",
		"close": "Close",
		"cancel": "Cancel",
	}
	return mapping.get(key, s.title())


def _transition_subtask_status_error_message(before_status: str, after_status: str, required_before: str) -> str:
	before_txt = telegram_utils._escape_html(before_status)
	after_txt = telegram_utils._escape_html(after_status)
	req_txt = telegram_utils._escape_html(required_before)
	default = (
		"❌ Status {before_status} tidak bisa diupdate ke status {after_status}, "
		"lakukan perubahan status {before_status} ke status {required_before} untuk mengupdate ke {after_status}"
	)
	return telegram_utils._render_response_text(
		"transition_error",
		default,
		{
			"before_status": before_txt,
			"after_status": after_txt,
			"required_before": req_txt,
		},
	)


def _validate_transition(before_status: str, after_status: str) -> Optional[str]:
	"""Return error message if transition is not allowed, else None.

	Allowed:
	- In Progress -> Resolved
	- Resolved -> Done
	"""
	before_norm = _normalize_doc_status(before_status)
	after_norm = _normalize_doc_status(after_status)

	allowed = {
		("In Progress", "Resolved"),
		("Resolved", "Done"),
	}
	if (before_norm, after_norm) in allowed:
		return None

	# Explain required intermediate state based on desired target.
	required_before = "In Progress" if after_norm == "Resolved" else "Resolved"
	return _transition_subtask_status_error_message(before_norm, after_norm, required_before)


def _sender_username(message) -> Optional[str]:
	user = getattr(message, "from_user", None)
	username = getattr(user, "username", None) if user else None
	if username in (None, ""):
		return None
	return str(username).strip().lstrip("@").lower() or None


def _requestor_username_from_doc(doc) -> Optional[str]:
	req = (getattr(doc, "requestor", None) or "").strip()
	if not req:
		return None
	# requestor stored by bot is typically '@username'
	return req.lstrip("@").strip().lower() or None


def _is_sender_task_pic(sender_username: str, task_id: str) -> bool:
	if not sender_username or not task_id:
		return False

	employee_ids = frappe.get_all("Task PIC", filters={"parent": task_id}, pluck="employee")
	employee_ids = [e for e in (employee_ids or []) if e]
	if not employee_ids:
		return False

	# Employee.user_telegram is the Telegram username (usually without '@')
	rows = frappe.get_all(
		"Employee",
		filters={"name": ["in", employee_ids]},
		fields=["name", "user_telegram"],
		limit_page_length=1000,
	)

	for r in rows or []:
		ut = (r.get("user_telegram") or "").strip().lstrip("@").lower()
		if ut and ut == sender_username:
			return True

	return False


def _expected_subtask_scope_settings(message) -> dict:
	return telegram_utils._conf_default_subtask_settings(message)


def _scope_subtask_update_error_message(settings: dict) -> str:
	expected_maintask = (settings.get("maintask") or "").strip()
	expected_tasks = (settings.get("tasks") or "").strip()

	maintask_name = (settings.get("maintask_name") or "").strip()
	if not maintask_name and expected_maintask:
		try:
			maintask_name = (frappe.db.get_value("MainTask", expected_maintask, "maintask_name") or "").strip()
		except Exception:
			maintask_name = ""

	tasks_name = ""
	if expected_tasks:
		try:
			tasks_name = (frappe.db.get_value("Tasks", expected_tasks, "task_name") or "").strip()
		except Exception:
			tasks_name = ""

	maintask_label = maintask_name or expected_maintask or "maintask tidak terkonfigurasi"
	tasks_label = tasks_name or expected_tasks or "task tidak terkonfigurasi"
	default = (
		"❌ Subtask bukan bagian dari maintask <b>{maintask_label}</b> dan task <b>{tasks_label}</b> yang ditentukan"
	)
	return telegram_utils._render_response_text(
		"scope_error",
		default,
		{
			"maintask_label": telegram_utils._escape_html(maintask_label),
			"tasks_label": telegram_utils._escape_html(tasks_label),
		},
	)


def _permission_update_subtask_error_message() -> str:
	return telegram_utils._render_response_text(
		"permission_denied",
		"❌ Anda tidak dapat update subtask ini karena anda bukan sebagai pic task / requestor",
	)

def _sender_error_message() -> str:
	return telegram_utils._render_response_text("sender_username_missing", "❌ Username Telegram tidak ditemukan")

def _status_update_subtask_error_message() -> str:
	return telegram_utils._render_response_text(
		"invalid_status",
		"❌ Hanya boleh update status ke <b>resolved</b> / <b>done</b>",
	)


def _issues_update_subtask_error_message(e) -> str:
	default = "❌ Issue Type {error}."
	return telegram_utils._render_response_text(
		"invalid_issue_type",
		default,
		{"error": e},
	)


def _format_user_mention(value: str) -> str:
	s = (value or "").strip()
	if not s:
		return "-"
	# If looks like a username without '@', prefix it.
	if "@" not in s and re.match(r"^[A-Za-z0-9_]{3,32}$", s):
		return "@" + s
	return s


def _subtask_link(subtask_id: str) -> Tuple[str, str]:
	base = (frappe.conf.get("telegram_aduan_site") or "").strip()
	url = (base + subtask_id) if base else subtask_id
	link = telegram_utils._format_hyperlink(subtask_id, url) if base else subtask_id
	return link, url


def aduan_update_status_response(payload: str, message, command_token: str) -> str:
	"""Handle /aduan_update_status <ST-ID> <resolved|done> ..."""

	# Ensure DB connection is alive (bot may be idle for hours).
	telegram_utils.ensure_db_connection()

	subtask_id, status_raw = _parse_update_status_payload(payload)

	try:
		frappe.db.rollback()
	except Exception:
		pass

	doc = frappe.get_doc("SubTask", subtask_id)

	# 1) Validate scope: subtask must belong to expected maintask+tasks for this thread.
	settings = _expected_subtask_scope_settings(message)
	expected_maintask = (settings.get("maintask") or "").strip()
	expected_tasks = (settings.get("tasks") or "").strip()
	if expected_maintask and getattr(doc, "maintask", None) != expected_maintask:
		return _scope_subtask_update_error_message(settings)
	if expected_tasks and getattr(doc, "tasks", None) != expected_tasks:
		return _scope_subtask_update_error_message(settings)

	# 2) Validate sender permission: must be task PIC or requestor.
	sender = _sender_username(message)
	if not sender:
		return _sender_error_message()

	req_user = _requestor_username_from_doc(doc)
	is_requestor = bool(req_user and req_user == sender)
	is_task_pic = _is_sender_task_pic(sender, getattr(doc, "tasks", ""))
	if not (is_requestor or is_task_pic):
		return _permission_update_subtask_error_message()

	# 3) Validate allowed status.
	try:
		new_status = _normalize_allowed_status(status_raw)
	except Exception:
		return _status_update_subtask_error_message()

	# 4) Validate transition rule.
	current_status = _normalize_doc_status(getattr(doc, "status", None))
	err = _validate_transition(current_status, new_status)
	if err:
		return err

	# 5) Switch Frappe user to PIC SubTask user_id for audit trail.
	pic_emp = getattr(doc, "pic_subtask", None)
	pic_user_id = None
	if pic_emp:
		try:
			pic_user_id = frappe.db.get_value("Employee", pic_emp, "user_id")
		except Exception:
			pic_user_id = None

	if pic_user_id in (None, ""):
		return telegram_utils._render_response_text(
			"pic_user_id_missing_for_status",
			"❌ PIC SubTask belum memiliki user_id, tidak bisa melakukan update status",
		)
	if not frappe.db.exists("User", pic_user_id):
		return telegram_utils._render_response_text(
			"pic_user_not_found_for_status",
			"❌ User PIC SubTask tidak ditemukan di system, tidak bisa melakukan update status",
		)

	# Update status via save() so timestamps/validation logic run.
	previous_user = getattr(frappe.session, "user", None)
	try:
		frappe.set_user(pic_user_id)
		doc.status = new_status
		doc.save(ignore_permissions=True)
		frappe.db.commit()
	finally:
		try:
			if previous_user and getattr(frappe.session, "user", None) != previous_user:
				frappe.set_user(previous_user)
		except Exception:
			pass

	# Build response.
	link, _url = _subtask_link(doc.name)
	requestor = _format_user_mention(getattr(doc, "requestor", "") or "")
	pic_name = (getattr(doc, "pic_subtask_name", None) or "").strip()
	if not pic_name:
		pic = getattr(doc, "pic_subtask", None)
		if pic:
			try:
				pic_name = (frappe.db.get_value("Employee", pic, "employee_name") or "").strip()
			except Exception:
				pic_name = ""
	pic_name = pic_name or "-"

	if new_status == "Resolved":
		default = (
			"🟡 Issue {link} telah berstatus resolved. "
			"Mohon {requestor} dapat melakukan pengecekan dan konfirmasi kembali ke {pic_name}"
		)
		return telegram_utils._render_response_text(
			"aduan_update_status_to_resolved",
			default,
			{
				"link": link,
				"requestor": telegram_utils._escape_html(requestor),
				"pic_name": telegram_utils._escape_html(pic_name),
			},
		).strip()

	# Done
	default = "🟢 Issue {link} {requestor} sudah selesai ditangani (Done) oleh {pic_name}"
	return telegram_utils._render_response_text(
		"aduan_update_status_to_done",
		default,
		{
			"link": link,
			"requestor": telegram_utils._escape_html(requestor),
			"pic_name": telegram_utils._escape_html(pic_name),
		},
	).strip()


def aduan_update_issues_response(payload: str, message, command_token: str) -> str:
	"""Handle /aduan_update_issues <ST-ID> <issues label...>"""

	telegram_utils.ensure_db_connection()

	subtask_id, issues_input = _parse_update_issues_payload(payload)

	try:
		frappe.db.rollback()
	except Exception:
		pass

	doc = frappe.get_doc("SubTask", subtask_id)

	# 1) Validate scope: subtask must belong to expected maintask+tasks for this thread.
	settings = _expected_subtask_scope_settings(message)
	expected_maintask = (settings.get("maintask") or "").strip()
	expected_tasks = (settings.get("tasks") or "").strip()
	if expected_maintask and getattr(doc, "maintask", None) != expected_maintask:
		return _scope_subtask_update_error_message(settings)
	if expected_tasks and getattr(doc, "tasks", None) != expected_tasks:
		return _scope_subtask_update_error_message(settings)

	# 2) Validate sender permission: must be task PIC or requestor.
	sender = _sender_username(message)
	if not sender:
		return _sender_error_message()

	req_user = _requestor_username_from_doc(doc)
	is_requestor = bool(req_user and req_user == sender)
	is_task_pic = _is_sender_task_pic(sender, getattr(doc, "tasks", ""))
	if not (is_requestor or is_task_pic):
		return _permission_update_subtask_error_message()

	# 3) Validate issues label against mapping + resolve Fusion Issue Types docname.
	maintask = (getattr(doc, "maintask", None) or "").strip()
	maintask_name = (settings.get("maintask_name") or "").strip()
	if not maintask_name and maintask:
		try:
			maintask_name = (frappe.db.get_value("MainTask", maintask, "maintask_name") or "").strip()
		except Exception:
			maintask_name = ""

	try:
		issue_docname, issue_label = telegram_utils._resolve_issue_type(issues_input, maintask, maintask_name)
	except Exception as e:
		return _issues_update_subtask_error_message(e)

	# 4) Switch Frappe user to PIC SubTask user_id for audit trail.
	pic_emp = getattr(doc, "pic_subtask", None)
	pic_user_id = None
	if pic_emp:
		try:
			pic_user_id = frappe.db.get_value("Employee", pic_emp, "user_id")
		except Exception:
			pic_user_id = None

	if pic_user_id in (None, ""):
		return telegram_utils._render_response_text(
			"pic_user_id_missing_for_issue_type",
			"❌ PIC SubTask belum memiliki user_id, tidak bisa melakukan update issue type",
		)
	if not frappe.db.exists("User", pic_user_id):
		return telegram_utils._render_response_text(
			"pic_user_not_found_for_issue_type",
			"❌ User PIC SubTask tidak ditemukan di system, tidak bisa melakukan update issue type",
		)

	previous_user = getattr(frappe.session, "user", None)
	try:
		frappe.set_user(pic_user_id)
		# Keep a single issue_type row (overwrite existing).
		try:
			doc.set("issues_type", [])
		except Exception:
			setattr(doc, "issues_type", [])
		doc.append("issues_type", {"issue": issue_docname})
		doc.save(ignore_permissions=True)
		frappe.db.commit()
	finally:
		try:
			if previous_user and getattr(frappe.session, "user", None) != previous_user:
				frappe.set_user(previous_user)
		except Exception:
			pass

	link, _url = _subtask_link(doc.name)
 
	pic_issue = "@justrenatta"
	if issues_input:
		pics = telegram_utils._pics_for_issue_user_input(issues_input)
		if pics:
			pic_issue = ", ".join(pics)
   
	default = "✏️ Issue type {link} telah diupdate menjadi {issue_label}."
	return telegram_utils._render_response_text(
		"aduan_update_issue",
		default,
		{
			"link": link,
			"issue_label": telegram_utils._escape_html(issue_label),
   			"pic_issue": telegram_utils._escape_html(pic_issue or ""),
		},
	).strip()

