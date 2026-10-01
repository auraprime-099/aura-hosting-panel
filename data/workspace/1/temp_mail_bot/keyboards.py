import urllib.parse
from typing import Optional, List, Dict, Any
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from premium_emojis import pe_id
from database import DEFAULT_BUTTON_EMOJIS, BUTTON_NAMES, BUTTON_CATEGORIES

# Custom Telegram Emoji IDs & Button Styles
COLOR_CONFIGS = {
    "primary": {"style": "primary", "icon": pe_id("bolt")},
    "success": {"style": "success", "icon": pe_id("check")},
    "danger":  {"style": "danger",  "icon": pe_id("trash")},
}

# Fixed default button colors
BUTTON_COLORS = {
    # Main Menu
    "inbox": "primary",
    "new": "success",
    "gen": "success",
    "profile": "primary",
    "refer": "success",
    "delete": "danger",
    "help": "primary",
    "admin": "primary",

    # Mail & Inbox
    "read_mail": "primary",
    "del_mail": "danger",
    "refresh_inbox": "primary",
    "back_inbox": "primary",
    "verify_link": "success",

    # Referral & Balance
    "claim": "success",
    "refer_friends": "success",
    "share": "success",
    "quick_share": "success",
    "leaderboard": "primary",
    "redeem": "success",

    # System & Navigation
    "back": "danger",
    "cancel": "danger",
    "fsub_verify": "success",

    # Admin Panel Actions
    "admin_stats": "primary",
    "admin_broadcast": "primary",
    "admin_fsub_list": "primary",
    "admin_add_credits": "success",
    "admin_redeem": "primary",
    "admin_btn_colors": "primary",
    "admin_btn_texts": "primary",
    "admin_btn_emojis": "primary",
    "admin_user_lookup": "primary",
    "add_fsub": "success",
    "del_fsub": "danger",
}

# In-memory cached button custom settings
ACTIVE_BUTTON_EMOJIS: Dict[str, str] = dict(DEFAULT_BUTTON_EMOJIS)
ACTIVE_BUTTON_COLORS: Dict[str, str] = dict(BUTTON_COLORS)
ACTIVE_BUTTON_TEXTS: Dict[str, str] = dict(BUTTON_NAMES)

def update_button_emojis_cache(new_emojis: Dict[str, str]):
    """Update in-memory button emojis cache."""
    ACTIVE_BUTTON_EMOJIS.update(new_emojis)

def reset_button_emojis_cache():
    """Reset in-memory button emojis cache to defaults."""
    ACTIVE_BUTTON_EMOJIS.clear()
    ACTIVE_BUTTON_EMOJIS.update(DEFAULT_BUTTON_EMOJIS)

def get_btn_emoji(btn_key: str) -> str:
    """Get active custom emoji ID for a button."""
    return ACTIVE_BUTTON_EMOJIS.get(btn_key, DEFAULT_BUTTON_EMOJIS.get(btn_key, "6129479035077531636"))

def update_button_colors_cache(new_colors: Dict[str, str]):
    """Update in-memory button colors cache."""
    ACTIVE_BUTTON_COLORS.update(new_colors)

def reset_button_colors_cache():
    """Reset in-memory button colors cache to defaults."""
    ACTIVE_BUTTON_COLORS.clear()
    ACTIVE_BUTTON_COLORS.update(BUTTON_COLORS)

def get_btn_color(btn_key: str) -> str:
    """Get active color style for a button ('primary', 'success', 'danger')."""
    return ACTIVE_BUTTON_COLORS.get(btn_key, BUTTON_COLORS.get(btn_key, "primary"))

def update_button_texts_cache(new_texts: Dict[str, str]):
    """Update in-memory button texts cache."""
    ACTIVE_BUTTON_TEXTS.update(new_texts)

def reset_button_texts_cache():
    """Reset in-memory button texts cache to defaults."""
    ACTIVE_BUTTON_TEXTS.clear()
    ACTIVE_BUTTON_TEXTS.update(BUTTON_NAMES)

def get_btn_text(btn_key: str, default: Optional[str] = None) -> str:
    """Get active text label for a button."""
    return ACTIVE_BUTTON_TEXTS.get(btn_key, default or BUTTON_NAMES.get(btn_key, btn_key))

