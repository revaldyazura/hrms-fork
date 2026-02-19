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
       - telegram_aduan_thread_id (optional)

    2) Simple multi:
       - telegram_aduan_chat_ids: [..] or "-1001,-1002" etc
       - telegram_aduan_thread_ids: [..] or "111,222" (optional)
         (applies to all listed chats)

    3) Advanced per-chat rules:
       - telegram_aduan_rules: [
           {"chat_id": -100..., "thread_ids": [111,222]},
           {"chat_id": -100..., "thread_ids": []}  # empty => allow any thread
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
            thread_ids = telegram_utils._coerce_int_list(rule.get("thread_ids"))

            # Optional human-friendly labels (used only for messaging/logging)
            chat_name = rule.get("chat_name") or rule.get("group_name") or rule.get("chat_label")
            if chat_name not in (None, ""):
                chat_name = str(chat_name).strip() or None
            else:
                chat_name = None

            thread_names: dict[int, str] = {}

            # Preferred format: threads=[{"id": 14665, "name": "Task Management"}, ...]
            threads = rule.get("threads")
            if isinstance(threads, list):
                for t in threads:
                    if not isinstance(t, dict):
                        continue
                    tid = telegram_utils._coerce_int(t.get("id") or t.get("thread_id"))
                    tname = t.get("name") or t.get("thread_name")
                    if tid is None or tname in (None, ""):
                        continue
                    thread_names[tid] = str(tname).strip()

            # Backward-friendly format: thread_name can be string or list aligned with thread_ids
            # Example: {"thread_ids": [14665], "thread_name": ["Task Management"]}
            raw_thread_name = rule.get("thread_name")
            if raw_thread_name not in (None, "") and thread_ids:
                if isinstance(raw_thread_name, str):
                    name = raw_thread_name.strip()
                    if name:
                        for tid in thread_ids:
                            thread_names.setdefault(tid, name)
                elif isinstance(raw_thread_name, list):
                    names = [str(x).strip() for x in raw_thread_name if str(x).strip()]
                    if len(names) == len(thread_ids):
                        for tid, name in zip(thread_ids, names):
                            thread_names.setdefault(tid, name)
                    elif len(names) == 1:
                        for tid in thread_ids:
                            thread_names.setdefault(tid, names[0])

            normalized.append(
                {
                    "chat_id": chat_id,
                    "thread_ids": thread_ids,
                    "chat_name": chat_name,
                    "thread_names": thread_names,
                }
            )
        if normalized:
            return normalized

    chat_ids = telegram_utils._coerce_int_list(frappe.conf.get("telegram_aduan_chat_ids"))
    thread_ids = telegram_utils._coerce_int_list(frappe.conf.get("telegram_aduan_thread_ids"))
    if chat_ids:
        return [{"chat_id": cid, "thread_ids": thread_ids} for cid in chat_ids]

    legacy_chat_id = telegram_utils._conf_int("telegram_aduan_chat_id")
    legacy_thread_id = telegram_utils._conf_int("telegram_aduan_thread_id")
    if legacy_chat_id is None:
        return []
    return [{"chat_id": legacy_chat_id, "thread_ids": ([legacy_thread_id] if legacy_thread_id is not None else [])}]


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


def _is_allowed_group_thread(message) -> bool:
    chat_id = getattr(getattr(message, "chat", None), "id", None)
    if chat_id is None:
        return False

    thread_id = getattr(message, "message_thread_id", None)
    rules = _aduan_rules()
    for rule in rules:
        if rule.get("chat_id") != chat_id:
            continue
        allowed_threads: list[int] = rule.get("thread_ids") or []
        # If thread_ids is empty/not provided, do NOT enforce thread restriction.
        if not allowed_threads:
            return True
        return thread_id in allowed_threads

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


def _resolve_issue_type(issue_label: str, maintask: str, maintask_name: str) -> str:
    """Return docname of Fusion Issue Types."""
    issue_input = (issue_label or "").strip()
    if not issue_input:
        raise frappe.ValidationError("Issue Type is required")

    issue_key = _issue_key_from_user_input(issue_input) or issue_input

    filters = {"issue": issue_key}
    # If maintask is provided, narrow down to avoid ambiguity
    if maintask:
        filters["maintask"] = maintask

    name = frappe.db.get_value("Fusion Issue Types", filters, "name")
    if not name:
        # Backward-friendly: if user typed a label and mapping exists but DB entry missing.
        raise frappe.DoesNotExistError(
            f"Fusion Issue Types not found for issue='{issue_key}'" + (f" and maintask='{maintask_name}'" if maintask else "")
        )
    return name


def _normalize_issue_label(label: str) -> str:
    return re.sub(r"\s+", " ", (label or "").strip()).lower()


def _issue_key_from_user_input(user_value: str) -> Optional[str]:
    """Translate user-provided issue value (label or key) into DB issue key."""
    v = (user_value or "").strip()
    if not v:
        return None

    mapping = telegram_utils._load_issue_mapping()
    if not mapping:
        return None

    # 1) If user already typed the key.
    if v in mapping:
        return v
    v_upper = v.upper()
    if v_upper in mapping:
        return v_upper

    # 2) Match by label (case-insensitive).
    wanted = _normalize_issue_label(v)
    for key, meta in mapping.items():
        if not isinstance(meta, dict):
            continue
        lbl = meta.get("label")
        if lbl in (None, ""):
            continue
        if _normalize_issue_label(str(lbl)) == wanted:
            return str(key).strip()

    return None


def _pics_for_issue_user_input(user_value: str) -> list[str]:
    """Return PIC mentions for an issue value provided by user (label or key)."""
    issue_key = _issue_key_from_user_input(user_value)
    mapping = telegram_utils._load_issue_mapping()
    if not issue_key or issue_key not in mapping:
        return []

    meta = mapping.get(issue_key)
    if not isinstance(meta, dict):
        return []

    pics = meta.get("pic")
    if isinstance(pics, str):
        pics = [pics]
    if not isinstance(pics, list):
        return []

    out: list[str] = []
    for p in pics:
        if p in (None, ""):
            continue
        s = str(p).strip()
        if s:
            out.append(s)
    return out

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
        issue_name = _resolve_issue_type(fields["issue_type"], maintask, settings["maintask_name"])
        doc.append("issues_type", {"issue": issue_name})

    _insert_with_owner(doc, owner)
    frappe.db.commit()
    return doc.name


def register_handlers(bot):
    """Register /aduan handler for a specific group+thread.

    Configuration in site_config (frappe.conf):
    - telegram_aduan_chat_id: int (required)
    - telegram_aduan_thread_id: int (optional)

    Defaults (optional overrides):
    - telegram_aduan_default_maintask
    - telegram_aduan_default_tasks
    - telegram_aduan_default_owner
    - telegram_aduan_default_pic_subtask
    - telegram_aduan_default_target_time
    - telegram_aduan_default_unit_target_time
    - telegram_aduan_default_value
    """

    @bot.message_handler(content_types=["text", "photo", "document", "video", "animation"])
    def handle_aduan(message):
        # TeleBot runs as a long-lived process; make sure we don't keep a long
        # DB transaction around (InnoDB REPEATABLE READ can otherwise show stale
        # snapshots across multiple messages).
        try:
            frappe.db.rollback()
            # Clear per-transaction value cache that can otherwise persist
            # across messages in a long-running process.
            try:
                frappe.db.value_cache.clear()
            except Exception:
                pass
        except Exception:
            pass

        chat_id = getattr(getattr(message, "chat", None), "id", None)
        if chat_id is None:
            return

        thread_id = getattr(message, "message_thread_id", None)

        # Enforce allowed chats/threads from config.
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

        allowed_threads: list[int] = matched_rule.get("thread_ids") or []
        # Only enforce thread restriction if thread_ids is configured (non-empty).
        if allowed_threads and thread_id not in allowed_threads:
        #     # Build a more specific message if labels are provided in config.
        #     thread_names: dict[int, str] = matched_rule.get("thread_names") or {}
        #     chat_name = matched_rule.get("chat_name")

        #     allowed_thread_labels = [thread_names.get(tid) for tid in allowed_threads]
        #     allowed_thread_labels = [t for t in allowed_thread_labels if t]
        #     if allowed_thread_labels:
        #         thread_label = " / ".join(dict.fromkeys(allowed_thread_labels))
        #     else:
        #         thread_label = "ADUAN"

        #     if chat_name:
        #         msg = f"❌ Aduan grup <b>{chat_name}</b> hanya boleh pada thread <b>{thread_label}</b>"
        #     else:
        #         msg = f"❌ Aduan hanya boleh di thread <b>{thread_label}</b>"

        #     _send(
        #         bot,
        #         chat_id,
        #         msg,
        #         thread_id=thread_id,
        #         reply_to=getattr(message, "message_id", None),
        #         parse_mode="HTML",
        #     )
            return

        chat_id = message.chat.id
        raw_text = ((getattr(message, "text", None) or getattr(message, "caption", None) or "")).strip()
        if not raw_text:
            return
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
                parse_mode="HTML",
            )
            return

        payload = telegram_utils.extract_command_payload(raw_text, cmd)

        # Separate flow for info-style commands, e.g. /aduan_info ST-...
        if telegram_utils.is_info_command(cmd):
            subtask_id = ((payload or "").strip().split() or [""])[0].strip()
            if not subtask_id:
                _send(
                    bot,
                    chat_id,
                    f"❌ Format {cmd} belum lengkap.\n\n" + _format_help(cmd),
                    thread_id=thread_id,
                    reply_to=message.message_id,
                    parse_mode="HTML",
                )
                return

            subtask_id = subtask_id.upper()
            if not re.match(r"^ST-\d{6}-\d{7}$", subtask_id):
                _send(
                    bot,
                    chat_id,
                    f"❌ Format {cmd} belum valid.\n\n" + _format_help(cmd),
                    thread_id=thread_id,
                    reply_to=message.message_id,
                    parse_mode="HTML",
                )
                return

            try:
                text = telegram_utils.format_aduan_info_response(subtask_id, command_token=cmd)
                _send(
                    bot,
                    chat_id,
                    text,
                    thread_id=thread_id,
                    reply_to=message.message_id,
                    parse_mode="HTML",
                )
            except Exception as e:
                _logger().error(f"/aduan_info failed: {e}")
                _send(
                    bot,
                    chat_id,
                    f"❌ Failed fetching Aduan info: {e}",
                    thread_id=thread_id,
                    reply_to=message.message_id,
                )
            return

        fields, freeform = _parse_aduan_fields(payload or "")

        pic_issue = "@justrenatta"
        if fields.get("issue_type"):
            pics = _pics_for_issue_user_input(fields["issue_type"])
            if pics:
                pic_issue = ", ".join(pics)

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
                parse_mode="HTML",
            )
            return

        try:
            subtask_id = _create_subtask_from_aduan(fields, message)
            _send(
                bot,
                chat_id,
                telegram_utils.format_aduan_success_response(cmd, subtask_id, pic_issue),
                thread_id=thread_id,
                reply_to=message.message_id,
                parse_mode="HTML",
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
        finally:
            # Always end the transaction for this message to avoid holding
            # stale snapshots / locks in a long-running bot process.
            try:
                frappe.db.rollback()
                try:
                    frappe.db.value_cache.clear()
                except Exception:
                    pass
            except Exception:
                pass
