from aiogram import types, Router, Bot
from aiogram.filters import Command, CommandObject
import json
import html
import os
import sys
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv
import asyncio
from loguru import logger
import utils
import time
import datetime
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from database import Database
from openai import OpenAI, OpenAIError
import base64
import io
import aiohttp
import urllib.parse

class UserMode(StatesGroup):
    ai = State()
    feedback = State()

class ReplyState(StatesGroup):
    fb_reply_wait = State()

class AdminState(StatesGroup):
    add_admin_wait = State()
    remove_admin_wait = State()

# Process start times (used for uptime)
START_TIME = datetime.datetime.utcnow()
START_MONO = time.monotonic()

router = Router()

load_dotenv()
gpt_token = os.getenv("COPILOT_API_KEY")
endpoint = "https://models.github.ai/inference"
model_name = "openai/gpt-4o-mini"
bot = Bot(os.getenv("BOT_TOKEN"))

client = OpenAI(api_key=gpt_token, base_url=endpoint, timeout=30.0)

with open("prompt.txt", "r", encoding="utf-8") as f:
    prompt = f.read()


db = Database('memory.db')

# я, саня, саша 
master = [1078401181, 8386113624, 5802369201, 1131150026]

for admin_id in master:
    db.add_admin(admin_id)

admin_cache = set(db.get_admins())

RATE_LIMIT_SECONDS = 2.0
IMAGE_MAX_BYTES = 5 * 1024 * 1024

last_request_at: dict[str, float] = {}


def is_admin(user_id: int) -> bool:
    return user_id in admin_cache


def h(text: str) -> str:
    return html.escape(text or "")


def rate_limit(key: str, interval_seconds: float = RATE_LIMIT_SECONDS) -> bool:
    now = time.monotonic()
    last = last_request_at.get(key, 0.0)
    if now - last < interval_seconds:
        return False
    last_request_at[key] = now
    return True


def is_private_message(message: types.Message) -> bool:
    return getattr(message.chat, "type", None) == "private"


def is_private_callback(callback: types.CallbackQuery) -> bool:
    return callback.message is not None and getattr(callback.message.chat, "type", None) == "private"


# ===|Copilot interaction|===
async def ask_copilot(chat_id: int, user_message: str, image_data: str = None):
    HISTORY_LIMIT = 40

    db_text = f"[Photo] {user_message}" if image_data else user_message
    await asyncio.to_thread(db.add_message, chat_id, "user", db_text) 
    history = await asyncio.to_thread(db.get_history, chat_id, limit=HISTORY_LIMIT)
    final_messages = [
        {"role": "system", "content": prompt}
    ]
    final_messages.extend(history)
    
    if image_data:
        current_content = [
            {"type": "text", "text": user_message if user_message else "Что на изображении?"},
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{image_data}"
                }
            }
        ]
    else:
        current_content = user_message

    final_messages.append({"role": "user", "content": current_content})
    
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=final_messages,
            timeout=30.0,
        )
        
        reply_content = response.choices[0].message.content

        await asyncio.to_thread(db.add_message, chat_id, "assistant", reply_content)
        return reply_content
        
    except OpenAIError as e:
        logger.exception(f"OpenAI/Copilot API Error for {chat_id}: {e}")
        return f"<a href='tg://emoji?id=5872829476143894491'>🐛</a> <b>Критическая ошибка в ИИ, сообщите о ней администрации</b> (/admins)\n\n<blockquote expandable><code>{e}</code></blockquote>"

    except Exception as e:
        logger.exception(f"Critical error in ask_copilot (non-API) for {chat_id}: {e}")
        return f"<a href='tg://emoji?id=5872829476143894491'>🐛</a> <b>Критическая ошибка в ИИ, сообщите о ней администрации</b> (/admins)\n\n<blockquote expandable><code>{e}</code></blockquote>"


# сука его тоже в дб надо записывать а не жсон
if not os.path.exists("fb_blacklist.json"):
    with open("fb_blacklist.json", "w", encoding="utf-8") as f:
        f.write('{"blocked": []}')

def get_fb_blacklist():
    with open("fb_blacklist.json", "r", encoding="utf-8") as f:
        return json.load(f)["blocked"]
    
def save_fb_blacklist(lst):
    with open("fb_blacklist.json", "w", encoding="utf-8") as f:
        json.dump({"blocked": lst}, f, indent=4)

