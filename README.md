# 🤖 Telegram Channel Keyword Editor Bot

A production-ready, fully asynchronous Telegram bot that automatically detects
configured keywords in a monitored channel and replaces them — all in real time,
without any manual intervention.

```
/nkey keywords          /rkey ONE global replacement
──────────────          ──────────────────────────
@user                           ↓
@oldchannel      →    replaces every match with    →   @hii
oldsite.com
#oldtag
```

---

## Features

| Feature | Details |
|---|---|
| Multiple keywords | Unlimited detection keywords via `/nkey` |
| One replacement | Single global phrase via `/rkey` |
| All Telegram media | Edits text, photo/video/document/audio/GIF captions |
| Formatting preserved | Bold, italic, URLs, mentions, custom emoji survive |
| Case sensitivity | Configurable (default: case-insensitive) |
| In-memory cache | Keywords loaded once; no DB hit per message |
| Owner + Admin system | Hierarchical access; MongoDB-backed |
| Conversation states | Per-user, 5-min TTL, fully isolated |
| Statistics | Messages processed / edited / keywords detected |
| Persistent settings | Survives restarts — everything stored in MongoDB |
| Deployable anywhere | Koyeb, Render, Linux, Termux, Docker |

---

## Prerequisites

| Requirement | How to get it |
|---|---|
| **Python 3.11+** | https://python.org |
| **Telegram Bot Token** | Talk to [@BotFather](https://t.me/BotFather) |
| **API ID + API Hash** | https://my.telegram.org |
| **MongoDB** | [Atlas free tier](https://cloud.mongodb.com) or self-hosted |
| **Your Telegram user ID** | Message [@userinfobot](https://t.me/userinfobot) |

### Bot Telegram permissions required

Add the bot as a **channel administrator** with the following permissions:

- ✅ **Edit Messages**
- ✅ **Delete Messages** *(optional)*
- ✅ Post Messages is **not** required — the bot only edits existing posts.

---

## Quick Start (Local)

```bash
# 1. Clone
git clone <your-repo>
cd telegram-keyword-editor

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure
cp .env.example .env
# Edit .env and fill in all required variables

# 5. Run
python bot.py
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `BOT_TOKEN` | ✅ | Bot token from @BotFather |
| `API_ID` | ✅ | Telegram API ID from my.telegram.org |
| `API_HASH` | ✅ | Telegram API hash from my.telegram.org |
| `MONGO_URI` | ✅ | Full MongoDB connection URI |
| `OWNER_ID` | ✅ | Your numeric Telegram user ID |
| `ECHANNEL_ID` | Optional | Channel to monitor (can be set via `/channel`) |
| `LOG_CHANNEL_ID` | Optional | Channel for bot event logs |

---

## Bot Commands

### Admin Commands

| Command | Description |
|---|---|
| `/start` | Show welcome message and command list |
| `/nkey` | Open the keyword manager (inline keyboard) |
| `/rkey` | Open the replacement phrase manager |
| `/status` | Show full bot status + statistics |
| `/on` | Enable the keyword editor |
| `/off` | Disable the keyword editor |
| `/reload` | Force-reload keyword cache from MongoDB |
| `/cancel` | Cancel any active conversation |

### Owner-Only Commands

| Command | Description |
|---|---|
| `/addadmin USER_ID` | Grant admin access to a user |
| `/deladmin USER_ID` | Revoke admin access |
| `/listadmin` | List all current admins |
| `/channel CHANNEL_ID` | Set (or change) the monitored channel |

---

## How Keyword Replacement Works

```
Configured /nkey keywords:     Configured /rkey replacement:
  1. @user                        @hii
  2. @oldchannel
  3. oldsite.com

New channel post:                Bot automatically edits to:
  Hello @user                      Hello @hii
  Join @oldchannel      →          Join @hii
  Visit oldsite.com                Visit @hii
```

**Key rules:**
- Every keyword maps to the **same** single replacement phrase.
- There are no per-keyword replacements.
- **All occurrences** in a message are replaced, not just the first.
- Replacement is case-insensitive by default.
- Telegram formatting (bold, italic, links, etc.) on surrounding text is preserved.

---

## MongoDB Collections

| Collection | Purpose |
|---|---|
| `settings` | Bot settings (channel, replacement, enabled flag, case sensitivity) |
| `admins` | Admin user IDs |
| `keywords` | Detection keywords |
| `statistics` | Counters (messages processed, edited, etc.) |

All settings survive container restarts because they live in MongoDB, not on the filesystem.

---

## Deployment

### 🐳 Docker (any host)

```bash
# Build
docker build -t keyword-editor-bot .

# Run
docker run -d \
  --name keyword-editor-bot \
  --restart unless-stopped \
  -e BOT_TOKEN=your_token \
  -e API_ID=your_api_id \
  -e API_HASH=your_api_hash \
  -e MONGO_URI=your_mongo_uri \
  -e OWNER_ID=your_user_id \
  -e ECHANNEL_ID=-1001234567890 \
  keyword-editor-bot
```

---

### ☁️ Koyeb

1. Push this repo to GitHub.
2. Go to [app.koyeb.com](https://app.koyeb.com) → **Create Service** → **GitHub**.
3. Select your repo.
4. Set **Build type** to `Dockerfile`.
5. Under **Environment Variables**, add all required variables from `.env.example`.
6. Set **Instance type** to `Nano` (sufficient for this workload).
7. Set **Ports**: leave empty — the bot is fully headless (no HTTP server).
8. Click **Deploy**.

> **Tip:** Koyeb will automatically rebuild and redeploy on every push to main.

---

### ☁️ Render

1. Push this repo to GitHub.
2. Go to [dashboard.render.com](https://dashboard.render.com) → **New** → **Web Service**.
   - Or use **Background Worker** if you don't need an HTTP port.
3. Connect your GitHub repo.
4. Set:
   - **Environment**: `Docker`
   - **Build Command**: *(leave blank — Dockerfile handles it)*
   - **Start Command**: *(leave blank — CMD in Dockerfile handles it)*
5. Add all environment variables under **Environment** → **Add Environment Variable**.
6. Click **Create Web Service**.

> **Note:** Render's free tier sleeps after inactivity. Use a paid tier or a
> Background Worker service type to keep the bot always running.

---

### 🐧 Linux (bare metal / VPS)

```bash
# Install Python 3.11
sudo apt update && sudo apt install python3.11 python3.11-venv python3-pip -y

# Clone and install
git clone <your-repo> && cd telegram-keyword-editor
python3.11 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env && nano .env

# Run in background with systemd
sudo tee /etc/systemd/system/keyword-editor-bot.service > /dev/null <<EOF
[Unit]
Description=Telegram Keyword Editor Bot
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$PWD
ExecStart=$PWD/venv/bin/python bot.py
Restart=always
RestartSec=10
EnvironmentFile=$PWD/.env

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now keyword-editor-bot
sudo journalctl -fu keyword-editor-bot   # view logs
```

---

### 📱 Termux (Android)

```bash
pkg update && pkg install python git -y
pip install -r requirements.txt
cp .env.example .env && nano .env
python bot.py

# Keep alive with Termux:Boot or nohup:
nohup python bot.py > bot.log 2>&1 &
```

---

## Architecture

```
bot.py              — startup, wires all components together
config.py           — reads env vars
database.py         — MongoDB (Motor async driver)

services/
  cache.py          — in-memory keyword + settings cache (asyncio.Lock)
  message_editor.py — replacement pipeline + Telegram API editing
  statistics.py     — async counter increments

handlers/
  start.py          — /start
  admin.py          — /addadmin, /deladmin, /listadmin
  keywords.py       — /nkey + inline keyboard callbacks
  replacement.py    — /rkey + inline keyboard callbacks
  settings.py       — /on, /off, /channel, /status, /cancel, /reload
  messages.py       — channel post handler → MessageEditor
  text_input.py     — conversation state router (group=1)

utils/
  states.py         — per-user state manager with TTL
  permissions.py    — is_owner(), is_admin()
  formatting.py     — entity-aware text replacement algorithm
  helpers.py        — format_number(), format_uptime(), etc.
```

---

## Security Notes

- Owner and admin IDs are never hard-coded.
- Every inline keyboard callback re-verifies the caller's Telegram ID.
- A non-admin user cannot trigger any admin action, even by crafting a callback.
- Secrets (`BOT_TOKEN`, `API_HASH`, `MONGO_URI`) are never logged.
- The Docker container runs as a non-root user.
- Conversation states are isolated per user — admins cannot interfere with each other.

---

## Troubleshooting

| Symptom | Check |
|---|---|
| Bot doesn't edit messages | Bot is admin with **Edit Messages** permission in the channel |
| `ChatAdminRequired` in logs | Same as above |
| Keywords not matching | Run `/reload` to refresh cache; check `/status` for keyword count |
| `MessageNotModified` | Message already contains the replacement — this is not an error |
| MongoDB connection failure | Check `MONGO_URI`, network access, IP whitelist on Atlas |
| Bot not responding to commands | Make sure you're messaging the bot in **private chat** (DM), not the channel |

---

## License

MIT — use freely, modify as needed.
