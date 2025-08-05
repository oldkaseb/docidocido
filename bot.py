import json
import os
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)

# مسیر فایل‌ها
USERS_FILE = 'data/users.json'
BLOCKED_FILE = 'data/blocked.json'
ADMINS_FILE = 'data/admins.json'
WELCOME_FILE = 'data/welcome.json'

# توکن ربات از ENV
BOT_TOKEN = os.getenv("BOT_TOKEN")

# اگر ENV برای adminها تعریف شده، آن‌ها را به فایل json اضافه کن
initial_admins = os.getenv("INITIAL_ADMINS", "")
if initial_admins:
    try:
        ids = [int(i.strip()) for i in initial_admins.split(",")]
        if os.path.exists(ADMINS_FILE):
            with open(ADMINS_FILE, 'r') as f:
                existing = json.load(f)
        else:
            existing = []
        updated = list(set(existing + ids))
        with open(ADMINS_FILE, 'w') as f:
            json.dump(updated, f)
    except Exception as e:
        print("خطا در بارگذاری اولیه ادمین‌ها:", e)

# توابع کمکی
def load_json(path, default):
    if not os.path.exists(path):
        with open(path, 'w') as f: json.dump(default, f)
        return default
    with open(path, 'r') as f: return json.load(f)

def save_json(path, data):
    with open(path, 'w') as f: json.dump(data, f)

def get_admins():
    return load_json(ADMINS_FILE, [])

def is_admin(user_id):
    return user_id in get_admins()

def get_welcome():
    return load_json(WELCOME_FILE, "سلام! برای ارتباط با ادمین، روی دکمه زیر کلیک کن 😊")

def block_user(user_id):
    blocked = load_json(BLOCKED_FILE, [])
    if user_id not in blocked:
        blocked.append(user_id)
        save_json(BLOCKED_FILE, blocked)

def unblock_user(user_id):
    blocked = load_json(BLOCKED_FILE, [])
    if user_id in blocked:
        blocked.remove(user_id)
        save_json(BLOCKED_FILE, blocked)

def is_blocked(user_id):
    return user_id in load_json(BLOCKED_FILE, [])

# پیام استارت
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    users = load_json(USERS_FILE, {})
    if str(user.id) not in users:
        users[str(user.id)] = {
            "name": user.full_name,
            "username": user.username,
            "start_time": datetime.now().isoformat()
        }
        save_json(USERS_FILE, users)

    keyboard = [[InlineKeyboardButton("✉️ ارسال پیام", callback_data="send_message")]]
    await update.message.reply_text(get_welcome(), reply_markup=InlineKeyboardMarkup(keyboard))

# دریافت درخواست کاربر
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    if query.data == "send_message":
        if is_blocked(user_id):
            await query.message.reply_text("شما توسط ادمین مسدود شده‌اید.")
        else:
            context.user_data["awaiting_message"] = True
            await query.message.reply_text("پیامتو بنویس تا برسونم به ادمین‌ها 📩")

    elif query.data.startswith("reply_"):
        uid = int(query.data.split("_")[1])
        context.user_data["reply_to"] = uid
        await query.message.reply_text("پاسخت رو بنویس تا برای کاربر ارسال بشه:")

    elif query.data.startswith("new_"):
        uid = int(query.data.split("_")[1])
        context.user_data["reply_to"] = uid
        await query.message.reply_text("پاسخ جدیدت رو بنویس:")

# پیام از کاربر
async def handle_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if is_blocked(user.id): return

    if context.user_data.get("awaiting_message"):
        context.user_data["awaiting_message"] = False
        msg = update.message.text

        admins = get_admins()
        for admin_id in admins:
            try:
                keyboard = [[
                    InlineKeyboardButton("✉️ پاسخ", callback_data=f"reply_{user.id}")
                ]]
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=f"📨 پیام از {user.full_name} (@{user.username or 'بدون'}):\n\n{msg}",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            except Exception:
                continue

        await update.message.reply_text("✅ پیامت فرستاده شد. به‌زودی جوابتو دریافت می‌کنی.")
        keyboard = [[InlineKeyboardButton("✉️ ارسال پیام جدید", callback_data="send_message")]]
        await update.message.reply_text("اگه پیام دیگه‌ای داری، دکمه زیر رو بزن 👇", reply_markup=InlineKeyboardMarkup(keyboard))