# ===|Handlers|===
@router.message(Command("start")) 
async def start(message: types.Message, state: FSMContext):
    if not is_private_message(message):
        return
    u = utils.user(message)
    if is_admin(u.id):
        logger.debug(f"One of admins ({u.username}) started the bot. (start command)")
        await message.answer(
            f"Hi <a href='tg://user?id={u.id}'>{h(u.first_name)}</a> [{h(u.username)}]! This is a test bot",
            parse_mode="HTML",
        )
        await asyncio.sleep(0.5)
        await message.reply("Glad to see you, master <a href='tg://emoji?id=5765017520612315383'>💖</a>", parse_mode="HTML")
    else:
        logger.critical(f"@{u.username} [{u.id}] started the bot.")
        await message.reply(
            f"Yo, how you find me <a href='tg://user?id={u.id}'>{h(u.full_name)}</a>?",
            parse_mode="HTML",
        )
        await message.answer(f"<b>This is a test bot (<i>Version: <code>{utils.version()}</code></i>)</b>\nSo please be carefull and send all bugs to <b><u>@revertPls</u></b> / <b><u>@IgorVasilekIV</u></b>", parse_mode="HTML")
    await state.set_state(UserMode.ai)

@router.message(Command("clear"))
async def clear(message: types.Message):
    if not is_private_message(message):
        return
    u = utils.user(message)
    logger.debug(f"@{u.username} [{u.id}] requested memory clear")
    db.clear_history(u.id)
    await message.answer("<a href='tg://emoji?id=5811966564039135541'>🧽</a> Memory cleared.", parse_mode="HTML")


@router.message(Command("stop"))
async def stop(message: types.Message):
    if not is_private_message(message):
        return
    u = utils.user(message)
    if is_admin(u.id):
        logger.debug(f"You ({u.username}) stopped the bot. (stop command)")
        await message.answer("<a href='tg://emoji?id=5879995903955179148'>🛑</a> Bot stopped.\n\n<b>Check the panel</b>", parse_mode="HTML")

        await bot.session.close()
        os._exit(0)
    else:
        logger.critical(f"@{u.username} / {u.id} tried to stop the bot without permission.")
        await message.reply("You don't have permission to use this command.")


@router.message(Command("ap"))
async def ap(message: types.Message):
    if not is_private_message(message):
        return
    u = utils.user(message)
    if is_admin(u.id):
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
                InlineKeyboardButton(text="➕ Add Admin", callback_data="ap_add_admin"),
                InlineKeyboardButton(text="➖ Remove Admin", callback_data="ap_remove_admin"),
                InlineKeyboardButton(text="📋 Admins", callback_data="ap_list_admins")
            ],
            [
                InlineKeyboardButton(text="========= Bot =========", callback_data="void"),
            ],
            [
                InlineKeyboardButton(text="📂 Logs", callback_data="ap_logs"),
                InlineKeyboardButton(text="🛑 Stop Bot", callback_data="ap_stop"),
                InlineKeyboardButton(text="🔄️ Restart Bot", callback_data="ap_restart")
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
    if not is_private_message(message):
        return
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
        "<a href='tg://emoji?id=5985616167740379273'>🤖</a> <b>Uptime</b>\n"
        f"• Started: <code>{START_TIME.strftime('%Y-%m-%d %H:%M:%S')} UTC</code>\n"
        f"• Uptime: <code>{utils.format_timedelta(uptime)}</code>\n\n"
        "<a href='tg://emoji?id=5879585266426973039'>🌐</a> <b>Ping</b>\n"
        f"• Telegram API RTT: <code>{ping_text}</code>\n\n"
        f"• Version: <code>{utils.version()}</code>" 
    )
    await message.answer(text, parse_mode="HTML")
    logger.debug(f"User (@{utils.user(message).username}) requested uptime.")

@router.message(Command("mode"))
async def toggle_mode(message: types.Message, state: FSMContext):
    if not is_private_message(message):
        return
    current = await state.get_state()

    if current == UserMode.ai.state:
        if await asyncio.to_thread(db.is_blacklisted, utils.user(message).id):
            await state.set_state(UserMode.ai)
            return await message.answer("<a href='tg://emoji?id=5922712343011135025'>🚫</a> Вы были заблокированы в фидбеке.", parse_mode="HTML")
            
        await state.set_state(UserMode.feedback)
        await message.answer("<a href='tg://emoji?id=5877410604225924969'>🔄</a> Режим переключен: <a href='tg://emoji?id=5891169510483823323'>📝</a> <b>Фидбек</b>", parse_mode="HTML")

    else:
        await state.set_state(UserMode.ai)
        await message.answer("<a href='tg://emoji?id=5877410604225924969'>🔄</a> Режим переключен: <a href='tg://emoji?id=5931415565955503486'>🤖</a> <b>ИИ Чат</b>", parse_mode="HTML")

