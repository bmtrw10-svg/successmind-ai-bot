import os
import logging
import aiohttp
from collections import defaultdict
from importlib import metadata, util
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv

# --- Basic safety checks to fail fast if environment is wrong ---
try:
    metadata.version("telegram")
    raise RuntimeError("Conflicting package 'telegram' is installed. Remove it from requirements or repo.")
except metadata.PackageNotFoundError:
    pass

try:
    ptb_ver = metadata.version("python-telegram-bot")
except metadata.PackageNotFoundError:
    raise RuntimeError("python-telegram-bot not installed. Add it to requirements.txt")

if int(ptb_ver.split(".")[0]) < 20:
    raise RuntimeError(f"python-telegram-bot>=20 required (found {ptb_ver}). Pin to 20.x in requirements.txt")

# --- Load env ---
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT = int(os.getenv("PORT", "10000"))

if not all([BOT_TOKEN, OPENAI_KEY, WEBHOOK_URL]):
    raise RuntimeError("Missing BOT_TOKEN, OPENAI_API_KEY, or WEBHOOK_URL environment variable")

# --- Logging minimal for production ---
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger("bot")
logger.propagate = False

# --- In-memory short context per chat ---
MAX_MEMORY = 5
chat_memory = defaultdict(list)  # chat_id -> list of {"role":..., "content":...}

# --- OpenAI call (async) ---
async def openai_chat(messages):
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "gpt-3.5-turbo",
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 800
    }
    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(url, json=payload, headers=headers) as resp:
            data = await resp.json()
            # Basic safety: ensure expected structure
            if "choices" in data and data["choices"]:
                return data["choices"][0]["message"]["content"].strip()
            raise RuntimeError("OpenAI response missing choices")

# --- Core responder ---
async def respond(update: Update, context: ContextTypes.DEFAULT_TYPE, user_text: str):
    chat_id = update.effective_chat.id
    # append user message
    chat_memory[chat_id].append({"role": "user", "content": user_text})
    chat_memory[chat_id] = chat_memory[chat_id][-MAX_MEMORY:]
    system_msg = {"role": "system", "content": "You are a concise, helpful assistant. Keep answers clear and professional."}
    messages = [system_msg] + [{"role": m["role"], "content": m["content"]} for m in chat_memory[chat_id]]
    try:
        reply = await openai_chat(messages)
    except Exception:
        await update.message.reply_text("Sorry, I couldn't reach the AI service right now. Try again later.")
        return
    # send reply
    await update.message.reply_text(reply)
    # store assistant reply
    chat_memory[chat_id].append({"role": "assistant", "content": reply})
    chat_memory[chat_id] = chat_memory[chat_id][-MAX_MEMORY:]

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("ProHybrid AI — DM me or mention me in groups (or use /ask).")

async def ask_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /ask your question")
        return
    prompt = " ".join(context.args)
    await respond(update, context, prompt)

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    text = update.message.text.strip()
    if not text:
        return
    # Private chat: full chat
    if update.effective_chat.type == "private":
        await respond(update, context, text)
        return
    # Group chat: only respond when mentioned or when message starts with /ask
    bot = await context.bot.get_me()
    mention = f"@{bot.username}"
    if text.startswith("/ask") or mention in text:
        # remove mention and /ask
        clean = text.replace(mention, "").replace("/ask", "").strip()
        if clean:
            await respond(update, context, clean)

# --- Build application ---
def build_app():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ask", ask_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    return app

# --- Run webhook server ---
if __name__ == "__main__":
    app = build_app()
    # This will set the webhook and start an aiohttp server listening on /webhook
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_path="/webhook",
        webhook_url=WEBHOOK_URL
    )
