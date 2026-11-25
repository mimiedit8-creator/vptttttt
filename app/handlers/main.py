from aiogram import Router, F
from html import escape
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from app.keyboards import main_keyboard, confirm_keyboard, privacy_keyboard
from app.services.schedule import get_cached_schedule, refresh_schedule
from app.services.tracking import track_parcel

router = Router()

class Flow(StatesGroup):
    recipient = State()
    message = State()
    tracking = State()

@router.message(CommandStart())
async def start(message: Message, db):
    await db.upsert_user(message.from_user)
    await message.answer(
        "Привет! Это VPT Bot для группы РКЛ-3. Выбери нужный раздел.",
        reply_markup=main_keyboard()
    )

@router.message(Command("help"))
async def help_cmd(message: Message):
    await message.answer("Команды: /start, /profile, /privacy, /block @username")

@router.message(F.text.in_({"📅 Сегодня", "📅 Завтра", "🗓 Неделя"}))
async def schedule(message: Message, db):
    await message.answer(await get_cached_schedule(db))

@router.message(F.text == "🔄 Обновить")
async def update_schedule(message: Message, db, config):
    await message.answer("Проверяю официальный источник расписания…")
    try:
        body = await refresh_schedule(db, config.schedule_url)
        await message.answer("Кэш расписания обновлён.\n\n" + escape(body[:3500]))
    except Exception as exc:
        await message.answer(f"Не получилось обновить расписание: {exc}\nСтарый кэш, если он есть, сохранён.")

@router.message(F.text == "👤 Профиль")
@router.message(Command("profile"))
async def profile(message: Message, db):
    await db.upsert_user(message.from_user)
    username = f"@{message.from_user.username}" if message.from_user.username else "не задан"
    await message.answer(f"Твой профиль\nID: {message.from_user.id}\nUsername: {username}")

@router.message(F.text == "⚙️ Приватность")
@router.message(Command("privacy"))
async def privacy(message: Message, db):
    await db.upsert_user(message.from_user)
    async with await db.connect() as conn:
        cur = await conn.execute("SELECT allow_messages FROM users WHERE user_id=?", (message.from_user.id,))
        row = await cur.fetchone()
    enabled = bool(row["allow_messages"]) if row else True
    await message.answer("Настройки входящих сообщений:", reply_markup=privacy_keyboard(enabled))

@router.callback_query(F.data == "privacy:toggle")
async def privacy_toggle(call: CallbackQuery, db):
    async with await db.connect() as conn:
        cur = await conn.execute("SELECT allow_messages FROM users WHERE user_id=?", (call.from_user.id,))
        row = await cur.fetchone()
    enabled = not bool(row["allow_messages"]) if row else False
    await db.set_allow_messages(call.from_user.id, enabled)
    await call.message.edit_text("Входящие сообщения включены." if enabled else "Входящие сообщения выключены.",
                                 reply_markup=privacy_keyboard(enabled))
    await call.answer()

@router.message(Command("block"))
async def block_user(message: Message, db):
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].startswith("@"):
        await message.answer("Использование: /block @username")
        return
    target = await db.get_user_by_username(parts[1])
    if not target:
        await message.answer("Пользователь не найден. Он должен сначала нажать /start.")
        return
    await db.block(message.from_user.id, target["user_id"])
    await message.answer("Пользователь заблокирован.")

@router.message(F.text == "💬 Написать")
async def begin_message(message: Message, state: FSMContext):
    await state.set_state(Flow.recipient)
    await message.answer("Отправь @username получателя.")

@router.message(Flow.recipient)
async def choose_recipient(message: Message, state: FSMContext, db):
    username = (message.text or "").strip()
    if not username.startswith("@"):
        await message.answer("Нужен username в формате @username.")
        return
    target = await db.get_user_by_username(username)
    if not target:
        await message.answer("Не нашёл. Получатель должен хотя бы раз нажать /start.")
        return
    if target["user_id"] == message.from_user.id:
        await message.answer("Нельзя отправить сообщение самому себе.")
        return
    if not await db.is_allowed(message.from_user.id, target["user_id"]):
        await message.answer("Этот пользователь отключил входящие сообщения или заблокировал тебя.")
        await state.clear()
        return
    await state.update_data(recipient_id=target["user_id"], recipient_name=target["first_name"])
    await state.set_state(Flow.message)
    await message.answer("Теперь напиши сообщение. Перед отправкой я попрошу подтверждение.")

@router.message(Flow.message)
async def write_message(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("Пока поддерживаются только текстовые сообщения.")
        return
    await state.update_data(body=message.text[:3000])
    await message.answer("Отправить это сообщение?", reply_markup=confirm_keyboard())

@router.callback_query(F.data.startswith("msg:"))
async def confirm_message(call: CallbackQuery, state: FSMContext, db, bot):
    data = await state.get_data()
    if call.data == "msg:no":
        await state.clear()
        await call.message.edit_text("Отправка отменена.")
        await call.answer()
        return
    recipient_id = data.get("recipient_id")
    body = data.get("body")
    if not recipient_id or not body or not await db.is_allowed(call.from_user.id, recipient_id):
        await state.clear()
        await call.message.edit_text("Не удалось отправить: получатель недоступен или отключил сообщения.")
        await call.answer()
        return
    try:
        await bot.send_message(recipient_id, f"Сообщение от @{escape(call.from_user.username or str(call.from_user.id))}:\n\n{escape(body)}")
        await db.save_message(call.from_user.id, recipient_id, body)
        await call.message.edit_text("Сообщение отправлено.")
    except Exception:
        await call.message.edit_text("Telegram не доставил сообщение. Возможно, получатель не запускал бота.")
    await state.clear()
    await call.answer()

@router.message(F.text == "📦 Посылки")
async def begin_tracking(message: Message, state: FSMContext, db):
    tracks = await db.get_tracks(message.from_user.id)
    suffix = "\nСохранённые треки:\n" + "\n".join(tracks[:10]) if tracks else ""
    await state.set_state(Flow.tracking)
    await message.answer("Отправь трек-номер для сохранения и проверки." + suffix)

@router.message(Flow.tracking)
async def tracking(message: Message, state: FSMContext, db, config):
    number = (message.text or "").strip().replace(" ", "")
    if len(number) < 5 or len(number) > 40:
        await message.answer("Проверь номер: длина должна быть от 5 до 40 символов.")
        return
    await db.save_track(message.from_user.id, number)
    await message.answer(await track_parcel(number, config.parcelle_api_key, config.parcelle_api_url))
    await state.clear()
