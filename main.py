import sqlite3
import asyncio
import imaplib
import email
import logging
import io
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# --- 1. SOZLAMALAR ---
API_TOKEN = '8739411184:AAHWQCfFzXJEyqcyVZ4AbczJy0aL8c7h4TU'
ADMIN_ID = 6696934007

GMAIL_USER = 'r.sarvar1211@gmail.com' 
GMAIL_PASS = 'goekalnuogvhjezm' 

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# --- 2. BAZA ---
def init_db():
    conn = sqlite3.connect('bot_users.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                      (user_id INTEGER PRIMARY KEY, status TEXT, expire_date TEXT)''')
    conn.commit()
    conn.close()

def check_access(user_id):
    conn = sqlite3.connect('bot_users.db')
    cursor = conn.cursor()
    cursor.execute("SELECT status, expire_date FROM users WHERE user_id=?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    if user and user[0] == 'active':
        expire_dt = datetime.strptime(user[1], '%Y-%m-%d')
        if expire_dt > datetime.now():
            return True
    return False

# --- 3. MONITORING (GMAIL VA RASMLAR) ---
async def check_gmail_loop():
    while True:
        try:
            # TUZATILDI: Gmail server manzili
            mail = imaplib.IMAP4_SSL("imap.gmail.com")
            mail.login(GMAIL_USER, GMAIL_PASS)
            mail.select("inbox")
            
            status, data = mail.search(None, 'UNSEEN')
            
            if data[0]:
                for num in data[0].split():
                    _, msg_data = mail.fetch(num, '(RFC822)')
                    for response_part in msg_data:
                        if isinstance(response_part, tuple):
                            msg = email.message_from_bytes(response_part[1])
                            subject = str(msg.get("Subject", "Mavzu yo'q"))
                            from_ = str(msg.get("From", "Noma'lum"))
                            
                            # TUZATILDI: photo_data va rasm qidirish qismi to'g'ri surildi
                            photo_data = None
                            for part in msg.walk():
                                if part.get_content_maintype() == 'image':
                                    photo_data = part.get_payload(decode=True)
                                    break
                            
                            # Faol foydalanuvchilarni olish
                            conn = sqlite3.connect('bot_users.db')
                            cursor = conn.cursor()
                            cursor.execute("SELECT user_id FROM users WHERE status='active'")
                            active_users = cursor.fetchall()
                            conn.close()

                            for user in active_users:
                                try:
                                    caption = f"📝 **Mavzu:** {subject}"
                                    if photo_data:
                                        photo = io.BytesIO(photo_data)
                                        await bot.send_photo(user[0], photo, caption=caption)
                                    else:
                                        await bot.send_message(user[0], caption)
                                except Exception as e:
                                    logging.error(f"Xabar yuborishda xato: {e}")
            mail.logout()
        except Exception as e:
            logging.error(f"Gmail xatosi: {e}")
        
        await asyncio.sleep(20)

# --- 4. HANDLERLAR ---
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    if check_access(message.from_user.id):
        await message.answer("✅ Bot faol! Gmail'ga xat yoki rasm kelsa, darhol yuboraman.")
    else:
        kb = ReplyKeyboardMarkup(resize_keyboard=True).add(KeyboardButton("📱 Raqamni yuborish", request_contact=True))
        await message.answer("⚠️ Botdan foydalanish uchun raqamingizni qoldiring.", reply_markup=kb)

@dp.message_handler(content_types=['contact'])
async def handle_contact(message: types.Message):
    conn = sqlite3.connect('bot_users.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO users (user_id, status) VALUES (?, 'pending')", (message.from_user.id,))
    conn.commit()
    conn.close()
    await message.answer("Raxmat! To'lovdan so'ng xizmat yoqiladi.")
    await bot.send_message(ADMIN_ID, f"🔔 Yangi mijoz ID: `{message.from_user.id}`\nYoqish: `/ok {message.from_user.id}`", parse_mode="Markdown")

@dp.message_handler(commands=['ok'], user_id=ADMIN_ID)
async def activate(message: types.Message):
    target_id = message.get_args()
    if target_id:
        expire_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
        conn = sqlite3.connect('bot_users.db')
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET status='active', expire_date=? WHERE user_id=?", (expire_date, target_id))
        conn.commit()
        conn.close()
        await message.answer(f"✅ User {target_id} faollashtirildi.")
        await bot.send_message(target_id, "🎉 To'lovingiz tasdiqlandi!")
    else:
        await message.answer("❌ ID yozilmadi. Misol: `/ok 1234567`")

if __name__ == '__main__':
    init_db()
    loop = asyncio.get_event_loop()
    loop.create_task(check_gmail_loop())
    executor.start_polling(dp, skip_updates=True)
