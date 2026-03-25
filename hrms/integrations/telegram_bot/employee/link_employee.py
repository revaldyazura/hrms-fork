"""Logic untuk command /link_employee.

Menghubungkan akun Telegram pengirim dengan data Employee berdasarkan NIP
yang diberikan. Menyimpan username, chat_id, waktu link, dan metode link.
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from hrms.integrations.telegram_bot.utils import helper

import frappe

if TYPE_CHECKING:
    pass

default_link_employee_command = "/link_employee"

def link_username_to_employee_data(message) -> None:
    """Tangani perintah /link_employee <NIP> dari private chat.

    Args:
        bot: instance TeleBot.
        message: objek Message dari pyTelegramBotAPI.
        send_fn: callable(chat_id, text, parse_mode) untuk mengirim pesan.
        response_text_fn: callable(key, default) untuk membaca template dari config.
        render_fn: callable(key, default, context) untuk merender template.
    """
    chat_id: int = message.chat.id
    username = helper._telegram_user_label(message)

    if not username:
        text = helper._render_response_text(
            "link_employee_no_username",
            "❌ Username Telegram Anda tidak ditemukan. Silakan aktifkan username di pengaturan Telegram.",
        )
        return text

    username = username.lstrip("@")  # simpan tanpa '@' untuk konsistensi
    # Ambil NIP dari payload pesan (teks setelah command)
    raw_text: str = message.text or ""
    parts = raw_text.strip().split(None, 1)  # split command dan sisa
    nip_input: str = parts[1].strip() if len(parts) > 1 else ""

    if not nip_input:
        text = helper._render_response_text(
            "link_employee_format",
            (
                "ℹ️ Format perintah:\n"
                "<code>{link_cmd} NIP</code>\n"
                "Contoh: <code>{link_cmd} 1234567890</code>"
            ),
            {"link_cmd": default_link_employee_command},
        )
        return text

    # Cari Employee berdasarkan NIP
    employees = frappe.get_all(
        "Employee",
        filters={"nip": nip_input},
        fields=["name", "employee_name", "nip", "user_telegram", "telegram_chat_id"],
        limit=1,
    )

    if not employees:
        text = helper._render_response_text(
            "link_employee_not_found",
            "❌ NIP <code>{nip}</code> tidak ditemukan dalam data pegawai.",
            {"nip": nip_input},
        )
        
        return text

    emp = employees[0]
    emp_doc_name: str = emp.get("name")
    emp_name: str = emp.get("employee_name") or emp_doc_name
    existing_tg: str | None = emp.get("user_telegram") or None

    # Jika sudah terhubung ke username yang berbeda, tolak
    if existing_tg and existing_tg.lower() != username.lower():
        text = helper._render_response_text(
            "link_employee_already_linked",
            (
                "❌ NIP <code>{nip}</code> sudah terhubung dengan akun Telegram lain.\n"
                "Silakan hubungi administrator jika ingin melepas tautan yang ada."
            ),
            {"nip": nip_input},
        )
        
        return text

    # Simpan data ke Employee
    try:
        doc = frappe.get_doc("Employee", emp_doc_name)
        doc.user_telegram = username
        doc.telegram_chat_id = str(chat_id)
        doc.telegram_linked_at = datetime.now()
        doc.telegram_link_method = "Telegram Command"
        doc.save(ignore_permissions=True)
        frappe.db.commit()
    except Exception as e:
        frappe.logger("telegram").error(
            f"link_employee: gagal simpan untuk {emp_doc_name}: {e}"
        )
        text = helper._render_response_text(
            "link_employee_save_error",
            "❌ Gagal menyimpan data. Silakan coba lagi atau hubungi administrator.",
            {},
        )
        
        return text

    nip_display: str = emp.get("nip") or nip_input
    text = helper._render_response_text(
        "link_employee_success",
        (
            "✅ Akun Telegram <b>@{username}</b> berhasil dihubungkan!\n\n"
            "Nama  : <b>{employee_name}</b>\n"
            "NIP   : <code>{nip}</code>"
        ),
        {"username": username, "employee_name": emp_name, "nip": nip_display},
    )
    return text



