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

# =========================================================
# CONFIG
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

REFERRAL_REWARD = float(os.getenv("REFERRAL_REWARD", "0.05"))
MIN_WITHDRAW = float(os.getenv("MIN_WITHDRAW", "5"))

DB_NAME = "referral_bot.db"

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing!")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

# Withdrawal conversation states
WD_AMOUNT, WD_METHOD, WD_ACCOUNT = range(3)


# =========================================================
# DATABASE
# =========================================================

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

    cur.execute(
        "SELECT * FROM users WHERE user_id=?",
        (user_id,)
    )

    row = cur.fetchone()
    con.close()
    return row


def create_user(user_id, username, first_name, referred_by=None):
    con = db()
    cur = con.cursor()

    # Don't allow self-referral
    if referred_by == user_id:
        referred_by = None

    cur.execute("""
        INSERT INTO users
        (user_id, username, first_name, balance, referrals,
         referred_by, joined_at)
        VALUES (?, ?, ?, 0, 0, ?, ?)
    """, (
        user_id,
        username or "",
        first_name or "",
        referred_by,
        datetime.now().isoformat()
    ))

    # Give referral reward
    if referred_by:
        cur.execute("""
            UPDATE users
            SET balance = balance + ?,
                referrals = referrals + 1
            WHERE user_id=?
        """, (
            REFERRAL_REWARD,
            referred_by
        ))

    con.commit()
    con.close()


# =========================================================
# KEYBOARDS
# =========================================================

def main_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🔗 My Referral",
                callback_data="referral"
            ),
            InlineKeyboardButton(
                "💰 Balance",
                callback_data="balance"
            )
        ],
        [
            InlineKeyboardButton(
                "👤 Profile",
                callback_data="profile"
            ),
            InlineKeyboardButton(
                "🏆 Leaderboard",
                callback_data="leaderboard"
            )
        ],
        [
            InlineKeyboardButton(
                "💳 Withdraw",
                callback_data="withdraw"
            ),
            InlineKeyboardButton(
                "ℹ️ Help",
                callback_data="help"
            )
        ]
    ])


def admin_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📊 Statistics",
                callback_data="admin_stats"
            ),
            InlineKeyboardButton(
                "💳 Withdrawals",
                callback_data="admin_withdrawals"
            )
        ]
    ])


# =========================================================
# START
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    if not get_user(user.id):

        referred_by = None

        if context.args:
            try:
                referred_by = int(context.args[0])
            except ValueError:
                referred_by = None

        create_user(
            user.id,
            user.username,
            user.first_name,
            referred_by
        )

    text = f"""
╭━━━━━━━━━━━━━━━━━━━━╮
       🚀 WELCOME
╰━━━━━━━━━━━━━━━━━━━━╯

👋 Hello, {user.first_name}!

🎁 Invite friends & earn USDT

💎 Reward:
+{REFERRAL_REWARD:.2f} USDT / referral

💳 Minimum Withdrawal:
{MIN_WITHDRAW:.2f} USDT

👇 Select an option below:
"""

    await update.message.reply_text(
        text,
        reply_markup=main_keyboard()
    )


# =========================================================
# REFERRAL
# =========================================================

