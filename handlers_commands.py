import logging
from keyboards import *
from handlers_actions import *

logger = logging.getLogger(__name__)

# Обработка /start
@router.message(Command("start"))
async def cmd_start(message: types.Message):
    try:
        db = router.db
        await db.execute(
            "INSERT INTO users (user_id, username, full_name) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
            message.chat.id,
            message.from_user.username,
            message.from_user.full_name
        )
        await message.answer(
            "Добро пожаловать! Давайте управлять проектами.",
            reply_markup=get_main_kb()
        )
        logger.info(f"От пользователя с ID:{message.chat.id} обработана команда /start")

    except Exception as e:
            logger.error(f"Ошибка в обработчике команды start: {e}")
            await callback.message.answer("Произошла ошибка. Попробуйте снова.")
            await state.clear()


# Обработка "Создать проект(основная клавиатура)"
@router.message(F.text == "Создать проект")
async def create_project_start(message: types.Message, state: FSMContext):
    try:
        await message.answer("Введите название проекта:", reply_markup=get_cancel_kb())
        await state.set_state(CreateProject.enter_title)

        logger.info(f"От пользователя с ID:{message.chat.id} обработана команда \"Создать проект\"")

    except Exception as e:
            logger.error(f"Ошибка в обработчике создания проекта(начало): {e}")
            await message.answer("Произошла ошибка. Попробуйте снова.")
            await state.clear()


# Обработка "Мои проекты" (основная клавиатура)
@router.message(F.text == "Мои проекты")
async def my_projects(message: types.Message, state: FSMContext):
    try:
        db = router.db
        projects = await db.get_user_projects(message.chat.id)

        if not projects:
            await message.answer("У вас нет проектов.")
            logger.info(f"От пользователя с ID:{message.chat.id} обработана команда \"Мои проекты\"")
            return

        for p in projects:
            text = f"Проект №{p['id']}: {p['title']}\n"
            if p['deadline']:
                text += f"Дедлайн: {p['deadline'].strftime('%d.%m.%Y %H:%M')}\n"
            else:
                text += "Дедлайн не установлен\n"

            sent_msg = await message.answer(
                text,
                reply_markup=get_project_actions_kb(p['id'])
            )
            await state.update_data({
                f"project_msg_{p['id']}": sent_msg.message_id,
                f"project_title_{p['id']}": p['title']
            })

        logger.info(f"От пользователя с ID:{message.chat.id} обработана команда \"Мои проекты\"")

    except Exception as e:
        logger.error(f"Ошибка в обработчике получения списка проектов: {e}")
        await message.answer("Произошла ошибка. Попробуйте снова.")
        await state.clear()


# Обработка удаления проекта (инлайн-клавиатура "действия с проектом")
@router.callback_query(F.data.startswith("delete_project_"))
async def delete_project(callback: types.CallbackQuery, state: FSMContext):
    try:
        project_id = int(callback.data.split("_")[-1])
        await state.update_data(project_id=project_id)

        await callback.message.answer(
            f"Вы уверены, что хотите удалить проект №{project_id}?",
            reply_markup=get_confirm_deletion_kb(project_id)
        )
        await state.set_state(DeleteProject.confirm)
        logger.info(f"Пользователь {callback.from_user.id} начал удаление проекта {project_id}")

    except Exception as e:
        logger.error(f"Ошибка в обработчике удаления проекта(начало): {e}")
        await callback.message.answer("Произошла ошибка. Попробуйте снова.")
        await state.clear()


# Обработка установки дедлайна (инлайн-клавиатура "действия с проектом")
@router.callback_query(F.data.startswith("set_deadline_"))
async def start_set_deadline(callback: CallbackQuery, state: FSMContext):
    try:
        project_id = int(callback.data.split("_")[-1])
        await state.update_data(project_id=project_id)
        await callback.message.answer(
            "Введите дедлайн в формате:\n<b>ДД.ММ.ГГГГ ЧЧ:ММ</b>\n\n"
            "Пример: 25.12.2026 18:30",
            parse_mode="HTML",
            reply_markup=types.ReplyKeyboardRemove()
        )
        await state.set_state(SetDeadline.input_date)
        await callback.answer()
        logger.info(f"От пользователя с ID:{callback.from_user.id} обработана команда \"Начать установку дедлайна\"")

    except Exception as e:
        logger.error(f"Ошибка в обработчике установки дедлайна(начало): {e}")
        await callback.message.answer("Произошла ошибка. Попробуйте снова.")
        await state.clear()