@router.message(Command("admins"))
async def admins(message: types.Message):
    if not is_private_message(message):
        return
    admins_sorted = sorted(admin_cache)
    admins_text = "\n".join([f"• <code>{admin_id}</code>" for admin_id in admins_sorted]) or "—"
    await message.answer(
        "<a href='tg://emoji?id=5431378302075960714'>😊</a> <b>Админы (ID):</b>\n"
        f"<blockquote expandable>{admins_text}</blockquote>",
        parse_mode="HTML",
    )

@router.callback_query(lambda c: c.data.startswith("fb_reply"))
async def fb_callbacks (callback: types.CallbackQuery, state: FSMContext):
    if not is_private_callback(callback):
        await callback.answer()
        return
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет прав.", show_alert=True)
        return
    target_id = int(callback.data.split("_")[2])
    await state.update_data(target_id=target_id)
    await callback.message.answer("<a href='tg://emoji?id=6039779802741739617'>✏️</a> Напишите ваш ответ", parse_mode="HTML")
    await state.set_state(ReplyState.fb_reply_wait)
    await callback.answer()

@router.message(ReplyState.fb_reply_wait)
async def fb_reply(message: types.Message, state: FSMContext):
    if not is_private_message(message):
        return
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    target_id = data["target_id"]
    await bot.send_message(target_id, f"Вам ответили: <b>{h(message.text)}</b>", parse_mode="HTML")
    await message.answer ("Ответ отправлен.")
    await state.clear()

@router.callback_query(lambda c: c.data.startswith("fb_block"))
async def fb_block(callback: types.CallbackQuery):
    if not is_private_callback(callback):
        await callback.answer()
        return
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет прав.", show_alert=True)
        return
    target_id = int(callback.data.split("_")[2])
    await asyncio.to_thread(db.add_blacklist, target_id)
    await bot.send_message(target_id, f"<a href='tg://emoji?id=5922712343011135025'>🚫</a> Вы были заблокированы в фидбеке.", parse_mode="HTML")
    await callback.answer("🚫 Пользователь был заблокирован в фидбеке.")
    nt = f"{callback.message.text}\n\n<b>======[<a href='tg://emoji?id=5208972891055473699'>⛔️</a> ЗАБАНЕН]======</b>"
    await callback.message.edit_text(nt, parse_mode="HTML")

@router.message(Command("fb_unban"))
async def fb_unban(message: types.Message, command: CommandObject):
    if not is_private_message(message):
        return
    args = command.args

    if not args:
        await message.answer("<a href='tg://emoji?id=5924719252379537729'>🤔</a> А кого разбанить то?", parse_mode="HTML")
        return
    if not is_admin(message.from_user.id):
        await message.answer("<b>You don't have permission to do this</b>", parse_mode="HTML")
        return
        
    try:
        target_id = int(args)
    except ValueError:
        return await message.answer("<a href='tg://emoji?id=6019102674832595118'>⚠️</a> ID должен быть числом.", parse_mode="HTML")

    is_banned = await asyncio.to_thread(db.is_blacklisted, target_id)

    if is_banned:
        try:
            await asyncio.to_thread(db.remove_blacklist, target_id)
            await message.answer("<a href='tg://emoji?id=5906995262378741881'>💖</a> Пользователь был разбанен.", parse_mode="HTML")
            await bot.send_message(target_id, "Вы были разбанены в фидбеке.", parse_mode="HTML")
        except Exception as e:
            logger.exception(f"Error while removing from blacklist: {e}")
            await message.answer(f"<a href='tg://emoji?id=6019102674832595118'>⚠️</a> Ошибка при попытке разбанить чела.\n\n<blockquote expandable><code>{e}</code></blockquote>", parse_mode="HTML")
    else:
        await message.answer("<a href='tg://emoji?id=6019102674832595118'>⚠️</a> Пользователь не был забанен.")

        
