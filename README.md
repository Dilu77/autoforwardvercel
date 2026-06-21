# 🚀 Live Forward Bot

A Telegram userbot-powered **live forwarding bot** — forwards messages **instantly** as they arrive in source channels. Supports multiple source channels per user, in-bot session generation, and full settings control.

---

## ✨ Features

- ⚡ **Live / instant forwarding** — message arrives → forwarded immediately
- 📥 **Multiple source channels** per user
- 📤 **One destination channel** per user
- 🔑 **In-bot session generator** — no external tool needed
- 🗄 **MongoDB storage** — session strings, channels, settings all persisted
- ⚙️ **Per-user settings**: Forward tag, remove caption, custom caption, media type filters
- ♻️ **Auto-resume** — forwarding restarts automatically after bot restart
- 🏥 **Health check** — Flask server keeps Koyeb alive

---

## ⚙️ Environment Variables

| Variable        | Description                                      |
|-----------------|--------------------------------------------------|
| `API_ID`        | Telegram API ID (from my.telegram.org)           |
| `API_HASH`      | Telegram API Hash                                |
| `BOT_TOKEN`     | Bot token from @BotFather                        |
| `DATABASE_URI`  | MongoDB connection string                        |
| `DATABASE_NAME` | MongoDB database name (default: `LiveForwardBot`)|
| `OWNER_ID`      | Your Telegram user ID (space-separated for many) |

---

## 🖥 Koyeb Deployment

**Run command (exactly as configured):**
```
gunicorn app:app & python3 main.py
```

**Health check path:** `/health`  
**Port:** `8080`

---

## 🤖 Bot Commands

| Command             | Description                              |
|---------------------|------------------------------------------|
| `/start`            | Open main menu                           |
| `/generate_session` | Start in-bot session generator           |
| `/stats`            | (Owner) Show user & active session stats |
| `/broadcast`        | (Owner) Broadcast a message to all users |

---

## 📖 How to Use

1. Start the bot → `/start`
2. Tap **🔑 Generate Session** and follow the prompts (phone → OTP → 2FA if needed)
3. Tap **📥 Sources** → **➕ Add Source Channel** → forward a message from your source channel
4. Tap **📤 Destination** → **✏️ Set Destination** → forward a message from your destination channel
5. Tap **▶️ Start Forwarding** — done! Messages flow live.

---

## ⚠️ Notes

- The userbot account **must be a member** of all source channels
- The userbot account **must be an admin** (post messages) in the destination channel
- Use at your own risk — automated userbot usage may violate Telegram ToS
