from aiogram import types, Router, Bot
from aiogram.filters import Command
import json
import os
import google.generativeai as genai
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv
import asyncio
from loguru import logger
import utils
import time
import datetime
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

class UserMode(StatesGroup):
    ai = State()
    feedback = State()
FSMContext.set_state(UserMode.ai)

# Process start times (used for uptime)
START_TIME = datetime.datetime.utcnow()
START_MONO = time.monotonic()

router = Router()

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

load_dotenv()
bot = Bot(os.getenv("BOT_TOKEN"))

master = [1078401181]

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

with open("prompt.txt", "r", encoding="utf-8") as f:
    prompt = f.read()

# ===|Ask GenAI|===
async def ask_gemini(chat_id: int, user_message: str):
    history = memory.get(str(chat_id), [])

    # new message to history
    history.append({"role": "user", "parts": user_message})

    # answer generate
    model = genai.GenerativeModel("gemini-2.5-flash", system_instruction=prompt)
    response = model.generate_content(history)

    # save to memory
    history.append({"role": "model", "parts": response.text})
    memory[str(chat_id)] = history[-40:]  # keep only last 40 messages
    save_memory(memory)

    return response.text



# ===|Handlers|===
@router.message(Command("start")) 
async def start(message: types.Message):
    u = utils.user(message)
    if u.id in master:
        logger.debug(f"One of admins ({u.username}) started the bot. (start command)")
        await message.answer(f"Hi @{u.username} / <a href='{u.id}'>{u.first_name}</a>! This is a test bot", parse_mode="HTML")
        await asyncio.sleep(0.5)
        await message.reply("Glad to see you, master <a href='tg://emoji?id=5335013413640748545'>😊</a>", parse_mode="HTML")
    else:
        logger.critical(f"@{u.username} / {u.id} started the bot without permission.")
        await message.reply(f"Yo, how you find me <a href='tg://user?id={u.id}'>{u.full_name}</a>?", parse_mode="HTML")
        await message.answer(f"<b>This is a test bot (<i>Version: {utils.version()}</i>)</b>\nSo please be carefull and send all bugs to <b><u>@monkeBananchik</u></b> / <b><u>@IgorVasilekIV</u></b>", parse_mode="HTML")


@router.message(Command("clear"))
async def clear(message: types.Message):
    u = utils.user(message)
    if u.id in master:
        logger.debug(f"One of admins ({u.username}) requested memory clear. (clear command)")
        memory.pop(str(message.chat.id), None)
        save_memory(memory)
        await message.answer("<a href='tg://emoji?id=5811966564039135541'>🧽</a> Memory cleared.", parse_mode="HTML")
    else:
        logger.critical(f"@{u.username} / {u.id} tried to clear memory.")
        await message.reply("<b>Get off me!</b>", parse_mode="HTML")


@router.message(Command("stop"))
async def stop(message: types.Message):
    u = utils.user(message)
    if u.id == master[0]:
        logger.debug(f"You ({u.username}) stopped the bot. (stop command)")
        await message.answer("<a href='tg://emoji?id=5879995903955179148'>🛑</a> Bot stopped.\n\n<b>Check the panel</b>", parse_mode="HTML")

        await bot.session.close()
        os._exit(0)
    else:
        logger.critical(f"@{u.username} / {u.id} tried to stop the bot without permission.")


@router.message(Command("ap"))
async def ap(message: types.Message):
    u = utils.user(message)
    if u.id == master[0]:
        logger.debug(f"You ({u.username}) opened the admin panel.")
        
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
            "<a href='tg://emoji?id=5988023995125993550'>🛠️</a> <b>Admin Panel</b>\n\n"
            "Select an action from the menu below:",
            parse_mode="HTML",
            reply_markup=keyboard
        )
    else:
        logger.critical(f"@{u.username} / {u.id} tried to access the admin panel without permission.")
        await message.reply("<b>You dont have permission to do this</b>", parse_mode="HTML")

@router.message(Command("uptime"))
async def uptime(message: types.Message):
    """Reply with uptime and Telegram API ping RTT."""
    now = datetime.datetime.utcnow()
    uptime = now - START_TIME

    t0 = time.monotonic()
    try:
        await bot.get_me()
        ping_ms = (time.monotonic() - t0) * 1000
        ping_text = f"{ping_ms:.0f} ms"
    except Exception as e:
        ping_text = f"error ({e.__class__.__name__})"

    text = (
        f"<a href='tg://emoji?id=5985616167740379273'>🤖</a> <b>Uptime</b>\n"
        f"• Started: <code>{START_TIME.strftime('%Y-%m-%d %H:%M:%S')} UTC</code>\n"
        f"• Uptime: <code>{utils.format_timedelta(uptime)}</code>\n\n"
        f"<a href='tg://emoji?id=5879585266426973039'>🌐</a> <b>Ping</b>\n"
        f"• Telegram API RTT: <code>{ping_text}</code>\n\n"
        f"• Version: {utils.version()}" 
    )
    await message.answer(text, parse_mode="HTML")
    logger.debug(f"User (@{utils.user(message).username}) requested uptime.")

@router.message(Command("mode"))
async def toggle_mode(message: types.Message, state: FSMContext):
    """From AI to Feedback and revert"""
    # Узнаем текущее состояние (вернет строку, например "UserMode:ai_chat", или None)
    current_state = await state.get_state()
    
    # Логика переключения
    # Обрати внимание: мы сравниваем со строковым значением состояния (.state)
    if current_state == UserMode.ai.state:
        await state.set_state(UserMode.feedback)
        await message.answer("🔄 Режим переключен: 📝 <b>Фидбек</b>", parse_mode="HTML")
        
    elif current_state == UserMode.feedback.state:
        await state.set_state(UserMode.ai)
        await message.answer("🔄 Режим переключен: 🤖 <b>ИИ Чат</b>", parse_mode="HTML")

@router.message()
async def chat(message: types.Message, state: FSMContext):
    u = utils.user(message)
    logger.debug(f"Message from (@{u.username}) [{u.id}]: {message.text}")
    if state.get_state() == UserMode.ai.state:
        reply_ai = await ask_gemini(message.chat.id, message.text)
        await message.reply(reply_ai, parse_mode="HTML")
    else:
        reply_fb = await message.reply("I got your message, but not send it to owner\nPlease send /mode to enable AI.")
        #await message.reply(reply_fb, parse_mode="HTML")
"""    if u.id in master:
        reply = await ask_gemini(message.chat.id, message.text)
        await message.reply(reply, parse_mode="HTML")
    else:
        logger.critical(f"@{u.username} / {u.id} used the bot without permission.")
        await message.reply("<b>Get off me!</b>", parse_mode="HTML")
"""


# ===|AP Callbacks|===
@router.callback_query(lambda c: c.data.startswith("ap_"))
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
        await callback.message.answer("<a href='tg://emoji?id=5879995903955179148'>🛑</a> Stopping bot...", parse_mode="HTML")
        logger.debug(f"{user.username} stopped the bot.")
        await bot.session.close()
        os._exit(0)
