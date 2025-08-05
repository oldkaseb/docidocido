import json
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

TOKEN = os.getenv("BOT_TOKEN")
DATA_PATH = "users.json"
ADMIN_PATH = "admins.json"
BLOCK_PATH = "blocked.json"
WELCOME_PATH = "welcome.txt"

# --- Data utils ---
def load_json(path):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except:
        return []

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def get_admins():
    return load_json(ADMIN_PATH)

def get_blocked():
    return load_json(BLOCK_PATH)

def get_users():
    return load_json(DATA_PATH)

def add_user(user):
    users = get_users()
    if not any(u["id"] == user.id for u in users):
        users.append({
            "id": user.id,
            "name": user.full_name,
            "username": user.username,
            "joined": datetime.now().strftime("%Y-%m-%d %H:%M"),
        })
        save_json(DATA_PATH, users)

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id in get_blocked():
        return
    add_user(user)
    keyboard = [[InlineKeyboardButton("📝 ارسال پیام", callback_data="send_msg")]]
    text = open(WELCOME_PATH, "r").read() if os.path.exists(WELCOME_PATH) else "سلام! پیام خودتو برای ادمین بفرست 😎"
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "send_msg":
        context.user_data["awaiting_msg"] = True
        await query.message.reply_text("خب رفیق 😄 پیام‌تو بفرست تا برسونم به ادمین!")

async def user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id in get_blocked():
        return
    if context.user_data.get("awaiting_msg"):
        context.user_data["awaiting_msg"] = False
        msg = f"📩 پیام جدید از کاربر:\n\n👤 نام: {user.full_name}\n🆔 آیدی: {user.id}\n📎 یوزرنیم: @{user.username or 'ندارد'}\n\n📝 {update.message.text}"
        for admin_id in get_admins():
            keyboard = [[InlineKeyboardButton("✉️ پاسخ", callback_data=f"reply:{user.id}")]]
            await context.bot.send_message(chat_id=admin_id, text=msg, reply_markup=InlineKeyboardMarkup(keyboard))
        await update.message.reply_text("پیامت ارسال شد ✅\n\nاگه دوست داری، می‌تونی دوباره پیام بدی!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📝 ارسال پیام جدید", callback_data="send_msg")]]))

async def admin_reply_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data.startswith("reply:"):
        uid = int(query.data.split(":")[1])
        context.user_data["reply_to"] = uid
        await query.message.reply_text("پیام خودتو برای کاربر بنویس:")

async def admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id in get_admins() and "reply_to" in context.user_data:
        target = context.user_data.pop("reply_to")
        try:
            await context.bot.send_message(chat_id=target, text=f"👨‍⚕️ پاسخ ادمین:\n\n{update.message.text}")
            await update.message.reply_text("✅ پیام ارسال شد به کاربر.")
        except:
            await update.message.reply_text("❌ ارسال نشد. شاید کاربر استارت نکرده یا بلاک کرده باشه.")

# --- Commands ---
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in get_admins():
        return
    users = get_users()
    text = "\n\n".join([f"{u['name']} | {u['id']} | @{u['username'] or 'ندارد'} | {u['joined']}" for u in users])
    await update.message.reply_text(f"📊 آمار کاربران ({len(users)} نفر):\n\n{text}")

async def forall(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in get_admins() or not update.message.reply_to_message:
        return
    text = update.message.reply_to_message.text
    for user in get_users():
        try:
            await context.bot.send_message(chat_id=user["id"], text=text)
        except:
            pass
    await update.message.reply_text("📬 پیام همگانی ارسال شد.")

async def addadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in get_admins():
        return
    try:
        uid = int(context.args[0])
        admins = get_admins()
        if uid not in admins:
            admins.append(uid)
            save_json(ADMIN_PATH, admins)
            await update.message.reply_text("✅ ادمین جدید اضافه شد.")
    except:
        await update.message.reply_text("❌ فرمت درست نیست. مثال: /addadmin 123456")

async def removeadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in get_admins():
        return
    try:
        uid = int(context.args[0])
        admins = get_admins()
        if uid in admins:
            admins.remove(uid)
            save_json(ADMIN_PATH, admins)
            await update.message.reply_text("✅ ادمین حذف شد.")
    except:
        await update.message.reply_text("❌ فرمت درست نیست. مثال: /removeadmin 123456")

async def block(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in get_admins():
        return
    try:
        uid = int(context.args[0])
        blocked = get_blocked()
        if uid not in blocked:
            blocked.append(uid)
            save_json(BLOCK_PATH, blocked)
            await update.message.reply_text("🔒 کاربر بلاک شد.")
    except:
        await update.message.reply_text("❌ فرمت درست نیست. مثال: /block 123456")

async def unblock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in get_admins():
        return
    try:
        uid = int(context.args[0])
        blocked = get_blocked()
        if uid in blocked:
            blocked.remove(uid)
            save_json(BLOCK_PATH, blocked)
            await update.message.reply_text("✅ کاربر آنبلاک شد.")
    except:
        await update.message.reply_text("❌ فرمت درست نیست. مثال: /unblock 123456")

async def setwelcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in get_admins():
        return
    if update.message.reply_to_message:
        with open(WELCOME_PATH, "w") as f:
            f.write(update.message.reply_to_message.text)
        await update.message.reply_text("✅ پیام خوش‌آمد ثبت شد.")

# --- Run bot ---
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("forall", forall))
    app.add_handler(CommandHandler("addadmin", addadmin))
    app.add_handler(CommandHandler("removeadmin", removeadmin))
    app.add_handler(CommandHandler("block", block))
    app.add_handler(CommandHandler("unblock", unblock))
    app.add_handler(CommandHandler("setwelcome", setwelcome))

    app.add_handler(CallbackQueryHandler(button_handler, pattern="^send_msg$"))
    app.add_handler(CallbackQueryHandler(admin_reply_callback, pattern="^reply:"))
    app.add_handler(MessageHandler(filters.TEXT & filters.USER(get_admins()), admin_text))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), user_message))

    print("🤖 Bot is running...")
    app.run_polling()
