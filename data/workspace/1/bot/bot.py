import asyncio
import logging
import html
import random
import string
import datetime
import aiohttp
from typing import Optional, Dict, Any, List
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, BotCommand, MenuButtonCommands, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession

class CustomAiohttpSession(AiohttpSession):
    """Custom session with ThreadedResolver to prevent Windows DNS resolution errors."""
    async def create_session(self) -> aiohttp.ClientSession:
        if self._should_reset_connector:
            await self.close()
        if self._session is None or self._session.closed:
            self._connector_init["resolver"] = aiohttp.ThreadedResolver()
            self._session = aiohttp.ClientSession(
                connector=self._connector_type(**self._connector_init),
                json_serialize=self.json_dumps
            )
            self._should_reset_connector = False
        return self._session

import socket
import sys
import aiosqlite

_single_instance_socket = None

def ensure_single_instance(port: int = 49512):
    global _single_instance_socket
    _single_instance_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        _single_instance_socket.bind(('127.0.0.1', port))
    except OSError:
        logging.getLogger(__name__).warning(f"Another instance of bot.py is already running on port {port}! Exiting cleanly.")
        sys.exit(0)
from config import (
    BOT_TOKEN,
    ADMIN_IDS,
    BOT_USERNAME,
    START_CREDITS,
    CREDITS_PER_REFERRAL,
    START_MAIL_QUOTA,
    MAILS_PER_CREDIT,
    POLL_INTERVAL,
    DB_PATH
)
from mail_service import mail_service
from database import (
    init_db,
    get_user,
    get_or_create_user,
    consume_user_credit,
    claim_mails_with_credits,
    add_user_credits,
    save_user_email,
    delete_user_email,
    get_admin_stats,
    get_all_user_ids,
    set_user_ban,
    add_force_channel,
    remove_force_channel,
    get_force_channels,
    set_user_theme,
    get_user_theme,
    get_button_emojis,
    set_button_emoji,
    reset_all_button_emojis,
    get_button_colors,
    set_button_color,
    reset_all_button_colors,
    get_button_texts,
    set_button_text,
    reset_all_button_texts,
    confirm_pending_referral,
    BUTTON_NAMES,
    BUTTON_CATEGORIES,
    get_referral_leaderboard,
    get_user_referral_rank,
    update_user_username,
    create_redeem_code,
    get_redeem_code,
    get_all_redeem_codes,
    delete_redeem_code,
    redeem_code_for_user,
    get_recent_received_messages,
    get_user_received_messages,
    get_total_received_messages_count,
    get_received_message_by_id
)
from extractor import (
    extract_sender_info,
    extract_otp,
    extract_verification_link,
    clean_text_content
)
from keyboards import (
    get_main_keyboard,
    get_profile_keyboard,
    get_referral_keyboard,
    get_leaderboard_keyboard,
    get_no_credits_keyboard,
    get_admin_keyboard,
    get_admin_all_mails_keyboard,
    get_cancel_broadcast_keyboard,
    get_full_mail_keyboard,
    get_mail_alert_keyboard,
    get_force_sub_keyboard,
    get_admin_channels_keyboard,
    get_remove_channel_keyboard,
    get_cancel_add_channel_keyboard,
    get_admin_redeem_keyboard,
    get_cancel_redeem_keyboard,
    get_delete_redeem_list_keyboard,
    make_btn,
    get_btn_emoji,
    get_btn_color,
    get_btn_text,
    update_button_emojis_cache,
    reset_button_emojis_cache,
    update_button_colors_cache,
    reset_button_colors_cache,
    update_button_texts_cache,
    reset_button_texts_cache,
    get_admin_btn_categories_keyboard,
    get_admin_category_buttons_keyboard,
    get_cancel_edit_emoji_keyboard,
    get_confirm_reset_emojis_keyboard,
    get_admin_btn_colors_categories_keyboard,
    get_admin_colors_buttons_keyboard,
    get_confirm_reset_colors_keyboard,
    get_admin_btn_texts_categories_keyboard,
    get_admin_texts_buttons_keyboard,
    get_cancel_edit_text_keyboard,
    get_confirm_reset_texts_keyboard
)
from premium_emojis import pe
from watcher import run_inbox_watcher

# Disable all live logging completely to prevent volume/disk space from filling up on hosting
logging.disable(logging.CRITICAL)
logging.basicConfig(handlers=[logging.NullHandler()], level=logging.CRITICAL)
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

# Suppress all library loggers completely
for log_name in ["aiogram", "aiogram.event", "aiogram.dispatcher", "aiogram.middlewares", "aiohttp", "aiohttp.access", "aiohttp.client", "asyncio", "urllib3"]:
    logging.getLogger(log_name).setLevel(logging.CRITICAL)
    logging.getLogger(log_name).addHandler(logging.NullHandler())

dp = Dispatcher()

# In-memory states for admin prompts & user flows
ADMIN_BROADCAST_STATE = set()
ADMIN_ADD_FSUB_STATE = set()
ADMIN_SEARCH_USER_MAILS_STATE = set()
ADMIN_EDIT_BTN_STATE: Dict[int, str] = {}
ADMIN_EDIT_TEXT_STATE: Dict[int, str] = {}
USER_REDEEM_STATE = set()
ADMIN_CREATE_REDEEM_STATE: Dict[int, Dict[str, Any]] = {}

def clear_user_states(user_id: int):
    """Clear all pending interactive text prompt states for a user to prevent state pollution & cross-talk."""
    USER_REDEEM_STATE.discard(user_id)
    ADMIN_CREATE_REDEEM_STATE.pop(user_id, None)
    ADMIN_BROADCAST_STATE.discard(user_id)
    ADMIN_ADD_FSUB_STATE.discard(user_id)
    ADMIN_SEARCH_USER_MAILS_STATE.discard(user_id)
    ADMIN_EDIT_BTN_STATE.pop(user_id, None)
    ADMIN_EDIT_TEXT_STATE.pop(user_id, None)

def to_math_bold(text: str) -> str:
    """Convert ASCII letters and digits into Mathematical Bold Serif Unicode characters."""
    out = []
    for ch in text:
        o = ord(ch)
        if 65 <= o <= 90:      # A-Z
            out.append(chr(0x1D400 + (o - 65)))
        elif 97 <= o <= 122:   # a-z
            out.append(chr(0x1D41A + (o - 97)))
        elif 48 <= o <= 57:    # 0-9
            out.append(chr(0x1D7CE + (o - 48)))
        else:
            out.append(ch)
    return "".join(out)

async def ensure_fsub(event: Any, bot: Bot) -> bool:
    """Verify if user is a member of all required force-sub channels (Matches Image 1). Admins bypass."""
    user_id = event.from_user.id
    if user_id in ADMIN_IDS:
        return True

    channels = await get_force_channels()
    if not channels:
        return True

    unjoined = []
    for ch in channels:
        try:
            member = await bot.get_chat_member(chat_id=ch["chat_id"], user_id=user_id)
            if member.status in ["left", "kicked"]:
                unjoined.append(ch)
        except Exception as e:
            logger.info(f"FSub check failed for user {user_id} in {ch['chat_id']}: {e}")
            unjoined.append(ch)

    if not unjoined:
        return True

    bullet_list = "\n".join([f"• <b>{html.escape(ch.get('title') or ch.get('chat_id'))}</b>" for ch in unjoined])
    v_btn_text = get_btn_text("fsub_verify", "I have joined all")
    text = (
        f"{pe('access_restricted')} <b>Access restricted</b>\n\n"
        f"Bot commands use karne se pehle in required channels/groups ko join karein:\n\n"
        f"{bullet_list}\n\n"
        f"Join karne ke baad <b>{html.escape(v_btn_text)}</b> par click karein."
    )
    kb = get_force_sub_keyboard(unjoined)

    if isinstance(event, CallbackQuery):
        try:
            await event.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=kb, disable_web_page_preview=True)
        except Exception:
            await event.message.answer(text, parse_mode=ParseMode.HTML, reply_markup=kb, disable_web_page_preview=True)
    else:
        await event.answer(text, parse_mode=ParseMode.HTML, reply_markup=kb, disable_web_page_preview=True)

    return False


@dp.message(CommandStart())
async def cmd_start(message: Message, bot: Bot):
    """Handle /start command with referral link support."""
    user_id = message.from_user.id
    clear_user_states(user_id)
    user_name = message.from_user.first_name or "Friend"
    is_admin = user_id in ADMIN_IDS

    # Parse potential referral ID: e.g. /start ref_123456
    referrer_id = None
    args = message.text.split()
    if len(args) > 1 and args[1].startswith("ref_"):
        ref_str = args[1].replace("ref_", "").strip()
        if ref_str.isdigit():
            referrer_id = int(ref_str)

    # Get or create user record
    user_data = await get_or_create_user(user_id, referrer_id)
    if user_data.get("is_banned"):
        await message.answer(f"{pe('cross')} Your account has been suspended on this bot.")
        return

    # Notify referrer if this is a brand new referral (Stage 1: Referral Detected - matches Image 2)
    if user_data.get("is_new_referral") and user_data.get("actual_referrer"):
        ref_id = user_data["actual_referrer"]
        try:
            ref_text_1 = (
                f"{pe('5372865660500067203')} <b>Rᴀᴏᴇʀʀᴀʟ Dᴇᴛᴇᴄᴛᴇᴅ</b>\n\n"
                f"{pe('5256143829672672750')} <b>Nᴀᴍᴇ :- </b>{html.escape(user_name)}\n\n"
                f"{pe('5271604874419647061')} <b>A ᴜsᴇʀ ᴊᴏɪɴᴇᴅ ᴠɪᴀ ʏᴏᴜʀ ʟɪɴᴋ. Wᴀɪᴛɪɴɢ ғᴏʀ ᴄʟᴀɴɴᴇʟ ᴠᴇʀɪғɪᴄᴀᴛɪᴏɴ...</b>"
            )
            await bot.send_message(chat_id=ref_id, text=ref_text_1, parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.warning(f"Could not notify referrer {ref_id} of referral detected: {e}")

    # Ensure Force Join membership before proceeding to bot
    if not await ensure_fsub(message, bot):
        return

    # If user immediately passed force sub (e.g. no channels or already joined), confirm referral (Stage 2)
    confirmed = await confirm_pending_referral(user_id)
    if confirmed:
        try:
            ref_text_2 = (
                f"{pe('5258079378159453410')} <b>Rᴀᴏᴇʀʀᴀʟ Cᴏɴғɪʀᴍᴇᴅ</b>\n\n"
                f"{pe('5256143829672672750')} <b>Nᴀᴍᴇ :- </b>{html.escape(user_name)}\n\n"
                f"{pe('5353057756662210233')} <b>Bᴏɴᴜs: +1 ᴄʀᴇᴅɪᴛ ᴀᴅᴅᴇᴅ ᴛᴏ ʏᴏᴜʀ ᴀᴄᴄᴏᴜɴᴛ!</b>"
            )
            await bot.send_message(chat_id=confirmed["user_id"], text=ref_text_2, parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.warning(f"Could not notify referrer of confirmed referral: {e}")

    credits = user_data.get("credits", START_CREDITS)
    mail_quota = user_data.get("mail_quota", START_MAIL_QUOTA)
    quota_str = "Unlimited" if is_admin else f"{mail_quota} Mails"
    credits_str = "Unlimited" if is_admin else f"{credits} Credits"

    if user_data and user_data.get("email"):
        email = user_data["email"]
        domain = user_data.get("domain", "olipii.com")
        text = (
            f"{pe('5436145964882606058')} Welcome <b>{html.escape(user_name)}</b>! {pe('5208748315805499400')}\n\n"
            f"{pe('5472239203590888751')} <b>Your Active Temp Email:</b>\n"
            f"{pe('5415758949129404605')} <code>{email}</code> <i>(Tap to copy)</i>\n\n"
            f"{pe('5447410659077661506')} <b>Domain:</b> <code>@{domain}</code>\n"
            f"{pe('6046322897654387087')} <b>Auto OTP Detection:</b> {pe('6233111867171018062')} Active!\n"
            f"{pe('6233111867171018062')} <b>Available Mails:</b> <code>{quota_str}</code>\n"
            f"{pe('5287231198098117669')} <b>Credits Balance:</b> <code>{credits_str}</code> <i>(1 Credit = 1 Mail)</i>\n\n"
            f"{pe('5312361253610475399')} <i>To generate a new email, click '{pe('5341463333532882949')} New Email' below!</i>"
        )
        await message.answer(text, parse_mode=ParseMode.HTML, reply_markup=get_main_keyboard(has_email=True, is_admin=is_admin))
    else:
        text = (
            f"{pe('5436145964882606058')} Welcome <b>{html.escape(user_name)}</b>! {pe('5208748315805499400')}\n\n"
            f"{pe('6129873536413605540')} Welcome to <b>Temp Mail & Instant OTP Bot</b>! {pe('6129792056589031358')}\n\n"
            f"{pe('5379668527919684482')} <b>Premium Features:</b>\n"
            f"• {pe('6129432481927010933')} Clean & Realistic usernames (Never rejected by websites)\n"
            f"• {pe('5447410659077661506')} Automatic Domain Rotation (Fresh domain each time)\n"
            f"• {pe('5341463333532882949')} Instant OTP & Verification Link detection\n"
            f"• {pe('6129479035077531636')} Auto Color-Changing Buttons\n"
            f"• {pe('5454371323595744068')} 1 Referral = 1 Credit (= 1 Email Claim!)\n\n"
            f"{pe('6233111867171018062')} <b>Available Mails:</b> <code>{quota_str}</code>\n"
            f"{pe('5287231198098117669')} <b>Credits Balance:</b> <code>{credits_str}</code> <i>(1 Credit = 1 Mail)</i>\n\n"
            f"Click the button below to generate your temporary email {pe('6339166816006312740')}"
        )
        await message.answer(text, parse_mode=ParseMode.HTML, reply_markup=get_main_keyboard(has_email=False, is_admin=is_admin))

@dp.message(Command("new"))
async def cmd_new(message: Message, bot: Bot):
    """Command /new [optional_custom_name] to generate a new temp email."""
    clear_user_states(message.from_user.id)
    if not await ensure_fsub(message, bot):
        return
    parts = message.text.strip().split()
    custom_name = parts[1].strip() if len(parts) > 1 else None
    await create_new_email(message.from_user.id, message, custom_name=custom_name)

@dp.callback_query(F.data == "new_email")
async def cb_new_email(callback: CallbackQuery, bot: Bot):
    """Callback to generate a new temp email with auto-changed domain."""
    clear_user_states(callback.from_user.id)
    if not await ensure_fsub(callback, bot):
        return
    await callback.answer("Generating new email...")
    await create_new_email(callback.from_user.id, callback.message, is_callback=True)

@dp.callback_query(F.data == "back_to_main")
async def cb_back_to_main(callback: CallbackQuery):
    """Return to main dashboard."""
    clear_user_states(callback.from_user.id)
    await callback.answer()
    user_id = callback.from_user.id
    is_admin = user_id in ADMIN_IDS
    user_data = await get_user(user_id)
    credits = user_data.get("credits", START_CREDITS) if user_data else START_CREDITS
    mail_quota = user_data.get("mail_quota", START_MAIL_QUOTA) if user_data else START_MAIL_QUOTA
    quota_str = "Unlimited" if is_admin else f"{mail_quota} Mails"
    credits_str = "Unlimited" if is_admin else f"{credits} Credits"

    if user_data and user_data.get("email"):
        email = user_data["email"]
        domain = user_data.get("domain", "olipii.com")
        text = (
            f"{pe('5472239203590888751')} <b>Your Active Temp Email:</b>\n"
            f"{pe('5415758949129404605')} <code>{email}</code> <i>(Tap to copy)</i>\n\n"
            f"{pe('5447410659077661506')} <b>Domain:</b> <code>@{domain}</code>\n"
            f"{pe('6046322897654387087')} <b>Auto OTP Detection:</b> {pe('6233111867171018062')} Active!\n"
            f"{pe('6233111867171018062')} <b>Available Mails:</b> <code>{quota_str}</code>\n"
            f"{pe('5287231198098117669')} <b>Credits Balance:</b> <code>{credits_str}</code> <i>(1 Credit = 1 Mail)</i>\n\n"
            f"{pe('5312361253610475399')} <i>To generate a new email, click '{pe('5341463333532882949')} New Email' below!</i>"
        )
        await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=get_main_keyboard(has_email=True, is_admin=is_admin))
    else:
        text = (
            f"Click the button below to generate a new temporary email {pe('6339166816006312740')}\n\n"
            f"{pe('6233111867171018062')} <b>Available Mails:</b> <code>{quota_str}</code>\n"
            f"{pe('5287231198098117669')} <b>Credits Balance:</b> <code>{credits_str}</code> <i>(1 Credit = 1 Mail)</i>"
        )
        await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=get_main_keyboard(has_email=False, is_admin=is_admin))

