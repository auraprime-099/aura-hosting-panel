"""
Telegram Premium Custom Emojis Map & Helpers
Provides animated custom emoji tags for message formatting (<tg-emoji>)
and custom emoji IDs for InlineKeyboardButton (icon_custom_emoji_id).
"""

# Custom Emoji IDs (mapped from user's provided Premium Emoji JSON)
PE_IDS = {
    # Core & Identity
    "verified": "6147565374289220368",      # ✅
    "blue_verified": "6147524086768604985", # 💎
    "crown": "6129705083501293112",         # 👑
    "fire": "6129792056589031358",          # 🔥
    "fire2": "6129897266107915247",         # 🔥
    "sparkle": "6129479035077531636",       # ✨
    "bolt": "6129805465476929485",          # ⚡
    "lightning": "6129695952400820630",     # ⚡
    "email": "6129432481927010933",         # ✉️
    "inbox": "5253742260054409879",         # 📬
    "card": "6129926111108275647",          # 💳
    "moneybag": "6123044667261981438",      # 💰
    "money": "6129732880529628243",         # 💵
    "gift": "6131660826924292492",          # 🎁
    "heart": "6147617184479711380",         # ❤️‍🔥
    "star": "6129909635613726974",          # ⭐
    "star2": "6129915811776698328",         # 🌟
    "top": "5463071033256848094",           # 🔝
    "rocket": "6129639980387015660",        # 🚀
    "trash": "6129486856212979482",         # 🗑️
    "refresh": "5375338737028841420",       # 🔄
    "gear": "5341715473882955310",          # ⚙️
    "search": "5231012545799666522",        # 🔍
    "lock": "6129906126625447892",          # 🔒
    "info": "5334544901428229844",          # ℹ️
    "warning": "6129782440157256336",       # ⚠️
    "cross": "5210952531676504517",         # ❌
    "check": "6129812419028982717",         # ✅
    "link": "6129589862413638401",          # 🔗
    "broadcast": "6129433877791382400",     # 📢
    "stats": "6129801569941592173",         # 📊
    "plus": "5397916757333654639",          # ➕
    "arrow_right": "6154421933095000846",   # ➡️
    "back": "6123107313654960925",          # ⬅️
    "globe": "5447410659077661506",         # 🌐
    "robot": "6129873536413605540",         # 🤖
    "party": "6129579803600231171",         # 🎉
    "user": "6084695058894819673",          # 👤
    "time": "6093456762113888541",          # ⏰
    "diamond": "6129760505759276442",       # 💎
    "handshake": "5463256910851546817",     # 🤝
    "bell": "6129577213734952104",          # 🔔
    "pin": "6129694470637100146",           # 📌
    "target": "5240245613089541481",        # 🎯
    "key": "6129731845442510016",           # 🔐
    "shield": "6086672466132865380",        # 🛡️
    "magic": "6129479035077531636",         # 🪄
    "cool": "6147464060305676048",          # 😎
    "love": "6089423023318766264",          # 🥰
    "trophy": "6156436440260549720",        # 🏆
    "bulb": "5422439311196834318",          # 💡
    "wave": "6095851644468072524",          # 👋
    "boom": "6129532314146838421",          # 💥
    "hundred": "6154257607646255757",       # 💯
    "bubble": "6129579597441801084",        # 💬
    # Specific IDs specified by user for Email Dashboard
    "user_namaste": "5436145964882606058",    # Welcome icon
    "user_welcome_end": "5208748315805499400", # Sparkle/star icon after username
    "user_email_head": "5472239203590888751",  # Your Active Temp Email
    "user_pointer": "5415758949129404605",     # Email pointer / copy
    "user_domain": "5447410659077661506",      # Domain icon
    "user_otp": "6046322897654387087",         # Auto OTP Detection
    "user_on_hai": "6233111867171018062",      # Active status icon
    "user_quota": "6233111867171018062",       # Available Mails
    "user_credits": "5287231198098117669",     # Credits Balance
    "user_tip": "5312361253610475399",         # Tip line start icon
    "user_new_email": "6129479035077531636",   # New Email emoji
    "user_inbox_empty": "5253742260054409879", # Inbox Khali Hai
    "user_inbox_alert": "6267039884016358504", # Alert bhejega
    "access_restricted": "6267039884016358504", # Access restricted
    "restricted": "6267039884016358504",        # Restricted
    # Referral notifications
    "ref_detected": "5372865660500067203",     # Referral Detected icon
    "ref_name": "5256143829672672750",         # Name icon
    "ref_waiting": "5271604874419647061",      # Waiting for verification icon
    "ref_confirmed": "5258079378159453410",    # Referral Confirmed icon
    "ref_bonus": "5353057756662210233",        # Bonus credit icon
}

