import asyncio
import os
import sqlite3
import logging
import time
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandObject
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import ChatPermissions
from aiohttp import web

# --- КОНФИГУРАЦИЯ ---
TOKEN = "8349041174:AAGuRx-fC4dzQ3zfLXqBOeYPWozQx23msDY"
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Константы
DEFAULT_BAD_WORDS = ["хуй", "пизд", "еблан", "сука", "блять", "пидор", "гандон", "лох", "даун"]
TITLES = {
    -10: "Изгой 👤",
    0: "Новичок 🌱",
    10: "Местный 🏠",
    50: "Уважаемый 🎖",
    100: "Авторитет 🔥",
    500: "Легенда 👑"
}

# --- ВЕБ-СЕРВЕР ДЛЯ RENDER ---
async def handle(request): return web.Response(text="ImbaMod System Online")
async def start_webserver():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    await web.TCPSite(runner, "0.0.0.0", port).start()

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect("imba.db")
    cur = conn.cursor()
    # Настройки групп
    cur.execute("""CREATE TABLE IF NOT EXISTS groups (
        chat_id INTEGER PRIMARY KEY, 
        bad_words TEXT, 
        welcome_msg TEXT DEFAULT 'Добро пожаловать!', 
        anti_link INTEGER DEFAULT 0
    )""")
    # Карма и стата
    cur.execute("""CREATE TABLE IF NOT EXISTS users (
        chat_id INTEGER, user_id INTEGER, username TEXT, 
        karma INTEGER DEFAULT 0, warns INTEGER DEFAULT 0, 
        msg_count INTEGER DEFAULT 0, last_karma_time INTEGER DEFAULT 0,
        PRIMARY KEY (chat_id, user_id)
    )""")
    conn.commit()
    conn.close()

# Универсальный запрос к БД
def db_query(sql, params=(), fetch=False):
    conn = sqlite3.connect("imba.db")
    cur = conn.cursor()
    cur.execute(sql, params)
    res = cur.fetchall() if fetch else None
    conn.commit()
    conn.close()
    return res

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def get_user_title(karma):
    res = "Новичок 🌱"
    for k, title in sorted(TITLES.items()):
        if karma >= k: res = title
    return res

async def is_admin(chat_id, user_id):
    member = await bot.get_chat_member(chat_id, user_id)
    return member.status in ["administrator", "creator"]

# --- ПРИВЕТСТВИЕ И СТАРТ ---
@dp.message(Command("start"), F.chat.type == "private")
async def cmd_start(message: types.Message):
    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(text="🚀 Добавить в чат", url=f"https://t.me/{(await bot.get_me()).username}?startgroup=true"))
    await message.answer(
        "🔮 **Привет! Я — ImbaMod.**\n\n"
        "Я создан, чтобы превратить твой чат в идеальное сообщество.\n"
        "❌ **Защита:** Удаление мата, ссылок, спама.\n"
        "📈 **Рейтинг:** Умная карма, звания и топ активных.\n"
        "🛠 **Админка:** Варны, муты и баны в одно касание.\n\n"
        "Добавь меня и напиши `/help` в чате!", 
        parse_mode="Markdown", reply_markup=kb.as_markup()
    )

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    text = (
        "📜 **Команды ImbaMod:**\n\n"
        "🛡 **Админка:**\n"
        "• `/warn` — выдать варн (3 варна = бан)\n"
        "• `/mute [мин]` — завалить ебало\n"
        "• `/ban` / `/unban` — управление доступом\n"
        "• `/set_words` — добавить свои маты\n"
        "• `/anti_link` — вкл/выкл запрет ссылок\n\n"
        "📊 **Статистика и Карма:**\n"
        "• `+` / `-` в ответ — изменить карму\n"
        "• `/karma` — твой профиль\n"
        "• `/top` — топ по карме\n"
        "• `/stats` — топ по сообщениям\n"
        "• `/id` / `/ping` — тех. инфо"
    )
    await message.answer(text, parse_mode="Markdown")

# --- СИСТЕМА КАРМЫ ---
@dp.message(F.text.regexp(r"^(\+|\-|респект|фу|👍|👎)$"), F.reply_to_message)
async def karma_logic(message: types.Message):
    target = message.reply_to_message.from_user
    if target.id == message.from_user.id: return
    if target.is_bot: return

    # Проверка КД (1 минута на выдачу кармы)
    now = int(time.time())
    user_data = db_query("SELECT last_karma_time FROM users WHERE chat_id=? AND user_id=?", (message.chat.id, message.from_user.id), True)
    if user_data and now - user_data[0][0] < 60:
        return await message.answer("⏳ Не так часто! Подожди минутку.")

    diff = 1 if message.text in ["+", "респект", "👍"] else -1
    db_query("""INSERT INTO users (chat_id, user_id, username, karma, last_karma_time) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(chat_id, user_id) DO UPDATE SET karma=karma+?, last_karma_time=?, username=?""",
             (message.chat.id, target.id, target.first_name, diff, 0, diff, now, target.first_name))
    
    db_query("UPDATE users SET last_karma_time=? WHERE chat_id=? AND user_id=?", (now, message.chat.id, message.from_user.id))
    
    new_karma = db_query("SELECT karma FROM users WHERE chat_id=? AND user_id=?", (message.chat.id, target.id), True)[0][0]
    await message.answer(f"⭐️ **{target.first_name}** ({diff}), текущая карма: `{new_karma}`\nЗвание: _{get_user_title(new_karma)}_", parse_mode="Markdown")