@dp.callback_query(F.data == "check_fsub")
async def cb_check_fsub(callback: CallbackQuery, bot: Bot):
    """Verify channel/group membership."""
    user_id = callback.from_user.id
    channels = await get_force_channels()
    unjoined = []
    for ch in channels:
        try:
            member = await bot.get_chat_member(chat_id=ch["chat_id"], user_id=user_id)
            if member.status in ["left", "kicked"]:
                unjoined.append(ch)
        except Exception:
            unjoined.append(ch)

    if unjoined:
        await callback.answer(f"⚠️ You haven't joined all required channels/groups yet! Please join first.", show_alert=True)
        return

    # If this user had a pending referral, confirm it and notify referrer (Stage 2: Referral Confirmed - matches Image 2)
    confirmed = await confirm_pending_referral(user_id)
    if confirmed:
        try:
            ref_user_name = callback.from_user.first_name or "Friend"
            ref_text_2 = (
                f"{pe('5258079378159453410')} <b>Rᴀᴏᴇʀʀᴀʟ Cᴏɴғɪʀᴍᴇᴅ</b>\n\n"
                f"{pe('5256143829672672750')} <b>Nᴀᴍᴇ :- </b>{html.escape(ref_user_name)}\n\n"
                f"{pe('5353057756662210233')} <b>Bᴏɴᴜs: +1 ᴄʀᴇᴅɪᴛ ᴀᴅᴅᴇᴅ ᴛᴏ ʏᴏᴜʀ ᴀᴄᴄᴏᴜɴᴛ!</b>"
            )
            await bot.send_message(chat_id=confirmed["user_id"], text=ref_text_2, parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.warning(f"Could not notify referrer of confirmed referral: {e}")

    await callback.answer("🎉 Verified! Your membership has been confirmed.", show_alert=True)
    await cb_back_to_main(callback)

# ============================================
# USER PROFILE & BALANCE HANDLERS
# ============================================

@dp.message(Command("profile"))
@dp.message(Command("balance"))
async def cmd_profile(message: Message, bot: Bot):
    """Show user profile and credits/mail balance."""
    clear_user_states(message.from_user.id)
    if not await ensure_fsub(message, bot):
        return
    await show_profile_panel(message.from_user.id, message)

@dp.callback_query(F.data == "show_profile")
async def cb_show_profile(callback: CallbackQuery, bot: Bot):
    """Callback to show profile & balance."""
    clear_user_states(callback.from_user.id)
    if not await ensure_fsub(callback, bot):
        return
    await callback.answer()
    await show_profile_panel(callback.from_user.id, callback.message, is_callback=True)

async def show_profile_panel(user_id: int, target: Message, is_callback: bool = False):
    """Display user profile showing only balance and total emails created."""
    user_data = await get_or_create_user(user_id)
    is_admin = user_id in ADMIN_IDS
    credits = user_data.get("credits", 0)
    total_created = user_data.get("total_emails_created", 0)

    admin_tag = f" {pe('crown')} (Admin)" if is_admin else ""
    credits_str = "Unlimited" if is_admin else f"{credits} Credits"

    text = (
        f"{pe('6086639764251873025')} <b>Profile & Balance{admin_tag}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{pe('5287231198098117669')} <b>Credits Balance:</b> <code>{credits_str}</code> <i>(1 Credit = 1 Mail)</i>\n"
        f"{pe('6057790228406470570')} <b>Total Emails Created:</b> <code>{total_created}</code>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━"
    )

    keyboard = get_profile_keyboard(credits=credits)
    if is_callback:
        try:
            await target.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
        except Exception:
            await target.answer(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
    else:
        await target.answer(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)

@dp.message(Command("claim"))
async def cmd_claim(message: Message, bot: Bot):
    """Command to claim 1 mail for 1 credit."""
    clear_user_states(message.from_user.id)
    if not await ensure_fsub(message, bot):
        return
    await execute_mail_claim(message.from_user.id, message)

@dp.callback_query(F.data == "claim_mails")
async def cb_claim_mails(callback: CallbackQuery, bot: Bot):
    """Callback to claim 1 mail using 1 credit."""
    clear_user_states(callback.from_user.id)
    if not await ensure_fsub(callback, bot):
        return
    await execute_mail_claim(callback.from_user.id, callback.message, callback=callback)

async def execute_mail_claim(user_id: int, target: Message, callback: Optional[CallbackQuery] = None):
    """Process credit to mail claiming."""
    res = await claim_mails_with_credits(user_id, 1)
    if not res["success"]:
        err_msg = res.get("error", "Insufficient credits!")
        if callback:
            await callback.answer(f"⚠️ {err_msg}", show_alert=True)
        else:
            await target.reply(f"{pe('warning')} {err_msg}")
        return

    alert_text = (
        f"{pe('party')} <b>Success! 1 New Email Claimed!</b> {pe('fire')}\n\n"
        f"• {pe('card')} Used: <code>1 Credit</code>\n"
        f"• {pe('email')} Added: <code>+1 Email</code> {pe('verified')}\n"
        f"• {pe('moneybag')} New Balance: <code>{res['new_credits']} Credits</code>"
    )
    if callback:
        await callback.answer("🎉 1 Email Claimed Successfully!", show_alert=True)
        await show_profile_panel(user_id, target, is_callback=True)
    else:
        await target.reply(alert_text, parse_mode=ParseMode.HTML)



# ============================================
# REFERRAL SYSTEM HANDLERS
# ============================================

@dp.message(Command("refer"))
async def cmd_refer(message: Message, bot: Bot):
    """Show referral link and stats."""
    clear_user_states(message.from_user.id)
    if not await ensure_fsub(message, bot):
        return
    if message.from_user.username:
        asyncio.create_task(update_user_username(message.from_user.id, message.from_user.username))
    await show_referral_panel(message.from_user.id, message)

@dp.callback_query(F.data == "refer_earn")
async def cb_refer_earn(callback: CallbackQuery, bot: Bot):
    """Callback to show referral panel."""
    clear_user_states(callback.from_user.id)
    if not await ensure_fsub(callback, bot):
        return
    if callback.from_user.username:
        asyncio.create_task(update_user_username(callback.from_user.id, callback.from_user.username))
    await callback.answer()
    await show_referral_panel(callback.from_user.id, callback.message, is_callback=True)

async def show_referral_panel(user_id: int, target: Message, is_callback: bool = False):
    """Display user's referral link, count, and free credits."""
    user_data = await get_or_create_user(user_id)
    credits = user_data.get("credits", START_CREDITS)
    mail_quota = user_data.get("mail_quota", START_MAIL_QUOTA)
    ref_count = user_data.get("referrals_count", 0)
    ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"

    text = (
        f"{pe('5454371323595744068')} <b>Refer & Earn Program</b> {pe('6129792056589031358')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"Invite your friends and earn <b>Unlimited Temp Emails</b>!\n\n"
        f"{pe('5278467510604160626')} <b>Reward Policy:</b>\n"
        f"{pe('5415758949129404605')} <b>1 Friend = +1 Credit (1 Credit = 1 Email!)</b>\n\n"
        f"{pe('6129589862413638401')} <b>Your Personal Referral Link:</b>\n"
        f"<code>{ref_link}</code> <i>(Tap to copy)</i>\n\n"
        f"{pe('5190806721286657692')} <b>Your Current Balance:</b>\n"
        f"• {pe('5287231198098117669')} <b>Credits Balance:</b> <code>{credits}</code> Credits\n"
        f"• {pe('5332724926216428039')} <b>Total Invited:</b> <code>{ref_count}</code> Friends\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"Click <b>'Share Link With Friends'</b> below to share directly with friends and groups!"
    )
    keyboard = get_referral_keyboard(user_id, BOT_USERNAME)

    if is_callback:
        try:
            await target.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard, disable_web_page_preview=True)
        except Exception:
            await target.answer(text, parse_mode=ParseMode.HTML, reply_markup=keyboard, disable_web_page_preview=True)
    else:
        await target.answer(text, parse_mode=ParseMode.HTML, reply_markup=keyboard, disable_web_page_preview=True)

# ============================================
# REFERRAL LEADERBOARD HANDLERS
# ============================================

@dp.message(Command("leaderboard", "top"))
async def cmd_leaderboard(message: Message, bot: Bot):
    """Show top referrers leaderboard."""
    clear_user_states(message.from_user.id)
    if not await ensure_fsub(message, bot):
        return
    if message.from_user.username:
        asyncio.create_task(update_user_username(message.from_user.id, message.from_user.username))
    await show_referral_leaderboard(message.from_user.id, message)

@dp.callback_query(F.data == "refer_leaderboard")
async def cb_refer_leaderboard(callback: CallbackQuery, bot: Bot):
    """Callback to show referral leaderboard."""
    clear_user_states(callback.from_user.id)
    if not await ensure_fsub(callback, bot):
        return
    if callback.from_user.username:
        asyncio.create_task(update_user_username(callback.from_user.id, callback.from_user.username))
    await callback.answer()
    await show_referral_leaderboard(callback.from_user.id, callback.message, is_callback=True)

async def show_referral_leaderboard(user_id: int, target: Message, is_callback: bool = False):
    """Display top referrers leaderboard and user's personal rank."""
    top_users = await get_referral_leaderboard(10)
    user_rank = await get_user_referral_rank(user_id)
    u = await get_user(user_id)
    my_refs = u.get("referrals_count", 0) if u else 0

    rank_medals = {1: "🥇", 2: "🥈", 3: "🥉"}

    text = (
        f"🏆 <b>REFERRAL LEADERBOARD</b> 🏆\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"Top 10 users with the most referrals:\n\n"
    )

    if not top_users:
        text += f"<i>No referrals recorded yet. Be the first to invite friends and reach the top! 🚀</i>\n\n"
    else:
        for idx, row in enumerate(top_users, start=1):
            medal = rank_medals.get(idx, f"<b>{idx}.</b>")
            uname = row.get("username")
            uid = row["user_id"]
            refs = row.get("referrals_count", 0)
            if uname:
                display_name = f"@{html.escape(uname)}"
            else:
                uid_str = str(uid)
                display_name = f"User {uid_str[:4]}****"

            is_me = " <i>(You)</i>" if uid == user_id else ""
            text += f"{medal} {display_name}{is_me} — <b>{refs} Invites</b>\n"
        text += "\n"

    rank_display = f"#{user_rank}" if user_rank > 0 else "Unranked"
    text += (
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"{pe('user')} <b>Your Stats:</b>\n"
        f"• <b>Rank:</b> <code>{rank_display}</code>\n"
        f"• <b>Friends Invited:</b> <code>{my_refs}</code> Friends\n"
        f"• <b>Credits Earned:</b> <code>+{my_refs}</code> Credits\n\n"
        f"{pe('gift')} <i>Invite friends to climb the leaderboard!</i>"
    )

    keyboard = get_leaderboard_keyboard(user_id, BOT_USERNAME)
    if is_callback:
        try:
            await target.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard, disable_web_page_preview=True)
        except Exception:
            await target.answer(text, parse_mode=ParseMode.HTML, reply_markup=keyboard, disable_web_page_preview=True)
    else:
        await target.answer(text, parse_mode=ParseMode.HTML, reply_markup=keyboard, disable_web_page_preview=True)

