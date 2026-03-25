"""Logic untuk command /cek_biodata.

Memeriksa apakah pengirim sudah terhubung dengan data Employee berdasarkan
field `user_telegram`. Jika belum, mengembalikan panduan /link_employee.
Jika sudah, mengembalikan nama dan NIP, serta menyimpan chat_id bila perlu.
"""
from __future__ import annotations

from typing import TYPE_CHECKING
from hrms.integrations.telegram_bot.utils import helper
from hrms.integrations.telegram_bot.employee import link_employee

import frappe

if TYPE_CHECKING:
    pass

default_cek_biodata_command = "/cek_biodata"

def cek_data_employee(message) -> None:
    """Tangani perintah /cek_biodata dari private chat.

    Args:
        bot: instance TeleBot.
        message: objek Message dari pyTelegramBotAPI.
        send_fn: callable(chat_id, text, parse_mode) untuk mengirim pesan.
        response_text_fn: callable(key, default) untuk membaca template dari config.
        render_fn: callable(key, default, context) untuk merender template.
    """
    chat_id: int = message.chat.id
    username: str | None = getattr(message.from_user, "username", None)

    if not username:
        
        text = helper._render_response_text(
            "cek_biodata_no_username",
            "❌ Username Telegram Anda tidak ditemukan. Silakan aktifkan username di pengaturan Telegram.",
            {}
        )
        return text

    # Cari Employee berdasarkan user_telegram (case-insensitive di level python agar cross-DB)
    employees = frappe.get_all(
        "Employee",
        filters={"user_telegram": username},
        fields=["name", "employee_name", "nip", "telegram_chat_id"],
        limit=1,
    )

    if not employees:
        # Belum terhubung — tampilkan panduan /link_employee
        text = helper._render_response_text(
            "cek_biodata_not_found",
            (
                "❌ Data pegawai dengan username Telegram <b>@{username}</b> tidak ditemukan.\n\n"
                "Silakan hubungkan akun Anda terlebih dahulu dengan perintah:\n"
                "<code>{link_cmd} NIP</code>\n"
                "Contoh: <code>{link_cmd} 1234567890</code>"
            ),
            {"username": username, "link_cmd": link_employee.default_link_employee_command},
        )
        return text

    emp = employees[0]
    emp_name: str = emp.get("employee_name") or emp.get("name")
    nip: str = emp.get("nip") or "-"
    emp_doc_name: str = emp.get("name")

    # Simpan / perbarui telegram_chat_id jika belum ada atau berbeda
    existing_chat_id = emp.get("telegram_chat_id")
    try:
        stored = int(existing_chat_id) if existing_chat_id not in (None, "", 0) else None
    except (ValueError, TypeError):
        stored = None

    if stored != chat_id:
        try:
            doc = frappe.get_doc("Employee", emp_doc_name)
            doc.telegram_chat_id = str(chat_id)
            doc.save(ignore_permissions=True)
            frappe.db.commit()
        except Exception as e:
            frappe.logger("telegram").warning(
                f"cek_biodata: gagal simpan telegram_chat_id untuk {emp_doc_name}: {e}"
            )

    text = helper._render_response_text(
        "cek_biodata_found",
        (
            "✅ Data pegawai ditemukan!\n\n"
            "Nama  : <b>{employee_name}</b>\n"
            "NIP   : <code>{nip}</code>"
        ),
        {"employee_name": emp_name, "nip": nip},
    )
    return text



