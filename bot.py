import asyncio
import os
import aiosqlite
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
DB_PATH = "homework.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS homework (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id BIGINT,
            subject TEXT,
            task TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        await db.commit()

async def add_homework(chat_id, subject, task):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('INSERT INTO homework (chat_id, subject, task) VALUES (?, ?, ?)',
                         (chat_id, subject.strip().title(), task.strip()))
        await db.commit()

async def get_latest_homework(chat_id, subjects):
    if not subjects: return {}
    placeholders = ','.join('?' for _ in subjects)
    query = f'SELECT subject, task FROM homework WHERE chat_id = ? AND subject IN ({placeholders}) ORDER BY created_at DESC'
    params = [chat_id] + [s.strip().title() for s in subjects]
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()

    latest = {}
    for subj, task in rows:
        if subj not in latest:
            latest[subj] = task
    return latest

def parse_input(text: str):
    lines = [l.strip() for l in text.strip().split('\n') if l.strip()]
    add_tasks = []
    query_subjects = []
    for line in lines:
        if ':' in line:
            s, t = line.split(':', 1)
            add_tasks.append((s.strip().title(), t.strip()))
        else:
            query_subjects.append(line.strip().title())
    return add_tasks, query_subjects

def get_scope_id(message):
    return message.chat.id if message.chat.type in ['group', 'supergroup'] else message.from_user.id

async def main():
    await init_db()
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    @dp.message(Command("start"))
    async def cmd_start(message: types.Message):
        await message.answer(
            "📚 *Бот для ДЗ*\n\n"
            "➕ *Добавить:* `Предмет: задание`\n"
            "🔍 *Узнать:* просто список предметов\n\n"
            "Примеры:\n"
            "`Математика: стр.45 №12-15`\n"
            "`Физика: параграф 10`\n\n"
            "Запрос ДЗ:\n"
            "`Математика`\n`Физика`\n`Русский язык`\n\n"
            "🗑 `/clear` — очистить все ДЗ в этом чате"
        )

    @dp.message(Command("clear"))
    async def cmd_clear(message: types.Message):
        scope = get_scope_id(message)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute('DELETE FROM homework WHERE chat_id = ?', (scope,))
            await db.commit()
        await message.answer("🗑 История ДЗ очищена.")

    @dp.message()
    async def handle_message(message: types.Message):
        if not message.text or message.text.startswith('/'):
            return

        add_tasks, query_subjects = parse_input(message.text)
        scope = get_scope_id(message)

        # 1. Добавление ДЗ
        if add_tasks:
            for subj, task in add_tasks:
                await add_homework(scope, subj, task)
            preview = "\n".join([f"✅ {s}: {t}" for s, t in add_tasks])
            return await message.answer(f"📝 *Добавлено:*\n{preview}")

        # 2. Запрос ДЗ по списку
        if query_subjects:
            latest = await get_latest_homework(scope, query_subjects)
            if not latest:
                return await message.answer("📭 Пока нет ДЗ по этим предметам. Сначала добавь их через `Предмет: задание`.")
            
            result = "📋 *Актуальное ДЗ:*\n\n"
            for subj in query_subjects:
                task = latest.get(subj)
                result += f"🔹 *{subj}*: {task}\n" if task else f"⚪ *{subj}*: не задано\n"
            return await message.answer(result)

        # 3. Формат не распознан
        await message.answer("⚠️ Напиши `Предмет: задание` для добавления или просто список предметов для проверки.")

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