async def referral(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    me = await context.bot.get_me()

    link = (
        f"https://t.me/{me.username}"
        f"?start={user.id}"
    )

    row = get_user(user.id)

    referrals = row[4] if row else 0
    balance = float(row[3]) if row else 0

    text = f"""
╭━━━━━━━━━━━━━━━━━━━━╮
       🔗 YOUR REFERRAL
╰━━━━━━━━━━━━━━━━━━━━╯

🎁 Invite friends & earn USDT!

🔗 Your Referral Link:

{link}

👥 Referrals: {referrals}
💰 Balance: {balance:.2f} USDT

💎 Reward:
+{REFERRAL_REWARD:.2f} USDT / referral

🚀 Share your link and earn!
"""

    await update.message.reply_text(
        text,
        reply_markup=main_keyboard()
    )


# =========================================================
# BALANCE
# =========================================================

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user
    row = get_user(user.id)

    amount = float(row[3]) if row else 0
    referrals = row[4] if row else 0

    await update.message.reply_text(
        f"""
╭━━━━━━━━━━━━━━━━━━━━╮
        💰 BALANCE
╰━━━━━━━━━━━━━━━━━━━━╯

💵 Balance:
{amount:.2f} USDT

👥 Referrals:
{referrals}

🎁 Per Referral:
{REFERRAL_REWARD:.2f} USDT

📌 Minimum Withdrawal:
{MIN_WITHDRAW:.2f} USDT
""",
        reply_markup=main_keyboard()
    )


# =========================================================
# PROFILE
# =========================================================

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user
    row = get_user(user.id)

    balance_amount = float(row[3]) if row else 0
    referrals = row[4] if row else 0

    await update.message.reply_text(
        f"""
╭━━━━━━━━━━━━━━━━━━━━╮
        👤 PROFILE
╰━━━━━━━━━━━━━━━━━━━━╯

🆔 ID:
{user.id}

👤 Name:
{user.first_name}

🔖 Username:
@{user.username or "N/A"}

👥 Referrals:
{referrals}

💰 Balance:
{balance_amount:.2f} USDT
""",
        reply_markup=main_keyboard()
    )


# =========================================================
# LEADERBOARD
# =========================================================

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):

    con = db()
    cur = con.cursor()

    cur.execute("""
        SELECT first_name, referrals
        FROM users
        ORDER BY referrals DESC
        LIMIT 10
    """)

    rows = cur.fetchall()
    con.close()

    text = """
╭━━━━━━━━━━━━━━━━━━━━╮
       🏆 LEADERBOARD
╰━━━━━━━━━━━━━━━━━━━━╯

"""

    medals = ["🥇", "🥈", "🥉"]

    if not rows:
        text += "No users yet."

    for i, row in enumerate(rows):

        prefix = medals[i] if i < 3 else f"{i + 1}."

        text += (
            f"{prefix} {row[0]} — "
            f"{row[1]} referrals\n"
        )

    await update.message.reply_text(
        text,
        reply_markup=main_keyboard()
    )


# =========================================================
# HELP
# =========================================================

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        f"""
╭━━━━━━━━━━━━━━━━━━━━╮
          ℹ️ HELP
╰━━━━━━━━━━━━━━━━━━━━╯

/start
/referral
/balance
/profile
/leaderboard
/withdraw

🎁 Referral Reward:
{REFERRAL_REWARD:.2f} USDT

💳 Minimum Withdrawal:
{MIN_WITHDRAW:.2f} USDT

💳 Withdrawal Methods:
• bKash
• Binance
"""
    )


# =========================================================
# WITHDRAW START
# =========================================================

async def withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user
    row = get_user(user.id)

    balance_amount = float(row[3]) if row else 0

    if balance_amount < MIN_WITHDRAW:

        await update.message.reply_text(
            f"""
❌ WITHDRAWAL UNAVAILABLE

💰 Your Balance:
{balance_amount:.2f} USDT

📌 Minimum:
{MIN_WITHDRAW:.2f} USDT

You need:
{MIN_WITHDRAW - balance_amount:.2f} USDT more.
"""
        )

        return ConversationHandler.END

    await update.message.reply_text(
        f"""
💳 WITHDRAWAL

💰 Available:
{balance_amount:.2f} USDT

📌 Minimum:
{MIN_WITHDRAW:.2f} USDT

Enter withdrawal amount:
"""
    )

    return WD_AMOUNT


async def wd_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):

    try:
        amount = float(update.message.text.strip())
    except ValueError:

        await update.message.reply_text(
            "❌ Enter a valid number."
        )

        return WD_AMOUNT

    user = update.effective_user
    row = get_user(user.id)

    balance_amount = float(row[3]) if row else 0

    if amount < MIN_WITHDRAW:

        await update.message.reply_text(
            f"❌ Minimum withdrawal is "
            f"{MIN_WITHDRAW:.2f} USDT."
        )

        return WD_AMOUNT

    if amount > balance_amount:

        await update.message.reply_text(
            f"""
❌ Insufficient balance.

Your balance:
{balance_amount:.2f} USDT
"""
        )

        return WD_AMOUNT

    context.user_data["wd_amount"] = amount

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "💳 bKash",
                callback_data="wd_method_bkash"
            ),
            InlineKeyboardButton(
                "🟡 Binance",
                callback_data="wd_method_binance"
            )
        ]
    ])

    await update.message.reply_text(
        "💳 Select withdrawal method:",
        reply_markup=keyboard
    )

    return WD_METHOD


