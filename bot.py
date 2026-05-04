import asyncio
import os
import sqlite3
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiohttp import web

# ЗАМЕНИ ЭТОТ ТОКЕН НА СВОЙ
TOKEN = "8349041174:AAGuRx-fC4dzQ3zfLXqBOeYPWozQx23msDY"

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- Веб-сервер для того, чтобы Render не убивал бота ---
async def handle(request):
    return web.Response(text="Бот работает!")

async def start_webserver():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

# --- База данных ---
def init_db():
    conn = sqlite3.connect("settings.db")
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS groups (chat_id INTEGER PRIMARY KEY, words TEXT)")
    conn.commit()
    conn.close()

def get_words(chat_id):
    conn = sqlite3.connect("settings.db")
    cur = conn.cursor()
    cur.execute("SELECT words FROM groups WHERE chat_id = ?", (chat_id,))
    res = cur.fetchone()
    conn.close()
    return res[0].split(",") if res and res[0] else []

# --- Команды ---
@dp.message(Command("set_words"))
async def set_words(message: types.Message):
    if message.chat.type == "private": return
    try:
        member = await bot.get_chat_member(message.chat.id, message.from_user.id)
        if member.status not in ["administrator", "creator"]:
            return await message.answer("❌ Ты не админ.")
    except: return
    
    words = message.text.replace("/set_words", "").strip().lower()
    conn = sqlite3.connect("settings.db")
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO groups (chat_id, words) VALUES (?, ?)", (message.chat.id, words))
    conn.commit()
    conn.close()
    await message.answer(f"✅ Плохие слова для этого чата обновлены!")

@dp.message(F.text)
async def cleaner(message: types.Message):
    if not message.chat or message.chat.type == "private": return
    
    bad_words = get_words(message.chat.id)
    if any(word.strip() in message.text.lower() for word in bad_words if word.strip()):
        try:
            await message.delete()
        except: pass

async def main():
    init_db()
    # Запуск бота и веб-сервера одновременно
    await asyncio.gather(start_webserver(), dp.start_polling(bot))

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
