<div align="center">

# ♪ Roshani Music
### A Telegram music bot for high quality voice chat streaming

Built with **Python**, **Pyrogram**, **PyTgCalls** and **FFmpeg**.
Fully controlled by its owner from an in-chat **Owner Panel**.

</div>

---

## Owner Panel

Open the bot in private and send **/panel** (only `OWNER_ID` can use it).
Everything is edited from buttons inside Telegram, saved to MongoDB and applied instantly. No restart, no code edits.

| Section | What you can edit |
|---|---|
| ♪ Branding | Bot name, your name, your link (shown on the welcome message and the Owner button) |
| ♪ Welcome | Private and group welcome text with full Telegram formatting, help header, live preview |
| ♪ Media | Welcome, help, ping/stats, default thumbnail and radio pictures. Upload a photo or paste a link |
| ♪ Animation | Pick the loading animation shown before a song starts (8 styles, live preview). Shortcut: **/animation** |
| ♪ Links | Support chat, updates channel, source button, up to 6 extra custom buttons |
| ♪ Limits | Max duration, queue size, playlist batch and total, video height |
| ♪ Features | Autoplay default, auto leave, queue end message, thumbnail generator, /vplay, play logger |
| ♪ Access | Add or remove sudo users, block or unblock users, blacklist or whitelist chats |
| ♪ System | CPU and RAM, send logs, restart, reset every setting |

Welcome texts accept these placeholders: `{user}` `{mention}` `{brand}` `{owner}` `{owner_link}` `{username}`.
Uploaded pictures are stored in MongoDB, so they survive redeploys on hosts with a temporary disk.

---

## Features

- ◉ **Autoplay**: when the queue ends, a similar song starts on its own. Per chat: `/autoplay`, or the button on the player
- ▷▷ **Fast start**: tracks preload while the current one plays, the artwork card is built while the voice chat connects
- ♪ YouTube search, direct links and playlists
- ♫ Spotify tracks, albums and playlists (optional)
- Live radio and video playback
- Queue, loop, seek, skip, pause and resume with inline controls
- Multiple assistant accounts for load balancing
- Authorized users, blacklists, broadcast and per chat language
- Seven languages built in
- Docker ready

---

## Setup

Requirements: Python 3.10+, FFmpeg, Deno, a MongoDB database and a Telegram API key.

```bash
git clone <your repository url>
cd <your repository folder>
cp sample.env .env      # fill in the values
pip install -r requirements.txt
bash start
```

### Required variables

| Variable | Purpose |
|---|---|
| `API_ID`, `API_HASH` | From https://my.telegram.org/apps |
| `BOT_TOKEN` | From @BotFather |
| `MONGO_DB_URI` | MongoDB connection string |
| `OWNER_ID` | Your Telegram user ID |
| `LOGGER_ID` | A private group where the bot is admin |
| `STRING_SESSION` | Assistant account session (Pyrogram) |

### Optional variables

`BRAND_NAME`, `OWNER_NAME`, `OWNER_LINK` are only first-run defaults. After that, edit them from `/panel`.
Everything else in `sample.env` (limits, feature flags, cookies, Spotify) also acts as a default that the panel can override.

### Docker

```bash
docker compose up -d --build
```

---

## Commands

Send `/help` to the bot for the full list. Owner and sudo extras: `/panel`, `/broadcast`, `/restart`, `/logs`, `/addsudo`, `/delsudo`, `/block`, `/blacklistchat`, `/enable vplay`.

---

## Credits

Created and maintained by **Roshani Patil**.
Based on the open source HasiiMusicBot project by Hasindu Nagolla, licensed under GPLv3 (see `LICENSE`).
