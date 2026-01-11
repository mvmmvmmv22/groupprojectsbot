import asyncpg
from datetime import datetime
import logging


logger = logging.getLogger(__name__)


# Инит
class Database:
    def __init__(self, dsn: str):
        self.dsn = dsn
        self.pool = None


# Подключение к базе данных
    async def connect(self):
        try:
            self.pool = await asyncpg.create_pool(self.dsn)
            logger.info(f"Подключение к PostgreSQL успешно")

        except Exception as e:
            logger.error(f"Ошибка подключения к PostgreSQL: {e}")
            raise


# Выполнить запрос
    async def execute(self, query: str, *args):
        try:
            async with self.pool.acquire() as conn:
                return await conn.execute(query, *args)
            logger.info(f"Был выполнен запрос к PostgreSQL(execute): {query}")

        except Exception as e:
            logger.error(f"Ошибка выполнения запроса к PostgreSQL(execute): {e}")
            raise


# Извлечь данные из запроса
    async def fetch(self, query: str, *args):
        try:
            logger.info(f"Был выполнен запрос к PostgreSQL(fetch): {query}")
            async with self.pool.acquire() as conn:
                return await conn.fetch(query, *args)

        except Exception as e:
            logger.error(f"Ошибка выполнения запроса к PostgreSQL(fetch): {e}")
            raise


# Проверка на существование пользователя
    async def user_exists(self, user_id):
        query = """
        SELECT * FROM users
        WHERE user_id = $1;
        """
        result = await self.fetch(query, user_id)
        return result


# Создание проекта в PostgreSQL
    async def create_project(self, title: str, creator_id: int) -> int:
        query = """
        INSERT INTO projects (title, creator_id, created_at)
        VALUES ($1, $2, NOW())
        RETURNING id;
        """
        try:
            project_id = await self.pool.fetchval(query, title, creator_id)
            logger.info(f"Проект с ID:{project_id} создан пользователем с ID:{creator_id}")
            return project_id

        except Exception as e:
            logger.error(f"Ошибка создания проекта: {e}")
            raise


# Получение списка проектов
    async def get_user_projects(self, user_id: int):
        query = """
        SELECT * FROM projects
        WHERE creator_id = $1;
        """
        try:
            projects = await self.fetch(query, user_id)
            logger.info(f"Получен список проектов для пользователя с ID:{user_id}")
            return projects

        except Exception as e:
            logger.error(f"Ошибка получения списка проектов: {e}")
            raise


# Удаление проекта
    async def delete_project(self, project_id: int, user_id: int) -> bool:
        try:
            row = await self.fetch(
                "SELECT 1 FROM projects WHERE id = $1 AND creator_id = $2;",
                project_id, user_id
            )
            if not row:
                logger.error(f"Ошибка удаления проекта: проекта не существует/у удаляющего пользователя нет прав")
                return False

            await self.execute(
                "DELETE FROM project_members WHERE project_id = $1;",
                project_id
            )
            await self.execute(
                "DELETE FROM projects WHERE id = $1;",
                project_id
            )
            logger.info(f"Проект с ID:{project_id} пользователя с ID:{user_id} удалён!")
            return True

        except Exception as e:
            logger.error(f"Ошибка удаления проекта: {e}")
            raise


# Добавление участника в проект
    async def add_member(self, project_id: int, user_id: int, creator_id: int) -> bool:
        try:
            row = await self.fetch(
                "SELECT 1 FROM projects WHERE id = $1 AND creator_id = $2;",
                project_id, creator_id
            )
            if not row:
                logger.error(f"Ошибка добавления участника в проект: проекта не существует/у добавляющего пользователя нет прав")
                return False

            if not await self.user_exists(user_id):
                logger.error(f"Ошибка добавления участника в проект: пользователя не существует")
                return False

            await self.execute(
                "INSERT INTO project_members (project_id, user_id) VALUES ($1, $2) ON CONFLICT DO NOTHING;",
                project_id, user_id
            )
            logger.info(f"В проект с ID:{project_id} пользователем с ID:{creator_id} добавлен пользователь с ID:{user_id}")
            return True

        except Exception as e:
            logger.error(f"Ошибка добавления пользователя в проект: {e}")
            raise


# Установка дедлайна
    async def set_deadline(self, project_id: int, deadline: datetime, creator_id: int) -> bool:
        try:
            row = await self.fetch(
                "SELECT 1 FROM projects WHERE id = $1 AND creator_id = $2;",
                project_id, creator_id
            )
            if not row:
                logger.error(f"Ошибка установки дедлайна: проекта не существует/у добавляющего пользователя нет прав")
                return False

            await self.execute(
                "UPDATE projects SET deadline = $1 WHERE id = $2;",
                deadline, project_id
            )
            logger.info(f"В проекте с ID:{project_id} пользователем с ID:{creator_id} установлен дедлайн {datetime}")
            return True

        except Exception as e:
            logger.error(f"Ошибка установки дедлайна: {e}")
            raise


