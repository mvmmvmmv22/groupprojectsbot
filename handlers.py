from aiogram import Router, types, F
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
    wait_project_id = State()
    wait_deadline = State()



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
        logger.info(f"От пользователя с ID:{user_id} обработана команда /start")
    except Exception as e:
            logger.error(f"Ошибка: {e}")
            raise


@router.message(F.text == "Создать проект")
async def create_project_start(message: types.Message, state: FSMContext):
    try:
        await message.answer("Введите название проекта:", reply_markup=get_cancel_kb())
        await state.set_state(CreateProject.enter_title)
        logger.info(f"От пользователя с ID:{user_id} обработана команда \"Создать проект\" с клавиатуры")
    except Exception as e:
            logger.error(f"Ошибка: {e}")
            raise



@router.message(CreateProject.enter_title)
async def create_project_finish(message: types.Message, state: FSMContext):
    try:
        db = router.db
        title = message.text.strip()

        if title.lower() == "отмена":
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
        logger.info(f"От пользователя с ID:{user_id} обработана команда \"\"")
    except Exception as e:
            logger.error(f"Ошибка: {e}")
            raise


@router.message(F.text == "Мои проекты")
async def my_projects(message: types.Message):
    db = router.db
    projects = await db.get_user_projects(message.from_user.id)

    if not projects:
        await message.answer("У вас нет проектов.")
        return

    for p in projects:
        text = f"Проект №{p['id']}: {p['title']}\n"
        if p['deadline']:
            text += f"Дедлайн: {p['deadline'].strftime('%d.%m.%Y %H:%M')}\n"
        else:
            text += "Дедлайн не установлен\n"

        await message.answer(
            text,
            reply_markup=get_project_actions_kb(p['id'])
        )



# Обработчик удаления проекта
@router.callback_query(F.data.startswith("delete_project_"))
async def confirm_delete_project(callback: types.CallbackQuery, state: FSMContext):
    db = router.db
    project_id = int(callback.data.split("_")[-1])

    await callback.message.answer(
        f"Вы уверены, что хотите удалить проект №{project_id}?",
        reply_markup=get_confirm_deletion_kb(project_id)
    )
    await state.update_data(project_id=project_id)
    await state.set_state(DeleteProject.confirm)




@router.callback_query(F.data.startswith("confirm_delete_"))
async def delete_project(callback: types.CallbackQuery, state: FSMContext):
    db = router.db
    data = await state.get_data()
    project_id = data.get("project_id")

    if not project_id:
        await callback.answer("Ошибка: проект не найден.")
        return

    success = await db.delete_project(project_id, callback.from_user.id)

    if success:
        await callback.message.answer(f"Проект №{project_id} удалён ✅")
    else:
        await callback.message.answer("Ошибка: у вас нет прав на удаление этого проекта.")


    await state.clear()



@router.callback_query(F.data == "cancel_deletion")
async def cancel_deletion(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Удаление отменено.")
    await state.clear()