@router.message(Command("fb_ban"))
async def fb_ban(message: types.Message, command: CommandObject):
    if not is_private_message(message):
        return
    args = command.args

    if not is_admin(message.from_user.id):
        await message.answer("<b>You don't have permission to do this</b>", parse_mode="HTML")
        return
    
    if not args:
        await message.answer("<a href='tg://emoji?id=5924719252379537729'>🤔</a> А кого банить то?")
        return
    try:
        target_id = int(args)
    except ValueError:
        return await message.answer("<a href='tg://emoji?id=6019102674832595118'>⚠️</a> ID должен быть числом.", parse_mode="HTML")

    is_banned = await asyncio.to_thread(db.is_blacklisted, target_id)

    if is_banned:
        await message.answer("<a href='tg://emoji?id=6019102674832595118'>⚠️</a> Пользователь уже был забанен.")
    else:
        try:
            await asyncio.to_thread(db.add_blacklist, target_id)
            await message.answer("<a href='tg://emoji?id=5922712343011135025'>🚫</a> Пользователь был забанен.")
            await bot.send_message(target_id, "<a href='tg://emoji?id=5922712343011135025'>🚫</a> Вы были заблокированы в фидбеке.", parse_mode="HTML")
        except Exception as e:
            logger.exception(f"Error while tring to add user to blacklist: {e}")
            await message.answer(f"Ошибка при попытке забанить чела.\n\n<blockquote expandable><code>{e}</code></blockquote>", parse_mode="HTML")


@router.message(AdminState.add_admin_wait)
async def add_admin_wait(message: types.Message, state: FSMContext):
    if not is_private_message(message):
        return
    if not is_admin(message.from_user.id):
        await state.clear()
        return

    raw = (message.text or "").strip()
    try:
        target_id = int(raw)
    except ValueError:
        return await message.answer("<a href='tg://emoji?id=6019102674832595118'>⚠️</a> ID должен быть числом.", parse_mode="HTML")

    if target_id in admin_cache:
        await message.answer("<a href='tg://emoji?id=5924719252379537729'>🤔</a> Уже админ.", parse_mode="HTML")
        await state.clear()
        return

    await asyncio.to_thread(db.add_admin, target_id)
    admin_cache.add(target_id)
    await message.answer("<a href='tg://emoji?id=5906995262378741881'>💖</a> Админ добавлен.", parse_mode="HTML")
    await state.clear()


@router.message(AdminState.remove_admin_wait)
async def remove_admin_wait(message: types.Message, state: FSMContext):
    if not is_private_message(message):
        return
    if not is_admin(message.from_user.id):
        await state.clear()
        return

    raw = (message.text or "").strip()
    try:
        target_id = int(raw)
    except ValueError:
        return await message.answer("<a href='tg://emoji?id=6019102674832595118'>⚠️</a> ID должен быть числом.", parse_mode="HTML")

    if target_id not in admin_cache:
        await message.answer("<a href='tg://emoji?id=5924719252379537729'>🤔</a> Это не админ.", parse_mode="HTML")
        await state.clear()
        return

    if target_id == message.from_user.id:
        await message.answer("<a href='tg://emoji?id=5924719252379537729'>🤔</a> Нельзя удалить самого себя.", parse_mode="HTML")
        await state.clear()
        return

    if len(admin_cache) <= 1:
        await message.answer("<a href='tg://emoji?id=5924719252379537729'>🤔</a> Нельзя удалить последнего админа.", parse_mode="HTML")
        await state.clear()
        return

    await asyncio.to_thread(db.remove_admin, target_id)
    admin_cache.discard(target_id)
    await message.answer("<a href='tg://emoji?id=5906995262378741881'>💖</a> Админ удалён.", parse_mode="HTML")
    await state.clear()

