import re
import threading
import time
from typing import Optional, Dict, Any

import frappe

from hrms.integrations.telegram_bot.aduan import telegram_aduan_bot

try:
    import telebot  # pyTelegramBotAPI
except ImportError:
    telebot = None


STATE_KEY_PREFIX = "telegram:state:"
STATE_AWAITING_NIP = "AWAITING_NIP"
MAX_NIP_ATTEMPTS = 3


def _logger():
    return frappe.logger("telegram")


def _cache():
    return frappe.cache()


def _state_key(chat_id: int) -> str:
    return f"{STATE_KEY_PREFIX}{chat_id}"


def get_state(chat_id: int) -> Optional[Dict[str, Any]]:
    raw = _cache().get_value(_state_key(chat_id))
    if not raw:
        return None
    try:
        if isinstance(raw, dict):
            return raw
        import json
        return json.loads(raw)
    except Exception:
        return None


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
    site = frappe.conf.get("default_site") or "frappe.revaldy"
    return site


def _find_employee_by_username(username: Optional[str]):
    if not username:
        return None
    # Strip leading @ if present
    username = username.lstrip("@")
    return frappe.db.get_value(
        "Employee", {"user_telegram": username, "status": "Active"}, "employee_name"
    )


def _find_employee_by_nip(nip: str):
    return frappe.db.get_value("Employee", {"nip": nip, "status": "Active"}, "employee_name")


def _is_linked(chat_id: int) -> Optional[str]:
    print(f"Checking link for chat_id={chat_id}")
    return frappe.db.get_value("Employee", {"telegram_chat_id": str(chat_id)}, "employee_name")


def _link_employee(employee_name: str, username:str, chat_id: int, method: str):
    frappe.db.set_value(
        "Employee",
        employee_name,
        {
            "user_telegram": username,
            "telegram_chat_id": str(chat_id),
            "telegram_linked_at": frappe.utils.now(),
            "telegram_link_method": method,
        },
    )
    frappe.db.commit()
    print(f"Linked chat_id={chat_id} employee={employee_name} via {method}")


def _unlink(chat_id: int):
    emp = _is_linked(chat_id)
    if not emp:
        return False
    frappe.db.set_value(
        "Employee", emp, {"telegram_chat_id": "", "telegram_link_method": "", "telegram_linked_at": ""}
    )
    frappe.db.commit()
    print(f"Unlinked chat_id={chat_id} employee={emp}")
    return True


def _welcome(bot, chat_id: int, employee_name: str):
    bot.send_message(
        chat_id,
        f"✅ Congratulations you're linked as: {employee_name}\nYou'll receive task notifications, have a nice day mate!",
    )


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
            types.BotCommand("aduan", "Create SubTask from complaint"),
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

        # Also set commands for the configured /aduan group specifically (overrides any chat-specific settings)
        try:
            chat_id = frappe.conf.get("telegram_aduan_chat_id")
            chat_id = int(chat_id) if chat_id not in (None, "") else None
        except Exception:
            chat_id = None

        if chat_id is not None:
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

        _logger().info(
            "Telegram bot commands configured: private=/start,/link,/unlink; group (all)=<none>; group (configured chat)=/aduan"
        )
        print(
            "Telegram bot commands configured: private=/start,/link,/unlink; group (all)=<none>; group (configured chat)=/aduan"
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

    @bot.message_handler(commands=["start"])
    def handle_start(message):
        if getattr(message.chat, "type", None) != "private":
            return
        chat_id = message.chat.id
        username = message.from_user.username
        print(f"Username telegram: {username} chat_id: {chat_id}")
        bot.send_message(
            chat_id,
            f"Hello {username} \n- /link for connecting this chat to task management system\n- /unlink for disconnecting",
        )

    @bot.message_handler(commands=["link"])
    def handle_link(message):
        if getattr(message.chat, "type", None) != "private":
            return
        chat_id = message.chat.id
        username = message.from_user.username
        print(f"Username telegram: {username} chat_id: {chat_id}")
        # Already linked?
        emp = _is_linked(chat_id)
        if emp:
            print(f"Chat {chat_id} already linked to employee {emp}")
            bot.send_message(chat_id, f"⚠️ This chat was linked, have a nice day {username}!")
            return
        employee_name = _find_employee_by_username(username)
        print(f"Attempting link via USERNAME={username} found employee={employee_name}")
        if employee_name:
            _link_employee(employee_name, username, chat_id, "USERNAME")
            _welcome(bot, chat_id, employee_name)
        else:
            set_state(chat_id, STATE_AWAITING_NIP, attempts=0)
            bot.send_message(chat_id, "Send me your NIP with this format:\nNIP <number>")

    @bot.message_handler(commands=["unlink"])
    def handle_unlink(message):
        if getattr(message.chat, "type", None) != "private":
            return
        chat_id = message.chat.id
        username = message.from_user.username
        if _unlink(chat_id):
            bot.send_message(chat_id, f"✅ Success unlink your chat.\nHave a nice day {username}!")
        else:
            bot.send_message(chat_id, "⚠️ No active link for this chat mate!")

    @bot.message_handler(func=lambda m: True)
    def handle_any(message):
        # Only handle private chat messages for link state-machine.
        # Group/topic messages are handled by dedicated modules.
        if getattr(message.chat, "type", None) != "private":
            return
        chat_id = message.chat.id
        username = message.from_user.username
        text = (message.text or "").strip()
        state = get_state(chat_id)

        # Check NIP flow
        if state and state.get("state") == STATE_AWAITING_NIP:
            m_nip = nip_regex.match(text)
            if m_nip:
                nip_value = m_nip.group(1)
                employee_name = _find_employee_by_nip(nip_value)
                print(f"{username} attempting link via NIP={nip_value} found employee={employee_name}")
                if employee_name:
                    _link_employee(employee_name, username, chat_id, "NIP")
                    clear_state(chat_id)
                    _welcome(bot, chat_id, employee_name)
                    return
                else:
                    attempts = state.get("attempts", 0) + 1
                    if attempts < MAX_NIP_ATTEMPTS:
                        set_state(chat_id, STATE_AWAITING_NIP, attempts=attempts)
                        bot.send_message(
                            chat_id,
                            f"NIP isn't found. Try again mate! ({attempts}/{MAX_NIP_ATTEMPTS}).\nSend me your NIP with this format:\nNIP <number>",
                        )
                    else:
                        clear_state(chat_id)
                        bot.send_message(
                            chat_id,
                            "You have reached your limits mate.\nContact admin for some help."
                        )
                    return
            else:
                # Has state but message not NIP pattern
                bot.send_message(chat_id, "Wrong format mate. Please use this format:\nNIP <number>")
                return

        # No active state
        if _is_linked(chat_id):
            bot.send_message(chat_id, "Linked. Use /unlink for disconnecting.")
        else:
            bot.send_message(chat_id, "Unlinked. Send /start then /link for connecting.")


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


def link_status(chat_id: int) -> Dict[str, Any]:
    """Utility function to inspect link status for debugging."""
    emp = _is_linked(chat_id)
    state = get_state(chat_id)
    return {"employee": emp, "state": state}
