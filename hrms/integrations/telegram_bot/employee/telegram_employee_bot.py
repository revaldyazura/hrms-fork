"""Modul utama bot Telegram untuk fitur Employee HRIS.

Menyediakan:
- Helper konfigurasi response teks dari site config (telegram_employee_response_texts).
- Helper daftar perintah menu private dari config (telegram_employee_private_command).
- Registrasi handler /cek_biodata dan /link_employee.
"""

from __future__ import annotations

from typing import Optional, List, Tuple

import frappe
import json
from hrms.integrations.telegram_bot.utils import helper
from hrms.integrations.telegram_bot.employee import cek_biodata
from hrms.integrations.telegram_bot.employee import link_employee
from hrms.integrations.telegram_bot import telebot_listener as telegram_listener


# ---------------------------------------------------------------------------
# Menu commands helper (dibaca dari config)
# ---------------------------------------------------------------------------

_DEFAULT_EMPLOYEE_MENU: list[tuple[str, str]] = [
    ("/cek_biodata", "Cek data biodata pegawai"),
    ("/link_employee", "Link akun Telegram dengan data pegawai"),
]


def _employee_command_map() -> dict[str, str]:
    """Return configured employee command map.

    Source:
    - telegram_employee_private_command (optional)

    Fallback:
    - `_DEFAULT_EMPLOYEE_MENU`
    """

    default_map = {cmd: desc for cmd, desc in _DEFAULT_EMPLOYEE_MENU if cmd}
    return helper.conf_command_map(
        "telegram_employee_private_command",
        default=default_map,
    )


def _employee_command_tokens() -> list[str]:
    return list(_employee_command_map().keys())


def employee_menu_commands() -> List[Tuple[str, str]]:
    """Kembalikan daftar (command, description) untuk ditampilkan di menu private chat.

    Dibaca dari ``telegram_employee_private_command`` di site config.
    Fallback ke daftar default jika config tidak ada.
    """
    # Keep output tokens with leading '/' (as historically returned by this module)
    return helper.menu_commands_from_map(_employee_command_map(), strip_slash=True)


def _employee_help_text_map() -> dict[str, str]:
    """Return normalized help text map keyed by command token.

    Config (optional): telegram_employee_help_texts
    Accepts:
    - dict (or JSON string of dict): {"/employee": "...", "employee_info": "..."}
    - list (or JSON string of list) aligned with telegram_employee_command tokens

    Notes:
    - Keys may be with or without leading '/'.
    - Values may include '{cmd}' which will be replaced at runtime.
    """
    default_cmd = (_employee_command_tokens() or ["/cek_biodata"])[0]
    return helper.conf_help_text_map(
        "telegram_employee_help_texts",
        command_tokens=_employee_command_tokens(),
        default_command=default_cmd,
    )


# ---------------------------------------------------------------------------
# Handler registration
# ---------------------------------------------------------------------------


def register_handlers(bot):
    """Daftarkan handler /cek_biodata dan /link_employee ke instance bot."""

    @bot.message_handler(commands=["cek_biodata"])
    def handle_cek_biodata(message):
        print("Handling /cek_biodata for chat_id:", message.chat.id)
        if getattr(message.chat, "type", None) != "private":
            return
        try:
            helper.ensure_db_connection()
        except Exception:
            pass

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
        print("Handling /cek_biodata for chat_id:", message.chat.id)
        res = cek_biodata.cek_data_employee(message=message)
        telegram_listener._send(bot, message.chat.id, res, parse_mode="HTML")

    @bot.message_handler(commands=["link_employee"])
    def handle_link(message):
        if getattr(message.chat, "type", None) != "private":
            return
        try:
            helper.ensure_db_connection()
        except Exception:
            pass

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
        res = link_employee.link_username_to_employee_data(message=message)
        telegram_listener._send(bot, message.chat.id, res, parse_mode="HTML")
