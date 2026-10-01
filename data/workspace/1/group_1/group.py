import asyncio
import aiohttp
import json
import re
import logging
import base64
import os
import html
import ipaddress
import time
import threading
import sys
import signal
from contextlib import suppress
from functools import wraps
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timedelta
from collections import deque
from typing import Optional, Dict, List, Any, Union, Tuple
from urllib.parse import parse_qsl, quote_plus, urlencode, urlsplit, urlunsplit
from telegram import (
    Update,
    InlineKeyboardButton as TelegramInlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardRemove,
    BotCommand,
    BotCommandScopeDefault,
    BotCommandScopeChat,
    MenuButtonCommands,
    MenuButtonDefault,
)
from telegram.constants import ParseMode, ChatType
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler
from telegram.error import RetryAfter, TelegramError

# ==================== PYTHON 3.11+ COMPATIBILITY ====================
try:
    sys.set_int_max_str_digits(0)
except AttributeError:
    pass

# ==================== SIGNAL HANDLING FOR PYTHON 3.11 ====================
def setup_signal_handlers(loop):
    def signal_handler():
        logger.info("Received shutdown signal, cleaning up...")
        asyncio.create_task(cleanup_on_shutdown())
    
    try:
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, signal_handler)
    except (NotImplementedError, RuntimeError):
        pass

async def cleanup_on_shutdown():
    global HTTP_SESSION
    logger.info("Cleaning up resources...")
    if HTTP_SESSION and not HTTP_SESSION.closed:
        await HTTP_SESSION.close()
    logger.info("Cleanup completed")

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

# -------------------- LOGGING --------------------
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# -------------------- CONFIGURATION --------------------
BOT_TOKEN: str = os.environ.get("BOT_TOKEN", "8326786598:AAGMWhqUcKh_JCHS1O8n4TLCbXbaaaX94A0").strip()
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is required. Add it as an environment secret before starting the bot.")
ADMIN_ID: int = 6566593716
DB_FILE: str = "database.json"
USERS_PER_PAGE: int = 15
PORT: int = int(os.environ.get("PORT", 8080))

BLACKLISTED_NUMBERS: List[str] = ["6352329758", "916352329758", "+916352329758", "6566593716"]
BLACKLISTED_IDS: List[str] = ["6352329758", "6566593716"]

_NUM_API_URL: str = os.environ.get(
    "NUM_API_URL",
    "https://auraxinfo-production.up.railway.app/api?key=auraontop&type=mobile&term={number}",
).strip()
if "uersxinfo" in _NUM_API_URL or not _NUM_API_URL:
    _NUM_API_URL = "https://auraxinfo-production.up.railway.app/api?key=auraontop&type=mobile&term={number}"
TG_LOOKUP_API_URL: str = os.environ.get(
    "TG_LOOKUP_API_URL",
    "https://auraxinfo-production.up.railway.app/api?key=auraontop&type=tg&term=",
).strip()
LEAK_API_URL: str = os.environ.get("LEAK_API_URL", "").strip()
LEAK_API_KEY: str = os.environ.get("LEAK_API_KEY", "").strip()

# OSINT API Configuration (used by /leak and /email)
OSINT_API_URL: str = os.environ.get(
    "OSINT_API_URL",
    "https://auraxinfo-production.up.railway.app/api?key=auraontop&type=osint&term={term}",
).strip()
PHONE_LOOKUP_API_URL: str = os.environ.get("PHONE_LOOKUP_API_URL", "").strip()
IP_INFO_API_URL: str = os.environ.get(
    "IP_INFO_API_URL",
    "http://ip-api.com/json/{ip}?fields=status,message,continent,continentCode,country,countryCode,region,regionName,city,district,zip,lat,lon,timezone,offset,currency,isp,org,as,asname,reverse,mobile,proxy,hosting",
).strip()

# Free Fire player info API
FF_INFO_API_URL: str = os.environ.get(
    "FF_INFO_API_URL",
    "https://ff-info-drsudo.vercel.app/api/player-info?id={uid}",
).strip()

# Vehicle API Configuration
VEHICLE_API_URL: str = os.environ.get(
    "VEHICLE_API_URL",
    "https://auraxinfo-production.up.railway.app/api",
).strip()
VEHICLE_API_KEY: str = os.environ.get("VEHICLE_API_KEY", "auraowner").strip()

# Aadhaar API Configuration
AADHAAR_API_URL: str = os.environ.get(
    "AADHAAR_API_URL",
    "https://auraxinfo-production.up.railway.app/api?key=auraontop&type=aadhaar&term={aadhaar}",
).strip()

# Number to Vehicle API Configuration
NUM2VEH_API_URL: str = os.environ.get(
    "NUM2VEH_API_URL",
    "https://auraxinfo-production.up.railway.app/api?key=auraontop&type=num_vehicle&term={number}",
).strip()

# -------------------- COLORED INLINE BUTTONS --------------------
BUTTON_EMOJI_IDS: Dict[str, str] = {
    "primary": os.environ.get("PRIMARY_BUTTON_EMOJI_ID", "").strip(),
    "success": os.environ.get("SUCCESS_BUTTON_EMOJI_ID", "").strip(),
    "danger": os.environ.get("DANGER_BUTTON_EMOJI_ID", "").strip(),
    "admin": os.environ.get("ADMIN_BUTTON_EMOJI_ID", "5447259175581132372").strip(),
}

ADMIN_PANEL_BUTTON_EMOJI_IDS: Dict[str, str] = {
    "broadcast": "5298609030321691620",
    "broadcast_pin": "6267129592998270736",
    "pin_active_broadcast": "6267172559851099903",
    "total_users": "5334756265358798915",
    "total_groups": "5251662946127336150",
    "bot_stats": "6338869823312761767",
    "refresh_db": "6267229004311303657",
    "manage_commands": "6267186750423045640",
    "leak_approvals": "6224532519673401301",
    "approve_user": "6089003761496232797",
    "revoke_user": "6337081879967044997",
    "set_trial_limit": "6093406373557571574",
    "set_trial_user_limit": "6145465006432459177",
    "reset_trial": "6001162025206550903",
    "maintenance_toggle": "6267144651153609853",
    "system_stats": "5231200819986047254",
    "blacklist_manage": "5240241223632954241",
    "view_logs": "5282843764451195532",
    "clear_cache": "5445267414562389170",
    "stop_bot": "5208840468623801290",
    "back_to_start": "5255703720078879038",
    "force_join": "5309789538862774805",
    "force_join_add": "5452155223550223362",
    "force_join_command": "5375540231124566377",
    "start_bot": "5210881166499921911",
}

ADMIN_BUTTON_UPDATED_EMOJI_ID = "5208540237524911208"

MAINTENANCE_MESSAGE_EMOJI_IDS: Dict[str, str] = {
    "header": "6122716050724230012",
    "enabled": "5213147006561692829",
    "disabled": "5208954641739430829",
    "updating": "5391079723449209646",
    "downtime": "5936176489958478278",
}

PUBLIC_LINK_BUTTON_EMOJI_IDS: Dict[str, str] = {
    "add_group": "6120630032353202244",
    "use_here": "6138734238628845209",
}

# The map button uses a premium custom emoji by default. Replace this with
# another valid custom-emoji ID through IP_MAP_BUTTON_EMOJI_ID if desired.
IP_MAP_BUTTON_EMOJI_ID: str = os.environ.get(
    "IP_MAP_BUTTON_EMOJI_ID",
    "5809727966954920776",
).strip()

STATUS_EMOJI_IDS: Dict[str, str] = {
    "bot_name": "5341463333532882949",
    "bot_status": "6338869823312761767",
    "status_value": "6147546996124163718",
    "date": "5251443675161976035",
    "time": "5787488119490088755",
    "speed": "5372917041193828849",
    "availability": "6339125180593346534",
    "system_stats": "6338869823312761767",
    "privacy": "5309789538862774805",
    "admin": "6086639764251873025",
    "join_group": "5309789538862774805",
    "support": "5382241599877044756",
}

WELCOME_EMOJI_ID = "5461151367559141950"

ADMIN_STATUS_EMOJI_IDS: Dict[str, str] = {
    "header": "6102775247713340088",
    "admin": "6086730808968614780",
    "total_users": "6089079919856325971",
    "total_groups": "6338869823312761767",
    "bot_status": "5231200819986047254",
    "status_value": "6087133294648890399",
    "maintenance": "5413398757226076065",
    "trial_limit": "6093421221259514937",
    "trial_user_limit": "6093651105089065114",
    "rate_limits": "5195276510931460616",
    "blacklist": "6086741365998227951",
    "cache": "6096080291347042802",
}

HELP_EMOJI_IDS: Dict[str, str] = {
    "commands_header": "5282989754684547639",
    "command": "5343528160535270636",
    "auto_delete": "6267039884016358504",
    "rate_limit": "6267229004311303657",
}

COMMAND_MANAGER_EMOJI_ID = "6089003761496232797"
COMMAND_STATUS_BUTTON_EMOJI_ID = "5208748315805499400"
FORCE_JOIN_VERIFY_EMOJI_ID = "5208727996315220567"
INVALID_USAGE_EMOJI_ID = "6267039884016358504"
GROUP_ONLY_EMOJI_ID = "6267000941547885720"
INFO_MAX_MESSAGE_SIZE = 3500
INFO_MAX_PARTS = 50

INFO_EMOJI_IDS: Dict[str, str] = {
    "requester": "5193125071618594501",
    "scroll": "6206354659003600828",
    "target": "5332670483210974079",
    "report": "6096080291347042802",
    "agent": "5237728603340300579",
    "auto_delete": "5382194935057372936",
}

AGENT_SIGNATURE = "⬎̸𝂈̽ 𝚨υ꧊𝆅ꝛ̴᧘ ❍ꮗ꒖𝛆꧊𝆅ꝛ̴ 𑩖 -//- ♡꯭〭𝁘〬"

ABOUT_EMOJI_IDS: Dict[str, str] = {
    "header": "5355051922862653659",
    "details": "6267172559851099903",
    "features": "5343528160535270636",
    "security": "6086672466132865380",
    "status": "5231200819986047254",
    "support": "5411285122215332752",
}

# ==================== EMOJI IDS ====================
SEARCHING_EMOJI_ID = "5267415876851744059"
DELETE_CONFIRM_EMOJI_ID = "5775903905498010383"
EMOJI_ADMIN_UNLIMITED = "6089003761496232797"
EMOJI_TRIAL_HEADER = "6089079919856325971"
EMOJI_USED_COUNT = "6089196601232854885"
EMOJI_REMAINING = "5208573171334135523"
EMOJI_TOTAL_USERS = "5258011929993026890"
EMOJI_ERROR_DISABLED = "6267000941547885720"
EMOJI_PAID_REQUIRED = "6267068789146260253"
EMOJI_COMMAND_DISABLED = "6267008582294705964"

def premium_emoji(emoji_id: str, fallback: str) -> str:
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'

def _button_style(text: str, callback_data: Optional[str]) -> str:
    label = text.lower()
    callback = (callback_data or "").lower()
    if (
        callback in {"back_to_start", "stop_bot"}
        or "back" in label
        or "cancel" in label
        or "delete" in label
        or "stop bot" in label
    ):
        return "danger"
    if callback in {"admin_panel", "start_bot"} or label == "🔧 admin panel" or "start bot" in label:
        return "success"
    return "primary"

def InlineKeyboardButton(text: str, **kwargs: Any) -> Any:
    if text.startswith("🔙 "):
        text = text[2:]
    requested_style = kwargs.pop("_style", None)
    requested_emoji_id = kwargs.pop("_emoji_id", None)
    callback_data = kwargs.get("callback_data")
    style = requested_style or _button_style(text, callback_data)
    api_kwargs = {"style": style}
    emoji_id = requested_emoji_id or BUTTON_EMOJI_IDS.get(style)
    if emoji_id:
        api_kwargs["icon_custom_emoji_id"] = emoji_id
    try:
        return TelegramInlineKeyboardButton(text=text, api_kwargs=api_kwargs, **kwargs)
    except TypeError:
        return TelegramInlineKeyboardButton(text=text, **kwargs)

ADMIN_KEYBOARD_TEXT = "Admin Panel"

def admin_inline_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(
            ADMIN_KEYBOARD_TEXT,
            callback_data="admin_panel",
            _style="primary",
            _emoji_id=BUTTON_EMOJI_IDS["admin"],
        )
    ]])

async def show_admin_keyboard(update: Update) -> None:
    if (
        not update.message
        or not update.effective_user
        or not update.effective_chat
        or update.effective_user.id != ADMIN_ID
        or update.effective_chat.type != ChatType.PRIVATE
    ):
        return
    await update.message.reply_text(
        f'<tg-emoji emoji-id="{ADMIN_BUTTON_UPDATED_EMOJI_ID}">✅</tg-emoji> '
        "<b>Admin button updated.</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=ReplyKeyboardRemove(),
    )
    await update.message.reply_text(
        f'<tg-emoji emoji-id="{ADMIN_STATUS_EMOJI_IDS["header"]}">🔧</tg-emoji> '
        "<b>Admin controls</b>\nUse the button below to open the admin panel.",
        parse_mode=ParseMode.HTML,
        reply_markup=admin_inline_keyboard(),
    )

def _g_u() -> str:
    return _NUM_API_URL

def build_num_api_url(base_url: str, phone_number: str) -> str:
    """Build the number lookup URL without corrupting existing query parameters."""
    base_url = base_url.strip()
    encoded_number = quote_plus(phone_number)

    for placeholder in ("{number}", "{phone}", "%s"):
        if placeholder in base_url:
            return base_url.replace(placeholder, encoded_number)

    parts = urlsplit(base_url)
    query_items = parse_qsl(parts.query, keep_blank_values=True)
    replaced_term = False
    normalized_items = []
    for key, value in query_items:
        if key.lower() == "term":
            normalized_items.append((key, phone_number))
            replaced_term = True
        else:
            normalized_items.append((key, value))

    if not replaced_term:
        normalized_items.append(("term", phone_number))

    return urlunsplit((
        parts.scheme,
        parts.netloc,
        parts.path,
        urlencode(normalized_items),
        parts.fragment,
    ))

def build_ff_info_api_url(base_url: str, player_uid: str) -> str:
    """Build the Free Fire player-info URL with a safely encoded UID."""
    base_url = base_url.strip()
    encoded_uid = quote_plus(player_uid)

    if "{uid}" in base_url:
        return base_url.replace("{uid}", encoded_uid)

    parts = urlsplit(base_url)
    query_items = parse_qsl(parts.query, keep_blank_values=True)
    replaced_id = False
    normalized_items = []
    for key, value in query_items:
        if key.lower() == "id":
            normalized_items.append((key, player_uid))
            replaced_id = True
        else:
            normalized_items.append((key, value))

    if not replaced_id:
        normalized_items.append(("id", player_uid))

    return urlunsplit((
        parts.scheme,
        parts.netloc,
        parts.path,
        urlencode(normalized_items),
        parts.fragment,
    ))

def build_ip_info_api_url(base_url: str, ip_address: str) -> str:
    """Build the IP lookup URL without damaging an existing query string."""
    base_url = base_url.strip()
    encoded_ip = quote_plus(ip_address)

    if "{ip}" in base_url:
        return base_url.replace("{ip}", encoded_ip)

    parts = urlsplit(base_url)
    path = parts.path.rstrip("/") + f"/{encoded_ip}"
    return urlunsplit((
        parts.scheme,
        parts.netloc,
        path,
        parts.query,
        parts.fragment,
    ))

ADMIN_USERNAME: str = "@Yourr_aura"
SECRET_GROUP_LINK: str = "https://t.me/+vjbVf1D-lolhNDg1"

API_TIMEOUT: aiohttp.ClientTimeout = aiohttp.ClientTimeout(total=6, connect=3, sock_read=5)
FF_INFO_API_TIMEOUT: aiohttp.ClientTimeout = aiohttp.ClientTimeout(
    total=20,
    connect=5,
    sock_read=15,
)
NUM_API_TIMEOUT: aiohttp.ClientTimeout = aiohttp.ClientTimeout(
    total=45,
    connect=10,
    sock_read=30,
)
NUM_API_MAX_ATTEMPTS = 3
API_CACHE_TTL: int = 300

EMOJI_THEMES: Dict[str, Dict[str, str]] = {
    "normal": {},
    "premium": {
        "✅": "✦",
        "❌": "⨯",
        "⚠️": "◇",
        "🔍": "◈",
        "📊": "▣",
        "👥": "◉",
        "🔧": "✧",
        "🟢": "●",
        "🔴": "●",
        "⏳": "◌",
        "🛡️": "⬢",
        "🚀": "➤",
        "💾": "▤",
        "📝": "▱",
        "🗑️": "⌫",
        "📌": "⌖",
        "🔄": "↻",
    },
}

HTTP_SESSION: Optional[aiohttp.ClientSession] = None
BOT_START_TIME: datetime = datetime.now()
REQUEST_COUNTER: int = 0
RATE_LIMIT_DICT: Dict[int, deque] = {}
LOG_BUFFER: deque = deque(maxlen=100)
API_CACHE: Dict[str, Tuple[Any, float]] = {}

def get_cached_response(key: str) -> Optional[Any]:
    if key in API_CACHE:
        data, timestamp = API_CACHE[key]
        if time.time() - timestamp < API_CACHE_TTL:
            return data
        else:
            del API_CACHE[key]
    return None

def set_cached_response(key: str, data: Any) -> None:
    API_CACHE[key] = (data, time.time())

def clear_cache() -> None:
    API_CACHE.clear()
    add_log("SYSTEM", "API cache cleared")

async def get_session() -> aiohttp.ClientSession:
    global HTTP_SESSION
    if HTTP_SESSION is None or HTTP_SESSION.closed:
        connector = aiohttp.TCPConnector(
            limit=1000,
            ttl_dns_cache=60,
            force_close=False,
            enable_cleanup_closed=True,
            keepalive_timeout=30
        )
        timeout = aiohttp.ClientTimeout(total=30)
        HTTP_SESSION = aiohttp.ClientSession(connector=connector, timeout=timeout)
    return HTTP_SESSION

async def fetch_num_api_response(url: str) -> Tuple[int, str]:
    """Fetch number data with retries for slow or temporarily unavailable APIs."""
    retryable_statuses = {429, 500, 502, 503, 504}
    last_error: Optional[BaseException] = None

    for attempt in range(NUM_API_MAX_ATTEMPTS):
        try:
            session = await get_session()
            async with session.get(url, timeout=NUM_API_TIMEOUT) as response:
                response_body = await response.text()
                if (
                    response.status in retryable_statuses
                    and attempt < NUM_API_MAX_ATTEMPTS - 1
                ):
                    await asyncio.sleep(1.5 * (attempt + 1))
                    continue
                return response.status, response_body
        except (asyncio.TimeoutError, aiohttp.ClientError) as exc:
            last_error = exc
            if attempt < NUM_API_MAX_ATTEMPTS - 1:
                await asyncio.sleep(1.5 * (attempt + 1))
                continue

    if last_error is not None:
        raise last_error
    raise RuntimeError("Number API request failed after retries")

# ==================== DELETE HELPER ====================
async def delete_info_after(bot, chat_id: int, message_id: int, delay: int, part_info: str = "") -> None:
    await asyncio.sleep(delay)
    try:
        chat = await bot.get_chat(chat_id)
        bot_member = await bot.get_chat_member(chat_id=chat_id, user_id=bot.id)
        can_delete = (
            bot_member.status in {"administrator", "creator"}
            and bool(getattr(bot_member, "can_delete_messages", False))
        )
        
        if not can_delete:
            await bot.send_message(
                chat_id=chat_id,
                text="⚠️ <b>Auto‑delete failed</b>\nI don't have permission to delete messages in this group.\nPlease make me an admin with 'Delete messages' right.",
                parse_mode=ParseMode.HTML
            )
            return

        await bot.delete_message(chat_id=chat_id, message_id=message_id)

        if part_info:
            confirm_text = (
                f'<tg-emoji emoji-id="{DELETE_CONFIRM_EMOJI_ID}">🗑️</tg-emoji> '
                f"<b>{part_info} Information Deleted Successfully</b>"
            )
        else:
            confirm_text = (
                f'<tg-emoji emoji-id="{DELETE_CONFIRM_EMOJI_ID}">🗑️</tg-emoji> '
                "<b>Information Deleted Successfully</b>"
            )

        await bot.send_message(
            chat_id=chat_id, 
            text=confirm_text, 
            parse_mode=ParseMode.HTML
        )

    except Exception as e:
        logger.error(f"Delete error in chat {chat_id}: {e}")
        if "message can't be deleted" in str(e).lower():
            await bot.send_message(
                chat_id=chat_id,
                text="❌ Could not delete message. It may be too old or I don't have enough rights.",
                parse_mode=ParseMode.HTML
            )

# -------------------- DATABASE --------------------
def load_db() -> Dict[str, Any]:
    if not os.path.exists(DB_FILE):
        return {"users": [], "groups": [], "disabled_commands": [], "leak_approvals": [], 
                "trial_usage": {}, "trial_limit": 2, "trial_user_limit": 0, "trial_users": [],
                "maintenance_mode": False, "blacklisted_numbers": [], "bot_offline": False,
                "last_broadcast": [], "force_join_targets": []}
    try:
        with open(DB_FILE, "r") as f:
            data = json.load(f)
            defaults = {
                "approved_groups": [],
                "approved_groups_meta": {},
                "official_group_id": None,
                "official_group_link": SECRET_GROUP_LINK,
                "group_alert_msg": "",
                "group_alert_btn_text": "🚀 JOIN OFFICIAL GROUP",
                "group_alert_btn_emoji": "6138734238628845209",
                "disabled_commands": [],
                "leak_approvals": [],
                "trial_usage": {},
                "trial_limit": 2,
                "trial_user_limit": 0,
                "trial_users": [],
                "maintenance_mode": False,
                "blacklisted_numbers": [],
                "bot_offline": False,
                "last_broadcast": [],
                "force_join_targets": [],
            }
            for key, default in defaults.items():
                if key not in data:
                    data[key] = default
            # Auto-migrate old default 100 to 0 (unlimited)
            if data.get("trial_user_limit") == 100:
                data["trial_user_limit"] = 0
            return data
    except Exception:
        return {"users": [], "groups": [], "disabled_commands": [], "leak_approvals": [], 
                "trial_usage": {}, "trial_limit": 2, "trial_user_limit": 0, "trial_users": [],
                "maintenance_mode": False, "blacklisted_numbers": [], "bot_offline": False,
                "last_broadcast": [], "force_join_targets": []}

def save_db(data: Dict[str, Any]) -> None:
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=4)

def get_emoji_theme() -> str:
    theme = str(load_db().get("emoji_theme", "normal")).lower()
    return theme if theme in EMOJI_THEMES else "normal"

def set_emoji_theme(theme: str) -> bool:
    normalized = theme.strip().lower()
    if normalized not in EMOJI_THEMES:
        return False
    db = load_db()
    db["emoji_theme"] = normalized
    save_db(db)
    add_log("ADMIN", f"Emoji theme changed to {normalized}")
    return True

def theme_text(text: str) -> str:
    replacements = EMOJI_THEMES.get(get_emoji_theme(), {})
    for source, target in replacements.items():
        text = text.replace(source, target)
    return text

def register_user(chat_id: int, chat_type: str, user_id: Optional[int] = None) -> None:
    db = load_db()
    changed = False
    chat_id_str = str(chat_id)
    if chat_type == ChatType.PRIVATE:
        if chat_id_str not in db["users"]:
            db["users"].append(chat_id_str)
            changed = True
    else:
        if chat_id_str not in db["groups"]:
            db["groups"].append(chat_id_str)
            changed = True
    if user_id is not None:
        user_id_str = str(user_id)
        if user_id_str not in db["users"]:
            db["users"].append(user_id_str)
            changed = True
    if changed:
        save_db(db)

def is_command_disabled(command_name: str) -> bool:
    db = load_db()
    if db.get("maintenance_mode", False):
        return True
    return command_name in db.get("disabled_commands", [])

def is_bot_offline() -> bool:
    db = load_db()
    return db.get("bot_offline", False)

def set_bot_offline(state: bool) -> bool:
    db = load_db()
    db["bot_offline"] = state
    save_db(db)
    return state

# -------------------- GROUP AUTHORIZATION & APPROVALS --------------------
def is_group_authorized(chat_id: Union[int, str]) -> bool:
    db = load_db()
    cid = str(chat_id)
    official_id = str(db.get("official_group_id") or "")
    if official_id and cid == official_id:
        return True
    approved = [str(x) for x in db.get("approved_groups", [])]
    return cid in approved

def add_approved_group(chat_id: Union[int, str], title: str = "") -> bool:
    db = load_db()
    cid = str(chat_id)
    approved = db.setdefault("approved_groups", [])
    approved_meta = db.setdefault("approved_groups_meta", {})
    if cid not in [str(x) for x in approved]:
        approved.append(cid)
        if title:
            approved_meta[cid] = title
        save_db(db)
        add_log("ADMIN", f"Group approved: {cid} ({title})")
        return True
    return False

def remove_approved_group(chat_id: Union[int, str]) -> bool:
    db = load_db()
    cid = str(chat_id)
    approved = db.get("approved_groups", [])
    str_approved = [str(x) for x in approved]
    if cid in str_approved:
        db["approved_groups"] = [x for x in approved if str(x) != cid]
        if "approved_groups_meta" in db and cid in db["approved_groups_meta"]:
            del db["approved_groups_meta"][cid]
        save_db(db)
        add_log("ADMIN", f"Group approval revoked: {cid}")
        return True
    return False

def set_official_group(chat_id: Union[int, str]) -> None:
    db = load_db()
    db["official_group_id"] = str(chat_id)
    save_db(db)
    add_log("ADMIN", f"Official group set to {chat_id}")

def get_official_group_link() -> str:
    db = load_db()
    return db.get("official_group_link") or SECRET_GROUP_LINK

def set_official_group_link(url: str) -> None:
    db = load_db()
    db["official_group_link"] = url
    save_db(db)
    add_log("ADMIN", f"Official group link set to {url}")

def remove_unicode_emojis(text: str) -> str:
    """Removes normal unicode emojis from text so only custom/premium emojis and clean text remain."""
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map
        "\U0001F1E0-\U0001F1FF"  # flags
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "\U0001F900-\U0001F9FF"  # supplemental symbols
        "\U0001FA70-\U0001FAFF"
        "\U00002600-\U000026FF"
        "]+",
        flags=re.UNICODE
    )
    cleaned = emoji_pattern.sub("", text).strip()
    return re.sub(r"\s+", " ", cleaned).strip()

DEFAULT_GROUP_ALERT_MSG = (
    '<tg-emoji emoji-id="6055296939761607847">🔒</tg-emoji> <b>Group Access Restricted!</b>\n\n'
    '<tg-emoji emoji-id="6267000941547885720">❌</tg-emoji> <b>Ye Info Command iss group me allow nahi hai.</b>\n\n'
    '<tg-emoji emoji-id="5334756265358798915">ℹ️</tg-emoji> <i>Security & Spam protection ki wajah se sare Information & Lookup commands sirf hamare <b>Official Group</b> me work karte hain.</i>\n\n'
    '<tg-emoji emoji-id="5246723622067807994">👉</tg-emoji> Commands use karne ke liye neeche button par click karke hamara <b>Official Group</b> join karein! <tg-emoji emoji-id="6314152643006569537">👇</tg-emoji>'
)
DEFAULT_GROUP_ALERT_BTN_TEXT = "JOIN OFFICIAL GROUP"
DEFAULT_GROUP_ALERT_BTN_EMOJI = "6138734238628845209"

def get_group_alert_msg() -> str:
    db = load_db()
    msg = db.get("group_alert_msg")
    if not msg or "6055296939761607847" not in msg:
        return DEFAULT_GROUP_ALERT_MSG
    return msg

def set_group_alert_msg(text: str) -> None:
    db = load_db()
    db["group_alert_msg"] = text
    save_db(db)
    add_log("ADMIN", "Group alert message updated")

def get_group_alert_btn_text() -> str:
    db = load_db()
    btn = db.get("group_alert_btn_text") or DEFAULT_GROUP_ALERT_BTN_TEXT
    # Always ensure normal unicode emojis are removed so only clean text + premium emoji show
    return remove_unicode_emojis(btn) or "JOIN OFFICIAL GROUP"

def set_group_alert_btn_text(text: str) -> None:
    db = load_db()
    db["group_alert_btn_text"] = text
    save_db(db)
    add_log("ADMIN", f"Group alert button text updated: {text}")

def get_group_alert_btn_emoji() -> str:
    db = load_db()
    return db.get("group_alert_btn_emoji") or DEFAULT_GROUP_ALERT_BTN_EMOJI

def set_group_alert_btn_emoji(emoji_id: str) -> None:
    db = load_db()
    db["group_alert_btn_emoji"] = emoji_id.strip()
    save_db(db)
    add_log("ADMIN", f"Group alert button emoji updated: {emoji_id}")

DEFAULT_GROUP_APPROVED_ANNOUNCEMENT = (
    '<tg-emoji emoji-id="6208445114075847396">🎉</tg-emoji> <b>GROUP APPROVED!</b>\n\n'
    '<tg-emoji emoji-id="5278658546454516040">✅</tg-emoji> <b>Yeh group ab officially approve ho chuka hai!</b>\n\n'
    'Ab iss group ke sabhi members bot ke sare commands freely use kar sakte hain.\n\n'
    'Type <code>/help</code> to see all available commands. <tg-emoji emoji-id="5219828279162215461">🚀</tg-emoji>'
)

def get_group_approved_announcement() -> str:
    db = load_db()
    msg = db.get("group_approved_announcement")
    if not msg or "6208445114075847396" not in msg:
        return DEFAULT_GROUP_APPROVED_ANNOUNCEMENT
    return msg

def set_group_approved_announcement(text: str) -> None:
    db = load_db()
    db["group_approved_announcement"] = text
    save_db(db)
    add_log("ADMIN", "Group approved announcement message updated")

DEFAULT_GROUP_REVOKED_ANNOUNCEMENT = (
    '<tg-emoji emoji-id="6267000941547885720">⚠️</tg-emoji> <b>GROUP ACCESS REVOKED!</b>\n\n'
    '<tg-emoji emoji-id="6055296939761607847">🔒</tg-emoji> <b>Iss group ki bot approval admin dwara revoke (hata) di gayi hai.</b>\n\n'
    '<tg-emoji emoji-id="5334756265358798915">ℹ️</tg-emoji> <i>Ab iss group me bot ke Information & Lookup commands work nahi karenge.\n'
    'Commands use karne ke liye neeche button par click karke hamara <b>Official Group</b> join karein!</i> 👇'
)

def get_group_revoked_announcement() -> str:
    db = load_db()
    return db.get("group_revoked_announcement") or DEFAULT_GROUP_REVOKED_ANNOUNCEMENT

