import aiosqlite
import logging
from typing import Optional, Dict, Any, List
from config import DB_PATH, START_CREDITS, CREDITS_PER_REFERRAL, START_MAIL_QUOTA, MAILS_PER_CREDIT

logger = logging.getLogger(__name__)

async def init_db():
    """Initialize database tables and handle column migrations."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                email TEXT,
                password TEXT,
                token TEXT,
                account_id TEXT,
                provider TEXT DEFAULT 'guerrilla',
                domain TEXT DEFAULT 'grr.la',
                username TEXT,
                last_message_id TEXT,
                is_monitoring INTEGER DEFAULT 1,
                credits INTEGER DEFAULT 1,
                mail_quota INTEGER DEFAULT 3,
                referred_by INTEGER DEFAULT NULL,
                referrals_count INTEGER DEFAULT 0,
                total_emails_created INTEGER DEFAULT 0,
                is_banned INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Run migrations for existing DBs if columns are missing
        migrations = [
            ("provider", "TEXT DEFAULT 'guerrilla'"),
            ("domain", "TEXT DEFAULT 'grr.la'"),
            ("username", "TEXT"),
            ("credits", f"INTEGER DEFAULT {START_CREDITS}"),
            ("mail_quota", f"INTEGER DEFAULT {START_MAIL_QUOTA}"),
            ("referred_by", "INTEGER DEFAULT NULL"),
            ("referrals_count", "INTEGER DEFAULT 0"),
            ("total_emails_created", "INTEGER DEFAULT 0"),
            ("is_banned", "INTEGER DEFAULT 0"),
            ("referral_status", "TEXT DEFAULT 'confirmed'")
        ]
        for col, col_type in migrations:
            try:
                await db.execute(f"ALTER TABLE users ADD COLUMN {col} {col_type};")
            except Exception:
                pass

        try:
            await db.execute("UPDATE users SET mail_quota = credits WHERE mail_quota IS NULL OR credits <= 0;")
            await db.execute("UPDATE users SET mail_quota = 0 WHERE credits <= 0;")
        except Exception:
            pass

        await db.execute("""
            CREATE TABLE IF NOT EXISTS received_messages (
                id TEXT PRIMARY KEY,
                user_id INTEGER,
                sender_service TEXT,
                sender_address TEXT,
                subject TEXT,
                otp_code TEXT,
                verification_link TEXT,
                received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS force_channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT UNIQUE,
                title TEXT,
                invite_link TEXT,
                chat_type TEXT DEFAULT 'channel',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        try:
            await db.execute("ALTER TABLE users ADD COLUMN theme TEXT DEFAULT 'auto';")
        except Exception:
            pass

        await db.execute("""
            CREATE TABLE IF NOT EXISTS button_emojis (
                btn_key TEXT PRIMARY KEY,
                emoji_id TEXT NOT NULL
            );
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS button_colors (
                btn_key TEXT PRIMARY KEY,
                color TEXT NOT NULL
            );
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS button_texts (
                btn_key TEXT PRIMARY KEY,
                btn_text TEXT NOT NULL
            );
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS redeem_codes (
                code TEXT PRIMARY KEY,
                credits INTEGER NOT NULL,
                max_users INTEGER NOT NULL,
                redeemed_count INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS redeem_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                redeemed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(code, user_id)
            );
        """)

        await db.commit()

    logger.info("Database initialized successfully with referral, admin, button customizer & force-sub support.")

async def get_user(user_id: int) -> Optional[Dict[str, Any]]:
    """Fetch user by Telegram user_id."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
    return None

async def get_or_create_user(user_id: int, referrer_id: Optional[int] = None) -> Dict[str, Any]:
    """Get existing user or register new user, handling referral rewards."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                u = dict(row)
                u["is_new_user"] = False
                u["is_new_referral"] = False
                return u

        # Handle referral if valid new user and referrer is different
        actual_referrer = None
        if referrer_id and referrer_id != user_id:
            # Check if referrer exists
            async with db.execute("SELECT 1 FROM users WHERE user_id = ?", (referrer_id,)) as ref_cur:
                if await ref_cur.fetchone():
                    actual_referrer = referrer_id

        # Insert new user with default credits and starting mail quota
        # If referred, referral_status is 'pending' until force-sub verification completes
        ref_status = 'pending' if actual_referrer else 'confirmed'
        await db.execute("""
            INSERT INTO users (user_id, credits, mail_quota, referred_by, referrals_count, is_monitoring, referral_status)
            VALUES (?, ?, ?, ?, 0, 1, ?)
        """, (user_id, START_CREDITS, START_CREDITS, actual_referrer, ref_status))

        await db.commit()

    u = await get_user(user_id) or {"user_id": user_id, "credits": START_CREDITS, "mail_quota": START_CREDITS, "referrals_count": 0}
    u["is_new_user"] = True
    u["is_new_referral"] = bool(actual_referrer)
    u["actual_referrer"] = actual_referrer
    return u

async def confirm_pending_referral(user_id: int) -> Optional[Dict[str, Any]]:
    """
    If the user has a pending referral, confirm it, award +1 credit & referral to the referrer,
    and return referrer info.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT referred_by, referral_status FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if not row or not row["referred_by"] or row["referral_status"] != "pending":
                return None
            referrer_id = row["referred_by"]

        # Mark user referral as confirmed
        await db.execute("UPDATE users SET referral_status = 'confirmed' WHERE user_id = ?", (user_id,))

        # Reward referrer with +1 credit & +1 referral count
        await db.execute("""
            UPDATE users 
            SET credits = credits + ?, mail_quota = mail_quota + ?, referrals_count = referrals_count + 1
            WHERE user_id = ?
        """, (CREDITS_PER_REFERRAL, CREDITS_PER_REFERRAL, referrer_id))

        await db.commit()

        async with db.execute("SELECT user_id, username, credits, referrals_count FROM users WHERE user_id = ?", (referrer_id,)) as c2:
            ref_row = await c2.fetchone()
            if ref_row:
                return dict(ref_row)
            return {"user_id": referrer_id}

async def claim_mails_with_credits(user_id: int, credits_to_use: int = 1) -> Dict[str, Any]:
    """Convert user credits into mail claims (1 Credit = 1 Mail)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT credits, mail_quota FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return {"success": False, "error": "User record not found."}

            current_credits = row["credits"] if row["credits"] is not None else 0

            if current_credits < credits_to_use:
                return {
                    "success": False,
                    "error": f"You don't have enough credits! (Needed: {credits_to_use}, You have: {current_credits})",
                    "credits": current_credits,
                    "mail_quota": current_credits
                }

            return {
                "success": True,
                "credits_used": credits_to_use,
                "mails_added": credits_to_use,
                "new_credits": current_credits,
                "new_mail_quota": current_credits
            }

async def consume_user_credit(user_id: int) -> bool:
    """Consume 1 credit when creating an email. Returns True if successful, False if credits < 1."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT credits, mail_quota FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                if START_CREDITS < 1:
                    return False
                await db.execute("INSERT INTO users (user_id, credits, mail_quota, total_emails_created) VALUES (?, ?, ?, 1)",
                                 (user_id, START_CREDITS - 1, START_CREDITS - 1))
                await db.commit()
                return True

            credits = row["credits"] if row["credits"] is not None else 0

            # Strictly require credits >= 1. If 0 credits, reject immediately!
            if credits < 1:
                await db.execute("UPDATE users SET mail_quota = 0 WHERE user_id = ? AND mail_quota > 0", (user_id,))
                await db.commit()
                return False

            new_credits = credits - 1
            await db.execute("""
                UPDATE users 
                SET credits = ?, 
                    mail_quota = ?, 
                    total_emails_created = total_emails_created + 1
                WHERE user_id = ?
            """, (new_credits, new_credits, user_id))
            await db.commit()
            return True


async def add_user_credits(user_id: int, amount: int) -> int:
    """Add credits to a user (Admin or Promo). Returns new balance."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO users (user_id, credits, mail_quota) VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET 
                credits = credits + excluded.credits,
                mail_quota = mail_quota + excluded.credits;
        """, (user_id, amount, amount))
        await db.commit()
    user = await get_user(user_id)
    return user["credits"] if user else amount

async def save_user_email(
    user_id: int,
    email: str,
    password: str,
    token: str,
    account_id: str,
    provider: str = "guerrilla",
    domain: str = "sharklasers.com",
    username: str = ""
):
    """Save or update user's active temp mail account."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO users (user_id, email, password, token, account_id, provider, domain, username, last_message_id, is_monitoring)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, 1)
            ON CONFLICT(user_id) DO UPDATE SET
                email = excluded.email,
                password = excluded.password,
                token = excluded.token,
                account_id = excluded.account_id,
                provider = excluded.provider,
                domain = excluded.domain,
                username = excluded.username,
                last_message_id = NULL,
                is_monitoring = 1;
        """, (user_id, email, password, token, account_id, provider, domain, username))
        await db.commit()

async def delete_user_email(user_id: int):
    """Remove user's active email."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE users 
            SET email = NULL, password = NULL, token = NULL, account_id = NULL, last_message_id = NULL, is_monitoring = 0
            WHERE user_id = ?;
        """, (user_id,))
        await db.commit()

async def delete_user_completely(user_id: int):
    """Completely delete a user and all their received messages from the database."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM received_messages WHERE user_id = ?;", (user_id,))
        await db.execute("DELETE FROM users WHERE user_id = ?;", (user_id,))
        await db.commit()