# ============================================
# CREATE EMAIL WITH CREDIT & QUOTA CHECK
# ============================================

async def create_new_email(user_id: int, target: Message, domain: Optional[str] = None, custom_name: Optional[str] = None, is_callback: bool = False):
    """Generate and assign a new temporary email to the user with quota and credit validation."""
    user_data = await get_or_create_user(user_id)
    is_admin = user_id in ADMIN_IDS

    if user_data.get("is_banned"):
        await target.answer(f"{pe('cross')} Your account has been blocked on this bot.")
        return

    # Check and consume mail quota (Admins have unlimited credits)
    if not is_admin:
        has_quota = await consume_user_credit(user_id)
        if not has_quota:
            current_user = await get_user(user_id)
            credits = current_user.get("credits", 0) if current_user else 0
            has_credits = credits >= 1
            no_credit_msg = (
                f"{pe('6267039884016358504')} <b>No Credits Available!</b>\n\n"
                f"You have <b>0 Credits</b>. You cannot generate a new temporary email without credits.\n\n"
                f"{pe('5287231198098117669')} <b>Your Balance:</b> <code>{credits} Credits</code> <i>(1 Credit = 1 Mail)</i>\n\n"
                f"{pe('5454371323595744068')} <b>How to get credits?</b>\n"
                f"• Invite your friends using your referral link!\n"
                f"• Earn <b>+1 Credit (= 1 Mail)</b> for each friend who joins.\n\n"
                f"Share your referral link below {pe('6339166816006312740')}"
            )
            keyboard = get_no_credits_keyboard(user_id, BOT_USERNAME, has_credits=has_credits)
            if is_callback:
                await target.edit_text(no_credit_msg, parse_mode=ParseMode.HTML, reply_markup=keyboard)
            else:
                await target.answer(no_credit_msg, parse_mode=ParseMode.HTML, reply_markup=keyboard)
            return

    prev_domain = user_data.get("domain") if user_data else None
    if user_data and user_data.get("token") and user_data.get("account_id"):
        provider = user_data.get("provider", "tempmailio")
        asyncio.create_task(mail_service.delete_account(user_data["token"], provider, user_data["account_id"]))

    account = await mail_service.create_temp_account(domain=domain, custom_name=custom_name, exclude_domain=prev_domain)
    if not account:
        error_msg = f"{pe('warning')} Error creating email. Please try again in 5 seconds."
        if is_callback:
            await target.edit_text(error_msg, reply_markup=get_main_keyboard(has_email=False, is_admin=is_admin))
        else:
            await target.reply(error_msg, reply_markup=get_main_keyboard(has_email=False, is_admin=is_admin))
        return

    email = account["email"]
    password = account.get("password", "")
    token = account["token"]
    account_id = account.get("account_id", "")
    provider = account.get("provider", "tempmailio")
    chosen_domain = account.get("domain", "")
    username = account.get("username", "")

    # Save to SQLite database
    await save_user_email(
        user_id=user_id,
        email=email,
        password=password,
        token=token,
        account_id=account_id,
        provider=provider,
        domain=chosen_domain,
        username=username
    )

    # Get updated quota and credits
    updated_user = await get_user(user_id)
    rem_quota = updated_user.get("mail_quota", 0) if (updated_user and not is_admin) else "Unlimited (Admin)"
    rem_credits = updated_user.get("credits", 0) if (updated_user and not is_admin) else "Unlimited (Admin)"

    response_text = (
        f"{pe('party')} <b>Your New Temporary Email Is Ready!</b> {pe('fire')}\n\n"
        f"{pe('5472239203590888751')} <b>Email Address:</b>\n"
        f"{pe('5415758949129404605')} <code>{email}</code> <i>(Tap to copy)</i>\n\n"
        f"{pe('5447410659077661506')} <b>Domain:</b> <code>@{chosen_domain}</code> <i>(Auto Changed)</i>\n"
        f"{pe('6046322897654387087')} <b>Auto OTP Detection:</b> {pe('6233111867171018062')} Active!\n"
        f"{pe('6233111867171018062')} <b>Available Mails:</b> <code>{rem_quota}</code>\n"
        f"{pe('5287231198098117669')} <b>Credits Balance:</b> <code>{rem_credits}</code> <i>(1 Credit = 1 Mail)</i>\n\n"
        f"{pe('5312361253610475399')} <b>Key Highlights:</b>\n"
        f"• {pe('sparkle')} Realistic format prevents websites from blocking or rejecting.\n"
        f"• {pe('globe')} Domains rotate automatically with each newly generated email.\n"
        f"• {pe('bolt')} OTP codes and verification links are delivered instantly here."
    )

    if is_callback:
        try:
            await target.edit_text(response_text, parse_mode=ParseMode.HTML, reply_markup=get_main_keyboard(has_email=True, is_admin=is_admin))
        except Exception:
            await target.answer(response_text, parse_mode=ParseMode.HTML, reply_markup=get_main_keyboard(has_email=True, is_admin=is_admin))
    else:
        await target.answer(response_text, parse_mode=ParseMode.HTML, reply_markup=get_main_keyboard(has_email=True, is_admin=is_admin))

# ============================================
# INBOX & EMAIL VIEW HANDLERS
# ============================================

@dp.message(Command("inbox"))
async def cmd_inbox(message: Message, bot: Bot):
    """Command /inbox to check received emails."""
    clear_user_states(message.from_user.id)
    if not await ensure_fsub(message, bot):
        return
    await check_user_inbox(message.from_user.id, message)

@dp.callback_query(F.data == "check_inbox")
async def cb_check_inbox(callback: CallbackQuery, bot: Bot):
    """Callback to check received emails."""
    clear_user_states(callback.from_user.id)
    await callback.answer("Refreshing inbox...")
    await check_user_inbox(callback.from_user.id, callback.message, is_callback=True)

async def check_user_inbox(user_id: int, target: Message, is_callback: bool = False):
    """Fetch and display inbox contents."""
    user_data = await get_user(user_id)
    is_admin = user_id in ADMIN_IDS
    if not user_data or not user_data.get("email"):
        msg = f"{pe('warning')} You don't have an active email right now. Generate one using the button below or <b>/new</b>."
        if is_callback:
            await target.edit_text(msg, parse_mode=ParseMode.HTML, reply_markup=get_main_keyboard(has_email=False, is_admin=is_admin))
        else:
            await target.answer(msg, parse_mode=ParseMode.HTML, reply_markup=get_main_keyboard(has_email=False, is_admin=is_admin))
        return

    token = user_data.get("token")
    email = user_data.get("email")
    provider = user_data.get("provider", "tempmailio")
    last_id = user_data.get("last_message_id")

    messages = await mail_service.get_messages(token, provider=provider, last_id=last_id, email=email)

    if not messages:
        text = (
            f"{pe('5253742260054409879')} <b>Your Inbox is Empty!</b>\n\n"
            f"{pe('5472239203590888751')} <b>Email:</b> <code>{email}</code>\n\n"
            f"No incoming emails received yet. As soon as an email or OTP arrives, the bot will automatically send an alert here! {pe('6267039884016358504')}"
        )
        if is_callback:
            try:
                await target.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=get_main_keyboard(has_email=True, is_admin=is_admin))
            except Exception:
                pass
        else:
            await target.answer(text, parse_mode=ParseMode.HTML, reply_markup=get_main_keyboard(has_email=True, is_admin=is_admin))
        return

    lines = [f"{pe('5253742260054409879')} <b>Your Inbox ({len(messages)} Messages):</b>\n{pe('5472239203590888751')} <b>Email:</b> <code>{email}</code>\n"]
    for i, msg in enumerate(messages[:5], 1):
        from_info = msg.get("from", {})
        sender_data = extract_sender_info(from_info)
        subject = html.escape(msg.get("subject") or "No Subject")
        created = msg.get("createdAt", "")[:19].replace("T", " ")
        msg_id = msg.get("id")

        lines.append(
            f"{pe('pin')} <b>{i}. {sender_data['service_name']}</b>\n"
            f"{pe('user')} From: <code>{html.escape(sender_data['sender_address'])}</code>\n"
            f"{pe('bubble')} Subject: <i>{subject}</i>\n"
            f"{pe('time')} Time: {created}\n"
            f"{pe('arrow_right')} Read full email: /read_{msg_id}\n"
        )

    text = "\n".join(lines)
    if is_callback:
        try:
            await target.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=get_main_keyboard(has_email=True, is_admin=is_admin))
        except Exception:
            pass
    else:
        await target.answer(text, parse_mode=ParseMode.HTML, reply_markup=get_main_keyboard(has_email=True, is_admin=is_admin))

@dp.message(F.text.startswith("/read_"))
async def cmd_read_message(message: Message):
    """Handle /read_<msg_id> command."""
    user_id = message.from_user.id
    msg_id = message.text.replace("/read_", "").strip()
    await display_full_email(user_id, msg_id, message)

@dp.callback_query(F.data.startswith("read_mail:"))
async def cb_read_mail(callback: CallbackQuery):
    """Callback to read full email."""
    await callback.answer("Loading email...")
    msg_id = callback.data.split("read_mail:")[1]
    await display_full_email(callback.from_user.id, msg_id, callback.message, is_callback=True)

async def display_full_email(user_id: int, message_id: str, target: Message, is_callback: bool = False):
    """Fetch and display complete details of an email."""
    user_data = await get_user(user_id)
    if not user_data or not user_data.get("token"):
        await target.answer(f"{pe('warning')} Session expired. Please restart using /start.")
        return

    provider = user_data.get("provider", "tempmailio")
    user_email = user_data.get("email", "")
    detail = await mail_service.get_message_detail(user_data["token"], provider=provider, message_id=message_id, email=user_email)
    
    if not detail:
        # Fallback to local database cache if external API expired or deleted the email
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM received_messages WHERE id = ?", (message_id,)) as cur:
                cached_row = await cur.fetchone()
                if cached_row:
                    detail = {
                        "subject": cached_row["subject"] or "No Subject",
                        "from": {"address": cached_row["sender_address"], "name": cached_row["sender_service"]},
                        "text": f"Service: {cached_row['sender_service']}\nFrom: {cached_row['sender_address']}\nSubject: {cached_row['subject']}",
                        "otp": cached_row["otp_code"],
                        "link": cached_row["verification_link"]
                    }

    if not detail:
        await target.answer(f"{pe('warning')} Message not found or already deleted.")
        return

    subject = detail.get("subject") or "No Subject"
    from_info = detail.get("from") or {}
    sender_data = extract_sender_info(from_info)

    text_body = detail.get("text") or ""
    html_body = ""
    if detail.get("html"):
        if isinstance(detail["html"], list):
            html_body = "".join(detail["html"])
        else:
            html_body = str(detail["html"])

    otp_code = extract_otp(subject, text_body, html_body) or detail.get("otp")
    verify_link = extract_verification_link(html_body, text_body) or detail.get("link")
    clean_body = clean_text_content(text_body, html_body)

    lines = [
        f"{pe('email')} <b>Full Email Details:</b> {pe('verified')}\n",
        f"{pe('globe')} <b>Website / Service:</b> <code>{html.escape(sender_data['service_name'])}</code>",
        f"{pe('user')} <b>From:</b> <code>{html.escape(sender_data['sender_address'])}</code>",
        f"{pe('bubble')} <b>Subject:</b> <b>{html.escape(subject)}</b>"
    ]

    if otp_code:
        lines.append(f"\n{pe('key')} <b>OTP / Verification Code:</b>\n{pe('arrow_right')} <code>{html.escape(otp_code)}</code> <i>(Tap to copy)</i> {pe('fire')}")

    if verify_link:
        if not otp_code:
            lines.append(f"\n{pe('magic')} <b>Direct Magic Link / One-Click Login:</b>\n{pe('arrow_right')} <a href=\"{verify_link}\">Click Here to Log In Directly</a> {pe('rocket')}")
        else:
            lines.append(f"\n{pe('link')} <b>Verification Link:</b>\n{pe('arrow_right')} <a href=\"{verify_link}\">Click Here to Verify Account</a> {pe('rocket')}")

    max_body_len = 2000
    if len(clean_body) > max_body_len:
        clean_body = clean_body[:max_body_len] + "... (truncated)"

    lines.append(f"\n{pe('pin')} <b>Email Body:</b>\n<blockquote>{html.escape(clean_body)}</blockquote>")

    text = "\n".join(lines)
    keyboard = get_full_mail_keyboard(message_id, verify_link)

    if is_callback:
        try:
            await target.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard, disable_web_page_preview=True)
        except Exception:
            await target.answer(text, parse_mode=ParseMode.HTML, reply_markup=keyboard, disable_web_page_preview=True)
    else:
        await target.answer(text, parse_mode=ParseMode.HTML, reply_markup=keyboard, disable_web_page_preview=True)

