import re
from typing import Dict, Optional, Tuple

import frappe
import json

from hrms.integrations.telegram_bot import utils as telegram_utils

ADUAN_COMMAND = "/aduan"


def _aduan_command_tokens() -> list[str]:
    """Return configured command tokens (each with leading '/').

    Config:
    - telegram_aduan_command: "/aduan" or "aduan" or ["/aduan", "/aduan_update", ...]
    """

    raw = frappe.conf.get("telegram_aduan_command")
    return telegram_utils.normalize_command_tokens(raw, default=[ADUAN_COMMAND])


def _aduan_command_token() -> str:
    """Return the configured command token (with leading '/').

    Config:
    - telegram_aduan_command: "/aduan" or "aduan" (optional)

    Note: Telegram may send commands as /cmd@BotUsername; we only store the base token.
    """

    # Backward-compatible: return the first configured token.
    tokens = _aduan_command_tokens()
    return tokens[0] if tokens else ADUAN_COMMAND


def aduan_command_for_menu() -> str:
    """Telegram BotCommand.command must NOT include leading '/'."""
    return telegram_utils.command_for_menu(_aduan_command_token()) or "aduan"


def aduan_commands_for_menu() -> list[str]:
    """Return command names (without leading '/') for Telegram menus."""
    out: list[str] = []
    for token in _aduan_command_tokens():
        cmd = telegram_utils.command_for_menu(token)
        if cmd:
            out.append(cmd)
    return out or ["aduan"]


def _aduan_menu_description_map() -> dict[str, str]:
    """Return normalized description map keyed by menu command (no leading '/').

    Config (optional): telegram_aduan_command_descriptions
    Accepts:
    - dict (or JSON string of dict): {"aduan": "...", "/aduan_info": "..."}
    - list (or JSON string of list) aligned with telegram_aduan_command tokens:
      ["desc for cmd1", "desc for cmd2", ...]
    """

    raw = frappe.conf.get("telegram_aduan_command_descriptions")
    if raw in (None, ""):
        return {}

    try:
        if isinstance(raw, str):
            raw = json.loads(raw)
    except Exception:
        # leave raw as-is
        pass

    normalized: dict[str, str] = {}

    def _norm_key(k: object) -> Optional[str]:
        if k in (None, ""):
            return None
        s = str(k).strip()
        if not s:
            return None
        return telegram_utils.command_for_menu(s)

    def _norm_desc(v: object) -> Optional[str]:
        if v in (None, ""):
            return None
        s = str(v).strip()
        return s or None

    if isinstance(raw, dict):
        for k, v in raw.items():
            kk = _norm_key(k)
            vv = _norm_desc(v)
            if kk and vv:
                normalized[kk] = vv
        return normalized

    if isinstance(raw, list):
        cmds = aduan_commands_for_menu()
        descs = [_norm_desc(x) for x in raw]
        # If lengths match, align 1:1. If only 1 provided, apply to all.
        if len(descs) == len(cmds):
            for c, d in zip(cmds, descs):
                if d:
                    normalized[c] = d
        elif len(descs) == 1 and descs[0]:
            for c in cmds:
                normalized[c] = descs[0]
        return normalized

    return {}


def aduan_menu_commands(default_description: str = "Create SubTask from complaint") -> list[tuple[str, str]]:
    """Return Telegram menu commands with per-command descriptions.

    Returns list of (command_without_slash, description).
    """

    cmds = aduan_commands_for_menu()
    desc_map = _aduan_menu_description_map()
    out: list[tuple[str, str]] = []
    for c in cmds:
        if not c:
            continue
        out.append((c, desc_map.get(c) or default_description))
    return out


def _aduan_help_text_map() -> dict[str, str]:
    """Return normalized help text map keyed by command token.

    Config (optional): telegram_aduan_help_texts
    Accepts:
    - dict (or JSON string of dict): {"/aduan": "...", "aduan_info": "..."}
    - list (or JSON string of list) aligned with telegram_aduan_command tokens

    Notes:
    - Keys may be with or without leading '/'.
    - Values may include '{cmd}' which will be replaced at runtime.
    """

    raw = frappe.conf.get("telegram_aduan_help_texts")
    if raw in (None, ""):
        return {}

    try:
        if isinstance(raw, str):
            raw = json.loads(raw)
    except Exception:
        pass

    normalized: dict[str, str] = {}

    def _norm_key(k: object) -> Optional[str]:
        if k in (None, ""):
            return None
        return telegram_utils.normalize_command_token(k, default=ADUAN_COMMAND)

    def _norm_val(v: object) -> Optional[str]:
        if v in (None, ""):
            return None
        s = str(v)
        return s if s.strip() else None

    if isinstance(raw, dict):
        for k, v in raw.items():
            kk = _norm_key(k)
            vv = _norm_val(v)
            if kk and vv:
                normalized[kk] = vv
        return normalized

    if isinstance(raw, list):
        tokens = _aduan_command_tokens()
        vals = [_norm_val(x) for x in raw]
        if len(vals) == len(tokens):
            for t, v in zip(tokens, vals):
                if v:
                    normalized[t] = v
        elif len(vals) == 1 and vals[0]:
            for t in tokens:
                normalized[t] = vals[0]
        return normalized

    return {}