async def get_all_active_users() -> List[Dict[str, Any]]:
    """Get all users with an active temp mail account and monitoring enabled."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE email IS NOT NULL AND token IS NOT NULL AND is_monitoring = 1 AND is_banned = 0") as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

async def update_last_message_id(user_id: int, last_msg_id: str):
    """Update last seen message ID for user."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET last_message_id = ? WHERE user_id = ?", (last_msg_id, user_id))
        await db.commit()

async def is_message_recorded(msg_id: str) -> bool:
    """Check if message has already been processed and alerted to user."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT 1 FROM received_messages WHERE id = ?", (msg_id,)) as cursor:
            row = await cursor.fetchone()
            return row is not None

async def record_received_message(msg_id: str, user_id: int, sender_service: str, sender_address: str, subject: str, otp_code: Optional[str], verification_link: Optional[str]):
    """Save processed message details."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR IGNORE INTO received_messages (id, user_id, sender_service, sender_address, subject, otp_code, verification_link)
            VALUES (?, ?, ?, ?, ?, ?, ?);
        """, (msg_id, user_id, sender_service, sender_address, subject, otp_code, verification_link))
        await db.commit()

async def get_recent_received_messages(limit: int = 8, offset: int = 0) -> List[Dict[str, Any]]:
    """Fetch recent messages across all users, joined with user email and username."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        sql = """
            SELECT r.*, u.email as user_email, u.username as tg_username
            FROM received_messages r
            LEFT JOIN users u ON r.user_id = u.user_id
            ORDER BY r.received_at DESC, r.rowid DESC
            LIMIT ? OFFSET ?
        """
        async with db.execute(sql, (limit, offset)) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

async def get_user_received_messages(target_user_id: int, limit: int = 8, offset: int = 0) -> List[Dict[str, Any]]:
    """Fetch messages and OTPs for a specific user."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        sql = """
            SELECT r.*, u.email as user_email, u.username as tg_username
            FROM received_messages r
            LEFT JOIN users u ON r.user_id = u.user_id
            WHERE r.user_id = ?
            ORDER BY r.received_at DESC, r.rowid DESC
            LIMIT ? OFFSET ?
        """
        async with db.execute(sql, (target_user_id, limit, offset)) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

async def get_total_received_messages_count(target_user_id: Optional[int] = None) -> int:
    """Get total count of received messages in system or for a specific user."""
    async with aiosqlite.connect(DB_PATH) as db:
        if target_user_id:
            async with db.execute("SELECT COUNT(*) FROM received_messages WHERE user_id = ?", (target_user_id,)) as cur:
                row = await cur.fetchone()
                return row[0] if row else 0
        else:
            async with db.execute("SELECT COUNT(*) FROM received_messages") as cur:
                row = await cur.fetchone()
                return row[0] if row else 0

async def get_received_message_by_id(msg_id: str) -> Optional[Dict[str, Any]]:
    """Fetch a single recorded message with user details."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        sql = """
            SELECT r.*, u.email as user_email, u.username as tg_username
            FROM received_messages r
            LEFT JOIN users u ON r.user_id = u.user_id
            WHERE r.id = ?
        """
        async with db.execute(sql, (msg_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def get_admin_stats() -> Dict[str, Any]:
    """Calculate comprehensive bot metrics for Admin Panel."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as c1:
            total_users = (await c1.fetchone())[0]

        async with db.execute("SELECT COUNT(*) FROM users WHERE email IS NOT NULL") as c2:
            active_emails = (await c2.fetchone())[0]

        async with db.execute("SELECT COUNT(*) FROM received_messages") as c3:
            total_messages = (await c3.fetchone())[0]

        async with db.execute("SELECT SUM(referrals_count) FROM users") as c4:
            row4 = await c4.fetchone()
            total_referrals = row4[0] if row4 and row4[0] else 0

        async with db.execute("SELECT COUNT(*) FROM users WHERE is_banned = 1") as c5:
            banned_users = (await c5.fetchone())[0]

    return {
        "total_users": total_users,
        "active_emails": active_emails,
        "total_messages": total_messages,
        "total_referrals": total_referrals,
        "banned_users": banned_users
    }