@router.message(Command("generate"))
async def generate(message: types.Message, command: CommandObject):
    if not is_private_message(message):
        return
    args = command.args
    user_id = message.from_user.id
    
    if not args:
        await message.answer(
            "Чтобы использовать эту команду, введите <code>/generate ваш запрос</code>\n\nРаботает на Pollinations.ai", 
            parse_mode="HTML"
        )
        return

    if not rate_limit(f"generate:{user_id}"):
        return await message.reply("<a href='tg://emoji?id=5924719252379537729'>⏳</a> Слишком часто. Подожди пару секунд.", parse_mode="HTML")

    prompt = urllib.parse.quote_plus(args)
    img_url = f"https://image.pollinations.ai/prompt/{prompt}"

    try:
        reply = await message.reply("<a href='tg://emoji?id=6026089641730382702'>🖼️</a> <b>Изображение генерируется, подождите...</b>", parse_mode="HTML")

        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(img_url) as resp:
                
                if resp.status != 200:
                    error_text = await resp.text()
                    raise Exception(f"Failed to fetch image. Status: {resp.status}, Response: {error_text[:100]}...")

                content_type = resp.headers.get('Content-Type', '')
                if 'image/' not in content_type:
                    raise Exception(f"Received non-image content: {content_type}")
                    
                image_bytes = await resp.read()

        await reply.delete()

        await message.reply_photo(
            types.BufferedInputFile(image_bytes, filename="generated_image.jpg"),
            caption=f"<blockquote expandable><code>{h(args)}</code></blockquote>",
            parse_mode="HTML"
        )

    except Exception as e:
        await reply.delete()
            
        await message.reply(
            f"<b>Ошибка при генерации изображения.</b>\n\n<blockquote expandable><code>{e}</code></blockquote>", 
            parse_mode="HTML"
        )
        logger.exception(f"Image generation error for user {user_id}: {e}")


@router.message(Command("donate"))
async def donate(message: types.Message):
    if not is_private_message(message):
        return
    await message.answer("Пытался сделать этого бота максимально крутым, и был бы очень благодарен за поддержку. Если есть желание помочь развитию проекта, <b>вот</b> <a href='https://t.me/BioVasilek/10'>инфопост</a>\n\n<tg-spoiler>сука даже тут ИИ 🤔</tg-spoiler>", parse_mode="HTML")


@router.message(Command("restart"))
async def restart(message: types.Message):
    if not is_private_message(message):
        return
    if not is_admin(utils.user(message).id):
        await message.answer("<b>You don't have permission to do this</b>", parse_mode="HTML")
        return
    await message.answer("<a href='tg://emoji?id=5877410604225924969'>🔄</a> Restarting bot...", parse_mode="HTML")
    logger.debug(f"{utils.user(message).username} restarted the bot.")
    await bot.session.close()
    db.connection.close()
    os.execl(sys.executable, sys.executable, "-m", "start")


@router.message()
async def chat(message: types.Message, state: FSMContext):
    if not is_private_message(message):
        return
    u = utils.user(message)
    current_state = await state.get_state()


    if current_state == UserMode.ai.state:
        if not message.photo and not message.text:
            return await message.reply("<a href='tg://emoji?id=6019102674832595118'>⚠️</a> <b>Я понимаю только текст и изображения</b>\nПожалуйста, не отправляйте видео, файлы или стикеры.", parse_mode="HTML")

        if not rate_limit(f"chat:{u.id}"):
            return await message.reply("<a href='tg://emoji?id=5924719252379537729'>⏳</a> Слишком часто. Подожди пару секунд.", parse_mode="HTML")

        await bot.send_chat_action(message.chat.id, action="typing")

        user_message = ""
        image_data = None

        if message.photo:
            try:
                photo = message.photo[-1]

                img_buffer = io.BytesIO()
                await bot.download(photo, destination=img_buffer)

                img_bytes = img_buffer.getvalue()
                if len(img_bytes) > IMAGE_MAX_BYTES:
                    return await message.reply("<a href='tg://emoji?id=6019102674832595118'>⚠️</a> Изображение слишком большое.", parse_mode="HTML")
                image_data = base64.b64encode(img_bytes).decode('utf-8')

                user_message = message.caption if message.caption else ""
        
            except Exception as e:
                logger.exception(f"Failed to process image from user {u.id}: {e}")
                return await message.reply(f"<a href='tg://emoji?id=5872829476143894491'>🐛</a> <b>Ошибка при обработке изображения, сообщите администрации</b> (/admins)\n\n<blockquote expandable><code>{e}</code></blockquote>", parse_mode="HTML")
        elif message.text:
            user_message = message.text

        msg_len = len(user_message) if user_message else 0
        logger.debug(f"Message from (@{u.username}) [{u.id}]: len={msg_len} Image included: {bool(image_data)}")

        reply_ai = await ask_copilot(message.chat.id, user_message, image_data=image_data)
        await message.reply(reply_ai, parse_mode="HTML")


    elif current_state == UserMode.feedback.state:
        fb_text = (
            "<a href='tg://emoji?id=5890741826230423364'>💬</a> Вам пришло сообщение!\n\n"
            f"<a href='tg://emoji?id=5994809115740737538'>🐱</a> От: [@{h(u.username)} / <code>{u.id}</code>]\n"
            f"<a href='tg://emoji?id=5994495149336434048'>⭐️</a> Сообщение: <b>{h(message.text)}</b>"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="Ответить", callback_data=f"fb_reply_{u.id}"),
                InlineKeyboardButton(text="Забанить", callback_data=f"fb_block_{u.id}")
            ]
        ])

        logger.debug(f"Forwarding feedback from {u.id} to master {master[0]} (callback buttons set)")
        await bot.send_message(master[0], fb_text, parse_mode="HTML", reply_markup=keyboard)
        await state.clear()
        return await message.reply("Сообщение было отправлено.", parse_mode="HTML")

