import asyncio
import logging
import os
import re
import sqlite3
from io import BytesIO
from pathlib import Path

import aiohttp
from telegram import (
    InlineKeyboardButton, InlineKeyboardMarkup, InputFile, Update,
)
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler, ContextTypes,
    MessageHandler, filters,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("sharkbonus-ai")

DB_PATH = Path(os.getenv("DATABASE_PATH", "sharkbonus.db"))
ADMIN_ID = int(os.getenv("ADMIN_ID", "8048582254"))
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
GEMINI_IMAGE_MODEL = os.getenv("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")
MAX_HISTORY_MESSAGES = 12


def db_connect():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    with db_connect() as db:
        # Keep the existing users table compatible with databases from the trivia version.
        db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                points INTEGER NOT NULL DEFAULT 0,
                quizzes_played INTEGER NOT NULL DEFAULT 0,
                correct_answers INTEGER NOT NULL DEFAULT 0
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL DEFAULT ''
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                user_id INTEGER NOT NULL,
                history TEXT NOT NULL DEFAULT '[]',
                PRIMARY KEY (user_id)
            )
        """)
        defaults = {
            "promo_text": "✨ Explore our AI tools: get helpful answers and create images with AI.",
            "promo_link": "",
            "promo_image": "",
            "reminders_enabled": "0",
            "reminder_hours": "5",
        }
        for key, value in defaults.items():
            db.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (key, value),
            )


def register_user(user):
    if not user:
        return
    with db_connect() as db:
        db.execute("""
            INSERT INTO users (user_id, username, first_name)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username=excluded.username,
                first_name=excluded.first_name
        """, (user.id, user.username or "", user.first_name or "User"))


def get_setting(key, default=""):
    with db_connect() as db:
        row = db.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key, value):
    with db_connect() as db:
        db.execute("""
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
        """, (key, str(value)))


def get_all_user_ids():
    with db_connect() as db:
        rows = db.execute("SELECT user_id FROM users").fetchall()
    return [row["user_id"] for row in rows]


def is_admin(user_id):
    return user_id == ADMIN_ID


def main_keyboard(provider="deepseek"):
    provider_label = "DeepSeek" if provider == "deepseek" else "ChatGPT"
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                f"🧠 {provider_label} (selected)", callback_data=f"provider:{provider}"
            )
        ],
        [
            InlineKeyboardButton("DeepSeek", callback_data="provider:deepseek"),
            InlineKeyboardButton("ChatGPT", callback_data="provider:openai"),
        ],
        [InlineKeyboardButton("🖼 Make Image · NanoBanana", callback_data="mode:image")],
        [InlineKeyboardButton("💬 Ask a Question", callback_data="mode:chat")],
    ])


def admin_keyboard():
    enabled = get_setting("reminders_enabled", "0") == "1"
    hours = get_setting("reminder_hours", "5")
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✏️ Change promo text", callback_data="admin:text"),
            InlineKeyboardButton("🖼 Change image", callback_data="admin:image"),
        ],
        [InlineKeyboardButton("🔗 Change link", callback_data="admin:link")],
        [InlineKeyboardButton("👁 Preview promotion", callback_data="admin:preview")],
        [
            InlineKeyboardButton(
                "🔔 Reminders: ON" if enabled else "🔕 Reminders: OFF",
                callback_data="admin:toggle",
            )
        ],
        [
            InlineKeyboardButton(
                "5 hours ✓" if hours == "5" else "5 hours",
                callback_data="admin:hours:5",
            ),
            InlineKeyboardButton(
                "10 hours ✓" if hours == "10" else "10 hours",
                callback_data="admin:hours:10",
            ),
        ],
    ])


def promo_keyboard():
    link = get_setting("promo_link", "").strip()
    if link.startswith(("https://", "http://")):
        return InlineKeyboardMarkup([[InlineKeyboardButton("✨ Explore Now", url=link)]])
    return None


async def send_promotion(bot, chat_id):
    text = get_setting("promo_text", "").strip() or "Discover our AI assistant."
    image_id = get_setting("promo_image", "").strip()
    markup = promo_keyboard()
    try:
        if image_id:
            await bot.send_photo(
                chat_id=chat_id, photo=image_id, caption=text[:1024],
                reply_markup=markup,
            )
        else:
            await bot.send_message(chat_id=chat_id, text=text[:4096], reply_markup=markup)
        return True
    except Exception as exc:
        logger.warning("Could not send promotion to %s: %s", chat_id, exc)
        return False


async def reminder_job(context: ContextTypes.DEFAULT_TYPE):
    user_ids = get_all_user_ids()
    sent = 0
    for user_id in user_ids:
        if await send_promotion(context.bot, user_id):
            sent += 1
        await asyncio.sleep(0.04)
    logger.info("Scheduled promotion sent to %s of %s users", sent, len(user_ids))


def configure_reminders(app: Application):
    for job in app.job_queue.get_jobs_by_name("promo-reminders"):
        job.schedule_removal()
    if get_setting("reminders_enabled", "0") == "1":
        hours = int(get_setting("reminder_hours", "5"))
        app.job_queue.run_repeating(
            reminder_job,
            interval=hours * 60 * 60,
            first=hours * 60 * 60,
            name="promo-reminders",
        )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    register_user(update.effective_user)
    context.user_data.setdefault("provider", "deepseek")
    context.user_data["mode"] = "chat"
    welcome = (
        "👋 Welcome to your AI assistant!\n\n"
        "🧠 *Explanations and answers*\n"
        "Ask questions and get help using DeepSeek or ChatGPT.\n\n"
        "🖼 *Visualize your ideas*\n"
        "Describe an image and NanoBanana will create it for you.\n\n"
        "Choose a tool below or simply send me a question."
    )
    await update.message.reply_text(
        welcome, reply_markup=main_keyboard(context.user_data["provider"]),
        parse_mode="Markdown",
    )


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("You are not authorized to use the admin panel.")
        return
    await update.message.reply_text(
        "⚙️ *AI BOT ADMIN PANEL*\nManage your promotional content and reminders below.",
        reply_markup=admin_keyboard(), parse_mode="Markdown",
    )


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["history"] = []
    context.user_data["mode"] = "chat"
    await update.message.reply_text("Your conversation has been cleared. Send a new question anytime.")


async def image_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["mode"] = "image"
    await update.message.reply_text(
        "🖼 Send me a description of the image you want NanoBanana to create."
    )


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data or ""
    user_id = query.from_user.id
    register_user(query.from_user)

    if data.startswith("provider:"):
        provider = data.split(":", 1)[1]
        if provider not in ("deepseek", "openai"):
            return
        context.user_data["provider"] = provider
        context.user_data["mode"] = "chat"
        label = "DeepSeek" if provider == "deepseek" else "ChatGPT"
        await query.edit_message_text(
            f"✅ {label} selected. Send me your question.",
            reply_markup=main_keyboard(provider),
        )
        return

    if data == "mode:image":
        context.user_data["mode"] = "image"
        await query.message.reply_text(
            "🖼 *NanoBanana image generator*\nDescribe the image you want me to create.",
            parse_mode="Markdown",
        )
        return

    if data == "mode:chat":
        context.user_data["mode"] = "chat"
        provider = context.user_data.get("provider", "deepseek")
        await query.message.reply_text(
            "💬 Chat mode is ready. Send me a question.",
            reply_markup=main_keyboard(provider),
        )
        return

    if data.startswith("admin:"):
        if not is_admin(user_id):
            await query.answer("Not authorized.", show_alert=True)
            return
        action = data.split(":")
        if action[1] == "text":
            context.user_data["admin_pending"] = "text"
            await query.message.reply_text("Send the new promotional text.")
        elif action[1] == "image":
            context.user_data["admin_pending"] = "image"
            await query.message.reply_text("Send the new promotional image as a photo.")
        elif action[1] == "link":
            context.user_data["admin_pending"] = "link"
            await query.message.reply_text("Send the destination URL (https://...). Send /clearlink to remove it.")
        elif action[1] == "preview":
            await send_promotion(context.bot, user_id)
        elif action[1] == "toggle":
            enabled = get_setting("reminders_enabled", "0") != "1"
            set_setting("reminders_enabled", "1" if enabled else "0")
            configure_reminders(context.application)
            await query.message.reply_text(
                "Scheduled reminders are now " + ("ON." if enabled else "OFF."),
                reply_markup=admin_keyboard(),
            )
        elif action[1] == "hours" and len(action) == 3 and action[2] in ("5", "10"):
            set_setting("reminder_hours", action[2])
            configure_reminders(context.application)
            await query.message.reply_text(
                f"Reminder interval set to every {action[2]} hours.",
                reply_markup=admin_keyboard(),
            )


async def call_chat_api(provider, messages):
    if provider == "deepseek":
        api_key = os.getenv("DEEPSEEK_API_KEY")
        endpoint = DEEPSEEK_URL
        model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    else:
        api_key = os.getenv("OPENAI_API_KEY")
        endpoint = OPENAI_URL
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    if not api_key:
        name = "DEEPSEEK_API_KEY" if provider == "deepseek" else "OPENAI_API_KEY"
        return f"⚠️ This provider is not configured yet. Add {name} to your hosting environment variables."

    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.7,
    }
    timeout = aiohttp.ClientTimeout(total=90)
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(endpoint, json=payload, headers=headers) as response:
            data = await response.json(content_type=None)
            if response.status >= 400:
                logger.error("%s API error %s: %s", provider, response.status, data)
                detail = data.get("error", {}).get("message", "The AI provider returned an error.")
                return f"⚠️ {detail}"
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError):
        logger.error("Unexpected %s response: %s", provider, data)
        return "Sorry, I couldn't read the AI response. Please try again."


async def generate_image(prompt):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None, "⚠️ Image generation is not configured yet. Add GEMINI_API_KEY to your hosting environment variables."

    endpoint = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_IMAGE_MODEL}:generateContent?key={api_key}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseModalities": ["IMAGE"]},
    }
    timeout = aiohttp.ClientTimeout(total=180)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(endpoint, json=payload) as response:
            data = await response.json(content_type=None)
            if response.status >= 400:
                logger.error("Gemini image error %s: %s", response.status, data)
                detail = data.get("error", {}).get("message", "Image generation failed.")
                return None, f"⚠️ {detail}"
    for candidate in data.get("candidates", []):
        for part in candidate.get("content", {}).get("parts", []):
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"):
                import base64
                raw = base64.b64decode(inline["data"])
                mime = inline.get("mimeType") or inline.get("mime_type") or "image/png"
                extension = "jpg" if "jpeg" in mime else "png"
                return (raw, extension), None
    return None, "The image provider did not return an image. Please try a different prompt."


async def handle_admin_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pending = context.user_data.get("admin_pending")
    if not pending or not is_admin(update.effective_user.id):
        return False

    if pending == "text":
        if not update.message.text:
            await update.message.reply_text("Please send the promotional text as a text message.")
            return True
        set_setting("promo_text", update.message.text.strip())
        context.user_data.pop("admin_pending", None)
        await update.message.reply_text("✅ Promotional text updated.", reply_markup=admin_keyboard())
        return True

    if pending == "link":
        if not update.message.text:
            await update.message.reply_text("Please send a valid URL beginning with https:// or http://.")
            return True
        value = update.message.text.strip()
        if value.lower() == "/clearlink":
            set_setting("promo_link", "")
        elif re.match(r"^https?://[^\s]+$", value):
            set_setting("promo_link", value)
        else:
            await update.message.reply_text("That URL doesn't look valid. Send a link beginning with https:// or http://.")
            return True
        context.user_data.pop("admin_pending", None)
        await update.message.reply_text("✅ Promotional link updated.", reply_markup=admin_keyboard())
        return True

    if pending == "image":
        if not update.message.photo:
            await update.message.reply_text("Please send the image as a Telegram photo.")
            return True
        set_setting("promo_image", update.message.photo[-1].file_id)
        context.user_data.pop("admin_pending", None)
        await update.message.reply_text("✅ Promotional image updated.", reply_markup=admin_keyboard())
        return True

    return False


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    register_user(user)

    if await handle_admin_input(update, context):
        return

    if not update.message or not update.message.text:
        return
    prompt = update.message.text.strip()
    if not prompt:
        return

    mode = context.user_data.get("mode", "chat")
    if mode == "image":
        status = await update.message.reply_text("🎨 Creating your image with NanoBanana. Please wait...")
        result, error = await generate_image(prompt)
        if error:
            await status.edit_text(error)
            return
        raw, extension = result
        await status.delete()
        await update.message.reply_photo(
            photo=InputFile(BytesIO(raw), filename=f"nanobanana.{extension}"),
            caption="✨ Your AI-generated image is ready!",
        )
        return

    provider = context.user_data.get("provider", "deepseek")
    history = context.user_data.setdefault("history", [])
    history.append({"role": "user", "content": prompt})
    history = history[-MAX_HISTORY_MESSAGES:]
    context.user_data["history"] = history
    status = await update.message.reply_text(
        "🧠 Thinking with " + ("DeepSeek" if provider == "deepseek" else "ChatGPT") + "..."
    )
    answer = await call_chat_api(
        provider,
        [{"role": "system", "content": "You are a helpful, clear and friendly AI assistant."}] + history,
    )
    if not answer.startswith("⚠️"):
        history.append({"role": "assistant", "content": answer})
        context.user_data["history"] = history[-MAX_HISTORY_MESSAGES:]
    await status.delete()
    for offset in range(0, len(answer), 4000):
        await update.message.reply_text(answer[offset:offset + 4000])


async def clear_link_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    set_setting("promo_link", "")
    context.user_data.pop("admin_pending", None)
    await update.message.reply_text("Promotional link removed.", reply_markup=admin_keyboard())


async def post_init(app: Application):
    configure_reminders(app)


def main():
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN environment variable is required.")
    init_db()
    app = (
        Application.builder()
        .token(token)
        .post_init(post_init)
        .build()
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(CommandHandler("imagine", image_command))
    app.add_handler(CommandHandler("clearlink", clear_link_command))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    app.add_handler(MessageHandler(filters.PHOTO, message_handler))
    logger.info("SharkBonus AI assistant is starting...")
    app.run_polling()


if __name__ == "__main__":
    main()
