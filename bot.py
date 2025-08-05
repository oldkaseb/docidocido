import os
import json
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN")
INITIAL_ADMINS = os.getenv("INITIAL_ADMINS", "")

ADMINS_FILE = "admins.json"
BLOCKED_FILE = "blocked.json"
USERS_FILE = "users.json"
WELCOME_FILE = "welcome.json"

# ---------------------- ابزار ذخیره و خواندن فایل ----------------------
def load_json(path, default):
    if not os.path.exists(path):
        with open(path, 'w') as f:
            json.dump(default, f)
        return default
    with open(path, 'r') as f:
        return json.load(f)

def save_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)

# ---------------------- مدیریت فایل‌های دیتا ----------------------
def get_admins():
    admins = load_json(ADMINS_FILE, [])
    if INITIAL_ADMINS:
        admins += [int(i) for i in INITIAL_ADMINS.split(",") if i.isdigit()]
        admins = list(set(admins))
    return admins

def get_blocked():
    return load_json(BLOCKED_FILE, [])

def get_users():
    return load_json(USERS_FILE, [])

def get_welcome():
    return load_json(WELCOME_FILE, {"text": "سلام! به ربات دکتر گشاد خوش اومدی 🤖\nبرای ارسال پیام به ما دکمه زیر رو بزن 😁"})

# ---------------------- پیام خوش‌آمد ----------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    blocked = get_blocked()
    if user.id in blocked:
        return

    users = get_users()
    if user.id not in [u['id'] for u in users]:
        users.append({"id": user.id, "name": user.full_name, "username": user.username or "", "joined": str(datetime.now())})
        save_json(USERS_FILE, users)

    welcome = get_welcome()["text"]
    keyboard = [[InlineKeyboardButton("📝 ارسال پیام", callback_data="send")]]
    await update.message.reply_text(welcome, reply_markup=InlineKeyboardMarkup(keyboard))

# ---------------------- هندلر کلی برای callback ها ----------------------
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    blocked = get_blocked()
    if user_id in blocked:
        return

    if query.data == "send":
        await context.bot.send_message(chat_id=user_id, text="خب، منتظرم! پیامتو بنویس تا بفرستمش 🚀")
        context.user_data['awaiting_message'] = True

    elif query.data.startswith("reply:"):
        reply_to_user = int(query.data.split(":")[1])
        context.user_data['reply_to'] = reply_to_user
        await query.message.reply_text("پاسختو بنویس تا بفرستم ✉️")

# ---------------------- دریافت پیام از کاربر ----------------------
async def handle_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    blocked = get_blocked()
    if user.id in blocked:
        return

    if context.user_data.get('awaiting_message'):
        context.user_data['awaiting_message'] = False

        for admin_id in get_admins():
            keyboard = [[InlineKeyboardButton("✉️ پاسخ", callback_data=f"reply:{user.id}")]]
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"📩 پیام جدید از {user.full_name} (@{user.username or 'ندارد'})\n🆔 {user.id}:\n\n{update.message.text}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        await update.message.reply_text("پیامت ارسال شد! منتظر پاسخ باش 🌟")

# ---------------------- پاسخ ادمین ----------------------
async def admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id not in get_admins():
        return
    reply_to = context.user_data.get('reply_to')
    if reply_to:
        try:
            await context.bot.send_message(chat_id=reply_to, text=f"📬 پاسخ ادمین:\n{update.message.text}")
            await update.message.reply_text("✅ پیام ارسال شد")
        except:
            await update.message.reply_text("❌ ارسال پیام به کاربر ناموفق بود")
        context.user_data['reply_to'] = None

# ---------------------- کامندهای ادمین ----------------------
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in get_admins(): return
    users = get_users()
    msg = "📊 آمار کاربران:\n"
    for u in users:
        msg += f"- {u['name']} | {u['id']} | @{u['username']} | {u['joined']}\n"
    msg += f"\n👥 تعداد کل کاربران: {len(users)}"
    await update.message.reply_text(msg or "هیچ کاربری نیست")

async def addadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in get_admins(): return
    if context.args:
        new_id = int(context.args[0])
        admins = get_admins()
        admins.append(new_id)
        save_json(ADMINS_FILE, list(set(admins)))
        await update.message.reply_text(f"✅ ادمین جدید اضافه شد: {new_id}")

async def removeadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in get_admins(): return
    if context.args:
        rem_id = int(context.args[0])
        admins = get_admins()
        if rem_id in admins:
            admins.remove(rem_id)
            save_json(ADMINS_FILE, admins)
            await update.message.reply_text(f"❌ ادمین حذف شد: {rem_id}")

async def block(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in get_admins(): return
    if context.args:
        blocked = get_blocked()
        user_id = int(context.args[0])
        if user_id not in blocked:
            blocked.append(user_id)
            save_json(BLOCKED_FILE, blocked)
            await update.message.reply_text("✅ بلاک شد")

async def unblock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in get_admins(): return
    if context.args:
        blocked = get_blocked()
        user_id = int(context.args[0])
        if user_id in blocked:
            blocked.remove(user_id)
            save_json(BLOCKED_FILE, blocked)
            await update.message.reply_text("🔓 آنبلاک شد")

async def setwelcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in get_admins(): return
    if context.args:
        text = " ".join(context.args)
        save_json(WELCOME_FILE, {"text": text})
        await update.message.reply_text("✅ پیام خوش‌آمدگویی تنظیم شد")

async def forall(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in get_admins(): return
    if not update.message.reply_to_message:
        await update.message.reply_text("لطفاً روی پیامی ریپلای کن")
        return
    text = update.message.reply_to_message.text
    for u in get_users():
        try:
            await context.bot.send_message(chat_id=u['id'], text=text)
        except:
            continue
    await update.message.reply_text("📨 پیام همگانی ارسال شد")

async def help_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in get_admins(): return
    text = (
        "🛠 <b>دستورات مدیریت ربات:</b>\n\n"
        "/stats - نمایش آمار کاربران\n"
        "/addadmin [id] - افزودن ادمین جدید\n"
        "/removeadmin [id] - حذف ادمین\n"
        "/block [id] - بلاک کاربر\n"
        "/unblock [id] - آنبلاک کاربر\n"
        "/setwelcome [متن] - تنظیم پیام خوش‌آمد\n"
        "/forall - ارسال پیام همگانی (با ریپلای)\n"
    )
    await update.message.reply_text(text, parse_mode="HTML")

# ---------------------- اجرای ربات ----------------------
app = Application.builder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("stats", stats))
app.add_handler(CommandHandler("addadmin", addadmin))
app.add_handler(CommandHandler("removeadmin", removeadmin))
app.add_handler(CommandHandler("block", block))
app.add_handler(CommandHandler("unblock", unblock))
app.add_handler(CommandHandler("setwelcome", setwelcome))
app.add_handler(CommandHandler("forall", forall))
app.add_handler(CommandHandler("help", help_admin))

app.add_handler(CallbackQueryHandler(handle_callback))
app.add_handler(MessageHandler(filters.TEXT & filters.User(get_admins()), admin_text))
app.add_handler(MessageHandler(filters.TEXT & (~filters.User(get_admins())), handle_user))

print("ربات با موفقیت اجرا شد ✅")
app.run_polling()