def set_group_revoked_announcement(text: str) -> None:
    db = load_db()
    db["group_revoked_announcement"] = text
    save_db(db)
    add_log("ADMIN", "Group revoked announcement message updated")

async def send_group_revocation_announcement(bot, chat_id: Union[int, str]) -> bool:
    text = get_group_revoked_announcement()
    official_link = get_official_group_link()
    btn_text = get_group_alert_btn_text()
    btn_emoji = get_group_alert_btn_emoji()
    keyboard = [[
        InlineKeyboardButton(btn_text, url=official_link, _emoji_id=btn_emoji)
    ]]
    try:
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard),
            disable_web_page_preview=True,
        )
        return True
    except Exception as e:
        logger.warning(f"Could not send revocation announcement to group {chat_id}: {e}")
        return False

def get_user_mention(user) -> str:
    name = user.first_name if user.first_name else "User"
    return f'<a href="tg://user?id={user.id}">{html.escape(name)}</a>'

async def get_user_info(bot, user_id: int) -> Dict[str, Any]:
    try:
        user = await bot.get_chat(user_id)
        username = user.username if user.username else None
        first_name = user.first_name if user.first_name else None
        last_name = user.last_name if user.last_name else ""
        full_name = f"{first_name} {last_name}".strip() if first_name else None
        return {
            "user_id": user_id,
            "username": username,
            "full_name": full_name,
            "mention": get_user_mention(user) if hasattr(user, 'first_name') else f"User {user_id}"
        }
    except Exception as e:
        logger.error(f"Could not get user info for {user_id}: {e}")
        return {
            "user_id": user_id,
            "username": None,
            "full_name": None,
            "mention": f"User ID: {user_id}"
        }

def add_log(level: str, message: str) -> None:
    timestamp = datetime.now().strftime("%H:%M:%S")
    LOG_BUFFER.append(f"[{timestamp}] {level}: {message}")

def check_rate_limit(user_id: int, limit: int = 3, period: int = 10) -> bool:
    now = time.time()
    if user_id not in RATE_LIMIT_DICT:
        RATE_LIMIT_DICT[user_id] = deque(maxlen=limit)
    
    user_times = RATE_LIMIT_DICT[user_id]
    while user_times and now - user_times[0] > period:
        user_times.popleft()
    
    if len(user_times) >= limit:
        return False
    
    user_times.append(now)
    return True

def is_maintenance_mode() -> bool:
    db = load_db()
    return db.get("maintenance_mode", False)

def set_maintenance_mode(enabled: bool) -> bool:
    db = load_db()
    db["maintenance_mode"] = enabled
    save_db(db)
    return enabled

def get_blacklisted() -> List[str]:
    db = load_db()
    return db.get("blacklisted_numbers", [])

def add_blacklist_number(number: str) -> bool:
    db = load_db()
    if "blacklisted_numbers" not in db:
        db["blacklisted_numbers"] = []
    clean_num = re.sub(r'\D', '', number)
    if clean_num and clean_num not in db["blacklisted_numbers"]:
        db["blacklisted_numbers"].append(clean_num)
        save_db(db)
        return True
    return False

def remove_blacklist_number(number: str) -> bool:
    db = load_db()
    clean_num = re.sub(r'\D', '', number)
    if "blacklisted_numbers" in db and clean_num in db["blacklisted_numbers"]:
        db["blacklisted_numbers"].remove(clean_num)
        save_db(db)
        return True
    return False

def is_blacklisted(number: str) -> bool:
    clean_num = re.sub(r'\D', '', number)
    blacklist = get_blacklisted()
    return clean_num in blacklist

def get_target_chat(chat_id: Union[int, str]) -> Union[int, str]:
    try:
        chat_str = str(chat_id).strip()
        if chat_str.startswith('-') and chat_str[1:].isdigit():
            return int(chat_str)
        elif chat_str.isdigit():
            return int(chat_str)
        return chat_str
    except Exception:
        return chat_id

def normalize_force_join_reference(target_ref: str) -> Tuple[str, Optional[str]]:
    """Return a Telegram chat reference and preserve any invite link."""
    value = str(target_ref or "").strip()
    if not value:
        return "", None

    url_match = re.match(
        r"^(?:https?://)?(?:www\.)?t\.me/([^/?#]+)",
        value,
        flags=re.IGNORECASE,
    )
    if not url_match:
        return value, None

    path_part = url_match.group(1)
    if path_part.startswith("+") or path_part.lower().startswith("joinchat"):
        return value, value

    if path_part.lower() in {"c", "joinchat"}:
        return value, value

    username = path_part.lstrip("@")
    if re.fullmatch(r"[A-Za-z0-9_]{5,32}", username):
        return f"@{username}", f"https://t.me/{username}"

    return value, None

def get_force_join_targets() -> List[Dict[str, Any]]:
    targets = load_db().get("force_join_targets", [])
    return targets if isinstance(targets, list) else []

def save_force_join_targets(targets: List[Dict[str, Any]]) -> None:
    db = load_db()
    db["force_join_targets"] = targets
    save_db(db)

def remove_force_join_target(target_ref: str) -> Optional[Dict[str, Any]]:
    normalized = str(target_ref).strip().lower()
    targets = get_force_join_targets()
    for index, target in enumerate(targets):
        values = {
            str(target.get("chat_id", "")).lower(),
            str(target.get("username", "")).lower(),
            str(target.get("title", "")).lower(),
        }
        if normalized in values:
            removed = targets.pop(index)
            save_force_join_targets(targets)
            return removed
    return None

async def add_force_join_target(
    bot,
    target_ref: str,
    invite_link: Optional[str] = None,
    resolved_chat=None,
) -> Tuple[bool, str]:
    target_ref = target_ref.strip()
    if not target_ref:
        return False, "Target is required."

    normalized_ref, detected_invite_link = normalize_force_join_reference(target_ref)
    if detected_invite_link and (
        detected_invite_link.rstrip("/").split("/")[-1].startswith("+")
        or "joinchat" in detected_invite_link.lower()
    ) and resolved_chat is None:
        return False, (
            "Private invite link se Telegram chat ID resolve nahi karta. "
            "Target group me <code>/fjaddhere "
            f"{html.escape(detected_invite_link)}</code> bhejein, ya private chat me "
            "numeric chat ID ke saath invite link bhejein."
        )

    chat_ref: Union[int, str] = get_target_chat(normalized_ref)
    try:
        chat = resolved_chat or await bot.get_chat(chat_ref)
    except Exception as e:
        logger.error(f"Force join target lookup failed for {target_ref}: {e}")
        return False, (
            "Target chat resolve nahi hua. Public chat ke liye @username use karein. "
            "Private chat ke liye target group me <code>/fjaddhere "
            "https://t.me/+invite_link</code> run karein."
        )

    chat_id = str(chat.id)
    username = getattr(chat, "username", None)
    title = getattr(chat, "title", None) or (
        f"@{username}" if username else chat_id
    )
    chat_type = getattr(chat, "type", "group")
    if chat_type not in {"channel", "group", "supergroup"}:
        return False, "Sirf channel, group ya supergroup add kar sakte hain."

    try:
        bot_member = await bot.get_chat_member(chat_id=chat.id, user_id=bot.id)
        if bot_member.status not in {"administrator", "creator"}:
            return False, (
                "Bot target chat me member hai, lekin administrator nahi hai. "
                "Bot ko admin rights dekar dobara try karein."
            )
    except Exception as e:
        logger.warning("Force join bot permission check failed for %s: %s", chat.id, e)
        return False, (
            "Bot target chat ki permissions verify nahi kar pa raha. "
            "Bot ko target chat me administrator bana kar /fjaddhere dobara run karein."
        )

    join_link = (invite_link or detected_invite_link or "").strip()
    if not join_link and username:
        join_link = f"https://t.me/{username}"
    if not join_link:
        return False, (
            "Private group/channel ke liye invite link bhi bhejein.\n"
            "Example: <code>/fjadd -1001234567890 https://t.me/+invite_link</code>"
        )

    targets = get_force_join_targets()
    for existing in targets:
        if str(existing.get("chat_id")) == chat_id:
            existing.update({
                "title": title,
                "username": username,
                "type": "channel" if chat_type == "channel" else "group",
                "join_link": join_link,
            })
            save_force_join_targets(targets)
            return True, f"Force join target updated: <b>{html.escape(title)}</b>"

    targets.append({
        "chat_id": chat_id,
        "title": title,
        "username": username,
        "type": "channel" if chat_type == "channel" else "group",
        "join_link": join_link,
    })
    save_force_join_targets(targets)
    add_log("ADMIN", f"Force join target added: {chat_id}")
    return True, f"Force join target added: <b>{html.escape(title)}</b>"

def force_join_button_text(target: Dict[str, Any]) -> str:
    custom_text = str(target.get("button_text") or "").strip()
    custom_emoji = str(target.get("button_emoji") or "").strip()
    emoji_id = str(target.get("button_emoji_id") or "").strip()
    try:
        emoji_space = max(0, min(10, int(target.get("button_emoji_space", 1))))
    except (TypeError, ValueError):
        emoji_space = 1
    if not custom_text:
        prefix = "Join Channel" if target.get("type") == "channel" else "Join Group"
        custom_text = f"{prefix}: {target.get('title') or 'Required chat'}"
    if custom_emoji:
        return f"{custom_emoji}{' ' * emoji_space}{custom_text}"
    if emoji_id and emoji_space:
        return f"{' ' * emoji_space}{custom_text}"
    return custom_text

def force_join_button_preview(target: Dict[str, Any]) -> str:
    text = force_join_button_text(target)
    emoji_id = str(target.get("button_emoji_id") or "").strip()
    if emoji_id:
        return f"[premium:{emoji_id}] {text}".strip()
    return text

def parse_force_join_button_input(
    raw: str,
) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[int], Optional[str]]:
    fields = [field.strip() for field in raw.split("|")]
    if len(fields) not in {2, 3}:
        return None, None, None, None, (
            "Format: <code>🔥 | Join VIP Group</code>\n"
            "Spacing ke saath: <code>🔥 | 3 | Join VIP Group</code>\n"
            "Premium ID: <code>premium:123456789 | 2 | Join VIP Group</code>"
        )

    emoji_value = fields[0]
    if len(fields) == 3:
        if not fields[1].isdigit() or int(fields[1]) > 10:
            return None, None, None, None, "Space value 0 se 10 ke beech hona chahiye."
        emoji_space = int(fields[1])
        text_part = fields[2]
    else:
        emoji_space = 1
        text_part = fields[1]

    emoji = emoji_value
    emoji_id = ""
    button_text = " ".join(text_part.split())
    emoji_lower = emoji_value.lower()
    if emoji_lower in {"-", "none", "no", "default"}:
        emoji = ""
    else:
        id_match = re.fullmatch(
            r"(?:premium(?:_emoji)?(?:_id)?|emoji_id|id)\s*[:=]\s*(\d+)",
            emoji_value,
            flags=re.IGNORECASE,
        )
        if id_match or emoji_value.isdigit():
            emoji_id = id_match.group(1) if id_match else emoji_value
            if len(emoji_id) > 25:
                return None, None, None, None, "Premium emoji ID invalid hai."
            emoji = ""
        elif re.match(
            r"^(?:premium|emoji_id|id)(?:_emoji)?(?:_id)?\s*[:=]",
            emoji_value,
            flags=re.IGNORECASE,
        ):
            return None, None, None, None, "Premium emoji ID sirf numbers me hona chahiye."
    if not button_text:
        return None, None, None, None, "Button name empty nahi ho sakta."
    if len(button_text) > 50:
        return None, None, None, None, "Button name maximum 50 characters ka ho sakta hai."
    if emoji_id and not emoji_id.isdigit():
        return None, None, None, None, "Premium emoji ID sirf numbers me hona chahiye."
    if not emoji_id and len(emoji) > 12:
        return None, None, None, None, "Emoji field bahut lamba hai. Ek ya do emoji use karein."
    return emoji, emoji_id, button_text, emoji_space, None

def save_force_join_button(
    target_index: int,
    button_emoji: str,
    button_emoji_id: str,
    button_text: str,
    button_emoji_space: int,
) -> Optional[Dict[str, Any]]:
    targets = get_force_join_targets()
    if target_index < 0 or target_index >= len(targets):
        return None
    targets[target_index]["button_emoji"] = button_emoji
    targets[target_index]["button_emoji_id"] = button_emoji_id
    targets[target_index]["button_text"] = button_text
    targets[target_index]["button_emoji_space"] = button_emoji_space
    save_force_join_targets(targets)
    return targets[target_index]

async def get_missing_force_join_targets(bot, user_id: int) -> List[Dict[str, Any]]:
    missing: List[Dict[str, Any]] = []
    for target in get_force_join_targets():
        try:
            member = await bot.get_chat_member(
                chat_id=get_target_chat(target.get("chat_id", "")),
                user_id=user_id,
            )
            is_member = member.status in {"member", "administrator", "creator"}
            if member.status == "restricted":
                is_member = bool(getattr(member, "is_member", False))
            if not is_member:
                missing.append(target)
        except Exception as e:
            logger.warning(
                "Force join membership check failed for %s: %s",
                target.get("chat_id"),
                e,
            )
            missing.append(target)
    return missing

def force_join_keyboard(
    targets: List[Dict[str, Any]],
    owner_user_id: Optional[int] = None,
) -> InlineKeyboardMarkup:
    buttons = []
    for target in targets:
        title = str(target.get("title") or target.get("username") or "Required chat")
        join_link = str(target.get("join_link") or "").strip()
        if join_link:
            buttons.append([
                InlineKeyboardButton(
                    force_join_button_text(target),
                    url=join_link,
                    _emoji_id=str(target.get("button_emoji_id") or "").strip() or None,
                )
            ])
    buttons.append([
        InlineKeyboardButton(
            "I have joined all",
            callback_data=(
                f"force_join_check_{owner_user_id}"
                if owner_user_id is not None
                else "force_join_check"
            ),
            _emoji_id=FORCE_JOIN_VERIFY_EMOJI_ID,
        )
    ])
    return InlineKeyboardMarkup(buttons)

async def enforce_force_join(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    if not user or user.id == ADMIN_ID:
        return False

    missing = await get_missing_force_join_targets(context.bot, user.id)
    if not missing:
        return False

    lines = [
        f'<tg-emoji emoji-id="6267039884016358504">⚠️</tg-emoji> '
        "<b>Access restricted</b>",
        "",
        "Bot commands use karne se pehle in required channels/groups ko join karein:",
        "",
    ]
    for target in missing:
        label = html.escape(str(target.get("title") or target.get("username") or "Required chat"))
        lines.append(f"• {label}")
    lines.extend(["", "Join karne ke baad <b>I have joined all</b> par click karein."])
    text = "\n".join(lines)
    markup = force_join_keyboard(missing, owner_user_id=user.id)

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=markup,
        )
    elif update.message:
        await update.message.reply_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=markup,
        )
    return True

