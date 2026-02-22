import re
from typing import Any, Dict, Optional, Tuple
import json
import frappe
import html
from functools import lru_cache



def _logger():
    return frappe.logger("telegram")


def _coerce_int(value) -> Optional[int]:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    try:
        return int(str(value).strip())
    except Exception:
        return None


def _coerce_int_list(value) -> list[int]:
    """Coerce config value into list[int].

    Accepts:
    - int
    - str int ("123")
    - list/tuple of int/str
    - comma-separated string ("1,2,3")
    - JSON array string ("[1,2,3]")
    """
    if value in (None, ""):
        return []

    if isinstance(value, (list, tuple, set)):
        out: list[int] = []
        for item in value:
            v = _coerce_int(item)
            if v is not None:
                out.append(v)
        return out

    if isinstance(value, int):
        return [value]

    s = str(value).strip()
    if not s:
        return []

    # JSON array string
    if s.startswith("[") and s.endswith("]"):
        try:
            parsed = json.loads(s)
            return _coerce_int_list(parsed)
        except Exception:
            return []

    # comma-separated
    if "," in s:
        parts = [p.strip() for p in s.split(",")]
        out2: list[int] = []
        for part in parts:
            v = _coerce_int(part)
            if v is not None:
                out2.append(v)
        return out2

    v = _coerce_int(s)
    return [v] if v is not None else []


def _is_db_connection_error(exc: Exception) -> bool:
    """Return True if exception likely indicates a dropped DB connection."""

    try:
        args = getattr(exc, "args", None) or []
        code = args[0] if args else None
        if isinstance(code, int) and code in (2006, 2013, 2014, 2055):
            return True
    except Exception:
        pass

    msg = str(exc or "").lower()
    markers = [
        "server has gone away",
        "lost connection to mysql server",
        "connection was killed",
        "is closed",
        "cannot operate on a closed",
    ]
    return any(m in msg for m in markers)


def ensure_db_connection() -> None:
    """Ensure `frappe.db` connection is alive for long-running processes.

    In TeleBot, the process may stay idle for hours. MariaDB/MySQL may close
    idle connections (wait_timeout), causing (2006, 'Server has gone away').
    """

    try:
        # Fast path: connection is healthy.
        frappe.db.sql("select 1")
        return
    except Exception as e:
        if not _is_db_connection_error(e):
            raise

    # Reconnect path.
    try:
        try:
            frappe.db.close()
        except Exception:
            pass

        # If we still have a db instance, reconnect in-place.
        try:
            frappe.db.connect()
        except Exception:
            # Fallback: recreate db instance from site config.
            frappe.connect(set_admin_as_user=False)

        # Validate.
        frappe.db.sql("select 1")
    finally:
        # Keep bot context stable.
        try:
            frappe.set_user("Administrator")
        except Exception:
            pass

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


@lru_cache(maxsize=1)
def _load_maintask_thread_mapping() -> list[dict[str, Any]]:
    """Load mapping_maintask.json.

    Expected shape (list):
    [{"chat_id": -100..., "thread_id": 2, "maintask": "...", "tasks": "...", "maintask_name": "..."}, ...]
    """

    try:
        raw = _load_json("mapping_maintask.json")
        return raw if isinstance(raw, list) else []
    except Exception:
        return []


def _settings_override_for_thread(chat_id: Optional[int], thread_id: Optional[int]) -> dict[str, str]:
    """Return maintask/tasks override based on chat+thread, else {}."""

    if chat_id is None and thread_id is None:
        return {}

    mapping = _load_maintask_thread_mapping()
    if not mapping:
        return {}

    best_row: Optional[dict[str, Any]] = None
    best_score = -1

    for row in mapping:
        if not isinstance(row, dict):
            continue

        cid = _coerce_int(row.get("chat_id"))
        tid = _coerce_int(row.get("thread_id"))

        # Missing cid/tid in mapping => wildcard.
        if cid is not None:
            if chat_id is None or cid != chat_id:
                continue
        if tid is not None:
            if thread_id is None or tid != thread_id:
                continue

        score = (1 if cid is not None else 0) + (1 if tid is not None else 0)
        if score > best_score:
            best_row = row
            best_score = score

    if not best_row:
        return {}

    maintask = (best_row.get("maintask") or "").strip()
    tasks = (best_row.get("tasks") or "").strip()
    maintask_name = (best_row.get("maintask_name") or "").strip()
    if not maintask or not tasks:
        return {}

    out = {"maintask": maintask, "tasks": tasks}
    if maintask_name:
        out["maintask_name"] = maintask_name
    return out

    return {}


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


