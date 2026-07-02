import asyncio
import logging
import os
import sqlite3
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from aiogram.exceptions import TelegramAPIError

# ------------------- SOZLAMALAR -------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")          # Railway'da Environment Variables'ga qo'yiladi
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
DB_PATH = os.getenv("DB_PATH", "movies.db")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN topilmadi! Environment Variables'ga qo'shing.")

# ------------------- LOGGING -------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# ------------------- BAZA -------------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS movies (
            code TEXT PRIMARY KEY,
            file_id TEXT NOT NULL,
            title TEXT,
            added_at TEXT
        )
    """)
    conn.commit()
    conn.close()

def save_movie(code: str, file_id: str, title: str = ""):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO movies (code, file_id, title, added_at) VALUES (?, ?, ?, ?)",
        (code, file_id, title, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()

def get_movie(code: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT file_id, title FROM movies WHERE code = ?", (code,))
    row = cur.fetchone()
    conn.close()
    return row

def delete_movie(code: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM movies WHERE code = ?", (code,))
    deleted = cur.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def count_movies() -> int:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM movies")
    n = cur.fetchone()[0]
    conn.close()
    return n

# ------------------- BOT -------------------
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

# /start
@dp.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "Assalomu alaykum! 🎬\n\n"
        "Kino kodini yuboring, men sizga kinoni jo'nataman.\n"
        "Masalan: 0001"
    )

# /stats — faqat admin
@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    if not is_admin(message.from_user.id):
        return
    total = count_movies()
    await message.answer(f"📊 Bazada jami: {total} ta kino")

# /delete <kod> — faqat admin
@dp.message(Command("delete"))
async def cmd_delete(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Foydalanish: /delete 0001")
        return
    code = parts[1].strip()
    if delete_movie(code):
        await message.answer(f"✅ {code} o'chirildi")
    else:
        await message.answer("❌ Bunday kod topilmadi")

# Admin video yuborsa (caption = kod)
@dp.message(F.video)
async def handle_video(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("Kechirasiz, faqat kod yuborishingiz mumkin.")
        return

    caption = (message.caption or "").strip()
    if not caption:
        await message.answer(
            "⚠️ Video bilan birga caption'ga kod yozing.\n"
            "Masalan, videoni yuborayotganda pastiga: 0001"
        )
        return

    code = caption.split()[0]  # birinchi so'zni kod sifatida olamiz
    title = caption[len(code):].strip()
    file_id = message.video.file_id

    save_movie(code, file_id, title)
    await message.answer(f"✅ Saqlandi!\nKod: {code}\nNomi: {title or '-'}")
    logger.info(f"Yangi kino qo'shildi: {code} by {message.from_user.id}")

# Foydalanuvchi kod yuborsa
@dp.message(F.text)
async def handle_code(message: Message):
    code = message.text.strip()
    row = get_movie(code)

    if not row:
        await message.answer("❌ Bunday kod topilmadi. Kodni tekshirib qayta yuboring.")
        return

    file_id, title = row
    try:
        caption = title if title else None
        await message.answer_video(video=file_id, caption=caption)
    except TelegramAPIError as e:
        logger.error(f"Video yuborishda xato: {e}")
        await message.answer("⚠️ Kinoni yuborishda xatolik yuz berdi, birozdan so'ng qayta urinib ko'ring.")

# ------------------- ISHGA TUSHIRISH -------------------
async def main():
    init_db()
    logger.info("Bot ishga tushdi ✅")
    # Eski xabarlarni tashlab, faqat yangi update'larni oladi
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    while True:
        try:
            asyncio.run(main())
        except Exception as e:
            logger.error(f"Bot to'xtadi, qayta ishga tushirilmoqda: {e}")
            import time
            time.sleep(5)