async def get_all_user_ids() -> List[int]:
    """Get all user IDs for broadcasting."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM users WHERE is_banned = 0") as cursor:
            rows = await cursor.fetchall()
            return [r[0] for r in rows]

async def set_user_ban(user_id: int, is_banned: int = 1):
    """Ban or unban a user."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET is_banned = ? WHERE user_id = ?", (is_banned, user_id))
        await db.commit()

async def add_force_channel(chat_id: str, title: str, invite_link: str, chat_type: str = "channel") -> bool:
    """Add or update a required force-subscription channel or group."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO force_channels (chat_id, title, invite_link, chat_type)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                title = excluded.title,
                invite_link = excluded.invite_link,
                chat_type = excluded.chat_type;
        """, (chat_id, title, invite_link, chat_type))
        await db.commit()
        return True

async def remove_force_channel(channel_id: int) -> bool:
    """Delete a force-sub channel by its database ID."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM force_channels WHERE id = ?", (channel_id,))
        await db.commit()
        return True

async def remove_force_channel_by_chat_id(chat_id: str) -> bool:
    """Delete a force-sub channel by its chat_id/username."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM force_channels WHERE chat_id = ?", (chat_id,))
        await db.commit()
        return True

async def get_force_channels() -> List[Dict[str, Any]]:
    """Retrieve all required force-sub channels and groups."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM force_channels ORDER BY id ASC") as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

async def set_user_theme(user_id: int, theme: str):
    """Save user color theme preference."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET theme = ? WHERE user_id = ?", (theme, user_id))
        await db.commit()