# پیام از ادمین
async def admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id): return

    if "reply_to" in context.user_data:
        target = context.user_data.pop("reply_to")
        try:
            await context.bot.send_message(chat_id=target, text=update.message.text)
            await update.message.reply_text("✅ پاسخ فرستاده شد.")
            keyboard = [[InlineKeyboardButton("✉️ پاسخ جدید", callback_data=f"new_{target}")]]
            await update.message.reply_text("اگه هنوز تموم نشده، از دکمه زیر استفاده کن 👇", reply_markup=InlineKeyboardMarkup(keyboard))
        except Exception as e:
            await update.message.reply_text(f"❌ خطا در ارسال پیام: {e}")

# آمار
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    users = load_json(USERS_FILE, {})
    text = "📊 آمار کاربران:\n"
    for uid, data in users.items():
        text += f"- {data['name']} (@{data['username'] or 'بدون'}) | {uid} | {data['start_time']}\n"
    await update.message.reply_text(text or "کاربری ثبت نشده.")

# پیام همگانی
async def forall(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    if not update.message.reply_to_message:
        await update.message.reply_text("روی پیام مورد نظر ریپلای بزن.")
        return

    text = update.message.reply_to_message.text
    users = load_json(USERS_FILE, {})
    count = 0
    for uid in users:
        try:
            await context.bot.send_message(chat_id=int(uid), text=text)
            count += 1
        except: pass
    await update.message.reply_text(f"✅ ارسال شد برای {count} کاربر.")

# افزودن ادمین
async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    try:
        new_id = int(context.args[0])
        admins = get_admins()
        if new_id not in admins:
            admins.append(new_id)
            save_json(ADMINS_FILE, admins)
            await update.message.reply_text("✅ ادمین جدید اضافه شد.")
        else:
            await update.message.reply_text("از قبل ادمین بود.")
    except:
        await update.message.reply_text("❌ آیدی عددی معتبر وارد کن.")

# حذف ادمین
async def remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    try:
        rm_id = int(context.args[0])
        admins = get_admins()
        if rm_id in admins:
            admins.remove(rm_id)
            save_json(ADMINS_FILE, admins)
            await update.message.reply_text("✅ ادمین حذف شد.")
        else:
            await update.message.reply_text("این آیدی ادمین نیست.")
    except:
        await update.message.reply_text("❌ آیدی عددی معتبر وارد کن.")

# بلاک و آنبلاک
async def block(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    try:
        block_user(int(context.args[0]))
        await update.message.reply_text("✅ بلاک شد.")
    except:
        await update.message.reply_text("❌ آیدی عددی بده.")

async def unblock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    try:
        unblock_user(int(context.args[0]))
        await update.message.reply_text("✅ آزاد شد.")
    except:
        await update.message.reply_text("❌ آیدی عددی بده.")

# تنظیم پیام خوش‌آمد
async def set_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    new_text = update.message.text.split(None, 1)[1]
    save_json(WELCOME_FILE, new_text)
    await update.message.reply_text("✅ پیام خوش‌آمد تغییر کرد.")

# راهنما
async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    text = (
        "/stats - آمار کاربران\n"
        "/forall - پیام همگانی (با ریپلای)\n"
        "/addadmin <id>\n"
        "/removeadmin <id>\n"
        "/block <id>\n"
        "/unblock <id>\n"
        "/setwelcome <text>\n"
    )
    await update.message.reply_text(text)

# اجرای اصلی
if __name__ == "__main__":
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.User(get_admins())), handle_user))
    app.add_handler(MessageHandler(filters.TEXT & filters.User(get_admins()), admin_text))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("forall", forall))
    app.add_handler(CommandHandler("addadmin", add_admin))
    app.add_handler(CommandHandler("removeadmin", remove_admin))
    app.add_handler(CommandHandler("block", block))
    app.add_handler(CommandHandler("unblock", unblock))
    app.add_handler(CommandHandler("setwelcome", set_welcome))
    app.add_handler(CommandHandler("help", help_cmd))
    app.run_polling()
