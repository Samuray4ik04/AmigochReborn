# TODO: разделение на модули. ЖЕЛАТЕЛЬНО облегчить код


import json
import asyncio
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from dotenv import load_dotenv
import google.generativeai as genai
import logging
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InlineQuery
from logging.handlers import RotatingFileHandler
import datetime
import sys




# ===|Settings|===
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()

prompt = """
Ты можешь использовать следующие HTML-теги в сообщениях Telegram:

<b>…</b> — жирный текст
<i>…</i> — курсив
<u>…</u> — подчёркнутый текст
<s>…</s> — зачёркнутый текст
<code>…</code> — моноширный (inline code)
<pre><code class="language-python">…</code></pre> — блок кода (с возможностью указать язык)
<tg-spoiler>…</tg-spoiler> — скрытый текст (спойлер)

⚠️ Правила использования:
1. Не злоупотребляй тегами — используй только там, где это действительно улучшает восприятие.
2. Избегай вложенности тегов, кроме простых случаев (например, <b><i>текст</i></b>).
3. Новые строки создавай через \\n, а не через <br>.
4. Сообщение должно корректно отображаться Telegram-клиентом и не вызывать ошибок.

Цель: формировать чистые, понятные и безопасные сообщения с использованием HTML-разметки.
"""


# idk why i need this lol
master = [1078401181] # yea that's me :D

# ===|LOGS|===
class CustomFormatter(logging.Formatter):
    """Кастомный форматтер для разных уровней логов"""
    
    FORMATS = {
        logging.DEBUG: "%(asctime)s | 👃 %(levelname)s 👃 | %(message)s",
        logging.INFO: "%(asctime)s | %(levelname)s | %(message)s",
        logging.WARNING: "%(asctime)s | ⚠️ %(levelname)s ⚠️ | %(message)s",
        logging.ERROR: "%(asctime)s | 🔴 %(levelname)s 🔴 | %(message)s",
        logging.CRITICAL: "          ================\n%(asctime)s | ⛔ %(levelname)s ⛔ | %(message)s\n          ================"
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, datefmt="%H:%M:%S")
        return formatter.format(record)

# Настройка handler'а с кастомным форматтером
handler = logging.StreamHandler()
handler.setFormatter(CustomFormatter())

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(handler)
# Отключаем передачу логов родительскому логгеру
logger.propagate = False


os.makedirs("logs", exist_ok=True)

# Очистка старых логов
log_files = [f for f in os.listdir("logs") if f.startswith("bot_") and f.endswith(".log")]
if len(log_files) >= 3:
    # Сортируем файлы по времени создания (старые в начале)
    log_files.sort(key=lambda f: os.path.getctime(os.path.join("logs", f)))
    # Удаляем самый старый файл
    oldest_log = os.path.join("logs", log_files[0])
    os.remove(oldest_log)

start_time = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
log_filename = f"logs/bot_{start_time}.log"

logger = logging.getLogger("bot_logger")
logger.setLevel(logging.DEBUG)

logger.handlers.clear()

file_handler = logging.FileHandler(log_filename, encoding="utf-8")
file_handler.setFormatter(CustomFormatter())
logger.addHandler(file_handler)

console_handler = logging.StreamHandler()
console_handler.setFormatter(CustomFormatter())
logger.addHandler(console_handler)

logger.propagate = False

logger.info(f"📂 Logging started — file: {log_filename}")
if len(log_files) >= 3:
    logger.info(f"🗑️ Removed old log file: {log_files[0]}")

def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        logger.info("🛑 Bot stopped manually")
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

sys.excepthook = handle_exception



# ===|AI memory|===
memory_file = "memory.json"

def load_memory():
    if not os.path.exists(memory_file):
        return {}
    with open(memory_file, "r", encoding="utf-8") as f:
        return json.load(f)

def save_memory(memory):
    with open(memory_file, "w", encoding="utf-8") as f:
        json.dump(memory, f, ensure_ascii=False, indent=2)

memory = load_memory()



# ===|Ask GenAI|===
async def ask_gemini(chat_id: int, user_message: str):
    history = memory.get(str(chat_id), [])

    # new message to history
    history.append({"role": "user", "parts": user_message})

    # answer generate
    model = genai.GenerativeModel("gemini-2.5-flash-lite", system_instruction=prompt)
    response = model.generate_content(history)

    # save to memory
    history.append({"role": "model", "parts": response.text})
    memory[str(chat_id)] = history[-50:]  # keep only last 50 messages
    save_memory(memory)

    return response.text