# ===|Inline Callbacks|===
@router.callback_query(lambda c: c.data.startswith("ap_"))
async def ap_callbacks(callback: types.CallbackQuery, state: FSMContext):
    user = callback.from_user
    action = callback.data.split("_")[1]
    if not is_private_callback(callback):
        await callback.answer()
        return
    if not is_admin(user.id):
        await callback.answer("Нет прав.", show_alert=True)
        return

    if action == "clear_memory":
        try:
            db.clear_global_history()
            logger.debug("All memory cleared.")
            await callback.answer("🧽 Memory cleared.", show_alert=True)
        except Exception as e:
            logger.exception(f"Failed to clear global memory: {e}")
            await callback.answer()
            await callback.message.answer(f"<a href='tg://emoji?id=6019102674832595118'>⚠️</a> Ошибка при очистке памяти.\n\n<blockquote expandable><code>{e}</code></blockquote>", parse_mode="HTML")

    elif action == "stats":
        users_count, messages_count = db.stats()
    
        stats_text = (
            "📊 Статистика бота:\n\n"
            f"👤 Активных пользователей: {users_count}\n"
            f"💬 Сообщений в памяти: {messages_count}\n"
            f"💾 Тип базы: SQLite3 / v{utils.version()}"
        )
    
        await callback.answer(stats_text, show_alert=True)

    elif action == "add":
        await callback.message.answer("Введите ID пользователя, которого нужно сделать админом.")
        await callback.answer()
        await state.set_state(AdminState.add_admin_wait)

    elif action == "remove":
        await callback.message.answer("Введите ID пользователя, которого нужно убрать из админов.")
        await callback.answer()
        await state.set_state(AdminState.remove_admin_wait)

    elif action == "list":
        admins_sorted = sorted(admin_cache)
        admins_text = "\n".join([f"• <code>{admin_id}</code>" for admin_id in admins_sorted]) or "—"
        await callback.message.answer(f"<b>Admins</b>\n{admins_text}", parse_mode="HTML")
        await callback.answer()

    elif action == "logs":
        try:
            files = [f for f in os.listdir("logs") if f.startswith("bot_") and f.endswith(".log")]
            if not files:
                await callback.answer("<a href='tg://emoji?id=6019102674832595118'>⚠️</a> Логи не найдены.", show_alert=True)
                return

            latest_log = max(files, key=lambda f: os.path.getctime(os.path.join("logs", f)))
            log_path = os.path.join("logs", latest_log)

            logger.debug(f"📤 Sending log file: {latest_log}")
            await callback.message.answer_document(
                document=types.FSInputFile(log_path),
                caption=f"<a href='tg://emoji?id=5839323457015256759'>📄</a> Лог-файл: <code>{latest_log}</code>",
                parse_mode="HTML"
            )

            await callback.answer("✅ Лог отправлен.")
        except Exception as e:
            logger.exception(f"Failed to send logs: {e}")
            await callback.answer()
            await callback.message.answer(f"<a href='tg://emoji?id=6019102674832595118'>⚠️</a> Ошибка при отправке логов.\n\n<blockquote expandable><code>{e}</code></blockquote>")

    elif action == "stop":
        await callback.message.answer("<a href='tg://emoji?id=5879995903955179148'>🛑</a> Stopping bot...", parse_mode="HTML")
        await callback.answer()
        logger.debug(f"{user.username} stopped the bot.")
        await bot.session.close()
        db.connection.close()
        os._exit(0)
    
    elif action == "restart":
        await callback.message.answer("<a href='tg://emoji?id=5877410604225924969'>🔄</a> Restarting bot...", parse_mode="HTML")
        await callback.answer()
        logger.debug(f"{user.username} restarted the bot.")
        await bot.session.close()
        db.connection.close()
        os.execl(sys.executable, sys.executable, "-m", "start")
