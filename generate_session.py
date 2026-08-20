"""
generate_session.py — Run this ONCE to create a Pyrogram user session string.

    python generate_session.py

Pyrogram will prompt for your phone number, the OTP Telegram sends you, and
your 2FA password (if enabled).  Nothing is stored on disk — the session lives
only in memory.  At the end the script prints the SESSION_STRING value; paste
it into your .env file and restart the bot.

Why is this needed?
    Telegram's Bot API blocks bots from reading channel history
    (messages.GetHistory returns BOT_METHOD_INVALID).  A regular user account
    is required to fetch past messages for /scan.  The user account only needs
    to be a member of the channel — all edits are still performed by the bot.
"""

# ── Python 3.10+ compatibility fix (same as bot.py) ──────────────────────────
import asyncio as _asyncio
try:
    _asyncio.get_event_loop()
except RuntimeError:
    _asyncio.set_event_loop(_asyncio.new_event_loop())
# ─────────────────────────────────────────────────────────────────────────────

import asyncio
import sys
import os

# Allow running from the project root without installing anything
sys.path.insert(0, os.path.dirname(__file__))

try:
    from pyrogram import Client
    from config import Config
except ImportError as exc:
    print(f"\n❌ Import error: {exc}")
    print("Make sure you have run:  pip install -r requirements.txt\n")
    sys.exit(1)


BANNER = """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Pyrogram Session String Generator
  (for the Telegram Keyword Editor Bot — /scan feature)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

def check_config() -> bool:
    ok = True
    if not Config.API_ID:
        print("❌ API_ID is missing from .env")
        ok = False
    if not Config.API_HASH:
        print("❌ API_HASH is missing from .env")
        ok = False
    return ok


async def generate() -> None:
    print(BANNER)
    print("Logging in to Telegram with your personal account.")
    print("Your password is used only to authenticate — it is NOT stored.")
    print()

    if not check_config():
        print("\nFill in API_ID and API_HASH in your .env file first.\n")
        return

    print(f"Using API_ID : {Config.API_ID}")
    print(f"Using API_HASH: {Config.API_HASH[:6]}…  (truncated for display)")
    print()

    # in_memory=True → Pyrogram will NOT create a .session file on disk
    # Pyrogram handles the interactive login flow automatically
    async with Client(
        name="session_generator",
        api_id=Config.API_ID,
        api_hash=Config.API_HASH,
        in_memory=True,
    ) as client:
        session_string = await client.export_session_string()
        me = await client.get_me()

        print()
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(f"  ✅ Logged in as: {me.first_name} (@{me.username or 'no username'})")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print()
        print("Add the following line to your .env file:")
        print()
        print(f"SESSION_STRING={session_string}")
        print()
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print()
        print("Next steps:")
        print("  1. Copy the SESSION_STRING line into .env")
        print("  2. Make sure your account is a member of ECHANNEL")
        print("     (it does NOT need to be an admin — read access is enough)")
        print("  3. Restart the bot:  python bot.py")
        print()


if __name__ == "__main__":
    asyncio.run(generate())