# ===|Handlers|===
@dp.message(Command("start")) 
async def start(message: types.Message):
    user = message.from_user
    logger.debug(f"One of admins ({user.username}) started the bot. (start command)")
    if user.id in master:
        await message.answer(f"Hi @{user.username} / <a href='{user.id}'>{user.first_name}</a>! This is a test bot", parse_mode="HTML")
        await asyncio.sleep(0.5)
        await message.reply("Glad to see you, master", parse_mode="HTML")
    else:
        logger.critical(f"@{user.username} / {user.id} started the bot without permission.")
        await message.reply(f"Yo, how you find me <a href='tg://user?id={user.id}'>{user.full_name}</a>?", parse_mode="HTML")


@dp.message(Command("clear"))
async def clear(message: types.Message):
    user = message.from_user
    logger.debug(f"One of admins ({user.username}) requested memory clear. (clear command)")
    if user.id in master:
        memory.pop(str(message.chat.id), None)
        save_memory(memory)
        await message.answer("🧽 Memory cleared.")
    else:
        logger.critical(f"@{user.username} / {user.id} tried to clear memory.")
        await message.reply("<b>Get off me!</b>", parse_mode="HTML")


@dp.message(Command("stop"))
async def stop(message: types.Message):
    user = message.from_user
    if user.id == master[0]:
        logger.debug(f"You ({user.username}) stopped the bot. (stop command)")
        await message.answer("🛑 Bot stopped.\n\n<b>Check the panel</b>", parse_mode="HTML")

        await bot.session.close()
        os._exit(0)
    else:
        logger.critical(f"@{user.username} / {user.id} tried to stop the bot without permission.")


@dp.message(Command("admpanel"))
async def ap(message: types.Message):
    user = message.from_user
    if user.id == master[0]:
        logger.debug(f"You ({user.username}) opened the admin panel.")
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="========= Chats =========", callback_data="void"),
            ],
            [
                InlineKeyboardButton(text="🧽 Clear Memory for All", callback_data="ap_clear_memory"),
                InlineKeyboardButton(text="📊 Stats", callback_data="ap_stats")
            ],
            [
                InlineKeyboardButton(text="========= Bot =========", callback_data="void"),
            ],
            [
                InlineKeyboardButton(text="📂 Logs", callback_data="ap_logs"),
                InlineKeyboardButton(text="🛑 Stop Bot", callback_data="ap_stop")
            ]
        ])

        await message.answer(
            "🛠️ <b>Admin Panel</b>\n\n"
            "Select an action from the menu below:",
            parse_mode="HTML",
            reply_markup=keyboard
        )
    else:
        logger.critical(f"@{user.username} / {user.id} tried to access the admin panel without permission.")
        await message.reply("<b>Get off me!</b>", parse_mode="HTML")


@dp.message()
async def chat(message: types.Message):
    user = message.from_user
    logger.debug(f"Message from (@{user.username}) [{user.id}]: {message.text}")
    if user.id in master:

        reply = await ask_gemini(message.chat.id, message.text)
        await message.reply(reply, parse_mode="HTML")
    else:
        logger.critical(f"@{user.username} / {user.id} used the bot without permission.")
        await message.reply("<b>Get off me!</b>", parse_mode="HTML")



# ===|AP Callbacks|===
@dp.callback_query(lambda c: c.data.startswith("ap_"))
async def ap_callbacks(callback: types.CallbackQuery):
    user = callback.from_user
    action = callback.data.split("_")[1]

    if action == "clear_memory":
        memory.clear()
        save_memory(memory)
        logger.debug(f"All memory cleared.")
        await callback.answer("🧽 Memory cleared.", show_alert=True)

    elif action == "stats":
        total_users = len(memory.keys())
        stats_text = f"Total users: {total_users}\n"
        await callback.answer(stats_text, show_alert=True)

    # We need send file of logs
    elif action == "logs":
        try:
            files = [f for f in os.listdir("logs") if f.startswith("bot_") and f.endswith(".log")]
            if not files:
                await callback.answer("❌ Логи не найдены.", show_alert=True)
                return

            latest_log = max(files, key=lambda f: os.path.getctime(os.path.join("logs", f)))
            log_path = os.path.join("logs", latest_log)

            logger.debug(f"📤 Sending log file: {latest_log}")
            await callback.message.answer_document(
                document=types.FSInputFile(log_path),
                caption=f"📄 Лог-файл: <code>{latest_log}</code>",
                parse_mode="HTML"
            )

            await callback.answer("✅ Лог отправлен.")
        except Exception as e:
            logger.error(f"Failed to send logs: {e}")
            await callback.answer("⚠️ Ошибка при отправке логов.", show_alert=True)

    elif action == "stop":
        await callback.answer("🛑 Stopping bot...", show_alert=True)
        logger.debug(f"{user.username} stopped the bot.")
        await bot.session.close()
        os._exit(0)


# ===|Start|===
async def main():
    logger.info("🤖 Bot started")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n")
        logger.info("🛑 Bot stopped from panel")