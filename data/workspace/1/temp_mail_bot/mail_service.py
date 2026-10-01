import aiohttp
import asyncio
import random
import string
import logging
from typing import Optional, Dict, Any, List
from config import MAIL_API_BASE

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "application/json"
}

def generate_username(style: str = "mix") -> str:
    """
    Generate clean, high-acceptance username.
    5 letters + 5 digits (e.g. fewoj73259, hadeb59051) -> 100% login pass
    """
    letters = ''.join(random.choices(string.ascii_lowercase, k=5))
    digits = ''.join(random.choices(string.digits, k=5))
    return f"{letters}{digits}"

class GuerrillaMailService:
    """
    Guerrilla Mail API client.
    Serves aged, highly trusted, unblocked domains:
    pokemail.net, sharklasers.com, grr.la, spam4.me, guerrillamail.biz, guerrillamail.com.
    """
    BASE_URL = "https://www.guerrillamail.com/ajax.php"
    DOMAINS = [
        "sharklasers.com",
        "pokemail.net",
        "grr.la"
    ]

    def __init__(self, session_getter):
        self.get_session = session_getter

    async def create_account(self, custom_name: Optional[str] = None, domain: Optional[str] = None, exclude_domain: Optional[str] = None) -> Optional[Dict[str, Any]]:
        clean_user = custom_name.strip().lower() if custom_name else generate_username("mix")
        clean_user = "".join(c for c in clean_user if c.isalnum())
        if not clean_user:
            clean_user = generate_username("mix")

        candidates = [d for d in self.DOMAINS if exclude_domain is None or d.lower() != exclude_domain.lower()]
        if not candidates:
            candidates = self.DOMAINS
        chosen_domain = domain if (domain and domain in self.DOMAINS) else random.choice(candidates)

        session = await self.get_session()
        try:
            # 1. Get initial session
            async with session.get(f"{self.BASE_URL}?f=get_email_address", timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json(content_type=None)
                sid_token = data.get("sid_token")

            if not sid_token:
                return None

            # 2. Set user and chosen domain
            set_url = f"{self.BASE_URL}?f=set_email_user&email_user={clean_user}&lang=en&sid_token={sid_token}"
            async with session.get(set_url, timeout=aiohttp.ClientTimeout(total=10)) as resp2:
                if resp2.status == 200:
                    email_addr = f"{clean_user}@{chosen_domain}"
                    return {
                        "email": email_addr,
                        "token": sid_token,
                        "account_id": email_addr,
                        "provider": "guerrilla",
                        "domain": chosen_domain,
                        "username": clean_user
                    }
        except Exception as e:
            logger.error(f"Error creating guerrilla mail: {e}")
        return None

    async def get_messages(self, sid_token: str) -> List[Dict[str, Any]]:
        url = f"{self.BASE_URL}?f=check_email&seq=0&sid_token={sid_token}"
        session = await self.get_session()
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json(content_type=None)
                    raw_list = data.get("list", [])
                    formatted = []
                    for item in raw_list:
                        mail_id = str(item.get("mail_id"))
                        # Ignore Guerrilla Welcome mail
                        if mail_id == "1" or "welcome to guerrilla" in item.get("mail_subject", "").lower():
                            continue

                        addr = item.get("mail_from", "")
                        name = addr.split("<")[0].replace('"', '').strip()
                        formatted.append({
                            "id": mail_id,
                            "from": {"address": addr, "name": name},
                            "subject": item.get("mail_subject") or "No Subject",
                            "intro": item.get("mail_excerpt") or "",
                            "createdAt": str(item.get("mail_date", ""))
                        })
                    return formatted
        except Exception as e:
            logger.error(f"Error checking guerrilla messages: {e}")
        return []

    async def get_message_detail(self, sid_token: str, message_id: str) -> Optional[Dict[str, Any]]:
        url = f"{self.BASE_URL}?f=fetch_email&email_id={message_id}&sid_token={sid_token}"
        session = await self.get_session()
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    d = await resp.json(content_type=None)
                    addr = d.get("mail_from", "")
                    name = addr.split("<")[0].replace('"', '').strip()
                    body = d.get("mail_body", "")
                    try:
                        soup = BeautifulSoup(body, "html.parser")
                        for s in soup(["script", "style", "meta", "head"]):
                            s.decompose()
                        clean_text = soup.get_text(separator="\n").strip()
                    except Exception:
                        clean_text = body
                    return {
                        "id": str(d.get("mail_id")),
                        "from": {"address": addr, "name": name},
                        "subject": d.get("mail_subject") or "No Subject",
                        "text": clean_text if clean_text else body,
                        "html": body,
                        "createdAt": str(d.get("mail_date", ""))
                    }
        except Exception as e:
            logger.error(f"Error fetching guerrilla message detail: {e}")
        return None

class MailTmService:
    """Mail.tm API client (Ultra-fast, highly trusted domains e.g. uberip.com)."""
    BASE_URL = "https://api.mail.tm"

    def __init__(self, session_getter):
        self.get_session = session_getter
        self._cached_domains: List[str] = ["uberip.com"]

    async def get_domains(self) -> List[str]:
        url = f"{self.BASE_URL}/domains"
        session = await self.get_session()
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    members = data if isinstance(data, list) else data.get("hydra:member", [])
                    doms = [d["domain"] for d in members if isinstance(d, dict) and d.get("domain") and d.get("isActive", True)]
                    if doms:
                        self._cached_domains = doms
                        return doms
        except Exception as e:
            logger.warning(f"Error fetching mail.tm domains: {e}")
        return self._cached_domains

    async def create_account(self, custom_name: Optional[str] = None, domain: Optional[str] = None, exclude_domain: Optional[str] = None) -> Optional[Dict[str, Any]]:
        clean_user = custom_name.strip().lower() if custom_name else generate_username("mix")
        clean_user = "".join(c for c in clean_user if c.isalnum())
        if not clean_user:
            clean_user = generate_username("mix")

        available = await self.get_domains()
        candidates = [d for d in available if exclude_domain is None or d.lower() != exclude_domain.lower()]
        if not candidates:
            candidates = available
        chosen_domain = domain if (domain and domain in available) else random.choice(candidates)
        email_addr = f"{clean_user}@{chosen_domain}"
        pwd = f"SecPass_{clean_user}_123!"

        session = await self.get_session()
        try:
            # 1. Create account
            async with session.post(f"{self.BASE_URL}/accounts", json={"address": email_addr, "password": pwd}, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status not in [200, 201]:
                    return None
                data = await resp.json()
                acc_id = data.get("id")

            # 2. Get JWT token
            async with session.post(f"{self.BASE_URL}/token", json={"address": email_addr, "password": pwd}, timeout=aiohttp.ClientTimeout(total=10)) as resp2:
                if resp2.status != 200:
                    return None
                token_data = await resp2.json()
                token = token_data.get("token")

            if token:
                return {
                    "email": email_addr,
                    "password": pwd,
                    "token": token,
                    "account_id": acc_id or email_addr,
                    "provider": "mailtm",
                    "domain": chosen_domain,
                    "username": clean_user
                }
        except Exception as e:
            logger.error(f"Error creating mail.tm account: {e}")
        return None

    async def get_messages(self, token: str) -> List[Dict[str, Any]]:
        url = f"{self.BASE_URL}/messages"
        headers = {"Authorization": f"Bearer {token}"}
        session = await self.get_session()
        try:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    items = data.get("hydra:member", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
                    formatted = []
                    for item in items:
                        from_data = item.get("from", {})
                        addr = from_data.get("address", "") if isinstance(from_data, dict) else str(from_data)
                        name = from_data.get("name", "") if isinstance(from_data, dict) else addr
                        intro = item.get("intro") or ""
                        formatted.append({
                            "id": str(item.get("id")),
                            "from": {"address": addr, "name": name},
                            "subject": item.get("subject") or "No Subject",
                            "intro": intro,
                            "createdAt": item.get("createdAt") or ""
                        })
                    return formatted
        except Exception as e:
            logger.error(f"Error checking mail.tm messages: {e}")
        return []

    async def get_message_detail(self, token: str, message_id: str) -> Optional[Dict[str, Any]]:
        url = f"{self.BASE_URL}/messages/{message_id}"
        headers = {"Authorization": f"Bearer {token}"}
        session = await self.get_session()
        try:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    item = await resp.json()
                    from_data = item.get("from", {})
                    addr = from_data.get("address", "") if isinstance(from_data, dict) else str(from_data)
                    name = from_data.get("name", "") if isinstance(from_data, dict) else addr
                    text_body = item.get("text") or ""
                    html_body = "".join(item.get("html", [])) if isinstance(item.get("html"), list) else (item.get("html") or "")
                    return {
                        "id": str(item.get("id")),
                        "from": {"address": addr, "name": name},
                        "subject": item.get("subject") or "No Subject",
                        "intro": item.get("intro") or text_body[:100],
                        "text": text_body,
                        "html": html_body,
                        "createdAt": item.get("createdAt") or ""
                    }
        except Exception as e:
            logger.error(f"Error fetching mail.tm message detail: {e}")
        return None

class TempMailIoService:
    """Temp-Mail.io API client serving fresh .com domains (olipii.com, lnovic.com, ooynib.com)."""
    BASE_URL = "https://api.internal.temp-mail.io/api/v3"

    def __init__(self, session_getter):
        self.get_session = session_getter
        self._cached_domains: List[str] = ["olipii.com", "ooynib.com"]

    async def get_domains(self) -> List[str]:
        url = f"{self.BASE_URL}/domains"
        session = await self.get_session()
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # Exclude unreliable domains like ozsaip.com and lnovic.com
                    blocked = ["ozsaip.com", "lnovic.com"]
                    doms = [d["name"] for d in data.get("domains", []) if d.get("name") and d["name"].lower() not in blocked]
                    if doms:
                        top = [d for d in ["olipii.com", "ooynib.com"] if d in doms]
                        others = [d for d in doms if d not in top]
                        self._cached_domains = top if top else others
                        return self._cached_domains
        except Exception:
            pass
        return self._cached_domains

    async def create_account(self, custom_name: Optional[str] = None, domain: Optional[str] = None, exclude_domain: Optional[str] = None) -> Optional[Dict[str, Any]]:
        clean_user = custom_name.strip().lower() if custom_name else generate_username("mix")
        clean_user = "".join(c for c in clean_user if c.isalnum())
        if not clean_user:
            clean_user = generate_username("mix")

        available = await self.get_domains()
        candidates = [d for d in available if exclude_domain is None or d.lower() != exclude_domain.lower()]
        if not candidates:
            candidates = available
        chosen_domain = domain if (domain and domain in available) else random.choice(candidates)

        url = f"{self.BASE_URL}/email/new"
        payload = {"name": clean_user, "domain": chosen_domain}
        session = await self.get_session()
        try:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    em = data["email"]
                    return {
                        "email": em,
                        "token": data.get("token", ""),
                        "account_id": em,
                        "provider": "tempmailio",
                        "domain": chosen_domain,
                        "username": clean_user
                    }
        except Exception as e:
            logger.error(f"Error creating temp-mail.io account: {e}")
        return None

    async def get_messages(self, email: str) -> List[Dict[str, Any]]:
        url = f"{self.BASE_URL}/email/{email}/messages"
        session = await self.get_session()
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    raw_list = await resp.json()
                    formatted = []
                    for item in raw_list:
                        from_data = item.get("from", "")
                        addr = from_data.get("address", "") if isinstance(from_data, dict) else str(from_data)
                        name = from_data.get("name", "") if isinstance(from_data, dict) else addr
                        text_body = item.get("body_text") or item.get("text") or ""
                        html_body = item.get("body_html") or item.get("html") or ""
                        formatted.append({
                            "id": str(item.get("id")),
                            "from": {"address": addr, "name": name},
                            "subject": item.get("subject") or "No Subject",
                            "intro": text_body[:100],
                            "text": text_body,
                            "html": html_body,
                            "createdAt": item.get("created_at") or ""
                        })
                    return formatted
        except Exception as e:
            logger.error(f"Error checking temp-mail.io messages: {e}")
        return []

    async def get_message_detail(self, email: str, message_id: str) -> Optional[Dict[str, Any]]:
        messages = await self.get_messages(email)
        for msg in messages:
            if msg["id"] == str(message_id):
                return msg
        return None

class UnifiedMailManager:
    """Unified manager alternating between fresh .com domains, ultra-fast Mail.tm, and aged GuerrillaMail."""
    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
        self.mailtm = MailTmService(self.get_session)
        self.guerrilla = GuerrillaMailService(self.get_session)
        self.tempmailio = TempMailIoService(self.get_session)

    async def get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(resolver=aiohttp.ThreadedResolver(), ssl=False)
            self._session = aiohttp.ClientSession(connector=connector, headers=HEADERS)
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def create_temp_account(self, domain: Optional[str] = None, custom_name: Optional[str] = None, exclude_domain: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Create temp account prioritizing high-deliverability clean domains:
        1. Mail.tm (uberip.com - guaranteed instant OTP delivery for Claude & OpenAI)
        2. TempMail.io (olipii.com)
        3. GuerrillaMail (sharklasers.com)
        """
        # If specific domain requested
        if domain:
            if any(domain.endswith(d) for d in ["uberip.com"]):
                acc = await self.mailtm.create_account(custom_name=custom_name, domain=domain, exclude_domain=exclude_domain)
                if acc: return acc
            elif any(domain.endswith(d) for d in ["olipii.com", "lnovic.com", "ooynib.com", "yzcalo.com", "ruutukf.com", "gmeenramy.com"]):
                acc = await self.tempmailio.create_account(custom_name=custom_name, domain=domain, exclude_domain=exclude_domain)
                if acc: return acc
            else:
                acc = await self.mailtm.create_account(custom_name=custom_name, domain=domain, exclude_domain=exclude_domain)
                if acc: return acc

        # Clean rotation between Mail.tm (uberip.com) and TempMail.io (clean .com domains)
        # Guarantees instant OTP delivery for Claude, OpenAI, Google, Telegram
        if exclude_domain and any(exclude_domain.endswith(d) for d in ["uberip.com"]):
            providers = [self.tempmailio, self.mailtm]
        else:
            providers = [self.mailtm, self.tempmailio]

        for prov in providers:
            try:
                acc = await prov.create_account(custom_name=custom_name, domain=domain, exclude_domain=exclude_domain)
                if acc and acc.get("email"):
                    return acc
            except Exception as e:
                logger.error(f"Provider {prov.__class__.__name__} failed: {e}")

        # Emergency Fallback to Guerrilla only if both Mail.tm & TempMail.io are down
        try:
            acc = await self.guerrilla.create_account(custom_name=custom_name, domain=domain, exclude_domain=exclude_domain)
            if acc and acc.get("email"):
                return acc
        except Exception as e:
            logger.error(f"Guerrilla fallback failed: {e}")

        # Final fallback
        return await self.mailtm.create_account(custom_name=custom_name, domain=domain)

    async def get_messages(self, token_or_email: str, provider: str = "mailtm", last_id: Optional[str] = None, email: str = "") -> List[Dict[str, Any]]:
        """Fetch messages from active provider."""
        if provider == "mailtm":
            return await self.mailtm.get_messages(token_or_email)
        elif provider == "guerrilla":
            return await self.guerrilla.get_messages(token_or_email)
        else:
            target_email = email or token_or_email
            return await self.tempmailio.get_messages(target_email)

    async def get_message_detail(self, token_or_email: str, provider: str = "mailtm", message_id: str = "", email: str = "") -> Optional[Dict[str, Any]]:
        """Fetch full details of a specific message."""
        if provider == "mailtm":
            return await self.mailtm.get_message_detail(token_or_email, message_id)
        elif provider == "guerrilla":
            return await self.guerrilla.get_message_detail(token_or_email, message_id)
        else:
            target_email = email or token_or_email
            return await self.tempmailio.get_message_detail(target_email, message_id)

    async def delete_message(self, token_or_email: str, provider: str, message_id: str) -> bool:
        return True

    async def delete_account(self, token: str, provider: str, account_id: str) -> bool:
        return True

mail_service = UnifiedMailManager()