async def get_user_theme(user_id: int) -> str:
    """Get user theme preference, defaults to 'auto'."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT theme FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row and row["theme"]:
                return row["theme"]
    return "auto"

# ============================================
# BUTTON EMOJIS (CUSTOMIZABLE VIA ADMIN)
# ============================================

DEFAULT_BUTTON_EMOJIS: Dict[str, str] = {
    # Main Menu Buttons
    "inbox": "6129479035077531636",         # Check Inbox
    "new": "6129479035077531636",           # New Email
    "gen": "6129479035077531636",           # Generate Temp Email
    "profile": "6129760505759276442",       # Profile / Balance
    "refer": "6129579803600231171",         # Refer & Earn
    "delete": "6129782440157256336",        # Delete Email
    "help": "5334544901428229844",          # Help & Guide
    "redeem": "6129805465476929485",        # Redeem Code
    "admin": "5341715473882955310",         # Admin Panel

    # Mail & Inbox Buttons
    "read_mail": "6129432481927010933",     # View Full Mail
    "del_mail": "6129486856212979482",      # Delete Mail
    "refresh_inbox": "5375338737028841420",  # Refresh Inbox
    "back_inbox": "5253742260054409879",    # Back to Inbox
    "verify_link": "6129639980387015660",   # Log In / Verify

    # Referral & Balance Buttons
    "claim": "6129805465476929485",         # Claim 1 Mail (1 Credit)
    "refer_friends": "6131660826924292492", # Refer Friends
    "share": "6129639980387015660",         # Share Link With Friends
    "quick_share": "6129639980387015660",   # Quick Share on Telegram
    "leaderboard": "6156436440260549720",   # Referral Leaderboard

    # System & Navigation Buttons
    "back": "6123107313654960925",          # Back to Main Menu / Back
    "cancel": "5210952531676504517",        # Cancel
    "fsub_verify": "6147565374289220368",   # I have joined all

    # Admin Panel Actions
    "admin_stats": "6129801569941592173",       # Detailed Stats
    "admin_broadcast": "6129433877791382400",   # Broadcast Message
    "admin_fsub_list": "6129906126625447892",   # Force Join Channels
    "admin_add_credits": "6123044667261981438", # Add User Credits
    "admin_redeem": "6129805465476929485",      # Manage Redeem Codes
    "admin_btn_colors": "6129479035077531636",  # Change Button Colors
    "admin_btn_texts": "6129479035077531636",   # Change Button Texts
    "admin_btn_emojis": "6129479035077531636",  # Change Button Emojis
    "admin_user_lookup": "5231012545799666522", # User Lookup
    "add_fsub": "5397916757333654639",          # Add Channel / Group
    "del_fsub": "6129486856212979482",          # Remove Channel
}

BUTTON_NAMES: Dict[str, str] = {
    # Main Menu
    "inbox": "Check Inbox",
    "new": "New Email",
    "gen": "Generate Temp Email",
    "profile": "Profile / Balance",
    "refer": "Refer & Earn",
    "redeem": "Redeem Code",
    "delete": "Delete Email",
    "help": "Help & Guide",
    "admin": "Admin Panel",

    # Mail & Inbox
    "read_mail": "View Full Mail",
    "del_mail": "Delete Mail",
    "refresh_inbox": "Refresh Inbox",
    "back_inbox": "Back to Inbox",
    "verify_link": "Log In / Verify",

    # Referral & Balance
    "claim": "Claim 1 Mail",
    "refer_friends": "Refer Friends",
    "share": "Share Link With Friends",
    "quick_share": "Quick Share on Telegram",
    "leaderboard": "Referral Leaderboard",

    # System & Navigation
    "back": "Back to Main Menu",
    "cancel": "Cancel Button",
    "fsub_verify": "I have joined all",

    # Admin Panel Actions
    "admin_stats": "Detailed Stats",
    "admin_broadcast": "Broadcast Message",
    "admin_fsub_list": "Force Join Channels",
    "admin_add_credits": "Add User Credits",
    "admin_redeem": "Manage Redeem Codes",
    "admin_btn_colors": "Change Button Colors",
    "admin_btn_texts": "Change Button Texts",
    "admin_btn_emojis": "Change Button Emojis",
    "admin_user_lookup": "User Lookup",
    "add_fsub": "Add Channel / Group",
    "del_fsub": "Remove Channel",
}

BUTTON_CATEGORIES: Dict[str, Dict[str, Any]] = {
    "cat_main": {
        "title": "Main Menu Buttons",
        "icon": "6129479035077531636",
        "keys": ["inbox", "new", "gen", "profile", "refer", "redeem", "delete", "help", "admin"]
    },
    "cat_mail": {
        "title": "Mail & Inbox Buttons",
        "icon": "5253742260054409879",
        "keys": ["read_mail", "del_mail", "refresh_inbox", "back_inbox", "verify_link"]
    },
    "cat_refer": {
        "title": "Refer & Balance Buttons",
        "icon": "6131660826924292492",
        "keys": ["claim", "refer_friends", "share", "quick_share", "leaderboard"]
    },
    "cat_nav": {
        "title": "Navigation & Admin Buttons",
        "icon": "5341715473882955310",
        "keys": ["back", "cancel", "fsub_verify", "admin_stats", "admin_broadcast", "admin_fsub_list", "admin_add_credits", "admin_redeem", "admin_btn_colors", "admin_btn_texts", "admin_btn_emojis", "admin_user_lookup", "add_fsub", "del_fsub"]
    }
}

async def get_button_emojis() -> Dict[str, str]:
    """Fetch all button emojis from database."""
    emojis = dict(DEFAULT_BUTTON_EMOJIS)
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT btn_key, emoji_id FROM button_emojis") as cursor:
            rows = await cursor.fetchall()
            for k, v in rows:
                emojis[k] = v
    return emojis

async def set_button_emoji(btn_key: str, emoji_id: str) -> bool:
    """Save button emoji to database."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO button_emojis (btn_key, emoji_id) VALUES (?, ?)
            ON CONFLICT(btn_key) DO UPDATE SET emoji_id = excluded.emoji_id;
        """, (btn_key, emoji_id.strip()))
        await db.commit()
    return True

async def reset_all_button_emojis() -> bool:
    """Reset all button emojis back to default values."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM button_emojis;")
        await db.commit()
    return True