@dp.callback_query(F.data.startswith("del_mail:"))
async def cb_del_mail(callback: CallbackQuery):
    """Delete a single email message."""
    await callback.answer("Message deleted.")
    user_id = callback.from_user.id
    user_data = await get_user(user_id)
    is_admin = user_id in ADMIN_IDS
    await callback.message.edit_text(f"{pe('trash')} Message has been deleted.", reply_markup=get_main_keyboard(has_email=bool(user_data and user_data.get("email")), is_admin=is_admin))

@dp.message(Command("delete"))
async def cmd_delete(message: Message):
    """Command /delete to remove active temp email."""
    clear_user_states(message.from_user.id)
    await process_delete_email(message.from_user.id, message)

@dp.callback_query(F.data == "delete_email")
async def cb_delete_email(callback: CallbackQuery):
    """Callback to remove active temp email."""
    clear_user_states(callback.from_user.id)
    await callback.answer()
    await process_delete_email(callback.from_user.id, callback.message, is_callback=True)

async def process_delete_email(user_id: int, target: Message, is_callback: bool = False):
    """Delete current temp email account from DB and remote provider."""
    user_data = await get_user(user_id)
    is_admin = user_id in ADMIN_IDS
    if not user_data or not user_data.get("email"):
        msg = f"{pe('warning')} You do not have an active email to delete."
        if is_callback:
            await target.edit_text(msg, parse_mode=ParseMode.HTML, reply_markup=get_main_keyboard(has_email=False, is_admin=is_admin))
        else:
            await target.answer(msg, parse_mode=ParseMode.HTML, reply_markup=get_main_keyboard(has_email=False, is_admin=is_admin))
        return

    old_email = user_data["email"]
    token = user_data.get("token")
    provider = user_data.get("provider", "tempmailio")
    account_id = user_data.get("account_id", "")

    if token:
        asyncio.create_task(mail_service.delete_account(token, provider, account_id))

    await delete_user_email(user_id)
    text = (
        f"{pe('trash')} <b>Email Successfully Deleted!</b> {pe('verified')}\n\n"
        f"Email <code>{old_email}</code> is now deactivated. "
        f"To generate a new email, click <b>'{pe('email')} Generate Temp Email'</b> below."
    )
    if is_callback:
        await target.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=get_main_keyboard(has_email=False, is_admin=is_admin))
    else:
        await target.answer(text, parse_mode=ParseMode.HTML, reply_markup=get_main_keyboard(has_email=False, is_admin=is_admin))

@dp.callback_query(F.data == "help_menu")
async def cb_help_menu(callback: CallbackQuery):
    """Callback for help menu."""
    clear_user_states(callback.from_user.id)
    await callback.answer()
    help_text = (
        f"{pe('info')} <b>How to Use Temp Mail Bot?</b> {pe('sparkle')}\n\n"
        f"1. Use <b>/new</b> or click the button below to generate a temporary email.\n"
        f"2. {pe('globe')} <b>Auto Rotate:</b> Each new email gets a fresh, realistic domain automatically.\n"
        f"3. {pe('bolt')} <b>Instant Alerts:</b> As soon as an email or OTP arrives, you will receive an alert immediately.\n"
        f"4. {pe('verified')} <b>Website Detection:</b> The sender's website or service name is cleanly detected.\n"
        f"5. {pe('link')} <b>Verification Link:</b> If the email has a verification link, a direct clickable button appears.\n"
        f"6. {pe('gift')} <b>Referral Program:</b> Earn <b>+{CREDITS_PER_REFERRAL} Credit (= 1 Email)</b> for every friend you invite!\n"
        f"7. {pe('trash')} <b>/delete:</b> Delete your temporary email whenever you are done."
    )
    user_data = await get_user(callback.from_user.id)
    has_email = bool(user_data and user_data.get("email"))
    is_admin = callback.from_user.id in ADMIN_IDS
    await callback.message.edit_text(help_text, parse_mode=ParseMode.HTML, reply_markup=get_main_keyboard(has_email=has_email, is_admin=is_admin))

@dp.message(Command("help"))
async def cmd_help(message: Message):
    """Handle /help command."""
    clear_user_states(message.from_user.id)
    help_text = (
        f"{pe('info')} <b>How to Use Temp Mail Bot?</b> {pe('sparkle')}\n\n"
        f"1. Use <b>/new</b> or click the button below to generate a temporary email.\n"
        f"2. {pe('globe')} <b>Auto Rotate:</b> Each new email gets a fresh, realistic domain automatically.\n"
        f"3. {pe('bolt')} <b>Instant Alerts:</b> As soon as an email or OTP arrives, you will receive an alert immediately.\n"
        f"4. {pe('verified')} <b>Website Detection:</b> The sender's website or service name is cleanly detected.\n"
        f"5. {pe('link')} <b>Verification Link:</b> If the email has a verification link, a direct clickable button appears.\n"
        f"6. {pe('gift')} <b>Referral Program:</b> Earn <b>+{CREDITS_PER_REFERRAL} Credit (= 1 Email)</b> for every friend you invite!\n"
        f"7. {pe('trash')} <b>/delete:</b> Delete your temporary email whenever you are done."
    )
    user_data = await get_user(message.from_user.id)
    has_email = bool(user_data and user_data.get("email"))
    is_admin = message.from_user.id in ADMIN_IDS
    await message.answer(help_text, parse_mode=ParseMode.HTML, reply_markup=get_main_keyboard(has_email=has_email, is_admin=is_admin))

# ============================================
# ADMIN PANEL HANDLERS
# ============================================

@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    """Open admin panel."""
    clear_user_states(message.from_user.id)
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Admin access required.")
        return
    await show_admin_dashboard(message.from_user.id, message)

@dp.callback_query(F.data == "admin_panel")
async def cb_admin_panel(callback: CallbackQuery):
    """Open admin dashboard from inline button."""
    clear_user_states(callback.from_user.id)
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Admin access required!", show_alert=True)
        return
    await callback.answer()
    await show_admin_dashboard(callback.from_user.id, callback.message, is_callback=True)

async def show_admin_dashboard(user_id: int, target: Message, is_callback: bool = False):
    """Display comprehensive admin dashboard."""
    stats = await get_admin_stats()
    fsub_channels = await get_force_channels()
    text = (
        f"{pe('gear')} <b>ADMIN CONTROL PANEL</b> {pe('crown')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"{pe('crown')} <b>Admin ID:</b> <code>{user_id}</code>\n\n"
        f"{pe('stats')} <b>Bot Key Metrics:</b>\n"
        f"• {pe('user')} <b>Total Users:</b> <code>{stats['total_users']}</code>\n"
        f"• {pe('email')} <b>Active Inboxes:</b> <code>{stats['active_emails']}</code>\n"
        f"• {pe('inbox')} <b>Total Messages Received:</b> <code>{stats['total_messages']}</code>\n"
        f"• {pe('gift')} <b>Total Referrals Done:</b> <code>{stats['total_referrals']}</code>\n"
        f"• {pe('lock')} <b>Force Join Channels:</b> <code>{len(fsub_channels)}</code> Active\n"
        f"• {pe('cross')} <b>Banned Users:</b> <code>{stats['banned_users']}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"{pe('gear')} <b>Quick Admin Commands:</b>\n"
        f"• <code>/addchannel &lt;@channel&gt;</code> - Add channel/group\n"
        f"• <code>/delchannel &lt;id&gt;</code> - Remove channel\n"
        f"• <code>/channels</code> - View active channels\n"
        f"• <code>/addcredits &lt;user_id&gt; &lt;amount&gt;</code> - Add credits\n"
        f"• <code>/user &lt;user_id&gt;</code> - View user profile\n"
        f"• <code>/allmails</code> - View all users' mails & OTPs\n"
        f"• <code>/ban &lt;user_id&gt;</code> | <code>/unban &lt;user_id&gt;</code>\n"
        f"• <code>/broadcast &lt;message&gt;</code> - Broadcast announcement"
    )
    keyboard = get_admin_keyboard()
    if is_callback:
        await target.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
    else:
        await target.answer(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)

PAGE_SIZE_ADMIN_MAILS = 6

@dp.message(Command("allmails"))
async def cmd_allmails(message: Message):
    """Admin command to directly view all user mails and OTPs."""
    if message.from_user.id not in ADMIN_IDS:
        return
    clear_user_states(message.from_user.id)
    await show_admin_mails_view(message.from_user.id, message, page=0, is_callback=False)

@dp.callback_query(F.data.startswith("admin_all_mails"))
async def cb_admin_all_mails(callback: CallbackQuery):
    """View all received emails and OTPs across all bot users."""
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("Admin access required!", show_alert=True)
    clear_user_states(callback.from_user.id)
    await callback.answer()
    parts = callback.data.split(":")
    page = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    await show_admin_mails_view(callback.from_user.id, callback.message, page=page, is_callback=True)

@dp.callback_query(F.data.startswith("admin_user_mails:"))
async def cb_admin_user_mails(callback: CallbackQuery):
    """View received emails and OTPs for a specific user."""
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("Admin access required!", show_alert=True)
    clear_user_states(callback.from_user.id)
    await callback.answer()
    parts = callback.data.split(":")
    target_user_id = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
    page = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
    await show_admin_mails_view(callback.from_user.id, callback.message, page=page, target_user_id=target_user_id, is_callback=True)

@dp.callback_query(F.data == "admin_search_user_mails")
async def cb_admin_search_user_mails(callback: CallbackQuery):
    """Prompt admin to enter user ID to view their mails."""
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("Admin access required!", show_alert=True)
    clear_user_states(callback.from_user.id)
    ADMIN_SEARCH_USER_MAILS_STATE.add(callback.from_user.id)
    await callback.answer()
    await callback.message.edit_text(
        f"{pe('user')} <b>Filter Mails & OTPs by User ID:</b>\n\n"
        f"Please send the numeric <b>User Telegram ID</b> (e.g. <code>6566593716</code>) to inspect all their received emails and OTP codes.\n\n"
        f"• Tap Cancel below to return.",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [make_btn(btn_key="cancel", text="Cancel", callback_data="admin_all_mails:0")]
        ])
    )

async def show_admin_mails_view(admin_id: int, target: Message, page: int = 0, target_user_id: Optional[int] = None, is_callback: bool = False):
    """Format and render admin all-mails / user-mails view."""
    total_count = await get_total_received_messages_count(target_user_id)
    total_pages = max(1, (total_count + PAGE_SIZE_ADMIN_MAILS - 1) // PAGE_SIZE_ADMIN_MAILS)
    if page >= total_pages:
        page = max(0, total_pages - 1)

    offset = page * PAGE_SIZE_ADMIN_MAILS
    if target_user_id:
        messages = await get_user_received_messages(target_user_id, limit=PAGE_SIZE_ADMIN_MAILS, offset=offset)
        title_header = f"{pe('inbox')} <b>MAILS & OTPS FOR USER</b> <code>{target_user_id}</code>"
    else:
        messages = await get_recent_received_messages(limit=PAGE_SIZE_ADMIN_MAILS, offset=offset)
        title_header = f"{pe('inbox')} <b>ALL USERS LIVE MAILS & OTPS</b> {pe('fire')}"

    lines = [
        f"{title_header}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>Total Mails/OTPs:</b> <code>{total_count}</code> | 📄 <b>Page:</b> <code>{page + 1}/{total_pages}</code>\n"
    ]

    if not messages:
        lines.append("<i>No incoming emails or OTPs recorded in database yet.</i>")
    else:
        for idx, m in enumerate(messages, start=offset + 1):
            u_id = m.get("user_id")
            u_email = m.get("user_email") or "Unknown"
            tg_uname = f"@{m['tg_username']}" if m.get("tg_username") else "No username"
            svc = html.escape(m.get("sender_service") or "Service")
            sender = html.escape(m.get("sender_address") or "")
            subj = html.escape(m.get("subject") or "No Subject")
            otp = m.get("otp_code")
            v_link = m.get("verification_link")
            r_at = str(m.get("received_at") or "")[:19].replace("T", " ")
            msg_id = m.get("id")

            block = [
                f"<b>{idx}. {svc}</b> ({sender})",
                f"• 👤 <b>User:</b> <code>{u_id}</code> ({tg_uname})",
                f"• ✉️ <b>Email:</b> <code>{u_email}</code>",
                f"• 📝 <b>Subject:</b> <b>{subj}</b>",
                f"• 🕒 <b>Time:</b> <code>{r_at}</code>"
            ]
            if otp:
                otp_safe = html.escape(otp)
                block.append(f"• 🔑 <b>OTP Code:</b> <code>{otp_safe}</code>  <i>(Tap to copy)</i> {pe('fire')}")
            if v_link:
                block.append(f"• 🔗 <a href=\"{v_link}\">Verification Link</a>")
            block.append(f"• 👁️ Read: /read_{msg_id}\n")
            lines.append("\n".join(block))

    text = "\n".join(lines)
    keyboard = get_admin_all_mails_keyboard(page, total_pages, user_id_filter=target_user_id)
    if is_callback:
        try:
            await target.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard, disable_web_page_preview=True)
        except Exception:
            pass
    else:
        await target.answer(text, parse_mode=ParseMode.HTML, reply_markup=keyboard, disable_web_page_preview=True)

