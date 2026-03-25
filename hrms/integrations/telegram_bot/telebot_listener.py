import re
import threading
import time
from typing import Optional, Dict, Any

import frappe

from hrms.integrations.telegram_bot.aduan import telegram_aduan_bot
from hrms.integrations.telegram_bot.employee import telegram_employee_bot
from hrms.integrations.telegram_bot.utils import helper

try:
    import telebot  # pyTelegramBotAPI
except ImportError:
    telebot = None


def _logger():
    return frappe.logger("telegram")


def _get_token() -> str:
    token = frappe.conf.get("telegram_bot_token")
    if not token:
        raise RuntimeError("telegram_bot_token missing in site config")
    return token


def _get_site() -> str:
    site = frappe.conf.get("default_site") or "hrms.localhost"
    return site


def _build_bot():
    if telebot is None:
        raise RuntimeError(
            "pyTelegramBotAPI is not installed. Jalankan: bench pip install pyTelegramBotAPI"
        )
    token = _get_token()
    # Gunakan threaded=False agar semua handler dieksekusi di thread polling tunggal dengan context Frappe global.
    bot = telebot.TeleBot(token, parse_mode=None, threaded=False)
    try:
        me = bot.get_me()
        _logger().info(f"TeleBot initialized. Username={me.username} ID={me.id}")
    except Exception as e:
        _logger().error(f"TeleBot get_me() failed: {e}")
        raise

    _configure_bot_commands(bot)
    return bot