def _normalize_issue_label(label: str) -> str:
    return re.sub(r"\s+", " ", (label or "").strip()).lower()


def normalize_command_token(raw: object, default: str) -> str:
    """Normalize a telegram command token.

    - Ensures it starts with '/'
    - Strips accidental '@BotName' suffix
    """

    # Backward-compatible: if a list/tuple/set is provided, use the first non-empty item.
    if isinstance(raw, (list, tuple, set)):
        chosen = None
        for item in raw:
            if item not in (None, "") and str(item).strip():
                chosen = item
                break
        raw = chosen

    token = str(raw).strip() if raw not in (None, "") else str(default).strip()
    if not token:
        token = str(default).strip()
    if not token.startswith("/"):
        token = "/" + token
    token = token.split("@", 1)[0].strip() or str(default).strip()
    if not token.startswith("/"):
        token = "/" + token
    return token


def normalize_command_tokens(raw: object, default: object) -> list[str]:
    """Normalize one or more telegram command tokens.

    Accepts raw as:
    - str ("/aduan" or "aduan")
    - list/tuple/set of str
    - JSON array string ("[\"/aduan\", \"/aduan_update\"]")

    Returns a de-duplicated list preserving order.
    """

    def _to_list(value: object) -> list[object]:
        if value in (None, ""):
            return []
        if isinstance(value, (list, tuple, set)):
            return list(value)
        if isinstance(value, str):
            s = value.strip()
            if s.startswith("[") and s.endswith("]"):
                try:
                    parsed = json.loads(s)
                    return _to_list(parsed)
                except Exception:
                    return [value]
            return [value]
        return [value]

    raw_items = _to_list(raw)
    default_items = _to_list(default)

    tokens: list[str] = []
    seen: set[str] = set()
    for item in (raw_items or default_items):
        if item in (None, ""):
            continue
        t = str(item).strip()
        if not t:
            continue
        t = normalize_command_token(t, default=str(default_items[0]) if default_items else "/")
        key = t.lower()
        if key in seen:
            continue
        seen.add(key)
        tokens.append(t)

    if tokens:
        return tokens

    # Last resort: always return at least one token.
    return [normalize_command_token(None, default=str(default_items[0]) if default_items else "/")]


def command_for_menu(command_token: str) -> str:
    """Return command name for Telegram menus (without leading '/')."""

    return (command_token or "").lstrip("/").strip().lower()


def _find_command_offset_single(text: str, command_token: str) -> Optional[int]:
    if not text:
        return None

    cmd = (command_token or "").strip()
    if not cmd:
        return None

    m = re.search(rf"(^|\s)({re.escape(cmd)})(?:@\w+)?\b", text, flags=re.IGNORECASE)
    if not m:
        return None

    return m.start(2)


def match_command(text: str, command_token: object) -> Optional[Tuple[str, int]]:
    """Return (matched_token, offset) if any command token matches, else None.

    - command_token may be a single string or a list/tuple/set of tokens.
    - If multiple tokens match, returns the earliest occurrence; ties prefer longer token.
    """

    tokens = normalize_command_tokens(command_token, default=[])
    if not tokens:
        return None

    best_token: Optional[str] = None
    best_offset: Optional[int] = None
    for t in tokens:
        off = _find_command_offset_single(text, t)
        if off is None:
            continue
        if best_offset is None or off < best_offset or (off == best_offset and best_token is not None and len(t) > len(best_token)):
            best_token = t
            best_offset = off

    if best_token is None or best_offset is None:
        return None
    return best_token, best_offset


def find_command_offset(text: str, command_token: object) -> Optional[int]:
    """Return index where command token starts, or None if not present.

    Detects '/cmd' or '/cmd@BotName' at start or after whitespace.
    """

    # Backward-compatible: accept a single token or multiple tokens.
    if isinstance(command_token, (list, tuple, set)):
        best = match_command(text, command_token)
        return best[1] if best else None

    return _find_command_offset_single(text, str(command_token or ""))


def extract_command_payload(text: str, command_token: object) -> Optional[str]:
    """If text begins with command, return payload after it; else None."""

    if not text:
        return None

    s = text.strip()
    if not s:
        return None

    # Multiple tokens: return payload for the first token that matches at the start.
    if isinstance(command_token, (list, tuple, set)):
        tokens = normalize_command_tokens(command_token, default=[])
        for t in tokens:
            m = re.match(
                rf"^{re.escape(t)}(?:@\w+)?\b\s*(.*)$",
                s,
                flags=re.IGNORECASE | re.DOTALL,
            )
            if m:
                return (m.group(1) or "").strip()
        return None

    cmd = (str(command_token or "")).strip()
    if not cmd:
        return None

    m = re.match(rf"^{re.escape(cmd)}(?:@\w+)?\b\s*(.*)$", s, flags=re.IGNORECASE | re.DOTALL)
    if not m:
        return None

    return (m.group(1) or "").strip()

