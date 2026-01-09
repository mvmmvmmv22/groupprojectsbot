from db import Database
from keyboards import get_main_kb
import os
from dotenv import load_dotenv
from aiogram import Router, types, F
from aiogram.types import CallbackQuery, Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

load_dotenv()
DB_DSN = os.getenv("DB_DSN")
router = Router()
router.db = Database(DB_DSN)

# Состояния FSM
class CreateProject(StatesGroup):
    enter_title = State()

class DeleteProject(StatesGroup):
    confirm = State()

class AddMember(StatesGroup):
    wait_project_id = State()
    wait_user_id = State()

class SetDeadline(StatesGroup):
    input_date = State()



# Обработка названия проекта(по состоянию FSM)
@router.message(CreateProject.enter_title)
async def create_project_finish(message: types.Message, state: FSMContext):
    try:
        db = router.db
        title = message.text.strip()

        if title.lower() == "отмена": # Обработка "Отмена"(клавиатура отмены)
            await state.clear()
            await message.answer("Создание проекта отменено.", reply_markup=get_main_kb())
            return

        if not title:
            await message.answer("Название не может быть пустым. Попробуйте снова:", reply_markup=get_cancel_kb())
            return

        if len(title) > 200:
            await message.answer(
                "Название слишком длинное (максимум 200 символов). Попробуйте снова:",
                reply_markup=get_cancel_kb()
            )
            return

        await db.create_project(title, message.chat.id)
        await message.answer(f"Проект \"{title}\" создан! ✅", reply_markup=get_main_kb())
        await state.clear()

        logger.info(f"От пользователя с ID:{message.chat.id} обработана команда \"Закончить создание проекта\"")

    except Exception as e:
        logger.error(f"Ошибка в обработчике ввода названия проекта: {e}")
        await message.answer("Произошла ошибка. Попробуйте снова.")
        await state.clear()


# Обработка подтверждения удаления проекта (по состоянию FSM)
@router.callback_query(F.data.startswith("confirm_delete_"))
async def confirm_delete_project(callback: types.CallbackQuery, state: FSMContext):
    try:
        data = await state.get_data()
        project_id = data.get("project_id")

        if not project_id:
            await callback.answer("Ошибка: проект не найден.")
            return

        db = router.db
        success = await db.delete_project(project_id, callback.from_user.id)

        chat_id = callback.message.chat.id

        if success:
            msg_id = data.get(f"project_msg_{project_id}")
            if msg_id:
                try:
                    await callback.bot.delete_message(chat_id=chat_id, message_id=msg_id)
                    logger.info(f"Сообщение о проекте {project_id} удалено (message_id={msg_id})")
                except Exception as e:
                    logger.error(f"Не удалось удалить сообщение {msg_id}: {e}")
            try:
                await callback.bot.delete_message(chat_id=chat_id, message_id=callback.message.message_id)
            except Exception as e:
                logger.error(f"Не удалось удалить подтверждение: {e}")


            await callback.answer("Проект удалён ✅")
        else:
            await callback.message.answer("Ошибка: у вас нет прав на удаление этого проекта.")
        await state.update_data({
            f"project_msg_{project_id}": None,
            f"project_title_{project_id}": None
        })
        await state.clear()  # Или state.reset_state()

        logger.info(f"Проект {project_id} удалён пользователем {callback.from_user.id}")

    except Exception as e:
        logger.error(f"Ошибка в обработчике подтверждения удаления проекта: {e}")
        await callback.message.answer("Произошла ошибка. Попробуйте снова.")
        await state.clear()


# Обработка отмены удаления проекта (по состоянию FSM)
@router.callback_query(F.data == "cancel_deletion")
async def cancel_deletion(callback: types.CallbackQuery, state: FSMContext):
    try:
        await callback.message.answer("Удаление отменено.")
        await state.clear()
        logger.info(f"От пользователя с ID:{callback.from_user.id} обработана команда \"Отменить удаление проекта\"")

    except Exception as e:
        logger.error(f"Ошибка в обработчике отмены удаления проекта: {e}")
        await callback.message.answer("Произошла ошибка. Попробуйте снова.")
        await state.clear()