def _configure_bot_commands(bot):
    """Configure command suggestions per chat scope.

    Important: this affects what Telegram shows in the '/' command menu.
    Handlers are still additionally guarded by chat.type checks.
    """

    # Older/newer pyTelegramBotAPI versions may differ; keep this best-effort.
    try:
        from telebot import types
    except Exception:
        return

    def _scope(name: str):
        return getattr(types, name, None)

    def _debug_dump():
        """Dump current command lists per scope for troubleshooting."""
        try:
            dumps = []
            scopes = [
                ("default", _scope("BotCommandScopeDefault")),
                ("all_private", _scope("BotCommandScopeAllPrivateChats")),
                ("all_group", _scope("BotCommandScopeAllGroupChats")),
                ("all_admins", _scope("BotCommandScopeAllChatAdministrators")),
            ]
            for label, scope_cls in scopes:
                if not scope_cls:
                    continue
                try:
                    cmds = bot.get_my_commands(scope=scope_cls())
                    dumps.append(f"{label}={[c.command for c in cmds]}")
                except Exception as e:
                    dumps.append(f"{label}=<error {e}>")

            try:
                chat_id = frappe.conf.get("telegram_aduan_chat_id")
                chat_id = int(chat_id) if chat_id not in (None, "") else None
            except Exception:
                chat_id = None

            if chat_id is not None:
                chat_scope_cls = _scope("BotCommandScopeChat")
                if chat_scope_cls:
                    try:
                        cmds = bot.get_my_commands(scope=chat_scope_cls(chat_id))
                        dumps.append(f"chat({chat_id})={[c.command for c in cmds]}")
                    except Exception as e:
                        dumps.append(f"chat({chat_id})=<error {e}>")

            msg = "Telegram bot commands dump: " + "; ".join(dumps)
            _logger().info(msg)
            print(msg)
        except Exception:
            pass

    try:
        # If these scope classes aren't available, we can't do per-scope menus.
        required = [
            _scope("BotCommandScopeAllPrivateChats"),
            _scope("BotCommandScopeAllGroupChats"),
            _scope("BotCommandScopeDefault"),
        ]
        if any(r is None for r in required):
            _logger().warning(
                "pyTelegramBotAPI too old for scoped commands; BotFather commands may still appear in groups."
            )
            print("WARNING: pyTelegramBotAPI too old for scoped commands")
            return

        private_commands = [
            types.BotCommand("start", "Show help")
        ]

        # Also expose aduan commands in private chats (keep existing commands intact).
        private_aduan_commands = [
            types.BotCommand(cmd, desc)
            for cmd, desc in (
                telegram_aduan_bot.aduan_menu_commands(is_private=True) or []
            )
            if cmd
        ]
        if private_aduan_commands:
            # De-duplicate while preserving order (first occurrence wins).
            seen = set()
            merged = []
            for c in private_commands + private_aduan_commands:
                if c.command in seen:
                    continue
                seen.add(c.command)
                merged.append(c)
            private_commands = merged

        # Also expose employee commands in private chats.
        private_employee_commands = [
            types.BotCommand(cmd.lstrip("/"), desc)
            for cmd, desc in (telegram_employee_bot.employee_menu_commands() or [])
            if cmd
        ]
        if private_employee_commands:
            seen = {c.command for c in private_commands}
            for c in private_employee_commands:
                if c.command not in seen:
                    seen.add(c.command)
                    private_commands.append(c)

        # By default, do NOT show any commands in group chats.
        # We'll enable /aduan only for the configured group chat_id scope.
        group_commands = []
        group_commands_for_configured_chat = [
            types.BotCommand(cmd, desc)
            for cmd, desc in (telegram_aduan_bot.aduan_menu_commands() or [])
            if cmd
        ]

        # Best-effort cleanup so old BotFather/default commands don't linger
        scopes_to_clear = [
            types.BotCommandScopeDefault(),
            types.BotCommandScopeAllPrivateChats(),
            types.BotCommandScopeAllGroupChats(),
            types.BotCommandScopeAllChatAdministrators(),
        ]
        for scope in scopes_to_clear:
            try:
                bot.delete_my_commands(scope=scope)
            except Exception:
                pass

        bot.set_my_commands(
            private_commands, scope=types.BotCommandScopeAllPrivateChats()
        )
        bot.set_my_commands(group_commands, scope=types.BotCommandScopeAllGroupChats())
        bot.set_my_commands(
            group_commands, scope=types.BotCommandScopeAllChatAdministrators()
        )

        def _aduan_chat_ids() -> list[int]:
            # Prefer advanced rules if present, else multi, else legacy.
            raw_rules = frappe.conf.get("telegram_aduan_rules")
            if raw_rules not in (None, ""):
                try:
                    if isinstance(raw_rules, str):
                        import json

                        raw_rules = json.loads(raw_rules)
                except Exception:
                    raw_rules = None
            if isinstance(raw_rules, list):
                ids = []
                for rule in raw_rules:
                    if isinstance(rule, dict):
                        cid = helper._coerce_int(rule.get("chat_id"))
                        if cid is not None:
                            ids.append(cid)
                if ids:
                    return sorted(list(set(ids)))

            ids = helper._coerce_int_list(
                frappe.conf.get("telegram_aduan_chat_ids")
            )
            if ids:
                return sorted(list(set(ids)))

            legacy = helper._coerce_int(
                frappe.conf.get("telegram_aduan_chat_id")
            )
            return [legacy] if legacy is not None else []

        # Also set commands for configured /aduan group(s) specifically (overrides any chat-specific settings)
        for chat_id in _aduan_chat_ids():
            try:
                bot.delete_my_commands(scope=types.BotCommandScopeChat(chat_id))
            except Exception:
                pass
            try:
                bot.delete_my_commands(
                    scope=types.BotCommandScopeChatAdministrators(chat_id)
                )
            except Exception:
                pass

            try:
                bot.set_my_commands(
                    group_commands_for_configured_chat,
                    scope=types.BotCommandScopeChat(chat_id),
                )
            except Exception:
                pass
            try:
                bot.set_my_commands(
                    group_commands_for_configured_chat,
                    scope=types.BotCommandScopeChatAdministrators(chat_id),
                )
            except Exception:
                pass

        configured_group_cmds = [c.command for c in group_commands_for_configured_chat]
        configured_private_commands = [c.command for c in private_commands]
        _logger().info(
            f"Telegram bot commands configured: private={configured_private_commands} group (all)=<none>; group (configured chat(s))={configured_group_cmds}"
        )
        print(
            f"Telegram bot commands configured: private={configured_private_commands} group (all)=<none>; group (configured chat(s))={configured_group_cmds}"
        )
        _debug_dump()

    except Exception as e:
        _logger().warning(f"set_my_commands failed (non-fatal): {e}")
        print(f"WARNING: set_my_commands failed (non-fatal): {e}")
        _debug_dump()


