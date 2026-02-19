import re
from typing import Dict, Optional, Tuple
import json
import frappe
import html



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

def _conf_default_subtask_settings() -> Dict[str, str]:
    return {
        "maintask": _conf_str("telegram_aduan_default_maintask", "MT-202511-0000073"),
        "maintask_name": _conf_str("telegram_aduan_default_maintask_name", "FUSION_REVAMP"),
        "tasks": _conf_str("telegram_aduan_default_tasks", "T-202511-0000413"),
        "owner": _conf_str("telegram_aduan_default_owner", "renata@stellardata.ai"),
        "pic_subtask": _conf_str("telegram_aduan_default_pic_subtask", "HR-EMP-00413"),
        "target_time": int(frappe.conf.get("telegram_aduan_default_target_time") or 1),
        "unit_target_time": _conf_str("telegram_aduan_default_unit_target_time", "Hours"),
        "value": int(frappe.conf.get("telegram_aduan_default_value") or 1),
    }


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

    label = issue_label_from_key(str(issue_key or "").strip())
    return label or "-"


def _subtask_progress_comments(subtask_name: str, limit: int = 10) -> list[str]:
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
        limit_page_length=int(limit or 10),
    )

    out: list[str] = []
    for r in rows or []:
        text = _strip_html_to_text(r.get("content") or "")
        if not text:
            continue
        by = (r.get("comment_email") or r.get("comment_by") or "").strip() or "unknown"
        out.append(f"- {text} ({by})")
    return out


def format_aduan_info_response(subtask_name: str, command_token: Optional[str] = None) -> str:
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

    doc = frappe.get_doc("SubTask", name)

    issue_label = _subtask_issue_label(doc)
    status_raw = (getattr(doc, "status", "") or "").strip() or "-"
    status_out = status_raw.lower() if status_raw != "-" else "-"

    pic_name = (getattr(doc, "pic_subtask_name", "") or "").strip()
    if not pic_name:
        pic = getattr(doc, "pic_subtask", None)
        if pic:
            try:
                pic_name = (frappe.db.get_value("Employee", pic, "employee_name") or "").strip()
            except Exception:
                pic_name = ""
    if not pic_name:
        pic_name = "-"

    root_cause = (getattr(doc, "root_cause", "") or "").strip() or "-"
    modified = getattr(doc, "modified", None) or "-"

    progress_lines = _subtask_progress_comments(doc.name, limit=10)
    progress_updates = "\n".join(["  " + l for l in (progress_lines or ["- (belum ada update)"])])

    base = (frappe.conf.get("telegram_aduan_site") or "").strip()
    subtask_url = (base + doc.name) if base else doc.name
    subtask_link = _format_hyperlink(doc.name, subtask_url) if base else doc.name

    context = {
        "name": _escape_html(doc.name),
        "issue": _escape_html(issue_label),
        "status": _escape_html(status_out),
        "pic_subtask_name": _escape_html(pic_name),
        "root_cause": _escape_html(root_cause),
        "modified": _escape_html(modified),
        "progress_updates": _escape_html(progress_updates),
        "subtask_url": _escape_html(subtask_url),
        "subtask_link": subtask_link,
    }

    template = response_template_for_command(command_token) if command_token else None
    if template:
        return _render_template(template, context).strip()

    # Fallback default (built-in)
    lines: list[str] = []
    lines.append("📌 Task Update")
    lines.append("")
    lines.append(f"• nomor aduan: {doc.name}")
    lines.append(f"• issue type: {issue_label}")
    lines.append(f"• Status          : {status_out}")
    lines.append(f"• PIC             : {pic_name}")
    lines.append(f"• Root Cause      : {root_cause}")
    lines.append("• Progress Update :")
    lines.extend(["  " + l for l in (progress_lines or ["- (belum ada update)"])])
    lines.append("")
    lines.append(f"🕒 Last Update: {modified}")
    return "\n".join(lines).strip()


def format_aduan_success_response(
    command_token: str,
    subtask_id: str,
    pic_issue: str,
) -> str:
    """Build success response for /aduan-style commands.

    Placeholders:
    - {subtask_id}
    - {subtask_url}
    - {subtask_link}
    - {pic_issue}
    - {cmd}
    """

    cmd = normalize_command_token(command_token, default="/aduan")
    sid = (subtask_id or "").strip()
    base = (frappe.conf.get("telegram_aduan_site") or "hris.ebdesk.com/app/subtask/").strip()
    subtask_url = (base + sid) if base else sid
    subtask_link = _format_hyperlink(sid, subtask_url) if base else sid

    context = {
        "cmd": _escape_html(cmd),
        "subtask_id": _escape_html(sid),
        "subtask_url": _escape_html(subtask_url),
        "subtask_link": subtask_link,
        "pic_issue": _escape_html(pic_issue or ""),
    }

    template = response_template_for_command(cmd)
    if template:
        return _render_template(template, context).strip()

    return (
        f"✅ Aduan telah dicatat dengan nomor {subtask_url} dan dalam proses pengecekan, "
        f"dibantu oleh tim kami {pic_issue} Silakan tunggu update lebih lanjut dari tim kami"
    ).strip()