async def wd_method(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    method = (
        "bKash"
        if query.data == "wd_method_bkash"
        else "Binance"
    )

    context.user_data["wd_method"] = method

    await query.message.reply_text(
        f"""
💳 Method: {method}

📱 Enter your {method} number / UID:
"""
    )

    return WD_ACCOUNT


async def wd_account(update: Update, context: ContextTypes.DEFAULT_TYPE):

    account = update.message.text.strip()

    user = update.effective_user

    amount = float(
        context.user_data["wd_amount"]
    )

    method = context.user_data["wd_method"]

    row = get_user(user.id)
    balance_amount = float(row[3]) if row else 0

    if amount > balance_amount:

        await update.message.reply_text(
            "❌ Insufficient balance."
        )

        return ConversationHandler.END

    con = db()
    cur = con.cursor()

    # Deduct balance
    cur.execute("""
        UPDATE users
        SET balance = balance - ?
        WHERE user_id=?
    """, (
        amount,
        user.id
    ))

    # Create withdrawal
    cur.execute("""
        INSERT INTO withdrawals
        (user_id, amount, method, account,
         status, created_at)
        VALUES (?, ?, ?, ?, 'pending', ?)
    """, (
        user.id,
        amount,
        method,
        account,
        datetime.now().isoformat()
    ))

    withdrawal_id = cur.lastrowid

    con.commit()
    con.close()

    await update.message.reply_text(
        f"""
╭━━━━━━━━━━━━━━━━━━━━╮
    ✅ WITHDRAWAL SENT
╰━━━━━━━━━━━━━━━━━━━━╯

🆔 Request:
#{withdrawal_id}

💰 Amount:
{amount:.2f} USDT

💳 Method:
{method}

📱 Account:
{account}

⏳ Status:
Pending

Admin will process your request.
"""
    )

    # Notify admin
    if ADMIN_ID:

        try:

            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "✅ Approve",
                        callback_data=f"approve_{withdrawal_id}"
                    ),
                    InlineKeyboardButton(
                        "❌ Reject",
                        callback_data=f"reject_{withdrawal_id}"
                    )
                ]
            ])

            await context.bot.send_message(
                ADMIN_ID,
                f"""
🔔 NEW WITHDRAWAL

🆔 Request:
#{withdrawal_id}

👤 User:
{user.id}

💰 Amount:
{amount:.2f} USDT

💳 Method:
{method}

📱 Account:
{account}

⏳ Status:
PENDING
""",
                reply_markup=keyboard
            )

        except Exception as e:
            logging.error(
                f"Admin notification failed: {e}"
            )

    context.user_data.clear()

    return ConversationHandler.END


async def wd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):

    context.user_data.clear()

    await update.message.reply_text(
        "❌ Withdrawal cancelled."
    )

    return ConversationHandler.END


# =========================================================
# ADMIN
# =========================================================

def is_admin(user_id):
    return user_id == ADMIN_ID


async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not is_admin(update.effective_user.id):

        await update.message.reply_text(
            "⛔ Admin access only."
        )

        return

    await update.message.reply_text(
        """
╭━━━━━━━━━━━━━━━━━━━━╮
        👑 ADMIN PANEL
╰━━━━━━━━━━━━━━━━━━━━╯

Welcome Admin!

Manage your bot below.
""",
        reply_markup=admin_keyboard()
    )


