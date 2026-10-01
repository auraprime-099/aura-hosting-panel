import re
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from typing import Optional, Dict, Any, Tuple, List

# Common known service domains map
KNOWN_SERVICES = {
    "google.com": "Google",
    "youtube.com": "YouTube",
    "instagram.com": "Instagram",
    "facebook.com": "Facebook",
    "facebookmail.com": "Facebook",
    "whatsapp.com": "WhatsApp",
    "telegram.org": "Telegram",
    "twitter.com": "Twitter / X",
    "x.com": "Twitter / X",
    "discord.com": "Discord",
    "github.com": "GitHub",
    "gitlab.com": "GitLab",
    "replit.com": "Replit",
    "anthropic.com": "Claude / Anthropic",
    "claude.ai": "Claude.ai",
    "openai.com": "ChatGPT / OpenAI",
    "tm.openai.com": "ChatGPT",
    "cursor.com": "Cursor",
    "cursor.sh": "Cursor",
    "vercel.com": "Vercel",
    "supabase.com": "Supabase",
    "netflix.com": "Netflix",
    "amazon.com": "Amazon",
    "amazon.in": "Amazon",
    "spotify.com": "Spotify",
    "microsoft.com": "Microsoft",
    "apple.com": "Apple",
    "steampowered.com": "Steam",
    "epicgames.com": "Epic Games",
    "roblox.com": "Roblox",
    "reddit.com": "Reddit",
    "linkedin.com": "LinkedIn",
    "tiktok.com": "TikTok",
    "uber.com": "Uber",
    "ola.in": "Ola",
    "swiggy.in": "Swiggy",
    "zomato.com": "Zomato",
    "paypal.com": "PayPal",
    "binance.com": "Binance"
}

IGNORE_LINK_KEYWORDS = [
    "unsubscribe", "privacy", "terms", "opt-out", "support",
    "preferences", "play.google.com", "apps.apple.com", "twitter.com",
    "facebook.com", "instagram.com", "linkedin.com", "youtube.com"
]

def extract_sender_info(from_data: Any) -> Dict[str, str]:
    """
    Extract website/service name and email address from sender object.
    from_data can be a dict {'name': '...', 'address': '...'} or string.
    """
    name = ""
    address = ""

    if isinstance(from_data, dict):
        name = from_data.get("name", "").strip()
        address = from_data.get("address", "").strip()
    elif isinstance(from_data, str):
        match = re.match(r'(?:"?([^"]*)"?\s*)?<?([^>]+)>?', from_data.strip())
        if match:
            name = match.group(1) or ""
            address = match.group(2) or ""
        else:
            address = from_data.strip()

    # Extract domain
    domain = ""
    if "@" in address:
        domain = address.split("@")[-1].lower()

    # Identify Service / Website Name
    detected_service = ""
    # Check known domain mappings
    for known_domain, service_title in KNOWN_SERVICES.items():
        if domain == known_domain or domain.endswith("." + known_domain):
            detected_service = service_title
            break

    # If not mapped, check if sender name is already nice
    if not detected_service and name and not name.startswith("http") and "@" not in name:
        detected_service = name

    # If still not found, derive from domain
    if not detected_service and domain:
        parts = domain.split(".")
        if len(parts) >= 2:
            detected_service = parts[-2].capitalize()
        else:
            detected_service = domain.capitalize()

    return {
        "service_name": detected_service or "Unknown Service",
        "sender_name": name or detected_service or "Unknown",
        "sender_address": address,
        "domain": domain
    }

