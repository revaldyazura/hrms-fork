import frappe
from typing import Optional
from hrms.integrations.telegram_bot import utils as telegram_utils


def _subtask_issue_label(subtask_doc) -> str:
    """Return best-effort issue label for a SubTask doc."""

    issues = getattr(subtask_doc, "issues_type", None) or []
    if not issues:
        return "-"

    first = issues[0]
    issue_docname = getattr(first, "issue", None)
    issue_key = None
    if issue_docname:
        try:
            issue_key = frappe.db.get_value("Fusion Issue Types", issue_docname, "issue")
        except Exception:
            issue_key = None

    if not issue_key:
        issue_key = getattr(first, "issue_name", None)

    label = telegram_utils.issue_label_from_key(str(issue_key or "").strip())
    return label or "-"



def _subtask_progress_comments(subtask_name: str, limit: int = 5) -> list[str]:
    """Return formatted progress update lines for a SubTask (oldest -> newest)."""

    rows = frappe.get_all(
        "Comment",
        filters={
            "reference_doctype": "SubTask",
            "reference_name": subtask_name,
            "comment_type": "Comment",
        },
        fields=["content", "comment_email", "comment_by", "creation"],
        order_by="creation asc",
        limit_page_length=int(limit or 5),
    )

    out: list[str] = []
    for r in rows or []:
        text = telegram_utils._strip_html_to_text(r.get("content") or "")
        if not text:
            continue
        out.append(f"- {text}")
    return out

def aduan_info_response(subtask_name: str, command_token: Optional[str] = None) -> str:
    """Build response message for /aduan_info <SubTask ID>.

    If `telegram_aduan_response_texts` provides a template for the command,
    this function will use it.

    Available placeholders:
    - {name}
    - {issue}
    - {status}
    - {pic_subtask_name}
    - {root_cause}
    - {modified}
    - {progress_updates}
    - {subtask_url}
    - {subtask_link}
    """

    name = (subtask_name or "").strip().upper()
    if not name:
        raise frappe.ValidationError("SubTask ID is required")

    # Ensure DB connection is alive (bot may be idle for hours).
    telegram_utils.ensure_db_connection()

    # TeleBot listener is a long-running process. Reset the current DB transaction
    # so reads don't get stuck on an old REPEATABLE READ snapshot.
    try:
        frappe.db.rollback()
    except Exception:
        pass

    doc = frappe.get_doc("SubTask", name)
    print(f"Fetched SubTask {name} for /aduan_info: {doc.as_dict() if doc else 'Not found'}")

    issue_label = _subtask_issue_label(doc)
    status_raw = doc.status if hasattr(doc, "status") else "-"
    status_out = status_raw.title() if status_raw != "-" else "-"

    pic_name = doc.pic_subtask_name if hasattr(doc, "pic_subtask_name") else None
    if not pic_name:
        pic = getattr(doc, "pic_subtask", None)
        if pic:
            try:
                pic_name = (frappe.db.get_value("Employee", pic, "employee_name") or "").strip()
            except Exception:
                pic_name = ""
    if not pic_name:
        pic_name = "-"

    root_cause = doc.root_cause if hasattr(doc, "root_cause") else "-"
    modified = doc.modified.strftime("%d-%m-%Y %H:%M") if hasattr(doc, "modified") and doc.modified else "-"

    progress_lines = _subtask_progress_comments(doc.name, limit=5)
    progress_updates = "\n".join(["  " + l for l in (progress_lines or ["- (belum ada update)"])])

    base = (frappe.conf.get("telegram_aduan_site") or "").strip()
    subtask_url = (base + doc.name) if base else doc.name
    subtask_link = telegram_utils._format_hyperlink(doc.name, subtask_url) if base else doc.name

    context = {
        "name": telegram_utils._escape_html(doc.name),
        "issue": telegram_utils._escape_html(issue_label),
        "status": telegram_utils._escape_html(status_out),
        "pic_subtask_name": telegram_utils._escape_html(pic_name),
        "root_cause": telegram_utils._escape_html(root_cause),
        "modified": telegram_utils._escape_html(modified),
        "progress_updates": telegram_utils._escape_html(progress_updates),
        "subtask_url": telegram_utils._escape_html(subtask_url),
        "subtask_link": subtask_link,
    }

    template = telegram_utils.response_template_for_command(command_token) if command_token else None
    if template:
        return telegram_utils._render_template(template, context).strip()

    # Fallback default (built-in)
    lines: list[str] = []
    lines.append("ℹ️ Progress Info")
    lines.append("")
    lines.append(f"• Nomor Aduan: {doc.name}")
    lines.append(f"• Issue Type: {issue_label}")
    lines.append(f"• Status          : {status_out}")
    lines.append(f"• PIC             : {pic_name}")
    lines.append(f"• Root Cause      : {root_cause}")
    lines.append("• Progress Update :")
    lines.extend(["  " + l for l in (progress_lines or ["- (belum ada update)"])])
    lines.append("")
    lines.append(f"🕒 Last Update: {modified}")
    return "\n".join(lines).strip()
