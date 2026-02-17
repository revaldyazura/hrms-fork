import re
from typing import Dict, Optional, Tuple

import frappe
import json

ADUAN_COMMAND = "/aduan"


def _logger():
    return frappe.logger("telegram")


def _conf_int(key: str) -> Optional[int]:
    value = frappe.conf.get(key)
    if value is None or value == "":
        return None
    try:
        return int(value)
    except Exception:
        return None


def _conf_str(key: str, default: str) -> str:
    value = frappe.conf.get(key)
    return value if value not in (None, "") else default

def _load_json(filename: str) -> Dict[str, str]:
    path = frappe.get_app_path(
        "hrms", "integrations", "telegram_bot", "aduan", filename
    )
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _clean_field_value(value: str) -> str:
    """Normalize user-provided values.

    Intentionally removes trailing punctuation like commas from list-style inputs:
    - "Bug," -> "Bug"
    - "menu," -> "menu"
    But preserves punctuation inside the text.
    """
    if value is None:
        return ""
    value = str(value).strip()
    # remove trailing commas/spaces
    value = re.sub(r"[\s,]+$", "", value)
    return value.strip()


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
                _logger().warning(f"Owner user not found: {owner_user}. Falling back to {previous_user}.")

        doc.insert(ignore_permissions=True)
    finally:
        if frappe.session.user != previous_user:
            frappe.set_user(previous_user)

def _conf_default_settings() -> Dict[str, str]:
    return {
        "maintask": _conf_str("telegram_aduan_default_maintask", "MT-202511-0000073"),
        "tasks": _conf_str("telegram_aduan_default_tasks", "T-202511-0000413"),
        "owner": _conf_str("telegram_aduan_default_owner", "renata@stellardata.ai"),
        "pic_subtask": _conf_str("telegram_aduan_default_pic_subtask", "HR-EMP-00413"),
        "target_time": str(frappe.conf.get("telegram_aduan_default_target_time") or 1),
        "unit_target_time": _conf_str("telegram_aduan_default_unit_target_time", "Hours"),
        "value": str(frappe.conf.get("telegram_aduan_default_value") or 1),
    }


def _is_allowed_group_topic(message) -> bool:
    allowed_chat_id = _conf_int("telegram_aduan_chat_id")
    allowed_topic_id = _conf_int("telegram_aduan_topic_id")

    if allowed_chat_id is None:
        return False

    chat_id = getattr(getattr(message, "chat", None), "id", None)
    if chat_id != allowed_chat_id:
        return False

    # If topic ID is configured, enforce it (Telegram forum topics)
    if allowed_topic_id is not None:
        thread_id = getattr(message, "message_thread_id", None)
        if thread_id != allowed_topic_id:
            return False

    return True


def _extract_command_payload(text: str) -> Optional[str]:
    if not text:
        return None
    print('raw text', text)
    text = text.strip()

    # Accept variants: /aduan, /aduan@BotName
    m = re.match(r"^/aduan(?:@\w+)?\b\s*(.*)$", text, flags=re.IGNORECASE | re.DOTALL)
    if not m:
        return None
    return (m.group(1) or "").strip()


def _find_aduan_command_offset(text: str) -> Optional[int]:
    """Return index where /aduan token starts, or None if not present.

    Used to detect users putting the command after other text.
    """
    if not text:
        print('no text')
        return None
    m = re.search(r"(^|\s)/aduan(?:@\w+)?\b", text, flags=re.IGNORECASE)
    if not m:
        return None
    # if matched with leading whitespace, command starts at group(0) end minus len(token)
    return m.start(0) + (1 if m.group(1) else 0)


def _format_help() -> str:
    return (
        "Format /aduan harus diawali dengan command, contoh:\n\n"
        "/aduan\n"
        "Type: Bug\n"
        "Priority: High (opsional, default 'medium')\n"
        "Issues: Maps\n"
        "Subject: Judul singkat\n"
        "Details: Jelaskan detailnya\n"
        "Link Dashboard: https://... (opsional)\n"
        "Link Maps: https://... (opsional)\n"
        "Workspace: ... (opsional)\n"
    )


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
        value = _clean_field_value(m.group(2))

        if key in ("issue type", "issues"):
            fields["issue_type"] = value.title()  # Normalize to title case for matching
        elif key == "link dashboard":
            fields["link_dashboard"] = value
        elif key == "link maps":
            fields["link_maps"] = value
        else:
            fields[key] = value

    return fields, "\n".join(freeform_lines).strip()


