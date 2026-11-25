from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📅 Сегодня"), KeyboardButton(text="📅 Завтра")],
            [KeyboardButton(text="🗓 Неделя"), KeyboardButton(text="🔄 Обновить")],
            [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="💬 Написать")],
            [KeyboardButton(text="📦 Посылки"), KeyboardButton(text="⚙️ Приватность")],
        ],
        resize_keyboard=True,
    )

def confirm_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Отправить", callback_data="msg:yes"),
        InlineKeyboardButton(text="Отмена", callback_data="msg:no"),
    ]])

def privacy_keyboard(enabled: bool):
    label = "Выключить входящие" if enabled else "Включить входящие"
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=label, callback_data="privacy:toggle")
    ]])
