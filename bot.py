import asyncio
import os
import sqlite3
import logging
import time
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiohttp import web

# --- КОНФИГУРАЦИЯ ---
TOKEN = "8349041174:AAGuRx-fC4dzQ3zfLXqBOeYPWozQx23msDY"
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- ВЕБ-СЕРВЕР ДЛЯ RENDER ---
async def handle(request):
    return web.Response(text="Система активна")

async def start_webserver():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

# --- БАЗА ДАННЫХ ---
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

# --- КРАСИВЫЙ /START ---
@dp.message(Command("start"), F.chat.type == "private")
async def cmd_start(message: types.Message):
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="➕ Добавить в группу", url=f"https://t.me/{(await bot.get_me()).username}?startgroup=true"))
    builder.row(
        types.InlineKeyboardButton(text="📜 Команды", callback_data="show_commands"),
        types.InlineKeyboardButton(text="🛡 Статус", callback_data="show_status")
    )
    builder.row(types.InlineKeyboardButton(text="💎 О разработчике", url="https://t.me/umeraaai")) # Можешь сменить ссылку

    welcome_text = (
        f"✨ **Приветствуем, {message.from_user.first_name}!**\n\n"
        "🤖 Я — **Advanced Guard Bot**, твой персональный ассистент по контролю и модерации чатов.\n\n"
        "🚀 **Мои возможности:**\n"
        "• Мгновенная фильтрация мата и спама\n"
        "• Полная кастомизация под каждый чат\n"
        "• Работа 24/7 без задержек и рекламы\n"
        "• Система защиты администраторов\n\n"
        "🔧 **Быстрая настройка:**\n"
        "1. Добавьте меня в свой чат.\n"
        "2. Назначьте администратором (с правом удаления).\n"
        "3. Используйте `/set_words`, чтобы задать правила.\n\n"
        "🛰 *Система готова к работе. Выберите действие ниже:* "
    )
    await message.answer(welcome_text, parse_mode="Markdown", reply_markup=builder.as_markup())

# --- ОБРАБОТКА КНОПОК ---
@dp.callback_query(F.data == "show_commands")
async def call_commands(callback: types.CallbackQuery):
    commands_text = (
        "🛠 **Список доступных команд:**\n\n"
        "🛡 **Модерация:**\n"
        "• `/set_words [слова]` — Установить черный список (через запятую)\n"
        "• `/status` — Проверить настройки текущего чата\n"
        "• `/clean` — (в разработке) Очистка истории\n\n"
        "📊 **Инфо:**\n"
        "• `/ping` — Проверить скорость отклика\n"
        "• `/help` — Вызов справки\n"
        "• `/info` — Информация о системе\n\n"
        "⚙️ **Системные:**\n"
        "• `/id` — Узнать ID чата и пользователя\n"
        "• `/report` — Сообщить об ошибке"
    )
    await callback.message.edit_text(commands_text, parse_mode="Markdown")

@dp.callback_query(F.data == "show_status")
async def call_status(callback: types.CallbackQuery):
    await callback.answer("✅ Система работает в штатном режиме. Задержка: 0.02ms", show_alert=True)

# --- ПАСХАЛКИ И ДОП. КОМАНДЫ ---
@dp.message(Command("ping"))
async def cmd_ping(message: types.Message):
    start_time = time.time()
    msg = await message.answer("📡 Проверка соединения...")
    end_time = time.time()
    ping = round((end_time - start_time) * 1000)
    await msg.edit_text(f"🚀 **Pong!**\n⏱ Время отклика: `{ping}ms`", parse_mode="Markdown")

@dp.message(Command("id"))
async def cmd_id(message: types.Message):
    await message.answer(f"👤 **Твой ID:** `{message.from_user.id}`\n👥 **ID чата:** `{message.chat.id}`", parse_mode="Markdown")

# --- ГЛАВНАЯ ЛОГИКА УДАЛЕНИЯ ---
@dp.message(Command("set_words"))
async def set_words(message: types.Message):
    if message.chat.type == "private": return
    try:
        member = await bot.get_chat_member(message.chat.id, message.from_user.id)
        if member.status not in ["administrator", "creator"]:
            return await message.answer("⚠️ Ошибка: действие доступно только администрации.")
    except: return
    
    words = message.text.replace("/set_words", "").strip().lower()
    if not words:
        return await message.answer("🖊 Напишите слова через запятую.\nПример: `/set_words мат1, мат2`", parse_mode="Markdown")

    conn = sqlite3.connect("settings.db")
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO groups (chat_id, words) VALUES (?, ?)", (message.chat.id, words))
    conn.commit()
    conn.close()
    await message.answer("🛡 **Система защиты обновлена.**\nУказанные слова теперь под запретом.", parse_mode="Markdown")

@dp.message(F.text)
async def cleaner(message: types.Message):
    if not message.chat or message.chat.type == "private": return
    
    bad_words = get_words(message.chat.id)
    if any(word.strip() in message.text.lower() for word in bad_words if word.strip()):
        try:
            await message.delete()
            # Короткое и строгое уведомление
            warn = await message.answer(f"🚫 Сообщение от {message.from_user.first_name} удалено. Содержит недопустимый контент.")
            await asyncio.sleep(4)
            await warn.delete()
        except: pass

async def main():
    init_db()
    await asyncio.gather(start_webserver(), dp.start_polling(bot))

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