def _logger():
    return frappe.logger("telegram")


def _aduan_rules() -> list[dict]:
    """Return normalized /aduan allow-list rules from config.

    Supported config shapes (backwards compatible):
    1) Legacy single:
       - telegram_aduan_chat_id
       - telegram_aduan_topic_id (optional)

    2) Simple multi:
       - telegram_aduan_chat_ids: [..] or "-1001,-1002" etc
       - telegram_aduan_topic_ids: [..] or "111,222" (optional)
         (applies to all listed chats)

    3) Advanced per-chat rules:
       - telegram_aduan_rules: [
           {"chat_id": -100..., "topic_ids": [111,222]},
           {"chat_id": -100..., "topic_ids": []}  # empty => allow any topic
         ]
    """

    raw_rules = frappe.conf.get("telegram_aduan_rules")
    if raw_rules not in (None, ""):
        try:
            if isinstance(raw_rules, str):
                raw_rules = json.loads(raw_rules)
        except Exception:
            raw_rules = None

    if isinstance(raw_rules, list):
        normalized: list[dict] = []
        for rule in raw_rules:
            if not isinstance(rule, dict):
                continue
            chat_id = telegram_utils._coerce_int(rule.get("chat_id"))
            if chat_id is None:
                continue
            topic_ids = telegram_utils._coerce_int_list(rule.get("topic_ids"))

            # Optional human-friendly labels (used only for messaging/logging)
            chat_name = rule.get("chat_name") or rule.get("group_name") or rule.get("chat_label")
            if chat_name not in (None, ""):
                chat_name = str(chat_name).strip() or None
            else:
                chat_name = None

            topic_names: dict[int, str] = {}

            # Preferred format: topics=[{"id": 14665, "name": "Task Management"}, ...]
            topics = rule.get("topics")
            if isinstance(topics, list):
                for t in topics:
                    if not isinstance(t, dict):
                        continue
                    tid = telegram_utils._coerce_int(t.get("id") or t.get("topic_id"))
                    tname = t.get("name") or t.get("topic_name")
                    if tid is None or tname in (None, ""):
                        continue
                    topic_names[tid] = str(tname).strip()

            # Backward-friendly format: topic_name can be string or list aligned with topic_ids
            # Example: {"topic_ids": [14665], "topic_name": ["Task Management"]}
            raw_topic_name = rule.get("topic_name")
            if raw_topic_name not in (None, "") and topic_ids:
                if isinstance(raw_topic_name, str):
                    name = raw_topic_name.strip()
                    if name:
                        for tid in topic_ids:
                            topic_names.setdefault(tid, name)
                elif isinstance(raw_topic_name, list):
                    names = [str(x).strip() for x in raw_topic_name if str(x).strip()]
                    if len(names) == len(topic_ids):
                        for tid, name in zip(topic_ids, names):
                            topic_names.setdefault(tid, name)
                    elif len(names) == 1:
                        for tid in topic_ids:
                            topic_names.setdefault(tid, names[0])

            normalized.append(
                {
                    "chat_id": chat_id,
                    "topic_ids": topic_ids,
                    "chat_name": chat_name,
                    "topic_names": topic_names,
                }
            )
        if normalized:
            return normalized

    chat_ids = telegram_utils._coerce_int_list(frappe.conf.get("telegram_aduan_chat_ids"))
    topic_ids = telegram_utils._coerce_int_list(frappe.conf.get("telegram_aduan_topic_ids"))
    if chat_ids:
        return [{"chat_id": cid, "topic_ids": topic_ids} for cid in chat_ids]

    legacy_chat_id = telegram_utils._conf_int("telegram_aduan_chat_id")
    legacy_topic_id = telegram_utils._conf_int("telegram_aduan_topic_id")
    if legacy_chat_id is None:
        return []
    return [{"chat_id": legacy_chat_id, "topic_ids": ([legacy_topic_id] if legacy_topic_id is not None else [])}]


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


def _is_allowed_group_topic(message) -> bool:
    chat_id = getattr(getattr(message, "chat", None), "id", None)
    if chat_id is None:
        return False

    thread_id = getattr(message, "message_thread_id", None)
    rules = _aduan_rules()
    for rule in rules:
        if rule.get("chat_id") != chat_id:
            continue
        allowed_topics: list[int] = rule.get("topic_ids") or []
        # If topic_ids is empty/not provided, do NOT enforce topic restriction.
        if not allowed_topics:
            return True
        return thread_id in allowed_topics

    return False