async def get_button_colors() -> Dict[str, str]:
    """Fetch all custom button colors from database."""
    colors = {}
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT btn_key, color FROM button_colors") as cursor:
            rows = await cursor.fetchall()
            for k, v in rows:
                colors[k] = v
    return colors

async def set_button_color(btn_key: str, color: str) -> bool:
    """Save button color to database."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO button_colors (btn_key, color) VALUES (?, ?)
            ON CONFLICT(btn_key) DO UPDATE SET color = excluded.color;
        """, (btn_key, color.strip()))
        await db.commit()
    return True

async def reset_all_button_colors() -> bool:
    """Reset all button colors back to default values."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM button_colors;")
        await db.commit()
    return True

async def get_button_texts() -> Dict[str, str]:
    """Fetch all custom button texts from database."""
    texts = {}
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT btn_key, btn_text FROM button_texts") as cursor:
            rows = await cursor.fetchall()
            for k, v in rows:
                texts[k] = v
    return texts

async def set_button_text(btn_key: str, btn_text: str) -> bool:
    """Save button text to database."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO button_texts (btn_key, btn_text) VALUES (?, ?)
            ON CONFLICT(btn_key) DO UPDATE SET btn_text = excluded.btn_text;
        """, (btn_key, btn_text.strip()))
        await db.commit()
    return True

async def reset_all_button_texts() -> bool:
    """Reset all button texts back to default values."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM button_texts;")
        await db.commit()
    return True

