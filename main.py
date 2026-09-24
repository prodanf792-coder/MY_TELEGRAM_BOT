import os
import telebot
import psycopg2
from telebot import types
from decimal import Decimal

=========================

SETTINGS

=========================

TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

ADMIN_ID = 7746782985

REFERRAL_REWARD = Decimal("0.05")
TASK_REWARD = Decimal("0.05")
MIN_WITHDRAW = Decimal("3.00")

bot = telebot.TeleBot(TOKEN)

=========================

DATABASE

=========================

def get_db_connection():
return psycopg2.connect(
DATABASE_URL,
sslmode="require"
)

def init_db():
conn = get_db_connection()
cursor = conn.cursor()

cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id BIGINT PRIMARY KEY,
        username TEXT,
        balance NUMERIC(12, 2) DEFAULT 0,
        referred_by BIGINT,
        referral_count INT DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        id SERIAL PRIMARY KEY,
        title TEXT NOT NULL,
        reward NUMERIC(12, 2) DEFAULT 0.05,
        link TEXT,
        active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS completed_tasks (
        user_id BIGINT,
        task_id INT,
        completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (user_id, task_id)
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS withdrawals (
        id SERIAL PRIMARY KEY,
        user_id BIGINT,
        amount NUMERIC(12, 2),
        method TEXT,
        account TEXT,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")

conn.commit()
cursor.close()
conn.close()

try:
init_db()
except Exception as e:
print("Database Init Error:", e)

=========================

MAIN MENU

=========================

def main_menu():
markup = types.ReplyKeyboardMarkup(
row_width=2,
resize_keyboard=True
)

markup.add(
    types.KeyboardButton("📊 My Profile"),
    types.KeyboardButton("🔗 Invite Link"),
    types.KeyboardButton("📋 Tasks"),
    types.KeyboardButton("💰 Balance"),
    types.KeyboardButton("💸 Withdraw"),
    types.KeyboardButton("🏆 Leaderboard")
)

return markup

=========================

START / REFERRAL

=========================

@bot.message_handler(commands=["start"])
def start(message):

user_id = message.from_user.id
username = message.from_user.username or f"User_{user_id}"

args = message.text.split()

referrer_id = None

if len(args) > 1:
    try:
        referrer_id = int(args[1])
    except ValueError:
        referrer_id = None

try:

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT user_id FROM users WHERE user_id = %s",
        (user_id,)
    )

    existing_user = cursor.fetchone()

    if not existing_user:

        # Create user
        cursor.execute("""
            INSERT INTO users
            (user_id, username, referred_by)
            VALUES (%s, %s, %s)
        """, (
            user_id,
            username,
            referrer_id if referrer_id != user_id else None
        ))

        # Give referral reward
        if referrer_id and referrer_id != user_id:

            cursor.execute("""
                UPDATE users
                SET
                    balance = balance + %s,
                    referral_count = referral_count + 1
                WHERE user_id = %s
            """, (
                REFERRAL_REWARD,
                referrer_id
            ))

            try:
                bot.send_message(
                    referrer_id,
                    f"🎉 নতুন referral!\n\n"
                    f"💰 আপনি পেয়েছেন {REFERRAL_REWARD} USDT"
                )
            except Exception:
                pass

        conn.commit()

    cursor.close()
    conn.close()

except Exception as e:
    print("Start Error:", e)

bot.send_message(
    message.chat.id,
    f"👋 স্বাগতম {username}!\n\n"
    f"🎁 Referral করলে পাবেন {REFERRAL_REWARD} USDT\n"
    f"📋 Task complete করলেও পাবেন {TASK_REWARD} USDT",
    reply_markup=main_menu()
)

=========================

PROFILE

=========================

@bot.message_handler(func=lambda message: message.text == "📊 My Profile")
def profile(message):

user_id = message.from_user.id

conn = get_db_connection()
cursor = conn.cursor()

cursor.execute("""
    SELECT username, balance, referral_count
    FROM users
    WHERE user_id = %s
""", (user_id,))

user = cursor.fetchone()

cursor.close()
conn.close()

if not user:
    bot.send_message(
        message.chat.id,
        "❌ আগে /start দিন।"
    )
    return

username, balance, referral_count = user

bot.send_message(
    message.chat.id,
    f"👤 Profile\n\n"
    f"Username: @{username}\n"
    f"💰 Balance: {balance} USDT\n"
    f"👥 Referrals: {referral_count}"
)

=========================

INVITE LINK

=========================

@bot.message_handler(func=lambda message: message.text == "🔗 Invite Link")
def invite_link(message):

user_id = message.from_user.id

bot_info = bot.get_me()

link = f"https://t.me/{bot_info.username}?start={user_id}"

bot.send_message(
    message.chat.id,
    f"🔗 আপনার Referral Link:\n\n"
    f"{link}\n\n"
    f"👥 প্রতি successful referral = {REFERRAL_REWARD} USDT"
)

=========================

BALANCE

=========================

@bot.message_handler(func=lambda message: message.text == "💰 Balance")
def balance(message):

user_id = message.from_user.id

conn = get_db_connection()
cursor = conn.cursor()

cursor.execute(
    "SELECT balance FROM users WHERE user_id = %s",
    (user_id,)
)

result = cursor.fetchone()

cursor.close()
conn.close()

balance_amount = result[0] if result else Decimal("0")

bot.send_message(
    message.chat.id,
    f"💰 আপনার Balance:\n\n"
    f"{balance_amount} USDT"
)

=========================

LEADERBOARD

=========================

@bot.message_handler(func=lambda message: message.text == "🏆 Leaderboard")
def leaderboard(message):

conn = get_db_connection()
cursor = conn.cursor()

cursor.execute("""
    SELECT username, referral_count
    FROM users
    ORDER BY referral_count DESC
    LIMIT 10
""")

users = cursor.fetchall()

cursor.close()
conn.close()

text = "🏆 Top Referrers\n\n"

if not users:
    text += "কোনো data নেই।"
else:
    for i, user in enumerate(users, 1):

        username = user[0] or "Unknown"
        referrals = user[1]

        text += f"{i}. @{username} — {referrals} referrals\n"

bot.send_message(
    message.chat.id,
    text
)

=========================

TASK LIST

=========================

@bot.message_handler(func=lambda message: message.text == "📋 Tasks")
def tasks(message):

user_id = message.from_user.id

conn = get_db_connection()
cursor = conn.cursor()

cursor.execute("""
    SELECT id, title, reward, link
    FROM tasks
    WHERE active = TRUE
    ORDER BY id DESC
""")

task_list = cursor.fetchall()

cursor.close()
conn.close()

if not task_list:

    bot.send_message(
        message.chat.id,
        "📋 এখন কোনো Task available নেই।"
    )

    return

for task_id, title, reward, link in task_list:

    markup = types.InlineKeyboardMarkup()

    if link:
        markup.add(
            types.InlineKeyboardButton(
                "🔗 Open Task",
                url=link
            )
        )

    markup.add(
        types.InlineKeyboardButton(
            "✅ Claim",
            callback_data=f"claim_{task_id}"
        )
    )

    bot.send_message(
        message.chat.id,
        f"📋 {title}\n\n"
        f"💰 Reward: {reward} USDT",
        reply_markup=markup
    )

=========================

CLAIM TASK

=========================

@bot.callback_query_handler(func=lambda call: call.data.startswith("claim_"))
def claim_task(call):

user_id = call.from_user.id
task_id = int(call.data.split("_")[1])

conn = get_db_connection()
cursor = conn.cursor()

cursor.execute("""
    SELECT id, reward
    FROM tasks
    WHERE id = %s AND active = TRUE
""", (task_id,))

task = cursor.fetchone()

if not task:

    cursor.close()
    conn.close()

    bot.answer_callback_query(
        call.id,
        "❌ Task পাওয়া যায়নি।",
        show_alert=True
    )

    return

cursor.execute("""
    SELECT user_id
    FROM completed_tasks
    WHERE user_id = %s AND task_id = %s
""", (
    user_id,
    task_id
))

already_completed = cursor.fetchone()

if already_completed:

    cursor.close()
    conn.close()

    bot.answer_callback_query(
        call.id,
        "⚠️ আপনি এই Task আগেই complete করেছেন।",
        show_alert=True
    )

    return

reward = task[1]

cursor.execute("""
    INSERT INTO completed_tasks
    (user_id, task_id)
    VALUES (%s, %s)
""", (
    user_id,
    task_id
))

cursor.execute("""
    UPDATE users
    SET balance = balance + %s
    WHERE user_id = %s
""", (
    reward,
    user_id
))

conn.commit()

cursor.close()
conn.close()

bot.answer_callback_query(
    call.id,
    f"🎉 আপনি {reward} USDT পেয়েছেন!",
    show_alert=True
)

=========================

WITHDRAW

=========================

@bot.message_handler(func=lambda message: message.text == "💸 Withdraw")
def withdraw_start(message):

user_id = message.from_user.id

conn = get_db_connection()
cursor = conn.cursor()

cursor.execute(
    "SELECT balance FROM users WHERE user_id = %s",
    (user_id,)
)

result = cursor.fetchone()

cursor.close()
conn.close()

balance_amount = result[0] if result else Decimal("0")

if balance_amount < MIN_WITHDRAW:

    bot.send_message(
        message.chat.id,
        f"❌ Minimum withdrawal {MIN_WITHDRAW} USDT.\n\n"
        f"আপনার বর্তমান balance: {balance_amount} USDT"
    )

    return

markup = types.InlineKeyboardMarkup()

markup.add(
    types.InlineKeyboardButton(
        "📱 bKash",
        callback_data="withdraw_bkash"
    ),
    types.InlineKeyboardButton(
        "📱 Nagad",
        callback_data="withdraw_nagad"
    )
)

markup.add(
    types.InlineKeyboardButton(
        "💵 USDT BEP20",
        callback_data="withdraw_bep20"
    )
)

bot.send_message(
    message.chat.id,
    "💸 Withdrawal method নির্বাচন করুন:",
    reply_markup=markup
)

=========================

WITHDRAW METHOD

=========================

@bot.callback_query_handler(
func=lambda call: call.data.startswith("withdraw_")
)
def withdraw_method(call):

method = call.data.replace(
    "withdraw_",
    ""
)

if method == "bep20":
    method_name = "USDT BEP20"

elif method == "bkash":
    method_name = "bKash"

else:
    method_name = "Nagad"

bot.answer_callback_query(call.id)

msg = bot.send_message(
    call.message.chat.id,
    f"💸 Method: {method_name}\n\n"
    f"আপনার {method_name} number/address পাঠান:"
)

bot.register_next_step_handler(
    msg,
    process_withdraw,
    method_name
)

=========================

PROCESS WITHDRAW

=========================

def process_withdraw(message, method_name):

user_id = message.from_user.id
account = message.text.strip()

conn = get_db_connection()
cursor = conn.cursor()

cursor.execute(
    "SELECT balance FROM users WHERE user_id = %s",
    (user_id,)
)

result = cursor.fetchone()

if not result:

    cursor.close()
    conn.close()

    bot.send_message(
        message.chat.id,
        "❌ User পাওয়া যায়নি।"
    )

    return

balance_amount = result[0]

if balance_amount < MIN_WITHDRAW:

    cursor.close()
    conn.close()

    bot.send_message(
        message.chat.id,
        "❌ আপনার balance minimum withdrawal-এর নিচে।"
    )

    return

amount = balance_amount

cursor.execute("""
    INSERT INTO withdrawals
    (user_id, amount, method, account)
    VALUES (%s, %s, %s, %s)
""", (
    user_id,
    amount,
    method_name,
    account
))

# Reserve balance
cursor.execute("""
    UPDATE users
    SET balance = 0
    WHERE user_id = %s
""", (user_id,))

conn.commit()

cursor.close()
conn.close()

bot.send_message(
    message.chat.id,
    f"✅ Withdrawal request submitted!\n\n"
    f"💰 Amount: {amount} USDT\n"
    f"💳 Method: {method_name}\n"
    f"📌 Status: Pending"
)

# Admin notification
try:

    bot.send_message(
        ADMIN_ID,
        f"🔔 New Withdrawal Request\n\n"
        f"👤 User ID: {user_id}\n"
        f"💰 Amount: {amount} USDT\n"
        f"💳 Method: {method_name}\n"
        f"📱 Account: {account}"
    )

except Exception as e:
    print("Admin notification error:", e)

=========================

ADMIN

=========================

@bot.message_handler(commands=["admin"])
def admin_panel(message):

if message.from_user.id != ADMIN_ID:

    bot.send_message(
        message.chat.id,
        "❌ আপনি Admin নন।"
    )

    return

bot.send_message(
    message.chat.id,
    "👑 Admin Panel\n\n"
    "বর্তমানে Admin panel-এর basic structure ready.\n"
    "পরের ধাপে Task Add/Delete এবং Withdrawal Approve/Reject যোগ করব।"
)

=========================

RUN BOT

=========================

print("Bot is running...")

bot.infinity_polling(
skip_pending=True
)