def maintenance_aware(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if user is None:
            return
        user_id = user.id
        if user_id == ADMIN_ID:
            return await func(update, context)
        
        if is_bot_offline():
            if update.message:
                await update.message.reply_text(
                    '<tg-emoji emoji-id="6235612354181080084">⏹️</tg-emoji> '
                    "<b>Bot is temporarily offline</b>\n\n"
                    "The bot has been temporarily shut down by the admin.\n"
                    "Please try again later.\n\n"
                    '<tg-emoji emoji-id="6087133294648890399">🟢</tg-emoji> '
                    "Bot will be back online soon.",
                    parse_mode=ParseMode.HTML
                )
            return
        
        if is_maintenance_mode():
            if update.message:
                await update.message.reply_text(
                    f'{premium_emoji(MAINTENANCE_MESSAGE_EMOJI_IDS["updating"], "🔄")} '
                    "<b>Bot is currently updating</b>\n\n"
                    "The system is undergoing maintenance. Please try again in a few minutes.\n\n"
                    f'{premium_emoji(MAINTENANCE_MESSAGE_EMOJI_IDS["downtime"], "⏳")} '
                    "Estimated downtime: 2-5 minutes",
                    parse_mode=ParseMode.HTML
                )
            return

        if await enforce_force_join(update, context):
            return
        
        if not check_rate_limit(user_id):
            if update.message:
                await update.message.reply_text(
                    "⏳ <b>Rate limit exceeded</b>\n\n"
                    "Please wait a few seconds before using this command again.\n"
                    "Maximum 3 requests per 10 seconds.",
                    parse_mode=ParseMode.HTML
                )
            return
        
        return await func(update, context)
    return wrapper

def info_group_restricted(func):
    """Restricts INFO lookup commands to official or approved groups only."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if user and user.id == ADMIN_ID:
            return await func(update, context)
        chat = update.effective_chat
        if chat and chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
            if not is_group_authorized(chat.id):
                official_link = get_official_group_link()
                btn_text = get_group_alert_btn_text()
                btn_emoji = get_group_alert_btn_emoji()
                keyboard = [
                    [InlineKeyboardButton(
                        btn_text,
                        url=official_link,
                        _emoji_id=btn_emoji,
                    )]
                ]
                alert_text = get_group_alert_msg()
                if update.message:
                    await update.message.reply_text(
                        alert_text,
                        parse_mode=ParseMode.HTML,
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        disable_web_page_preview=True,
                    )
                return
        return await func(update, context)
    return wrapper

def get_all_active_users() -> List[int]:
    db = load_db()
    user_ids = set()
    for u in db.get("users", []):
        try:
            uid = int(u)
            if uid > 0:
                user_ids.add(uid)
        except (ValueError, TypeError):
            pass
    for u in db.get("trial_users", []):
        try:
            uid = int(u)
            if uid > 0:
                user_ids.add(uid)
        except (ValueError, TypeError):
            pass
    for entry in db.get("leak_approvals", []):
        try:
            uid = int(entry.get("user_id"))
            if uid > 0:
                user_ids.add(uid)
        except (ValueError, TypeError):
            pass
    for uid_str in db.get("trial_usage", {}).keys():
        try:
            uid = int(uid_str)
            if uid > 0:
                user_ids.add(uid)
        except (ValueError, TypeError):
            pass
    return sorted(list(user_ids))

def add_leak_approval(user_id: int, days: Optional[int] = None) -> bool:
    db = load_db()
    if "leak_approvals" not in db:
        db["leak_approvals"] = []
    for entry in db["leak_approvals"]:
        if entry["user_id"] == user_id:
            if days:
                entry["expiry"] = (datetime.now() + timedelta(days=days)).isoformat()
                save_db(db)
                return True
            return False
    expiry = None
    if days:
        expiry = (datetime.now() + timedelta(days=days)).isoformat()
    db["leak_approvals"].append({
        "user_id": user_id,
        "approved_at": datetime.now().isoformat(),
        "expiry": expiry
    })
    save_db(db)
    return True

def remove_leak_approval(user_id: int) -> bool:
    db = load_db()
    if "leak_approvals" not in db:
        return False
    original_len = len(db["leak_approvals"])
    db["leak_approvals"] = [e for e in db["leak_approvals"] if e["user_id"] != user_id]
    if len(db["leak_approvals"]) != original_len:
        save_db(db)
        return True
    return False

def is_leak_approved(user_id: int) -> bool:
    db = load_db()
    if "leak_approvals" not in db:
        return False
    for entry in db["leak_approvals"]:
        if entry["user_id"] == user_id:
            if entry.get("expiry"):
                try:
                    expiry = datetime.fromisoformat(entry["expiry"])
                    if datetime.now() > expiry:
                        return False
                except ValueError:
                    try:
                        expiry = datetime.strptime(entry["expiry"], "%Y-%m-%dT%H:%M:%S.%f")
                        if datetime.now() > expiry:
                            return False
                    except ValueError:
                        return False
            return True
    return False

def get_leak_approvals() -> List[Dict[str, Any]]:
    db = load_db()
    return db.get("leak_approvals", [])

def get_trial_limit() -> int:
    db = load_db()
    return db.get("trial_limit", 2)

def set_trial_limit(limit: int) -> bool:
    if limit < 0:
        return False
    db = load_db()
    db["trial_limit"] = limit
    save_db(db)
    return True

def get_trial_user_limit() -> int:
    db = load_db()
    limit = db.get("trial_user_limit", 0)
    if limit == 100:
        return 0
    return limit

def set_trial_user_limit(limit: int) -> bool:
    if limit < 0:
        return False
    db = load_db()
    db["trial_user_limit"] = limit
    save_db(db)
    return True

def get_trial_users() -> List[int]:
    db = load_db()
    return db.get("trial_users", [])

def add_trial_user(user_id: int) -> bool:
    db = load_db()
    if "trial_users" not in db:
        db["trial_users"] = []
    if user_id not in db["trial_users"]:
        db["trial_users"].append(user_id)
        save_db(db)
        return True
    return False

def get_trial_usage(user_id: int) -> int:
    db = load_db()
    return db.get("trial_usage", {}).get(str(user_id), 0)

def increment_trial_usage(user_id: int) -> int:
    db = load_db()
    if "trial_usage" not in db:
        db["trial_usage"] = {}
    used = db["trial_usage"].get(str(user_id), 0) + 1
    db["trial_usage"][str(user_id)] = used
    save_db(db)
    return used

def reset_trial_usage(user_id: Optional[int] = None) -> bool:
    db = load_db()
    if user_id is None:
        db["trial_usage"] = {}
        db["trial_users"] = []
    else:
        changed = False
        if str(user_id) in db["trial_usage"]:
            del db["trial_usage"][str(user_id)]
            changed = True
        if user_id in db["trial_users"]:
            db["trial_users"].remove(user_id)
            changed = True
        if not changed:
            return False
    save_db(db)
    return True

def split_text_by_lines(
    text: str,
    max_size: int = INFO_MAX_MESSAGE_SIZE,
    max_parts: int = INFO_MAX_PARTS,
) -> List[str]:
    lines = text.split('\n')
    chunks = []
    current_chunk = []
    current_size = 0
    
    for line in lines:
        if len(line) > max_size:
            if current_chunk:
                chunks.append("\n".join(current_chunk))
                current_chunk = []
                current_size = 0
            for i in range(0, len(line), max_size):
                chunks.append(line[i:i+max_size])
            continue
        
        if current_size + len(line) + 1 > max_size:
            if current_chunk:
                chunks.append("\n".join(current_chunk))
            current_chunk = [line]
            current_size = len(line) + 1
        else:
            current_chunk.append(line)
            current_size += len(line) + 1
            
    if current_chunk:
        chunks.append("\n".join(current_chunk))

    if not chunks:
        return [""]

    if len(chunks) <= max_parts:
        return chunks

    marker = f"\n... (remaining content omitted after {max_parts} parts)"
    chunks = chunks[:max_parts]
    chunks[-1] = chunks[-1][:max(0, max_size - len(marker))] + marker
    return chunks

def sanitize_num_api_response(payload: Any) -> Any:
    """Remove provider metadata that should not be shown in /num results."""
    if isinstance(payload, dict):
        sanitized = {}
        for key, value in payload.items():
            if key in {"key_details", "cached", "owner", "admin"}:
                continue
            if key == "developer":
                sanitized[key] = ADMIN_USERNAME
            else:
                sanitized[key] = sanitize_num_api_response(value)
        return sanitized
    if isinstance(payload, list):
        return [sanitize_num_api_response(item) for item in payload]
    return payload

def parse_num_api_response(response_body: str) -> Any:
    """Parse JSON responses while preserving plain-text provider responses."""
    clean_body = (response_body or "").lstrip("\ufeff").strip()
    if not clean_body:
        return {"message": "Number API returned an empty response."}
    try:
        payload = sanitize_num_api_response(json.loads(clean_body))
        normalized_payload = json.dumps(payload, ensure_ascii=False).lower()
        if (
            "reached your limit" in normalized_payload
            or "rate limit" in normalized_payload
            or ("please wait" in normalized_payload and "limit" in normalized_payload)
        ):
            return {
                "data": {
                    "error": "Service error. Please try again later",
                },
            }
        return payload
    except json.JSONDecodeError:
        return {"upstream_response": clean_body}

def format_info_report(
    *,
    user_mention: str,
    target: str,
    report: str,
    payload: str,
    part_number: int = 1,
    total_parts: int = 1,
    report_title: str = "SCROLL OF TRUTH",
) -> str:
    part_info = f" <b>(Part {part_number}/{total_parts})</b>" if total_parts > 1 else ""
    return (
        f'<tg-emoji emoji-id="{INFO_EMOJI_IDS["requester"]}">👤</tg-emoji> '
        f"{user_mention}\n\n"
        f'<tg-emoji emoji-id="{INFO_EMOJI_IDS["scroll"]}">📜</tg-emoji> — '
        f"{report_title}{part_info}\n"
        "────────────────────\n"
        f'<tg-emoji emoji-id="{INFO_EMOJI_IDS["target"]}">🎯</tg-emoji> '
        f"TARGET: <code>{html.escape(target)}</code>\n"
        f'<tg-emoji emoji-id="{INFO_EMOJI_IDS["report"]}">📁</tg-emoji> '
        f"REPORT: {report}\n\n"
        f"<pre><code class='language-json'>{html.escape(payload)}</code></pre>\n"
        "────────────────────\n"
        f'<tg-emoji emoji-id="{INFO_EMOJI_IDS["agent"]}">🕵️</tg-emoji> '
        f"AGENT: {user_mention}\n\n"
        f'<tg-emoji emoji-id="{INFO_EMOJI_IDS["auto_delete"]}">⏳</tg-emoji> '
        "This message will be automatically deleted after 1 minute."
    )

async def send_info_report_parts(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    status_message,
    user_mention: str,
    target: str,
    report: str,
    payload: str,
    reply_markup=None,
    report_title: str = "SCROLL OF TRUTH",
    delete_label: str = "",
    delay: float = 0.5,
) -> None:
    chunks = split_text_by_lines(payload)
    total_parts = len(chunks)

    for index, chunk in enumerate(chunks):
        result_msg = format_info_report(
            user_mention=user_mention,
            target=target,
            report=report,
            payload=chunk,
            part_number=index + 1,
            total_parts=total_parts,
            report_title=report_title,
        )
        if index == 0:
            sent_message = await safe_send_message(
                context,
                chat_id,
                result_msg,
                reply_markup=reply_markup,
                edit_message_id=status_message.message_id,
            )
        else:
            sent_message = await safe_send_message(
                context,
                chat_id,
                result_msg,
                reply_markup=reply_markup,
            )

        if sent_message:
            asyncio.create_task(
                delete_info_after(
                    context.bot,
                    chat_id,
                    sent_message.message_id,
                    60,
                    delete_label,
                )
            )
        if index < total_parts - 1:
            await asyncio.sleep(delay)

async def safe_send_message(context, chat_id: int, text: str, reply_markup=None, edit_message_id: Optional[int] = None):
    for attempt in range(5):
        try:
            themed_text = theme_text(text)
            if edit_message_id is not None:
                return await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=edit_message_id,
                    text=themed_text,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                    reply_markup=reply_markup
                )
            else:
                return await context.bot.send_message(
                    chat_id=chat_id,
                    text=themed_text,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                    reply_markup=reply_markup
                )
        except RetryAfter as e:
            logger.warning(f"Flood control hit! Sleeping for {e.retry_after}s before retrying...")
            await asyncio.sleep(e.retry_after + 1)
        except TelegramError as e:
            if edit_message_id and ("message to edit not found" in str(e).lower() or "message is not modified" in str(e).lower()):
                edit_message_id = None
                continue
            logger.error(f"Telegram error during dispatch: {e}")
            await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Generic safe dispatch error: {e}")
            await asyncio.sleep(1)
    return None

# ==================== COMMAND HANDLERS ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text: return
    register_user(update.effective_chat.id, update.effective_chat.type, update.effective_user.id if update.effective_user else None)
    if await enforce_force_join(update, context):
        return

    try:
        await context.bot.set_chat_menu_button(
            chat_id=update.effective_chat.id,
            menu_button=MenuButtonCommands(),
        )
    except Exception:
        pass
    
    bot_info = await context.bot.get_me()
    user_mention = get_user_mention(update.effective_user)
    keyboard = [
        [InlineKeyboardButton(
            "ADD ME TO YOUR GROUP",
            url=f"https://t.me/{bot_info.username}?startgroup=true",
            _emoji_id=PUBLIC_LINK_BUTTON_EMOJI_IDS["add_group"],
        )],
        [InlineKeyboardButton(
            "USE ME HERE",
            url=SECRET_GROUP_LINK,
            _emoji_id=PUBLIC_LINK_BUTTON_EMOJI_IDS["use_here"],
        )],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f'<tg-emoji emoji-id="{WELCOME_EMOJI_ID}">🎉</tg-emoji> '
        f"<b>Welcome {user_mention} You can now use me:</b>\n\n"
        "Use /help to see all available commands.",
        parse_mode=ParseMode.HTML, reply_markup=reply_markup
    )
    await show_admin_keyboard(update)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text: return
    register_user(update.effective_chat.id, update.effective_chat.type, update.effective_user.id if update.effective_user else None)
    user_mention = get_user_mention(update.effective_user)
    if update.effective_user.id != ADMIN_ID and is_command_disabled("help"):
        await update.message.reply_text("❌ The /help command is currently disabled by the admin.")
        return
    bot_info = await context.bot.get_me()
    help_text = (
        f"Hello — <b>{user_mention}</b>\n\n"
        f'<tg-emoji emoji-id="{HELP_EMOJI_IDS["commands_header"]}">🛠️</tg-emoji> '
        "<b>Bot Commands List:</b>\n\n"
        f'<tg-emoji emoji-id="{HELP_EMOJI_IDS["command"]}">💡</tg-emoji> '
        "/num Mobile number search (only in groups)\nExample: <code>/num 9876543210</code>\n\n"
        f'<tg-emoji emoji-id="{HELP_EMOJI_IDS["command"]}">💡</tg-emoji> '
        "/ip Convert IP JSON into readable information with Google Maps button (only in groups)\n"
        "Example: <code>/ip 8.8.8.8</code>\n\n"
        f'<tg-emoji emoji-id="{HELP_EMOJI_IDS["command"]}">💡</tg-emoji> '
        "/tg Telegram ID or username to Number (only in groups)\nExample: "
        "<code>/tg 123456789</code> or <code>/tg username</code>\n\n"
        f'<tg-emoji emoji-id="{HELP_EMOJI_IDS["command"]}">💡</tg-emoji> '
        "/adhar Aadhaar details by Aadhaar number (only in groups)\nExample: "
        "<code>/adhar 413509342303</code> (12 digits)\n\n"
        f'<tg-emoji emoji-id="{HELP_EMOJI_IDS["command"]}">💡</tg-emoji> '
        "/leak OSINT lookup by number (only in groups)\nExample: "
        "<code>/leak 918755178417</code>\n\n"
        f'<tg-emoji emoji-id="{HELP_EMOJI_IDS["command"]}">💡</tg-emoji> '
        "/email OSINT lookup by email (only in groups)\nExample: "
        "<code>/email example@gmail.com</code>\n\n"
        f'<tg-emoji emoji-id="{HELP_EMOJI_IDS["command"]}">💡</tg-emoji> '
        "/veh Vehicle information by registration number (only in groups)\nExample: "
        "<code>/veh RJ14CV0005</code>\n\n"
        f'<tg-emoji emoji-id="{HELP_EMOJI_IDS["command"]}">💡</tg-emoji> '
        "/num2veh Vehicle lookup by phone number (only in groups)\nExample: "
        "<code>/num2veh 7502379832</code>\n\n"
         f'<tg-emoji emoji-id="{HELP_EMOJI_IDS["command"]}">💡</tg-emoji> '
         "/ffinfo Free Fire player information by UID (only in groups)\nExample: "
         "<code>/ffinfo 10323158965</code>\n\n"
        f'<tg-emoji emoji-id="{HELP_EMOJI_IDS["command"]}">💡</tg-emoji> '
        "/mytrial Check your remaining trial uses for /leak\n\n"
        f'<tg-emoji emoji-id="{HELP_EMOJI_IDS["command"]}">💡</tg-emoji> '
        "/statu Check bot system status\nExample: <code>/statu</code>\n\n"
        f'<tg-emoji emoji-id="{HELP_EMOJI_IDS["command"]}">💡</tg-emoji> '
        "/about Show bot information and version\n\n"
        f'<tg-emoji emoji-id="{HELP_EMOJI_IDS["auto_delete"]}">⚠️</tg-emoji> '
        "<i>Results auto-delete after 1 minute.</i>\n"
        f'<tg-emoji emoji-id="{HELP_EMOJI_IDS["rate_limit"]}">⏳</tg-emoji> '
        "<i>Rate limit: 3 requests per 10 seconds per user.</i>"
    )
    keyboard = [
        [InlineKeyboardButton(
            "ADD ME TO YOUR GROUP",
            url=f"https://t.me/{bot_info.username}?startgroup=true",
            _emoji_id=PUBLIC_LINK_BUTTON_EMOJI_IDS["add_group"],
        )],
        [InlineKeyboardButton(
            "USE ME HERE",
            url=SECRET_GROUP_LINK,
            _emoji_id=PUBLIC_LINK_BUTTON_EMOJI_IDS["use_here"],
        )],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(help_text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
    await show_admin_keyboard(update)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global REQUEST_COUNTER
    REQUEST_COUNTER += 1
    if not update.message or not update.message.text: return
    if update.effective_user.id != ADMIN_ID and is_command_disabled("statu"):
        await update.message.reply_text("❌ The /statu command is currently disabled by the admin.")
        return
    db = load_db()
    now = datetime.now()
    date_str = now.strftime("%d-%m-%Y").upper()
    time_str = now.strftime("%I:%M %p")
    trial_limit = get_trial_limit()
    trial_user_limit = get_trial_user_limit()
    trial_users_count = len(get_trial_users())
    
    bot_status = "OFFLINE" if is_bot_offline() else "ONLINE"
    if is_maintenance_mode():
        bot_status = "MAINTENANCE"
    
    bot_name = "NUMBER X INFO BOT"
    status_text = (
        f'<tg-emoji emoji-id="{STATUS_EMOJI_IDS["bot_name"]}">⚡</tg-emoji> '
        f"<b>{bot_name}</b>\n────────────────────\n\n"
        f'<tg-emoji emoji-id="{STATUS_EMOJI_IDS["bot_status"]}">📊</tg-emoji> '
        f'<b>Bot Status:</b> <tg-emoji emoji-id="{STATUS_EMOJI_IDS["status_value"]}">🔘</tg-emoji> {bot_status}\n'
        f'<tg-emoji emoji-id="{STATUS_EMOJI_IDS["date"]}">📅</tg-emoji> DATE : {date_str}\n'
        f'<tg-emoji emoji-id="{STATUS_EMOJI_IDS["time"]}">🕒</tg-emoji> TIME : {time_str}\n\n'
        "────────────────────\n"
        f'<tg-emoji emoji-id="{STATUS_EMOJI_IDS["speed"]}">🚀</tg-emoji> SPEED : VERY FAST '
        f'<tg-emoji emoji-id="{STATUS_EMOJI_IDS["speed"]}">🚀</tg-emoji>\n'
        f'<tg-emoji emoji-id="{STATUS_EMOJI_IDS["availability"]}">✅</tg-emoji> AVAILABILITY : 24/7\n\n'
        f'<tg-emoji emoji-id="{STATUS_EMOJI_IDS["system_stats"]}">📊</tg-emoji> SYSTEM STATS:\n'
        f"┣ Active Groups (DB): {len(db['groups'])}\n┣ Total Users (DB): {len(db['users'])}\n"
        f"┣ Trial /leak uses per user: {trial_limit}\n"
        f"┗ Trial users: {trial_users_count} / {'Unlimited' if trial_user_limit <= 0 else trial_user_limit}\n\n"
        f'────────────────────\n<tg-emoji emoji-id="{STATUS_EMOJI_IDS["privacy"]}">🛡️</tg-emoji> '
        "Privacy and data security active.\n\n"
        f"by - {ADMIN_USERNAME} <tg-emoji emoji-id=\"{STATUS_EMOJI_IDS['admin']}\">💀</tg-emoji>"
    )
    keyboard = [
        [InlineKeyboardButton(
            "Join Private Group",
            url=SECRET_GROUP_LINK,
            _emoji_id=STATUS_EMOJI_IDS["join_group"],
        )],
        [InlineKeyboardButton(
            "Support",
            url=f"https://t.me/{ADMIN_USERNAME.replace('@', '')}",
            _emoji_id=STATUS_EMOJI_IDS["support"],
        )]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(status_text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)

async def mytrial_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global REQUEST_COUNTER
    REQUEST_COUNTER += 1
    user_id = update.effective_user.id
    if user_id == ADMIN_ID:
        await update.message.reply_text(
            f'<tg-emoji emoji-id="{EMOJI_ADMIN_UNLIMITED}">👑</tg-emoji> '
            "Admin has unlimited /leak usage (no trial limit).", 
            parse_mode=ParseMode.HTML
        )
        return
    if is_leak_approved(user_id):
        await update.message.reply_text(
            f'<tg-emoji emoji-id="{EMOJI_ADMIN_UNLIMITED}">✅</tg-emoji> '
            "You are approved for /leak. Unlimited usage (no trial limit).", 
            parse_mode=ParseMode.HTML
        )
        return
    used = get_trial_usage(user_id)
    limit = get_trial_limit()
    trial_users = get_trial_users()
    user_limit = get_trial_user_limit()
    if user_id in trial_users:
        remaining = max(0, limit - used)
        await update.message.reply_text(
            f'<tg-emoji emoji-id="{EMOJI_TRIAL_HEADER}">📊</tg-emoji> '
            f"<b>Your /leak trial usage</b>\n\n"
            f'<tg-emoji emoji-id="{EMOJI_USED_COUNT}">✅</tg-emoji> '
            f"Used: <code>{used}</code> / {limit}\n"
            f'<tg-emoji emoji-id="{EMOJI_REMAINING}">🔹</tg-emoji> '
            f"Remaining trials: <code>{remaining}</code>\n\n"
            f'<tg-emoji emoji-id="{EMOJI_TOTAL_USERS}">👥</tg-emoji> '
            f"Total trial users: {len(trial_users)} / {'Unlimited' if user_limit <= 0 else user_limit}\n"
            f"After trials finish, you need admin approval to continue using /leak.",
            parse_mode=ParseMode.HTML
        )
    else:
        remaining = limit
        await update.message.reply_text(
            f'<tg-emoji emoji-id="{EMOJI_TRIAL_HEADER}">📊</tg-emoji> '
            f"<b>Your /leak trial usage</b>\n\n"
            f'<tg-emoji emoji-id="{EMOJI_USED_COUNT}">✅</tg-emoji> '
            f"Used: <code>0</code> / {limit}\n"
            f'<tg-emoji emoji-id="{EMOJI_REMAINING}">🔹</tg-emoji> '
            f"Remaining trials: <code>{limit}</code>\n\n"
            f'<tg-emoji emoji-id="{EMOJI_TOTAL_USERS}">👥</tg-emoji> '
            f"Total trial users: {len(trial_users)} / {'Unlimited' if user_limit <= 0 else user_limit}\n"
            f"After trials finish, you need admin approval to continue using /leak.",
            parse_mode=ParseMode.HTML
        )

async def pin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID:
        return
    
    if not update.message.reply_to_message:
        await update.message.reply_text("⚠️ Please reply to the message you want to pin.")
        return

    try:
        await context.bot.pin_chat_message(
            chat_id=update.effective_chat.id,
            message_id=update.message.reply_to_message.message_id,
            disable_notification=False
        )
        await update.message.reply_text("📌 Message has been pinned successfully!")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to pin message. Make sure I am Admin with pin rights.\nError: {e}")

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type != ChatType.PRIVATE:
        await update.message.reply_text("❌ Admin panel is only available in private chat with the bot.")
        return
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return
    await show_admin_keyboard(update)
    await show_admin_panel(update, context, update.message.chat_id)

async def show_force_join_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID:
        if update.callback_query:
            await update.callback_query.edit_message_text("❌ Unauthorized.")
        return
    if update.effective_chat.type != ChatType.PRIVATE:
        if update.callback_query:
            await update.callback_query.edit_message_text("❌ Force join management is private-chat only.")
        return

    targets = get_force_join_targets()
    if targets:
        text = "<b>FORCE JOIN MANAGEMENT</b>\n\nRequired chats:\n"
        for index, target in enumerate(targets):
            label = html.escape(str(target.get("title") or target.get("chat_id")))
            target_type = "Channel" if target.get("type") == "channel" else "Group"
            button_preview = html.escape(force_join_button_preview(target))
            emoji_space = int(target.get("button_emoji_space", 1) or 0)
            text += (
                f"\n{index + 1}. <b>{target_type}</b> — {label}\n"
                f"   Button: <code>{button_preview}</code> "
                f"(space: <code>{emoji_space}</code>)\n"
            )
    else:
        text = (
            "<b>FORCE JOIN MANAGEMENT</b>\n\n"
            "No required channel/group configured yet."
        )

    keyboard = [[
        InlineKeyboardButton(
            "Add Channel/Group",
            callback_data="fj_add",
            _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["force_join_add"],
        ),
    ]]
    for index, target in enumerate(targets):
        label = str(target.get("title") or target.get("chat_id"))
        keyboard.append([
            InlineKeyboardButton(
                f"Edit Button {label[:30]}",
                callback_data=f"fj_edit_{index}",
            )
        ])
        keyboard.append([
            InlineKeyboardButton(
                f"Remove {label[:35]}",
                callback_data=f"fj_remove_{index}",
            )
        ])
    keyboard.extend([
        [InlineKeyboardButton(
            "Add/Remove by command",
            callback_data="fj_command_help",
            _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["force_join_command"],
        )],
        [InlineKeyboardButton(
            "Back to Admin Panel",
            callback_data="admin_panel",
            _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["back_to_start"],
        )],
    ])
    markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=markup,
        )
    else:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=markup,
        )

async def force_join_add_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or update.effective_user.id != ADMIN_ID:
        return
    context.user_data.pop("force_join_mode", None)
    if update.effective_chat.type != ChatType.PRIVATE:
        await update.message.reply_text("❌ Use this command in the bot's private chat.")
        return
    if not context.args:
        await update.message.reply_text(
            "Usage:\n"
            "<code>/fjadd @publicchannel</code>\n"
            "<code>/fjadd -1001234567890 https://t.me/+invite_link</code>\n"
            "<code>/fjaddhere https://t.me/+invite_link</code> "
            "(target group/channel ke andar)",
            parse_mode=ParseMode.HTML,
        )
        return

    success, message = await add_force_join_target(
        context.bot,
        context.args[0],
        context.args[1] if len(context.args) > 1 else None,
    )
    await update.message.reply_text(
        f"{'✅' if success else '❌'} {message}",
        parse_mode=ParseMode.HTML,
    )
    await show_force_join_panel(update, context)

async def force_join_here_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Add the chat where the admin sends this command."""
    message = update.effective_message
    is_channel_post = bool(update.channel_post)
    is_configured_admin = bool(
        update.effective_user and update.effective_user.id == ADMIN_ID
    )
    if not message or (not is_configured_admin and not is_channel_post):
        return

    chat = update.effective_chat
    if not chat or chat.type not in {ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL}:
        text = "❌ `/fjaddhere` target group/channel ke andar run karein."
        if is_channel_post:
            await context.bot.send_message(
                chat_id=chat.id if chat else message.chat_id,
                text=text,
                parse_mode=ParseMode.MARKDOWN,
            )
        else:
            await message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
        return

    invite_link = context.args[0] if context.args else None
    if not invite_link and getattr(chat, "username", None):
        invite_link = f"https://t.me/{chat.username}"

    if not invite_link:
        text = (
            "❌ Ye private chat lag raha hai. Command ke saath invite link bhejein:\n"
            "<code>/fjaddhere https://t.me/+invite_link</code>",
        )
        if is_channel_post:
            await context.bot.send_message(
                chat_id=chat.id,
                text=text,
                parse_mode=ParseMode.HTML,
            )
        else:
            await message.reply_text(text, parse_mode=ParseMode.HTML)
        return

    success, message = await add_force_join_target(
        context.bot,
        str(chat.id),
        invite_link,
        resolved_chat=chat,
    )
    result_text = f"{'✅' if success else '❌'} {message}"
    if is_channel_post:
        await context.bot.send_message(
            chat_id=chat.id,
            text=result_text,
            parse_mode=ParseMode.HTML,
        )
    else:
        await update.effective_message.reply_text(
            result_text,
            parse_mode=ParseMode.HTML,
        )

async def force_join_remove_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or update.effective_user.id != ADMIN_ID:
        return
    context.user_data.pop("force_join_mode", None)
    if update.effective_chat.type != ChatType.PRIVATE:
        await update.message.reply_text("❌ Use this command in the bot's private chat.")
        return
    if not context.args:
        await update.message.reply_text(
            "Usage: <code>/fjremove @channel_or_chat_id</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    removed = remove_force_join_target(context.args[0])
    if removed:
        add_log("ADMIN", f"Force join target removed: {removed.get('chat_id')}")
        message = f"✅ Removed: <b>{html.escape(str(removed.get('title') or removed.get('chat_id')))}</b>"
    else:
        message = "❌ Force join target not found."
    await update.message.reply_text(message, parse_mode=ParseMode.HTML)
    await show_force_join_panel(update, context)

async def force_join_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or update.effective_user.id != ADMIN_ID:
        return
    if update.effective_chat.type != ChatType.PRIVATE:
        await update.message.reply_text("❌ Use this command in the bot's private chat.")
        return
    await show_force_join_panel(update, context)

async def force_join_admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if (
        not update.message
        or not update.effective_user
        or update.effective_user.id != ADMIN_ID
        or update.effective_chat.type != ChatType.PRIVATE
    ):
        return

    mode = context.user_data.pop("force_join_mode", None)
    if mode not in {"add", "remove", "edit_button"}:
        return

    if not update.message.text:
        await update.message.reply_text(
            "❌ Sirf text target details bhejein. Photo/file nahi."
        )
        await show_force_join_panel(update, context)
        return

    parts = update.message.text.strip().split()
    if mode == "add" and parts:
        success, message = await add_force_join_target(
            context.bot,
            parts[0],
            parts[1] if len(parts) > 1 else None,
        )
        await update.message.reply_text(
            f"{'✅' if success else '❌'} {message}",
            parse_mode=ParseMode.HTML,
        )
    elif mode == "remove" and parts:
        removed = remove_force_join_target(parts[0])
        message = (
            f"✅ Removed: <b>{html.escape(str(removed.get('title') or removed.get('chat_id')))}</b>"
            if removed
            else "❌ Force join target not found."
        )
        await update.message.reply_text(message, parse_mode=ParseMode.HTML)
    elif mode == "edit_button":
        target_index = context.user_data.pop("force_join_edit_index", None)
        if "|" not in update.message.text:
            await update.message.reply_text(
                "❌ Format use karein: <code>🔥 | Join VIP Group</code>\n"
                "Spacing ke saath: <code>🔥 | 3 | Join VIP Group</code>",
                parse_mode=ParseMode.HTML,
            )
        elif target_index is None:
            await update.message.reply_text("❌ Target button session expire ho gaya.")
        else:
            emoji, emoji_id, button_text, emoji_space, error = parse_force_join_button_input(
                update.message.text.strip()
            )
            if error:
                await update.message.reply_text(
                    f"❌ {error}",
                    parse_mode=ParseMode.HTML,
                )
            else:
                target = save_force_join_button(
                    int(target_index),
                    emoji or "",
                    emoji_id or "",
                    button_text or "",
                    emoji_space if emoji_space is not None else 1,
                )
                if target:
                    await update.message.reply_text(
                        f"✅ Button updated: <code>{html.escape(force_join_button_preview(target))}</code>",
                        parse_mode=ParseMode.HTML,
                    )
                else:
                    await update.message.reply_text("❌ Force Join target not found.")
    else:
        await update.message.reply_text("❌ Target details nahi mile.")
    await show_force_join_panel(update, context)


def maintenance_control_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "ENABLE MAINTENANCE",
                callback_data="maintenance_enable",
                _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["maintenance_toggle"],
            ),
            InlineKeyboardButton(
                "DISABLE MAINTENANCE",
                callback_data="maintenance_disable",
                _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["maintenance_toggle"],
            ),
        ],
        [
            InlineKeyboardButton(
                "Back to Admin Panel",
                callback_data="admin_panel",
                _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["back_to_start"],
            )
        ],
    ])


def maintenance_control_text() -> str:
    enabled = is_maintenance_mode()
    status_emoji = (
        premium_emoji(MAINTENANCE_MESSAGE_EMOJI_IDS["enabled"], "🔧")
        if enabled
        else premium_emoji(MAINTENANCE_MESSAGE_EMOJI_IDS["disabled"], "✅")
    )
    status = f"{'ENABLED' if enabled else 'DISABLED'} {status_emoji}"
    access = (
        "Only the admin can use the bot right now."
        if enabled
        else "All users can use the bot normally."
    )
    return (
        f'{premium_emoji(MAINTENANCE_MESSAGE_EMOJI_IDS["header"], "⚙️")} '
        f"<b>Maintenance Mode: {status}</b>\n\n"
        f"{access}\n\n"
        "Choose an action below:"
    )


async def show_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: Optional[int] = None) -> None:
    if chat_id is None:
        chat_id = update.effective_chat.id
    
    db = load_db()
    bot_offline = db.get("bot_offline", False)
    
    toggle_buttons = [[
        InlineKeyboardButton(
            "START BOT",
            callback_data="start_bot",
            _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["start_bot"],
        ),
        InlineKeyboardButton(
            "STOP BOT",
            callback_data="stop_bot",
            _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["stop_bot"],
        ),
    ]]

    active_broadcast = db.get("last_broadcast", [])
    broadcast_actions = []
    if active_broadcast:
        broadcast_actions = [[
            InlineKeyboardButton(
                "Pin This Broadcast",
                callback_data="pin_active_broadcast",
                _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["pin_active_broadcast"],
            )
        ]]

    keyboard = [
        [
            InlineKeyboardButton(
                "Broadcast Message",
                callback_data="broadcast",
                _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["broadcast"],
            ),
            InlineKeyboardButton(
                "Broadcast Setup (Pin control)",
                callback_data="broadcast_pin",
                _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["broadcast_pin"],
            ),
        ]
    ]
    keyboard.extend(broadcast_actions)
    keyboard.extend([
        [
            InlineKeyboardButton(
                "Total Users",
                callback_data="total_users",
                _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["total_users"],
            ),
            InlineKeyboardButton(
                "Total Groups",
                callback_data="total_groups",
                _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["total_groups"],
            ),
        ],
        [InlineKeyboardButton(
            "Bot Statics",
            callback_data="bot_stats",
            _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["bot_stats"],
        )],
        [InlineKeyboardButton(
            "Refresh Database",
            callback_data="refresh_db",
            _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["refresh_db"],
        )],
        [InlineKeyboardButton(
            "Manage Commands",
            callback_data="manage_commands",
            _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["manage_commands"],
        )],
        [InlineKeyboardButton(
            "Force Join Channels/Groups",
            callback_data="force_join",
            _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["force_join"],
        )],
        [InlineKeyboardButton(
            "Manage Approved Groups",
            callback_data="manage_approved_groups",
            _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS.get("total_groups", ""),
        )],
        [InlineKeyboardButton(
            "Leak Approvals",
            callback_data="leak_approvals",
            _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["leak_approvals"],
        )],
        [InlineKeyboardButton(
            "Approve User",
            callback_data="approve_user",
            _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["approve_user"],
        )],
        [InlineKeyboardButton(
            "Revoke User",
            callback_data="revoke_user",
            _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["revoke_user"],
        )],
        [InlineKeyboardButton(
            "Set Trial Limit",
            callback_data="set_trial_limit",
            _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["set_trial_limit"],
        )],
        [InlineKeyboardButton(
            "Set Trial User Limit",
            callback_data="set_trial_user_limit",
            _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["set_trial_user_limit"],
        )],
        [InlineKeyboardButton(
            "Reset Trial Usage",
            callback_data="reset_trial",
            _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["reset_trial"],
        )],
        [InlineKeyboardButton(
            "Maintenance Mode",
            callback_data="maintenance_menu",
            _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["maintenance_toggle"],
        )],
        [InlineKeyboardButton(
            "System Stats",
            callback_data="system_stats",
            _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["system_stats"],
        )],
        [InlineKeyboardButton(
            "Blacklist Management",
            callback_data="blacklist_manage",
            _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["blacklist_manage"],
        )],
        [InlineKeyboardButton(
            "View Logs",
            callback_data="view_logs",
            _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["view_logs"],
        )],
        [InlineKeyboardButton(
            "Clear Cache",
            callback_data="clear_cache",
            _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["clear_cache"],
        )],
    ])
    keyboard.extend(toggle_buttons)
    keyboard.append([
        InlineKeyboardButton(
            "Back to Main Menu",
            callback_data="back_to_start",
            _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["back_to_start"],
        )
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    maintenance_status = "MAINTENANCE ON" if db.get("maintenance_mode", False) else "ONLINE"
    bot_status = "OFFLINE" if bot_offline else "ONLINE"
    
    admin_text = (
        f'<tg-emoji emoji-id="{ADMIN_STATUS_EMOJI_IDS["header"]}">🔧</tg-emoji> '
        "<b>ADMIN CONTROL PANEL</b>\n─────────────────────\n\n"
        f'<tg-emoji emoji-id="{ADMIN_STATUS_EMOJI_IDS["admin"]}">👤</tg-emoji> '
        f"<b>Admin:</b> {ADMIN_USERNAME}\n"
        f'<tg-emoji emoji-id="{ADMIN_STATUS_EMOJI_IDS["total_users"]}">📊</tg-emoji> '
        f"<b>Total Users:</b> {len(db['users'])}\n"
        f'<tg-emoji emoji-id="{ADMIN_STATUS_EMOJI_IDS["total_groups"]}">👥</tg-emoji> '
        f"<b>Total Groups:</b> {len(db['groups'])}\n"
        f'<tg-emoji emoji-id="{ADMIN_STATUS_EMOJI_IDS["bot_status"]}">⚙️</tg-emoji> '
        f'<b>Bot Status:</b> <tg-emoji emoji-id="{ADMIN_STATUS_EMOJI_IDS["status_value"]}">🔘</tg-emoji> {bot_status}\n'
        f'<tg-emoji emoji-id="{ADMIN_STATUS_EMOJI_IDS["maintenance"]}">🔧</tg-emoji> '
        f'<b>Maintenance:</b> <tg-emoji emoji-id="{ADMIN_STATUS_EMOJI_IDS["status_value"]}">🔘</tg-emoji> {maintenance_status}\n'
        f'<tg-emoji emoji-id="{ADMIN_STATUS_EMOJI_IDS["trial_limit"]}">🎯</tg-emoji> '
        f"<b>Trial /leak uses per user:</b> {get_trial_limit()}\n"
        f'<tg-emoji emoji-id="{ADMIN_STATUS_EMOJI_IDS["trial_user_limit"]}">👥</tg-emoji> '
        f"<b>Trial User Limit:</b> {'Unlimited' if get_trial_user_limit() <= 0 else get_trial_user_limit()} (used: {len(get_trial_users())})\n"
        f'<tg-emoji emoji-id="{ADMIN_STATUS_EMOJI_IDS["rate_limits"]}">🚦</tg-emoji> '
        f"<b>Active rate limits:</b> {len(RATE_LIMIT_DICT)} users\n"
        f'<tg-emoji emoji-id="{ADMIN_STATUS_EMOJI_IDS["blacklist"]}">🚫</tg-emoji> '
        f"<b>Blacklisted numbers:</b> {len(get_blacklisted())}\n"
        f'<tg-emoji emoji-id="{ADMIN_STATUS_EMOJI_IDS["cache"]}">💾</tg-emoji> '
        f"<b>Cache entries:</b> {len(API_CACHE)}\n\n"
        "─────────────────────\n"
        "<i>Select an option below:</i>"
    )
    
    if update.callback_query:
        await update.callback_query.edit_message_text(admin_text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
    else:
        await context.bot.send_message(chat_id=chat_id, text=admin_text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)

MANAGEABLE_COMMANDS: List[str] = [
    "num",
    "ip",
    "tg",
    "adhar",
    "statu",
    "help",
    "leak",
    "email",
    "about",
    "mytrial",
    "veh",
    "num2veh",
    "ffinfo",
]

async def manage_commands(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_ID or query.message.chat.type != ChatType.PRIVATE:
        await query.edit_message_text("❌ Unauthorized.")
        return

    db = load_db()
    disabled = db.get("disabled_commands", [])
    keyboard = []
    for cmd in MANAGEABLE_COMMANDS:
        status = "ENABLED" if cmd not in disabled else "DISABLED"
        keyboard.append([InlineKeyboardButton(
            f"{cmd} - {status}",
            callback_data=f"toggle_cmd_{cmd}",
            _emoji_id=COMMAND_STATUS_BUTTON_EMOJI_ID,
        )])
    keyboard.append([InlineKeyboardButton(
        "Back to Admin Panel",
        callback_data="admin_panel",
        _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["back_to_start"],
    )])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        f'<tg-emoji emoji-id="{COMMAND_MANAGER_EMOJI_ID}">🔧</tg-emoji> '
        "<b>COMMAND MANAGER</b>\n\n"
        "Click on a command to toggle its status.\n"
        "Disabled commands will not work for regular users (admin can always use them).\n\n"
        "Current status:",
        parse_mode=ParseMode.HTML,
        reply_markup=reply_markup
    )

async def toggle_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_ID:
        await query.edit_message_text("❌ Unauthorized.")
        return

    cmd = query.data.split("_")[2]
    db = load_db()
    disabled = db.get("disabled_commands", [])
    if cmd in disabled:
        disabled.remove(cmd)
        status_msg = (
            f'<tg-emoji emoji-id="{EMOJI_COMMAND_DISABLED}">✅</tg-emoji> '
            f"Command /{cmd} has been <b>ENABLED</b>."
        )
    else:
        disabled.append(cmd)
        status_msg = (
            f'<tg-emoji emoji-id="{EMOJI_COMMAND_DISABLED}">❌</tg-emoji> '
            f"Command /{cmd} has been <b>DISABLED</b>."
        )
    db["disabled_commands"] = disabled
    save_db(db)

    await manage_commands(update, context)
    await query.message.reply_text(status_msg, parse_mode=ParseMode.HTML)

async def total_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query if update.callback_query else None
    db = load_db()
    users = db.get("users", [])
    count = len(users)
    
    page = 1
    if query and query.data.startswith("total_users_page_"):
        try:
            page = int(query.data.split("_")[-1])
        except:
            page = 1
    elif context.args and len(context.args) > 0:
        try:
            page = int(context.args[0])
        except:
            page = 1
    
    total_pages = (count + USERS_PER_PAGE - 1) // USERS_PER_PAGE if count > 0 else 1
    if page < 1: page = 1
    if page > total_pages and total_pages > 0: page = total_pages
    
    start_idx = (page - 1) * USERS_PER_PAGE
    end_idx = min(start_idx + USERS_PER_PAGE, count)
    page_users = users[start_idx:end_idx]
    
    if count == 0:
        user_text = "👥 <b>Total Users:</b> <code>0</code>\n\nNo users found."
    else:
        user_text = f"👥 <b>USER LIST</b> — Page {page}/{total_pages}\n─────────────────────\n\n"
        user_text += f"<b>Total Users:</b> <code>{count}</code>\n\n"
        for i, uid in enumerate(page_users, start=start_idx + 1):
            info = await get_user_info(context.bot, int(uid))
            display = info['full_name'][:25] if info['full_name'] else (f"@{info['username']}" if info['username'] else "No name/username")
            user_text += f"{i}. <code>{uid}</code>\n   └ 👤 {html.escape(display)}\n"
    
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton("◀️ Previous", callback_data=f"total_users_page_{page-1}"))
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton("Next ▶️", callback_data=f"total_users_page_{page+1}"))
    
    keyboard = []
    if nav_buttons:
        keyboard.append(nav_buttons)
    keyboard.append([InlineKeyboardButton("📊 Export User List", callback_data="export_users")])
    keyboard.append([InlineKeyboardButton(
        "Back to Admin Panel",
        callback_data="admin_panel",
        _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["back_to_start"],
    )])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if query:
        await query.edit_message_text(user_text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
    else:
        await update.message.reply_text(user_text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)

async def export_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    db = load_db()
    users = db.get("users", [])
    if not users:
        await query.edit_message_text("No users found to export.")
        return
    text = f"📊 <b>EXPORT USER DATA</b>\n─────────────────────\n\nTotal users: <code>{len(users)}</code>\n\nSelect export format:"
    keyboard = [
        [InlineKeyboardButton("📝 Export as Text", callback_data="export_text")],
        [InlineKeyboardButton("📋 Export as JSON", callback_data="export_json")],
        [InlineKeyboardButton(
            "Back to User List",
            callback_data="total_users",
            _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["back_to_start"],
        )]
    ]
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))

async def export_users_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    db = load_db()
    users = db.get("users", [])
    export = f"📊 USER DATABASE EXPORT\n═══════════════════════════════\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\nTotal Users: {len(users)}\n═══════════════════════════════\n\n"
    for i, uid in enumerate(users, 1):
        info = await get_user_info(context.bot, int(uid))
        phone = await get_phone_from_tg_api(str(uid))
        export += f"{i}. USER ID: {info['user_id']}\n   ├ Name: {info['full_name'] or 'Not set'}\n   ├ Username: @{info['username'] if info['username'] else 'Not set'}\n   └ Phone: {phone}\n\n"
    if len(export) > 4000:
        for chunk in [export[i:i+4000] for i in range(0, len(export), 4000)]:
            await query.message.reply_text(f"<pre>{html.escape(chunk)}</pre>", parse_mode=ParseMode.HTML)
        await query.answer("Export sent in multiple messages")
    else:
        await query.edit_message_text(f"<pre>{html.escape(export)}</pre>", parse_mode=ParseMode.HTML)
    keyboard = [[InlineKeyboardButton(
        "Back to User List",
        callback_data="total_users",
        _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["back_to_start"],
    )]]
    await query.message.reply_text("✅ Export complete!", reply_markup=InlineKeyboardMarkup(keyboard))

