from __future__ import annotations

from datetime import datetime
import tempfile
from typing import Optional, Any

import frappe
from hrms.integrations.telegram_bot.utils import helper

ADUAN_INFO_COMMAND = "/aduan_info"

def is_info_command(command_token: str) -> bool:
    """Return True if command token represents an info-style command.

    We treat commands whose menu name contains 'info' (e.g. 'aduan_info',
    'aduan_info_staging') as the info flow.
    """

    name = helper.command_for_menu(command_token)
    if not name:
        return False
    return "info" in name

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
    
    issue_label = helper.issue_label_from_key(str(issue_key or "").strip())
    if not issue_label:
        issue_label = helper.issue_label_maintask_mapping_from_key(str(issue_key or "").strip(), subtask_doc.maintask)
    return issue_label or "-"



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
        text = helper._strip_html_to_text(r.get("content") or "")
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
    helper.ensure_db_connection()

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
    subtask_link = helper._format_hyperlink(doc.name, subtask_url) if base else doc.name

    context = {
        "name": helper._escape_html(doc.name),
        "issue": helper._escape_html(issue_label),
        "status": helper._escape_html(status_out),
        "pic_subtask_name": helper._escape_html(pic_name),
        "root_cause": helper._escape_html(root_cause),
        "modified": helper._escape_html(modified),
        "progress_updates": helper._escape_html(progress_updates),
        "subtask_url": helper._escape_html(subtask_url),
        "subtask_link": subtask_link,
    }
    
    default = "ℹ️ Progress Info\n\n• Nomor Aduan: {subtask_link}\n• Issue Type: {issue}\n• Status          : {status}\n• PIC             : {pic_subtask_name}\n• Root Cause      : {root_cause}\n• Progress Update :\n{progress_updates}\n\n🕒 Last Update: {modified}"
    
    template = helper._render_response_text(
		"aduan_info",  # command_token may be None or not match a menu, so we use the base command as key for config lookup with a sensible default template.
		default,
		context
	)
    # template = helper.response_template_for_command(command_token) if command_token else None
    if template:
        return template.strip()
        # return helper._render_template(template, context).strip()

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


def _subtask_type_from_doc(doc: Any) -> str:
    types = getattr(doc, "type", None) or []
    if not types:
        return "-"
    first = types[0]
    val = getattr(first, "subtask_type", None) or getattr(first, "type", None)
    s = ("" if val in (None, "") else str(val)).strip()
    return s or "-"

def aduan_saya_response(message):
    """Return message text + optional .txt report path for /aduan_saya.

    `requestor` must match the value stored in SubTask.requestor.
    In our telegram flows this is typically `helper._telegram_user_label(message)`.

    Returns:
    - message_text_html: str (safe for parse_mode="HTML")
    - report_file_path: Optional[str] (full detail in .txt when message exceeds Telegram limits)
    """

    requestor = helper._telegram_user_label(message)

    if not requestor:
        raise frappe.ValidationError("Requestor is required")

    helper.ensure_db_connection()

    # TeleBot listener is a long-running process. Reset the current DB transaction
    # so reads don't get stuck on an old REPEATABLE READ snapshot.
    try:
        frappe.db.rollback()
    except Exception:
        pass

    # Keep it bounded; this is a chat response.
    # limit = 10

    rows = frappe.get_all(
        "SubTask",
        filters={
            "requestor": requestor,
            "status": ["not in", ["Close", "Done"]],
        },  # Only show non-closed tickets  # Only show non-closed/cancelled tickets
        fields=["name", "subtask_name", "priority", "modified", "status", "subtask_open_date"],
        order_by="modified desc",
        # limit_page_length=limit,
    )

    if not rows:
        empty_default = "Anda belum memiliki tiket aduan."
        msg = helper._render_response_text(
            "aduan_saya_empty",
            empty_default,
            {"requestor": helper._escape_html(requestor)},
        ).strip()
        return msg, None

    ticket_blocks_html: list[str] = []
    ticket_blocks_raw: list[str] = []

    for r in rows:
        name = (r.get("name") or "").strip()
        if not name:
            continue

        # Need child tables (type/issues_type), so load the doc.
        doc = frappe.get_doc("SubTask", name)

        subtask_name = (getattr(doc, "subtask_name", None) or "-").strip() or "-"
        subtask_type = _subtask_type_from_doc(doc)
        issue_label = _subtask_issue_label(doc)
        priority = (getattr(doc, "priority", None) or "-").strip() or "-"
        status = (getattr(doc, "status", None) or "-").strip() or "-"
        open_date = doc.subtask_open_date.strftime("%d-%m-%Y") if getattr(doc, "subtask_open_date", None) else "-"

        ticket_blocks_raw.append(
            "\n".join(
                [
                    f"{name}",
                    f"Subject : {subtask_name}",
                    f"Type  : {subtask_type}",
                    f"Issues   : {issue_label}",
                    f"Priority: {priority}",
                    f"Status  : {status}",
                    f"Open Date: {open_date}",
                ]
            ).rstrip()
        )

        ticket_blocks_html.append(
            "\n".join(
                [
                    helper._escape_html(name),
                    f"Subject : {helper._escape_html(subtask_name)}",
                    f"Type  : {helper._escape_html(subtask_type)}",
                    f"Issues   : {helper._escape_html(issue_label)}",
                    f"Priority: {helper._escape_html(priority)}",
                    f"Status  : {helper._escape_html(status)}",
                    f"Open Date: {helper._escape_html(open_date)}",
                ]
            ).rstrip()
        )

    sep = "━━━━━━━━━━━━━━━━"
    blocks_raw = f"\n{sep}\n".join([b for b in ticket_blocks_raw if b])
    blocks_html = f"\n{sep}\n".join([b for b in ticket_blocks_html if b])

    ctx = {
        "requestor": helper._escape_html(requestor),
        "ticket_count": str(len(ticket_blocks_html)),
        "ticket_blocks": blocks_html,
    }

    default = f"📋 TICKET LIST\n{sep}\n{{ticket_blocks}}"
    full_html = (helper._render_response_text("aduan_saya", default, ctx) or "").strip()
    full_raw = (f"📋 TICKET LIST\n{sep}\n" + blocks_raw).strip() + "\n"

    # Telegram message limit is ~4096 chars. Keep safe margin.
    max_len = 3800
    if len(full_html) <= max_len:
        return full_html, None

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=".txt",
        prefix=f"aduan_{requestor}_{ts}_",
        delete=False,
    ) as f:
        f.write(full_raw)
        report_path = f.name

    # Keep preview short to avoid breaking any HTML in configured templates.
    ids = [str((r.get("name") or "")).strip() for r in (rows or []) if str((r.get("name") or "")).strip()]
    shown = "\n".join([helper._escape_html(x) for x in ids[:10]]).strip()
    shown = shown + ("\n..." if len(ids) > 10 else "")
    preview_default = "📋 TICKET LIST terlalu panjang untuk ditampilkan di chat.\n\n{shown}\n\n📎 Detail lengkap dikirim sebagai file .txt"
    preview = helper._render_response_text(
        "aduan_saya_overflow",
        preview_default,
        {"shown": shown, "ticket_count": str(len(ids))},
    ).strip()
    return preview, report_path
    
    