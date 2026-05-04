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

# ================= НАСТРОЙКИ =================
TOKEN = "ТВОЙ_ТОКЕН_ЗДЕСЬ"
bot = Bot(token=TOKEN)
dp = Dispatcher()

DEFAULT_BAD_WORDS = ["хуй", "пизд", "еблан", "сука", "блять", "пидор", "гандон", "лох", "даун", "чмо"]
TITLES = {
    -10: "Изгой 👤",
    0: "Новичок 🌱",
    10: "Местный 🏠",
    50: "Уважаемый 🎖",
    100: "Авторитет 🔥",
    500: "Легенда 👑",
    1000: "Бог чата ✨"
}

# ================= ВЕБ-СЕРВЕР (RENDER) =================
async def handle(request): return web.Response(text="ImbaMod System Online")
async def start_webserver():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    await web.TCPSite(runner, "0.0.0.0", port).start()

# ================= БАЗА ДАННЫХ =================
def init_db():
    conn = sqlite3.connect("imba.db")
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS groups (
        chat_id INTEGER PRIMARY KEY, 
        bad_words TEXT DEFAULT '', 
        anti_link INTEGER DEFAULT 0
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS users (
        chat_id INTEGER, user_id INTEGER, username TEXT, 
        karma INTEGER DEFAULT 0, warns INTEGER DEFAULT 0, 
        msg_count INTEGER DEFAULT 0, last_karma_time INTEGER DEFAULT 0,
        PRIMARY KEY (chat_id, user_id)
    )""")
    conn.commit()
    conn.close()

def db_query(sql, params=(), fetch=False):
    conn = sqlite3.connect("imba.db")
    cur = conn.cursor()
    try:
        cur.execute(sql, params)
        res = cur.fetchall() if fetch else None
        conn.commit()
        return res
    finally:
        conn.close()

# ================= ВСПОМОГАТЕЛЬНОЕ =================
async def is_admin(chat_id, user_id):
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in ["administrator", "creator"]
    except: return False

def get_title(karma):
    res = "Новичок 🌱"
    for k in sorted(TITLES.keys()):
        if karma >= k: res = TITLES[k]
    return res

# ================= КОМАНДЫ (ВЫСШИЙ ПРИОРИТЕТ) =================

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if message.chat.type != "private": return
    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(text="🚀 Добавить в чат", url=f"https://t.me/{(await bot.get_me()).username}?startgroup=true"))
    await message.answer("🦾 **ImbaMod v2.0 активирован!**\n\nЯ — твой ультимативный инструмент модерации.\nУдаляю мат, считаю карму, выдаю варны и строю топы.\n\nНапиши `/help` в чате, чтобы увидеть мощь.", parse_mode="Markdown", reply_markup=kb.as_markup())

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    text = (
        "📜 **Мануал ImbaMod:**\n\n"
        "👑 **Админка:**\n"
        "• `/warn` (в ответ) — +1 варн (3 = бан)\n"
        "• `/mute [мин]` — заткнуть юзера\n"
        "• `/ban` / `/unban` — бан/разбан\n"
        "• `/set_words [слово, слово]` — свои маты\n"
        "• `/anti_link` — переключатель ссылок\n\n"
        "🏆 **Карма и Стата:**\n"
        "• `+` или `-` (в ответ) — репутация\n"
        "• `/karma` — твой профиль или профиль друга\n"
        "• `/top` — топ-10 по карме\n"
        "• `/stats` — топ по сообщениям\n\n"
        "⚙️ **Прочее:**\n"
        "• `/ping` — отклик системы\n"
        "• `/id` — инфо по ID"
    )
    await message.answer(text, parse_mode="Markdown")

@dp.message(Command("id"))
async def cmd_id(message: types.Message):
    t_id = message.reply_to_message.from_user.id if message.reply_to_message else message.from_user.id
    await message.answer(f"🆔 **ID Пользователя:** `{t_id}`\n🆔 **ID Чата:** `{message.chat.id}`", parse_mode="Markdown")

@dp.message(Command("ping"))
async def cmd_ping(message: types.Message):
    s = time.time()
    m = await message.answer("📡 *Проверка узлов...*", parse_mode="Markdown")
    await m.edit_text(f"🚀 **Система стабильна!**\n⏱ Отклик: `{round((time.time()-s)*1000)}ms`", parse_mode="Markdown")

# ================= МОДЕРАЦИЯ =================

@dp.message(Command("warn"), F.reply_to_message)
async def cmd_warn(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id): return
    target = message.reply_to_message.from_user
    if target.is_bot: return

    db_query("INSERT INTO users (chat_id, user_id, username, warns) VALUES (?, ?, ?, 1) ON CONFLICT(chat_id, user_id) DO UPDATE SET warns=warns+1, username=?", (message.chat.id, target.id, target.first_name, target.first_name))
    res = db_query("SELECT warns FROM users WHERE chat_id=? AND user_id=?", (message.chat.id, target.id), True)
    warns = res[0][0]

    if warns >= 3:
        await bot.ban_chat_member(message.chat.id, target.id)
        db_query("UPDATE users SET warns=0 WHERE chat_id=? AND user_id=?", (message.chat.id, target.id))
        await message.answer(f"⛔️ **{target.first_name}** набрал 3/3 варна и был удален из чата!")
    else:
        await message.answer(f"⚠️ **{target.first_name}**, тебе выдан варн! ({warns}/3)")

@dp.message(Command("mute"), F.reply_to_message)
async def cmd_mute(message: types.Message, command: CommandObject):
    if not await is_admin(message.chat.id, message.from_user.id): return
    mins = int(command.args) if command.args and command.args.isdigit() else 15
    try:
        await bot.restrict_chat_member(message.chat.id, message.reply_to_message.from_user.id, ChatPermissions(can_send_messages=False), until_date=datetime.now()+timedelta(minutes=mins))
        await message.answer(f"🔇 **{message.reply_to_message.from_user.first_name}** отправлен в мут на {mins} мин.")
    except Exception as e: await message.answer(f"❌ Ошибка: {e}")

@dp.message(Command("ban"), F.reply_to_message)
async def cmd_ban(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id): return
    await bot.ban_chat_member(message.chat.id, message.reply_to_message.from_user.id)
    await message.answer(f"🚫 **{message.reply_to_message.from_user.first_name}** забанен.")

@dp.message(Command("unban"))
async def cmd_unban(message: types.Message, command: CommandObject):
    if not await is_admin(message.chat.id, message.from_user.id): return
    if not command.args: return await message.answer("Пиши: `/unban ID` или ответом на сообщение.")
    uid = int(command.args) if command.args.isdigit() else message.reply_to_message.from_user.id
    await bot.unban_chat_member(message.chat.id, uid, only_if_banned=True)
    await message.answer(f"✅ Пользователь `{uid}` разбанен.")

# ================= КАРМА И ТОПЫ =================

@dp.message(Command("karma"))
async def cmd_karma(message: types.Message):
    target = message.reply_to_message.from_user if message.reply_to_message else message.from_user
    res = db_query("SELECT karma, warns, msg_count FROM users WHERE chat_id=? AND user_id=?", (message.chat.id, target.id), True)
    k, w, m = res[0] if res else (0, 0, 0)
    await message.answer(f"👤 **Профиль: {target.first_name}**\n⭐ Карма: `{k}`\n🎖 Звание: `{get_title(k)}`\n⚠️ Варны: `{w}/3`\n✉️ Сообщений: `{m}`", parse_mode="Markdown")

@dp.message(Command("top"))
async def cmd_top(message: types.Message):
    rows = db_query("SELECT username, karma FROM users WHERE chat_id=? ORDER BY karma DESC LIMIT 10", (message.chat.id,), True)
    text = "🏆 **Топ кармы чата:**\n\n" + "\n".join([f"{i+1}. {r[0]} — `{r[1]}`" for i, r in enumerate(rows)])
    await message.answer(text, parse_mode="Markdown")

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    rows = db_query("SELECT username, msg_count FROM users WHERE chat_id=? ORDER BY msg_count DESC LIMIT 10", (message.chat.id,), True)
    text = "📊 **Самые активные:**\n\n" + "\n".join([f"{i+1}. {r[0]} — `{r[1]} шт.`" for i, r in enumerate(rows)])
    await message.answer(text, parse_mode="Markdown")

# ================= НАСТРОЙКИ ЧАТА =================

@dp.message(Command("set_words"))
async def set_words(message: types.Message, command: CommandObject):
    if not await is_admin(message.chat.id, message.from_user.id): return
    words = command.args if command.args else ""
    db_query("INSERT INTO groups (chat_id, bad_words) VALUES (?, ?) ON CONFLICT(chat_id) DO UPDATE SET bad_words=?", (message.chat.id, words, words))
    await message.answer(f"✅ Доп. фильтр слов обновлен.")

@dp.message(Command("anti_link"))
async def cmd_antilink(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id): return
    db_query("INSERT INTO groups (chat_id, anti_link) VALUES (?, 1) ON CONFLICT(chat_id) DO UPDATE SET anti_link = NOT anti_link", (message.chat.id,))
    res = db_query("SELECT anti_link FROM groups WHERE chat_id=?", (message.chat.id,), True)
    await message.answer(f"🔗 Анти-ссылка: {'✅ ВКЛ' if res[0][0] else '❌ ВЫКЛ'}")

# ================= ЛОГИКА ТЕКСТА (КАРМА И ФИЛЬТР) =================

@dp.message(F.text)
async def text_handler(message: types.Message):
    if not message.chat or message.chat.type == "private": return
    
    # Счётчик сообщений
    db_query("INSERT INTO users (chat_id, user_id, username, msg_count) VALUES (?, ?, ?, 1) ON CONFLICT(chat_id, user_id) DO UPDATE SET msg_count=msg_count+1, username=?", (message.chat.id, message.from_user.id, message.from_user.first_name, message.from_user.first_name))

    # Карма (проверка на + / -)
    if message.reply_to_message and not message.reply_to_message.from_user.is_bot:
        if message.text.strip() in ["+", "-", "👍", "👎", "респект", "фу"]:
            if message.reply_to_message.from_user.id == message.from_user.id:
                return await message.answer("самолюб?")
            
            # КД на карму
            now = int(time.time())
            u_data = db_query("SELECT last_karma_time FROM users WHERE chat_id=? AND user_id=?", (message.chat.id, message.from_user.id), True)
            if u_data and now - u_data[0][0] < 30: return
            
            diff = 1 if message.text.strip() in ["+", "👍", "респект"] else -1
            db_query("UPDATE users SET karma=karma+?, username=? WHERE chat_id=? AND user_id=?", (diff, message.reply_to_message.from_user.first_name, message.chat.id, message.reply_to_message.from_user.id))
            db_query("UPDATE users SET last_karma_time=? WHERE chat_id=? AND user_id=?", (now, message.chat.id, message.from_user.id))
            
            res = db_query("SELECT karma FROM users WHERE chat_id=? AND user_id=?", (message.chat.id, message.reply_to_message.from_user.id), True)
            await message.answer(f"{'📈' if diff>0 else '📉'} Карма **{message.reply_to_message.from_user.first_name}** стала: `{res[0][0]}`", parse_mode="Markdown")
            return

    # Фильтр мата и ссылок
    st = db_query("SELECT bad_words, anti_link FROM groups WHERE chat_id=?", (message.chat.id,), True)
    c_words = st[0][0].split(",") if st and st[0][0] else []
    a_link = st[0][1] if st else 0
    
    text = message.text.lower()
    is_bad = any(w.strip() in text for w in DEFAULT_BAD_WORDS + c_words if w.strip())
    is_link = ("t.me/" in text or "http" in text) if a_link else False

    if is_bad or is_link:
        if not await is_admin(message.chat.id, message.from_user.id):
            try:
                await message.delete()
                m = await message.answer(f"⛔️ {message.from_user.first_name}, твоё сообщение удалено!")
                await asyncio.sleep(3); await m.delete()
            except: pass

# ================= ЗАПУСК =================
async def main():
    init_db()
    logging.basicConfig(level=logging.INFO)
    await asyncio.gather(start_webserver(), dp.start_polling(bot))

if __name__ == "__main__":
    asyncio.run(main())