# =========================================================
# ADMIN STATS
# =========================================================

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not is_admin(update.effective_user.id):
        return

    con = db()
    cur = con.cursor()

    cur.execute("SELECT COUNT(*) FROM users")
    users = cur.fetchone()[0]

    cur.execute(
        "SELECT COALESCE(SUM(referrals),0) FROM users"
    )
    referrals = cur.fetchone()[0]

    cur.execute(
        "SELECT COALESCE(SUM(balance),0) FROM users"
    )
    total_balance = float(cur.fetchone()[0])

    cur.execute("""
        SELECT COUNT(*)
        FROM withdrawals
        WHERE status='pending'
    """)

    pending = cur.fetchone()[0]

    con.close()

    await update.message.reply_text(
        f"""
📊 BOT STATISTICS

👥 Users:
{users}

🔗 Referrals:
{referrals}

💰 User Balance:
{total_balance:.2f} USDT

💳 Pending Withdrawals:
{pending}

🎁 Reward:
{REFERRAL_REWARD:.2f} USDT

📌 Minimum Withdraw:
{MIN_WITHDRAW:.2f} USDT
"""
    )


# =========================================================
# ADMIN WITHDRAWALS
# =========================================================

async def withdrawals(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not is_admin(update.effective_user.id):
        return

    con = db()
    cur = con.cursor()

    cur.execute("""
        SELECT id, user_id, amount, method, account
        FROM withdrawals
        WHERE status='pending'
        ORDER BY id DESC
        LIMIT 30
    """)

    rows = cur.fetchall()
    con.close()

    if not rows:

        await update.message.reply_text(
            "✅ No pending withdrawals."
        )

        return

    for row in rows:

        wid, uid, amount, method, account = row

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "✅ Approve",
                    callback_data=f"approve_{wid}"
                ),
                InlineKeyboardButton(
                    "❌ Reject",
                    callback_data=f"reject_{wid}"
                )
            ]
        ])

        await update.message.reply_text(
            f"""
💳 WITHDRAWAL #{wid}

👤 User:
{uid}

💰 Amount:
{amount:.2f} USDT

💳 Method:
{method}

📱 Account:
{account}

⏳ Pending
""",
            reply_markup=keyboard
        )


# =========================================================
# CALLBACKS
# =========================================================