def extract_otp(subject: str, text: str, html: str = "") -> Optional[str]:
    """
    Extract OTP / Verification code (4-8 digits, or codes like G-123456).
    Handles plain text and raw HTML (OpenAI, Claude, Google, Koyeb, Supabase, etc.).
    Normalizes whitespace and removes tags to ensure 100% detection rate.
    """
    # 1. Look for Google-style or Prefix-style codes: e.g. G-123456 or CODE-123456 in subject or raw text
    prefix_match = re.search(r'\b([A-Z]{1,4}-\d{4,8})\b', f"{subject}\n{text}")
    if prefix_match:
        return prefix_match.group(1)

    # 2. Extract clean text from HTML if present
    raw_combined = f"{text}\n{html}"
    if "<" in raw_combined and ">" in raw_combined:
        try:
            soup = BeautifulSoup(raw_combined, "html.parser")
            for s in soup(["script", "style", "meta", "head"]):
                s.decompose()
            clean_body = soup.get_text(separator=" ")
        except Exception:
            clean_body = text
    else:
        clean_body = text

    # Normalize whitespace so table padding or blank lines don't break regex proximity
    normalized_body = re.sub(r'\s+', ' ', clean_body).strip()
    normalized_subject = re.sub(r'\s+', ' ', subject).strip()

    # 3. Strict keyword-based OTP in Subject or Normalized Body
    keyword_patterns = [
        r'(?:verification|security|confirmation|login|otp|passcode|secret|access)?\s*(?:code|pin|otp|password)\s*(?:is|:|-)?\s*([0-9]{4,8})\b',
        r'\b(?:code|pin|otp|password|passcode)\b[^\d]{0,80}\b([0-9]{4,8})\b',
        r'\b([0-9]{4,8})\b[^\d]{0,80}\b(?:is\s+your|is\s+the|to\s+verify|for\s+verification|code|pin|otp)\b',
        r'(?:enter|use)\s*(?:this|the)?\s*(?:temporary|security|verification)?\s*(?:code|pin|otp)?\s*(?:is|:|-)?\s*([0-9]{4,8})\b',
        r'\bcode:\s*([0-9]{4,8})\b',
        r'(?:one-time|one\s+time)\s+(?:code|password|passcode)\s*(?:is|:|-)?\s*([0-9]{4,8})\b',
        r'\botp\s*(?:is|:|-)?\s*([0-9]{4,8})\b'
    ]

    for pattern in keyword_patterns:
        match = re.search(pattern, normalized_subject, re.IGNORECASE)
        if match:
            return match.group(1)

    for pattern in keyword_patterns:
        match = re.search(pattern, normalized_body, re.IGNORECASE)
        if match:
            val = match.group(1)
            # Avoid years
            if len(val) == 4 and val.startswith("202"):
                continue
            # Avoid postal code / street numbers like "PMB 90375" or "PO Box"
            start_pos = match.start(1)
            preceding = normalized_body[max(0, start_pos - 25):start_pos].lower()
            if any(term in preceding for term in ["pmb", "box", "st,", "street", "suite", "apt"]):
                continue
            return val

    # 4. Check subject for standalone 4-8 digit number IF subject has auth/verification words
    if any(k in normalized_subject.lower() for k in ["code", "otp", "verify", "verification", "confirm", "security", "use"]):
        subject_digits = re.search(r'\b([0-9]{4,8})\b', normalized_subject)
        if subject_digits:
            val = subject_digits.group(1)
            if not (len(val) == 4 and val.startswith("202")):
                return val

    # 5. Check HTML tags for standalone code e.g. <code>123456</code>, <p>123456</p>, <b>123456</b>
    if html or ("<" in text and ">" in text):
        raw_html = html if html else text
        try:
            soup = BeautifulSoup(raw_html, "html.parser")
            for tag in soup.find_all(["code", "b", "strong", "h1", "h2", "h3", "span", "p", "div", "td", "font"]):
                tag_text = tag.get_text(strip=True)
                if re.fullmatch(r'[0-9]{4,8}', tag_text):
                    if not (len(tag_text) == 4 and tag_text.startswith("202")):
                        parent_text = (tag.parent.get_text() if tag.parent else "").lower()
                        full_text = normalized_body.lower()
                        if any(kw in parent_text or kw in full_text for kw in ["code", "otp", "pin", "verify", "verification", "security", "temporary", "use", "confirm"]):
                            if "pmb" not in parent_text and "street" not in parent_text:
                                return tag_text
        except Exception:
            pass

    return None

def extract_verification_link(html: str, text: str) -> Optional[str]:
    """
    Extract verification, confirmation, or direct magic login link from HTML or plain text.
    Handles Claude.ai, Replit, Supabase, Google, ChatGPT, and other auth emails.
    """
    action_keywords = [
        "verify", "confirm", "activate", "sign in", "signin", "log in", "login",
        "magic link", "get started", "complete registration", "continue", "access"
    ]
    url_keywords = [
        "magic-link", "magic_link", "token=", "verify", "verification",
        "confirm", "activate", "auth/verify", "login/magic"
    ]

    # 1. Search HTML <a> tags
    if html or ("<" in text and ">" in text):
        raw_html = html if html else text
        try:
            soup = BeautifulSoup(raw_html, "html.parser")
            links = soup.find_all("a", href=True)
            
            # Priority 1: Anchor text contains action keyword
            for a in links:
                href = a['href'].strip()
                anchor_text = a.get_text(strip=True).lower()
                
                if not href.startswith("http"):
                    continue
                
                if any(k in anchor_text for k in action_keywords):
                    if not any(ign in href.lower() for ign in IGNORE_LINK_KEYWORDS):
                        return href

            # Priority 2: href itself contains verification / magic link parameters
            for a in links:
                href = a['href'].strip()
                if not href.startswith("http"):
                    continue
                lower_href = href.lower()
                if any(k in lower_href for k in url_keywords):
                    if not any(ign in lower_href for ign in IGNORE_LINK_KEYWORDS):
                        return href
        except Exception:
            pass

    # 2. Search plain text for URLs
    url_pattern = r'(https?://[^\s<>"\']+)'
    urls = re.findall(url_pattern, text)
    for url in urls:
        clean_url = url.rstrip(".,;)>]")
        lower_url = clean_url.lower()
        if any(k in lower_url for k in url_keywords + ["signin", "login"]):
            if not any(ign in lower_url for ign in IGNORE_LINK_KEYWORDS):
                return clean_url

    return None

def clean_text_content(text: str, html: str = "") -> str:
    """
    Get clean, human-readable plain text from email, stripping all HTML formatting.
    """
    source = text
    is_html = ("<" in text and ">" in text) or bool(html)
    
    if is_html:
        raw = html if html else text
        try:
            soup = BeautifulSoup(raw, "html.parser")
            for s in soup(["script", "style", "meta", "head", "img"]):
                s.decompose()
            clean = soup.get_text(separator="\n").strip()
        except Exception:
            clean = text.strip()
    elif text and text.strip():
        clean = text.strip()
    else:
        clean = "No text content available."

    # Remove repeated spaces and excessive blank lines
    clean = re.sub(r'[ \t]+', ' ', clean)
    clean = re.sub(r'\n{3,}', '\n\n', clean).strip()

    if len(clean) > 2000:
        return clean[:1950] + "\n\n...[Truncated - Read full mail for more]"
    return clean
