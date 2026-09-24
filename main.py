import os
import sqlite3
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
REFERRAL_REWARD = float(os.getenv("REFERRAL_REWARD", "0.05"))
MIN_WITHDRAW = float(os.getenv("MIN_WITHDRAW", "5"))
DB_NAME = "referral_bot.db"

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing!")

logging.basicConfig(level=logging.INFO)
WD_AMOUNT, WD_METHOD, WD_ACCOUNT = range(3)

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
    cur.execute("""
        CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            method TEXT,
            account TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT
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
        INSERT INTO users (user_id, username, first_name, balance, referrals, referred_by, joined_at)
        VALUES (?, ?, ?, 0, 0, ?, ?)
    """, (user_id, username or "", first_name or "", referred_by, datetime.now().isoformat()))
    if referred_by:
        cur.execute("UPDATE users SET balance = balance + ?, referrals = referrals + 1 WHERE user_id=?", (REFERRAL_REWARD, referred_by))
    con.commit()
    con.close()

def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("My Referral", callback_data="referral"), InlineKeyboardButton("Balance", callback_data="balance")],
        [InlineKeyboardButton("Profile", callback_data="profile"), InlineKeyboardButton("Leaderboard", callback_data="leaderboard")],
        [InlineKeyboardButton("Withdraw", callback_data="withdraw"), InlineKeyboardButton("Help", callback_data="help")]
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not get_user(user.id):
        ref = int(context.args[0]) if context.args and context.args[0].isdigit() else None
        create_user(user.id, user.username, user.first_name, ref)
    
    me = await context.bot.get_me()
    link = f"https://t.me/{me.username}?start={user.id}"
    text = f"Welcome, {user.first_name}!\n\nInvite friends & earn USDT.\nReward: {REFERRAL_REWARD} USDT / referral\n\nYour Link:\n{link}"
    await update.message.reply_text(text, reply_markup=main_keyboard())

async def referral_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    me = await context.bot.get_me()
    row = get_user(user.id)
    link = f"https://t.me/{me.username}?start={user.id}"
    await update.message.reply_text(f"Your Referral Link:\n{link}\n\nReferrals: {row[4]}\nBalance: {row[3]:.2f} USDT", reply_markup=main_keyboard())

async def balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    row = get_user(update.effective_user.id)
    await update.message.reply_text(f"Balance: {row[3]:.2f} USDT\nReferrals: {row[4]}", reply_markup=main_keyboard())

async def profile_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    row = get_user(user.id)
    await update.message.reply_text(f"Profile:\nID: {user.id}\nName: {user.first_name}\nBalance: {row[3]:.2f} USDT\nReferrals: {row[4]}")

async def leaderboard_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    con = db()
    cur = con.cursor()
    cur.execute("SELECT first_name, referrals FROM users ORDER BY referrals DESC LIMIT 10")
    rows = cur.fetchall()
    con.close()
    text = "Leaderboard:\n" + "\n".join([f"{i+1}. {r[0]} - {r[1]} refs" for i, r in enumerate(rows)])
    await update.message.reply_text(text, reply_markup=main_keyboard())

async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "referral":
        await referral_cmd(update, context)
    elif query.data == "balance":
        await balance_cmd(update, context)
    elif query.data == "profile":
        await profile_cmd(update, context)
    elif query.data == "leaderboard":
        await leaderboard_cmd(update, context)
    elif query.data == "help":
        await query.message.reply_text("Help section: Use buttons to navigate.")

def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("referral", referral_cmd))
    app.add_handler(CommandHandler("balance", balance_cmd))
    app.add_handler(CommandHandler("profile", profile_cmd))
    app.add_handler(CommandHandler("leaderboard", leaderboard_cmd))
    app.add_handler(CallbackQueryHandler(callbacks))
    print("Bot Started Successfully!")
    app.run_polling()

if __name__ == "__main__":
    main()