def _conf_default_subtask_settings(message: object = None) -> Dict[str, Any]:
    settings: Dict[str, Any] = {
        "maintask": _conf_str("telegram_aduan_default_maintask", "MT-202511-0000073"),
        "maintask_name": _conf_str("telegram_aduan_default_maintask_name", "FUSION_REVAMP"),
        "tasks": _conf_str("telegram_aduan_default_tasks", "T-202511-0000413"),
        "owner": _conf_str("telegram_aduan_default_owner", "renata@stellardata.ai"),
        "pic_subtask": _conf_str("telegram_aduan_default_pic_subtask", "HR-EMP-00413"),
        "target_time": int(frappe.conf.get("telegram_aduan_default_target_time") or 1),
        "unit_target_time": _conf_str("telegram_aduan_default_unit_target_time", "Hours"),
        "value": int(frappe.conf.get("telegram_aduan_default_value") or 1),
    }

    if message is not None:
        chat_id = _coerce_int(getattr(getattr(message, "chat", None), "id", None))
        thread_id = _coerce_int(getattr(message, "message_thread_id", None))
        override = _settings_override_for_thread(chat_id, thread_id)
        if override:
            settings.update(override)

    return settings


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


def is_info_command(command_token: str) -> bool:
    """Return True if command token represents an info-style command.

    We treat commands whose menu name contains 'info' (e.g. 'aduan_info',
    'aduan_info_staging') as the info flow.
    """

    name = command_for_menu(command_token)
    if not name:
        return False
    return "info" in name


def _strip_html_to_text(value: str) -> str:
    """Best-effort HTML -> text for Comment.content."""

    html = value or ""
    try:
        from frappe.utils import strip_html

        text = strip_html(html)
    except Exception:
        text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", (text or "")).strip()
    return text


def _load_issue_mapping() -> dict:
    """Load mapping_pic_issue.json as a dict.

    Expected shape:
    {
      "APPS/MENU": {"label": "Menu", "pic": ["@a", "@b"]},
      ...
    }
    """

    try:
        raw = _load_json("mapping_pic_issue.json")
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def issue_label_from_key(issue_key: str) -> str:
    """Return human label for an issue key if mapping exists; else issue_key."""

    key = (issue_key or "").strip()
    if not key:
        return ""

    mapping = _load_issue_mapping()
    meta = mapping.get(key) or mapping.get(key.upper())
    if isinstance(meta, dict):
        lbl = meta.get("label")
        if lbl not in (None, ""):
            s = str(lbl).strip()
            if s:
                return s
    return key

def _format_hyperlink(text: str, url: str) -> str:
    """Format text as a Telegram hyperlink if possible; else return text."""
    t = (text or "").strip()
    u = (url or "").strip()
    if not t:
        return ""
    if not u:
        return t
    return f'<a href="{u}">{t}</a>'


def _escape_html(value: object) -> str:
    s = "" if value in (None, "") else str(value)
    try:
        from frappe.utils import escape_html as frappe_escape_html

        return frappe_escape_html(s)
    except Exception:
        return html.escape(s, quote=True)


class _SafeFormatDict(dict):
    def __missing__(self, key: str):
        # Keep unknown placeholders as-is so templates don't crash.
        return "{" + str(key) + "}"


def _render_template(template: str, context: dict) -> str:
    tpl = template or ""
    try:
        return tpl.format_map(_SafeFormatDict(context or {}))
    except Exception:
        # If template is malformed, fall back to raw.
        return tpl


def _aduan_response_template_map() -> dict[str, str]:
    """Return response templates keyed by normalized command token.

    Config (optional): telegram_aduan_response_texts
    Accepts:
    - dict (or JSON string of dict): {"/aduan": "...", "aduan_info": "..."}
    - list (or JSON string of list) aligned with telegram_aduan_command tokens

    Keys may be with or without leading '/'.
    """

    raw = frappe.conf.get("telegram_aduan_response_texts")
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
        return normalize_command_token(k, default="/")

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
        # Align with configured command tokens
        tokens = normalize_command_tokens(frappe.conf.get("telegram_aduan_command"), default=[])
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


def response_template_for_command(command_token: str) -> Optional[str]:
    """Get configured response template for a given command token."""

    cmd = normalize_command_token(command_token, default="/")
    return _aduan_response_template_map().get(cmd)