# Fallback Unicode Emojis
FALLBACKS = {
    "verified": "✅",
    "blue_verified": "💎",
    "crown": "👑",
    "fire": "🔥",
    "fire2": "🔥",
    "sparkle": "✨",
    "bolt": "⚡",
    "lightning": "⚡",
    "email": "✉️",
    "inbox": "📬",
    "card": "💳",
    "moneybag": "💰",
    "money": "💵",
    "gift": "🎁",
    "heart": "❤️‍🔥",
    "star": "⭐",
    "star2": "🌟",
    "top": "🔝",
    "rocket": "🚀",
    "trash": "🗑️",
    "refresh": "🔄",
    "gear": "⚙️",
    "search": "🔍",
    "lock": "🔒",
    "info": "ℹ️",
    "warning": "⚠️",
    "cross": "❌",
    "check": "✅",
    "link": "🔗",
    "broadcast": "📢",
    "stats": "📊",
    "plus": "➕",
    "arrow_right": "👉",
    "back": "⬅️",
    "globe": "🌐",
    "robot": "🤖",
    "party": "🎉",
    "user": "👤",
    "time": "⏰",
    "diamond": "💎",
    "handshake": "🤝",
    "bell": "🔔",
    "pin": "📌",
    "target": "🎯",
    "key": "🔐",
    "shield": "🛡️",
    "magic": "🪄",
    "cool": "😎",
    "love": "🥰",
    "trophy": "🏆",
    "bulb": "💡",
    "wave": "👋",
    "boom": "💥",
    "hundred": "💯",
    "bubble": "💬",
    "user_namaste": "🙏",
    "user_email_head": "✉️",
    "user_pointer": "👉",
    "user_domain": "🌐",
    "user_otp": "⚡",
    "user_on_hai": "⚡",
    "user_quota": "📧",
    "user_tip": "💡",
    "user_new_email": "⚡",
    "access_restricted": "🚨",
    "restricted": "🚨",
    "ref_detected": "☠️",
    "ref_name": "👤",
    "ref_waiting": "⏳",
    "ref_confirmed": "✔️",
    "ref_bonus": "🎁",
    "6339166816006312740": "👇",
    "5379668527919684482": "🌟",
    "5454371323595744068": "🎁",
    "6129873536413605540": "🤖",
    "6129792056589031358": "🔥",
    "5278467510604160626": "🎁",
    "5190806721286657692": "💳",
    "5332724926216428039": "👥",
    "6086639764251873025": "👤",
    "6057790228406470570": "✉️",
    "6267039884016358504": "🚫",
    "6267000941547885720": "❌",
    "6129579803600231171": "🎉",
    "5240228673738527951": "🎟️",
    "5438212260763808371": "🎁",
    "5210952608985923439": "✅",
    "5445353829304387411": "💳",
}

def pe(name: str) -> str:
    """Format a premium custom emoji tag for HTML parse mode. Supports named keys or raw numeric emoji IDs."""
    if name.isdigit():
        fb = FALLBACKS.get(name, "✨")
        return f'<tg-emoji emoji-id="{name}">{fb}</tg-emoji>'
    emoji_id = PE_IDS.get(name)
    fb = FALLBACKS.get(name, "✨")
    if emoji_id:
        return f'<tg-emoji emoji-id="{emoji_id}">{fb}</tg-emoji>'
    return fb

def pe_id(name: str) -> str:
    """Get the raw custom emoji ID for inline keyboard buttons. Supports named keys or raw numeric emoji IDs."""
    if name.isdigit():
        return name
    return PE_IDS.get(name, "6129479035077531636")