def make_btn(
    text: Optional[str] = None,
    callback_data: Optional[str] = None,
    url: Optional[str] = None,
    color: Optional[str] = None,
    emoji_key: Optional[str] = None,
    emoji_id: Optional[str] = None,
    btn_key: Optional[str] = None
) -> InlineKeyboardButton:
    """Build InlineKeyboardButton with native Telegram button style and animated custom premium emoji."""
    if btn_key:
        if text is None:
            text = get_btn_text(btn_key)
        if color is None:
            color = get_btn_color(btn_key)
        if emoji_id is None and emoji_key is None:
            emoji_id = get_btn_emoji(btn_key)

    color = color or "primary"
    text = text or ""
    cfg = COLOR_CONFIGS.get(color, COLOR_CONFIGS["primary"])
    if emoji_id:
        icon_id = str(emoji_id)
    elif emoji_key:
        icon_id = pe_id(emoji_key)
    else:
        icon_id = cfg["icon"]

    kwargs = {
        "text": text,
        "style": cfg["style"],
        "icon_custom_emoji_id": icon_id
    }
    if callback_data:
        kwargs["callback_data"] = callback_data
    if url:
        kwargs["url"] = url
    return InlineKeyboardButton(**kwargs)

# ============================================
# MAIN NAVIGATION KEYBOARDS
# ============================================