@dp.callback_query(F.data == "admin_fsub_list")
async def cb_admin_fsub_list(callback: CallbackQuery):
    """Show current force join channels with add/remove options."""
    clear_user_states(callback.from_user.id)
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("Admin access required!", show_alert=True)
    await callback.answer()
    channels = await get_force_channels()
    text = (
        f"{pe('lock')} <b>FORCE JOIN (FSUB) CHANNELS & GROUPS</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"Total Active Channels/Groups: <b>{len(channels)}</b>\n\n"
    )
    if channels:
        for idx, ch in enumerate(channels, 1):
            c_type = f"{pe('handshake')} Group" if ch.get("chat_type") == "group" else f"{pe('broadcast')} Channel"
            text += (
                f"{idx}. {c_type}: <b>{html.escape(ch.get('title') or '')}</b>\n"
                f"   {pe('pin')} ID: <code>{ch['chat_id']}</code>\n"
                f"   {pe('link')} Link: {ch['invite_link']}\n"
                f"   {pe('trash')} To remove: <code>/delchannel {ch['id']}</code>\n\n"
            )
    else:
        text += f"<i>No Force Join channels configured yet. Users can access the bot without restriction.</i>\n\n"

    text += (
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"• <b>Add Channel/Group {pe('plus')}:</b> Link a new channel or group.\n"
        f"• <b>Remove Channel {pe('trash')}:</b> Unlink a force join channel.\n\n"
        f"{pe('warning')} <b>Important:</b> Ensure the bot is an <b>Admin</b> in the channel/group to verify members!"
    )
    await callback.message.edit_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_admin_channels_keyboard(channels),
        disable_web_page_preview=True
    )

@dp.callback_query(F.data == "admin_add_fsub")
async def cb_admin_add_fsub(callback: CallbackQuery):
    """Prompt admin to enter channel username or ID."""
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("Admin access required!", show_alert=True)
    clear_user_states(callback.from_user.id)
    await callback.answer()
    ADMIN_ADD_FSUB_STATE.add(callback.from_user.id)
    text = (
        f"{pe('plus')} <b>Add Force Join Channel / Group</b> {pe('fire')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"Please send the Channel or Group <b>Username</b> or <b>ID</b>:\n\n"
        f"<b>Formats:</b>\n"
        f"1️⃣ <b>Public Channel:</b> Send username directly (Example: <code>@MyChannel</code>)\n"
        f"2️⃣ <b>Private Channel:</b> <code>-100xxxxxxxx https://t.me/+invite ChannelName</code>\n\n"
        f"{pe('arrow_right')} Or use the direct command:\n"
        f"<code>/addchannel @MyChannel</code>\n\n"
        f"{pe('warning')} <i>Note: The bot must already be an <b>Admin</b> in the channel/group!</i>"
    )
    await callback.message.edit_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_cancel_add_channel_keyboard()
    )

@dp.callback_query(F.data == "admin_cancel_fsub_add")
async def cb_admin_cancel_fsub_add(callback: CallbackQuery):
    """Cancel channel addition."""
    clear_user_states(callback.from_user.id)
    await callback.answer("Cancelled.")
    await cb_admin_fsub_list(callback)

@dp.callback_query(F.data == "admin_del_fsub")
async def cb_admin_del_fsub(callback: CallbackQuery):
    """List channels for deletion."""
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("Admin access required!", show_alert=True)
    await callback.answer()
    channels = await get_force_channels()
    if not channels:
        return await callback.answer("No channels configured!", show_alert=True)
    text = f"{pe('trash')} <b>Select a channel to remove:</b>"
    await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=get_remove_channel_keyboard(channels))

@dp.callback_query(F.data.startswith("admin_rm_chan:"))
async def cb_admin_rm_chan(callback: CallbackQuery):
    """Delete channel by DB ID."""
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("Admin access required!", show_alert=True)
    ch_id_str = callback.data.split("admin_rm_chan:")[1]
    if ch_id_str.isdigit():
        await remove_force_channel(int(ch_id_str))
        await callback.answer("✅ Channel removed successfully!", show_alert=True)
    await cb_admin_fsub_list(callback)


@dp.callback_query(F.data == "admin_stats")
async def cb_admin_stats(callback: CallbackQuery):
    """Open comprehensive detailed stats panel."""
    clear_user_states(callback.from_user.id)
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("Not allowed", show_alert=True)
    await callback.answer("Opening Detailed Stats...")
    await show_detailed_stats_panel(callback.from_user.id, callback.message, is_callback=True)

async def show_detailed_stats_panel(user_id: int, target: Message, is_callback: bool = False):
    """Show dedicated detailed bot metrics and statistics."""
    stats = await get_admin_stats()
    fsub_channels = await get_force_channels()
    codes = await get_all_redeem_codes()
    total_codes_count = len(codes)
    total_redemptions = sum(c.get("redeemed_count", 0) for c in codes)
    active_codes_count = sum(1 for c in codes if c.get("is_active") and c.get("redeemed_count", 0) < c.get("max_users", 0))

    now_str = datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S")

    text = (
        f"{pe('stats')} <b>DETAILED SYSTEM & BOT STATISTICS</b> {pe('fire')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 <b>User Metrics:</b>\n"
        f"• Total Registered Users: <code>{stats['total_users']}</code>\n"
        f"• Active Temp Inboxes: <code>{stats['active_emails']}</code>\n"
        f"• Total Referrals Completed: <code>{stats['total_referrals']}</code>\n"
        f"• Banned Accounts: <code>{stats['banned_users']}</code>\n\n"
        f"📬 <b>Email Monitoring & Traffic:</b>\n"
        f"• Total Messages/OTPs Delivered: <code>{stats['total_messages']}</code>\n"
        f"• Background Watcher: <code>Active (Every {POLL_INTERVAL}s)</code>\n"
        f"• Force Join Channels: <code>{len(fsub_channels)} Active</code>\n\n"
        f"🎟️ <b>Redeem Codes Summary:</b>\n"
        f"• Total Codes Created: <code>{total_codes_count}</code>\n"
        f"• Currently Active Codes: <code>{active_codes_count}</code>\n"
        f"• Total Code Redemptions: <code>{total_redemptions}</code> Claims\n\n"
        f"⚙️ <b>Bot & Server Identity:</b>\n"
        f"• Bot Username: <code>@{BOT_USERNAME}</code>\n"
        f"• Database Engine: <code>SQLite (tempmail.db)</code>\n"
        f"• Last Updated: <code>{now_str}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━"
    )

    buttons = [
        [
            InlineKeyboardButton(text="🔄 Refresh Details", callback_data="admin_stats")
        ],
        [
            InlineKeyboardButton(text="🎟️ Manage Redeem Codes", callback_data="admin_redeem_manage"),
            InlineKeyboardButton(text="📢 Broadcast", callback_data="admin_broadcast")
        ],
        [
            InlineKeyboardButton(text="🔙 Back to Admin Menu", callback_data="admin_panel")
        ]
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    try:
        if is_callback:
            await target.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
        else:
            await target.answer(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
    except Exception:
        pass

@dp.callback_query(F.data == "admin_broadcast")
async def cb_admin_broadcast(callback: CallbackQuery):
    """Initiate broadcast mode."""
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("Not allowed", show_alert=True)
    clear_user_states(callback.from_user.id)
    await callback.answer()
    ADMIN_BROADCAST_STATE.add(callback.from_user.id)
    text = (
        f"{pe('broadcast')} <b>BROADCAST MODE ACTIVE</b> {pe('fire')}\n\n"
        f"Your next message will be <b>broadcasted to all bot users</b>!\n\n"
        f"{pe('arrow_right')} Or use the direct command:\n"
        f"<code>/broadcast Your message here...</code>\n\n"
        f"To cancel broadcast, click the button below 👇"
    )
    await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=get_cancel_broadcast_keyboard())

@dp.callback_query(F.data == "admin_cancel_broadcast")
async def cb_cancel_broadcast(callback: CallbackQuery):
    """Cancel broadcast input."""
    clear_user_states(callback.from_user.id)
    await callback.answer("Broadcast cancelled.")
    await show_admin_dashboard(callback.from_user.id, callback.message, is_callback=True)

# ============================================
# ADMIN BUTTON EMOJIS CUSTOMIZER
# ============================================

@dp.callback_query(F.data == "admin_btn_emojis")
async def cb_admin_btn_emojis(callback: CallbackQuery):
    """Display button emoji categories menu."""
    clear_user_states(callback.from_user.id)
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("Admin access required!", show_alert=True)
    await callback.answer()
    text = (
        f"{pe('sparkle')} <b>All Buttons Emoji Manager</b> {pe('fire')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"Choose a category below to view and customize button emojis:\n\n"
        f"• <b>Total Customizable Buttons:</b> <code>{len(BUTTON_NAMES)}</code> buttons\n"
        f"• You can change emojis for <b>every single button</b> in the bot!"
    )
    await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=get_admin_btn_categories_keyboard())

@dp.callback_query(F.data.startswith("admin_emojis_cat:"))
async def cb_admin_emojis_cat(callback: CallbackQuery):
    """Display buttons inside a specific category."""
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("Admin access required!", show_alert=True)
    await callback.answer()
    ADMIN_EDIT_BTN_STATE.pop(callback.from_user.id, None)
    cat_key = callback.data.split("admin_emojis_cat:")[1]
    cat_data = BUTTON_CATEGORIES.get(cat_key)
    if not cat_data:
        return await cb_admin_btn_emojis(callback)

    text = (
        f"{cat_data['title']}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"Tap any button below to update its animated emoji icon:"
    )
    await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=get_admin_category_buttons_keyboard(cat_key))

@dp.callback_query(F.data.startswith("admin_edit_emoji:"))
async def cb_admin_edit_emoji(callback: CallbackQuery):
    """Prompt admin to enter new emoji for a specific button."""
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("Admin access required!", show_alert=True)
    clear_user_states(callback.from_user.id)
    await callback.answer()
    btn_key = callback.data.split("admin_edit_emoji:")[1]
    btn_title = BUTTON_NAMES.get(btn_key, btn_key)
    curr_emoji = get_btn_emoji(btn_key)
    ADMIN_EDIT_BTN_STATE[callback.from_user.id] = btn_key

    text = (
        f"✨ <b>Change Emoji for '{btn_title}'</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"• <b>Button Key:</b> <code>{btn_key}</code>\n"
        f"• <b>Current Icon:</b> {pe(curr_emoji)} (ID: <code>{curr_emoji}</code>)\n\n"
        f"<b>How to update:</b>\n"
        f"1️⃣ Send any <b>Telegram Premium Emoji</b> directly from your keyboard!\n"
        f"2️⃣ OR send its numeric <b>Custom Emoji ID</b> (e.g. <code>5472239203590888751</code>).\n\n"
        f"To cancel, click the button below 👇"
    )
    await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=get_cancel_edit_emoji_keyboard(btn_key))

@dp.callback_query(F.data == "admin_reset_emojis_prompt")
async def cb_admin_reset_emojis_prompt(callback: CallbackQuery):
    """Prompt confirmation to reset all button emojis to defaults."""
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("Admin access required!", show_alert=True)
    await callback.answer()
    text = (
        f"{pe('warning')} <b>Reset All Button Emojis?</b>\n\n"
        f"This will reset all <code>{len(BUTTON_NAMES)}</code> bot button emojis back to their factory default values.\n\n"
        f"Are you sure you want to proceed?"
    )
    await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=get_confirm_reset_emojis_keyboard())

@dp.callback_query(F.data == "admin_reset_emojis_confirm")
async def cb_admin_reset_emojis_confirm(callback: CallbackQuery):
    """Execute reset of all button emojis."""
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("Admin access required!", show_alert=True)
    await reset_all_button_emojis()
    reset_button_emojis_cache()
    await callback.answer("All emojis reset to default successfully!", show_alert=True)
    await cb_admin_btn_emojis(callback)

# ============================================
# ADMIN BUTTON COLORS CUSTOMIZER
# ============================================

@dp.callback_query(F.data == "admin_btn_colors")
async def cb_admin_btn_colors(callback: CallbackQuery):
    """Display button color categories menu."""
    clear_user_states(callback.from_user.id)
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("Admin access required!", show_alert=True)
    await callback.answer()
    text = (
        f"🎨 <b>All Buttons Color Manager</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"Choose a category below to customize button styles and colors:\n\n"
        f"• <b>Total Customizable Buttons:</b> <code>{len(BUTTON_NAMES)}</code> buttons\n"
        f"• Supported Colors: 🔵 <b>Primary</b> | 🟢 <b>Success</b> | 🔴 <b>Danger</b>\n"
        f"• Tap any button inside a category to instantly toggle its color!"
    )
    await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=get_admin_btn_colors_categories_keyboard())