async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = query.data

    # -----------------------------------------------------
    # USER
    # -----------------------------------------------------

    if data == "referral":

        me = await context.bot.get_me()

        link = (
            f"https://t.me/{me.username}"
            f"?start={user_id}"
        )

        row = get_user(user_id)

        balance_amount = float(row[3])
        referrals = row[4]

        await query.message.reply_text(
            f"""
🔗 YOUR REFERRAL

{link}

👥 Referrals:
{referrals}

💰 Balance:
{balance_amount:.2f} USDT

🎁 Reward:
{REFERRAL_REWARD:.2f} USDT/referral
"""
        )

    elif data == "balance":

        row = get_user(user_id)

        await query.message.reply_text(
            f"""
💰 BALANCE

{float(row[3]):.2f} USDT

👥 Referrals:
{row[4]}
"""
        )

    elif data == "profile":

        row = get_user(user_id)

        await query.message.reply_text(
            f"""
👤 PROFILE

🆔 ID: {user_id}

👤 Name:
{row[2]}

👥 Referrals:
{row[4]}

💰 Balance:
{float(row[3]):.2f} USDT
"""
        )

    elif data == "leaderboard":

        con = db()
        cur = con.cursor()

        cur.execute("""
            SELECT first_name, referrals
            FROM users
            ORDER BY referrals DESC
            LIMIT 10
        """)

        rows = cur.fetchall()
        con.close()

        text = "🏆 LEADERBOARD\n\n"

        for i, row in enumerate(rows, 1):

            text += (
                f"{i}. {row[0]} — "
                f"{row[1]} referrals\n"
            )

        await query.message.reply_text(text)

    elif data == "withdraw":

        row = get_user(user_id)

        balance_amount = float(row[3])

        if balance_amount < MIN_WITHDRAW:

            await query.message.reply_text(
                f"""
❌ Not enough balance.

💰 Balance:
{balance_amount:.2f} USDT

📌 Minimum:
{MIN_WITHDRAW:.2f} USDT
"""
            )

            return

        await query.message.reply_text(
            "Use /withdraw to start withdrawal."
        )

    elif data == "help":

        await query.message.reply_text(
            f"""
ℹ️ HELP

🎁 Referral:
{REFERRAL_REWARD:.2f} USDT

💳 Minimum Withdrawal:
{MIN_WITHDRAW:.2f} USDT

💳 Methods:
bKash / Binance
"""
        )

    # -----------------------------------------------------
    # ADMIN
    # -----------------------------------------------------

    elif data == "admin_stats":

        if is_admin(user_id):
            await stats(update, context)

    elif data == "admin_withdrawals":

        if is_admin(user_id):
            await withdrawals(update, context)

    # -----------------------------------------------------
    # APPROVE
    # -----------------------------------------------------

    elif data.startswith("approve_"):

        if not is_admin(user_id):
            return

        wid = int(data.split("_")[1])

        con = db()
        cur = con.cursor()

        cur.execute("""
            SELECT user_id, amount, status
            FROM withdrawals
            WHERE id=?
        """, (wid,))

        row = cur.fetchone()

        if not row:

            con.close()

            await query.edit_message_text(
                "❌ Withdrawal not found."
            )

            return

        target_user, amount, status = row

        if status != "pending":

            con.close()

            await query.edit_message_text(
                f"⚠️ Request #{wid} already processed."
            )

            return

        cur.execute("""
            UPDATE withdrawals
            SET status='approved'
            WHERE id=?
        """, (wid,))

        con.commit()
        con.close()

        await query.edit_message_text(
            f"""
✅ WITHDRAWAL APPROVED

Request: #{wid}
Amount: {amount:.2f} USDT

Please send the payment manually.
"""
        )

        try:

            await context.bot.send_message(
                target_user,
                f"""
✅ YOUR WITHDRAWAL WAS APPROVED

🆔 Request:
#{wid}

💰 Amount:
{amount:.2f} USDT

Your payment has been approved by admin.
"""
            )

        except Exception as e:
            logging.error(e)

    # -----------------------------------------------------
    # REJECT
    # -----------------------------------------------------

    elif data.startswith("reject_"):

        if not is_admin(user_id):
            return

        wid = int(data.split("_")[1])

        con = db()
        cur = con.cursor()

        cur.execute("""
            SELECT user_id, amount, status
            FROM withdrawals
            WHERE id=?
        """, (wid,))

        row = cur.fetchone()

        if not row:

            con.close()

            await query.edit_message_text(
                "❌ Withdrawal not found."
            )

            return

        target_user, amount, status = row

        if status != "pending":

            con.close()

            await query.edit_message_text(
                f"⚠️ Request #{wid} already processed."
            )

            return

        # Refund amount
        cur.execute("""
            UPDATE users
            SET balance = balance + ?
            WHERE user_id=?
        """, (
            amount,
            target_user
        ))

        cur.execute("""
            UPDATE withdrawals
            SET status='rejected'
            WHERE id=?
        """, (wid,))

        con.commit()
        con.close()

        await query.edit_message_text(
            f"""
❌ WITHDRAWAL REJECTED

Request: #{wid}

💰 {amount:.2f} USDT
was refunded to the user.
"""
        )

        try:

            await context.bot.send_message(
                target_user,
                f"""
❌ WITHDRAWAL REJECTED

🆔 Request:
#{wid}

💰 Amount:
{amount:.2f} USDT

The amount has been returned to your balance.
"""
            )

        except Exception as e:
            logging.error(e)


# =========================================================
# MAIN
# =========================================================

def main():

    init_db()

    app = (
        Application
        .builder()
        .token(BOT_TOKEN)
        .build()
    )

    # Basic commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("referral", referral))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("profile", profile))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(CommandHandler("help", help_command))

    # Admin
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(
        CommandHandler("withdrawals", withdrawals)
    )

    # Withdrawal conversation
    withdrawal_handler = ConversationHandler(
        entry_points=[
            CommandHandler("withdraw", withdraw)
        ],

        states={

            WD_AMOUNT: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    wd_amount
                )
            ],

            WD_METHOD: [
                CallbackQueryHandler(
                    wd_method,
                    pattern="^wd_method_"
                )
            ],

            WD_ACCOUNT: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    wd_account
                )
            ],
        },

        fallbacks=[
            CommandHandler("cancel", wd_cancel)
        ],

        allow_reentry=True
    )

    app.add_handler(withdrawal_handler)

    # Inline buttons
    app.add_handler(
        CallbackQueryHandler(callbacks)
    )

    print("🚀 Referral Bot Started!")

    app.run_polling()


if __name__ == "__main__":
    main()
