import frappe
from hrms.integrations.telegram_bot.utils import helper
import html
from typing import Dict, Optional, Tuple
import re

ADUAN_COMMAND = "/aduan"

def _parse_aduan_fields(payload: str) -> Tuple[Dict[str, str], str]:
    """Parse a structured /aduan payload.

    Returns (fields, freeform).

    fields keys: type, priority, issue_type, subject, details, link_dashboard, link_maps, workspace
    """

    fields: Dict[str, str] = {}
    freeform_lines = []

    if not payload:
        return fields, ""

    for raw_line in payload.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        # Key: Value format
        m = re.match(
            r"^(Type|Priority|Issue Type|Issues|Subject|Details|Link Dashboard|Link Maps|Workspace)\s*:\s*(.+)$",
            line,
            flags=re.IGNORECASE,
        )
        if not m:
            freeform_lines.append(line)
            continue

        key = m.group(1).strip().lower()
        value = helper._clean_field_value(m.group(2))

        if key in ("issue type", "issues"):
            # User input matches mapping label (e.g. "Menu"); database expects key (e.g. "APPS/MENU").
            # Keep the original label here; we will map it later.
            fields["issue_type"] = value
        elif key == "link dashboard":
            fields["link_dashboard"] = value
        elif key == "link maps":
            fields["link_maps"] = value
        else:
            fields[key] = value

    return fields, "\n".join(freeform_lines).strip()


def _missing_required_fields(fields: Dict[str, str]) -> list[str]:
    missing = []
    if not (fields.get("type") or "").strip():
        missing.append("Type")
    if not (fields.get("issue_type") or "").strip():
        missing.append("Issues")
    if not (fields.get("subject") or "").strip():
        missing.append("Subject")
    if not (fields.get("details") or "").strip():
        missing.append("Details")
    return missing


def _insert_with_owner(doc, owner_user: str):
    """Insert doc so that `owner` becomes `owner_user`.

    Note: Frappe core sets `owner = frappe.session.user` for new docs in
    `Document.set_user_and_timestamp()`, overriding any provided owner value.
    """

    previous_user = frappe.session.user
    try:
        if owner_user and owner_user != previous_user:
            if frappe.db.exists("User", owner_user):
                frappe.set_user(owner_user)
            else:
                helper._logger().warning(
                    f"Owner user not found: {owner_user}. Falling back to {previous_user}."
                )

        doc.insert(ignore_permissions=True)
    finally:
        if frappe.session.user != previous_user:
            frappe.set_user(previous_user)


def _create_subtask_from_aduan(fields: Dict[str, str], message) -> str:
    settings = helper._conf_default_subtask_settings(message)

    maintask = settings["maintask"]
    tasks = settings["tasks"]
    owner = settings["owner"]
    pic_subtask = settings["pic_subtask"]

    subtask_name = (fields.get("subject") or "").strip()
    if not subtask_name:
        raise frappe.ValidationError("Subject is required")

    priority = helper._normalize_priority(fields.get("priority"))
    chat_id = helper._coerce_int(getattr(getattr(message, "chat", None), "id", None))
    thread_id = helper._coerce_int(getattr(message, "message_thread_id", None))
 
    mapping_row = helper._maintask_mapping_row_for_message(chat_id, thread_id)

    description = helper._build_description(fields, "", message)

    doc = frappe.get_doc(
        {
            "doctype": "SubTask",
            "maintask": maintask,
            "tasks": tasks,
            "subtask_name": subtask_name,
            "description": description,
            "requestor": helper._telegram_user_label(message),
            "created_by": helper._telegram_user_label(message),
            "priority": priority,
            "status": "Open",
            "pic_subtask": pic_subtask,
            "target_time": int(settings["target_time"]),
            "unit_target_time": settings["unit_target_time"],
            "value": str(settings["value"]),
            # `owner` is set by Frappe based on frappe.session.user during insert.
            # We still pass it for clarity, but actual owner is enforced in _insert_with_owner().
            "owner": owner,
        }
    )

    # Child tables
    if fields.get("type"):
        type_name = helper._resolve_subtask_type(fields["type"])
        doc.append("type", {"subtask_type": type_name})

    if fields.get("issue_type"):
        if mapping_row:
            issue_name, issue_label, pics = helper._resolve_issue_type_from_maintask_mapping(
                fields.get("issue_type") or "",
                mapping_row,
                maintask,
                settings.get("maintask_name") or "",
            )
        else:
            issue_name, issue_label = helper._resolve_issue_type(
                fields["issue_type"], maintask, settings["maintask_name"]
            )
        doc.append("issues_type", {"issue": issue_name})

    _insert_with_owner(doc, owner)
    frappe.db.commit()
    return doc.name


def aduan_success_response(command_token: str, fields: Dict[str, str], message) -> str:
    """Build success response for /aduan-style commands.

    Placeholders:
    - {subtask_id}
    - {subtask_url}
    - {subtask_link}
    - {pic_issue}
    - {cmd}
    """

    cmd = helper.normalize_command_token(command_token, default="/aduan")
    subtask_id = _create_subtask_from_aduan(fields, message)
    base = (
        frappe.conf.get("telegram_aduan_site") or "hris.ebdesk.com/app/subtask/"
    ).strip()
    subtask_url = (base + subtask_id) if base else subtask_id
    subtask_link = helper._format_hyperlink(subtask_id, subtask_url) if base else subtask_id

    pic_issue = "@justrenatta"
    if fields.get("issue_type"):
        pics = helper._pics_for_issue_user_input(fields["issue_type"])
        if pics:
            pic_issue = ", ".join(pics)

    context = {
        "cmd": helper._escape_html(cmd),
        "subtask_id": helper._escape_html(subtask_id),
        "subtask_url": helper._escape_html(subtask_url),
        "subtask_link": subtask_link,
        "pic_issue": helper._escape_html(pic_issue or ""),
    }
    default = "✅ Aduan dicatat dengan nomor: {subtask_url}\ndan dalam proses pengecekan, dibantu oleh tim kami:\n{pic_issue}\nSilakan tunggu update lebih lanjut dari tim kami"

    template = helper._render_response_text("aduan", default, context)
    # template = helper.response_template_for_command(cmd)
    if template:
        return template.strip()
        # return helper._render_template(template, context).strip()

    return (
        f"✅ Aduan telah dicatat dengan nomor {subtask_url} dan dalam proses pengecekan, "
        f"dibantu oleh tim kami {pic_issue} Silakan tunggu update lebih lanjut dari tim kami"
    ).strip()