async def get_referral_leaderboard(limit: int = 10) -> List[Dict[str, Any]]:
    """Retrieve top referrers ordered by referrals_count descending."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT user_id, username, referrals_count, total_emails_created
            FROM users
            WHERE is_banned = 0 AND referrals_count > 0
            ORDER BY referrals_count DESC, total_emails_created DESC
            LIMIT ?
        """, (limit,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

async def get_user_referral_rank(user_id: int) -> int:
    """Get the leaderboard rank of a specific user."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT referrals_count FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if not row or row[0] is None or row[0] == 0:
                return 0
            user_refs = row[0]

        async with db.execute("SELECT COUNT(*) FROM users WHERE referrals_count > ? AND is_banned = 0", (user_refs,)) as c2:
            rank = (await c2.fetchone())[0] + 1
            return rank

async def update_user_username(user_id: int, username: str):
    """Save Telegram username for leaderboard and admin lookup."""
    if not username:
        return
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET username = ? WHERE user_id = ?", (username.lstrip("@"), user_id))
        await db.commit()


# ============================================
# REDEEM CODE MANAGEMENT
# ============================================

async def create_redeem_code(code: str, credits: int, max_users: int) -> tuple[bool, str]:
    """Create a new redeem code with credit amount and total valid users."""
    code_clean = code.strip().upper()
    if not code_clean:
        return False, "Redeem code cannot be empty!"
    if credits <= 0:
        return False, "Credits must be greater than 0!"
    if max_users <= 0:
        return False, "Total valid users must be at least 1!"

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT code FROM redeem_codes WHERE code = ?", (code_clean,)) as cursor:
            if await cursor.fetchone():
                return False, f"Code <code>{code_clean}</code> already exists!"

        await db.execute("""
            INSERT INTO redeem_codes (code, credits, max_users, redeemed_count, is_active)
            VALUES (?, ?, ?, 0, 1)
        """, (code_clean, credits, max_users))
        await db.commit()
        return True, f"Redeem Code <code>{code_clean}</code> created successfully!"

async def get_redeem_code(code: str) -> Optional[Dict[str, Any]]:
    """Fetch details of a specific redeem code."""
    code_clean = code.strip().upper()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM redeem_codes WHERE code = ?", (code_clean,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def get_all_redeem_codes() -> List[Dict[str, Any]]:
    """Retrieve all redeem codes ordered by newest first."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM redeem_codes ORDER BY created_at DESC") as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