def get_main_keyboard(has_email: bool = False, is_admin: bool = False) -> InlineKeyboardMarkup:
    """Generate main navigation buttons with customizable colors, texts, and emojis."""
    buttons = []
    if has_email:
        buttons.append([
            make_btn(btn_key="inbox", callback_data="check_inbox")
        ])
        buttons.append([
            make_btn(btn_key="new", callback_data="new_email")
        ])
        buttons.append([
            make_btn(btn_key="profile", callback_data="show_profile"),
            make_btn(btn_key="refer", callback_data="refer_earn")
        ])
        buttons.append([
            make_btn(btn_key="redeem", callback_data="redeem_code"),
            make_btn(btn_key="delete", callback_data="delete_email")
        ])
    else:
        buttons.append([
            make_btn(btn_key="gen", callback_data="new_email")
        ])
        buttons.append([
            make_btn(btn_key="profile", callback_data="show_profile"),
            make_btn(btn_key="refer", callback_data="refer_earn")
        ])
        buttons.append([
            make_btn(btn_key="redeem", callback_data="redeem_code")
        ])

    bottom_row = [
        make_btn(btn_key="help", callback_data="help_menu")
    ]
    if is_admin:
        bottom_row.append(make_btn(btn_key="admin", callback_data="admin_panel"))
    buttons.append(bottom_row)

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_profile_keyboard(credits: int = 0) -> InlineKeyboardMarkup:
    """Keyboard for user profile & balance view with clean and focused navigation."""
    buttons = [
        [
            make_btn(btn_key="new", callback_data="new_email"),
            make_btn(btn_key="refer", callback_data="refer_earn")
        ],
        [
            make_btn(btn_key="redeem", callback_data="redeem_code"),
            make_btn(btn_key="leaderboard", callback_data="refer_leaderboard")
        ],
        [
            make_btn(btn_key="back", callback_data="back_to_main")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_referral_keyboard(user_id: int, bot_username: str) -> InlineKeyboardMarkup:
    """Generate referral program keyboard with 1-click share."""
    ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
    share_text = urllib.parse.quote(
        f"Unlimited Temporary Emails & Instant OTP Generator Bot!\n\n"
        f"Generate disposable emails and receive instant OTPs in one click 👇\n"
        f"{ref_link}"
    )
    share_url = f"https://t.me/share/url?url={urllib.parse.quote(ref_link)}&text={share_text}"

    buttons = [
        [make_btn(btn_key="share", url=share_url)],
        [
            make_btn(btn_key="leaderboard", callback_data="refer_leaderboard"),
            make_btn(btn_key="profile", callback_data="show_profile")
        ],
        [
            make_btn(btn_key="back", callback_data="back_to_main")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_leaderboard_keyboard(user_id: int, bot_username: str) -> InlineKeyboardMarkup:
    """Keyboard for referral leaderboard view."""
    ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
    share_text = urllib.parse.quote(
        f"Unlimited Temporary Emails & Instant OTP Generator Bot!\n\n"
        f"Generate disposable emails and receive instant OTPs in one click 👇\n"
        f"{ref_link}"
    )
    share_url = f"https://t.me/share/url?url={urllib.parse.quote(ref_link)}&text={share_text}"

    buttons = [
        [make_btn(btn_key="share", url=share_url)],
        [
            make_btn(btn_key="refer", callback_data="refer_earn"),
            make_btn(btn_key="profile", callback_data="show_profile")
        ],
        [
            make_btn(btn_key="back", callback_data="back_to_main")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_no_credits_keyboard(user_id: int, bot_username: str, has_credits: bool = False) -> InlineKeyboardMarkup:
    """Keyboard when user has exhausted their free email credits."""
    ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
    share_text = urllib.parse.quote(
        f"Unlimited Temporary Emails & Instant OTP Generator Bot!\n\n"
        f"Join now and receive free disposable email credits: {ref_link}"
    )
    share_url = f"https://t.me/share/url?url={urllib.parse.quote(ref_link)}&text={share_text}"

    buttons = []
    if has_credits:
        buttons.append([make_btn(btn_key="claim", callback_data="claim_mails")])
    buttons.append([
        make_btn(btn_key="redeem", callback_data="redeem_code"),
        make_btn(btn_key="refer_friends", callback_data="refer_earn")
    ])
    buttons.append([make_btn(btn_key="quick_share", url=share_url)])
    buttons.append([
        make_btn(btn_key="profile", callback_data="show_profile"),
        make_btn(btn_key="back", callback_data="back_to_main")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_admin_keyboard() -> InlineKeyboardMarkup:
    """Admin dashboard navigation buttons with dedicated controls."""
    buttons = [
        [
            InlineKeyboardButton(text="📬 View All Users' Mails & OTPs", callback_data="admin_all_mails:0")
        ],
        [
            make_btn(btn_key="admin_stats", callback_data="admin_stats"),
            make_btn(btn_key="admin_broadcast", callback_data="admin_broadcast")
        ],
        [
            make_btn(btn_key="admin_fsub_list", callback_data="admin_fsub_list"),
            make_btn(btn_key="admin_add_credits", callback_data="admin_add_credits_info")
        ],
        [
            make_btn(btn_key="admin_redeem", callback_data="admin_redeem_manage"),
            make_btn(btn_key="admin_user_lookup", callback_data="admin_user_lookup_info")
        ],
        [
            make_btn(btn_key="admin_btn_colors", callback_data="admin_btn_colors"),
            make_btn(btn_key="admin_btn_texts", callback_data="admin_btn_texts")
        ],
        [
            make_btn(btn_key="admin_btn_emojis", callback_data="admin_btn_emojis"),
            make_btn(btn_key="back", callback_data="back_to_main")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_admin_all_mails_keyboard(page: int, total_pages: int, user_id_filter: Optional[int] = None) -> InlineKeyboardMarkup:
    """Navigation and controls keyboard for Admin All Mails & OTPs viewer."""
    nav_buttons = []
    cb_prefix = f"admin_user_mails:{user_id_filter}" if user_id_filter else "admin_all_mails"

    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀️ Previous", callback_data=f"{cb_prefix}:{page - 1}"))
    nav_buttons.append(InlineKeyboardButton(text=f"📄 {page + 1}/{max(1, total_pages)}", callback_data="noop"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="Next ▶️", callback_data=f"{cb_prefix}:{page + 1}"))

    buttons = []
    if nav_buttons:
        buttons.append(nav_buttons)

    action_row = [
        InlineKeyboardButton(text="🔄 Refresh", callback_data=f"{cb_prefix}:{page}"),
        InlineKeyboardButton(text="🔍 Filter User ID", callback_data="admin_search_user_mails")
    ]
    if user_id_filter:
        action_row.append(InlineKeyboardButton(text="🌐 View All Users", callback_data="admin_all_mails:0"))
    buttons.append(action_row)

    buttons.append([
        make_btn(btn_key="back", text="Back to Admin Panel", callback_data="admin_panel")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_admin_redeem_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for Admin Redeem Code management menu."""
    buttons = [
        [
            InlineKeyboardButton(text="➕ Create Redeem Code", callback_data="admin_create_redeem")
        ],
        [
            InlineKeyboardButton(text="🗑️ Delete Redeem Code", callback_data="admin_delete_redeem_list")
        ],
        [
            make_btn(btn_key="back", text="Back to Admin", callback_data="admin_panel")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_cancel_redeem_keyboard() -> InlineKeyboardMarkup:
    """Cancel button during redeem code creation or input."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [make_btn(btn_key="cancel", text="Cancel", callback_data="cancel_redeem_action")]
    ])

def get_delete_redeem_list_keyboard(codes: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """Keyboard listing redeem codes that can be deleted."""
    buttons = []
    for c in codes[:15]:
        code_str = c["code"]
        credits_str = c.get("credits", 1)
        used_str = f"{c.get('redeemed_count', 0)}/{c.get('max_users', 0)}"
        buttons.append([
            InlineKeyboardButton(text=f"🗑️ {code_str} (+{credits_str} | {used_str})", callback_data=f"del_code:{code_str}")
        ])
    buttons.append([
        InlineKeyboardButton(text="🔙 Back to Redeem Codes", callback_data="admin_redeem_manage")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_cancel_broadcast_keyboard() -> InlineKeyboardMarkup:
    """Cancel button for broadcast input."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [make_btn(btn_key="cancel", text="Cancel Broadcast", callback_data="admin_cancel_broadcast")]
    ])

def get_mail_alert_keyboard(message_id: str, verify_url: Optional[str] = None) -> InlineKeyboardMarkup:
    """Keyboard for new email alert."""
    buttons = []
    if verify_url and verify_url.startswith("http"):
        buttons.append([
            make_btn(btn_key="verify_link", url=verify_url)
        ])
    buttons.append([
        make_btn(btn_key="read_mail", callback_data=f"read_mail:{message_id}"),
        make_btn(btn_key="del_mail", callback_data=f"del_mail:{message_id}")
    ])
    buttons.append([
        make_btn(btn_key="refresh_inbox", callback_data="check_inbox")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_full_mail_keyboard(message_id: str, verify_url: Optional[str] = None) -> InlineKeyboardMarkup:
    """Keyboard for full mail view."""
    buttons = []
    if verify_url and verify_url.startswith("http"):
        buttons.append([
            make_btn(btn_key="verify_link", url=verify_url)
        ])
    buttons.append([
        make_btn(btn_key="del_mail", callback_data=f"del_mail:{message_id}"),
        make_btn(btn_key="back_inbox", callback_data="check_inbox")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ============================================
# FORCE JOIN (FSUB) KEYBOARDS
# ============================================

def get_force_sub_keyboard(unjoined_channels: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """Keyboard prompting user to join required channels before accessing bot (Matches Image 1)."""
    buttons = []
    for idx, ch in enumerate(unjoined_channels, start=1):
        title = ch.get("title") or f"Channel {idx}"
        url = ch.get("invite_link")
        c_type = "Group" if ch.get("chat_type") == "group" else "Channel"
        emoji_type = "broadcast" if ch.get("chat_type") != "group" else "handshake"
        buttons.append([
            make_btn(f"Join {c_type}: {title}", url=url, color="primary", emoji_key=emoji_type)
        ])

    buttons.append([
        make_btn(btn_key="fsub_verify", callback_data="check_fsub")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_admin_channels_keyboard(channels: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """Admin panel management keyboard for Force Join channels."""
    buttons = [
        [
            make_btn(btn_key="add_fsub", callback_data="admin_add_fsub"),
            make_btn(btn_key="del_fsub", callback_data="admin_del_fsub")
        ],
        [
            make_btn(btn_key="back", text="Back to Admin Panel", callback_data="admin_panel")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_remove_channel_keyboard(channels: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """List all active force-join channels for admin removal."""
    buttons = []
    for ch in channels:
        ch_id = ch["id"]
        title = ch.get("title") or ch.get("chat_id")
        buttons.append([
            make_btn(f"Remove: {title}", callback_data=f"admin_rm_chan:{ch_id}", btn_key="del_fsub")
        ])
    buttons.append([
        make_btn(btn_key="back", text="Cancel / Back", callback_data="admin_fsub_list")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_cancel_add_channel_keyboard() -> InlineKeyboardMarkup:
    """Cancel adding channel input."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [make_btn(btn_key="cancel", text="Cancel", callback_data="admin_cancel_fsub_add")]
    ])

# ============================================
# ADMIN BUTTON EMOJIS CUSTOMIZATION KEYBOARDS
# ============================================

def get_admin_btn_categories_keyboard() -> InlineKeyboardMarkup:
    """Keyboard listing all button categories for emoji manager."""
    buttons = []
    for cat_key, cat_data in BUTTON_CATEGORIES.items():
        buttons.append([
            make_btn(
                f"{cat_data['title']} ({len(cat_data['keys'])})",
                callback_data=f"admin_emojis_cat:{cat_key}",
                color="primary",
                emoji_id=cat_data.get("icon", get_btn_emoji("admin_btn_emojis"))
            )
        ])
    buttons.append([
        make_btn("Reset All Emojis to Default", callback_data="admin_reset_emojis_prompt", color="danger", emoji_key="refresh")
    ])
    buttons.append([
        make_btn("Back to Admin Panel", callback_data="admin_panel", btn_key="back")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_admin_category_buttons_keyboard(cat_key: str) -> InlineKeyboardMarkup:
    """Keyboard listing buttons in a specific category for emoji customization."""
    cat_data = BUTTON_CATEGORIES.get(cat_key)
    if not cat_data:
        return get_admin_btn_categories_keyboard()

    buttons = []
    for key in cat_data["keys"]:
        name = get_btn_text(key)
        current_emoji_id = get_btn_emoji(key)
        buttons.append([
            make_btn(
                f"{name}",
                callback_data=f"admin_edit_emoji:{key}",
                color=get_btn_color(key),
                emoji_id=current_emoji_id
            )
        ])
    buttons.append([
        make_btn("Back to Categories", callback_data="admin_btn_emojis", color="primary", emoji_key="back"),
        make_btn("Admin Panel", callback_data="admin_panel", btn_key="back")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_cancel_edit_emoji_keyboard(btn_key: Optional[str] = None) -> InlineKeyboardMarkup:
    """Cancel button when editing button emoji."""
    target_cat = "cat_main"
    if btn_key:
        for c_k, c_d in BUTTON_CATEGORIES.items():
            if btn_key in c_d["keys"]:
                target_cat = c_k
                break
    return InlineKeyboardMarkup(inline_keyboard=[
        [make_btn("Cancel", callback_data=f"admin_emojis_cat:{target_cat}", btn_key="cancel")]
    ])

def get_confirm_reset_emojis_keyboard() -> InlineKeyboardMarkup:
    """Confirmation prompt before resetting all button emojis."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            make_btn("Yes, Reset All Emojis", callback_data="admin_reset_emojis_confirm", color="danger", emoji_key="check"),
            make_btn("Cancel", callback_data="admin_btn_emojis", color="primary", emoji_key="cross")
        ]
    ])

# ============================================
# ADMIN BUTTON COLORS CUSTOMIZATION KEYBOARDS
# ============================================

def get_admin_btn_colors_categories_keyboard() -> InlineKeyboardMarkup:
    """Keyboard listing button categories for color customization."""
    buttons = []
    for cat_key, cat_data in BUTTON_CATEGORIES.items():
        buttons.append([
            make_btn(
                f"{cat_data['title']} ({len(cat_data['keys'])})",
                callback_data=f"admin_colors_cat:{cat_key}",
                color="primary",
                emoji_id=cat_data.get("icon", get_btn_emoji("admin_btn_colors"))
            )
        ])
    buttons.append([
        make_btn("Reset All Colors to Default", callback_data="admin_reset_colors_prompt", color="danger", emoji_key="refresh")
    ])
    buttons.append([
        make_btn("Back to Admin Panel", callback_data="admin_panel", btn_key="back")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_admin_colors_buttons_keyboard(cat_key: str) -> InlineKeyboardMarkup:
    """Keyboard listing buttons in category with current color tag. Clicking toggles color."""
    cat_data = BUTTON_CATEGORIES.get(cat_key)
    if not cat_data:
        return get_admin_btn_colors_categories_keyboard()

    color_tags = {
        "primary": "Primary",
        "success": "Success",
        "danger": "Danger"
    }

    buttons = []
    for key in cat_data["keys"]:
        name = get_btn_text(key)
        curr_color = get_btn_color(key)
        tag = color_tags.get(curr_color, "Primary")
        buttons.append([
            make_btn(
                f"{name} [{tag}]",
                callback_data=f"admin_toggle_color:{cat_key}:{key}",
                color=curr_color,
                emoji_id=get_btn_emoji(key)
            )
        ])

    buttons.append([
        make_btn("Back to Categories", callback_data="admin_btn_colors", color="primary", emoji_key="back"),
        make_btn("Admin Panel", callback_data="admin_panel", btn_key="back")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_confirm_reset_colors_keyboard() -> InlineKeyboardMarkup:
    """Confirmation prompt before resetting all button colors."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            make_btn("Yes, Reset All Colors", callback_data="admin_reset_colors_confirm", color="danger", emoji_key="check"),
            make_btn("Cancel", callback_data="admin_btn_colors", color="primary", emoji_key="cross")
        ]
    ])

# ============================================
# ADMIN BUTTON TEXTS CUSTOMIZATION KEYBOARDS
# ============================================

def get_admin_btn_texts_categories_keyboard() -> InlineKeyboardMarkup:
    """Keyboard listing button categories for text label customization."""
    buttons = []
    for cat_key, cat_data in BUTTON_CATEGORIES.items():
        buttons.append([
            make_btn(
                f"{cat_data['title']} ({len(cat_data['keys'])})",
                callback_data=f"admin_texts_cat:{cat_key}",
                color="primary",
                emoji_id=cat_data.get("icon", get_btn_emoji("admin_btn_texts"))
            )
        ])
    buttons.append([
        make_btn("Reset All Texts to Default", callback_data="admin_reset_texts_prompt", color="danger", emoji_key="refresh")
    ])
    buttons.append([
        make_btn("Back to Admin Panel", callback_data="admin_panel", btn_key="back")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_admin_texts_buttons_keyboard(cat_key: str) -> InlineKeyboardMarkup:
    """Keyboard listing buttons in category to customize their text."""
    cat_data = BUTTON_CATEGORIES.get(cat_key)
    if not cat_data:
        return get_admin_btn_texts_categories_keyboard()

    buttons = []
    for key in cat_data["keys"]:
        current_text = get_btn_text(key)
        buttons.append([
            make_btn(
                f"{current_text}",
                callback_data=f"admin_edit_text:{key}",
                color=get_btn_color(key),
                emoji_id=get_btn_emoji(key)
            )
        ])

    buttons.append([
        make_btn("Back to Categories", callback_data="admin_btn_texts", color="primary", emoji_key="back"),
        make_btn("Admin Panel", callback_data="admin_panel", btn_key="back")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_cancel_edit_text_keyboard(btn_key: Optional[str] = None) -> InlineKeyboardMarkup:
    """Cancel button when editing button text."""
    target_cat = "cat_main"
    if btn_key:
        for c_k, c_d in BUTTON_CATEGORIES.items():
            if btn_key in c_d["keys"]:
                target_cat = c_k
                break
    return InlineKeyboardMarkup(inline_keyboard=[
        [make_btn("Cancel", callback_data=f"admin_texts_cat:{target_cat}", btn_key="cancel")]
    ])

def get_confirm_reset_texts_keyboard() -> InlineKeyboardMarkup:
    """Confirmation prompt before resetting all button texts."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            make_btn("Yes, Reset All Texts", callback_data="admin_reset_texts_confirm", color="danger", emoji_key="check"),
            make_btn("Cancel", callback_data="admin_btn_texts", color="primary", emoji_key="cross")
        ]
    ])
