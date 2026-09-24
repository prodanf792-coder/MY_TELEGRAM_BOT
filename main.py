import os
import sqlite3
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
DB_NAME = "referral_bot.db"

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing!")

logging.basicConfig(level=logging.INFO)

def db():
    return sqlite3.connect(DB_NAME)

def init_db():
    con = db()
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            balance REAL DEFAULT 0,
            referrals INTEGER DEFAULT 0,
            referred_by INTEGER DEFAULT NULL,
            joined_at TEXT
        )
    """)
    con.commit()
    con.close()

def get_user(user_id):
    con = db()
    cur = con.cursor()
    cur.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    con.close()
    return row

def create_user(user_id, username, first_name, referred_by=None):
    con = db()
    cur = con.cursor()
    if referred_by == user_id:
        referred_by = None
    cur.execute("""
        INSERT OR IGNORE INTO users (user_id, username, first_name, balance, referrals, referred_by)
        VALUES (?, ?, ?, 0, 0, ?)
    """, (user_id, username or "", first_name or "", referred_by))
    con.commit()
    con.close()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ref = int(context.args[0]) if context.args and context.args[0].isdigit() else None
    create_user(user.id, user.username, user.first_name, ref)
    
    me = await context.bot.get_me()
    link = f"https://t.me/{me.username}?start={user.id}"
    text = f"Welcome, {user.first_name}!\n\nYour Referral Link:\n{link}"
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("My Referral", callback_data="referral")]
    ])
    await update.message.reply_text(text, reply_markup=keyboard)

async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    me = await context.bot.get_me()
    link = f"https://t.me/{me.username}?start={user_id}"
    row = get_user(user_id)
    await query.message.reply_text(f"Your Link:\n{link}\n\nReferrals: {row[4]}\nBalance: {row[3]:.2f} USDT")

def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callbacks))
    print("Bot Started Successfully!")
    app.run_polling()

if __name__ == "__main__":
    main()