def _telegram_user_label(message) -> str:
    user = getattr(message, "from_user", None)
    if not user:
        return "unknown"

    username = getattr(user, "username", None)
    if username:
        return f"@{username}"

    first = (getattr(user, "first_name", "") or "").strip()
    last = (getattr(user, "last_name", "") or "").strip()
    name = (first + " " + last).strip()
    return name or str(getattr(user, "id", "unknown"))


def _build_message_link(message) -> Optional[str]:
    chat = getattr(message, "chat", None)
    if not chat:
        return None

    message_id = getattr(message, "message_id", None)
    if not message_id:
        return None

    chat_username = getattr(chat, "username", None)
    if chat_username:
        return f"https://t.me/{chat_username}/{message_id}"

    # For private supergroups (no username), use /c/<internal_id>/<message_id>
    chat_id = getattr(chat, "id", None)
    if not isinstance(chat_id, int):
        return None

    # Supergroup IDs are typically -100xxxxxxxxxx
    if str(chat_id).startswith("-100"):
        internal_id = str(chat_id)[4:]
        if internal_id.isdigit():
            return f"https://t.me/c/{internal_id}/{message_id}"

    return None


def _send(bot, chat_id: int, text: str, thread_id: Optional[int] = None, reply_to: Optional[int] = None):
    kwargs = {}
    if thread_id is not None:
        kwargs["message_thread_id"] = thread_id
    if reply_to is not None:
        kwargs["reply_to_message_id"] = reply_to
    return bot.send_message(chat_id, text, **kwargs)


def _resolve_subtask_type(type_label: str) -> str:
    """Return docname of SubTask Types."""
    type_label = (type_label or "").strip()
    if not type_label:
        raise frappe.ValidationError("Type is required")

    # SubTask Types autoname=field:type, so name typically equals type
    name = frappe.db.get_value("SubTask Types", {"type": type_label}, "name")
    if not name:
        raise frappe.DoesNotExistError(f"SubTask Types not found for type='{type_label}'")
    return name


def _resolve_issue_type(issue_label: str, maintask: str) -> str:
    """Return docname of Fusion Issue Types."""
    issue_label = (issue_label or "").strip()
    if not issue_label:
        raise frappe.ValidationError("Issue Type is required")

    filters = {"issue": issue_label}
    # If maintask is provided, narrow down to avoid ambiguity
    if maintask:
        filters["maintask"] = maintask

    name = frappe.db.get_value("Fusion Issue Types", filters, "name")
    if not name:
        raise frappe.DoesNotExistError(
            f"Fusion Issue Types not found for issue='{issue_label}'" + (f" and maintask='{maintask}'" if maintask else "")
        )
    return name


def _normalize_priority(priority: Optional[str]) -> str:
    if not priority:
        return "Medium"

    p = priority.strip().lower()
    mapping = {
        "low": "Low",
        "medium": "Medium",
        "med": "Medium",
        "high": "High",
        "urgent": "Urgent",
    }
    return mapping.get(p, "Medium")


def _build_description(fields: Dict[str, str], freeform: str, message) -> str:
    parts = []

    requestor = _telegram_user_label(message)
    parts.append("[Aduan]")
    parts.append(f"Requestor: {requestor}")

    msg_link = _build_message_link(message)
    if msg_link:
        parts.append(f"Chat: {msg_link}")

    thread_id = getattr(message, "message_thread_id", None)
    # if thread_id is not None:
    #     parts.append(f"Topic ID: {thread_id}")

    parts.append("---")

    details = fields.get("details")
    if details:
        # parts.append("Details:")
        parts.append(details)

    # Additional lines (links/workspace) go into description too
    if fields.get("link_dashboard"):
        parts.append(f"Link Dashboard: {fields['link_dashboard']}")
    if fields.get("link_maps"):
        parts.append(f"Link Maps: {fields['link_maps']}")
    if fields.get("workspace"):
        parts.append(f"Workspace: {fields['workspace']}")

    if freeform:
        parts.append("---")
        parts.append(freeform)

    return "\n".join([p for p in parts if p is not None and str(p).strip() != ""]).strip()