@dp.callback_query(F.data.startswith("admin_colors_cat:"))
async def cb_admin_colors_cat(callback: CallbackQuery):
    """Display buttons inside a specific category with their current color."""
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("Admin access required!", show_alert=True)
    await callback.answer()
    ADMIN_EDIT_TEXT_STATE.pop(callback.from_user.id, None)
    ADMIN_EDIT_BTN_STATE.pop(callback.from_user.id, None)
    cat_key = callback.data.split("admin_colors_cat:")[1]
    cat_data = BUTTON_CATEGORIES.get(cat_key)
    if not cat_data:
        return await cb_admin_btn_colors(callback)

    text = (
        f"{cat_data['title']} - <b>Color Style Manager</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"Tap any button below to toggle its color (🔵 Primary ➔ 🟢 Success ➔ 🔴 Danger):"
    )
    await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=get_admin_colors_buttons_keyboard(cat_key))

@dp.callback_query(F.data.startswith("admin_toggle_color:"))
async def cb_admin_color_toggle(callback: CallbackQuery):
    """Toggle button color cycle (primary -> success -> danger -> primary)."""
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("Admin access required!", show_alert=True)
    parts = callback.data.split(":")
    if len(parts) < 3:
        return await callback.answer("Invalid request.")
    cat_key = parts[1]
    btn_key = parts[2]

    curr_color = get_btn_color(btn_key)
    cycle = {
        "primary": "success",
        "success": "danger",
        "danger": "primary"
    }
    new_color = cycle.get(curr_color, "primary")

    await set_button_color(btn_key, new_color)
    update_button_colors_cache({btn_key: new_color})

    color_names = {"primary": "🔵 Primary", "success": "🟢 Success", "danger": "🔴 Danger"}
    await callback.answer(f"Color changed to {color_names.get(new_color, new_color)}!")
    try:
        await callback.message.edit_reply_markup(reply_markup=get_admin_colors_buttons_keyboard(cat_key))
    except Exception:
        pass

@dp.callback_query(F.data == "admin_reset_colors_prompt")
async def cb_admin_reset_colors_prompt(callback: CallbackQuery):
    """Prompt confirmation to reset all button colors to defaults."""
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("Admin access required!", show_alert=True)
    await callback.answer()
    text = (
        f"{pe('warning')} <b>Reset All Button Colors?</b>\n\n"
        f"This will reset all <code>{len(BUTTON_NAMES)}</code> bot button colors back to their original factory styles.\n\n"
        f"Are you sure you want to proceed?"
    )
    await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=get_confirm_reset_colors_keyboard())

@dp.callback_query(F.data == "admin_reset_colors_confirm")
async def cb_admin_reset_colors_confirm(callback: CallbackQuery):
    """Execute reset of all button colors."""
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("Admin access required!", show_alert=True)
    await reset_all_button_colors()
    reset_button_colors_cache()
    await callback.answer("All colors reset to default successfully!", show_alert=True)
    await cb_admin_btn_colors(callback)

# ============================================
# ADMIN BUTTON TEXTS CUSTOMIZER
# ============================================

@dp.callback_query(F.data == "admin_btn_texts")
async def cb_admin_btn_texts(callback: CallbackQuery):
    """Display button text categories menu."""
    clear_user_states(callback.from_user.id)
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("Admin access required!", show_alert=True)
    await callback.answer()
    text = (
        f"✏️ <b>All Buttons Text & Label Manager</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"Choose a category below to customize button text and labels:\n\n"
        f"• <b>Total Customizable Buttons:</b> <code>{len(BUTTON_NAMES)}</code> buttons\n"
        f"• You can change labels for <b>every single button</b> in the bot!"
    )
    await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=get_admin_btn_texts_categories_keyboard())

@dp.callback_query(F.data.startswith("admin_texts_cat:"))
async def cb_admin_texts_cat(callback: CallbackQuery):
    """Display buttons inside a specific category for text editing."""
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("Admin access required!", show_alert=True)
    await callback.answer()
    ADMIN_EDIT_TEXT_STATE.pop(callback.from_user.id, None)
    ADMIN_EDIT_BTN_STATE.pop(callback.from_user.id, None)
    cat_key = callback.data.split("admin_texts_cat:")[1]
    cat_data = BUTTON_CATEGORIES.get(cat_key)
    if not cat_data:
        return await cb_admin_btn_texts(callback)

    text = (
        f"{cat_data['title']} - <b>Button Text Manager</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"Tap any button below to customize its text label:"
    )
    await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=get_admin_texts_buttons_keyboard(cat_key))

@dp.callback_query(F.data.startswith("admin_edit_text:"))
async def cb_admin_edit_text(callback: CallbackQuery):
    """Prompt admin to enter new text for a specific button."""
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("Admin access required!", show_alert=True)
    clear_user_states(callback.from_user.id)
    await callback.answer()
    btn_key = callback.data.split("admin_edit_text:")[1]
    curr_text = get_btn_text(btn_key)
    ADMIN_EDIT_TEXT_STATE[callback.from_user.id] = btn_key

    text = (
        f"✏️ <b>Change Text for '{curr_text}'</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"• <b>Button Key:</b> <code>{btn_key}</code>\n"
        f"• <b>Current Label:</b> <code>{curr_text}</code>\n\n"
        f"Please send the <b>new button label</b> in chat now!\n\n"
        f"To cancel, click the button below 👇"
    )
    await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=get_cancel_edit_text_keyboard(btn_key))

@dp.callback_query(F.data == "admin_reset_texts_prompt")
async def cb_admin_reset_texts_prompt(callback: CallbackQuery):
    """Prompt confirmation to reset all button texts to defaults."""
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("Admin access required!", show_alert=True)
    await callback.answer()
    text = (
        f"{pe('warning')} <b>Reset All Button Texts?</b>\n\n"
        f"This will reset all <code>{len(BUTTON_NAMES)}</code> bot button texts back to factory defaults.\n\n"
        f"Are you sure you want to proceed?"
    )
    await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=get_confirm_reset_texts_keyboard())

@dp.callback_query(F.data == "admin_reset_texts_confirm")
async def cb_admin_reset_texts_confirm(callback: CallbackQuery):
    """Execute reset of all button texts."""
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("Admin access required!", show_alert=True)
    await reset_all_button_texts()
    reset_button_texts_cache()
    await callback.answer("All texts reset to default successfully!", show_alert=True)
    await cb_admin_btn_texts(callback)

@dp.callback_query(F.data == "admin_add_credits_info")
async def cb_add_credits_info(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    await callback.answer()
    await callback.message.reply(
        f"{pe('plus')} <b>How to Add Credits:</b>\n\n"
        f"Send this command in chat:\n"
        f"<code>/addcredits &lt;user_id&gt; &lt;credits&gt;</code>\n\n"
        f"Example:\n<code>/addcredits 6566593716 10</code>",
        parse_mode=ParseMode.HTML
    )

@dp.callback_query(F.data == "admin_user_lookup_info")
async def cb_user_lookup_info(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    await callback.answer()
    await callback.message.reply(
        f"{pe('search')} <b>User Lookup:</b>\n\n"
        f"Send this command in chat:\n"
        f"<code>/user &lt;user_id&gt;</code>\n\n"
        f"Example:\n<code>/user 6566593716</code>",
        parse_mode=ParseMode.HTML
    )

# ============================================
# REDEEM CODE SYSTEM (USER & ADMIN)
# ============================================

@dp.message(Command("redeem"))
async def cmd_redeem(message: Message, bot: Bot):
    """User command to redeem promo / gift code."""
    if not await ensure_fsub(message, bot):
        return
    user_id = message.from_user.id
    clear_user_states(user_id)
    parts = message.text.split(maxsplit=1)
    if len(parts) > 1:
        code_input = parts[1].strip()
        await execute_user_redeem(message, code_input)
        return

    USER_REDEEM_STATE.add(user_id)
    text = (
        f"{pe('5240228673738527951')} <b>Redeem Gift / Promo Code:</b>\n\n"
        f"Please send the <b>Redeem Code</b> you received to claim free email credits!\n\n"
        f"• <i>Example:</i> <code>WELCOME50</code>\n"
        f"• <i>Tap Cancel below if you don't have a code.</i>"
    )
    await message.reply(text, parse_mode=ParseMode.HTML, reply_markup=get_cancel_redeem_keyboard())

@dp.callback_query(F.data == "redeem_code")
async def cb_redeem_code(callback: CallbackQuery, bot: Bot):
    """User callback button to redeem code."""
    if not await ensure_fsub(callback, bot):
        return
    user_id = callback.from_user.id
    clear_user_states(user_id)
    USER_REDEEM_STATE.add(user_id)
    await callback.answer()
    text = (
        f"{pe('5240228673738527951')} <b>Redeem Gift / Promo Code:</b>\n\n"
        f"Please send the <b>Redeem Code</b> you received to claim free email credits!\n\n"
        f"• <i>Example:</i> <code>WELCOME50</code>\n"
        f"• <i>Tap Cancel below if you don't have a code.</i>"
    )
    await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=get_cancel_redeem_keyboard())

async def execute_user_redeem(message: Message, code_text: str):
    """Process code redemption for a user."""
    user_id = message.from_user.id
    USER_REDEEM_STATE.discard(user_id)
    code_clean = code_text.strip().upper()
    if not code_clean:
        await message.reply(f"{pe('warning')} Please provide a valid code.", reply_markup=get_profile_keyboard())
        return

    success, alert_msg, credits_added = await redeem_code_for_user(code_clean, user_id)
    u = await get_or_create_user(user_id)
    has_mail = bool(u.get("email"))
    is_admin = user_id in ADMIN_IDS

    if success:
        reply_text = (
            f"{pe('6129579803600231171')} <b>Code Redeemed Successfully!</b> {pe('6129579803600231171')}\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"• {pe('5240228673738527951')} <b>Code Applied:</b> <code>{code_clean}</code>\n"
            f"• {pe('5438212260763808371')} <b>Credits Added:</b> <b>+{credits_added} Credits</b> {pe('5210952608985923439')}\n"
            f"• {pe('5445353829304387411')} <b>Total Balance:</b> <b>{u.get('credits', 0)} Credits</b>\n\n"
            f"{pe('6129792056589031358')} You can now generate disposable emails and receive instant OTPs!"
        )
        await message.reply(
            reply_text,
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_keyboard(has_email=has_mail, is_admin=is_admin)
        )
    else:
        if "Invalid Redeem Code" in alert_msg:
            err_line = f"{pe('6267000941547885720')} {alert_msg}"
        else:
            err_line = f"{pe('warning')} {alert_msg}"

        await message.reply(
            f"{pe('6267039884016358504')} <b>Redemption Failed:</b>\n\n{err_line}",
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_keyboard(has_email=has_mail, is_admin=is_admin)
        )

# --- ADMIN REDEEM CODE CONTROLS ---

@dp.callback_query(F.data == "admin_redeem_manage")
async def cb_admin_redeem_manage(callback: CallbackQuery):
    """Admin menu to view and manage redeem codes."""
    clear_user_states(callback.from_user.id)
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("Admin access required!", show_alert=True)
    await callback.answer()
    codes = await get_all_redeem_codes()
    text = (
        f"{pe('gift')} <b>Admin Redeem Code Manager</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
    )
    if not codes:
        text += "<i>No redeem codes created yet. Tap below to create your first code!</i>\n"
    else:
        text += f"Total Codes: <b>{len(codes)}</b>\n\n"
        for c in codes[:12]:
            code = c["code"]
            credits_val = c.get("credits", 1)
            used = c.get("redeemed_count", 0)
            max_u = c.get("max_users", 0)
            is_act = c.get("is_active", 1)
            status_icon = "🟢" if is_act and used < max_u else "🔴"
            text += f"{status_icon} <code>{code}</code> ➔ <b>+{credits_val} Credits</b> | 👥 <b>{used}/{max_u} Claimed</b>\n"

    await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=get_admin_redeem_keyboard())

@dp.callback_query(F.data == "admin_create_redeem")
async def cb_admin_create_redeem(callback: CallbackQuery):
    """Initiate multi-step redeem code creation."""
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("Admin access required!", show_alert=True)
    user_id = callback.from_user.id
    clear_user_states(user_id)
    ADMIN_CREATE_REDEEM_STATE[user_id] = {"step": "code"}
    await callback.answer()
    text = (
        f"{pe('5240228673738527951')} <b>Create Redeem Code [Step 1/3]</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📝 <b>1. Code Name / Text:</b>\n"
        f"Pehle kis <b>Name</b> ka redeem code banana hai, wo likh kar bhejiye:\n\n"
        f"• <i>Example:</i> <code>WELCOME50</code> ya <code>VIP100</code>\n"
        f"• <i>Ya</i> <code>auto</code> <i>bhejiye random code generate karne ke liye.</i>"
    )
    await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=get_cancel_redeem_keyboard())

@dp.callback_query(F.data == "admin_delete_redeem_list")
async def cb_admin_delete_redeem_list(callback: CallbackQuery):
    """Display list of codes to delete."""
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("Admin access required!", show_alert=True)
    clear_user_states(callback.from_user.id)
    codes = await get_all_redeem_codes()
    if not codes:
        return await callback.answer("No redeem codes exist to delete!", show_alert=True)
    await callback.answer()
    text = (
        f"🗑️ <b>Delete Redeem Code:</b>\n\n"
        f"Tap any code below to delete it permanently from the database:"
    )
    await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=get_delete_redeem_list_keyboard(codes))