# Обработка даты дедлайна (по состоянию FSM)
@router.message(SetDeadline.input_date)
async def process_deadline_input(message: Message, state: FSMContext):
    try:
        user_input = message.text.strip()
        try:
            deadline = datetime.strptime(user_input, "%d.%m.%Y %H:%M")
        except ValueError:
            await message.answer(
                "Неверный формат даты!\n"
                "Используйте: <b>ДД.ММ.ГГГГ ЧЧ:ММ</b>\n"
                "Пример: 25.12.2026 18:30",
                parse_mode="HTML"
            )
            return

        data = await state.get_data()
        project_id = data.get("project_id")
        creator_id = message.chat.id

        if not project_id:
            await message.answer("Ошибка: проект не найден.")
            await state.clear()
            return

        db = router.db
        success = await db.set_deadline(project_id, deadline, creator_id)

        if success:
            msg_id = data.get(f"project_msg_{project_id}")
            project_title = data.get(f"project_title_{project_id}", "Неизвестно")
            chat_id = message.chat.id

            if msg_id:
                new_text = (
                    f"Проект №{project_id}: {project_title}\n"
                    f"Дедлайн: {deadline.strftime('%d.%m.%Y %H:%M')}"
                )
                try:
                    await message.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=msg_id,
                        text=new_text,
                        reply_markup=get_project_actions_kb(project_id)
                    )
                    logger.info(f"Дедлайн проекта {project_id} обновлён")
                except Exception as e:
                    logger.error(f"Не удалось обновить сообщение {msg_id}: {e}")

            await message.answer(
                f"Дедлайн успешно установлен:\n<b>{deadline.strftime('%d.%m.%Y %H:%M')}</b>",
                parse_mode="HTML"
            )
        else:
            await message.answer("Ошибка: у вас нет прав на установку дедлайна для этого проекта.")

        await state.clear()

    except Exception as e:
        logger.error(f"Ошибка в обработчике ввода даты дедлайна: {e}")
        await message.send("Произошла ошибка. Попробуйте снова.")
        await state.clear()


# Обработка установки времени между уведомлениями
@router.callback_query(F.data.startswith("set_hours_"))
async def set_reminder_hours(callback: CallbackQuery, state: FSMContext):
    try:
        hours_str = callback.data.split("_")[-1]  # например, "24_6_1"
        hours = list(map(int, hours_str.split("-")))
        await update_notification_settings(callback.from_user.id, hours=hours)
        await callback.answer(f"Напоминания будут приходить за {', '.join(map(str, hours))} часов")
        await notification_settings(callback.message, None)

    except Exception as e:
        logger.error(f"Ошибка в обработчике установки времени между уведомлениями: {e}")
        await callback.message.answer("Произошла ошибка. Попробуйте снова.")
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


# Обработка обновления интервалов
@router.callback_query(F.data.startswith("reminder_toggle_"))
async def toggle_reminder_hour(callback: CallbackQuery, state: FSMContext):
    try:
        user_id = callback.from_user.id
        hour = int(callback.data.split("_")[-1])
        db = router.db
        settings = await db.get_notification_settings(user_id)
        hours = settings["reminder_hours"] if settings else []
        if hour in hours:
            hours.remove(hour)
        else:
            hours.append(hour)
        await db.update_notification_settings(
            user_id=user_id,
            enable_reminders=True,
            reminder_hours=hours
        )

        await callback.answer(f"Интервалы обновлены: {hours}")
        await select_reminder_intervals(callback.message, state)

    except Exception as e:
        logger.error(f"Ошибка в обработчике обновления интервалов: {e}")
        await callback.message.answer("Произошла ошибка. Попробуйте снова.")
        await state.clear()

