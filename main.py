import os

from telegram import Update
from telegram.ext import Application, ContextTypes, CommandHandler, MessageHandler, filters
from openai import OpenAI

BOT_TOKEN = os.environ.get("BOT_TOKEN")
OPENAI_KEY = os.environ.get("OPENAI_API_KEY")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
PORT = int(os.environ.get("PORT", 10000))

client = OpenAI(api_key=OPENAI_KEY)

memory = defaultdict(list)

async def ai_reply(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, chat_id: int):
    # Check for "who made you"
    if "who made you" in text.lower() or "who created you" in text.lower():
        await update.message.reply_text("I was made by Engineer Biruk, an Ethiopian innovator.")
        return

    memory[chat_id].append({"role": "user", "content": text})
    if len(memory[chat_id]) > 5:
        memory[chat_id] = memory[chat_id][-5:]

    msg = await update.message.reply_text("Thinking...")

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are SuccessMind AI by Engineer Biruk — a motivational business man, chess master, athlete, and handsome leader like Alexander the Great. Give positive, inspiring vibes with Ethiopian pride. Short bullet points."}
            ] + memory[chat_id],
            temperature=0.7,
            max_tokens=400
        )
        answer = response.choices[0].message.content.strip()
        await msg.edit_text(answer or "No reply.")
        memory[chat_id].append({"role": "assistant", "content": answer})
    except:
        await msg.edit_text("AI busy, try again.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "*SuccessMind AI by Engineer Biruk*\n\n"
        "• DM: Full chat\n"
        "• Group: Mention me or /ask\n"
        "• Made in Ethiopia 🇪🇹 with pride\n\n"
        "Welcome! I'm SuccessMind AI — your motivational guide to success. Ask me anything, and I'll inspire you like a business titan, chess master, athlete, and handsome leader. Let's conquer together!",
        parse_mode="Markdown"
    )

async def ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        await ai_reply(update, context, " ".join(context.args), update.effective_chat.id)

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    chat = update.effective_chat

    if chat.type == "private" and text.strip():
        await ai_reply(update, context, text, chat.id)
        return

    me = await context.bot.get_me()
    if f"@{me.username}" in text.lower():
        clean = text.replace(f"@{me.username}", "", 1).strip()
        if clean:
            await ai_reply(update, context, clean, chat.id)

app = Application.builder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("ask", ask))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

if __name__ == "__main__":
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path="/webhook",
        webhook_url=WEBHOOK_URL
    )