async def delete_redeem_code(code: str) -> bool:
    """Delete a redeem code and its history from the database."""
    code_clean = code.strip().upper()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM redeem_history WHERE code = ?", (code_clean,))
        cursor = await db.execute("DELETE FROM redeem_codes WHERE code = ?", (code_clean,))
        await db.commit()
        return cursor.rowcount > 0

async def redeem_code_for_user(code: str, user_id: int) -> tuple[bool, str, int]:
    """
    Attempt to redeem a code for a user.
    Returns: (success: bool, message: str, credits_added: int)
    """
    code_clean = code.strip().upper()
    if not code_clean:
        return False, "Please enter a valid redeem code.", 0

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        
        # 1. Check code existence and status
        async with db.execute("SELECT * FROM redeem_codes WHERE code = ?", (code_clean,)) as cursor:
            code_data = await cursor.fetchone()
            if not code_data:
                return False, "Invalid Redeem Code! Please check the code and try again.", 0
            
            code_dict = dict(code_data)
            if not code_dict.get("is_active", 1):
                return False, "This redeem code has been deactivated by the admin.", 0
            
            max_users = code_dict.get("max_users", 0)
            redeemed_count = code_dict.get("redeemed_count", 0)
            credits_to_give = code_dict.get("credits", 1)

            if redeemed_count >= max_users:
                return False, "This redeem code has expired! Maximum user redemption limit reached.", 0

        # 2. Check if user already claimed this code
        async with db.execute("SELECT id FROM redeem_history WHERE code = ? AND user_id = ?", (code_clean, user_id)) as cursor:
            if await cursor.fetchone():
                return False, "You have already redeemed this code! Each code can only be used once per account.", 0

        # 3. Process redemption atomically
        try:
            # Add to history
            await db.execute("INSERT INTO redeem_history (code, user_id) VALUES (?, ?)", (code_clean, user_id))
            
            # Increment redeemed count
            await db.execute("UPDATE redeem_codes SET redeemed_count = redeemed_count + 1 WHERE code = ?", (code_clean,))
            
            # Award credits to user (1 credit = 1 mail quota)
            await db.execute("""
                UPDATE users 
                SET credits = credits + ?, mail_quota = mail_quota + ? 
                WHERE user_id = ?
            """, (credits_to_give, credits_to_give * MAILS_PER_CREDIT, user_id))
            
            await db.commit()
            return True, f"🎉 Success! <b>+{credits_to_give} Credits</b> added to your account!", credits_to_give
        except Exception as e:
            return False, f"Failed to redeem code: {e}", 0