def _send(
    bot,
    chat_id: int,
    text: Optional[str] = None,
    thread_id: Optional[int] = None,
    reply_to: Optional[int] = None,
    parse_mode: Optional[str] = None,
    caption: Optional[str] = None,
    send_document: Optional[bool] = None,
    file_path: Optional[str] = None,
):
    kwargs = {}
    if thread_id is not None:
        kwargs["message_thread_id"] = thread_id
    if reply_to is not None:
        kwargs["reply_to_message_id"] = reply_to
    if parse_mode is not None:
        kwargs["parse_mode"] = parse_mode
    if caption is not None:
        kwargs["caption"] = caption

    if send_document and file_path:
        with open(file_path, "rb") as f:
            return bot.send_document(chat_id, f, **kwargs)
    return bot.send_message(chat_id, text, **kwargs)


def _register_handlers(bot):

    @bot.message_handler(commands=["start"])
    def handle_start(message):
        if getattr(message.chat, "type", None) != "private":
            return
        chat_id = message.chat.id
        username = message.from_user.username
        print(f"Username telegram: {username} chat_id: {chat_id}")
        default = f"Welcome {username} to the HRIS Telegram Bot!"

        # Reuse the already-configured private command menu.
        # We fetch it from Telegram (so it stays consistent with `_configure_bot_commands`).
        commands_text = ""
        try:
            from telebot import types

            cmds = bot.get_my_commands(scope=types.BotCommandScopeAllPrivateChats())
            lines: list[str] = []
            for c in (cmds or []):
                cmd = helper.normalize_command_token(
                    getattr(c, "command", "") or "",
                    default="/start",
                )
                desc = (getattr(c, "description", "") or "").strip()
                lines.append(f"{cmd} - {desc}".strip(" -"))
            commands_text = "\n".join([l for l in lines if l.strip()])
        except Exception:
            commands_text = ""

        if not (commands_text or "").strip():
            # Fallback: build from local menu definitions.
            # Keep this minimal and rely on helper normalization + de-dup.
            items: list[tuple[str, str]] = [("/start", "Show help")]

            try:
                items.extend(telegram_aduan_bot.aduan_menu_commands(is_private=True) or [])
            except Exception:
                pass
            try:
                items.extend(telegram_employee_bot.employee_menu_commands() or [])
            except Exception:
                pass

            seen: set[str] = set()
            lines2: list[str] = []
            for raw_cmd, raw_desc in items:
                cmd2 = helper.normalize_command_token(raw_cmd, default="/start")
                if cmd2 in seen:
                    continue
                seen.add(cmd2)
                desc2 = ("" if raw_desc in (None, "") else str(raw_desc)).strip()
                lines2.append(f"{cmd2} - {desc2}".strip(" -"))
            commands_text = "\n".join([l for l in lines2 if l.strip()])

        context = {
            "username": username,
            "commands": commands_text,
        }
        template = helper._render_response_text(
            "start",  # command_token may be None or not match a menu, so we use the base command as key for config lookup with a sensible default template.
            default,
            context,
        )
        if template:
            response_text = template.strip()
        else:
            response_text = default
        _send(
            bot,
            chat_id,
            response_text
        )


    # Register employee handlers (private chat only)
    telegram_employee_bot.register_handlers(bot)
    # Register group/topic handler(s) in a separate module
    telegram_aduan_bot.register_private_handlers(bot)
    telegram_aduan_bot.register_handlers(bot)


def run_bot(blocking: bool = True):
    """Entry point untuk menjalankan TeleBot.

    Perubahan: gunakan threaded=False dan context Frappe global tunggal agar tidak muncul error 'object is not bound'.
    """
    # Init context global sekali
    site = _get_site()
    frappe.init(site=site)
    frappe.connect()
    frappe.set_user("Administrator")

    bot = _build_bot()
    _register_handlers(bot)
    print("Starting TeleBot polling loop (single-thread)...")

    def _poll():
        while True:
            try:
                bot.infinity_polling(timeout=20, long_polling_timeout=20)
            except Exception as e:
                _logger().error(f"infinity_polling exception: {e}")
                time.sleep(5)

    if blocking:
        _poll()
    else:
        t = threading.Thread(target=_poll, name="telebot-poll", daemon=True)
        t.start()
        return t
