import os
import json
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes
)

# تنظیمات اولیه
BOT_TOKEN = os.getenv("BOT_TOKEN")

# پوشه دیتا
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

ADMINS_FILE = os.path.join(DATA_DIR, "admins.json")
USERS_FILE = os.path.join(DATA_DIR, "users.json")
BLOCKED_FILE = os.path.join(DATA_DIR, "blocked.json")
WELCOME_FILE = os.path.join(DATA_DIR, "welcome.txt")

# لاگ‌ها
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# ابزارها
def load_json(path, default):
    if not os.path.exists(path):
        with open(path, "w") as f:
            json.dump(default, f)
        return default
    with open(path, "r") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f)

def get_admins():
    return load_json(ADMINS_FILE, [])

def get_blocked():
    return load_json(BLOCKED_FILE, [])

def is_admin(user_id: int):
    return user_id in get_admins()

def is_blocked(user_id: int):
    return user_id in get_blocked()

def log_user(user: Update.effective_user):
    users = load_json(USERS_FILE, {})
    if str(user.id) not in users:
        users[str(user.id)] = {
            "id": user.id,
            "name": user.full_name,
            "username": user.username,
            "joined": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        save_json(USERS_FILE, users)

# هندلر استارت
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if is_blocked(user.id):
        return
    log_user(user)

    welcome = "سلام خوش اومدی به ربات دکتر گشاد 😎\n\nبا زدن دکمه زیر می‌تونی پیامتو بفرستی."
    if os.path.exists(WELCOME_FILE):
        with open(WELCOME_FILE, "r") as f:
            welcome = f.read()

    button = [[InlineKeyboardButton("✉️ ارسال پیام", callback_data="send_message")]]
    await update.message.reply_text(welcome, reply_markup=InlineKeyboardMarkup(button))

# پیام جدید از کاربر
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "send_message":
        context.user_data["awaiting_message"] = True
        await query.message.reply_text("خب داداش، پیامتو بنویس تا برسونم به ادمین 😏")

# دریافت پیام کاربر
async def user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if is_blocked(user.id):
        return

    if context.user_data.get("awaiting_message"):
        context.user_data["awaiting_message"] = False
        log_user(user)

        for admin_id in get_admins():
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=f"📩 پیام جدید از {user.full_name} (@{user.username}) [{user.id}]:\n\n{update.message.text}",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("✉️ پاسخ", callback_data=f"reply_{user.id}")],
                        [InlineKeyboardButton("🚫 بلاک", callback_data=f"block_{user.id}")]
                    ])
                )
            except:
                pass

        await update.message.reply_text("✅ پیامت ارسال شد. به زودی پاسخ می‌رسه.")
        await update.message.reply_text("اگه خواستی پیام دیگه‌ای بدی دکمه زیر رو بزن",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✉️ ارسال پیام جدید", callback_data="send_message")]])
        )

# ادمین روی دکمه‌ها کلیک می‌کنه
async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    admin_id = query.from_user.id

    if not is_admin(admin_id):
        return

    data = query.data
    if data.startswith("reply_"):
        user_id = int(data.split("_")[1])
        context.user_data["reply_to"] = user_id
        await query.message.reply_text("✍️ پاسخ خودتو بنویس تا براش بفرستم.")
    elif data.startswith("block_"):
        user_id = int(data.split("_")[1])
        blocked = get_blocked()
        if user_id not in blocked:
            blocked.append(user_id)
            save_json(BLOCKED_FILE, blocked)
            await query.message.reply_text("✅ کاربر بلاک شد.")

# دریافت پاسخ ادمین
async def admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_id = update.effective_user.id
    if not is_admin(admin_id):
        return

    user_id = context.user_data.get("reply_to")
    if user_id:
        try:
            await context.bot.send_message(chat_id=user_id, text=update.message.text)
            await update.message.reply_text("✅ پاسخ ارسال شد.")
        except:
            await update.message.reply_text("❌ ارسال نشد. کاربر شاید بلاک کرده یا دسترسی نداره.")
        context.user_data["reply_to"] = None

# کامند اضافه کردن ادمین
async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("❗ استفاده: /addadmin [user_id]")
        return
    try:
        new_id = int(context.args[0])
        admins = get_admins()
        if new_id not in admins:
            admins.append(new_id)
            save_json(ADMINS_FILE, admins)
            await update.message.reply_text("✅ ادمین جدید اضافه شد.")
        else:
            await update.message.reply_text("ℹ️ این کاربر قبلاً ادمین بوده.")
    except:
        await update.message.reply_text("❌ آیدی نامعتبر است.")

# کامند حذف ادمین
async def remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("❗ استفاده: /removeadmin [user_id]")
        return
    try:
        remove_id = int(context.args[0])
        admins = get_admins()
        if remove_id in admins:
            admins.remove(remove_id)
            save_json(ADMINS_FILE, admins)
            await update.message.reply_text("✅ ادمین حذف شد.")
        else:
            await update.message.reply_text("ℹ️ ادمینی با این آیدی نیست.")
    except:
        await update.message.reply_text("❌ خطا در پردازش آیدی.")

# آمار کاربران
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    users = load_json(USERS_FILE, {})
    msg = f"👥 تعداد کاربران: {len(users)}\n\n"
    for u in users.values():
        msg += f"{u['name']} (@{u['username']}) [{u['id']}] - {u['joined']}\n"
    await update.message.reply_text(msg or "هیچ کاربری ثبت نشده.")

# راهنما
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await update.message.reply_text(
        "/addadmin [id] - افزودن ادمین\n"
        "/removeadmin [id] - حذف ادمین\n"
        "/stats - آمار کاربران\n"
        "/help - راهنما"
    )

# اجرای ربات
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addadmin", add_admin))
    app.add_handler(CommandHandler("removeadmin", remove_admin))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("help", help_command))

    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(CallbackQueryHandler(admin_callback))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.User(user_id=get_admins()), user_message))
    app.add_handler(MessageHandler(filters.TEXT & filters.User(user_id=get_admins()), admin_text))

    app.run_polling()