@dp.message(Command("karma"))
async def my_karma(message: types.Message):
    target = message.reply_to_message.from_user if message.reply_to_message else message.from_user
    data = db_query("SELECT karma, warns, msg_count FROM users WHERE chat_id=? AND user_id=?", (message.chat.id, target.id), True)
    k, w, m = data[0] if data else (0, 0, 0)
    await message.answer(
        f"👤 **Профиль: {target.first_name}**\n"
        f"⭐ Карма: `{k}`\n"
        f"🎖 Звание: `{get_user_title(k)}`\n"
        f"⚠️ Варны: `{w}/3`\n"
        f"✉️ Сообщений: `{m}`", parse_mode="Markdown"
    )

# --- МОДЕРАЦИЯ (ВАРНЫ, БАНЫ, МУТЫ) ---
@dp.message(Command("warn"), F.reply_to_message)
async def cmd_warn(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id): return
    target = message.reply_to_message.from_user
    
    db_query("INSERT INTO users (chat_id, user_id, username, warns) VALUES (?, ?, ?, 1) ON CONFLICT(chat_id, user_id) DO UPDATE SET warns=warns+1",
             (message.chat.id, target.id, target.first_name))
    
    warns = db_query("SELECT warns FROM users WHERE chat_id=? AND user_id=?", (message.chat.id, target.id), True)[0][0]
    
    if warns >= 3:
        await bot.ban_chat_member(message.chat.id, target.id)
        db_query("UPDATE users SET warns=0 WHERE chat_id=? AND user_id=?", (message.chat.id, target.id))
        await message.answer(f"🚫 **{target.first_name}** получил 3-й варн и был забанен!")
    else:
        await message.answer(f"⚠️ **{target.first_name}** предупрежден! ({warns}/3)")

@dp.message(Command("mute"), F.reply_to_message)
async def cmd_mute(message: types.Message, command: CommandObject):
    if not await is_admin(message.chat.id, message.from_user.id): return
    duration = int(command.args) if command.args and command.args.isdigit() else 15
    until = datetime.now() + timedelta(minutes=duration)
    await bot.restrict_chat_member(message.chat.id, message.reply_to_message.from_user.id, 
                                   ChatPermissions(can_send_messages=False), until_date=until)
    await message.answer(f"🔇 **{message.reply_to_message.from_user.first_name}** замучен на {duration} мин.")

# --- ФИЛЬТРЫ И СТАТИСТИКА ---
@dp.message(F.text)
async def main_filter(message: types.Message):
    if not message.chat or message.chat.type == "private": return
    
    # Считаем сообщение в стат
    db_query("INSERT INTO users (chat_id, user_id, username, msg_count) VALUES (?, ?, ?, 1) ON CONFLICT(chat_id, user_id) DO UPDATE SET msg_count=msg_count+1, username=?",
             (message.chat.id, message.from_user.id, message.from_user.first_name, message.from_user.first_name))

    # Проверка на мат и ссылки
    settings = db_query("SELECT bad_words, anti_link FROM groups WHERE chat_id=?", (message.chat.id,), True)
    custom_words = settings[0][0].split(",") if settings and settings[0][0] else []
    anti_link = settings[0][1] if settings else 0
    
    text = message.text.lower()
    is_bad = any(w in text for w in DEFAULT_BAD_WORDS + [x.strip() for x in custom_words if x.strip()])
    has_link = ("http://" in text or "https://" in text or "t.me/" in text) if anti_link else False

    if is_bad or has_link:
        if not await is_admin(message.chat.id, message.from_user.id):
            try:
                await message.delete()
                reason = "мат" if is_bad else "ссылка"
                tmp = await message.answer(f"⚠️ {message.from_user.first_name}, твое сообщение удалено ({reason}).")
                await asyncio.sleep(3); await tmp.delete()
            except: pass

# --- ТОПЫ ---
@dp.message(Command("top"))
async def cmd_top(message: types.Message):
    users = db_query("SELECT username, karma FROM users WHERE chat_id=? ORDER BY karma DESC LIMIT 10", (message.chat.id,), True)
    text = "🏆 **Топ по карме:**\n" + "\n".join([f"{i+1}. {u[0]} — `{u[1]}`" for i, u in enumerate(users)])
    await message.answer(text, parse_mode="Markdown")

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    users = db_query("SELECT username, msg_count FROM users WHERE chat_id=? ORDER BY msg_count DESC LIMIT 10", (message.chat.id,), True)
    text = "📊 **Самые активные сегодня:**\n" + "\n".join([f"{i+1}. {u[0]} — `{u[1]} сообщ.`" for i, u in enumerate(users)])
    await message.answer(text, parse_mode="Markdown")

# --- НАСТРОЙКИ ---
@dp.message(Command("anti_link"))
async def cmd_antilink(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id): return
    db_query("INSERT INTO groups (chat_id, anti_link) VALUES (?, 1) ON CONFLICT(chat_id) DO UPDATE SET anti_link = NOT anti_link", (message.chat.id,))
    state = db_query("SELECT anti_link FROM groups WHERE chat_id=?", (message.chat.id,), True)[0][0]
    await message.answer(f"🔗 Анти-ссылка: {'✅ ВКЛ' if state else '❌ ВЫКЛ'}")

@dp.message(Command("ping"))
async def cmd_ping(message: types.Message):
    s = time.time()
    m = await message.answer("⌛️")
    await m.edit_text(f"🚀 **ImbaMod Online**\nОтклик: `{round((time.time()-s)*1000)}ms`", parse_mode="Markdown")

# --- ЗАПУСК ---
async def main():
    init_db()
    logging.basicConfig(level=logging.INFO)
    await asyncio.gather(start_webserver(), dp.start_polling(bot))

if __name__ == "__main__":
    asyncio.run(main())
