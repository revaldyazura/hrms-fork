
import re
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional

import frappe

from hrms.integrations.telegram_bot import utils as telegram_utils


DEFAULT_STATISTIC_COMMAND = "/aduan_statistic"


def is_statistic_command(command_token: str) -> bool:
	"""Return True if command token represents the statistic command.

	We treat commands whose menu name contains 'statistic' (e.g.
	'aduan_statistic', 'aduan_statistic_staging') as the statistic flow.
	"""

	name = telegram_utils.command_for_menu(command_token)
	return bool(name) and "statistic" in name


def _parse_maintask_id(payload: str) -> str:
	parts = (payload or "").strip().split()
	if not parts:
		raise frappe.ValidationError("Format belum lengkap")
	maintask_id = (parts[0] or "").strip().upper()
	if not maintask_id:
		raise frappe.ValidationError("MainTask ID tidak boleh kosong")
	if not re.match(r"^MT-\d{6}-\d{7}$", maintask_id):
		raise frappe.ValidationError("Format MainTask ID belum valid")
	return maintask_id


def _format_id_date(dt: datetime) -> str:
	# Example: Senin, 23 Februari 2026
	weekday_id = {
		0: "Senin",
		1: "Selasa",
		2: "Rabu",
		3: "Kamis",
		4: "Jumat",
		5: "Sabtu",
		6: "Minggu",
	}
	month_id = {
		1: "Januari",
		2: "Februari",
		3: "Maret",
		4: "April",
		5: "Mei",
		6: "Juni",
		7: "Juli",
		8: "Agustus",
		9: "September",
		10: "Oktober",
		11: "November",
		12: "Desember",
	}
	wd = weekday_id.get(int(dt.weekday()), "")
	mm = month_id.get(int(dt.month), "")
	return f"{wd}, {dt.day} {mm} {dt.year}".strip().strip(",")


def _previous_monday_window(now: datetime) -> tuple[datetime, datetime]:
	# Rule: start from the most recent Monday before/at `now` (start of current week).
	# Example: called on Tue 3 Mar 2026 -> start Mon 2 Mar 2026 00:00.
	start_of_this_week = (now - timedelta(days=now.weekday())).replace(
		hour=0, minute=0, second=0, microsecond=0
	)
	return start_of_this_week, now


def _status_counts_by_maintask(maintask_id: str) -> dict[str, int]:
	rows = frappe.db.sql(
		"""
		select ifnull(status, '') as status, count(*) as cnt
		from `tabSubTask`
		where maintask = %s
		group by status
		""",
		(maintask_id,),
		as_dict=True,
	)
	counts: dict[str, int] = {}
	for r in rows or []:
		k = (r.get("status") or "").strip() or "-"
		counts[k] = int(r.get("cnt") or 0)
	return counts


def _closed_count_in_window(maintask_id: str, start: datetime, end: datetime) -> int:
	# Prefer subtask_close_date; fallback to modified if close_date is NULL.
	row = frappe.db.sql(
		"""
		select count(*) as cnt
		from `tabSubTask`
		where maintask = %s
		  and status = 'Close'
		  and ifnull(subtask_close_date, modified) >= %s
		  and ifnull(subtask_close_date, modified) <= %s
		""",
		(maintask_id, start, end),
		as_dict=True,
	)
	try:
		return int((row or [{}])[0].get("cnt") or 0)
	except Exception:
		return 0


def _open_issue_counts_by_type(maintask_id: str) -> list[tuple[str, int]]:
	# Count issue rows on Open subtasks, including Open subtasks with no issue.
	rows = frappe.db.sql(
		"""
		select
			case
				when sti.name is null then ''
				else ifnull(fit.issue, sti.issue_name)
			end as issue_key,
			count(*) as cnt
		from `tabSubTask` st
		left join `tabSubTask Issues` sti on sti.parent = st.name
		left join `tabFusion Issue Types` fit on fit.name = sti.issue
		where st.maintask = %s
		  and st.status = 'Open'
		group by
			case
				when sti.name is null then ''
				else ifnull(fit.issue, sti.issue_name)
			end
		order by cnt desc
		""",
		(maintask_id,),
		as_dict=True,
	)

	agg: dict[str, int] = defaultdict(int)
	for r in rows or []:
		key = (r.get("issue_key") or "").strip()
		if not key:
			label = "Not Set"
			agg[label] += int(r.get("cnt") or 0)
			continue
		label = telegram_utils.issue_label_from_key(key) or key
		agg[label] += int(r.get("cnt") or 0)
	# stable-ish ordering: count desc then label asc
	out = sorted(agg.items(), key=lambda x: (-x[1], x[0].lower()))
	return [(k, int(v)) for k, v in out]


def aduan_statistic_response(payload: str, command_token: Optional[str] = None) -> str:
	"""Build response message for /aduan_statistic <MainTask ID>."""

	maintask_id = _parse_maintask_id(payload)

	telegram_utils.ensure_db_connection()
	try:
		frappe.db.rollback()
	except Exception:
		pass

	try:
		maintask_doc = frappe.get_doc("MainTask", maintask_id)
	except Exception:
		raise frappe.ValidationError("MainTask tidak ditemukan")

	maintask_title = (getattr(maintask_doc, "maintask_name", None) or "").strip()

	now = frappe.utils.now_datetime()
	start, end = _previous_monday_window(now)

	status_counts = _status_counts_by_maintask(maintask_id)
	closed_this_week = _closed_count_in_window(maintask_id, start, end)
	open_issues = _open_issue_counts_by_type(maintask_id)

	def _c(key: str) -> int:
		return int(status_counts.get(key, 0) or 0)

	open_issues_lines: list[str] = []
	if not open_issues:
		open_issues_lines.append("- (tidak ada)")
	else:
		for issue_label, cnt in open_issues:
			open_issues_lines.append(f"- {telegram_utils._escape_html(issue_label)} : {int(cnt)}")

	context = {
		"now": telegram_utils._escape_html(_format_id_date(now)),
		"maintask_id": telegram_utils._escape_html(maintask_id),
		"maintask_title": telegram_utils._escape_html(maintask_title),
		"open_count": _c("Open"),
		"in_progress_count": _c("In Progress"),
		"pause_count": _c("Pause"),
		"resolved_count": _c("Resolved"),
		"done_count": _c("Done"),
		"cancel_count": _c("Cancel"),
		"closed_count": _c("Close"),
		"closed_weekly_count": int(closed_this_week),
		"open_issues_by_type": "\n".join(open_issues_lines).strip(),
	}

	default = (
		"📊 TASK SUMMARY\n"
		"{now}\n\n"
		"MAIN TASK: {maintask_id} {maintask_title}\n\n"
		"Overview Status\n"
		"Open              : {open_count}\n"
		"In Progress       : {in_progress_count}\n"
		"Pause             : {pause_count}\n"
		"Resolved          : {resolved_count}\n"
		"Done              : {done_count}\n"
		"Cancel            : {cancel_count}\n"
		"Closed            : {closed_count}\n"
		"Closed (This Week): {closed_weekly_count}\n\n"
		"Open Issues by Type:\n"
		"{open_issues_by_type}"
	)

	return telegram_utils._render_response_text("aduan_statistic", default, context).strip()

