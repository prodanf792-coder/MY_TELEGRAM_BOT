import os
import telebot
import psycopg2
from telebot import types

# ভেরিয়েবল থেকে টোকেন ও ডাটাবেজ নেওয়া
TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

bot = telebot.TeleBot(TOKEN)

# ডাটাবেজ কানেকশন
def get_db_connection():
    return psycopg2.connect(DATABASE_URL, sslmode='require')

# টেবিল তৈরি
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            balance INT DEFAULT 0,
            referred_by BIGINT
        )
    ''')
    conn.commit()
    cursor.close()
    conn.close()

try:
    init_db()
except Exception as e:
    print(f"Database Init Error: {e}")

# প্রধান মেন্যু
def main_menu():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn1 = types.KeyboardButton('📊 My Profile')
    btn2 = types.KeyboardButton('🔗 Invite Link')
    btn3 = types.KeyboardButton('🏆 Leaderboard')
    markup.add(btn1, btn2, btn3)
    return markup

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    username = message.from_user.username or f"User_{user_id}"
    
    args = message.text.split()
    referrer_id = None
    if len(args) > 1:
        try:
            referrer_id = int(args[1])
        except ValueError:
            pass

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
        user = cursor.fetchone()
        
        if not user:
            if referrer_id and referrer_id != user_id:
                cursor.execute("UPDATE users SET balance = balance + 1 WHERE user_id = %s", (referrer_id,))
                cursor.execute("INSERT INTO users (user_id, username, referred_by) VALUES (%s, %s, %s)", (user_id, username, referrer_id))
                try:
                    bot.send_message(referrer_id, f"🎉 আপনার লিংক থেকে নতুন একজন জয়েন করেছে! আপনি ১ পয়েন্ট পেয়েছেন।")
                except:
                    pass
            else:
                cursor.execute("INSERT INTO users (user_id, username) VALUES (%s, %s)", (user_id, username))
            conn.commit()
        
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Start command error: {e}")
    
    bot.send_message(message.chat.id, f"👋 স্বাগতম {username}! আমাদের রেফারেল বটে আপনাকে স্বাগতম।", reply_markup=main_menu())

@bot.message_handler(func=lambda message: True)
def handle_menu(message):
    user_id = message.from_user.id
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if message.text == '📊 My Profile':
            cursor.execute("SELECT balance FROM users WHERE user_id = %s", (user_id,))
            res = cursor.fetchone()
            balance = res[0] if res else 0
            bot.send_message(message.chat.id, f"👤 **আপনার প্রোফাইল**\n\n💰 মোট ব্যালেন্স: {balance} পয়েন্ট")
            
        elif message.text == '🔗 Invite Link':
            bot_info = bot.get_me()
            invite_link = f"https://t.me{bot_info.username}?start={user_id}"
            bot.send_message(message.chat.id, f"📢 **আপনার রেফারেল লিংক:**\n\n{invite_link}\n\nএই লিংকটি বন্ধুদের সাথে শেয়ার করুন। প্রতি রেফারে পাবেন ১ পয়েন্ট!")
            
        elif message.text == '🏆 Leaderboard':
            cursor.execute("SELECT username, balance FROM users ORDER BY balance DESC LIMIT 5")
            top_users = cursor.fetchall()
            text = "🏆 **শীর্ষ ৫ রেফারার:**\n\n"
            for i, u in enumerate(top_users, 1):
                text += f"{i}. @{u[0]} - {u[1]} পয়েন্ট\n"
            bot.send_message(message.chat.id, text)

        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Menu handle error: {e}")

print("Bot is running...")
bot.infinity_polling()