# Обработка вызова ручной проверки уведомлений
@router.message(F.text == "Проверить уведомления")
async def check_notifications(message: Message):
    try:
        user_id=message.chat.id,
        projects = await db.fetch(
            "SELECT * FROM projects WHERE creator_id = $1 AND next_notification <= NOW()",
            user_id
        )
        for project in projects:
            deadline = project["deadline"]
            hours_left = (deadline - datetime.now()).total_seconds() // 3600
            await message.answer(
                f"⚠️ Напоминание! Проект «{project['title']}»\n"
                f"Дедлайн через {int(hours_left)} часов!",
                reply_markup=get_project_actions_kb(project["id"])
            )
            await schedule_next_notification(project["id"])
    except Exception as e:
        logger.error(f"Ошибка в обработчике ручной проверки просроченных уведомлений: {e}")
        await message.answer("Произошла ошибка. Попробуйте снова.")
        await state.clear()


# Обработка вызова настроек уведомлений
@router.message(F.text == "Настройки уведомлений")
async def show_notifications(message: Message, state: FSMContext):
    try:
        user_id = message.chat.id
        db = router.db
        settings = await db.get_notification_settings(user_id)
        if not settings:
            await db.update_notification_settings(user_id, True, [24, 6, 1])
            settings = {"enable_reminders": True, "reminder_hours": [24, 6, 1]}
        await message.answer(
            f"Включены: {settings['enable_reminders']}\n"
            f"За сколько часов до дедлайна отправлять уведомления: {settings['reminder_hours']}",
            reply_markup=get_notifications_kb()
        )
        logger.info("Меню настроек отправлено user_id=%d", user_id)
    except Exception as e:
        logger.error(f"Ошибка в обработчике вызова настроек уведомлений: {e}")
        await message.answer("Произошла ошибка. Попробуйте снова.")
        await state.clear()


# Обработка кнопок настроек
@router.message(F.text == "Включить уведомления")
async def enable_notifications(message: Message, state: FSMContext):
    try:
        db = router.db
        await db.update_notification_settings(message.chat.id, enable_reminders=True)
        await message.answer("Уведомления включены ✅", reply_markup=get_notifications_kb())

    except Exception as e:
        logger.error(f"Ошибка в обработчике кнопок настроек(включение уведомлений): {e}")
        await message.answer("Произошла ошибка. Попробуйте снова.")
        await state.clear()


@router.message(F.text == "Отключить уведомления")
async def disable_notifications(message: Message, state: FSMContext):
    try:
        db = router.db
        await db.update_notification_settings(message.chat.id, enable_reminders=False)
        await message.answer("Уведомления отключены ❌", reply_markup=get_notifications_kb())

    except Exception as e:
        logger.error(f"Ошибка в обработчике кнопок настроек(выключение уведомлений): {e}")
        await message.answer("Произошла ошибка. Попробуйте снова.")
        await state.clear()


@router.message(F.text == "Назад")
async def back_to_main(message: Message, state: FSMContext):
    try:
        await message.answer("Главное меню:", reply_markup=get_main_kb())
        await state.clear()

    except Exception as e:
        logger.error(f"Ошибка в обработчике кнопок настроек(возврат в главное меню): {e}")
        await message.answer("Произошла ошибка. Попробуйте снова.")
        await state.clear()


@router.message(F.text == "Выбрать интервалы")
async def select_reminder_intervals(message: Message, state: FSMContext):
    try:
        user_id=message.chat.id
        db = router.db
        settings = await db.get_notification_settings(user_id)
        if not settings:
            await db.update_notification_settings(user_id, True, [24, 6, 1])
            settings = {"enable_reminders": True, "reminder_hours": [24, 6, 1]}

        try:
            await message.edit_text(
                f"За сколько часов до дедлайна отправлять уведомления(вкл/выкл уведомление):\n"
                f"Текущие: {settings['reminder_hours']}",
                reply_markup=get_reminder_kb()
            )
        except Exception:
            await message.answer(
                f"За сколько часов до дедлайна отправлять уведомления(вкл/выкл уведомление):\n"
                f"Текущие: {settings['reminder_hours']}",
                reply_markup=get_reminder_kb()
            )

    except Exception as e:
        logger.error(f"Ошибка в обработчике кнопок настроек(выбор интервалов между уведомлениями): {e}")
        await message.answer("Произошла ошибка. Попробуйте снова.")
        await state.clear()


@router.callback_query(F.data == "reminder_save")
async def save_reminder_settings(callback: CallbackQuery, state: FSMContext):
    try:
        await callback.answer("Настройки сохранены!")
        await show_notifications(callback.message, state)
    except Exception as e:
        logger.error(f"Ошибка в обработчике кнопок настроек(сохранение интервалов): {e}")
        await callback.message.answer("Произошла ошибка. Попробуйте снова.")
        await state.clear()
