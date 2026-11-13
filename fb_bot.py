#!/usr/bin/env python3
"""
🤖 FB COOKIE BOT v4 — Premium Edition
⚡ Power by Robbany ⚡

Runs on mobile (Termux/Pydroid) AND desktop (PC/VPS).
Needs: pip install requests
Run:   python3 fb_bot.py
"""
import html
import json
import os
import queue
import random
import sqlite3
import threading
import time
import urllib.parse
import urllib.request

import requests

# ================= CONFIG =================
BOT_TOKEN = "PASTE_YOUR_BOT_TOKEN_HERE"
ADMIN_IDS = [5858681713]          # Robbany
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fbbot.db")

MOBILE_UA = ("Mozilla/5.0 (Linux; Android 13; SM-A125F) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36")

BRAND = "⚡ Power by Robbany ⚡"
LINE = "━━━━━━━━━━━━━━━━━━━━━━"
# ==========================================

user_states = {}
user_temp_data = {}
task_queue = queue.Queue()
batch_queue = queue.Queue()
_db_lock = threading.Lock()


# ---------------- DATABASE ----------------
def db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _db_lock:
        c = db()
        cols = [r[1] for r in c.execute("PRAGMA table_info(users)")]
        if "status" not in cols:
            c.execute("ALTER TABLE users ADD COLUMN status TEXT DEFAULT 'pending'")
            if "approved" in cols:
                c.execute("UPDATE users SET status='approved' WHERE approved=1")
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users(
            tg_id INTEGER PRIMARY KEY, username TEXT, joined_at TEXT,
            license TEXT, status TEXT DEFAULT 'pending',
            total_cookies INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS cookies(
            id INTEGER PRIMARY KEY AUTOINCREMENT, tg_id INTEGER,
            account TEXT, cookie TEXT, created_at TEXT
        );
        """)
        c.execute("UPDATE users SET status='pending' WHERE status IS NULL")
        for r in c.execute("SELECT tg_id FROM users WHERE license IS NULL").fetchall():
            c.execute("UPDATE users SET license=? WHERE tg_id=?",
                      (str(random.randint(10000000, 99999999)), r["tg_id"]))
        c.commit(); c.close()


def upsert_user(uid, uname):
    """Every new user automatically gets a random 8-digit license key."""
    with _db_lock:
        c = db()
        r = c.execute("SELECT tg_id, license FROM users WHERE tg_id=?", (uid,)).fetchone()
        if not r:
            lic = str(random.randint(10000000, 99999999))
            c.execute("""INSERT INTO users(tg_id, username, joined_at, license, status)
                         VALUES(?,?,datetime('now'),?, 'pending')""", (uid, uname, lic))
            c.commit(); c.close()
            return lic
        if r["license"] is None:
            lic = str(random.randint(10000000, 99999999))
            c.execute("UPDATE users SET license=? WHERE tg_id=?", (lic, uid))
            c.commit()
        else:
            lic = r["license"]
        c.execute("UPDATE users SET username=? WHERE tg_id=?", (uname, uid))
        c.commit(); c.close()
        return lic


def get_user(uid):
    with _db_lock:
        c = db()
        r = c.execute("SELECT * FROM users WHERE tg_id=?", (uid,)).fetchone()
        c.close()
    return dict(r) if r else None


def is_approved(uid):
    if uid in ADMIN_IDS:
        return True
    u = get_user(uid)
    return bool(u and u.get("status") == "approved")


def is_banned(uid):
    u = get_user(uid)
    return bool(u and u.get("status") == "banned")


def set_status(uid, status):
    with _db_lock:
        c = db()
        c.execute("UPDATE users SET status=? WHERE tg_id=?", (status, uid))
        c.commit(); c.close()


def all_users():
    with _db_lock:
        c = db()
        rows = c.execute("SELECT * FROM users ORDER BY joined_at DESC").fetchall()
        c.close()
    return [dict(r) for r in rows]


def save_cookie(uid, account, cookie):
    with _db_lock:
        c = db()
        c.execute("INSERT INTO cookies(tg_id, account, cookie, created_at) VALUES(?,?,?,datetime('now'))",
                  (uid, account, cookie))
        c.execute("UPDATE users SET total_cookies = total_cookies+1 WHERE tg_id=?", (uid,))
        c.commit(); c.close()


def stats():
    with _db_lock:
        c = db()
        g = lambda q: c.execute(q).fetchone()["n"]
        u = g("SELECT COUNT(*) n FROM users")
        a = g("SELECT COUNT(*) n FROM users WHERE status='approved'")
        p = g("SELECT COUNT(*) n FROM users WHERE status='pending'")
        b = g("SELECT COUNT(*) n FROM users WHERE status='banned'")
        ck = g("SELECT COUNT(*) n FROM cookies")
        c.close()
    return u, a, p, b, ck


# ---------------- TELEGRAM API (HTML parse mode — never crashes on user text) ----------------
class Bot:
    def __init__(self, token):
        self.base = f"https://api.telegram.org/bot{token}"
        self.offset = 0

    def call(self, method, data=None):
        try:
            body = urllib.parse.urlencode(data or {}).encode()
            req = urllib.request.Request(f"{self.base}/{method}", data=body, method="POST")
            req.add_header("Content-Type", "application/x-www-form-urlencoded")
            with urllib.request.urlopen(req, timeout=35) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            print(f"API {method}: {e}")
            return None

    def send(self, chat_id, text, kb=None):
        d = {"chat_id": chat_id, "text": text[:4090], "parse_mode": "HTML",
             "disable_web_page_preview": True}
        if kb: d["reply_markup"] = json.dumps(kb)
        return self.call("sendMessage", d)

    def edit(self, chat_id, mid, text):
        d = {"chat_id": chat_id, "message_id": mid, "text": text[:4090],
             "parse_mode": "HTML", "disable_web_page_preview": True}
        return self.call("editMessageText", d)

    def send_file(self, chat_id, path, caption=""):
        try:
            with open(path, "rb") as f:
                files = {"document": (os.path.basename(path), f)}
                data = {"chat_id": str(chat_id)}
                if caption:
                    data["caption"] = caption[:1000]
                return requests.post(f"{self.base}/sendDocument", data=data,
                                     files=files, timeout=120).json()
        except Exception as e:
            print("sendFile:", e)
            return None

    def updates(self):
        r = self.call("getUpdates", {"offset": self.offset, "timeout": 30})
        if r and r.get("ok"):
            ups = r.get("result", [])
            if ups:
                self.offset = ups[-1]["update_id"] + 1
            return ups
        return []


# ---------------- KEYBOARDS ----------------
def kb_main(admin=False):
    rows = [["🍪 Single Cookies", "📋 All Cookies"],
            ["🎟️ My License", "📊 My Info"],
            ["🆘 Help"]]
    if admin:
        rows.append(["👑 Admin Panel"])
    return {"keyboard": rows, "resize_keyboard": True}


def kb_admin_panel():
    return {"keyboard": [["✅ Approve License", "👥 Pending List"],
                         ["🚫 Ban User", "✅ Unban User"],
                         ["👥 All Users", "📊 Stats"],
                         ["📣 Broadcast"],
                         ["🏠 Main Menu"]],
            "resize_keyboard": True}


def kb_back():
    return {"keyboard": [["🏠 Main Menu"]], "resize_keyboard": True}


def kb_work():
    return {"keyboard": [["🏠 Main Menu"], ["🔄 New Task"]], "resize_keyboard": True}


def esc(s):
    return html.escape(str(s or ""))


# ---------------- FB LOGIN ----------------
def fb_login(email, password):
    s = requests.Session()
    s.headers.update({"User-Agent": MOBILE_UA, "Accept-Language": "en-US,en;q=0.9"})
    s.get("https://www.facebook.com/login/", timeout=30)
    r = s.post("https://www.facebook.com/login/device-based/regular/login/?login_source=login",
               data={"email": email, "pass": password, "login": "Log In", "persistent": "1"},
               timeout=30, allow_redirects=True)
    ck = s.cookies.get_dict()
    if "c_user" in ck and "xs" in ck:
        return s, None
    url = r.url.lower()
    if "two_factor" in url:
        return s, "2FA is ON — turn it off first."
    if "checkpoint" in url:
        return s, 'Checkpoint — approve "It was me" from your phone, then retry.'
    if r.status_code == 400:
        return s, "Server IP blocked by Facebook (run from Termux/mobile — works 100% there)"
    return s, "Login failed — try again."


def verify_session(s):
    try:
        r = s.get("https://mbasic.facebook.com/home.php", timeout=30)
        return "logout" in r.text.lower() or "news feed" in r.text.lower()
    except Exception:
        return False


def cookie_str(s):
    return "; ".join(f"{k}={v}" for k, v in s.cookies.get_dict().items())


# ---------------- SINGLE WORKER ----------------
def do_single(bot, chat_id, uid, account, password, mid):
    t0 = time.time()
    try:
        bot.edit(chat_id, mid, f"""🔐 <b>GENERATING COOKIE</b>
{LINE}
📡 Step 1/3 • Connecting...
👤 <code>{esc(account)}</code>
{LINE}
{BRAND}""")
        s, err = fb_login(account, password)
        if err:
            raise Exception(err)

        bot.edit(chat_id, mid, f"""🔐 <b>GENERATING COOKIE</b>
{LINE}
🍪 Step 2/3 • Extracting session...
📦 Collecting cookies...
{LINE}
{BRAND}""")
        ck = cookie_str(s)
        if "c_user" not in ck:
            raise Exception("Incomplete cookies — checkpoint possible.")
        ok = verify_session(s)
        save_cookie(uid, account, ck)
        el = time.time() - t0

        bot.edit(chat_id, mid, f"""✅ <b>COOKIE GENERATED!</b> ⏱ {el:.1f}s {'✅' if ok else ''}
{LINE}
👤 <b>Account:</b> <code>{esc(account)}</code>

🍪 <b>Cookies — tap to copy:</b>

<code>{esc(ck)}</code>
{LINE}
💡 Cookie keeps you logged in without password.
🚫 Never share it with anyone!
{LINE}
{BRAND}""", kb_work())
    except Exception as e:
        el = time.time() - t0
        bot.edit(chat_id, mid, f"""❌ <b>FAILED</b> ⏱ {el:.1f}s
{LINE}
👤 <code>{esc(account)}</code>
🐛 {esc(str(e)[:180])}
{LINE}
💡 Tap 🔄 New Task to retry!
{LINE}
{BRAND}""", kb_work())


def single_worker(bot):
    while True:
        try:
            job = task_queue.get(timeout=1)
            if job:
                do_single(bot, **job)
            task_queue.task_done()
        except queue.Empty:
            time.sleep(0.1)
        except Exception as e:
            print("singleWorker:", e)


# ---------------- BATCH WORKER ----------------
def batch_worker(bot):
    while True:
        try:
            job = batch_queue.get(timeout=1)
            if not job:
                continue
            chat_id, uid, ids, password = job["chat_id"], job["uid"], job["ids"], job["password"]
            mid = job["mid"]
            total = len(ids)
            done = failed = 0
            results = []

            bot.edit(chat_id, mid, f"""📋 <b>BATCH PROCESSOR</b>
{LINE}
📊 Total accounts: <b>{total}</b>
🔄 Starting...
{LINE}
{BRAND}""")

            for i, acc in enumerate(ids, 1):
                try:
                    s, err = fb_login(acc, password)
                    if err:
                        failed += 1
                        results.append((acc, None, err))
                    else:
                        ck = cookie_str(s)
                        if "c_user" not in ck:
                            failed += 1
                            results.append((acc, None, "Incomplete cookies"))
                        else:
                            done += 1
                            results.append((acc, ck, None))
                            save_cookie(uid, acc, ck)
                except Exception as e:
                    failed += 1
                    results.append((acc, None, str(e)[:80]))

                if i % 2 == 0 or i == total:
                    try:
                        bot.edit(chat_id, mid, f"""📋 <b>BATCH — LIVE 🔄</b>
{LINE}
⏳ Progress: {i}/{total}
✅ Success: {done}
❌ Failed: {failed}
📊 Remaining: {total - i}
{LINE}
{BRAND}""")
                    except Exception:
                        pass

            fname = f"cookies_{uid}_{int(time.time())}.txt"
            fpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), fname)
            with open(fpath, "w", encoding="utf-8") as f:
                f.write("=" * 40 + "\n")
                f.write("  FACEBOOK COOKIES — BATCH RESULT\n")
                f.write(f"  Success: {done}/{total}  |  {time.strftime('%Y-%m-%d %H:%M')}\n")
                f.write("=" * 40 + "\n\n")
                for acc, ck, err in results:
                    if ck:
                        f.write(f"ACCOUNT : {acc}\nCOOKIE  : {ck}\n" + "-" * 40 + "\n\n")
                    else:
                        f.write(f"ACCOUNT : {acc}\nERROR   : {err}\n" + "-" * 40 + "\n\n")

            bot.edit(chat_id, mid, f"""🎉 <b>BATCH COMPLETE!</b>
{LINE}
📊 Total: {total}
✅ Success: <b>{done}</b>
❌ Failed: <b>{failed}</b>
{LINE}
📄 Your file is sending... 👇
{LINE}
{BRAND}""")
            bot.send_file(chat_id, fpath, f"🍪 Cookies: {done}/{total} success | {BRAND}")
            try:
                os.remove(fpath)
            except Exception:
                pass
            batch_queue.task_done()
        except queue.Empty:
            time.sleep(0.1)
        except Exception as e:
            print("batchWorker:", e)


# ---------------- MENUS ----------------
def main_menu(bot, chat_id, uid, first_name=""):
    admin = uid in ADMIN_IDS
    u = get_user(uid) or {}
    kb = kb_main(admin)
    lic = u.get("license") or "—"
    status = u.get("status") or "pending"

    if admin:
        bot.send(chat_id, f"""🔥 <b>FACEBOOK COOKIE BOT</b> 🔥
{LINE}
👋 Welcome back, <b>Admin {esc(first_name)}</b>!
🔓 All features unlocked.
{LINE}
{BRAND}""", kb)
    elif status == "approved":
        bot.send(chat_id, f"""🔥 <b>FACEBOOK COOKIE BOT</b> 🔥
{LINE}
👋 Welcome, <b>{esc(first_name)}</b>!
🎟️ License: ✅ <b>ACTIVE</b>
{LINE}
{BRAND}""", kb)
    elif status == "banned":
        bot.send(chat_id, f"""🔥 <b>FACEBOOK COOKIE BOT</b> 🔥
{LINE}
🚫 <b>You are BANNED</b>
Contact admin if you think this is a mistake.
{LINE}
{BRAND}""", kb)
    else:
        bot.send(chat_id, f"""🔥 <b>FACEBOOK COOKIE BOT</b> 🔥
{LINE}
👋 Welcome, <b>{esc(first_name)}</b>!

🎟️ <b>Your License Key:</b>
━━━━━━━━━━━━━━━━━━
   🔢  <b><code>{esc(lic)}</code></b>  🔢
━━━━━━━━━━━━━━━━━━
👆 Tap to copy, then send it to Admin.
⏳ After admin approval, all features unlock!
{LINE}
{BRAND}""", kb)


# ---------------- HANDLE ----------------
def handle(bot, update):
    msg = update.get("message")
    if not msg:
        return
    chat_id = msg["chat"]["id"]
    uid = msg["from"]["id"]
    uname = msg["from"].get("username") or msg["from"].get("first_name", "User")
    text = msg.get("text", "").strip()
    admin = uid in ADMIN_IDS

    upsert_user(uid, uname)

    if is_banned(uid) and not admin:
        bot.send(chat_id, f"🚫 <b>Banned</b> — contact admin.\n\n{BRAND}")
        return

    state = user_states.get(uid, "")

    if text in ("🏠 Main Menu", "🔄 New Task", "/start"):
        user_states.pop(uid, None)
        user_temp_data.pop(uid, None)
        main_menu(bot, chat_id, uid, uname)
        return

    # ---------- LICENSE ----------
    if text == "🎟️ My License":
        u = get_user(uid) or {}
        lic = u.get("license") or "—"
        st = u.get("status") or "pending"
        sts = {"pending": "⏳ PENDING — waiting for admin approval",
               "approved": "✅ ACTIVE — all features unlocked!",
               "banned": "🚫 BANNED"}.get(st, st)
        bot.send(chat_id, f"""🎟️ <b>YOUR LICENSE</b>
{LINE}
🔢 License Key:
━━━━━━━━━━━━━━━━━━
   <b><code>{esc(lic)}</code></b>
━━━━━━━━━━━━━━━━━━
👆 Tap to copy

📊 Status: {sts}
{LINE}
{BRAND}""", kb_back())
        return

    # ---------- SINGLE COOKIE ----------
    if text == "🍪 Single Cookies":
        if not is_approved(uid):
            bot.send(chat_id, f"""🔒 <b>LICENSE REQUIRED</b>
{LINE}
This feature needs an approved license.

🎟️ Tap <b>My License</b> → copy your key
→ send it to Admin!
{LINE}
{BRAND}""", kb_back())
            return
        user_states[uid] = "S_ACC"
        bot.send(chat_id, f"""🍪 <b>SINGLE COOKIE</b>
{LINE}
📱 Send your Facebook login:

🆔 UID • 📱 Number • 📧 Email

💡 Any ONE of them works!
{LINE}
{BRAND}""", kb_back())
        return

    if state == "S_ACC":
        user_temp_data[uid] = {"acc": text}
        user_states[uid] = "S_PASS"
        bot.send(chat_id, f"""🔑 <b>STEP 2/2 — PASSWORD</b>
{LINE}
👤 <code>{esc(text)}</code>

🔐 Now send the password:
{LINE}
{BRAND}""", kb_back())
        return

    if state == "S_PASS":
        acc = user_temp_data.pop(uid, {}).get("acc", "")
        user_states.pop(uid, None)
        if not acc or not text:
            bot.send(chat_id, f"❌ Error — start again: 🍪 Single Cookies\n\n{BRAND}", kb_back())
            return
        m = bot.send(chat_id, f"""🔐 <b>GENERATING COOKIE</b>
{LINE}
⏳ Task started...
👤 <code>{esc(acc)}</code>
{LINE}
{BRAND}""")
        mid = (m or {}).get("result", {}).get("message_id")
        task_queue.put({"chat_id": chat_id, "uid": uid, "account": acc,
                        "password": text, "mid": mid})
        return

    # ---------- ALL COOKIES ----------
    if text == "📋 All Cookies":
        if not is_approved(uid):
            bot.send(chat_id, f"""🔒 <b>LICENSE REQUIRED</b>
{LINE}
This feature needs an approved license.

🎟️ Tap <b>My License</b> → send key to Admin!
{LINE}
{BRAND}""", kb_back())
            return
        user_states[uid] = "B_IDS"
        bot.send(chat_id, f"""📋 <b>BATCH MODE</b>
{LINE}
🆔 <b>Step 1/2 — Send all account IDs</b>

One per line — unlimited!
(UID / Number / Email — any mix)

📌 Example:
<code>1000123456789
8801712345678
user@gmail.com</code>
{LINE}
{BRAND}""", kb_back())
        return

    if state == "B_IDS":
        ids = [l.strip() for l in text.splitlines() if l.strip()]
        if not ids:
            bot.send(chat_id, f"❌ Send at least ONE account ID!\n\n{BRAND}", kb_back())
            return
        user_temp_data[uid] = {"ids": ids}
        user_states[uid] = "B_PASS"
        bot.send(chat_id, f"""🔑 <b>STEP 2/2 — COMMON PASSWORD</b>
{LINE}
📊 Accounts loaded: <b>{len(ids)}</b>

🔐 All accounts must share the SAME password.
Send it now:
{LINE}
{BRAND}""", kb_back())
        return

    if state == "B_PASS":
        data = user_temp_data.pop(uid, {})
        user_states.pop(uid, None)
        ids = data.get("ids", [])
        if not ids or not text:
            bot.send(chat_id, f"❌ Error — start again: 📋 All Cookies\n\n{BRAND}", kb_back())
            return
        m = bot.send(chat_id, f"""📋 <b>BATCH PROCESSOR</b>
{LINE}
📊 Total: <b>{len(ids)}</b> accounts
⏳ Starting... live progress below 👇
{LINE}
{BRAND}""")
        mid = (m or {}).get("result", {}).get("message_id")
        batch_queue.put({"chat_id": chat_id, "uid": uid, "ids": ids,
                         "password": text, "mid": mid})
        return

    # ---------- INFO / HELP ----------
    if text == "📊 My Info":
        u = get_user(uid) or {}
        lic = u.get("license") or "—"
        st = u.get("status") or "pending"
        ck = u.get("total_cookies", 0)
        sts = {"pending": "⏳ Pending", "approved": "✅ Active", "banned": "🚫 Banned"}.get(st, st)
        bot.send(chat_id, f"""📊 <b>MY PROFILE</b>
{LINE}
🆔 ID: <code>{uid}</code>
🎟️ License: <code>{esc(lic)}</code>
🔑 Status: {sts}
🍪 Cookies generated: <b>{ck}</b>
{LINE}
{BRAND}""", kb_back())
        return

    if text == "🆘 Help":
        bot.send(chat_id, f"""🆘 <b>HOW TO USE</b>
{LINE}
1️⃣ Tap 🎟️ <b>My License</b> → copy your key
2️⃣ Send it to Admin → get approved ✅

🍪 <b>Single Cookies</b> — one account → cookie
📋 <b>All Cookies</b> — many accounts → .txt file

⚠️ Checkpoint? Approve "It was me" on your phone.
{LINE}
{BRAND}""", kb_back())
        return

    # ---------- ADMIN ----------
    if admin and text == "👑 Admin Panel":
        u, a, p, b, ck = stats()
        bot.send(chat_id, f"""👑 <b>ADMIN PANEL</b>
{LINE}
👥 Users: <b>{u}</b>  |  ✅ Approved: <b>{a}</b>
⏳ Pending: <b>{p}</b>  |  🚫 Banned: <b>{b}</b>
🍪 Cookies: <b>{ck}</b>
{LINE}
{BRAND}""", kb_admin_panel())
        return

    if admin and text == "✅ Approve License":
        user_states[uid] = "A_APPROVE"
        bot.send(chat_id, f"""✅ <b>APPROVE LICENSE</b>
{LINE}
🔢 Send the user's <b>8-digit license key</b>:

💡 Check 👥 Pending List first!
{LINE}
{BRAND}""", kb_admin_panel())
        return

    if state == "A_APPROVE" and admin:
        user_states.pop(uid, None)
        lic = text.strip()
        found = next((u for u in all_users() if (u.get("license") or "") == lic), None)
        if not found:
            bot.send(chat_id, f"❌ License <code>{esc(lic)}</code> not found!\n\n{BRAND}", kb_admin_panel())
            return
        set_status(found["tg_id"], "approved")
        bot.send(chat_id, f"""🎉 <b>APPROVED!</b>
{LINE}
🎟️ License: <code>{esc(lic)}</code>
👤 User: <code>{found['tg_id']}</code> (@{esc(found.get('username') or 'N/A')})
🔓 All features unlocked!
{LINE}
{BRAND}""", kb_admin_panel())
        bot.send(found["tg_id"], f"""🎉 <b>LICENSE APPROVED!</b>
{LINE}
✅ Your license <code>{esc(lic)}</code> is now ACTIVE!
🔓 All features unlocked — start now! 🚀
{LINE}
{BRAND}""")
        return

    if admin and text == "🚫 Ban User":
        user_states[uid] = "A_BAN"
        bot.send(chat_id, f"""🚫 <b>BAN USER</b>
{LINE}
🆔 Send the user's <b>Telegram ID</b>:
{LINE}
{BRAND}""", kb_admin_panel())
        return

    if state == "A_BAN" and admin:
        user_states.pop(uid, None)
        try:
            target = int(text.strip())
            if target in ADMIN_IDS:
                bot.send(chat_id, f"😅 You can't ban yourself, Boss!\n\n{BRAND}", kb_admin_panel())
                return
            set_status(target, "banned")
            bot.send(chat_id, f"🚫 User <code>{target}</code> is now BANNED.\n\n{BRAND}", kb_admin_panel())
            bot.send(target, f"🚫 <b>You are banned!</b>\nContact admin.\n\n{BRAND}")
        except Exception:
            bot.send(chat_id, f"❌ Send a valid Telegram ID.\n\n{BRAND}", kb_admin_panel())
        return

    if admin and text == "✅ Unban User":
        user_states[uid] = "A_UNBAN"
        bot.send(chat_id, f"""✅ <b>UNBAN USER</b>
{LINE}
🆔 Send the banned user's <b>Telegram ID</b>:
{LINE}
{BRAND}""", kb_admin_panel())
        return

    if state == "A_UNBAN" and admin:
        user_states.pop(uid, None)
        try:
            target = int(text.strip())
            set_status(target, "pending")
            bot.send(chat_id, f"✅ User <code>{target}</code> unbanned → pending.\n\n{BRAND}", kb_admin_panel())
            bot.send(target, f"🎉 <b>You are unbanned!</b>\nAsk admin to approve your license.\n\n{BRAND}")
        except Exception:
            bot.send(chat_id, f"❌ Send a valid Telegram ID.\n\n{BRAND}", kb_admin_panel())
        return

    if admin and text == "👥 Pending List":
        rows = [u for u in all_users() if (u.get("status") or "pending") == "pending"]
        if not rows:
            bot.send(chat_id, f"⏳ No pending users right now.\n\n{BRAND}", kb_admin_panel())
            return
        lines = "\n".join(
            f"🔢 <code>{esc(u.get('license') or '—')}</code> → 🆔 <code>{u['tg_id']}</code> @{esc(u.get('username') or 'N/A')}"
            for u in rows[:30])
        bot.send(chat_id, f"""⏳ <b>PENDING USERS ({len(rows)})</b>
{LINE}
{lines}
{LINE}
💡 Copy a key → ✅ Approve License
{LINE}
{BRAND}""", kb_admin_panel())
        return

    if admin and text == "👥 All Users":
        rows = all_users()
        icon = lambda s: "✅" if s == "approved" else "⏳" if s == "pending" else "🚫"
        lines = "\n".join(
            f"{icon(u.get('status') or 'pending')} <code>{u['tg_id']}</code> @{esc(u.get('username') or 'N/A')} 🍪{u.get('total_cookies', 0)}"
            for u in rows[:40]) or "No users yet"
        bot.send(chat_id, f"""👥 <b>ALL USERS ({len(rows)})</b>
{LINE}
{lines}
{LINE}
{BRAND}""", kb_admin_panel())
        return

    if admin and text == "📣 Broadcast":
        user_states[uid] = "A_BCAST"
        bot.send(chat_id, f"""📣 <b>BROADCAST</b>
{LINE}
✍️ Write the message for ALL users:
{LINE}
{BRAND}""", kb_admin_panel())
        return

    if state == "A_BCAST" and admin:
        user_states.pop(uid, None)
        sent = 0
        for u in all_users():
            if bot.send(u["tg_id"], f"📣 <b>NOTICE</b>\n{LINE}\n{esc(text)}\n{LINE}\n{BRAND}"):
                sent += 1
            time.sleep(0.05)
        bot.send(chat_id, f"📣 Delivered to <b>{sent}</b> users.\n\n{BRAND}", kb_admin_panel())
        return

    if admin and text == "📊 Stats":
        u, a, p, b, ck = stats()
        bot.send(chat_id, f"""📊 <b>LIVE STATS</b>
{LINE}
👥 Users: <b>{u}</b>
✅ Approved: <b>{a}</b>
⏳ Pending: <b>{p}</b>
🚫 Banned: <b>{b}</b>
🍪 Cookies: <b>{ck}</b>
{LINE}
{BRAND}""", kb_admin_panel())
        return

    if admin:
        bot.send(chat_id, "🤔 Pick from the menu below 👇", kb_main(True))


# ---------------- MAIN ----------------
def main():
    print("=" * 50)
    print("🤖 FB COOKIE BOT v4 — Premium")
    print("=" * 50)
    init_db()
    bot = Bot(BOT_TOKEN)
    me = bot.call("getMe") or {}
    print("✅ Bot:", me.get("result", {}).get("username"))
    bot.call("setMyCommands", {"commands": json.dumps([{"command": "start", "description": "🏠 Start"}])})
    threading.Thread(target=single_worker, args=(bot,), daemon=True).start()
    threading.Thread(target=batch_worker, args=(bot,), daemon=True).start()
    print("🧵 Workers ready")
    print("✅ LIVE!")
    while True:
        try:
            ups = bot.updates()
            for u in ups:
                try:
                    handle(bot, u)
                except Exception as e:
                    print("Handle:", e)
            if not ups:
                time.sleep(0.4)
        except KeyboardInterrupt:
            print("👋 Stopped!")
            break
        except Exception as e:
            print("Loop:", e); time.sleep(2)


if __name__ == "__main__":
    main()