@dp.callback_query(F.data.startswith("del_code:"))
async def cb_del_code(callback: CallbackQuery):
    """Delete a specific redeem code."""
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("Admin access required!", show_alert=True)
    clear_user_states(callback.from_user.id)
    target_code = callback.data.split(":", 1)[1].strip()
    await delete_redeem_code(target_code)
    await callback.answer(f"Code {target_code} deleted successfully!", show_alert=True)
    await cb_admin_redeem_manage(callback)

@dp.callback_query(F.data == "cancel_redeem_action")
async def cb_cancel_redeem_action(callback: CallbackQuery):
    """Cancel any active redeem code action."""
    user_id = callback.from_user.id
    clear_user_states(user_id)
    await callback.answer("Action cancelled.")
    if user_id in ADMIN_IDS:
        await cb_admin_redeem_manage(callback)
    else:
        u = await get_or_create_user(user_id)
        await callback.message.edit_text(
            f"{pe('info')} <b>Redemption cancelled.</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_keyboard(has_email=bool(u.get("email")), is_admin=False)
        )

async def process_admin_create_redeem_step(message: Message, text: str):
    """Handle sequential 3-step text input when admin is creating a redeem code."""
    user_id = message.from_user.id
    state = ADMIN_CREATE_REDEEM_STATE.get(user_id)
    if not state:
        return

    step = state.get("step")

    # Step 1: Code Name
    if step == "code":
        raw_code = text.strip()
        if raw_code.lower() == "auto":
            code_name = "GIFT-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
        else:
            code_name = "".join(c for c in raw_code if c.isalnum() or c in "_-").upper()

        if not code_name:
            await message.reply(
                f"{pe('warning')} Code name invalid hai. Please valid code name bhejiye (e.g. <code>SPECIAL50</code>):",
                parse_mode=ParseMode.HTML,
                reply_markup=get_cancel_redeem_keyboard()
            )
            return

        ADMIN_CREATE_REDEEM_STATE[user_id] = {"step": "credits", "code": code_name}
        await message.reply(
            f"🎟️ <b>Code Name:</b> <code>{code_name}</code> ✅\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{pe('5438212260763808371')} <b>Create Redeem Code [Step 2/3]</b>\n\n"
            f"🪙 <b>2. Credits Amount:</b>\n"
            f"Ye code claim karne par har user ko <b>kitne email credits</b> milne chahiye?\n\n"
            f"• <i>Example:</i> <code>5</code> (har user ko 5 credits milenge)",
            parse_mode=ParseMode.HTML,
            reply_markup=get_cancel_redeem_keyboard()
        )
        return

    # Step 2: Credits per user
    if step == "credits":
        if not text.isdigit() or int(text) <= 0:
            await message.reply(
                f"{pe('warning')} Please valid positive number bhejiye credits ke liye (e.g. <code>5</code>):",
                parse_mode=ParseMode.HTML,
                reply_markup=get_cancel_redeem_keyboard()
            )
            return
        credits_val = int(text)
        code_name = state.get("code")
        ADMIN_CREATE_REDEEM_STATE[user_id] = {"step": "max_users", "code": code_name, "credits": credits_val}
        await message.reply(
            f"🎟️ <b>Code Name:</b> <code>{code_name}</code> ✅\n"
            f"{pe('5438212260763808371')} <b>Credits:</b> <code>+{credits_val} Credits</code> ✅\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{pe('5445353829304387411')} <b>Create Redeem Code [Step 3/3]</b>\n\n"
            f"👥 <b>3. Total Valid Users:</b>\n"
            f"Ye code total <b>kitne users</b> ke liye valid hona chahiye?\n\n"
            f"• <i>Example:</i> <code>50</code> (first 50 users claim kar sakenge)",
            parse_mode=ParseMode.HTML,
            reply_markup=get_cancel_redeem_keyboard()
        )
        return

    # Step 3: Total valid users (max_users)
    if step == "max_users":
        if not text.isdigit() or int(text) <= 0:
            await message.reply(
                f"{pe('warning')} Please valid positive number bhejiye total users ke liye (e.g. <code>50</code>):",
                parse_mode=ParseMode.HTML,
                reply_markup=get_cancel_redeem_keyboard()
            )
            return
        max_users_val = int(text)
        code_name = state.get("code")
        credits_val = state.get("credits", 1)
        ADMIN_CREATE_REDEEM_STATE.pop(user_id, None)

        ok, resp = await create_redeem_code(code_name, credits_val, max_users_val)
        if ok:
            promo_text = (
                f"{pe('5438212260763808371')} <b>Special Redeem Code Alert!</b>\n\n"
                f"Use code <code>{code_name}</code> in @{BOT_USERNAME} to get <b>+{credits_val} Free Email Credits</b>!\n\n"
                f"⚡ Valid for the first <b>{max_users_val} users</b> only. Claim now!"
            )
            await message.reply(
                f"{pe('verified')} <b>Redeem Code Created Successfully!</b> {pe('party')}\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"• {pe('5240228673738527951')} <b>Code Name:</b> <code>{code_name}</code>\n"
                f"• {pe('5438212260763808371')} <b>Credits Amount:</b> <code>+{credits_val} Credits</code>\n"
                f"• {pe('5445353829304387411')} <b>Total Valid Users:</b> <code>{max_users_val} Users</code>\n\n"
                f"📋 <b>Ready to forward promotion message:</b>\n"
                f"<blockquote>{promo_text}</blockquote>",
                parse_mode=ParseMode.HTML,
                reply_markup=get_admin_redeem_keyboard()
            )
        else:
            await message.reply(
                f"{pe('cross')} <b>Failed to create code:</b>\n{resp}",
                parse_mode=ParseMode.HTML,
                reply_markup=get_admin_redeem_keyboard()
            )
        return

@dp.message(Command("addcredits"))
async def cmd_addcredits(message: Message, bot: Bot):
    """Admin command to add credits to a user."""
    if message.from_user.id not in ADMIN_IDS:
        return

    parts = message.text.split()
    if len(parts) < 3 or not parts[1].isdigit() or not parts[2].isdigit():
        await message.reply(f"{pe('warning')} Invalid format. Use:\n<code>/addcredits &lt;user_id&gt; &lt;amount&gt;</code>", parse_mode=ParseMode.HTML)
        return

    target_user_id = int(parts[1])
    amount = int(parts[2])

    new_bal = await add_user_credits(target_user_id, amount)
    await message.reply(
        f"{pe('verified')} <b>Success!</b>\n\n"
        f"Given <b>+{amount} Credits</b> to user <code>{target_user_id}</code>.\n"
        f"New Balance: <code>{new_bal}</code> Emails {pe('fire')}",
        parse_mode=ParseMode.HTML
    )

    # Notify target user
    try:
        await bot.send_message(
            chat_id=target_user_id,
            text=f"{pe('gift')} <b>Admin Gift!</b> {pe('fire')}\n\nYou received <b>+{amount} Email Credits</b> from admin!\n🎟️ New Balance: <code>{new_bal}</code> Emails {pe('verified')}",
            parse_mode=ParseMode.HTML
        )
    except Exception:
        pass

@dp.message(Command("user"))
async def cmd_user_info(message: Message):
    """Admin command to lookup user details."""
    if message.from_user.id not in ADMIN_IDS:
        return

    parts = message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.reply(f"{pe('warning')} Format: <code>/user &lt;user_id&gt;</code>", parse_mode=ParseMode.HTML)
        return

    target_user_id = int(parts[1])
    u = await get_user(target_user_id)
    if not u:
        await message.reply(f"{pe('cross')} User not found.")
        return

    text = (
        f"{pe('user')} <b>User Details:</b>\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"{pe('pin')} <b>User ID:</b> <code>{u['user_id']}</code>\n"
        f"{pe('email')} <b>Active Email:</b> <code>{u.get('email') or 'None'}</code>\n"
        f"{pe('globe')} <b>Domain:</b> <code>@{u.get('domain') or 'None'}</code>\n"
        f"{pe('card')} <b>Credits:</b> <code>{u.get('credits', 0)}</code>\n"
        f"{pe('handshake')} <b>Referrals:</b> <code>{u.get('referrals_count', 0)}</code>\n"
        f"{pe('user')} <b>Referred By:</b> <code>{u.get('referred_by') or 'None'}</code>\n"
        f"{pe('shield')} <b>Is Banned:</b> {'Yes' if u.get('is_banned') else 'No'}\n"
        f"{pe('time')} <b>Joined At:</b> {u.get('created_at')}"
    )
    await message.reply(text, parse_mode=ParseMode.HTML)

@dp.message(Command("ban"))
async def cmd_ban(message: Message):
    """Ban a user."""
    if message.from_user.id not in ADMIN_IDS:
        return
    parts = message.text.split()
    if len(parts) >= 2 and parts[1].isdigit():
        uid = int(parts[1])
        await set_user_ban(uid, 1)
        await message.reply(f"{pe('cross')} User <code>{uid}</code> has been banned.", parse_mode=ParseMode.HTML)

@dp.message(Command("unban"))
async def cmd_unban(message: Message):
    """Unban a user."""
    if message.from_user.id not in ADMIN_IDS:
        return
    parts = message.text.split()
    if len(parts) >= 2 and parts[1].isdigit():
        uid = int(parts[1])
        await set_user_ban(uid, 0)
        await message.reply(f"{pe('verified')} User <code>{uid}</code> has been unbanned.", parse_mode=ParseMode.HTML)

@dp.message(Command("broadcast"))
async def cmd_broadcast(message: Message, bot: Bot):
    """Direct command broadcast to all users."""
    if message.from_user.id not in ADMIN_IDS:
        return

    broadcast_text = message.text.replace("/broadcast", "", 1).strip()
    if not broadcast_text:
        await message.reply(f"{pe('warning')} Message missing. Use: <code>/broadcast Your message here</code>", parse_mode=ParseMode.HTML)
        return

    await execute_broadcast(bot, message.from_user.id, broadcast_text, message)

async def execute_broadcast(bot: Bot, admin_id: int, broadcast_text: str, reply_target: Message):
    """Send broadcast to all registered bot users."""
    user_ids = await get_all_user_ids()
    total = len(user_ids)
    sent = 0
    failed = 0

    progress_msg = await reply_target.reply(f"{pe('broadcast')} <b>Broadcasting started...</b> (Total: {total})", parse_mode=ParseMode.HTML)

    for uid in user_ids:
        try:
            await bot.send_message(
                chat_id=uid,
                text=broadcast_text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)

    await progress_msg.edit_text(
        f"{pe('verified')} <b>Broadcast Completed Successfully!</b> {pe('party')}\n\n"
        f"{pe('stats')} <b>Stats:</b>\n"
        f"• {pe('user')} Total Users: <code>{total}</code>\n"
        f"• 📤 Sent Successfully: <code>{sent}</code> {pe('check')}\n"
        f"• {pe('cross')} Failed: <code>{failed}</code>",
        parse_mode=ParseMode.HTML
    )

@dp.message(Command("channels"))
async def cmd_channels(message: Message):
    """List all force join channels for admin."""
    if message.from_user.id not in ADMIN_IDS:
        return
    channels = await get_force_channels()
    if not channels:
        await message.reply(f"{pe('info')} No force join channels configured currently.")
        return
    text = f"{pe('lock')} <b>Active Force Join Channels:</b>\n\n"
    for ch in channels:
        text += f"• <b>{html.escape(ch.get('title') or '')}</b> (ID: <code>{ch['id']}</code>, Chat: <code>{ch['chat_id']}</code>)\n  {pe('link')} Link: {ch['invite_link']}\n"
    await message.reply(text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)

@dp.message(Command("addchannel"))
async def cmd_addchannel(message: Message, bot: Bot):
    """Command to add force join channel."""
    if message.from_user.id not in ADMIN_IDS:
        return
    raw_input = message.text.replace("/addchannel", "", 1).strip()
    if not raw_input:
        await message.reply(f"{pe('warning')} Format: <code>/addchannel @channel_username</code>", parse_mode=ParseMode.HTML)
        return
    await process_add_channel(bot, message, raw_input)

@dp.message(Command("delchannel"))
async def cmd_delchannel(message: Message):
    """Command to delete force join channel."""
    if message.from_user.id not in ADMIN_IDS:
        return
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply(f"{pe('warning')} Format: <code>/delchannel &lt;channel_id_or_username&gt;</code>", parse_mode=ParseMode.HTML)
        return
    target = parts[1].strip()
    if target.isdigit():
        await remove_force_channel(int(target))
        await message.reply(f"{pe('verified')} Channel ID <code>{target}</code> removed successfully.", parse_mode=ParseMode.HTML)
    else:
        await remove_force_channel_by_chat_id(target)
        await message.reply(f"{pe('verified')} Channel <code>{target}</code> removed successfully.", parse_mode=ParseMode.HTML)

