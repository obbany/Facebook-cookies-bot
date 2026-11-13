# 🔥 Facebook Cookie Bot

Facebook session-cookie generator Telegram bot with license system, admin panel, single & batch cookie modes.

⚡ Power by Robbany ⚡

---

## ✨ Features

| Feature | What it does |
|---|---|
| 🍪 **Single Cookies** | One account (UID / phone / email + password) → session cookies, tap-to-copy |
| 📋 **All Cookies** | Many accounts + one common password → live progress → `.txt` file |
| 🎟️ **License System** | Every new user auto-gets a random 8-digit license key. Admin approves → full access |
| 👑 **Admin Panel** | Approve license, ban/unban users, pending list, all users, broadcast, live stats |
| 📱💻 | Runs on **Android (Termux/Pydroid)** AND **PC/VPS** |

---

## ⚙️ Setup (ONE TIME)

### 1. Edit the config at the top of `fb_bot.py`:

```python
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"      # from @BotFather
ADMIN_IDS = [YOUR_TELEGRAM_USER_ID]    # your numeric Telegram ID
```

> 🆔 Don't know your ID? Open [@userinfobot](https://t.me/userinfobot) on Telegram → it shows your ID.

### 2. Install & Run

---

## 📱 Run on Android (Termux) — RECOMMENDED

> Facebook blocks datacenter IPs — mobile internet works 100%.

```bash
pkg update -y && pkg install python git -y
pip install requests
git clone https://github.com/obbany/Facebook-cookies-bot.git
cd Facebook-cookies-bot
nano fb_bot.py          # edit BOT_TOKEN + ADMIN_IDS (save: Ctrl+X → Y → Enter)
python3 fb_bot.py
```

Keep Termux open — the bot runs. To stop: `Ctrl+C`.

### 📌 Keep-alive (Termux)
Turn off battery optimization for Termux + in Termux settings enable *Acquire wakelock* (`termux-wake-lock`).

---

## 💻 Run on PC / VPS

```bash
git clone https://github.com/obbany/Facebook-cookies-bot.git
cd Facebook-cookies-bot
pip install requests
# edit fb_bot.py → BOT_TOKEN + ADMIN_IDS
python3 fb_bot.py
```

Run in background (Linux VPS):

```bash
nohup python3 fb_bot.py > bot.log 2>&1 &
```

> ⚠️ Datacenter/VPS IPs are often **blocked by Facebook for login**. If you see
> `Server IP blocked by Facebook`, run the bot from mobile internet instead.

---

## 🚀 How Users Use It

1. `/start` → bot shows their **8-digit license key** (auto-generated)
2. Tap the key → copies → send to **Admin**
3. Admin: 👑 Admin Panel → ✅ Approve License → paste the key
4. User gets notified 🎉 → all features unlock

**🍪 Single Cookies:** send UID/number/email → password → cookie arrives (tap to copy)
**📋 All Cookies:** send many IDs (one per line) → one common password → live progress → `.txt` file

---

## 🗄️ Database

`fbbot.db` (SQLite) is auto-created — stores users, licenses, cookies, stats.

---

## 📄 License

Personal project by **Robbany**.