def _format_help(cmd: Optional[str] = None) -> str:
    cmd = cmd or _aduan_command_token()

    # 1) Try per-command configured help text.
    help_map = _aduan_help_text_map()
    if help_map:
        chosen = help_map.get(cmd)
        if not chosen:
            # Allow fallback by first token if caller passed an alias token.
            chosen = help_map.get(_aduan_command_token())
        if chosen:
            return chosen.replace("{cmd}", cmd)

    # 2) Default built-in help.
    return (
        f"Format {cmd} harus diawali dengan command, contoh:\n\n"
        f"{cmd}\n"
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
        value = telegram_utils._clean_field_value(m.group(2))

        if key in ("issue type", "issues"):
            fields["issue_type"] = value.title()  # Normalize to title case for matching
        elif key == "link dashboard":
            fields["link_dashboard"] = value
        elif key == "link maps":
            fields["link_maps"] = value
        else:
            fields[key] = value

    return fields, "\n".join(freeform_lines).strip()


def _send(
    bot,
    chat_id: int,
    text: str,
    thread_id: Optional[int] = None,
    reply_to: Optional[int] = None,
    parse_mode: Optional[str] = None,
):
    kwargs = {}
    if thread_id is not None:
        kwargs["message_thread_id"] = thread_id
    if reply_to is not None:
        kwargs["reply_to_message_id"] = reply_to
    if parse_mode is not None:
        kwargs["parse_mode"] = parse_mode
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

def _create_subtask_from_aduan(fields: Dict[str, str], message) -> str:
    settings = telegram_utils._conf_default_subtask_settings()

    maintask = settings["maintask"]
    tasks = settings["tasks"]
    owner = settings["owner"]
    pic_subtask = settings["pic_subtask"]

    subtask_name = (fields.get("subject") or "").strip()
    if not subtask_name:
        raise frappe.ValidationError("Subject is required")

    priority = telegram_utils._normalize_priority(fields.get("priority"))

    description = telegram_utils._build_description(fields, "", message)

    doc = frappe.get_doc(
        {
            "doctype": "SubTask",
            "maintask": maintask,
            "tasks": tasks,
            "subtask_name": subtask_name,
            "description": description,
            "requestor": telegram_utils._telegram_user_label(message),
            "created_by": telegram_utils._telegram_user_label(message),
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

    @bot.message_handler(
        func=lambda m: telegram_utils.find_command_offset(
            getattr(m, "text", "") or "", _aduan_command_tokens()
        )
        is not None
    )
    def handle_aduan(message):
        chat_id = getattr(getattr(message, "chat", None), "id", None)
        if chat_id is None:
            return

        thread_id = getattr(message, "message_thread_id", None)

        # Enforce allowed chats/topics from config.
        rules = _aduan_rules()
        if not rules:
            return

        matched_rule = None
        for rule in rules:
            if rule.get("chat_id") == chat_id:
                matched_rule = rule
                break

        if not matched_rule:
            return

        allowed_topics: list[int] = matched_rule.get("topic_ids") or []
        # Only enforce topic restriction if topic_ids is configured (non-empty).
        if allowed_topics and thread_id not in allowed_topics:
            # Build a more specific message if labels are provided in config.
            topic_names: dict[int, str] = matched_rule.get("topic_names") or {}
            chat_name = matched_rule.get("chat_name")

            allowed_topic_labels = [topic_names.get(tid) for tid in allowed_topics]
            allowed_topic_labels = [t for t in allowed_topic_labels if t]
            if allowed_topic_labels:
                topic_label = " / ".join(dict.fromkeys(allowed_topic_labels))
            else:
                topic_label = "ADUAN"

            if chat_name:
                msg = f"❌ Aduan grup <b>{chat_name}</b> hanya boleh pada topic <b>{topic_label}</b>"
            else:
                msg = f"❌ Aduan hanya boleh di topic <b>{topic_label}</b>"

            _send(
                bot,
                chat_id,
                msg,
                thread_id=thread_id,
                reply_to=getattr(message, "message_id", None),
                parse_mode="HTML",
            )
            return

        chat_id = message.chat.id
        raw_text = (message.text or "").strip()
        tokens = _aduan_command_tokens()
        matched = telegram_utils.match_command(raw_text, tokens)
        if not matched:
            return

        matched_cmd, offset = matched
        cmd = matched_cmd

        # Telegram best-practice: command should be at start of message.
        if offset is not None and offset > 0:
            _send(
                bot,
                chat_id,
                f"❌ Command {cmd} harus ditulis di awal pesan.\n\n" + _format_help(cmd),
                thread_id=thread_id,
                reply_to=message.message_id,
            )
            return

        payload = telegram_utils.extract_command_payload(raw_text, cmd)

        fields, freeform = _parse_aduan_fields(payload or "")

        pic_issue = "@justrenatta"
        if fields.get("issue_type"):
            issue_type_key = (fields["issue_type"] or "").strip().title()
            mapping_raw = telegram_utils._load_json("mapping_pic_issue.json")
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
                f"❌ Format {cmd} belum lengkap.\n\n" + _format_help(cmd),
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
