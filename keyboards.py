from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)



def get_main_kb() -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="Создать проект")],
        [KeyboardButton(text="Мои проекты")],
        [KeyboardButton(text="Настройки уведомлений")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)



def get_project_actions_kb(project_id: int) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                text="Удалить проект",
                callback_data=f"delete_project_{project_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text="Добавить участника",
                callback_data=f"add_member_{project_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text="Установить дедлайн",
                callback_data=f"set_deadline_{project_id}"
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)



def get_cancel_kb() -> ReplyKeyboardMarkup:
    buttons = [[KeyboardButton(text="Отмена")]]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)



def get_confirm_deletion_kb(project_id: int) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                text="Да, удалить",
                callback_data=f"confirm_delete_{project_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text="Отменить",
                callback_data="cancel_deletion"
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)



def get_notifications_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="Включить уведомления"), KeyboardButton(text="Отключить уведомления")],
        [KeyboardButton(text="Выбрать интервалы"), KeyboardButton(text="Назад")]
    ], resize_keyboard=True)



def get_reminder_kb():
    hours = [1, 2, 6, 12, 24]
    buttons = []

    for i in range(0, len(hours), 3):
        row = [
            InlineKeyboardButton(
                text=f"{h} ч",
                callback_data=f"reminder_toggle_{h}"
            )
            for h in hours[i:i+3]
        ]
        buttons.append(row)

    buttons.append([
        InlineKeyboardButton(text="Сохранить", callback_data="reminder_save")
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_notification_settings_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Изменить интервалы",
                callback_data="edit_reminders"
            )
        ],
        [
            InlineKeyboardButton(
                text="Назад",
                callback_data="back_to_main"
            )
        ]
    ])