def _create_subtask_from_aduan(fields: Dict[str, str], message) -> str:
    settings = _conf_default_settings()

    maintask = settings["maintask"]
    tasks = settings["tasks"]
    owner = settings["owner"]
    pic_subtask = settings["pic_subtask"]

    subtask_name = (fields.get("subject") or "").strip()
    if not subtask_name:
        raise frappe.ValidationError("Subject is required")

    priority = _normalize_priority(fields.get("priority"))

    description = _build_description(fields, "", message)

    doc = frappe.get_doc(
        {
            "doctype": "SubTask",
            "maintask": maintask,
            "tasks": tasks,
            "subtask_name": subtask_name,
            "description": description,
            "requestor": _telegram_user_label(message),
            "created_by": _telegram_user_label(message),
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
        type_name = _resolve_subtask_type(fields["type"])
        doc.append("type", {"subtask_type": type_name})

    if fields.get("issue_type"):
        issue_name = _resolve_issue_type(fields["issue_type"], maintask)
        doc.append("issues_type", {"issue": issue_name})

    _insert_with_owner(doc, owner)
    frappe.db.commit()
    return doc.name


def register_handlers(bot):
    """Register /aduan handler for a specific group+topic.

    Configuration in site_config (frappe.conf):
    - telegram_aduan_chat_id: int (required)
    - telegram_aduan_topic_id: int (optional)

    Defaults (optional overrides):
    - telegram_aduan_default_maintask
    - telegram_aduan_default_tasks
    - telegram_aduan_default_owner
    - telegram_aduan_default_pic_subtask
    - telegram_aduan_default_target_time
    - telegram_aduan_default_unit_target_time
    - telegram_aduan_default_value
    """

    @bot.message_handler(func=lambda m: _find_aduan_command_offset(getattr(m, "text", "") or "") is not None)
    def handle_aduan(message):
        if not _is_allowed_group_topic(message):
            return

        chat_id = message.chat.id
        thread_id = getattr(message, "message_thread_id", None)
        raw_text = (message.text or "").strip()
        print('received message', raw_text)
        offset = _find_aduan_command_offset(raw_text)

        # Telegram best-practice: command should be at start of message.
        if offset is not None and offset > 0:
            _send(
                bot,
                chat_id,
                "❌ Command /aduan harus ditulis di awal pesan.\n\n" + _format_help(),
                thread_id=thread_id,
                reply_to=message.message_id,
            )
            return

        payload = _extract_command_payload(raw_text)

        fields, freeform = _parse_aduan_fields(payload or "")

        pic_issue = "@justrenatta"
        if fields.get("issue_type"):
            issue_type_key = (fields["issue_type"] or "").strip().title()
            mapping_raw = _load_json("mapping_pic_issue.json")
            mapping = {str(k).strip(): v for k, v in (mapping_raw or {}).items()}
            pic_issue = mapping.get(issue_type_key, "@justrenatta")
            if isinstance(pic_issue, list):
                pic_issue = ", ".join(pic_issue)

        # Merge any unmatched lines into details if details already exists
        if freeform:
            if fields.get("details"):
                fields["details"] = (fields["details"].rstrip() + "\n\n" + freeform).strip()
            else:
                fields["details"] = freeform

        missing = _missing_required_fields(fields)
        if missing:
            _send(
                bot,
                chat_id,
                "❌ Format /aduan belum lengkap. Field wajib: " + ", ".join(missing) + "\n\n" + _format_help(),
                thread_id=thread_id,
                reply_to=message.message_id,
            )
            return

        try:
            subtask_id = _create_subtask_from_aduan(fields, message)
            _send(
                bot,
                chat_id,
                f"✅ Aduan telah dicatat dengan nomor hris.ebdesk.com/app/subtask/{subtask_id} dan dalam proses pengecekan, dibantu oleh tim kami  {pic_issue} Silakan tunggu update lebih lanjut dari tim kami",
                thread_id=thread_id,
                reply_to=message.message_id,
            )
        except Exception as e:
            _logger().error(f"/aduan create failed: {e}")
            _send(
                bot,
                chat_id,
                f"❌ Failed creating Aduan as SubTask: {e}",
                thread_id=thread_id,
                reply_to=message.message_id,
            )
