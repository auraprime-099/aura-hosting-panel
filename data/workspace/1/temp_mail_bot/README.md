# 📧 Temp Mail & Auto OTP Telegram Bot

Ek high-speed Telegram Bot jo users ko **Temporary Disposable Emails** provide karta hai aur kisi bhi website/app se aane wale **OTPs**, **Verification Codes**, aur **Verification Links** ko automatically detect karke real-time me Telegram par deliver karta hai.

---

## ✨ Main Features

1. ⚡ **Instant Temp Mail Generation**:
   - `/new` command ya button se single-click me disposable email generate hota hai.
   - Click-to-copy code block format.

2. 🌐 **Website / Service Name Identifier**:
   - Email bhejne wali company ya website ka naam (e.g. *Instagram, Google, Netflix, Discord, Twitter/X*) alag se show karta hai.

3. 🔢 **Smart OTP & Verification Code Extraction**:
   - Subject aur body se OTP codes (4-8 digits, Google codes jaise `G-123456`) scan karke alag se **Bold highlight** karta hai, jise single tap se copy kiya ja sakta hai.

4. 🔗 **Verification Link Detector**:
   - Agar email me activation/verification link (`Confirm Email`, `Verify Account`, etc.) hai, toh bot message me direct clickable link aur inline URL button deta hai.

5. 🔄 **Auto Inbox Watcher (Real-time)**:
   - Background me active inboxes ko har 3-4 seconds me check karta hai.
   - User ko baar-baar refresh dabane ki zaroorat nahi padti.

6. 📖 **Full Email Reader**:
   - `View Full Mail` button se email ki poori details (Sender, Subject, Time, Full Text) padh sakte hain.

7. 🗑️ **Delete & Clean**:
   - Individual emails ya poora temp account single tap me delete ho jata hai.

---

## 🚀 Setup & Run Instructions

### 1. Requirements Install Karein
```bash
pip install -r requirements.txt
```

### 2. `.env` File Configure Karein
`temp_mail_bot` folder me `.env` file banayein aur apna bot token dalein:
```env
BOT_TOKEN=your_telegram_bot_token_here
POLL_INTERVAL=4
```

### 3. Bot Run Karein
```bash
python bot.py
```

---

## 📱 Bot Commands

| Command | Action |
|---|---|
| `/start` | Bot start karein aur main menu dekhein |
| `/new` | Naya temporary email banayein |
| `/inbox` | Apne inbox ke messages check karein |
| `/delete` | Current temporary email delete karein |
| `/help` | Bot ke use karne ka guide |