# Получение настроек уведомлений
    async def get_notification_settings(self, user_id: int) -> dict | None:
        try:
            result = await self.fetch(
                "SELECT enable_reminders, reminder_hours FROM notifications_settings WHERE user_id = $1;",
                user_id
            )
            if result:
                row = result[0]
                return {
                    "enable_reminders": row["enable_reminders"],
                    "reminder_hours": row["reminder_hours"]
                }
            logger.debug(f"У пользователя с ID:{user_id} нет настроек")
            return None
        except Exception as e:
            logger.error(f"Ошибка получения настроек для пользователя с ID:{user_id}: {e}")
            return None


# Обновление настроек уведомлений
    async def update_notification_settings(
        self,
        user_id: int,
        enable_reminders: bool | None = None,
        reminder_hours: list[int] | None = None
    ):
        try:
            if reminder_hours is not None:
                if not reminder_hours:
                    raise ValueError("Список интервалов не может быть пустым")
                if not all(isinstance(h, int) and h > 0 for h in reminder_hours):
                    raise ValueError("Все интервалы должны быть положительными целыми числами")
            query = """
                INSERT INTO notifications_settings (user_id, enable_reminders, reminder_hours)
                VALUES ($1, $2, $3)
                ON CONFLICT (user_id) DO UPDATE
                SET
                    enable_reminders = CASE
                        WHEN $2 IS NULL THEN notifications_settings.enable_reminders
                        ELSE $2
                    END,
                    reminder_hours = CASE
                        WHEN $3 IS NULL THEN notifications_settings.reminder_hours
                        ELSE $3
                    END;
            """
            await self.execute(query, user_id, enable_reminders, reminder_hours)
            logger.info(f"Настройки сохранены для пользователя с ID:{user_id}")

        except Exception as e:
            logger.error(f"Ошибка сохранения настроек для пользователя с ID:{user_id}")
            raise


# Получение проектов с приближающимся дедлайном
    async def get_projects_near_deadline(self) -> list[dict]:
        query = """
        SELECT DISTINCT
            p.id,
            p.title,
            p.deadline,
            p.creator_id,
            ns.reminder_hours
        FROM projects p
        JOIN notifications_settings ns ON p.creator_id = ns.user_id
        JOIN UNNEST(ns.reminder_hours) AS rh ON TRUE
        WHERE
            p.deadline BETWEEN NOW() AND NOW() + INTERVAL '24 hours'
            AND ns.enable_reminders = TRUE
            AND (
                p.last_notification_sent IS NULL
                OR p.last_notification_sent <
                p.deadline - (rh * INTERVAL '1 hour')
            )
            AND p.deadline - (rh * INTERVAL '1 hour') >= NOW()
            ORDER BY p.deadline;
            """
        try:
            projects = await self.fetch(query)
            logger.info("Найдено проектов для уведомлений: %d", len(projects))
            return projects

        except Exception as e:
            logger.error(f"Ошибка выборки проектов: {e}")
            return []


# Обновить таймер уведомлений
    async def set_last_notification(self, project_id: int, ts: datetime):
        try:
            await self.execute("UPDATE projects SET last_notification_sent = $1 WHERE id = $2;", ts, project_id)
            logger.info(f"Таймер уведомлений обновлён для проекта с ID:{project_id}")

        except Exception as e:
            logger.error(f"Ошибка обновления таймера уведомлений для проекта с ID:{project_id}: {e}")


# Установить unikey
    async def set_unikey(self, unikey: str, active: bool, answer: bool):
        query = """
        INSERT INTO invites (key, active, answer)
        VALUES ($1, $2, $3)
        ON CONFLICT (key) DO UPDATE
        SET active = $2, answer = $3
        """
        try:
            await self.execute(query, unikey, active, answer)
            logger.info(f"Задан unikey: {unikey}")

        except Exception as e:
            logger.error(f"Ошибка установки уникального кода приглашения: {e}")


# Проверить unikey на активность
    async def unikey_isactive(self, unikey: str) -> bool:
        query = """
        SELECT * FROM invites
        WHERE key = $1
        AND active = True;
        """
        try:
            result = await self.fetch(query, unikey)
            if not result:
                logger.info(f"unikey {unikey} не найден или неактивен")
                return False
            record = result[0]
            is_active = record['active']
            is_valid = is_active
            logger.info(f"unikey {unikey} проверен, результат: {is_valid}")
            return is_valid

        except Exception as e:
            logger.error(f"Ошибка проверки уникального кода приглашения: {e}")
            return False



    async def check_unikey(self, unikey: str) -> bool:
        query = """
        SELECT * FROM invites
        WHERE key = $1
        AND active = True;
        """
        try:
            result = await self.fetch(query, unikey)
            if not result:
                logger.info(f"unikey {unikey} не найден или неактивен")
                return False
            record = result[0]
            is_active = record['active']
            has_answer = record['answer']
            is_valid = is_active and has_answer
            logger.info(f"unikey {unikey} проверен, результат: {is_valid}")
            return is_valid

        except Exception as e:
            logger.error(f"Ошибка проверки уникального кода приглашения: {e}")
            return False
