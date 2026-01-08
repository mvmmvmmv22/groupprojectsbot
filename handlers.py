from aiogram import Router, types, F
from aiogram.types import CallbackQuery, Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime
import logging
from keyboards import (
    get_main_kb,
    get_project_actions_kb,
    get_cancel_kb,
    get_confirm_deletion_kb
)

logger = logging.getLogger(__name__)

router = Router()

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

# Обработка /start
@router.message(Command("start"))
async def cmd_start(message: types.Message):
    try:
        db = router.db
        await db.execute(
            "INSERT INTO users (user_id, username, full_name) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
            message.from_user.id,
            message.from_user.username,
            message.from_user.full_name
        )
        await message.answer(
            "Добро пожаловать! Давайте управлять проектами.",
            reply_markup=get_main_kb()
        )
        logger.info(f"От пользователя с ID:{message.from_user.id} обработана команда /start")
    except Exception as e:
            logger.error(f"Ошибка: {e}")
            await callback.message.answer("Произошла ошибка. Попробуйте снова.")
            await state.clear()


# Обработка "Создать проект(основная клавиатура)"
@router.message(F.text == "Создать проект")
async def create_project_start(message: types.Message, state: FSMContext):
    try:
        await message.answer("Введите название проекта:", reply_markup=get_cancel_kb())
        await state.set_state(CreateProject.enter_title)

        logger.info(f"От пользователя с ID:{message.from_user.id} обработана команда \"Создать проект\"")

    except Exception as e:
            logger.error(f"Ошибка: {e}")
            await callback.message.answer("Произошла ошибка. Попробуйте снова.")
            await state.clear()


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

        await db.create_project(title, message.from_user.id)
        await message.answer(f"Проект \"{title}\" создан! ✅", reply_markup=get_main_kb())
        await state.clear()

        logger.info(f"От пользователя с ID:{message.from_user.id} обработана команда \"Закончить создание проекта\"")

    except Exception as e:
            logger.error(f"Ошибка: {e}")
            await callback.message.answer("Произошла ошибка. Попробуйте снова.")
            await state.clear()


# Обработка "Мои проекты" (основная клавиатура)
@router.message(F.text == "Мои проекты")
async def my_projects(message: types.Message, state: FSMContext):
    try:
        db = router.db
        projects = await db.get_user_projects(message.from_user.id)

        if not projects:
            await message.answer("У вас нет проектов.")
            logger.info(f"От пользователя с ID:{message.from_user.id} обработана команда \"Мои проекты\"")
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
            await state.update_data({f"project_msg_{p['id']}": sent_msg.message_id})


        logger.info(f"От пользователя с ID:{message.from_user.id} обработана команда \"Мои проекты\"")


    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await message.answer("Произошла ошибка. Попробуйте снова.")
        await state.clear()


# Обработка удаления проекта (инлайн-клавиатура "действия с проектом")
@router.callback_query(F.data.startswith("delete_project_"))
async def confirm_delete_project(callback: types.CallbackQuery, state: FSMContext):
    try:
        db = router.db
        project_id = int(callback.data.split("_")[-1])

        await callback.message.answer(
            f"Вы уверены, что хотите удалить проект №{project_id}?",
            reply_markup=get_confirm_deletion_kb(project_id)
        )
        await state.update_data(project_id=project_id)
        await state.set_state(DeleteProject.confirm)

        logger.info(f"От пользователя с ID:{callback.from_user.id} обработана команда \"Начать удаление проекта\"")


    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await callback.message.answer("Произошла ошибка. Попробуйте снова.")
        await state.clear()


# Обработка подтверждения удаления проекта (по состоянию FSM)
@router.callback_query(F.data.startswith("confirm_delete_"))
async def delete_project(callback: types.CallbackQuery, state: FSMContext):
    try:
        db = router.db
        data = await state.get_data()
        project_id = data.get("project_id")


        if not project_id:
            await callback.answer("Ошибка: проект не найден.")
            return

        success = await db.delete_project(project_id, callback.from_user.id)

        if success:
            msg_id = data.get(f"project_msg_{project_id}")
            chat_id = callback.message.chat.id
            if msg_id:
                try:
                    await callback.bot.delete_message(chat_id=chat_id, message_id=msg_id)
                except:
                    pass
            try:
                await callback.bot.delete_message(
                    chat_id=chat_id,
                    message_id=callback.message.message_id
                )
            except:
                pass

            await callback.answer("Проект удалён ✅")
        else:
            await callback.message.answer("Ошибка: у вас нет прав на удаление этого проекта.")


        await state.clear()
        logger.info(f"От пользователя с ID:{callback.from_user.id} обработана команда \"Подтвердить удаление проекта\"")


    except Exception as e:
        logger.error(f"Ошибка: {e}")
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
        logger.error(f"Ошибка: {e}")
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
        logger.error(f"Ошибка: {e}")
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
        creator_id = message.from_user.id

        if not project_id:
            await message.answer("Ошибка: проект не найден.")
            await state.clear()
            return

        db = router.db
        success = await db.set_deadline(project_id, deadline, creator_id)

        if success:
            msg_id = data.get(f"project_msg_{project_id}")
            chat_id = message.chat.id

            if msg_id:
                new_text = (
                    f"Проект №{project_id}: {data.get('project_title', 'Неизвестно')}\n"
                    f"Дедлайн: {deadline.strftime('%d.%m.%Y %H:%M')}"
                )
                try:
                    await message.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=msg_id,
                        text=new_text,
                        reply_markup=get_project_actions_kb(project_id)
                    )
                except:
                    pass

            await message.answer(
                f"Дедлайн успешно установлен:\n<b>{deadline.strftime('%d.%m.%Y %H:%M')}</b>",
                parse_mode="HTML"
            )
            logger.info(f"Дедлайн для проекта с ID:{project_id} обновлён пользователем с ID:{creator_id}")
        else:
            await message.answer("Ошибка: у вас нет прав на установку дедлайна для этого проекта")

        await state.clear()

    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await message.answer("Произошла ошибка. Попробуйте снова.")
        await state.clear()
