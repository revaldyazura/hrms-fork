import re
import threading
import time
from typing import Optional, Dict, Any

import frappe

from hrms.integrations.telegram_bot.aduan import telegram_aduan_bot
from hrms.integrations.telegram_bot import utils as telegram_utils

try:
    import telebot  # pyTelegramBotAPI
except ImportError:
    telebot = None



def _logger():
    return frappe.logger("telegram")


def _cache():
    return frappe.cache()


def _state_key(chat_id: int) -> str:
    return f"telegram_bot:state:{chat_id}"



def set_state(chat_id: int, state: str, attempts: int = 0, ttl: int = 900):
    import json
    data = json.dumps({"state": state, "attempts": attempts, "ts": int(time.time())})
    _cache().set_value(_state_key(chat_id), data, expires_in_sec=ttl)


def clear_state(chat_id: int):
    _cache().delete_value(_state_key(chat_id))


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
        raise RuntimeError("pyTelegramBotAPI is not installed. Jalankan: bench pip install pyTelegramBotAPI")
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
            types.BotCommand("start", "Show help"),
            types.BotCommand("link", "Link this private chat"),
            types.BotCommand("unlink", "Unlink this private chat"),
        ]

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

        bot.set_my_commands(private_commands, scope=types.BotCommandScopeAllPrivateChats())
        bot.set_my_commands(group_commands, scope=types.BotCommandScopeAllGroupChats())
        bot.set_my_commands(group_commands, scope=types.BotCommandScopeAllChatAdministrators())

    
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
                        cid = telegram_utils._coerce_int(rule.get("chat_id"))
                        if cid is not None:
                            ids.append(cid)
                if ids:
                    return sorted(list(set(ids)))

            ids = telegram_utils._coerce_int_list(frappe.conf.get("telegram_aduan_chat_ids"))
            if ids:
                return sorted(list(set(ids)))

            legacy = telegram_utils._coerce_int(frappe.conf.get("telegram_aduan_chat_id"))
            return [legacy] if legacy is not None else []

        # Also set commands for configured /aduan group(s) specifically (overrides any chat-specific settings)
        for chat_id in _aduan_chat_ids():
            try:
                bot.delete_my_commands(scope=types.BotCommandScopeChat(chat_id))
            except Exception:
                pass
            try:
                bot.delete_my_commands(scope=types.BotCommandScopeChatAdministrators(chat_id))
            except Exception:
                pass

            try:
                bot.set_my_commands(group_commands_for_configured_chat, scope=types.BotCommandScopeChat(chat_id))
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
        _logger().info(
            f"Telegram bot commands configured: private=/start,/link,/unlink; group (all)=<none>; group (configured chat(s))={configured_group_cmds}"
        )
        print(
            f"Telegram bot commands configured: private=/start,/link,/unlink; group (all)=<none>; group (configured chat(s))={configured_group_cmds}"
        )
        _debug_dump()

    except Exception as e:
        _logger().warning(f"set_my_commands failed (non-fatal): {e}")
        print(f"WARNING: set_my_commands failed (non-fatal): {e}")
        _debug_dump()


def _register_handlers(bot):
    nip_regex = re.compile(r"^NIP\s+(\d+)$", re.IGNORECASE)

    # Register group/topic handler(s) in a separate module
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