async def process_add_channel(bot: Bot, message: Message, raw_input: str):
    """Resolve channel information and add to database."""
    parts = raw_input.strip().split()
    target = parts[0].strip()

    if "t.me/" in target:
        target = "@" + target.split("t.me/")[-1].replace("/", "").strip()

    try:
        chat = await bot.get_chat(target)
        chat_id_str = str(chat.id)
        title = chat.title or (f"@{chat.username}" if chat.username else chat_id_str)
        c_type = "group" if chat.type in ["group", "supergroup"] else "channel"

        if chat.username:
            invite_link = f"https://t.me/{chat.username}"
        elif len(parts) > 1 and parts[1].startswith("http"):
            invite_link = parts[1].strip()
        elif chat.invite_link:
            invite_link = chat.invite_link
        else:
            try:
                invite_link = await bot.export_chat_invite_link(chat.id)
            except Exception:
                invite_link = f"https://t.me/{target.lstrip('@')}"

        if len(parts) > 2:
            title = " ".join(parts[2:])

        await add_force_channel(
            chat_id=chat_id_str,
            title=title,
            invite_link=invite_link,
            chat_type=c_type
        )

        await message.reply(
            f"{pe('verified')} <b>Channel Added Successfully!</b> {pe('party')}\n\n"
            f"• <b>Title:</b> {html.escape(title)}\n"
            f"• <b>Type:</b> {pe('handshake') if c_type == 'group' else pe('broadcast')} {'Group' if c_type == 'group' else 'Channel'}\n"
            f"• <b>Chat ID:</b> <code>{chat_id_str}</code>\n"
            f"• <b>Link:</b> {invite_link}\n\n"
            f"{pe('lock')} All new users must now join this channel before using the bot.",
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.error(f"Error adding channel {target}: {e}")
        if (target.startswith("-100") or target.isdigit()) and len(parts) >= 2:
            invite_link = parts[1]
            title = " ".join(parts[2:]) if len(parts) > 2 else f"Channel {target}"
            await add_force_channel(target, title, invite_link, "channel")
            await message.reply(
                f"{pe('verified')} <b>Private Channel Added!</b>\n\n"
                f"• <b>Title:</b> {html.escape(title)}\n"
                f"• <b>Chat ID:</b> <code>{target}</code>\n"
                f"• <b>Link:</b> {invite_link}",
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
        else:
            await message.reply(
                f"{pe('cross')} <b>Could not access channel!</b>\n\n"
                f"<b>Error:</b> <code>{html.escape(str(e))}</code>\n\n"
                f"{pe('bulb')} <i>Please check:</i>\n"
                f"1. Is the bot an <b>Admin</b> in that channel/group?\n"
                f"2. Is the username or invite link valid?",
                parse_mode=ParseMode.HTML
            )

@dp.message(F.text & ~F.text.startswith("/"))
async def handle_admin_text_input(message: Message, bot: Bot):
    """Intercept text messages for admin prompts and user interactive flows."""
    user_id = message.from_user.id
    text = message.text.strip()

    # 1. Admin operations have absolute top priority for Admins
    if user_id in ADMIN_IDS:
        # Check admin search user mails state
        if user_id in ADMIN_SEARCH_USER_MAILS_STATE:
            ADMIN_SEARCH_USER_MAILS_STATE.discard(user_id)
            if not text.isdigit():
                await message.reply(f"{pe('warning')} Please send a valid numeric Telegram User ID.")
                return
            target_uid = int(text)
            await show_admin_mails_view(user_id, message, page=0, target_user_id=target_uid, is_callback=False)
            return

        # Check admin create redeem code multi-step state
        if user_id in ADMIN_CREATE_REDEEM_STATE:
            USER_REDEEM_STATE.discard(user_id)
            await process_admin_create_redeem_step(message, text)
            return

        # Check button text edit state
        if user_id in ADMIN_EDIT_TEXT_STATE:
            USER_REDEEM_STATE.discard(user_id)
            btn_key = ADMIN_EDIT_TEXT_STATE.pop(user_id)
            new_text = message.text.strip()
            if not new_text:
                await message.reply(f"{pe('cross')} Button text cannot be empty.")
                ADMIN_EDIT_TEXT_STATE[user_id] = btn_key
                return

            await set_button_text(btn_key, new_text)
            update_button_texts_cache({btn_key: new_text})

            target_cat = "cat_main"
            for c_k, c_d in BUTTON_CATEGORIES.items():
                if btn_key in c_d["keys"]:
                    target_cat = c_k
                    break

            await message.reply(
                f"✅ <b>Button Text Updated!</b> 🎉\n\n"
                f"• <b>Button Key:</b> <code>{btn_key}</code>\n"
                f"• <b>New Text:</b> <b>{html.escape(new_text)}</b>\n\n"
                f"All bot users will now see this label on the button!",
                parse_mode=ParseMode.HTML,
                reply_markup=get_admin_texts_buttons_keyboard(target_cat)
            )
            return

        # Check button emoji edit state
        if user_id in ADMIN_EDIT_BTN_STATE:
            USER_REDEEM_STATE.discard(user_id)
            btn_key = ADMIN_EDIT_BTN_STATE.pop(user_id)

            # 1. Try extracting custom_emoji_id from message entities (Direct Telegram Premium Emoji from keyboard)
            extracted_emoji_id = None
            if message.entities:
                for entity in message.entities:
                    if entity.type == "custom_emoji" and hasattr(entity, "custom_emoji_id") and entity.custom_emoji_id:
                        extracted_emoji_id = str(entity.custom_emoji_id)
                        break

            # 2. If not an entity, check if admin sent numeric custom emoji ID
            if not extracted_emoji_id:
                cleaned = message.text.strip()
                if cleaned.isdigit():
                    extracted_emoji_id = cleaned

            if not extracted_emoji_id:
                await message.reply(
                    f"{pe('cross')} <b>Invalid Emoji!</b>\n\n"
                    f"Please send either:\n"
                    f"• A <b>Telegram Premium Emoji</b> directly from your keyboard, or\n"
                    f"• A numeric <b>Custom Emoji ID</b> (e.g. <code>5472239203590888751</code>).",
                    parse_mode=ParseMode.HTML
                )
                ADMIN_EDIT_BTN_STATE[user_id] = btn_key
                return

            # Save to database and update cache
            await set_button_emoji(btn_key, extracted_emoji_id)
            update_button_emojis_cache({btn_key: extracted_emoji_id})
            btn_title = BUTTON_NAMES.get(btn_key, btn_key)

            # Find category of this button
            target_cat = "cat_main"
            for c_k, c_d in BUTTON_CATEGORIES.items():
                if btn_key in c_d["keys"]:
                    target_cat = c_k
                    break

            await message.reply(
                f"{pe('verified')} <b>Button Emoji Updated!</b> {pe('party')}\n\n"
                f"• <b>Button:</b> {btn_title} (<code>{btn_key}</code>)\n"
                f"• <b>New Emoji:</b> {pe(extracted_emoji_id)} (ID: <code>{extracted_emoji_id}</code>)\n\n"
                f"All bot users will now see this new emoji on the button!",
                parse_mode=ParseMode.HTML,
                reply_markup=get_admin_category_buttons_keyboard(target_cat)
            )
            return

        # Check broadcast state
        if user_id in ADMIN_BROADCAST_STATE:
            USER_REDEEM_STATE.discard(user_id)
            ADMIN_BROADCAST_STATE.discard(user_id)
            await execute_broadcast(bot, user_id, message.text, message)
            return

        # Check Force Join add state
        if user_id in ADMIN_ADD_FSUB_STATE:
            USER_REDEEM_STATE.discard(user_id)
            ADMIN_ADD_FSUB_STATE.discard(user_id)
            await process_add_channel(bot, message, message.text)
            return

    # 2. User Redeem Flow State (Only active if user clicked Redeem Code button and NOT executing an admin flow)
    if user_id in USER_REDEEM_STATE:
        USER_REDEEM_STATE.discard(user_id)
        await execute_user_redeem(message, text)
        return

@dp.message(Command("setbtnemoji"))
async def cmd_setbtnemoji(message: Message):
    """Direct command to set emoji for a button: /setbtnemoji <button_key> <emoji_or_id>"""
    if message.from_user.id not in ADMIN_IDS:
        return

    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        valid_keys = ", ".join([f"<code>{k}</code>" for k in BUTTON_NAMES.keys()])
        await message.reply(
            f"{pe('warning')} <b>Format:</b> <code>/setbtnemoji &lt;button_key&gt; &lt;emoji_or_id&gt;</code>\n\n"
            f"<b>Available Button Keys:</b>\n{valid_keys}",
            parse_mode=ParseMode.HTML
        )
        return

    btn_key = parts[1].strip().lower()
    if btn_key not in BUTTON_NAMES:
        valid_keys = ", ".join([f"<code>{k}</code>" for k in BUTTON_NAMES.keys()])
        await message.reply(f"{pe('cross')} Unknown button key <code>{btn_key}</code>. Available: {valid_keys}", parse_mode=ParseMode.HTML)
        return

    extracted_emoji_id = None
    if message.entities:
        for entity in message.entities:
            if entity.type == "custom_emoji" and hasattr(entity, "custom_emoji_id") and entity.custom_emoji_id:
                extracted_emoji_id = str(entity.custom_emoji_id)
                break

    if not extracted_emoji_id:
        val = parts[2].strip()
        if val.isdigit():
            extracted_emoji_id = val

    if not extracted_emoji_id:
        await message.reply(f"{pe('cross')} Invalid emoji ID provided.", parse_mode=ParseMode.HTML)
        return

    await set_button_emoji(btn_key, extracted_emoji_id)
    update_button_emojis_cache({btn_key: extracted_emoji_id})
    await message.reply(
        f"{pe('verified')} Emoji for button <b>{BUTTON_NAMES[btn_key]}</b> set to {pe(extracted_emoji_id)} (ID: <code>{extracted_emoji_id}</code>).",
        parse_mode=ParseMode.HTML
    )

@dp.message(Command("resetbtnemojis"))
async def cmd_resetbtnemojis(message: Message):
    """Admin command to reset all button emojis back to defaults."""
    if message.from_user.id not in ADMIN_IDS:
        return
    await reset_all_button_emojis()
    reset_button_emojis_cache()
    await message.reply(
        f"{pe('verified')} <b>All button emojis have been reset to factory defaults!</b>",
        parse_mode=ParseMode.HTML
    )

@dp.message(Command("resetbtncolors"))
async def cmd_resetbtncolors(message: Message):
    """Admin command to reset all button colors back to defaults."""
    if message.from_user.id not in ADMIN_IDS:
        return
    await reset_all_button_colors()
    reset_button_colors_cache()
    await message.reply(
        f"{pe('verified')} <b>All button colors have been reset to factory defaults!</b>",
        parse_mode=ParseMode.HTML
    )

@dp.message(Command("resetbtntexts"))
async def cmd_resetbtntexts(message: Message):
    """Admin command to reset all button texts back to defaults."""
    if message.from_user.id not in ADMIN_IDS:
        return
    await reset_all_button_texts()
    reset_button_texts_cache()
    await message.reply(
        f"{pe('verified')} <b>All button texts have been reset to factory defaults!</b>",
        parse_mode=ParseMode.HTML
    )

# ============================================
# BOT SETUP & RUNNER
# ============================================

async def setup_bot_commands(bot: Bot):
    """Configure the blue Menu button in Telegram chat."""
    commands = [
        BotCommand(command="start", description="🚀 Start Bot & Main Menu"),
        BotCommand(command="new", description="📧 Generate Temp Email"),
        BotCommand(command="inbox", description="📬 Check Inbox & OTPs"),
        BotCommand(command="profile", description="👤 Profile & Balance"),
        BotCommand(command="leaderboard", description="🏆 Referral Leaderboard"),
        BotCommand(command="refer", description="🎁 Refer & Earn (+1 Credit)"),
        BotCommand(command="redeem", description="🎟️ Redeem Promo / Gift Code"),
        BotCommand(command="delete", description="🗑️ Delete Current Email"),
        BotCommand(command="help", description="ℹ️ How to Use Guide"),
        BotCommand(command="admin", description="⚙️ Admin Panel (For Admins)")
    ]
    try:
        await bot.set_my_commands(commands)
        await bot.set_chat_menu_button(menu_button=MenuButtonCommands())
        logger.info("Bot commands and Menu button configured successfully.")
    except Exception as e:
        logger.error(f"Error configuring bot commands: {e}")

async def main():
    """Main entrypoint for bot."""
    ensure_single_instance()
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is missing! Please configure BOT_TOKEN in .env file.")
        return

    # Initialize Database & load button customizers
    await init_db()
    btn_emojis = await get_button_emojis()
    update_button_emojis_cache(btn_emojis)
    btn_colors = await get_button_colors()
    update_button_colors_cache(btn_colors)
    btn_texts = await get_button_texts()
    update_button_texts_cache(btn_texts)

    bot = Bot(token=BOT_TOKEN, session=CustomAiohttpSession(), default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    # Dynamically resolve active bot username for referral links
    try:
        bot_info = await bot.get_me()
        if bot_info and bot_info.username:
            import config
            config.BOT_USERNAME = bot_info.username
            global BOT_USERNAME
            BOT_USERNAME = bot_info.username
    except Exception:
        pass

    # Configure Telegram Menu button & commands
    await setup_bot_commands(bot)

    # Start background inbox watcher
    asyncio.create_task(run_inbox_watcher(bot))

    logger.info("Bot is starting polling...")
    print("\n✅ Multi-Domain Temp Mail & Auto OTP Bot with Referral & Admin Panel is RUNNING!")

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        await mail_service.close()

if __name__ == "__main__":
    asyncio.run(main())