async def export_users_json(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    db = load_db()
    users = db.get("users", [])
    data = []
    for uid in users:
        info = await get_user_info(context.bot, int(uid))
        phone = await get_phone_from_tg_api(str(uid))
        info["phone"] = phone
        data.append(info)
    export_data = {"export_date": datetime.now().isoformat(), "total_users": len(users), "users": data}
    json_text = json.dumps(export_data, indent=2, ensure_ascii=False)
    if len(json_text) > 4000:
        for chunk in [json_text[i:i+4000] for i in range(0, len(json_text), 4000)]:
            await query.message.reply_text(f"<pre>{html.escape(chunk)}</pre>", parse_mode=ParseMode.HTML)
        await query.answer("Export sent in multiple messages")
    else:
        await query.edit_message_text(f"<pre>{html.escape(json_text)}</pre>", parse_mode=ParseMode.HTML)
    keyboard = [[InlineKeyboardButton(
        "Back to User List",
        callback_data="total_users",
        _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["back_to_start"],
    )]]
    await query.message.reply_text("✅ Export complete!", reply_markup=InlineKeyboardMarkup(keyboard))

async def total_groups(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query if update.callback_query else None
    db = load_db()
    groups = db.get("groups", [])
    count = len(groups)
    
    if count == 0:
        group_text = "📊 <b>Total Groups:</b> <code>0</code>\n\nNo groups found."
    else:
        group_text = f"📊 <b>GROUPS LIST</b>\n─────────────────────\n\n<b>Total Groups:</b> <code>{count}</code>\n\n"
        for idx, gid in enumerate(groups[:20], 1):
            try:
                chat = await context.bot.get_chat(int(gid))
                title = chat.title or "No Title"
                uname = chat.username
                if uname:
                    link = f"https://t.me/{uname}"
                    group_text += f"{idx}. <a href='{link}'>{html.escape(title)}</a>\n   └ 🆔 <code>{gid}</code> | @{uname}\n"
                else:
                    try:
                        invite_link = await chat.export_invite_link()
                        group_text += f"{idx}. <a href='{invite_link}'>{html.escape(title)}</a>\n   └ 🆔 <code>{gid}</code> | 🔒 Private (invite link)\n"
                    except Exception:
                        group_text += f"{idx}. {html.escape(title)}\n   └ 🆔 <code>{gid}</code> | 🔒 No link (bot not admin)\n"
            except Exception as e:
                group_text += f"{idx}. Group ID: <code>{gid}</code> (Cannot fetch details)\n"
        if count > 20:
            group_text += f"\n... and {count - 20} more groups"
    
    keyboard = [
        [InlineKeyboardButton("📊 Export Group List", callback_data="export_groups")],
        [InlineKeyboardButton(
            "Back to Admin Panel",
            callback_data="admin_panel",
            _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["back_to_start"],
        )]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if query:
        await query.edit_message_text(group_text, parse_mode=ParseMode.HTML, disable_web_page_preview=True, reply_markup=reply_markup)
    else:
        await update.message.reply_text(group_text, parse_mode=ParseMode.HTML, disable_web_page_preview=True, reply_markup=reply_markup)

async def export_groups(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    db = load_db()
    groups = db.get("groups", [])
    if not groups:
        await query.edit_message_text("No groups found to export.")
        return
    
    export = f"📊 GROUP DATABASE EXPORT\n═══════════════════════════════\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\nTotal Groups: {len(groups)}\n═══════════════════════════════\n\n"
    for i, gid in enumerate(groups, 1):
        try:
            chat = await context.bot.get_chat(int(gid))
            title = chat.title or "No Title"
            uname = chat.username
            if uname:
                link = f"https://t.me/{uname}"
                export += f"{i}. GROUP ID: {gid}\n   ├ Title: {title}\n   └ Link: {link}\n\n"
            else:
                try:
                    invite_link = await chat.export_invite_link()
                    export += f"{i}. GROUP ID: {gid}\n   ├ Title: {title}\n   └ Link: {invite_link} (private)\n\n"
                except:
                    export += f"{i}. GROUP ID: {gid}\n   ├ Title: {title}\n   └ Link: Not available (bot not admin)\n\n"
        except:
            export += f"{i}. GROUP ID: {gid} (Cannot fetch details)\n\n"
    
    if len(export) > 4000:
        for chunk in [export[i:i+4000] for i in range(0, len(export), 4000)]:
            await query.message.reply_text(f"<pre>{html.escape(chunk)}</pre>", parse_mode=ParseMode.HTML)
        await query.answer("Export sent in multiple messages")
    else:
        await query.edit_message_text(f"<pre>{html.escape(export)}</pre>", parse_mode=ParseMode.HTML)
    keyboard = [[InlineKeyboardButton(
        "Back to Groups List",
        callback_data="total_groups",
        _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["back_to_start"],
    )]]
    await query.message.reply_text("✅ Export complete!", reply_markup=InlineKeyboardMarkup(keyboard))

async def bot_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    db = load_db()
    trial_limit = get_trial_limit()
    trial_user_limit = get_trial_user_limit()
    trial_users_count = len(get_trial_users())
    stats_text = (
        "📈 <b>BOT STATISTICS</b>\n─────────────────────\n\n"
        f"👥 <b>Total Registered Users:</b> <code>{len(db['users'])}</code>\n"
        f"👥 <b>Total Groups:</b> <code>{len(db['groups'])}</code>\n"
        f"🎯 <b>Trial /leak uses per user:</b> <code>{trial_limit}</code>\n"
        f"👥 <b>Trial User Limit:</b> <code>{trial_users_count} / {'Unlimited' if trial_user_limit <= 0 else trial_user_limit}</code>\n"
        f"💾 <b>Cache entries:</b> <code>{len(API_CACHE)}</code>\n\n─────────────────────\n"
        "<i>System running smoothly</i>"
    )
    keyboard = [[InlineKeyboardButton(
        "Back to Admin Panel",
        callback_data="admin_panel",
        _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["back_to_start"],
    )]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(stats_text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)

async def refresh_db(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    db = load_db()
    context.bot_data['db'] = db
    refresh_text = (
        "🔄 <b>DATABASE REFRESHED</b>\n─────────────────────\n\n"
        f"✅ Database reloaded successfully!\n"
        f"👥 Users: <code>{len(db['users'])}</code>\n"
        f"👥 Groups: <code>{len(db['groups'])}</code>\n\n"
        "<i>Database is now up to date</i>"
    )
    keyboard = [[InlineKeyboardButton(
        "Back to Admin Panel",
        callback_data="admin_panel",
        _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["back_to_start"],
    )]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(refresh_text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)

async def back_to_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    bot_info = await context.bot.get_me()
    user_mention = get_user_mention(update.effective_user)
    keyboard = [
        [InlineKeyboardButton(
            "ADD ME TO YOUR GROUP",
            url=f"https://t.me/{bot_info.username}?startgroup=true",
            _emoji_id=PUBLIC_LINK_BUTTON_EMOJI_IDS["add_group"],
        )],
        [InlineKeyboardButton(
            "USE ME HERE",
            url=SECRET_GROUP_LINK,
            _emoji_id=PUBLIC_LINK_BUTTON_EMOJI_IDS["use_here"],
        )],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        f'<tg-emoji emoji-id="{WELCOME_EMOJI_ID}">🎉</tg-emoji> '
        f"<b>Welcome back {user_mention}!</b>\nUse /help to see commands.",
        parse_mode=ParseMode.HTML, reply_markup=reply_markup
    )
    if update.effective_user.id == ADMIN_ID and update.effective_chat.type == ChatType.PRIVATE:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=(
                f'<tg-emoji emoji-id="{ADMIN_BUTTON_UPDATED_EMOJI_ID}">✅</tg-emoji> '
                "<b>Admin button updated.</b>"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=ReplyKeyboardRemove(),
        )
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=(
                f'<tg-emoji emoji-id="{ADMIN_STATUS_EMOJI_IDS["header"]}">🔧</tg-emoji> '
                "<b>Admin controls</b>\nUse the button below to open the admin panel."
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=admin_inline_keyboard(),
        )

async def broadcast_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_ID or query.message.chat.type != ChatType.PRIVATE:
        await query.edit_message_text("❌ Unauthorized or wrong chat.")
        return
    
    is_pin_mode = (query.data == "broadcast_pin")
    if is_pin_mode:
        context.user_data['awaiting_broadcast_pin'] = True
        context.user_data.pop('awaiting_broadcast', None)
        mode_text = "📢 <b>BROADCAST SETUP (PIN CONTROL)</b>\n\nMessage send hone ke baad admin panel me <b>'Pin This Broadcast'</b> button aayega, jispe click karte hi sabhi groups/chats me message pin ho jayega."
    else:
        context.user_data['awaiting_broadcast'] = True
        context.user_data.pop('awaiting_broadcast_pin', None)
        mode_text = "📢 <b>NORMAL BROADCAST MODE</b>\n\nSabh chats aur groups mein normal message send hoga (Pin nahi hoga)."

    keyboard = [[InlineKeyboardButton(
        "Cancel",
        callback_data="admin_panel",
        _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["back_to_start"],
    )]]
    await query.edit_message_text(
        f"{mode_text}\n\n"
        "Please send me the message you want to broadcast to all users and groups.\n"
        "You can send text, photo, video, document, audio, sticker, or a Poll/Quiz.\n"
        "Channel se koi message forward karke bhejoge to broadcast me uska original "
        "<b>Forwarded from</b> header bhi visible rahega.\n\n"
        "Type /cancel to abort.",
        parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.user_data.get("force_join_mode"):
        await force_join_admin_message(update, context)
        return

    is_normal = context.user_data.get('awaiting_broadcast')
    is_pin = context.user_data.get('awaiting_broadcast_pin')
    
    if not is_normal and not is_pin:
        return
    if update.effective_user.id != ADMIN_ID or update.effective_chat.type != ChatType.PRIVATE:
        return

    context.user_data.pop('awaiting_broadcast', None)
    context.user_data.pop('awaiting_broadcast_pin', None)

    db = load_db()
    # Broadcast ko private bot users aur dono tarah ke Telegram groups
    # (normal group + supergroup) tak bhejo.  set() duplicate chat IDs ko
    # remove karta hai, isliye kisi chat ko do baar message nahi milega.
    user_chats = {str(chat_id) for chat_id in db.get("users", [])}
    group_chats = {str(chat_id) for chat_id in db.get("groups", [])}
    all_chats = list(user_chats | group_chats)
    if not all_chats:
        await update.message.reply_text(
            "❌ No bot users or groups found to broadcast."
        )
        return

    pin_info_text = " with manual pin configuration" if is_pin else ""
    prog_msg = await update.message.reply_text(
        f"🚀 Broadcasting{pin_info_text} to "
        f"{len(user_chats)} bot users and {len(group_chats)} groups "
        f"({len(all_chats)} unique chats)...",
        parse_mode=ParseMode.HTML,
    )
    success = 0
    failed = 0
    sent_messages = []

    msg = update.message
    # Agar admin ne kisi channel/group ka message bot ko forward kiya hai,
    # copy_message() use karne par Telegram ka original "Forwarded from"
    # header chala jata hai.  Aise message ko forward_message() se bhejna
    # zaroori hai, taaki source channel ka naam/link recipients ko dikhe.
    # PTB ke naye versions me forward_origin hota hai; purane versions ke
    # liye forward_from / forward_from_chat fallback rakhe gaye hain.
    is_forwarded_message = bool(
        getattr(msg, "forward_origin", None)
        or getattr(msg, "forward_from", None)
        or getattr(msg, "forward_from_chat", None)
    )

    for chat_id in all_chats:
        sent_msg_id = None
        target_chat = get_target_chat(chat_id)
        try:
            if is_forwarded_message:
                # Preserve the original source attribution (especially for
                # channel posts) in every recipient chat.
                res = await context.bot.forward_message(
                    chat_id=target_chat,
                    from_chat_id=msg.chat_id,
                    message_id=msg.message_id,
                )
            else:
                res = await context.bot.copy_message(
                    chat_id=target_chat,
                    from_chat_id=msg.chat_id,
                    message_id=msg.message_id,
                )
            sent_msg_id = res.message_id

            sent_messages.append({"chat_id": str(target_chat), "message_id": sent_msg_id})
            success += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            logger.error(f"Broadcast failed to {chat_id}: {e}")
            failed += 1

    db = load_db()
    db["last_broadcast"] = sent_messages
    save_db(db)

    report_text = (
        f"✅ Broadcast Finished!\n"
        f"👤 Bot users: {len(user_chats)}\n"
        f"👥 Groups: {len(group_chats)}\n"
        f"🟢 Success: {success}\n"
        f"🔴 Failed: {failed}"
    )
    if is_forwarded_message:
        report_text += "\n📨 Original forwarded source header preserved."
    if is_pin:
        report_text += "\n\n📌 <i>Go to Admin Panel and tap 'Pin This Broadcast' to pin this message across all chats.</i>"
        
    await prog_msg.edit_text(report_text, parse_mode=ParseMode.HTML)
    await show_admin_panel(update, context, update.effective_chat.id)

async def pin_active_broadcast_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    db = load_db()
    last_broadcast = db.get("last_broadcast", [])
    
    if not last_broadcast:
        await query.message.reply_text("❌ No active broadcast found to pin.")
        return
        
    status_msg = await query.message.reply_text("📌 <b>Pinning last broadcasted messages...</b>", parse_mode=ParseMode.HTML)
    pinned_count = 0
    failed_count = 0
    
    for msg_info in last_broadcast:
        try:
            chat_id = msg_info["chat_id"]
            msg_id = msg_info["message_id"]
            target_chat = get_target_chat(chat_id)
            await context.bot.pin_chat_message(chat_id=target_chat, message_id=msg_id, disable_notification=False)
            pinned_count += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            logger.warning(f"Failed to pin broadcast message in {chat_id}: {e}")
            failed_count += 1
            
    await status_msg.edit_text(
        f"📌 <b>Pin Report:</b>\n─────────────────────\n\n"
        f"🟢 Successfully Pinned: <code>{pinned_count}</code>\n"
        f"🔴 Failed/Insufficient Rights: <code>{failed_count}</code>",
        parse_mode=ParseMode.HTML
    )
    await show_admin_panel(update, context, update.effective_chat.id)

async def delete_last_broadcast_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    db = load_db()
    last_broadcast = db.get("last_broadcast", [])
    
    if not last_broadcast:
        await query.message.reply_text("❌ No active broadcast found to delete.")
        return
    
    status_msg = await query.message.reply_text("🗑️ <b>Deleting last broadcasted messages...</b>", parse_mode=ParseMode.HTML)
    success = 0
    failed = 0
    
    for msg_info in last_broadcast:
        try:
            chat_id = msg_info["chat_id"]
            msg_id = msg_info["message_id"]
            target_chat = get_target_chat(chat_id)
            await context.bot.delete_message(chat_id=target_chat, message_id=msg_id)
            success += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            logger.error(f"Failed to delete broadcast message in {chat_id}: {e}")
            failed += 1
            
    db["last_broadcast"] = []
    save_db(db)
    
    status_text = (
        f"🗑️ <b>Broadcast Deletion Report</b>\n─────────────────────\n\n"
        f"🟢 Deleted Successfully: <code>{success}</code>\n"
        f"🔴 Failed to Delete: <code>{failed}</code>\n\n"
        f"<i>Database record cleared successfully.</i>"
    )
    await status_msg.edit_text(status_text, parse_mode=ParseMode.HTML)
    await show_admin_panel(update, context, update.effective_chat.id)

async def cancel_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID:
        return
    context.user_data.pop("force_join_mode", None)
    if context.user_data.get('awaiting_broadcast') or context.user_data.get('awaiting_broadcast_pin'):
        context.user_data.pop('awaiting_broadcast', None)
        context.user_data.pop('awaiting_broadcast_pin', None)
        await update.message.reply_text("❌ Broadcast cancelled.")
        await show_admin_panel(update, context, update.effective_chat.id)

async def user_details_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized.")
        return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text(
            f'<tg-emoji emoji-id="{INVALID_USAGE_EMOJI_ID}">⚠️</tg-emoji> '
            "<b>Usage:</b> <code>/userdetails &lt;user_id&gt;</code>",
            parse_mode=ParseMode.HTML,
        )
        return
    user_id = int(context.args[0])
    info = await get_user_info(context.bot, user_id)
    phone = await get_phone_from_tg_api(str(user_id))
    details = (
        f"👤 <b>USER DETAILS</b>\n─────────────────────\n\n"
        f"🆔 <b>User ID:</b> <code>{info['user_id']}</code>\n"
        f"👤 <b>Full Name:</b> {info['full_name'] or 'Not set'}\n"
        f"📝 <b>Username:</b> @{info['username'] if info['username'] else 'Not set'}\n"
        f"📞 <b>Phone Number:</b> <code>{phone}</code>\n"
        f"🔗 <b>Mention:</b> {info['mention']}\n─────────────────────\n"
        f"💡 <i>This user can be mentioned using the mention link above.</i>"
    )
    await update.message.reply_text(details, parse_mode=ParseMode.HTML)

async def get_phone_from_tg_api(tg_id: str) -> str:
    try:
        if not PHONE_LOOKUP_API_URL:
            return "Not configured"
        separator = "&" if "?" in PHONE_LOOKUP_API_URL else "?"
        url = f"{PHONE_LOOKUP_API_URL}{separator}term={tg_id}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    def find_phone(obj):
                        if isinstance(obj, dict):
                            for key in ["phone", "number", "mobile", "msisdn", "Phone", "Number", "Mobile", "phone_number", "contact"]:
                                if key in obj and obj[key]:
                                    val = str(obj[key])
                                    if re.match(r'^\+?\d{7,15}$', val):
                                        return val
                                    if val.isdigit() and len(val) >= 7:
                                        return val
                            for v in obj.values():
                                result = find_phone(v)
                                if result:
                                    return result
                        elif isinstance(obj, list):
                            for item in obj:
                                result = find_phone(item)
                                if result:
                                    return result
                        elif isinstance(obj, str):
                            if re.match(r'^\+?\d{7,15}$', obj):
                                return obj
                        return None
                    phone = find_phone(data)
                    return phone if phone else "Not found"
                else:
                    return "Not found"
    except Exception:
        return "Not found"

def extract_tg_id_from_payload(payload: Any) -> Optional[str]:
    """Find a Telegram user ID in an upstream response, if one was returned."""
    if isinstance(payload, dict):
        for key in (
            "tg_id",
            "user_id",
            "telegram_id",
            "telegram_user_id",
            "telegram_userid",
            "userId",
            "telegramId",
            "id",
        ):
            value = payload.get(key)
            if value is not None and str(value).isdigit():
                return str(value)
        for value in payload.values():
            found = extract_tg_id_from_payload(value)
            if found:
                return found
    elif isinstance(payload, list):
        for value in payload:
            found = extract_tg_id_from_payload(value)
            if found:
                return found
    elif isinstance(payload, str):
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            return None
        return extract_tg_id_from_payload(parsed)
    return None


async def resolve_tg_id(
    bot: Any,
    search_type: str,
    raw_input: str,
    upstream_response: Any = None,
    record: Any = None,
) -> Optional[str]:
    """Resolve the Telegram ID from API data first, then Telegram itself."""
    if search_type == "ID":
        return raw_input

    tg_id = extract_tg_id_from_payload(record) or extract_tg_id_from_payload(upstream_response)
    if tg_id:
        return tg_id

    try:
        telegram_user = await bot.get_chat(chat_id=f"@{raw_input}")
        resolved_id = getattr(telegram_user, "id", None)
        if resolved_id is not None:
            return str(resolved_id)
    except Exception:
        pass
    return None


async def build_tg_not_found_response(
    bot: Any,
    search_type: str,
    raw_input: str,
    upstream_response: Any = None,
) -> Dict[str, Any]:
    """Return the stable /tg fallback shape requested by the bot owner."""
    tg_id = await resolve_tg_id(
        bot,
        search_type,
        raw_input,
        upstream_response=upstream_response,
    )

    result: Dict[str, Any] = {
        "country": "not found",
        "country_code": "",
        "msg": "Details not fetched",
        "number": "Phone number not found",
        "success": True,
    }
    if search_type == "USERNAME":
        result["tg_username"] = raw_input
    # Never hide the field when the external lookup is unavailable. Prefer the
    # numeric ID; otherwise keep the requested username visible as a reference.
    result["tg_id"] = tg_id or raw_input

    return {
        "result": result,
        "success": True,
        "status": True,
        "cached": False,
        "developer": ADMIN_USERNAME,
    }


@maintenance_aware
async def lookup_tg(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global REQUEST_COUNTER
    REQUEST_COUNTER += 1
    if not update.message or not update.message.text: return
    register_user(update.effective_chat.id, update.effective_chat.type, update.effective_user.id if update.effective_user else None)
    if update.effective_chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        await update.message.reply_text(
            f'<tg-emoji emoji-id="{GROUP_ONLY_EMOJI_ID}">❌</tg-emoji> '
            "This command only works inside Groups.",
            parse_mode=ParseMode.HTML,
        )
        return
    if update.effective_user.id != ADMIN_ID and is_command_disabled("tg"):
        await update.message.reply_text(
            f'<tg-emoji emoji-id="{EMOJI_ERROR_DISABLED}">❌</tg-emoji> '
            "The /tg command is currently disabled by the admin.",
            parse_mode=ParseMode.HTML
        )
        return

    user_mention = get_user_mention(update.effective_user)
    bot_info = await context.bot.get_me()
    if not context.args:
        error_msg = await update.effective_chat.send_message(
            f'<tg-emoji emoji-id="{INVALID_USAGE_EMOJI_ID}">⚠️</tg-emoji> '
            "<b>Invalid Usage!</b>\nFormat: <code>/tg &lt;user_id_or_username&gt;</code>\n"
            "Example: <code>/tg 123456789</code> or <code>/tg username</code>",
            parse_mode=ParseMode.HTML
        )
        asyncio.create_task(delete_info_after(context.bot, update.effective_chat.id, error_msg.message_id, 10))
        return

    raw_input = context.args[0].strip()
    if raw_input.startswith('@'):
        raw_input = raw_input[1:]

    if not raw_input:
        error_msg = await update.effective_chat.send_message(
            f'<tg-emoji emoji-id="{INVALID_USAGE_EMOJI_ID}">⚠️</tg-emoji> '
            "<b>Invalid Telegram ID or username.</b>",
            parse_mode=ParseMode.HTML
        )
        asyncio.create_task(delete_info_after(context.bot, update.effective_chat.id, error_msg.message_id, 10))
        return

    if raw_input.isdigit() and raw_input in BLACKLISTED_IDS:
        block_msg = await update.effective_chat.send_message(
            f"❌ <b>Access Denied!</b>\nTarget ID: <code>{html.escape(raw_input)}</code>\nStatus: <b>PROTECTED</b> 🛡️",
            parse_mode=ParseMode.HTML
        )
        asyncio.create_task(delete_info_after(context.bot, update.effective_chat.id, block_msg.message_id, 20))
        return

    search_type = "USERNAME" if not raw_input.isdigit() else "ID"
    display_target = raw_input
    cache_key = f"tg_{raw_input}"
    lookup_value = raw_input if search_type == "ID" else f"@{raw_input}"

    status_msg = await update.effective_chat.send_message(
        f'<tg-emoji emoji-id="{SEARCHING_EMOJI_ID}">🔍</tg-emoji> '
        f"<b>Fetching Data for {search_type}: {html.escape(display_target)}...</b>",
        parse_mode=ParseMode.HTML
    )

    keyboard = [
        [InlineKeyboardButton(
            "USE ME HERE",
            url=SECRET_GROUP_LINK,
            _emoji_id=PUBLIC_LINK_BUTTON_EMOJI_IDS["use_here"],
        )],
        [InlineKeyboardButton(
            "ADD ME TO YOUR GROUP",
            url=f"https://t.me/{bot_info.username}?startgroup=true",
            _emoji_id=PUBLIC_LINK_BUTTON_EMOJI_IDS["add_group"],
        )]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    cached_data = get_cached_response(cache_key)
    if cached_data and search_type == "USERNAME" and isinstance(cached_data, dict):
        cached_result = cached_data.get("result")
        cached_tg_id = cached_result.get("tg_id") if isinstance(cached_result, dict) else None
        if not cached_tg_id or str(cached_tg_id) == raw_input or not str(cached_tg_id).isdigit():
            API_CACHE.pop(cache_key, None)
            cached_data = None

    if cached_data:
        formatted_json = (
            cached_data
            if isinstance(cached_data, str)
            else json.dumps(cached_data, indent=2, ensure_ascii=False)
        )
        chunks = split_text_by_lines(formatted_json, max_size=3500)
        total_parts = len(chunks)
        
        for i, chunk in enumerate(chunks):
            result_msg = format_info_report(
                user_mention=user_mention,
                target=display_target,
                report=f"TELEGRAM {'ID' if search_type == 'ID' else 'USERNAME'} INFO",
                payload=chunk,
                part_number=i + 1,
                total_parts=total_parts,
                report_title="SCROLL OF TRUTH (Cached)",
            )
            if i == 0:
                success_msg = await safe_send_message(context, update.effective_chat.id, result_msg, reply_markup=reply_markup, edit_message_id=status_msg.message_id)
                if success_msg:
                    asyncio.create_task(delete_info_after(context.bot, update.effective_chat.id, success_msg.message_id, 60, f"TELEGRAM {search_type} INFO"))
            else:
                new_msg = await safe_send_message(context, update.effective_chat.id, result_msg, reply_markup=reply_markup)
                if new_msg:
                    asyncio.create_task(delete_info_after(context.bot, update.effective_chat.id, new_msg.message_id, 60, f"TELEGRAM {search_type} INFO"))
            await asyncio.sleep(0.5)
        return

    TG_API_TIMEOUT = aiohttp.ClientTimeout(total=25, connect=5, sock_read=20)

    try:
        if not TG_LOOKUP_API_URL:
            await status_msg.edit_text(
                "◇ <b>Telegram lookup is not configured.</b>\n\n"
                "Set TG_LOOKUP_API_URL in the environment.",
                parse_mode=ParseMode.HTML,
            )
            return
        tg_api_url = TG_LOOKUP_API_URL + quote_plus(lookup_value)
        session = await get_session()
        async with session.get(
            tg_api_url,
            timeout=TG_API_TIMEOUT,
        ) as resp:
            response_body = await resp.text()
            if resp.status == 200:
                try:
                    upstream_response: Any = json.loads(response_body)
                except json.JSONDecodeError:
                    upstream_response = response_body

                normalized_result: Dict[str, Any] = {
                    "country": None,
                    "country_code": None,
                    "msg": "Details not found",
                    "number": None,
                    "success": False,
                }
                if search_type == "USERNAME":
                    normalized_result["tg_username"] = raw_input
                normalized_result["tg_id"] = raw_input

                record: Optional[Dict[str, Any]] = None
                upstream_success: Optional[bool] = None

                if isinstance(upstream_response, dict):
                    response_section = upstream_response.get("response")
                    if isinstance(response_section, dict):
                        parameters = response_section.get("parameters")
                        if isinstance(parameters, dict) and "success" in parameters:
                            upstream_success = bool(parameters.get("success"))
                        data = response_section.get("data")
                        if isinstance(data, list) and data and isinstance(data[0], dict):
                            record = data[0]
                        elif isinstance(data, dict):
                            record = data

                    if record is None:
                        data = upstream_response.get("data")
                        if isinstance(data, list) and data and isinstance(data[0], dict):
                            record = data[0]
                        elif isinstance(data, dict):
                            record = data

                    if record is None and isinstance(upstream_response.get("result"), dict):
                        record = upstream_response["result"]

                    if "success" in upstream_response:
                        upstream_success = bool(upstream_response.get("success"))

                if record:
                    normalized_result["country"] = record.get("country")
                    normalized_result["country_code"] = record.get("country_code")
                    normalized_result["number"] = (
                        record.get("number")
                        or record.get("phone")
                        or record.get("mobile")
                    )
                    normalized_result["tg_id"] = (
                        extract_tg_id_from_payload(record)
                        or extract_tg_id_from_payload(upstream_response)
                        or raw_input
                    )
                    if search_type == "USERNAME":
                        normalized_result["tg_username"] = (
                            record.get("tg_username")
                            or record.get("username")
                            or raw_input
                        )

                    record_success = record.get("success")
                    if record_success is not None:
                        upstream_success = bool(record_success)
                    normalized_result["success"] = (
                        upstream_success
                        if upstream_success is not None
                        else bool(normalized_result["number"])
                    )
                    normalized_result["msg"] = (
                        record.get("msg")
                        or ("Details fetched" if normalized_result["success"] else "Details not found")
                    )

                if search_type == "USERNAME":
                    resolved_tg_id = await resolve_tg_id(
                        context.bot,
                        search_type,
                        raw_input,
                        upstream_response=upstream_response,
                        record=record,
                    )
                    if resolved_tg_id:
                        normalized_result["tg_id"] = resolved_tg_id

                if (
                    not record
                    or upstream_success is False
                    or not normalized_result.get("number")
                    or not normalized_result.get("success")
                ):
                    normalized_data = await build_tg_not_found_response(
                        context.bot,
                        search_type,
                        raw_input,
                        upstream_response,
                    )
                else:
                    normalized_data = {
                        "result": normalized_result,
                        "success": normalized_result["success"],
                        "status": normalized_result["success"],
                        "cached": False,
                        "developer": ADMIN_USERNAME,
                    }
                    set_cached_response(cache_key, normalized_data)
                formatted_json = json.dumps(
                    normalized_data,
                    indent=2,
                    ensure_ascii=False,
                )
                chunks = split_text_by_lines(formatted_json, max_size=3500)
                total_parts = len(chunks)
                
                for i, chunk in enumerate(chunks):
                    result_msg = format_info_report(
                        user_mention=user_mention,
                        target=display_target,
                        report=f"TELEGRAM {'ID' if search_type == 'ID' else 'USERNAME'} INFO",
                        payload=chunk,
                        part_number=i + 1,
                        total_parts=total_parts,
                    )
                    if i == 0:
                        success_msg = await safe_send_message(context, update.effective_chat.id, result_msg, reply_markup=reply_markup, edit_message_id=status_msg.message_id)
                        if success_msg:
                            asyncio.create_task(delete_info_after(context.bot, update.effective_chat.id, success_msg.message_id, 60, f"TELEGRAM {search_type} INFO"))
                    else:
                        new_msg = await safe_send_message(context, update.effective_chat.id, result_msg, reply_markup=reply_markup)
                        if new_msg:
                            asyncio.create_task(delete_info_after(context.bot, update.effective_chat.id, new_msg.message_id, 60, f"TELEGRAM {search_type} INFO"))
                    
                    await asyncio.sleep(0.8 if total_parts > 5 else 0.5)
            else:
                await status_msg.delete()
                error_data = await build_tg_not_found_response(
                    context.bot,
                    search_type,
                    raw_input,
                    response_body,
                )
                formatted_json = json.dumps(error_data, indent=2, ensure_ascii=False)
                caption = format_info_report(
                    user_mention=user_mention,
                    target=display_target,
                    report=f"TELEGRAM {'ID' if search_type == 'ID' else 'USERNAME'} INFO",
                    payload=formatted_json,
                )
                error_msg = await update.effective_chat.send_message(caption, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
                asyncio.create_task(delete_info_after(context.bot, update.effective_chat.id, error_msg.message_id, 60, f"TELEGRAM {search_type} INFO"))
    except asyncio.TimeoutError:
        await status_msg.delete()
        error_data = await build_tg_not_found_response(
            context.bot,
            search_type,
            raw_input,
        )
        formatted_json = json.dumps(error_data, indent=2, ensure_ascii=False)
        caption = format_info_report(
            user_mention=user_mention,
            target=display_target,
            report=f"TELEGRAM {'ID' if search_type == 'ID' else 'USERNAME'} INFO",
            payload=formatted_json,
        )
        error_msg = await update.effective_chat.send_message(caption, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
        asyncio.create_task(delete_info_after(context.bot, update.effective_chat.id, error_msg.message_id, 60, f"TELEGRAM {search_type} INFO"))
    except Exception as e:
        await status_msg.delete()
        error_data = await build_tg_not_found_response(
            context.bot,
            search_type,
            raw_input,
        )
        formatted_json = json.dumps(error_data, indent=2, ensure_ascii=False)
        caption = format_info_report(
            user_mention=user_mention,
            target=display_target,
            report=f"TELEGRAM {'ID' if search_type == 'ID' else 'USERNAME'} INFO",
            payload=formatted_json,
        )
        error_msg = await update.effective_chat.send_message(caption, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
        asyncio.create_task(delete_info_after(context.bot, update.effective_chat.id, error_msg.message_id, 60, f"TELEGRAM {search_type} INFO"))

def _ip_display_value(value: Any) -> str:
    """Convert an API value into a readable, non-empty report value."""
    if value is None or value == "" or value == []:
        return "N/A"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(", ", ": "))
    return str(value)


def _ip_status_flag(value: Any, positive: str = "Detected", negative: str = "Not detected") -> str:
    if value is None:
        return "N/A"
    return positive if bool(value) else negative


def format_ip_info_payload(data: Dict[str, Any], ip_address: str) -> str:
    """Normalize provider JSON into the stable IP report structure."""
    latitude = data.get("lat")
    longitude = data.get("lon")
    maps_url = (
        f"https://www.google.com/maps/search/?api=1&query={latitude},{longitude}"
        if latitude is not None and longitude is not None
        else None
    )

    report = {
        "ip_information_report": {
            "ip_address": ip_address,
            "ip_version": (
                "IPv4"
                if ipaddress.ip_address(ip_address).version == 4
                else "IPv6"
            ),
            "location": {
                "continent": data.get("continent"),
                "continent_code": data.get("continentCode"),
                "country": data.get("country"),
                "country_code": data.get("countryCode"),
                "region": data.get("regionName"),
                "region_code": data.get("region"),
                "city": data.get("city"),
                "district": data.get("district"),
                "postal_code": data.get("zip"),
                "coordinates": {
                    "latitude": latitude,
                    "longitude": longitude,
                },
                "timezone": data.get("timezone"),
                "utc_offset_seconds": data.get("offset"),
            },
            "network": {
                "isp": data.get("isp"),
                "organization": data.get("org"),
                "as_number": data.get("as"),
                "as_name": data.get("asname"),
                "reverse_dns": data.get("reverse"),
                "mobile_network": data.get("mobile"),
                "hosting_or_data_center": data.get("hosting"),
            },
            "security": {
                "proxy": data.get("proxy"),
                "vpn_tor_note": "Provider proxy flag only",
                "scan_status": data.get("status", "success"),
            },
            "country_details": {
                "currency": data.get("currency"),
            },
            "google_maps": {
                "url": maps_url,
            },
        }
    }
    return json.dumps(report, indent=2, ensure_ascii=False)


def ip_result_keyboard(bot_username: str, latitude: Any = None, longitude: Any = None) -> InlineKeyboardMarkup:
    """Build IP result buttons with Telegram button color and premium emoji."""
    keyboard = []
    if latitude is not None and longitude is not None:
        maps_url = (
            "https://www.google.com/maps/search/?api=1"
            f"&query={quote_plus(f'{latitude},{longitude}')}"
        )
        keyboard.append([
            InlineKeyboardButton(
                "OPEN GOOGLE MAPS",
                url=maps_url,
                _style="danger",
                _emoji_id=IP_MAP_BUTTON_EMOJI_ID or None,
            )
        ])
    keyboard.extend([
        [InlineKeyboardButton(
            "USE ME HERE",
            url=SECRET_GROUP_LINK,
            _emoji_id=PUBLIC_LINK_BUTTON_EMOJI_IDS["use_here"],
        )],
        [InlineKeyboardButton(
            "ADD ME TO YOUR GROUP",
            url=f"https://t.me/{bot_username}?startgroup=true",
            _emoji_id=PUBLIC_LINK_BUTTON_EMOJI_IDS["add_group"],
        )],
    ])
    return InlineKeyboardMarkup(keyboard)


@maintenance_aware
async def ip_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Look up an IP, convert the JSON response, and add a Google Maps button."""
    global REQUEST_COUNTER
    REQUEST_COUNTER += 1
    if not update.message or not update.message.text:
        return

    register_user(update.effective_chat.id, update.effective_chat.type, update.effective_user.id if update.effective_user else None)
    if update.effective_chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        await update.message.reply_text(
            f'<tg-emoji emoji-id="{GROUP_ONLY_EMOJI_ID}">❌</tg-emoji> '
            "This command only works inside Groups.",
            parse_mode=ParseMode.HTML,
        )
        return

    if update.effective_user.id != ADMIN_ID and is_command_disabled("ip"):
        await update.message.reply_text(
            f'<tg-emoji emoji-id="{EMOJI_ERROR_DISABLED}">❌</tg-emoji> '
            "The /ip command is currently disabled by the admin.",
            parse_mode=ParseMode.HTML,
        )
        return

    if not context.args or len(context.args) != 1:
        error_msg = await update.effective_chat.send_message(
            f'<tg-emoji emoji-id="{INVALID_USAGE_EMOJI_ID}">⚠️</tg-emoji> '
            "<b>Invalid Usage!</b>\n"
            "Format: <code>/ip &lt;ip_address&gt;</code>\n"
            "Example: <code>/ip 8.8.8.8</code>",
            parse_mode=ParseMode.HTML,
        )
        asyncio.create_task(
            delete_info_after(context.bot, update.effective_chat.id, error_msg.message_id, 10)
        )
        return

    ip_address = context.args[0].strip()
    try:
        ipaddress.ip_address(ip_address)
    except ValueError:
        error_msg = await update.effective_chat.send_message(
            f'<tg-emoji emoji-id="{INVALID_USAGE_EMOJI_ID}">⚠️</tg-emoji> '
            f"<b>Invalid IP address:</b> <code>{html.escape(ip_address)}</code>",
            parse_mode=ParseMode.HTML,
        )
        asyncio.create_task(
            delete_info_after(context.bot, update.effective_chat.id, error_msg.message_id, 10)
        )
        return

    user_mention = get_user_mention(update.effective_user)
    bot_info = await context.bot.get_me()
    status_msg = await update.effective_chat.send_message(
        f'<tg-emoji emoji-id="{SEARCHING_EMOJI_ID}">🔍</tg-emoji> '
        f"<b>Fetching IP information for {html.escape(ip_address)}...</b>",
        parse_mode=ParseMode.HTML,
    )

    try:
        if not IP_INFO_API_URL:
            raise RuntimeError("IP_INFO_API_URL is not configured")

        api_url = build_ip_info_api_url(IP_INFO_API_URL, ip_address)
        session = await get_session()
        async with session.get(api_url, timeout=API_TIMEOUT) as response:
            response_body = await response.text()
            try:
                payload = json.loads(response_body)
            except json.JSONDecodeError:
                payload = {"error": "IP API returned a non-JSON response."}

            is_success = (
                200 <= response.status < 300
                and isinstance(payload, dict)
                and str(payload.get("status", "success")).lower() != "fail"
            )

            if is_success:
                latitude = payload.get("lat")
                longitude = payload.get("lon")
                formatted_report = format_ip_info_payload(payload, ip_address)
                report_markup = ip_result_keyboard(
                    bot_info.username,
                    latitude,
                    longitude,
                )
                await send_info_report_parts(
                    context=context,
                    chat_id=update.effective_chat.id,
                    status_message=status_msg,
                    user_mention=user_mention,
                    target=ip_address,
                    report="IP INFO",
                    payload=formatted_report,
                    reply_markup=report_markup,
                    report_title="IP INFORMATION",
                    delete_label="IP",
                )
                return

            error_data = {
                "api_status": response.status,
                "target": ip_address,
                "error": payload.get("message", "IP information not found")
                if isinstance(payload, dict)
                else "IP information not found",
            }
            await send_info_report_parts(
                context=context,
                chat_id=update.effective_chat.id,
                status_message=status_msg,
                user_mention=user_mention,
                target=ip_address,
                report="IP INFO",
                payload=json.dumps(error_data, indent=2, ensure_ascii=False),
                reply_markup=ip_result_keyboard(bot_info.username),
                report_title="IP INFORMATION",
                delete_label="IP",
            )
    except Exception as exc:
        logger.exception("IP lookup failed for %s: %s", ip_address, exc)
        error_data = {
            "error": f"{type(exc).__name__}: {exc}",
            "target": ip_address,
        }
        await send_info_report_parts(
            context=context,
            chat_id=update.effective_chat.id,
            status_message=status_msg,
            user_mention=user_mention,
            target=ip_address,
            report="IP INFO",
            payload=json.dumps(error_data, indent=2, ensure_ascii=False),
            reply_markup=ip_result_keyboard(bot_info.username),
            report_title="IP INFORMATION",
            delete_label="IP",
        )


@maintenance_aware
async def lookup_num(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global REQUEST_COUNTER
    REQUEST_COUNTER += 1
    if not update.message or not update.message.text: return
    register_user(update.effective_chat.id, update.effective_chat.type, update.effective_user.id if update.effective_user else None)
    if update.effective_chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        await update.message.reply_text(
            f'<tg-emoji emoji-id="{GROUP_ONLY_EMOJI_ID}">❌</tg-emoji> '
            "This command only works inside Groups.",
            parse_mode=ParseMode.HTML,
        )
        return
    if update.effective_user.id != ADMIN_ID and is_command_disabled("num"):
        await update.message.reply_text(
            f'<tg-emoji emoji-id="{EMOJI_ERROR_DISABLED}">❌</tg-emoji> '
            "The /num command is currently disabled by the admin.",
            parse_mode=ParseMode.HTML
        )
        return

    user_mention = get_user_mention(update.effective_user)
    bot_info = await context.bot.get_me()
    if not context.args or len(context.args[0]) < 10 or not context.args[0].isdigit():
        error_msg = await update.effective_chat.send_message(
            f'<tg-emoji emoji-id="{INVALID_USAGE_EMOJI_ID}">⚠️</tg-emoji> '
            "<b>Invalid Usage!</b>\nFormat: <code>/num 9876543210</code>",
            parse_mode=ParseMode.HTML
        )
        asyncio.create_task(delete_info_after(context.bot, update.effective_chat.id, error_msg.message_id, 10))
        return

    phone_number = context.args[0]
    if any(blacklisted in phone_number for blacklisted in BLACKLISTED_NUMBERS) or is_blacklisted(phone_number):
        block_msg = await update.effective_chat.send_message(
            f"❌ <b>Access Denied!</b>\nTarget: <code>{html.escape(phone_number)}</code>\nStatus: <b>PROTECTED</b> 🛡️",
            parse_mode=ParseMode.HTML
        )
        asyncio.create_task(delete_info_after(context.bot, update.effective_chat.id, block_msg.message_id, 20))
        return

    status_msg = await update.effective_chat.send_message(
        f'<tg-emoji emoji-id="{SEARCHING_EMOJI_ID}">🔍</tg-emoji> '
        f"<b>Searching Scroll for {html.escape(phone_number)}...</b>",
        parse_mode=ParseMode.HTML
    )

    keyboard = [
        [InlineKeyboardButton(
            "USE ME HERE",
            url=SECRET_GROUP_LINK,
            _emoji_id=PUBLIC_LINK_BUTTON_EMOJI_IDS["use_here"],
        )],
        [InlineKeyboardButton(
            "ADD ME TO YOUR GROUP",
            url=f"https://t.me/{bot_info.username}?startgroup=true",
            _emoji_id=PUBLIC_LINK_BUTTON_EMOJI_IDS["add_group"],
        )]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        if not _g_u():
            await status_msg.edit_text(
                "◇ <b>Number lookup is not configured.</b>\n\n"
                "Set NUM_API_URL in the environment.",
                parse_mode=ParseMode.HTML,
            )
            return
        lookup_num_term = phone_number.lstrip("+").strip()
        if lookup_num_term.startswith("91") and len(lookup_num_term) == 12:
            lookup_num_term = lookup_num_term[2:]
        t_u = build_num_api_url(_g_u(), lookup_num_term)
        response_status, response_body = await fetch_num_api_response(t_u)
        if 200 <= response_status < 300:
                upstream_response: Any = parse_num_api_response(response_body)

                if isinstance(upstream_response, dict):
                    upstream_response["developer"] = "@Yourr_aura"
                else:
                    upstream_response = {
                        "response": upstream_response,
                        "developer": "@Yourr_aura",
                    }

                formatted_json = json.dumps(
                    upstream_response,
                    indent=2,
                    ensure_ascii=False,
                )
                await send_info_report_parts(
                    context=context,
                    chat_id=update.effective_chat.id,
                    status_message=status_msg,
                    user_mention=user_mention,
                    target=phone_number,
                    report="NUMBER INFO",
                    payload=formatted_json,
                    reply_markup=reply_markup,
                    delete_label="Number",
                )
        else:
                parsed_error: Any = parse_num_api_response(response_body)
                if isinstance(parsed_error, dict):
                    parsed_error["developer"] = ADMIN_USERNAME
                else:
                    parsed_error = {
                        "error": str(parsed_error),
                        "developer": ADMIN_USERNAME,
                    }
                error_data = {
                    "api_status": response_status,
                    "api_response": parsed_error,
                }
                formatted_json = json.dumps(error_data, indent=2, ensure_ascii=False)
                await send_info_report_parts(
                    context=context,
                    chat_id=update.effective_chat.id,
                    status_message=status_msg,
                    user_mention=user_mention,
                    target=phone_number,
                    report="NUMBER INFO",
                    payload=formatted_json,
                    reply_markup=reply_markup,
                    delete_label="Number",
                )
    except asyncio.TimeoutError:
        await status_msg.delete()
        error_data = {
            "error": "Number API request timed out",
            "target": phone_number,
            "developer": "@Yourr_aura",
        }
        formatted_json = json.dumps(error_data, indent=2, ensure_ascii=False)
        caption = format_info_report(
            user_mention=user_mention,
            target=phone_number,
            report="NUMBER INFO",
            payload=formatted_json,
        )
        error_msg = await update.effective_chat.send_message(caption, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
        asyncio.create_task(delete_info_after(context.bot, update.effective_chat.id, error_msg.message_id, 60, "Number"))
    except Exception as e:
        await status_msg.delete()
        error_data = {
            "error": f"{type(e).__name__}: {e}",
            "target": phone_number,
            "developer": "@Yourr_aura",
        }
        formatted_json = json.dumps(error_data, indent=2, ensure_ascii=False)
        caption = format_info_report(
            user_mention=user_mention,
            target=phone_number,
            report="NUMBER INFO",
            payload=formatted_json,
        )
        error_msg = await update.effective_chat.send_message(caption, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
        asyncio.create_task(delete_info_after(context.bot, update.effective_chat.id, error_msg.message_id, 60, "Number"))

@maintenance_aware
async def adhar_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global REQUEST_COUNTER
    REQUEST_COUNTER += 1
    if not update.message or not update.message.text: return
    register_user(update.effective_chat.id, update.effective_chat.type, update.effective_user.id if update.effective_user else None)
    if update.effective_chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        await update.message.reply_text(
            f'<tg-emoji emoji-id="{GROUP_ONLY_EMOJI_ID}">❌</tg-emoji> '
            "This command only works inside Groups.",
            parse_mode=ParseMode.HTML,
        )
        return
    if update.effective_user.id != ADMIN_ID and is_command_disabled("adhar"):
        await update.message.reply_text(
            f'<tg-emoji emoji-id="{EMOJI_ERROR_DISABLED}">❌</tg-emoji> '
            "The /adhar command is currently disabled by the admin.",
            parse_mode=ParseMode.HTML
        )
        return

    user_mention = get_user_mention(update.effective_user)
    args = context.args
    if not args or len(args) < 1:
        error_msg = await update.effective_chat.send_message(
            f'<tg-emoji emoji-id="{INVALID_USAGE_EMOJI_ID}">⚠️</tg-emoji> '
            "<b>Invalid Usage!</b>\nFormat: <code>/adhar &lt;aadhaar_number&gt;</code>\n"
            "Example: <code>/adhar 413509342303</code> (12 digits)",
            parse_mode=ParseMode.HTML
        )
        asyncio.create_task(delete_info_after(context.bot, update.effective_chat.id, error_msg.message_id, 10))
        return
    aadhaar_number = re.sub(r'\D', '', args[0])
    if not aadhaar_number or len(aadhaar_number) != 12:
        error_msg = await update.effective_chat.send_message(
            f'<tg-emoji emoji-id="{INVALID_USAGE_EMOJI_ID}">⚠️</tg-emoji> '
            "<b>Invalid Aadhaar number!</b>\nPlease provide a valid 12-digit Aadhaar number.",
            parse_mode=ParseMode.HTML
        )
        asyncio.create_task(delete_info_after(context.bot, update.effective_chat.id, error_msg.message_id, 10))
        return
    if any(black in aadhaar_number for black in BLACKLISTED_NUMBERS) or is_blacklisted(aadhaar_number):
        block_msg = await update.effective_chat.send_message(
            f"❌ <b>Access Denied!</b>\nTarget: <code>{html.escape(aadhaar_number)}</code>\nStatus: <b>PROTECTED</b> 🛡️",
            parse_mode=ParseMode.HTML
        )
        asyncio.create_task(delete_info_after(context.bot, update.effective_chat.id, block_msg.message_id, 20))
        return

    status_msg = await update.effective_chat.send_message(
        f'<tg-emoji emoji-id="{SEARCHING_EMOJI_ID}">🔍</tg-emoji> '
        f"<b>Fetching Aadhaar details for {html.escape(aadhaar_number)}...</b>",
        parse_mode=ParseMode.HTML
    )

    bot_info = await context.bot.get_me()
    keyboard = [
        [InlineKeyboardButton(
            "USE ME HERE",
            url=SECRET_GROUP_LINK,
            _emoji_id=PUBLIC_LINK_BUTTON_EMOJI_IDS["use_here"],
        )],
        [InlineKeyboardButton(
            "ADD ME TO YOUR GROUP",
            url=f"https://t.me/{bot_info.username}?startgroup=true",
            _emoji_id=PUBLIC_LINK_BUTTON_EMOJI_IDS["add_group"],
        )]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        url = AADHAAR_API_URL.replace("{aadhaar}", quote_plus(aadhaar_number))
        session = await get_session()
        async with session.get(url, timeout=API_TIMEOUT) as resp:
            if resp.status == 200:
                try:
                    data = await resp.json()
                    if isinstance(data, dict):
                        data.pop("key_details", None)
                    formatted_json = json.dumps(data, indent=2, ensure_ascii=False)
                except Exception:
                    formatted_json = await resp.text()

                await send_info_report_parts(
                    context=context,
                    chat_id=update.effective_chat.id,
                    status_message=status_msg,
                    user_mention=user_mention,
                    target=aadhaar_number,
                    report="AADHAAR DETAILS",
                    payload=formatted_json,
                    reply_markup=reply_markup,
                    report_title="AADHAAR SCROLL",
                    delete_label="Aadhaar",
                )
            else:
                await status_msg.delete()
                error_text = f"API returned status {resp.status}\nNo data found for {aadhaar_number}."
                caption = format_info_report(
                    user_mention=user_mention,
                    target=aadhaar_number,
                    report="AADHAAR DETAILS",
                    payload=error_text,
                    report_title="AADHAAR SCROLL",
                )
                error_msg = await update.effective_chat.send_message(caption, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
                asyncio.create_task(delete_info_after(context.bot, update.effective_chat.id, error_msg.message_id, 60, "Aadhaar"))
    except asyncio.TimeoutError:
        await status_msg.delete()
        error_text = "API Request Timeout - Please try again"
        caption = format_info_report(
            user_mention=user_mention,
            target=aadhaar_number,
            report="AADHAAR DETAILS",
            payload=error_text,
            report_title="AADHAAR SCROLL",
        )
        error_msg = await update.effective_chat.send_message(caption, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
        asyncio.create_task(delete_info_after(context.bot, update.effective_chat.id, error_msg.message_id, 60, "Aadhaar"))
    except Exception as e:
        await status_msg.delete()
        error_text = f"API Error: {str(e)}"
        caption = format_info_report(
            user_mention=user_mention,
            target=aadhaar_number,
            report="AADHAAR DETAILS",
            payload=error_text,
            report_title="AADHAAR SCROLL",
        )
        error_msg = await update.effective_chat.send_message(caption, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
        asyncio.create_task(delete_info_after(context.bot, update.effective_chat.id, error_msg.message_id, 60, "Aadhaar"))

# ==================== FREE FIRE PLAYER INFO COMMAND ====================
@maintenance_aware
async def ffinfo_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global REQUEST_COUNTER
    REQUEST_COUNTER += 1
    if not update.message or not update.message.text:
        return

    register_user(update.effective_chat.id, update.effective_chat.type, update.effective_user.id if update.effective_user else None)
    if update.effective_chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        await update.message.reply_text(
            f'<tg-emoji emoji-id="{GROUP_ONLY_EMOJI_ID}">❌</tg-emoji> '
            "This command only works inside Groups.",
            parse_mode=ParseMode.HTML,
        )
        return

    if update.effective_user.id != ADMIN_ID and is_command_disabled("ffinfo"):
        await update.message.reply_text(
            f'<tg-emoji emoji-id="{EMOJI_ERROR_DISABLED}">❌</tg-emoji> '
            "The /ffinfo command is currently disabled by the admin.",
            parse_mode=ParseMode.HTML,
        )
        return

    user_mention = get_user_mention(update.effective_user)
    bot_info = await context.bot.get_me()
    args = context.args

    if not args or not args[0].strip().isdigit() or len(args[0].strip()) > 20:
        error_msg = await update.effective_chat.send_message(
            f'<tg-emoji emoji-id="{INVALID_USAGE_EMOJI_ID}">⚠️</tg-emoji> '
            "<b>Invalid Usage!</b>\n"
            "Format: <code>/ffinfo &lt;uid&gt;</code>\n"
            "Example: <code>/ffinfo 10323158965</code>\n"
            "UID must contain only digits.",
            parse_mode=ParseMode.HTML,
        )
        asyncio.create_task(
            delete_info_after(
                context.bot,
                update.effective_chat.id,
                error_msg.message_id,
                10,
            )
        )
        return

    player_uid = args[0].strip()
    status_msg = await update.effective_chat.send_message(
        f'<tg-emoji emoji-id="{SEARCHING_EMOJI_ID}">🔍</tg-emoji> '
        f"<b>Fetching Free Fire player info for "
        f"{html.escape(player_uid)}...</b>",
        parse_mode=ParseMode.HTML,
    )

    keyboard = [
        [InlineKeyboardButton(
            "USE ME HERE",
            url=SECRET_GROUP_LINK,
            _emoji_id=PUBLIC_LINK_BUTTON_EMOJI_IDS["use_here"],
        )],
        [InlineKeyboardButton(
            "ADD ME TO YOUR GROUP",
            url=f"https://t.me/{bot_info.username}?startgroup=true",
            _emoji_id=PUBLIC_LINK_BUTTON_EMOJI_IDS["add_group"],
        )],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    cache_key = f"ffinfo_{player_uid}"

    cached_data = get_cached_response(cache_key)
    if cached_data is not None:
        formatted_json = json.dumps(
            cached_data,
            indent=2,
            ensure_ascii=False,
        )
        await send_info_report_parts(
            context=context,
            chat_id=update.effective_chat.id,
            status_message=status_msg,
            user_mention=user_mention,
            target=player_uid,
            report="FREE FIRE PLAYER INFO",
            payload=formatted_json,
            reply_markup=reply_markup,
            report_title="FREE FIRE REPORT (Cached)",
            delete_label="Free Fire",
        )
        return

    async def send_ffinfo_report(payload: Any) -> None:
        formatted_json = (
            json.dumps(payload, indent=2, ensure_ascii=False)
            if not isinstance(payload, str)
            else payload
        )
        await send_info_report_parts(
            context=context,
            chat_id=update.effective_chat.id,
            status_message=status_msg,
            user_mention=user_mention,
            target=player_uid,
            report="FREE FIRE PLAYER INFO",
            payload=formatted_json,
            reply_markup=reply_markup,
            report_title="FREE FIRE REPORT",
            delete_label="Free Fire",
        )

    try:
        if not FF_INFO_API_URL:
            await send_ffinfo_report({
                "error": "Free Fire info API is not configured.",
                "developer": ADMIN_USERNAME,
            })
            return

        api_url = build_ff_info_api_url(FF_INFO_API_URL, player_uid)
        session = await get_session()
        async with session.get(api_url, timeout=FF_INFO_API_TIMEOUT) as resp:
            response_body = await resp.text()
            try:
                upstream_response: Any = json.loads(response_body)
            except json.JSONDecodeError:
                upstream_response = response_body.strip() or "Empty response received from the API."

            if isinstance(upstream_response, dict):
                upstream_response.pop("credits", None)
                response_status = str(upstream_response.get("status", "")).lower()

                if response_status == "error":
                    upstream_response["data"] = {
                        "error": "Data not found",
                        "developer": ADMIN_USERNAME,
                    }
                    upstream_response.pop("developer", None)
                else:
                    upstream_response["developer"] = ADMIN_USERNAME

                if 200 <= resp.status < 300:
                    if upstream_response.get("status") == "success":
                        set_cached_response(cache_key, upstream_response)
                    await send_ffinfo_report(upstream_response)
                else:
                    await send_ffinfo_report(upstream_response)
            elif 200 <= resp.status < 300:
                await send_ffinfo_report({
                    "response": upstream_response,
                    "developer": ADMIN_USERNAME,
                })
            else:
                await send_ffinfo_report({
                    "api_status": resp.status,
                    "api_response": upstream_response,
                    "data": {
                        "error": "Data not found",
                    },
                    "developer": ADMIN_USERNAME,
                })
    except asyncio.TimeoutError:
        await send_ffinfo_report({
            "error": "Free Fire info API request timed out.",
            "target": player_uid,
            "developer": ADMIN_USERNAME,
        })
    except Exception as e:
        logger.exception("Free Fire info lookup failed for UID %s: %s", player_uid, e)
        await send_ffinfo_report({
            "error": f"{type(e).__name__}: {e}",
            "target": player_uid,
            "developer": ADMIN_USERNAME,
        })

# ==================== VEHICLE COMMAND ====================
@maintenance_aware
async def vehicle_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global REQUEST_COUNTER
    REQUEST_COUNTER += 1
    if not update.message or not update.message.text:
        return
    register_user(update.effective_chat.id, update.effective_chat.type, update.effective_user.id if update.effective_user else None)
    
    if update.effective_chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        await update.message.reply_text(
            f'<tg-emoji emoji-id="{GROUP_ONLY_EMOJI_ID}">❌</tg-emoji> '
            "This command only works inside Groups.",
            parse_mode=ParseMode.HTML,
        )
        return
    
    if update.effective_user.id != ADMIN_ID and is_command_disabled("veh"):
        await update.message.reply_text(
            f'<tg-emoji emoji-id="{EMOJI_ERROR_DISABLED}">❌</tg-emoji> '
            "The /veh command is currently disabled by the admin.",
            parse_mode=ParseMode.HTML
        )
        return

    user_mention = get_user_mention(update.effective_user)
    bot_info = await context.bot.get_me()
    args = context.args
    
    if not args or len(args) < 1:
        error_msg = await update.effective_chat.send_message(
            f'<tg-emoji emoji-id="{INVALID_USAGE_EMOJI_ID}">⚠️</tg-emoji> '
            "<b>Invalid Usage!</b>\nFormat: <code>/veh &lt;vehicle_number&gt;</code>\n"
            "Example: <code>/veh RJ14CV0005</code>",
            parse_mode=ParseMode.HTML
        )
        asyncio.create_task(delete_info_after(context.bot, update.effective_chat.id, error_msg.message_id, 10))
        return

    vehicle_number = args[0].strip().upper()
    
    # Validate vehicle number format (basic check)
    if len(vehicle_number) < 8 or len(vehicle_number) > 12:
        error_msg = await update.effective_chat.send_message(
            f'<tg-emoji emoji-id="{INVALID_USAGE_EMOJI_ID}">⚠️</tg-emoji> '
            "<b>Invalid vehicle number!</b>\n"
            "Please provide a valid vehicle registration number.\n"
            "Example: <code>RJ14CV0005</code>",
            parse_mode=ParseMode.HTML
        )
        asyncio.create_task(delete_info_after(context.bot, update.effective_chat.id, error_msg.message_id, 10))
        return

    status_msg = await update.effective_chat.send_message(
        f'<tg-emoji emoji-id="{SEARCHING_EMOJI_ID}">🔍</tg-emoji> '
        f"<b>Fetching vehicle details for {html.escape(vehicle_number)}...</b>",
        parse_mode=ParseMode.HTML
    )

    keyboard = [
        [InlineKeyboardButton(
            "USE ME HERE",
            url=SECRET_GROUP_LINK,
            _emoji_id=PUBLIC_LINK_BUTTON_EMOJI_IDS["use_here"],
        )],
        [InlineKeyboardButton(
            "ADD ME TO YOUR GROUP",
            url=f"https://t.me/{bot_info.username}?startgroup=true",
            _emoji_id=PUBLIC_LINK_BUTTON_EMOJI_IDS["add_group"],
        )]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        separator = "&" if "?" in VEHICLE_API_URL else "?"
        api_url = f"{VEHICLE_API_URL}{separator}key={VEHICLE_API_KEY}&type=vehicle&term={quote_plus(vehicle_number)}"
        
        session = await get_session()
        async with session.get(api_url, timeout=API_TIMEOUT) as resp:
            if resp.status == 200:
                try:
                    data = await resp.json()
                    if isinstance(data, dict):
                        # Remove any sensitive metadata if needed
                        if "metadata" in data:
                            del data["metadata"]
                        data["developer"] = ADMIN_USERNAME
                except Exception:
                    data = await resp.text()
                    if not data.strip():
                        data = "Empty response received from the API."
                
                if isinstance(data, dict) and data.get("status") == "error":
                    # Handle API error response
                    error_text = f"❌ <b>Vehicle Not Found</b>\n\nNumber: <code>{html.escape(vehicle_number)}</code>\n\n{data.get('message', 'No details found.')}"
                    await status_msg.delete()
                    error_msg = await update.effective_chat.send_message(
                        error_text,
                        parse_mode=ParseMode.HTML,
                        reply_markup=reply_markup
                    )
                    asyncio.create_task(delete_info_after(context.bot, update.effective_chat.id, error_msg.message_id, 60, "Vehicle"))
                    return
                
                formatted_json = json.dumps(data, indent=2, ensure_ascii=False) if isinstance(data, dict) else data
                
                await send_info_report_parts(
                    context=context,
                    chat_id=update.effective_chat.id,
                    status_message=status_msg,
                    user_mention=user_mention,
                    target=vehicle_number,
                    report="VEHICLE INFO",
                    payload=formatted_json,
                    reply_markup=reply_markup,
                    report_title="VEHICLE REPORT",
                    delete_label="Vehicle",
                    delay=0.8,
                )
            else:
                await status_msg.delete()
                error_text = f"API returned status {resp.status}\nNo data found for {html.escape(vehicle_number)}."
                caption = format_info_report(
                    user_mention=user_mention,
                    target=vehicle_number,
                    report="VEHICLE INFO",
                    payload=error_text,
                    report_title="VEHICLE REPORT",
                )
                error_msg = await update.effective_chat.send_message(caption, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
                asyncio.create_task(delete_info_after(context.bot, update.effective_chat.id, error_msg.message_id, 60, "Vehicle"))
                
    except asyncio.TimeoutError:
        await status_msg.delete()
        error_text = "API Request Timeout - Please try again"
        caption = format_info_report(
            user_mention=user_mention,
            target=vehicle_number,
            report="VEHICLE INFO",
            payload=error_text,
            report_title="VEHICLE REPORT",
        )
        error_msg = await update.effective_chat.send_message(caption, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
        asyncio.create_task(delete_info_after(context.bot, update.effective_chat.id, error_msg.message_id, 60, "Vehicle"))
        
    except Exception as e:
        await status_msg.delete()
        error_text = f"API Error: {str(e)}"
        caption = format_info_report(
            user_mention=user_mention,
            target=vehicle_number,
            report="VEHICLE INFO",
            payload=error_text,
            report_title="VEHICLE REPORT",
        )
        error_msg = await update.effective_chat.send_message(caption, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
        asyncio.create_task(delete_info_after(context.bot, update.effective_chat.id, error_msg.message_id, 60, "Vehicle"))

# ==================== NUMBER TO VEHICLE COMMAND ====================
@maintenance_aware
async def num2veh_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global REQUEST_COUNTER
    REQUEST_COUNTER += 1
    if not update.message or not update.message.text:
        return
    register_user(update.effective_chat.id, update.effective_chat.type, update.effective_user.id if update.effective_user else None)

    if update.effective_chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        await update.message.reply_text(
            f'<tg-emoji emoji-id="{GROUP_ONLY_EMOJI_ID}">❌</tg-emoji> '
            "This command only works inside Groups.",
            parse_mode=ParseMode.HTML,
        )
        return

    if update.effective_user.id != ADMIN_ID and is_command_disabled("num2veh"):
        await update.message.reply_text(
            f'<tg-emoji emoji-id="{EMOJI_ERROR_DISABLED}">❌</tg-emoji> '
            "The /num2veh command is currently disabled by the admin.",
            parse_mode=ParseMode.HTML
        )
        return

    user_mention = get_user_mention(update.effective_user)
    bot_info = await context.bot.get_me()
    args = context.args

    if not args or len(args) < 1:
        error_msg = await update.effective_chat.send_message(
            f'<tg-emoji emoji-id="{INVALID_USAGE_EMOJI_ID}">⚠️</tg-emoji> '
            "<b>Invalid Usage!</b>\nFormat: <code>/num2veh &lt;phone_number&gt;</code>\n"
            "Example: <code>/num2veh 7502379832</code>",
            parse_mode=ParseMode.HTML
        )
        asyncio.create_task(delete_info_after(context.bot, update.effective_chat.id, error_msg.message_id, 10))
        return

    phone_number = re.sub(r'\D', '', args[0])
    if not phone_number or len(phone_number) < 10 or len(phone_number) > 13:
        error_msg = await update.effective_chat.send_message(
            f'<tg-emoji emoji-id="{INVALID_USAGE_EMOJI_ID}">⚠️</tg-emoji> '
            "<b>Invalid phone number!</b>\n"
            "Please provide a valid phone number (10-13 digits).\n"
            "Example: <code>/num2veh 7502379832</code>",
            parse_mode=ParseMode.HTML
        )
        asyncio.create_task(delete_info_after(context.bot, update.effective_chat.id, error_msg.message_id, 10))
        return

    if any(black in phone_number for black in BLACKLISTED_NUMBERS) or is_blacklisted(phone_number):
        block_msg = await update.effective_chat.send_message(
            f"❌ <b>Access Denied!</b>\nTarget: <code>{html.escape(phone_number)}</code>\nStatus: <b>PROTECTED</b> 🛡️",
            parse_mode=ParseMode.HTML
        )
        asyncio.create_task(delete_info_after(context.bot, update.effective_chat.id, block_msg.message_id, 20))
        return

    status_msg = await update.effective_chat.send_message(
        f'<tg-emoji emoji-id="{SEARCHING_EMOJI_ID}">🔍</tg-emoji> '
        f"<b>Fetching vehicle details for number {html.escape(phone_number)}...</b>",
        parse_mode=ParseMode.HTML
    )

    keyboard = [
        [InlineKeyboardButton(
            "USE ME HERE",
            url=SECRET_GROUP_LINK,
            _emoji_id=PUBLIC_LINK_BUTTON_EMOJI_IDS["use_here"],
        )],
        [InlineKeyboardButton(
            "ADD ME TO YOUR GROUP",
            url=f"https://t.me/{bot_info.username}?startgroup=true",
            _emoji_id=PUBLIC_LINK_BUTTON_EMOJI_IDS["add_group"],
        )]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        api_url = NUM2VEH_API_URL.replace("{number}", quote_plus(phone_number))
        session = await get_session()
        async with session.get(api_url, timeout=API_TIMEOUT) as resp:
            if resp.status == 200:
                try:
                    data = await resp.json()
                    if isinstance(data, dict):
                        data.pop("key_details", None)
                        data["developer"] = ADMIN_USERNAME
                except Exception:
                    data = await resp.text()
                    if not data.strip():
                        data = "Empty response received from the API."

                if isinstance(data, dict) and data.get("status") == "error":
                    error_text = f"❌ <b>No Vehicle Found</b>\n\nNumber: <code>{html.escape(phone_number)}</code>\n\n{data.get('message', 'No vehicle details found for this number.')}"
                    await status_msg.delete()
                    error_msg = await update.effective_chat.send_message(
                        error_text,
                        parse_mode=ParseMode.HTML,
                        reply_markup=reply_markup
                    )
                    asyncio.create_task(delete_info_after(context.bot, update.effective_chat.id, error_msg.message_id, 60, "Num2Veh"))
                    return

                formatted_json = json.dumps(data, indent=2, ensure_ascii=False) if isinstance(data, (dict, list)) else data

                await send_info_report_parts(
                    context=context,
                    chat_id=update.effective_chat.id,
                    status_message=status_msg,
                    user_mention=user_mention,
                    target=phone_number,
                    report="NUM2VEH DETAILS",
                    payload=formatted_json,
                    reply_markup=reply_markup,
                    report_title="NUM2VEH REPORT",
                    delete_label="Num2Veh",
                    delay=0.8,
                )
            else:
                await status_msg.delete()
                error_text = f"API returned status {resp.status}\nNo vehicle data found for {html.escape(phone_number)}."
                caption = format_info_report(
                    user_mention=user_mention,
                    target=phone_number,
                    report="NUM2VEH DETAILS",
                    payload=error_text,
                    report_title="NUM2VEH REPORT",
                )
                error_msg = await update.effective_chat.send_message(caption, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
                asyncio.create_task(delete_info_after(context.bot, update.effective_chat.id, error_msg.message_id, 60, "Num2Veh"))

    except asyncio.TimeoutError:
        await status_msg.delete()
        error_text = "API Request Timeout - Please try again"
        caption = format_info_report(
            user_mention=user_mention,
            target=phone_number,
            report="NUM2VEH DETAILS",
            payload=error_text,
            report_title="NUM2VEH REPORT",
        )
        error_msg = await update.effective_chat.send_message(caption, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
        asyncio.create_task(delete_info_after(context.bot, update.effective_chat.id, error_msg.message_id, 60, "Num2Veh"))

    except Exception as e:
        await status_msg.delete()
        error_text = f"API Error: {str(e)}"
        caption = format_info_report(
            user_mention=user_mention,
            target=phone_number,
            report="NUM2VEH DETAILS",
            payload=error_text,
            report_title="NUM2VEH REPORT",
        )
        error_msg = await update.effective_chat.send_message(caption, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
        asyncio.create_task(delete_info_after(context.bot, update.effective_chat.id, error_msg.message_id, 60, "Num2Veh"))

# ==================== LEAK COMMAND ====================
@maintenance_aware
async def leak_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global REQUEST_COUNTER
    REQUEST_COUNTER += 1
    if not update.message or not update.message.text:
        return
    register_user(update.effective_chat.id, update.effective_chat.type, update.effective_user.id if update.effective_user else None)
    if update.effective_chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        await update.message.reply_text(
            f'<tg-emoji emoji-id="{GROUP_ONLY_EMOJI_ID}">❌</tg-emoji> '
            "This command only works inside Groups.",
            parse_mode=ParseMode.HTML,
        )
        return
    if update.effective_user.id != ADMIN_ID and is_command_disabled("leak"):
        await update.message.reply_text(
            f'<tg-emoji emoji-id="{EMOJI_ERROR_DISABLED}">❌</tg-emoji> '
            "The /leak command is currently disabled by the admin.",
            parse_mode=ParseMode.HTML
        )
        return

    user_id = update.effective_user.id
    trial_notice = ""
    if user_id == ADMIN_ID:
        pass
    else:
        if is_leak_approved(user_id):
            pass
        else:
            trial_users = get_trial_users()
            trial_user_limit = get_trial_user_limit()
            if user_id not in trial_users:
                # If trial_user_limit > 0, enforce limit. If <= 0, unlimited active users can try
                if trial_user_limit > 0 and len(trial_users) >= trial_user_limit:
                    await update.message.reply_text(
                        f'<tg-emoji emoji-id="{EMOJI_ERROR_DISABLED}">❌</tg-emoji> '
                        f"<b>Trial user limit reached!</b>\n\n"
                        f"Only {trial_user_limit} users can try /leak for free.\n"
                        f"Please contact admin for approval - {ADMIN_USERNAME}",
                        parse_mode=ParseMode.HTML
                    )
                    return
                add_trial_user(user_id)
            used = get_trial_usage(user_id)
            limit = get_trial_limit()
            if limit <= 0:
                await update.message.reply_text(
                    f'<tg-emoji emoji-id="{EMOJI_ERROR_DISABLED}">❌</tg-emoji> '
                    "<b>Trial not available</b>\n\nThe trial limit is set to 0. Please contact admin for approval.",
                    parse_mode=ParseMode.HTML
                )
                return
            if used >= limit:
                remaining = 0
                await update.message.reply_text(
                    f'<tg-emoji emoji-id="{EMOJI_ERROR_DISABLED}">❌</tg-emoji> '
                    f"<b>You have used your {used} free trials.</b>\n\n"
                    f'<tg-emoji emoji-id="{EMOJI_PAID_REQUIRED}">💰</tg-emoji> '
                    f"<b>Paid Access Required:</b>\n"
                    f"Contact admin for approval - {ADMIN_USERNAME}\n\n"
                    f'<tg-emoji emoji-id="{EMOJI_TRIAL_HEADER}">📊</tg-emoji> '
                    f"Your free uses trial: {remaining} / {limit} remaining",
                    parse_mode=ParseMode.HTML
                )
                return
            increment_trial_usage(user_id)
            remaining = limit - (used + 1)
            trial_notice = f"\n\n🎯 <i>You have {remaining} trial use(s) remaining.</i>"
    
    user_mention = get_user_mention(update.effective_user)
    bot_info = await context.bot.get_me()
    args = context.args
    if not args or len(args) < 1:
        error_msg = await update.effective_chat.send_message(
            f'<tg-emoji emoji-id="{INVALID_USAGE_EMOJI_ID}">⚠️</tg-emoji> '
            "<b>Invalid Usage!</b>\nFormat: <code>/leak &lt;countrycode_number&gt;</code>\n"
            "Example: <code>/leak 911234567890</code> (country code + number, no '+' sign)",
            parse_mode=ParseMode.HTML
        )
        asyncio.create_task(delete_info_after(context.bot, update.effective_chat.id, error_msg.message_id, 10))
        return

    raw_input = re.sub(r'\D', '', args[0])
    if len(raw_input) < 10:
        error_msg = await update.effective_chat.send_message(
            f'<tg-emoji emoji-id="{INVALID_USAGE_EMOJI_ID}">⚠️</tg-emoji> '
            "<b>Invalid number!</b>\nPlease provide a number with country code (minimum 10 digits).",
            parse_mode=ParseMode.HTML
        )
        asyncio.create_task(delete_info_after(context.bot, update.effective_chat.id, error_msg.message_id, 10))
        return

    if any(black in raw_input for black in BLACKLISTED_NUMBERS) or is_blacklisted(raw_input):
        block_msg = await update.effective_chat.send_message(
            f"❌ <b>Access Denied!</b>\nTarget: <code>{html.escape(raw_input)}</code>\nStatus: <b>PROTECTED</b> 🛡️",
            parse_mode=ParseMode.HTML
        )
        asyncio.create_task(delete_info_after(context.bot, update.effective_chat.id, block_msg.message_id, 20))
        return

    status_msg = await update.effective_chat.send_message(
        f'<tg-emoji emoji-id="{SEARCHING_EMOJI_ID}">🔍</tg-emoji> '
        f"<b>Leaking data for {html.escape(raw_input)}...</b>",
        parse_mode=ParseMode.HTML
    )

    api_url = OSINT_API_URL.replace("{term}", quote_plus(raw_input))

    keyboard = [
        [InlineKeyboardButton(
            "USE ME HERE",
            url=SECRET_GROUP_LINK,
            _emoji_id=PUBLIC_LINK_BUTTON_EMOJI_IDS["use_here"],
        )],
        [InlineKeyboardButton(
            "ADD ME TO YOUR GROUP",
            url=f"https://t.me/{bot_info.username}?startgroup=true",
            _emoji_id=PUBLIC_LINK_BUTTON_EMOJI_IDS["add_group"],
        )]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    LEAK_API_TIMEOUT = aiohttp.ClientTimeout(total=25, connect=5, sock_read=20)
    formatted_text = ""

    try:
        session = await get_session()
        async with session.get(api_url, timeout=LEAK_API_TIMEOUT) as resp:
            if resp.status == 200:
                try:
                    data = await resp.json()
                    if isinstance(data, dict):
                        if "metadata" in data:
                            del data["metadata"]
                        if "result" in data:
                            formatted_data = data["result"]
                        elif "data" in data:
                            formatted_data = data["data"]
                        else:
                            formatted_data = data
                    else:
                        formatted_data = data
                    
                    new_data = {
                        "success": True,
                        "result": formatted_data,
                        "cached": False,
                        "proxyUsed": "none",
                        "attempt": 1,
                        "developer": "@Yourr_aura"
                    }
                    formatted_text = json.dumps(new_data, indent=2, ensure_ascii=False)
                except Exception:
                    formatted_text = await resp.text()
                    if not formatted_text.strip():
                        formatted_text = "Empty response received from the API."
            else:
                await status_msg.delete()
                error_text = f"API returned status {resp.status}\nNo data found for {raw_input}."
                caption = format_info_report(
                    user_mention=user_mention,
                    target=raw_input,
                    report="DATA LEAK INFO",
                    payload=error_text,
                    report_title="LEAK REPORT",
                )
                error_msg = await update.effective_chat.send_message(caption, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
                asyncio.create_task(delete_info_after(context.bot, update.effective_chat.id, error_msg.message_id, 60, "Leak"))
                return
                
    except asyncio.TimeoutError:
        await status_msg.delete()
        error_text = "API Request Timeout - Render Server taking too long. Please try again"
        caption = format_info_report(
            user_mention=user_mention,
            target=raw_input,
            report="DATA LEAK INFO",
            payload=error_text,
            report_title="LEAK REPORT",
        )
        error_msg = await update.effective_chat.send_message(caption, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
        asyncio.create_task(delete_info_after(context.bot, update.effective_chat.id, error_msg.message_id, 60, "Leak"))
        return
        
    except Exception as e:
        await status_msg.delete()
        error_text = f"API Error: {str(e)}"
        caption = format_info_report(
            user_mention=user_mention,
            target=raw_input,
            report="DATA LEAK INFO",
            payload=error_text,
            report_title="LEAK REPORT",
        )
        error_msg = await update.effective_chat.send_message(caption, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
        asyncio.create_task(delete_info_after(context.bot, update.effective_chat.id, error_msg.message_id, 60, "Leak"))
        return

    if formatted_text:
        if user_id != ADMIN_ID and not is_leak_approved(user_id) and trial_notice:
            formatted_text += trial_notice
        await send_info_report_parts(
            context=context,
            chat_id=update.effective_chat.id,
            status_message=status_msg,
            user_mention=user_mention,
            target=raw_input,
            report="DATA LEAK INFO",
            payload=formatted_text,
            reply_markup=reply_markup,
            report_title="LEAK REPORT",
            delete_label="Leak",
            delay=1.2,
        )

# ==================== EMAIL OSINT COMMAND ====================
@maintenance_aware
async def email_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global REQUEST_COUNTER
    REQUEST_COUNTER += 1
    if not update.message or not update.message.text:
        return
    register_user(update.effective_chat.id, update.effective_chat.type, update.effective_user.id if update.effective_user else None)

    if update.effective_chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        await update.message.reply_text(
            f'<tg-emoji emoji-id="{GROUP_ONLY_EMOJI_ID}">❌</tg-emoji> '
            "This command only works inside Groups.",
            parse_mode=ParseMode.HTML,
        )
        return

    if update.effective_user.id != ADMIN_ID and is_command_disabled("email"):
        await update.message.reply_text(
            f'<tg-emoji emoji-id="{EMOJI_ERROR_DISABLED}">❌</tg-emoji> '
            "The /email command is currently disabled by the admin.",
            parse_mode=ParseMode.HTML
        )
        return

    user_mention = get_user_mention(update.effective_user)
    bot_info = await context.bot.get_me()
    args = context.args

    if not args or len(args) < 1:
        error_msg = await update.effective_chat.send_message(
            f'<tg-emoji emoji-id="{INVALID_USAGE_EMOJI_ID}">⚠️</tg-emoji> '
            "<b>Invalid Usage!</b>\nFormat: <code>/email &lt;email_address&gt;</code>\n"
            "Example: <code>/email example@gmail.com</code>",
            parse_mode=ParseMode.HTML
        )
        asyncio.create_task(delete_info_after(context.bot, update.effective_chat.id, error_msg.message_id, 10))
        return

    email_input = args[0].strip()
    # Basic email validation
    if not re.match(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$', email_input):
        error_msg = await update.effective_chat.send_message(
            f'<tg-emoji emoji-id="{INVALID_USAGE_EMOJI_ID}">⚠️</tg-emoji> '
            "<b>Invalid email address!</b>\n"
            "Please provide a valid email.\n"
            "Example: <code>/email example@gmail.com</code>",
            parse_mode=ParseMode.HTML
        )
        asyncio.create_task(delete_info_after(context.bot, update.effective_chat.id, error_msg.message_id, 10))
        return

    status_msg = await update.effective_chat.send_message(
        f'<tg-emoji emoji-id="{SEARCHING_EMOJI_ID}">🔍</tg-emoji> '
        f"<b>Running OSINT lookup for {html.escape(email_input)}...</b>",
        parse_mode=ParseMode.HTML
    )

    keyboard = [
        [InlineKeyboardButton(
            "USE ME HERE",
            url=SECRET_GROUP_LINK,
            _emoji_id=PUBLIC_LINK_BUTTON_EMOJI_IDS["use_here"],
        )],
        [InlineKeyboardButton(
            "ADD ME TO YOUR GROUP",
            url=f"https://t.me/{bot_info.username}?startgroup=true",
            _emoji_id=PUBLIC_LINK_BUTTON_EMOJI_IDS["add_group"],
        )]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        api_url = OSINT_API_URL.replace("{term}", quote_plus(email_input))
        OSINT_TIMEOUT = aiohttp.ClientTimeout(total=25, connect=5, sock_read=20)
        session = await get_session()
        async with session.get(api_url, timeout=OSINT_TIMEOUT) as resp:
            if resp.status == 200:
                try:
                    data = await resp.json()
                    if isinstance(data, dict):
                        if "metadata" in data:
                            del data["metadata"]
                        if "result" in data:
                            formatted_data = data["result"]
                        elif "data" in data:
                            formatted_data = data["data"]
                        else:
                            formatted_data = data
                    else:
                        formatted_data = data

                    new_data = {
                        "success": True,
                        "result": formatted_data,
                        "cached": False,
                        "proxyUsed": "none",
                        "attempt": 1,
                        "developer": "@Yourr_aura"
                    }
                    formatted_text = json.dumps(new_data, indent=2, ensure_ascii=False)
                except Exception:
                    formatted_text = await resp.text()
                    if not formatted_text.strip():
                        formatted_text = "Empty response received from the API."

                await send_info_report_parts(
                    context=context,
                    chat_id=update.effective_chat.id,
                    status_message=status_msg,
                    user_mention=user_mention,
                    target=email_input,
                    report="EMAIL OSINT",
                    payload=formatted_text,
                    reply_markup=reply_markup,
                    report_title="EMAIL REPORT",
                    delete_label="Email",
                    delay=1.2,
                )
            else:
                await status_msg.delete()
                error_text = f"API returned status {resp.status}\nNo data found for {html.escape(email_input)}."
                caption = format_info_report(
                    user_mention=user_mention,
                    target=email_input,
                    report="EMAIL OSINT",
                    payload=error_text,
                    report_title="EMAIL REPORT",
                )
                error_msg = await update.effective_chat.send_message(caption, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
                asyncio.create_task(delete_info_after(context.bot, update.effective_chat.id, error_msg.message_id, 60, "Email"))

    except asyncio.TimeoutError:
        await status_msg.delete()
        error_text = "API Request Timeout - Please try again"
        caption = format_info_report(
            user_mention=user_mention,
            target=email_input,
            report="EMAIL OSINT",
            payload=error_text,
            report_title="EMAIL REPORT",
        )
        error_msg = await update.effective_chat.send_message(caption, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
        asyncio.create_task(delete_info_after(context.bot, update.effective_chat.id, error_msg.message_id, 60, "Email"))

    except Exception as e:
        await status_msg.delete()
        error_text = f"API Error: {str(e)}"
        caption = format_info_report(
            user_mention=user_mention,
            target=email_input,
            report="EMAIL OSINT",
            payload=error_text,
            report_title="EMAIL REPORT",
        )
        error_msg = await update.effective_chat.send_message(caption, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
        asyncio.create_task(delete_info_after(context.bot, update.effective_chat.id, error_msg.message_id, 60, "Email"))

async def approve_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized.")
        return
    if not context.args:
        await update.message.reply_text(
            f'<tg-emoji emoji-id="{INVALID_USAGE_EMOJI_ID}">⚠️</tg-emoji> '
            "<b>Usage:</b>\n"
            "• <code>/approve &lt;user_id&gt; [days]</code> – Approve single user\n"
            "• <code>/approve all [days]</code> – Approve ALL active users\n\n"
            "Examples:\n"
            "• <code>/approve 123456789 7</code> (approves single user for 7 days)\n"
            "• <code>/approve all</code> (approves all active users forever)\n"
            "• <code>/approve all 30</code> (approves all active users for 30 days)",
            parse_mode=ParseMode.HTML
        )
        return
    target = context.args[0].lower().strip()
    if target in ("all", "active"):
        days = None
        if len(context.args) >= 2 and context.args[1].isdigit():
            days = int(context.args[1])
        active_users = get_all_active_users()
        if not active_users:
            await update.message.reply_text("⚠️ No active users found in database.")
            return
        count = 0
        for uid in active_users:
            if add_leak_approval(uid, days):
                count += 1
        expiry_text = f" for {days} days" if days else " (never expires)"
        await update.message.reply_text(
            f"✅ <b>All Active Users Approved!</b>\n\n"
            f"• Total active users: <code>{len(active_users)}</code>\n"
            f"• Newly approved: <code>{count}</code>\n"
            f"• Already approved: <code>{len(active_users) - count}</code>\n"
            f"• Duration: <b>{expiry_text.strip()}</b>",
            parse_mode=ParseMode.HTML
        )
        add_log("ADMIN", f"Approved all {len(active_users)} active users for /leak{expiry_text}")
        return

    if not target.isdigit():
        await update.message.reply_text(
            f'<tg-emoji emoji-id="{INVALID_USAGE_EMOJI_ID}">⚠️</tg-emoji> '
            "<b>Usage:</b> <code>/approve &lt;user_id|all&gt; [days]</code>",
            parse_mode=ParseMode.HTML
        )
        return
    user_id = int(target)
    days = None
    if len(context.args) >= 2 and context.args[1].isdigit():
        days = int(context.args[1])
    if add_leak_approval(user_id, days):
        expiry_text = f" for {days} days" if days else " (never expires)"
        await update.message.reply_text(f"✅ User <code>{user_id}</code> approved to use /leak{expiry_text}.", parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(f"⚠️ User <code>{user_id}</code> is already approved.", parse_mode=ParseMode.HTML)

async def approve_all_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized.")
        return
    days = None
    if context.args and context.args[0].isdigit():
        days = int(context.args[0])
    active_users = get_all_active_users()
    if not active_users:
        await update.message.reply_text("⚠️ No active users found in database.")
        return
    count = 0
    for uid in active_users:
        if add_leak_approval(uid, days):
            count += 1
    expiry_text = f" for {days} days" if days else " (never expires)"
    await update.message.reply_text(
        f"✅ <b>All Active Users Approved!</b>\n\n"
        f"• Total active users: <code>{len(active_users)}</code>\n"
        f"• Newly approved: <code>{count}</code>\n"
        f"• Already approved: <code>{len(active_users) - count}</code>\n"
        f"• Duration: <b>{expiry_text.strip()}</b>",
        parse_mode=ParseMode.HTML
    )
    add_log("ADMIN", f"Approved all {len(active_users)} active users for /leak{expiry_text}")

async def revoke_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized.")
        return
    if not context.args:
        await update.message.reply_text(
            f'<tg-emoji emoji-id="{INVALID_USAGE_EMOJI_ID}">⚠️</tg-emoji> '
            "<b>Usage:</b>\n"
            "• <code>/revoke &lt;user_id&gt;</code> – Revoke single user\n"
            "• <code>/revoke all</code> – Revoke ALL users",
            parse_mode=ParseMode.HTML,
        )
        return
    target = context.args[0].lower().strip()
    if target in ("all", "active"):
        approvals = get_leak_approvals()
        total = len(approvals)
        db = load_db()
        db["leak_approvals"] = []
        save_db(db)
        await update.message.reply_text(f"✅ Revoked leak access for all <code>{total}</code> approved users.", parse_mode=ParseMode.HTML)
        add_log("ADMIN", f"Revoked all {total} leak approvals")
        return
    if not target.isdigit():
        await update.message.reply_text(
            f'<tg-emoji emoji-id="{INVALID_USAGE_EMOJI_ID}">⚠️</tg-emoji> '
            "<b>Usage:</b> <code>/revoke &lt;user_id|all&gt;</code>",
            parse_mode=ParseMode.HTML,
        )
        return
    user_id = int(target)
    if remove_leak_approval(user_id):
        await update.message.reply_text(f"✅ Revoked leak access for user <code>{user_id}</code>.", parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(f"⚠️ User <code>{user_id}</code> was not in approval list.", parse_mode=ParseMode.HTML)

async def approved_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized.")
        return
    approvals = get_leak_approvals()
    if not approvals:
        await update.message.reply_text("📭 No users are approved for /leak command.")
        return
    text = "<b>📋 LEAK APPROVED USERS</b>\n─────────────────────\n\n"
    for entry in approvals:
        uid = entry["user_id"]
        approved_at = entry["approved_at"].split("T")[0]
        expiry = entry.get("expiry")
        if expiry:
            expiry_date = expiry.split("T")[0]
            status = f"Expires: {expiry_date}"
        else:
            status = "Never expires"
        try:
            user = await context.bot.get_chat(uid)
            name = user.full_name or user.username or str(uid)
        except:
            name = str(uid)
        text += f"• <code>{uid}</code> – {html.escape(name)}\n   └ Approved: {approved_at} | {status}\n"
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


# ==================== GROUP AUTHORIZATION COMMANDS & CALLBACKS ====================
async def show_manage_approved_groups(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    db = load_db()
    approved = db.get("approved_groups", [])
    official_id = db.get("official_group_id") or "Not Set"
    official_link = get_official_group_link()
    btn_text = get_group_alert_btn_text()
    btn_emoji = get_group_alert_btn_emoji()
    
    text = (
        "🛡️ <b>Group Authorization & Alert Settings</b>\n"
        "────────────────────────────\n"
        f"👑 <b>Official Group ID:</b> <code>{official_id}</code>\n"
        f"🔗 <b>Official Link:</b> {official_link}\n"
        f"✅ <b>Approved Groups:</b> <code>{len(approved)}</code>\n"
        f"🔘 <b>Alert Button Text:</b> <code>{html.escape(btn_text)}</code>\n"
        f"🎨 <b>Button Emoji ID:</b> <code>{btn_emoji}</code>\n\n"
        "<i>Info commands (/num, /ip, /tg, /adhar, /leak, /veh, /ffinfo) will ONLY work in Official or Approved groups.</i>"
    )
    keyboard = [
        [
            InlineKeyboardButton("➕ Approve Group", callback_data="grp_approve_prompt"),
            InlineKeyboardButton("➖ Revoke Group", callback_data="grp_revoke_prompt"),
        ],
        [
            InlineKeyboardButton("📋 View Approved Groups", callback_data="grp_list"),
            InlineKeyboardButton("👑 Set Official", callback_data="grp_set_official_prompt"),
        ],
        [
            InlineKeyboardButton("✏️ Set Button Text", callback_data="grp_set_btn_prompt"),
            InlineKeyboardButton("🎨 Set Button Emoji", callback_data="grp_set_emoji_prompt"),
        ],
        [
            InlineKeyboardButton("🔗 Set Official Link", callback_data="grp_set_link_prompt"),
            InlineKeyboardButton("📝 Edit Message", callback_data="grp_set_msg_prompt"),
        ],
        [
            InlineKeyboardButton("👁️ Preview Alert Message", callback_data="grp_preview_alert"),
        ],
        [
            InlineKeyboardButton(
                "Back to Admin Panel",
                callback_data="admin_panel",
                _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["back_to_start"],
            )
        ]
    ]
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))

async def grp_set_btn_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    text = (
        "🔘 <b>Change Alert Button Text</b>\n\n"
        "Use command:\n"
        "<code>/setgroupbtn &lt;your_button_text&gt;</code>\n\n"
        "Example:\n"
        "<code>/setgroupbtn 🚀 JOIN OFFICIAL GROUP</code>\n"
        "<code>/setgroupbtn 🌟 USE IN OFFICIAL GROUP</code>\n\n"
        f"Current: <code>{get_group_alert_btn_text()}</code>"
    )
    keyboard = [[
        InlineKeyboardButton("Back", callback_data="manage_approved_groups", _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["back_to_start"])
    ]]
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))

async def grp_set_emoji_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    text = (
        "<b>Set Button Premium Emoji</b>\n\n"
        "Aap direct apna <b>Premium Emoji</b> daal sakte hain ya <b>Emoji ID</b>:\n\n"
        "1. <b>Direct Premium Emoji se:</b>\n"
        "<code>/setgroupemoji [aapka_premium_emoji]</code>\n\n"
        "2. <b>Numeric Emoji ID se:</b>\n"
        "<code>/setgroupemoji &lt;emoji_id&gt;</code>\n\n"
        "Example: <code>/setgroupemoji 6138734238628845209</code>\n\n"
        f"Current Emoji ID: <code>{get_group_alert_btn_emoji()}</code>\n\n"
        "<i>Normal unicode emoji button se automatically hat jayega taaki sirf premium emoji dikhe.</i>"
    )
    keyboard = [[
        InlineKeyboardButton("Back", callback_data="manage_approved_groups", _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["back_to_start"])
    ]]
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))

async def grp_set_msg_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    text = (
        "📝 <b>Change Alert Message Text</b>\n\n"
        "Use command:\n"
        "<code>/setgroupmsg &lt;your HTML message&gt;</code>\n\n"
        "Reset to default:\n"
        "<code>/resetgroupmsg</code>\n\n"
        "Aap message me custom premium emojis bhi laga sakte hain, example:\n"
        '<code>&lt;tg-emoji emoji-id="6138734238628845209"&gt;👉&lt;/tg-emoji&gt;</code>'
    )
    keyboard = [[
        InlineKeyboardButton("Back", callback_data="manage_approved_groups", _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["back_to_start"])
    ]]
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))

async def grp_preview_alert_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    official_link = get_official_group_link()
    btn_text = get_group_alert_btn_text()
    btn_emoji = get_group_alert_btn_emoji()
    alert_text = get_group_alert_msg()
    
    keyboard = [
        [InlineKeyboardButton(btn_text, url=official_link, _emoji_id=btn_emoji)],
        [InlineKeyboardButton("Back to Settings", callback_data="manage_approved_groups", _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["back_to_start"])]
    ]
    await query.edit_message_text(
        f"<b>[ PREVIEW OF GROUP ALERT MESSAGE ]</b>\n────────────────────────────\n\n" + alert_text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard),
        disable_web_page_preview=True,
    )

async def grp_approve_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    text = (
        "➕ <b>Approve a Group</b>\n\n"
        "You can approve a group in two ways:\n\n"
        "1. <b>Inside the group:</b> Run <code>/approvegroup</code> directly in that group.\n"
        "2. <b>Using Chat ID:</b> Run <code>/approvegroup &lt;group_id&gt;</code>\n\n"
        "Example: <code>/approvegroup -1001234567890</code>\n\n"
        "Once approved, all bot commands will work in that group."
    )
    keyboard = [[
        InlineKeyboardButton("Back", callback_data="manage_approved_groups", _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["back_to_start"])
    ]]
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))

async def grp_revoke_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    text = (
        "➖ <b>Revoke a Group</b>\n\n"
        "You can revoke group approval in two ways:\n\n"
        "1. <b>Inside the group:</b> Run <code>/revokegroup</code> directly in that group.\n"
        "2. <b>Using Chat ID:</b> Run <code>/revokegroup &lt;group_id&gt;</code>\n\n"
        "Example: <code>/revokegroup -1001234567890</code>\n\n"
        "Commands will immediately stop working in that group."
    )
    keyboard = [[
        InlineKeyboardButton("Back", callback_data="manage_approved_groups", _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["back_to_start"])
    ]]
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))

async def grp_list_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    db = load_db()
    approved = db.get("approved_groups", [])
    meta = db.get("approved_groups_meta", {})
    
    if not approved:
        text = "📋 <b>Approved Groups</b>\n\n<i>No groups have been approved yet. Commands only work in the official group.</i>"
        keyboard = [[
            InlineKeyboardButton("Back", callback_data="manage_approved_groups", _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["back_to_start"])
        ]]
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    text = f"📋 <b>Approved Groups ({len(approved)}):</b>\n────────────────────────────\n"
    keyboard = []
    for cid in approved:
        title = meta.get(str(cid), "")
        disp = f"{title} ({cid})" if title else str(cid)
        text += f"• <code>{cid}</code> {html.escape(title)}\n"
        keyboard.append([
            InlineKeyboardButton(f"❌ Revoke {disp[:20]}", callback_data=f"grp_revoke_{cid}")
        ])
    
    keyboard.append([
        InlineKeyboardButton("Back", callback_data="manage_approved_groups", _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["back_to_start"])
    ])
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))

async def grp_set_official_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    text = (
        "👑 <b>Set Official Group</b>\n\n"
        "To set the main official group:\n\n"
        "1. <b>Inside the group:</b> Run <code>/setofficial</code> directly in that group.\n"
        "2. <b>Using Chat ID:</b> Run <code>/setofficial &lt;group_id&gt;</code>\n\n"
        "Example: <code>/setofficial -1001234567890</code>"
    )
    keyboard = [[
        InlineKeyboardButton("Back", callback_data="manage_approved_groups", _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["back_to_start"])
    ]]
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))

async def grp_set_link_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    text = (
        "🔗 <b>Set Official Group Link</b>\n\n"
        "Use command:\n"
        "<code>/setgrouplink &lt;invite_url&gt;</code>\n\n"
        f"Current: {get_official_group_link()}"
    )
    keyboard = [[
        InlineKeyboardButton("Back", callback_data="manage_approved_groups", _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["back_to_start"])
    ]]
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))

async def approve_group_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized.")
        return
    chat_id = None
    title = ""
    if context.args and len(context.args) > 0:
        arg = context.args[0]
        try:
            chat_id = int(arg)
        except ValueError:
            await update.message.reply_text("❌ Invalid group ID. Must be numeric (e.g. -1001234567890).")
            return
    elif update.effective_chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
        chat_id = update.effective_chat.id
        title = update.effective_chat.title or ""
    else:
        await update.message.reply_text(
            "<b>Usage:</b>\n"
            "• Inside target group: <code>/approvegroup</code>\n"
            "• From anywhere: <code>/approvegroup &lt;group_id&gt;</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    if not title:
        try:
            chat_obj = await context.bot.get_chat(chat_id)
            title = chat_obj.title or ""
        except Exception:
            pass

    if add_approved_group(chat_id, title):
        group_announcement = get_group_approved_announcement()
        if update.effective_chat.id == chat_id:
            await update.message.reply_text(group_announcement, parse_mode=ParseMode.HTML)
        else:
            sent_to_group = False
            try:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=group_announcement,
                    parse_mode=ParseMode.HTML,
                )
                sent_to_group = True
            except Exception as e:
                logger.warning(f"Could not send announcement to group {chat_id}: {e}")

            status_note = "\n📢 Group me approval notification send kar diya gaya hai." if sent_to_group else "\n⚠️ (Group me message send nahi ho paya, verify bot permissions in group)."
            await update.message.reply_text(
                f"✅ <b>Group Approved!</b>\n"
                f"ID: <code>{chat_id}</code>\n"
                f"Title: <b>{html.escape(title or 'Unknown')}</b>"
                f"{status_note}",
                parse_mode=ParseMode.HTML,
            )
    else:
        await update.message.reply_text(
            f"⚠️ Group <code>{chat_id}</code> already approved hai.",
            parse_mode=ParseMode.HTML,
        )

async def revoke_group_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized.")
        return
    chat_id = None
    if context.args and len(context.args) > 0:
        arg = context.args[0]
        try:
            chat_id = int(arg)
        except ValueError:
            await update.message.reply_text("❌ Invalid group ID. Must be numeric (e.g. -1001234567890).")
            return
    elif update.effective_chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
        chat_id = update.effective_chat.id
    else:
        await update.message.reply_text(
            "<b>Usage:</b>\n"
            "• Inside target group: <code>/revokegroup</code>\n"
            "• From anywhere: <code>/revokegroup &lt;group_id&gt;</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    if remove_approved_group(chat_id):
        if update.effective_chat.id == chat_id:
            await send_group_revocation_announcement(context.bot, chat_id)
        else:
            sent = await send_group_revocation_announcement(context.bot, chat_id)
            status_note = "\n📢 Group me revocation notice send kar diya gaya hai." if sent else "\n⚠️ (Group me message send nahi ho paya, verify bot permissions in group)."
            await update.message.reply_text(
                f"✅ <b>Group Approval Revoked!</b>\n"
                f"ID: <code>{chat_id}</code>\n\n"
                f"Iss group me bot ke commands ab work nahi karenge."
                f"{status_note}",
                parse_mode=ParseMode.HTML,
            )
    else:
        await update.message.reply_text(
            f"⚠️ Group <code>{chat_id}</code> approved list me nahi tha.",
            parse_mode=ParseMode.HTML,
        )

async def set_official_group_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized.")
        return
    chat_id = None
    if context.args and len(context.args) > 0:
        try:
            chat_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("❌ Invalid group ID.")
            return
    elif update.effective_chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
        chat_id = update.effective_chat.id
    else:
        await update.message.reply_text(
            "<b>Usage:</b>\n"
            "• Inside official group: <code>/setofficial</code>\n"
            "• By ID: <code>/setofficial &lt;group_id&gt;</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    set_official_group(chat_id)
    await update.message.reply_text(
        f"👑 <b>Official Group Set!</b>\nID: <code>{chat_id}</code>",
        parse_mode=ParseMode.HTML,
    )

async def set_group_link_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized.")
        return
    if not context.args:
        await update.message.reply_text("<b>Usage:</b> <code>/setgrouplink &lt;url&gt;</code>", parse_mode=ParseMode.HTML)
        return
    link = context.args[0].strip()
    set_official_group_link(link)
    await update.message.reply_text(f"✅ <b>Official Group Link Updated:</b>\n{link}", parse_mode=ParseMode.HTML)

async def set_group_btn_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized.")
        return
    if not context.args:
        await update.message.reply_text(
            "<b>Usage:</b> <code>/setgroupbtn &lt;button_text&gt;</code>\n\n"
            "Example: <code>/setgroupbtn 🚀 JOIN OFFICIAL GROUP</code>",
            parse_mode=ParseMode.HTML,
        )
        return
    btn_text = " ".join(context.args).strip()
    set_group_alert_btn_text(btn_text)
    await update.message.reply_text(
        f"✅ <b>Button Text Updated:</b>\n<code>{html.escape(btn_text)}</code>",
        parse_mode=ParseMode.HTML,
    )

async def set_group_emoji_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized.")
        return

    custom_emoji_id = None

    # 1. Direct premium emoji from message entities
    if update.message and update.message.entities:
        for ent in update.message.entities:
            if ent.type in ("custom_emoji", "CustomEmoji") and getattr(ent, "custom_emoji_id", None):
                custom_emoji_id = str(ent.custom_emoji_id)
                break

    # 2. From reply message if admin replied to a message containing a custom emoji
    if not custom_emoji_id and update.message and update.message.reply_to_message:
        reply_ents = update.message.reply_to_message.entities or []
        for ent in reply_ents:
            if ent.type in ("custom_emoji", "CustomEmoji") and getattr(ent, "custom_emoji_id", None):
                custom_emoji_id = str(ent.custom_emoji_id)
                break

    # 3. Numeric ID passed as argument
    if not custom_emoji_id and context.args:
        arg = context.args[0].strip()
        if arg.isdigit():
            custom_emoji_id = arg

    if not custom_emoji_id:
        await update.message.reply_text(
            "<b>Set Button Premium Emoji</b>\n\n"
            "Aap direct apna <b>Premium Emoji</b> bhej kar set kar sakte hain:\n"
            "<code>/setgroupemoji [premium_emoji]</code>\n\n"
            "Ya fir numeric Emoji ID bhej sakte hain:\n"
            "<code>/setgroupemoji &lt;emoji_id&gt;</code>\n\n"
            "Example: <code>/setgroupemoji 6138734238628845209</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    set_group_alert_btn_emoji(custom_emoji_id)

    # Clean normal emojis from the button text so only clean text remains
    current_btn = get_group_alert_btn_text()
    cleaned_btn = remove_unicode_emojis(current_btn)
    if cleaned_btn:
        set_group_alert_btn_text(cleaned_btn)

    await update.message.reply_text(
        f"✅ <b>Button Premium Emoji Set!</b>\n\n"
        f"Emoji ID: <code>{custom_emoji_id}</code>\n"
        f"Button Text: <code>{html.escape(get_group_alert_btn_text())}</code>\n"
        f"<i>Normal emoji button se hata diya gaya hai taaki sirf premium emoji dikhe.</i>\n\n"
        f"Preview dekhne ke liye <code>/previewgroupmsg</code> chalayein.",
        parse_mode=ParseMode.HTML,
    )

async def set_group_msg_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized.")
        return
    # Get raw message text after command
    text = update.message.text or ""
    parts = text.split(None, 1)
    if len(parts) < 2:
        await update.message.reply_text(
            "<b>Usage:</b> <code>/setgroupmsg &lt;HTML text&gt;</code>\n\n"
            'Tip: You can use HTML tags like &lt;b&gt;, &lt;i&gt;, &lt;code&gt; and &lt;tg-emoji emoji-id="..."&gt;.',
            parse_mode=ParseMode.HTML,
        )
        return
    custom_msg = parts[1].strip()
    set_group_alert_msg(custom_msg)
    await update.message.reply_text(
        "✅ <b>Group Alert Message Updated!</b>\n\n"
        "Preview dekhne ke liye <code>/previewgroupmsg</code> chalayein.",
        parse_mode=ParseMode.HTML,
    )

async def reset_group_msg_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized.")
        return
    set_group_alert_msg(DEFAULT_GROUP_ALERT_MSG)
    await update.message.reply_text("✅ Group alert message reset to default.", parse_mode=ParseMode.HTML)

async def set_approved_msg_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized.")
        return
    text = update.message.text or ""
    parts = text.split(None, 1)
    if len(parts) < 2:
        await update.message.reply_text(
            "<b>Usage:</b> <code>/setapprovedmsg &lt;HTML text&gt;</code>",
            parse_mode=ParseMode.HTML,
        )
        return
    custom_msg = parts[1].strip()
    set_group_approved_announcement(custom_msg)
    await update.message.reply_text("✅ <b>Group Approved Announcement Message Updated!</b>", parse_mode=ParseMode.HTML)

async def reset_approved_msg_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized.")
        return
    set_group_approved_announcement(DEFAULT_GROUP_APPROVED_ANNOUNCEMENT)
    await update.message.reply_text("✅ Group approved announcement message reset to default.", parse_mode=ParseMode.HTML)

async def set_revoked_msg_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized.")
        return
    text = update.message.text or ""
    parts = text.split(None, 1)
    if len(parts) < 2:
        await update.message.reply_text(
            "<b>Usage:</b> <code>/setrevokedmsg &lt;HTML text&gt;</code>",
            parse_mode=ParseMode.HTML,
        )
        return
    custom_msg = parts[1].strip()
    set_group_revoked_announcement(custom_msg)
    await update.message.reply_text("✅ <b>Group Revoked Announcement Message Updated!</b>", parse_mode=ParseMode.HTML)

async def reset_revoked_msg_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized.")
        return
    set_group_revoked_announcement(DEFAULT_GROUP_REVOKED_ANNOUNCEMENT)
    await update.message.reply_text("✅ Group revoked announcement message reset to default.", parse_mode=ParseMode.HTML)

async def preview_group_msg_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized.")
        return
    official_link = get_official_group_link()
    btn_text = get_group_alert_btn_text()
    btn_emoji = get_group_alert_btn_emoji()
    alert_text = get_group_alert_msg()
    keyboard = [[
        InlineKeyboardButton(btn_text, url=official_link, _emoji_id=btn_emoji)
    ]]
    await update.message.reply_text(
        alert_text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard),
        disable_web_page_preview=True,
    )

async def setup_bot_menu(application) -> None:
    """Configures the native Telegram Menu Button and command list."""
    user_commands = [
        BotCommand("start", "Start the bot"),
        BotCommand("help", "Help & guide"),
        BotCommand("num", "Lookup mobile number info"),
        BotCommand("tg", "Lookup Telegram user ID"),
        BotCommand("ip", "Lookup IP address info"),
        BotCommand("veh", "Lookup vehicle registration"),
        BotCommand("num2veh", "Vehicle lookup by phone number"),
        BotCommand("ffinfo", "Lookup Free Fire player info"),
        BotCommand("leak", "OSINT lookup by number"),
        BotCommand("email", "OSINT lookup by email"),
        BotCommand("adhar", "Lookup Aadhaar details"),
        BotCommand("statu", "Bot status & uptime"),
        BotCommand("about", "About bot & developer"),
    ]
    try:
        await application.bot.set_my_commands(user_commands)
        await application.bot.set_chat_menu_button(menu_button=MenuButtonCommands())
        logger.info("✅ Native Telegram Menu button & commands configured successfully")
    except Exception as e:
        logger.warning(f"Could not set default menu commands: {e}")

    # Remove any admin commands from Menu list so menu stays clean
    try:
        await application.bot.delete_my_commands(scope=BotCommandScopeChat(chat_id=ADMIN_ID))
        logger.info("✅ Admin special menu commands deleted successfully")
    except Exception as e:
        logger.warning(f"Could not delete admin chat commands scope: {e}")

async def set_menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized.")
        return
    await setup_bot_menu(context.application)
    await update.message.reply_text(
        "✅ <b>Telegram Menu button set successfully!</b>\n"
        "Aapke chat input bar me blue <b>Menu</b> button active ho gaya hai.",
        parse_mode=ParseMode.HTML,
    )

async def approved_groups_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized.")
        return
    db = load_db()
    approved = db.get("approved_groups", [])
    meta = db.get("approved_groups_meta", {})
    official_id = db.get("official_group_id") or "Not Set"
    official_link = get_official_group_link()

    text = (
        "🛡️ <b>GROUP AUTHORIZATION STATUS</b>\n"
        "────────────────────────────\n"
        f"👑 <b>Official Group:</b> <code>{official_id}</code>\n"
        f"🔗 <b>Official Link:</b> {official_link}\n"
        f"✅ <b>Total Approved Groups:</b> <code>{len(approved)}</code>\n\n"
    )
    if approved:
        text += "<b>Approved Groups List:</b>\n"
        for cid in approved:
            title = meta.get(str(cid), "")
            text += f"• <code>{cid}</code> {html.escape(title)}\n"
    else:
        text += "<i>No groups approved yet. All commands only work in official group.</i>"

    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def set_trial_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized.")
        return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text(
            f'<tg-emoji emoji-id="{INVALID_USAGE_EMOJI_ID}">⚠️</tg-emoji> '
            "<b>Usage:</b> <code>/settrial &lt;number&gt;</code>\n"
            "Example: <code>/settrial 3</code>",
            parse_mode=ParseMode.HTML,
        )
        return
    new_limit = int(context.args[0])
    if new_limit < 0:
        await update.message.reply_text("❌ Trial limit must be 0 or higher. 0 means no trials.", parse_mode=ParseMode.HTML)
        return
    if set_trial_limit(new_limit):
        await update.message.reply_text(f"✅ Trial /leak uses per user set to <code>{new_limit}</code>.", parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text("❌ Failed to set limit.", parse_mode=ParseMode.HTML)

async def set_trial_user_limit_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized.")
        return
    if not context.args:
        curr = get_trial_user_limit()
        curr_str = "Unlimited" if curr <= 0 else str(curr)
        await update.message.reply_text(
            f'<tg-emoji emoji-id="{INVALID_USAGE_EMOJI_ID}">⚠️</tg-emoji> '
            "<b>Usage:</b> <code>/settrialuserlimit &lt;number|unlimited&gt;</code>\n\n"
            "• <code>/settrialuserlimit 0</code> or <code>unlimited</code>: Unlimited active users can try /leak\n"
            "• <code>/settrialuserlimit 100</code>: Limit to 100 distinct users\n\n"
            f"Current limit: <code>{curr_str}</code>",
            parse_mode=ParseMode.HTML,
        )
        return
    arg = context.args[0].lower().strip()
    if arg in ("unlimited", "inf", "all", "none"):
        new_limit = 0
    elif arg.isdigit():
        new_limit = int(arg)
    else:
        await update.message.reply_text("❌ Please enter a valid number or 'unlimited' (0 for unlimited).", parse_mode=ParseMode.HTML)
        return

    if set_trial_user_limit(new_limit):
        if new_limit == 0:
            await update.message.reply_text("✅ Maximum users who can try /leak set to <b>Unlimited</b> (all active users).", parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text(f"✅ Maximum number of users who can try /leak set to <code>{new_limit}</code>.", parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text("❌ Failed to set limit.", parse_mode=ParseMode.HTML)

async def reset_trial_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized.")
        return
    if context.args and context.args[0].isdigit():
        user_id = int(context.args[0])
        if reset_trial_usage(user_id):
            await update.message.reply_text(f"✅ Reset trial usage for user <code>{user_id}</code>.", parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text(f"⚠️ No trial usage record found for user <code>{user_id}</code>.", parse_mode=ParseMode.HTML)
    else:
        reset_trial_usage()
        await update.message.reply_text("✅ Reset trial usage for <b>all</b> users.", parse_mode=ParseMode.HTML)

async def maintenance_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized.")
        return
    
    current = is_maintenance_mode()
    new_state = not current
    set_maintenance_mode(new_state)
    
    status_emoji = (
        premium_emoji(MAINTENANCE_MESSAGE_EMOJI_IDS["enabled"], "🔧")
        if new_state
        else premium_emoji(MAINTENANCE_MESSAGE_EMOJI_IDS["disabled"], "✅")
    )
    status = f"{'ENABLED' if new_state else 'DISABLED'} {status_emoji}"
    await update.message.reply_text(
        f'{premium_emoji(MAINTENANCE_MESSAGE_EMOJI_IDS["header"], "⚙️")} '
        f"<b>Maintenance Mode: {status}</b>\n\n"
        f"Bot is now {'ONLY accessible to admin' if new_state else 'fully accessible to all users'}.\n"
        f"Non-admin users will see an update message.",
        parse_mode=ParseMode.HTML
    )
    add_log("ADMIN", f"Maintenance mode {'enabled' if new_state else 'disabled'} by admin")

async def toggle_bot_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized.")
        return
    
    current = is_bot_offline()
    new_state = not current
    set_bot_offline(new_state)
    
    status = "OFFLINE ⏹️" if new_state else "ONLINE 🟢"
    await update.message.reply_text(
        f"🔌 <b>Bot State: {status}</b>\n\n"
        f"Bot is now {'temporarily offline' if new_state else 'back online'}.\n"
        f"{'All non-admin users will see an offline message.' if new_state else 'Bot is fully functional again.'}",
        parse_mode=ParseMode.HTML
    )
    add_log("ADMIN", f"Bot {'went offline' if new_state else 'came online'} by admin")

async def uptime_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized.")
        return
    
    uptime = datetime.now() - BOT_START_TIME
    days = uptime.days
    hours, remainder = divmod(uptime.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    if HAS_PSUTIL:
        try:
            mem = psutil.Process().memory_info()
            mem_mb = mem.rss / 1024 / 1024
            cpu = psutil.cpu_percent()
        except:
            mem_mb = 0
            cpu = 0
    else:
        mem_mb = 0
        cpu = 0
    
    db = load_db()
    stats_text = (
        "📊 <b>BOT SYSTEM STATUS</b>\n─────────────────────\n\n"
        f"⏱ <b>Uptime:</b> {days}d {hours}h {minutes}m {seconds}s\n"
        f"📅 <b>Started:</b> {BOT_START_TIME.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"📊 <b>Requests processed:</b> <code>{REQUEST_COUNTER}</code>\n"
        f"💾 <b>Memory:</b> {mem_mb:.1f} MB\n"
        f"⚡ <b>CPU:</b> {cpu}%\n"
        f"👥 <b>Registered users:</b> <code>{len(db['users'])}</code>\n"
        f"👥 <b>Groups:</b> <code>{len(db['groups'])}</code>\n"
        f"🔧 <b>Maintenance:</b> {'🟢 ON' if is_maintenance_mode() else '🔴 OFF'}\n"
        f"🔌 <b>Bot State:</b> {'⏹️ OFFLINE' if is_bot_offline() else '🟢 ONLINE'}\n"
        f"🚦 <b>Active rate limits:</b> <code>{len(RATE_LIMIT_DICT)}</code> users\n"
        f"📝 <b>Log entries:</b> <code>{len(LOG_BUFFER)}</code>\n"
        f"💾 <b>Cache entries:</b> <code>{len(API_CACHE)}</code>\n\n"
        "─────────────────────\n"
        "🟢 System running smoothly"
    )
    await update.message.reply_text(stats_text, parse_mode=ParseMode.HTML)

async def logs_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized.")
        return
    
    if not LOG_BUFFER:
        await update.message.reply_text("📭 No logs available.")
        return
    
    log_text = "📝 <b>RECENT LOGS</b>\n─────────────────────\n\n"
    for log in list(LOG_BUFFER)[-30:]:
        log_text += f"{log}\n"
    
    if len(log_text) > 4000:
        log_text = log_text[:3900] + "\n... (truncated)"
    
    await update.message.reply_text(log_text, parse_mode=ParseMode.HTML)

async def blacklist_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized.")
        return
    
    if not context.args:
        blacklist = get_blacklisted()
        if blacklist:
            text = "🚫 <b>BLACKLISTED NUMBERS</b>\n─────────────────────\n\n"
            for num in blacklist[:20]:
                text += f"• <code>{num}</code>\n"
            if len(blacklist) > 20:
                text += f"\n... and {len(blacklist) - 20} more"
        else:
            text = "📭 No numbers are blacklisted."
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
        return
    
    action = context.args[0].lower()
    if len(context.args) < 2:
        await update.message.reply_text(
            f'<tg-emoji emoji-id="{INVALID_USAGE_EMOJI_ID}">⚠️</tg-emoji> '
            "<b>Usage:</b>\n"
            "<code>/blacklist add &lt;number&gt;</code>\n"
            "<code>/blacklist remove &lt;number&gt;</code>\n"
            "<code>/blacklist list</code>",
            parse_mode=ParseMode.HTML
        )
        return
    
    number = re.sub(r'\D', '', context.args[1])
    if not number:
        await update.message.reply_text(
            f'<tg-emoji emoji-id="{INVALID_USAGE_EMOJI_ID}">⚠️</tg-emoji> '
            "<b>Invalid number format.</b>",
            parse_mode=ParseMode.HTML,
        )
        return
    
    if action == "add":
        if add_blacklist_number(number):
            await update.message.reply_text(f"✅ Added <code>{number}</code> to blacklist.", parse_mode=ParseMode.HTML)
            add_log("ADMIN", f"Blacklisted number: {number}")
        else:
            await update.message.reply_text(f"⚠️ <code>{number}</code> is already blacklisted.", parse_mode=ParseMode.HTML)
    elif action == "remove":
        if remove_blacklist_number(number):
            await update.message.reply_text(f"✅ Removed <code>{number}</code> from blacklist.", parse_mode=ParseMode.HTML)
            add_log("ADMIN", f"Unblacklisted number: {number}")
        else:
            await update.message.reply_text(f"⚠️ <code>{number}</code> was not in blacklist.", parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(
            f'<tg-emoji emoji-id="{INVALID_USAGE_EMOJI_ID}">⚠️</tg-emoji> '
            "<b>Invalid action.</b> Use 'add' or 'remove'.",
            parse_mode=ParseMode.HTML,
        )

async def shutdown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized.")
        return    
    await update.message.reply_text(
        "⚠️ <b>SHUTDOWN NOTIFICATION</b>\n\n"
        "Bot is going offline now.\n"
        "This is a simulated shutdown message.\n\n"
        "🟢 Bot is still running in the background.",
        parse_mode=ParseMode.HTML
    )
    add_log("ADMIN", "Shutdown notification displayed by admin")

async def cleanup_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized.")
        return
    
    await update.message.reply_text("🔄 Cleaning up old entries...", parse_mode=ParseMode.HTML)
    add_log("ADMIN", "Cleanup initiated")
    
    removed_entries = len(API_CACHE)
    clear_cache()
    
    await update.message.reply_text(
        "✅ <b>Cleanup completed</b>\n\n"
        "Database is optimized.\n"
        f"💾 Cache cleared ({removed_entries} entries removed).",
        parse_mode=ParseMode.HTML
    )

@maintenance_aware
async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global REQUEST_COUNTER
    REQUEST_COUNTER += 1
    
    if update.effective_chat.type == ChatType.PRIVATE:
        keyboard = [[InlineKeyboardButton(
            "Back",
            callback_data="back_to_start",
            _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["back_to_start"],
        )]]
        reply_markup = InlineKeyboardMarkup(keyboard)
    else:
        reply_markup = None
    
    uptime = datetime.now() - BOT_START_TIME
    days = uptime.days
    hours, remainder = divmod(uptime.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    db = load_db()
    
    about_text = (
        f'<tg-emoji emoji-id="{ABOUT_EMOJI_IDS["header"]}">🤖</tg-emoji> '
        "<b>BOT INFORMATION</b>\n─────────────────────\n\n"
        f'<tg-emoji emoji-id="{ABOUT_EMOJI_IDS["details"]}">📌</tg-emoji> '
        "<b>Name:</b> Number X Info Bot\n"
        f'<tg-emoji emoji-id="{ABOUT_EMOJI_IDS["details"]}">📌</tg-emoji> '
        "<b>Version:</b> 2.1.5 (Vehicle Command Added)\n"
        f'<tg-emoji emoji-id="{ABOUT_EMOJI_IDS["details"]}">📌</tg-emoji> '
        "<b>Developer:</b> @Yourr_aura\n"
        f'<tg-emoji emoji-id="{ABOUT_EMOJI_IDS["details"]}">📌</tg-emoji> '
        "<b>Framework:</b> python-telegram-bot\n\n"
        f'<tg-emoji emoji-id="{ABOUT_EMOJI_IDS["features"]}">⚡</tg-emoji> '
        "<b>Features:</b>\n"
        "• Number lookup /num\n"
        "• Telegram ID lookup /tg\n"
        "• Aadhaar details /adhar\n"
        "• Data leak search /leak\n"
        "• Vehicle information /veh\n"
        "• Admin panel /admin\n"
        "• Maintenance mode /maintenance\n"
        "• Rate limiting (3 req/10s)\n"
        "• Auto-delete results (60s)\n"
        "• Temporary shutdown toggle\n"
        "• API Response Caching (5 min)\n\n"
        f'<tg-emoji emoji-id="{ABOUT_EMOJI_IDS["security"]}">🔐</tg-emoji> '
        "<b>Security:</b>\n"
        "• Blacklist system\n"
        "• Trial usage limits\n"
        "• Admin approval system\n"
        "• Command toggling\n\n"
        f'<tg-emoji emoji-id="{ABOUT_EMOJI_IDS["status"]}">📊</tg-emoji> '
        "<b>Status:</b>\n"
        f"• Uptime: {days}d {hours}h {minutes}m {seconds}s\n"
        f"• Requests: {REQUEST_COUNTER}\n"
        f"• Users: {len(db['users'])}\n"
        f'• Bot State: <tg-emoji emoji-id="{ABOUT_EMOJI_IDS["status"]}">🔘</tg-emoji> '
        f'{"OFFLINE" if is_bot_offline() else "ONLINE"}\n'
        f"• Cache: {len(API_CACHE)} entries\n\n"
        "─────────────────────\n"
        f'<tg-emoji emoji-id="{ABOUT_EMOJI_IDS["support"]}">💡</tg-emoji> '
        f"<i>For support: {ADMIN_USERNAME}</i>"
    )
    await update.message.reply_text(about_text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)

async def emoji_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user or update.effective_user.id != ADMIN_ID:
        return
    requested = context.args[0].lower() if context.args else ""
    if requested not in EMOJI_THEMES:
        await update.message.reply_text(
            f'<tg-emoji emoji-id="{INVALID_USAGE_EMOJI_ID}">⚠️</tg-emoji> '
            "<b>Usage:</b> <code>/emoji normal</code> or <code>/emoji premium</code>\n\n"
            f"Current theme: <b>{html.escape(get_emoji_theme())}</b>",
            parse_mode=ParseMode.HTML,
        )
        return
    set_emoji_theme(requested)
    await update.message.reply_text(
        f"✅ Emoji theme changed to <b>{html.escape(requested)}</b>.",
        parse_mode=ParseMode.HTML,
    )

async def admin_keyboard_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if (
        not update.message
        or not update.effective_user
        or not update.effective_chat
        or update.effective_user.id != ADMIN_ID
        or update.effective_chat.type != ChatType.PRIVATE
        or update.message.text not in {ADMIN_KEYBOARD_TEXT, "🔧 Admin Panel"}
    ):
        return
    await show_admin_keyboard(update)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    data = query.data or ""

    if data == "force_join_check" or data.startswith("force_join_check_"):
        owner_user_id: Optional[int] = None
        if data.startswith("force_join_check_"):
            owner_value = data.rsplit("_", 1)[-1]
            if owner_value.isdigit():
                owner_user_id = int(owner_value)

        if owner_user_id is not None and query.from_user.id != owner_user_id:
            other_user_already_verified = not await get_missing_force_join_targets(
                context.bot,
                query.from_user.id,
            )
            message = (
                "This verification button is for another user. "
                "You are already verified."
                if other_user_already_verified
                else
                "This verification button is for another user. "
                "Please use /start to get your own button."
            )
            await query.answer(message, show_alert=True)
            return

        if not await get_missing_force_join_targets(context.bot, query.from_user.id):
            await query.answer()
            await query.edit_message_text(
                '<tg-emoji emoji-id="6095742874421301875">✅</tg-emoji> '
                "<b>Verification successful.</b>\n\n"
                "Aap ab bot ke commands use kar sakte hain.",
                parse_mode=ParseMode.HTML,
            )
            return

        await query.answer()
        if await enforce_force_join(update, context):
            return
        await query.edit_message_text(
            '<tg-emoji emoji-id="6095742874421301875">✅</tg-emoji> '
            "<b>Verification successful.</b>\n\n"
            "Aap ab bot ke commands use kar sakte hain.",
            parse_mode=ParseMode.HTML,
        )
        return

    await query.answer()

    if data in ["admin_panel", "total_users", "total_groups", "bot_stats", "refresh_db", "broadcast", "broadcast_pin", 
                "export_users", "export_text", "export_json", "export_groups", "manage_commands", 
                "leak_approvals", "approve_all_active_users", "approve_user", "revoke_user", "set_trial_limit", 
                "set_trial_user_limit", "reset_trial", "reset_trial_all", "maintenance_toggle", "maintenance_menu",
                "maintenance_enable", "maintenance_disable", "system_stats", 
                 "blacklist_manage", "view_logs", "stop_bot", "start_bot", "clear_cache",
                 "pin_active_broadcast", "force_join", "fj_add", "fj_command_help", "manage_approved_groups", "grp_approve_prompt", "grp_revoke_prompt", "grp_list", "grp_set_official_prompt", "grp_set_link_prompt", "grp_set_btn_prompt", "grp_set_emoji_prompt", "grp_set_msg_prompt", "grp_preview_alert"] or data.startswith("total_users_page_") or data.startswith("toggle_cmd_") or data.startswith("fj_remove_") or data.startswith("fj_edit_") or data.startswith("grp_revoke_"):
        if query.from_user.id != ADMIN_ID:
            await query.edit_message_text("❌ Unauthorized.")
            return
        if query.message.chat.type != ChatType.PRIVATE:
            await query.edit_message_text("❌ Admin panel only available in private chat.")
            return

    if data == "manage_approved_groups":
        await show_manage_approved_groups(update, context)
    elif data == "grp_approve_prompt":
        await grp_approve_prompt(update, context)
    elif data == "grp_revoke_prompt":
        await grp_revoke_prompt(update, context)
    elif data == "grp_list":
        await grp_list_callback(update, context)
    elif data.startswith("grp_revoke_"):
        grp_id = data.split("grp_revoke_")[1]
        if remove_approved_group(grp_id):
            await send_group_revocation_announcement(context.bot, grp_id)
            await query.answer(f"Revoked {grp_id} & notification sent")
        else:
            await query.answer(f"Group {grp_id} was not approved")
        await grp_list_callback(update, context)
    elif data == "grp_set_official_prompt":
        await grp_set_official_prompt(update, context)
    elif data == "grp_set_link_prompt":
        await grp_set_link_prompt(update, context)
    elif data == "grp_set_btn_prompt":
        await grp_set_btn_prompt(update, context)
    elif data == "grp_set_emoji_prompt":
        await grp_set_emoji_prompt(update, context)
    elif data == "grp_set_msg_prompt":
        await grp_set_msg_prompt(update, context)
    elif data == "grp_preview_alert":
        await grp_preview_alert_callback(update, context)
    elif data == "admin_panel":
        await show_admin_panel(update, context)
    elif data.startswith("total_users_page_"):
        await total_users(update, context)
    elif data == "total_users":
        await total_users(update, context)
    elif data == "total_groups":
        await total_groups(update, context)
    elif data == "bot_stats":
        await bot_stats(update, context)
    elif data == "refresh_db":
        await refresh_db(update, context)
    elif data == "export_users":
        await export_users(update, context)
    elif data == "export_text":
        await export_users_text(update, context)
    elif data == "export_json":
        await export_users_json(update, context)
    elif data == "export_groups":
        await export_groups(update, context)
    elif data in ["broadcast", "broadcast_pin"]:
        await broadcast_button(update, context)
    elif data == "pin_active_broadcast":
        await pin_active_broadcast_action(update, context)
    elif data == "back_to_start":
        await back_to_start(update, context)
    elif data == "manage_commands":
        await manage_commands(update, context)
    elif data.startswith("toggle_cmd_"):
        await toggle_command(update, context)
    elif data == "force_join":
        context.user_data.pop("force_join_mode", None)
        context.user_data.pop("force_join_edit_index", None)
        await show_force_join_panel(update, context)
    elif data == "fj_add":
        context.user_data["force_join_mode"] = "add"
        context.user_data.pop("force_join_edit_index", None)
        await query.edit_message_text(
            "<b>ADD FORCE-JOIN TARGET</b>\n\n"
            "Ab isi chat me target details bhejein:\n"
            "• Public channel/group: <code>@username</code>\n"
            "• Private chat: <code>-1001234567890 https://t.me/+invite_link</code>\n\n"
            "Private invite link alone resolve nahi hota. Agar bot target chat me admin hai, "
            "target chat ke andar <code>/fjaddhere https://t.me/+invite_link</code> run karein.\n\n"
            "Bot ko target channel/group me add karke required admin permissions dein.",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    "Back",
                    callback_data="force_join",
                    _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["back_to_start"],
                )
            ]]),
        )
    elif data == "fj_command_help":
        context.user_data.pop("force_join_mode", None)
        context.user_data.pop("force_join_edit_index", None)
        await query.edit_message_text(
            "<b>FORCE-JOIN COMMANDS</b>\n\n"
            "<code>/fjadd @publicchannel</code>\n"
            "<code>/fjadd -1001234567890 https://t.me/+invite_link</code>\n\n"
            "<code>/fjaddhere https://t.me/+invite_link</code> "
            "(target group/channel ke andar)\n\n"
            "<code>/fjremove @channel_or_chat_id</code>\n"
            "<code>/fjlist</code>\n\n"
            "Private invite link ko admin panel me akela bhejne se chat ID resolve nahi hoti.",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    "Back",
                    callback_data="force_join",
                    _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["back_to_start"],
                )
            ]]),
        )
    elif data.startswith("fj_edit_"):
        try:
            index = int(data.rsplit("_", 1)[-1])
        except ValueError:
            await show_force_join_panel(update, context)
            return

        targets = get_force_join_targets()
        if index < 0 or index >= len(targets):
            await show_force_join_panel(update, context)
            return

        target = targets[index]
        context.user_data["force_join_mode"] = "edit_button"
        context.user_data["force_join_edit_index"] = index
        await query.edit_message_text(
            "<b>EDIT FORCE-JOIN BUTTON</b>\n\n"
            f"Target: <b>{html.escape(str(target.get('title') or target.get('chat_id')))}</b>\n"
            f"Current: <code>{html.escape(force_join_button_preview(target))}</code>\n\n"
            "Normal emoji aur button name is format me bhejein:\n"
            "<code>🔥 | Join VIP Group</code>\n\n"
            "Premium custom emoji ID ke liye:\n"
            "<code>premium:123456789 | Join VIP Group</code>\n"
            "Ya direct numeric ID:\n"
            "<code>123456789 | Join VIP Group</code>\n\n"
            "Emoji remove karne ke liye:\n"
            "<code>- | Join VIP Group</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    "Back",
                    callback_data="force_join",
                    _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["back_to_start"],
                )
            ]]),
        )
    elif data.startswith("fj_remove_"):
        try:
            index = int(data.rsplit("_", 1)[-1])
        except ValueError:
            await show_force_join_panel(update, context)
            return
        targets = get_force_join_targets()
        if index < 0 or index >= len(targets):
            await show_force_join_panel(update, context)
            return
        removed = targets.pop(index)
        save_force_join_targets(targets)
        add_log("ADMIN", f"Force join target removed: {removed.get('chat_id')}")
        await show_force_join_panel(update, context)
    elif data == "leak_approvals":
        approvals = get_leak_approvals()
        active_users = get_all_active_users()
        if not approvals:
            text = f"📭 No users are approved for /leak command.\n\n👥 <b>Total Active Users:</b> <code>{len(active_users)}</code>"
        else:
            text = f"<b>📋 LEAK APPROVED USERS ({len(approvals)})</b>\n👥 <b>Total Active Users:</b> <code>{len(active_users)}</code>\n─────────────────────\n\n"
            for entry in approvals[:20]:
                uid = entry["user_id"]
                approved_at = entry["approved_at"].split("T")[0]
                expiry = entry.get("expiry")
                if expiry:
                    expiry_date = expiry.split("T")[0]
                    status = f"Expires: {expiry_date}"
                else:
                    status = "Never expires"
                try:
                    user = await context.bot.get_chat(uid)
                    name = user.full_name or user.username or str(uid)
                except:
                    name = str(uid)
                text += f"• <code>{uid}</code> – {html.escape(name)}\n   └ Approved: {approved_at} | {status}\n"
            if len(approvals) > 20:
                text += f"\n<i>...and {len(approvals) - 20} more users</i>\n"
        keyboard = [
            [InlineKeyboardButton(
                f"✅ Approve All Active Users ({len(active_users)})",
                callback_data="approve_all_active_users",
                _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS.get("approve_user", ""),
            )],
            [InlineKeyboardButton(
                "Back to Admin Panel",
                callback_data="admin_panel",
                _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["back_to_start"],
            )]
        ]
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
    elif data == "approve_all_active_users":
        active_users = get_all_active_users()
        if not active_users:
            await query.answer("No active users found to approve.", show_alert=True)
            return
        count = 0
        for uid in active_users:
            if add_leak_approval(uid):
                count += 1
        await query.answer(f"Approved {count} users ({len(active_users)} total active)!", show_alert=True)
        # Refresh the view
        approvals = get_leak_approvals()
        text = f"<b>📋 LEAK APPROVED USERS ({len(approvals)})</b>\n👥 <b>Total Active Users:</b> <code>{len(active_users)}</code>\n─────────────────────\n\n"
        for entry in approvals[:20]:
            uid = entry["user_id"]
            approved_at = entry["approved_at"].split("T")[0]
            expiry = entry.get("expiry")
            if expiry:
                expiry_date = expiry.split("T")[0]
                status = f"Expires: {expiry_date}"
            else:
                status = "Never expires"
            try:
                user = await context.bot.get_chat(uid)
                name = user.full_name or user.username or str(uid)
            except:
                name = str(uid)
            text += f"• <code>{uid}</code> – {html.escape(name)}\n   └ Approved: {approved_at} | {status}\n"
        if len(approvals) > 20:
            text += f"\n<i>...and {len(approvals) - 20} more users</i>\n"
        keyboard = [
            [InlineKeyboardButton(
                f"✅ Approve All Active Users ({len(active_users)})",
                callback_data="approve_all_active_users",
                _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS.get("approve_user", ""),
            )],
            [InlineKeyboardButton(
                "Back to Admin Panel",
                callback_data="admin_panel",
                _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["back_to_start"],
            )]
        ]
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
    elif data == "approve_user":
        active_users = get_all_active_users()
        await query.edit_message_text(
            "📝 <b>Approve User for /leak</b>\n\n"
            "Use the command:\n"
            "• <code>/approve &lt;user_id&gt; [days]</code> – Approve single user\n"
            "• <code>/approve all [days]</code> – Approve ALL active users\n\n"
            "Examples:\n"
            "• <code>/approve all</code> (approves all active users forever)\n"
            "• <code>/approve all 30</code> (approves all active users for 30 days)\n"
            "• <code>/approve 123456789 7</code> (approves single user for 7 days)\n\n"
            f"👥 Current Active Users: <code>{len(active_users)}</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    f"✅ Approve All Active Users ({len(active_users)})",
                    callback_data="approve_all_active_users",
                    _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS.get("approve_user", ""),
                )],
                [InlineKeyboardButton(
                    "Back",
                    callback_data="admin_panel",
                    _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["back_to_start"],
                )]
            ])
        )
    elif data == "revoke_user":
        await query.edit_message_text(
            "📝 <b>Revoke User</b>\n\n"
            "Use the command:\n"
            "• <code>/revoke &lt;user_id&gt;</code> – Revoke single user\n"
            "• <code>/revoke all</code> – Revoke ALL users\n\n"
            "Examples:\n"
            "• <code>/revoke 123456789</code>\n"
            "• <code>/revoke all</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    "Back",
                    callback_data="admin_panel",
                    _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["back_to_start"],
                )
            ]])
        )
    elif data == "set_trial_limit":
        await query.edit_message_text(
            "🎯 <b>Set Trial Limit (per user)</b>\n\n"
            "Use the command:\n<code>/settrial &lt;number&gt;</code>\n\n"
            "Example: <code>/settrial 5</code> (each user can try /leak 5 times total)\n"
            f"Current limit: <code>{get_trial_limit()}</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    "Back",
                    callback_data="admin_panel",
                    _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["back_to_start"],
                )
            ]])
        )
    elif data == "set_trial_user_limit":
        curr = get_trial_user_limit()
        curr_str = "Unlimited" if curr <= 0 else str(curr)
        await query.edit_message_text(
            "👥 <b>Set Trial User Limit (max distinct users)</b>\n\n"
            "Use the command:\n<code>/settrialuserlimit &lt;number|unlimited&gt;</code>\n\n"
            "• <code>/settrialuserlimit 0</code> or <code>unlimited</code>: <b>Unlimited</b> active users can try /leak\n"
            "• <code>/settrialuserlimit 100</code>: Only first 100 users can try /leak\n\n"
            f"Current user limit: <code>{curr_str}</code> (used: <code>{len(get_trial_users())}</code>)",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    "Back",
                    callback_data="admin_panel",
                    _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["back_to_start"],
                )
            ]])
        )
    elif data == "reset_trial":
        await query.edit_message_text(
            "🔄 <b>Reset Trial Usage</b>\n\n"
            "Use the command:\n<code>/resettrial [user_id]</code>\n\n"
            "• Without user_id: reset trial usage for ALL users (clears user list too).\n"
            "• With user_id: reset trial usage for that specific user.\n\n"
            "Example: <code>/resettrial 123456789</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    "🔄 Reset Trial For All Users",
                    callback_data="reset_trial_all",
                    _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS.get("reset_trial", ""),
                )],
                [InlineKeyboardButton(
                    "Back",
                    callback_data="admin_panel",
                    _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["back_to_start"],
                )]
            ])
        )
    elif data == "reset_trial_all":
        reset_trial_usage()
        add_log("ADMIN", "Reset trial usage for all users via admin panel")
        await query.answer("✅ Trial usage reset for ALL users! Everyone has fresh trials now.", show_alert=True)
        await query.edit_message_text(
            "✅ <b>Trial usage reset for ALL users!</b>\n\n"
            "All active users can now use /leak trial again.",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    "Back to Admin Panel",
                    callback_data="admin_panel",
                    _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["back_to_start"],
                )
            ]])
        )
    elif data in {"maintenance_menu", "maintenance_toggle"}:
        await query.edit_message_text(
            maintenance_control_text(),
            parse_mode=ParseMode.HTML,
            reply_markup=maintenance_control_markup(),
        )
    elif data in {"maintenance_enable", "maintenance_disable"}:
        new_state = data == "maintenance_enable"
        set_maintenance_mode(new_state)
        await query.edit_message_text(
            maintenance_control_text(),
            parse_mode=ParseMode.HTML,
            reply_markup=maintenance_control_markup(),
        )
        add_log("ADMIN", f"Maintenance mode {'enabled' if new_state else 'disabled'} via admin panel")
    
    elif data == "stop_bot":
        set_bot_offline(True)
        await query.edit_message_text(
            '<tg-emoji emoji-id="6235612354181080084">⏹️</tg-emoji> '
            "<b>BOT IS NOW OFFLINE</b>\n\n"
            "The bot has been temporarily shut down.\n"
            "All non-admin users will see an offline message.\n\n"
            "Click <b>'START BOT'</b> in the admin panel to bring it back online.",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    "Back to Admin Panel",
                    callback_data="admin_panel",
                    _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["back_to_start"],
                )
            ]])
        )
        add_log("ADMIN", "Bot stopped via admin panel")
    
    elif data == "start_bot":
        set_bot_offline(False)
        await query.edit_message_text(
            '<tg-emoji emoji-id="6235405113419109550">▶️</tg-emoji> '
            "<b>BOT IS NOW ONLINE</b>\n\n"
            "The bot is back online and fully functional.\n"
            "All users can now use the bot normally.",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    "Back to Admin Panel",
                    callback_data="admin_panel",
                    _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["back_to_start"],
                )
            ]])
        )
        add_log("ADMIN", "Bot started via admin panel")
    
    elif data == "clear_cache":
        clear_cache()
        await query.edit_message_text(
            "🗑️ <b>CACHE CLEARED</b>\n\n"
            "All API cache entries have been cleared.\n"
            "New requests will fetch fresh data.",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    "Back to Admin Panel",
                    callback_data="admin_panel",
                    _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["back_to_start"],
                )
            ]])
        )
        add_log("ADMIN", "Cache cleared via admin panel")
    
    elif data == "system_stats":
        uptime = datetime.now() - BOT_START_TIME
        days = uptime.days
        hours, remainder = divmod(uptime.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        if HAS_PSUTIL:
            try:
                mem = psutil.Process().memory_info()
                mem_mb = mem.rss / 1024 / 1024
                cpu = psutil.cpu_percent()
            except:
                mem_mb = 0
                cpu = 0
        else:
            mem_mb = 0
            cpu = 0
        
        db = load_db()
        stats_text = (
            "📊 <b>DETAILED SYSTEM STATS</b>\n─────────────────────\n\n"
            f"⏱ <b>Uptime:</b> {days}d {hours}h {minutes}m {seconds}s\n"
            f"📅 <b>Started:</b> {BOT_START_TIME.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"📊 <b>Requests:</b> <code>{REQUEST_COUNTER}</code>\n"
            f"💾 <b>Memory:</b> {mem_mb:.1f} MB\n"
            f"⚡ <b>CPU:</b> {cpu}%\n"
            f"👥 <b>Users:</b> <code>{len(db['users'])}</code>\n"
            f"👥 <b>Groups:</b> <code>{len(db['groups'])}</code>\n"
            f"🔧 <b>Maintenance:</b> {'🟢 ON' if is_maintenance_mode() else '🔴 OFF'}\n"
            f"🔌 <b>Bot State:</b> {'⏹️ OFFLINE' if is_bot_offline() else '🟢 ONLINE'}\n"
            f"🚦 <b>Rate-limited users:</b> <code>{len(RATE_LIMIT_DICT)}</code>\n"
            f"🚫 <b>Blacklisted:</b> <code>{len(get_blacklisted())}</code>\n"
            f"📝 <b>Log entries:</b> <code>{len(LOG_BUFFER)}</code>\n"
            f"💾 <b>Cache entries:</b> <code>{len(API_CACHE)}</code>\n"
            f"📊 <b>Approved users:</b> <code>{len(get_leak_approvals())}</code>\n"
            f"🎯 <b>Trial users:</b> <code>{len(get_trial_users())}</code>\n"
            "─────────────────────\n"
            "🟢 System stable"
        )
        await query.edit_message_text(
            stats_text, 
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    "Back",
                    callback_data="admin_panel",
                    _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["back_to_start"],
                )
            ]])
        )
    
    elif data == "blacklist_manage":
        blacklist = get_blacklisted()
        if blacklist:
            text = "🚫 <b>BLACKLISTED NUMBERS</b>\n─────────────────────\n\n"
            for num in blacklist[:20]:
                text += f"• <code>{num}</code>\n"
            if len(blacklist) > 20:
                text += f"\n... and {len(blacklist) - 20} more"
            text += "\n\nUse <code>/blacklist add/remove &lt;number&gt;</code>"
        else:
            text = "📭 No numbers are blacklisted.\n\nUse <code>/blacklist add &lt;number&gt;</code>"
        
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    "Back",
                    callback_data="admin_panel",
                    _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["back_to_start"],
                )
            ]])
        )
    
    elif data == "view_logs":
        if not LOG_BUFFER:
            text = "📭 No logs available."
        else:
            text = "📝 <b>RECENT LOGS</b>\n─────────────────────\n\n"
            for log in list(LOG_BUFFER)[-30:]:
                text += f"{log}\n"
        
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    "Back",
                    callback_data="admin_panel",
                    _emoji_id=ADMIN_PANEL_BUTTON_EMOJI_IDS["back_to_start"],
                )
            ]])
        )

class KeepAliveHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'OK')
    def log_message(self, format, *args):
        pass

def run_keep_alive():
    server = HTTPServer(('0.0.0.0', PORT), KeepAliveHandler)
    server.serve_forever()

async def ignore_regular_messages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    return

def main():
    thread = threading.Thread(target=run_keep_alive, daemon=True)
    thread.start()
    logger.info(f"Keep-alive HTTP server started on port {PORT}")

    db = load_db()
    
    if "maintenance_mode" not in db:
        db["maintenance_mode"] = False
        save_db(db)
    if "blacklisted_numbers" not in db:
        db["blacklisted_numbers"] = []
        save_db(db)
    if "bot_offline" not in db:
        db["bot_offline"] = False
        save_db(db)
    if "last_broadcast" not in db:
        db["last_broadcast"] = []
        save_db(db)

    app = ApplicationBuilder().token(BOT_TOKEN).post_init(setup_bot_menu).build()
    app.bot_data['db'] = db

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", maintenance_aware(help_command)))
    app.add_handler(CommandHandler("statu", maintenance_aware(status_command)))
    app.add_handler(CommandHandler("num", info_group_restricted(lookup_num)))
    app.add_handler(CommandHandler("ip", info_group_restricted(ip_command)))
    app.add_handler(CommandHandler("tg", info_group_restricted(lookup_tg)))
    app.add_handler(CommandHandler(["adhar", "aadhaar"], info_group_restricted(adhar_command)))
    app.add_handler(CommandHandler("leak", info_group_restricted(leak_command)))
    app.add_handler(CommandHandler("email", info_group_restricted(email_command)))
    app.add_handler(CommandHandler("veh", info_group_restricted(vehicle_command)))
    app.add_handler(CommandHandler("num2veh", info_group_restricted(num2veh_command)))
    app.add_handler(CommandHandler("ffinfo", info_group_restricted(ffinfo_command)))
    app.add_handler(CommandHandler("mytrial", maintenance_aware(mytrial_command)))
    app.add_handler(CommandHandler("about", maintenance_aware(about_command)))
    app.add_handler(CommandHandler("pin", pin_command))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CommandHandler("userdetails", user_details_command))
    app.add_handler(CommandHandler("cancel", cancel_broadcast))
    app.add_handler(CommandHandler("approve", approve_command))
    app.add_handler(CommandHandler("revoke", revoke_command))
    app.add_handler(CommandHandler("approvegroup", approve_group_command))
    app.add_handler(CommandHandler("revokegroup", revoke_group_command))
    app.add_handler(CommandHandler("setofficial", set_official_group_command))
    app.add_handler(CommandHandler("setgrouplink", set_group_link_command))
    app.add_handler(CommandHandler("approvedgroups", approved_groups_list_command))
    app.add_handler(CommandHandler("setgroupbtn", set_group_btn_command))
    app.add_handler(CommandHandler("setgroupemoji", set_group_emoji_command))
    app.add_handler(CommandHandler("setgroupmsg", set_group_msg_command))
    app.add_handler(CommandHandler("resetgroupmsg", reset_group_msg_command))
    app.add_handler(CommandHandler("previewgroupmsg", preview_group_msg_command))
    app.add_handler(CommandHandler("setmenu", set_menu_command))
    app.add_handler(CommandHandler("setapprovedmsg", set_approved_msg_command))
    app.add_handler(CommandHandler("resetapprovedmsg", reset_approved_msg_command))
    app.add_handler(CommandHandler("setrevokedmsg", set_revoked_msg_command))
    app.add_handler(CommandHandler("resetrevokedmsg", reset_revoked_msg_command))
    app.add_handler(CommandHandler("approvedlist", approved_list_command))
    app.add_handler(CommandHandler("approveall", approve_all_command))
    app.add_handler(CommandHandler("settrial", set_trial_command))
    app.add_handler(CommandHandler("settrialuserlimit", set_trial_user_limit_command))
    app.add_handler(CommandHandler("resettrial", reset_trial_command))
    app.add_handler(CommandHandler("maintenance", maintenance_command))
    app.add_handler(CommandHandler("togglebot", toggle_bot_command))
    app.add_handler(CommandHandler("uptime", uptime_command))
    app.add_handler(CommandHandler("logs", logs_command))
    app.add_handler(CommandHandler("blacklist", blacklist_command))
    app.add_handler(CommandHandler("shutdown", shutdown_command))
    app.add_handler(CommandHandler("cleanup", cleanup_command))
    app.add_handler(CommandHandler("emoji", emoji_command))
    app.add_handler(CommandHandler("fjadd", force_join_add_command))
    app.add_handler(CommandHandler("fjaddhere", force_join_here_command))
    app.add_handler(CommandHandler("fjremove", force_join_remove_command))
    app.add_handler(CommandHandler("fjlist", force_join_list_command))

    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(
        MessageHandler(
            filters.TEXT
            & filters.User(ADMIN_ID)
            & filters.Regex(r"^(?:🔧 )?Admin Panel$"),
            admin_keyboard_button,
        )
    )
    app.add_handler(MessageHandler(filters.ALL & filters.User(ADMIN_ID), handle_broadcast_message))
    app.add_handler(MessageHandler(filters.ALL, ignore_regular_messages))

    bot_status = "⏹️ OFFLINE" if is_bot_offline() else "🟢 ONLINE"
    maintenance_status = "🔧 MAINTENANCE ON" if is_maintenance_mode() else "🟢 ONLINE"
    logger.info(f"✅ Bot started with version 2.1.6 (Free Fire Info Command Added)")
    logger.info(f"Bot Status: {bot_status}")
    logger.info(f"Maintenance: {maintenance_status}")
    logger.info(f"Rate limit: 3 requests per 10 seconds per user")
    logger.info(f"API Cache: {len(API_CACHE)} entries, TTL: {API_CACHE_TTL}s")
    logger.info(f"Command management: {len(MANAGEABLE_COMMANDS)} commands available")
    logger.info(f"Leak approval system active. Trial uses per user: {get_trial_limit()}")
    logger.info(f"Vehicle API: {VEHICLE_API_URL}")
    logger.info(f"Free Fire Info API: {FF_INFO_API_URL}")
    logger.info(f"IP Info API: {IP_INFO_API_URL}")
    

    try:
        app.run_polling(drop_pending_updates=True)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")
    except Exception as e:
        logger.exception("Bot stopped after an unrecoverable error: %s", e)
        add_log("ERROR", f"Bot stopped: {e}")

if __name__ == "__main__":
    main()