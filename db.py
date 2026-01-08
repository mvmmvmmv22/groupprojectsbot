import asyncpg
from datetime import datetime
import os
import logging

logging.getLogger('asyncpg').setLevel(logging.DEBUG)
logger = logging.getLogger(__name__)

class Database:
    def __init__(self, dsn: str):
        self.dsn = dsn
        self.pool = None

    async def connect(self):
        self.pool = await asyncpg.create_pool(self.dsn)

    async def execute(self, query: str, *args):
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)

    async def fetch(self, query: str, *args):
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args)

    async def create_project(self, title: str, creator_id: int) -> int:
        query = """
        INSERT INTO projects (title, creator_id, created_at)
        VALUES ($1, $2, NOW())
        RETURNING id
        """
        try:
            project_id = await self.pool.fetchval(query, title, creator_id)
            logger.info(f"Проект с ID:{project_id} успешно создан!")
            return project_id
        except Exception as e:
            logger.error(f"Ошибка: {e}")
            raise



    async def get_user_projects(self, user_id: int):
        try:
            query = """
            SELECT * FROM projects
            WHERE creator_id = $1
            """
            logger.info(f"Пользователь с ID:{user_id} получил список проектов")
            return await self.fetch(query, user_id)

        except Exception as e:
            logger.error(f"Ошибка: {e}")
            raise

    async def delete_project(self, project_id: int, user_id: int) -> bool:
        try:
            row = await self.fetch(
                "SELECT 1 FROM projects WHERE id = $1 AND creator_id = $2",
                project_id, user_id
            )
            if not row:
                return False

            await self.execute(
                "DELETE FROM project_members WHERE project_id = $1",
                project_id
            )
            await self.execute(
                "DELETE FROM projects WHERE id = $1",
                project_id
            )
            logger.info(f"Проект с ID:{project_id} пользователя с ID:{user_id} удалён!")
            return True

        except Exception as e:
            logger.error(f"Ошибка: {e}")
            raise

    async def add_member(self, project_id: int, user_id: int, creator_id: int) -> bool:
        try:
            row = await self.fetch(
                "SELECT 1 FROM projects WHERE id = $1 AND creator_id = $2",
                project_id, creator_id
            )
            if not row:
                return False

            user_exists = await self.fetch(
                "SELECT 1 FROM users WHERE user_id = $1",
                user_id
            )
            if not user_exists:
                return False

            await self.execute(
                "INSERT INTO project_members (project_id, user_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                project_id, user_id
            )
            logger.info(f"В проект с ID:{project_id} пользователем с ID:{creator_id} добавлен пользователь с ID:{user_id}")
            return True

        except Exception as e:
            logger.error(f"Ошибка: {e}")
            raise

    async def set_deadline(self, project_id: int, deadline: datetime, creator_id: int) -> bool:
        try:
            row = await self.fetch(
                "SELECT 1 FROM projects WHERE id = $1 AND creator_id = $2",
                project_id, creator_id
            )
            if not row:
                return False

            await self.execute(
                "UPDATE projects SET deadline = $1 WHERE id = $2",
                deadline, project_id
            )
            logger.info(f"В проекте с ID:{project_id} пользователем с ID:{creator_id} установлен дедлайн {datetime}")
            return True

        except Exception as e:
            logger.error(f"Ошибка: {e}")
            raise


    async def get_notification_settings(self, user_id: int) -> dict | None:
        try:
            result = await self.fetch(
                "SELECT enable_reminders, reminder_hours FROM notifications_settings WHERE user_id = $1",
                user_id
            )
            if result:
                row = result[0]  # Берём первую запись
                return {
                    "enable_reminders": row["enable_reminders"],
                    "reminder_hours": row["reminder_hours"]
                }
            return None
        except Exception as e:
            logger.error("Ошибка получения настроек user_id=%d: %s", user_id, e)
            return None


    async def update_notification_settings(
        self,
        user_id: int,
        enable_reminders: bool | None = None,
        reminder_hours: list[int] | None = None
    ):
        try:
            # Валидация входных данных
            if reminder_hours is not None:
                if not reminder_hours:
                    raise ValueError("Список интервалов не может быть пустым")
                if not all(isinstance(h, int) and h > 0 for h in reminder_hours):
                    raise ValueError("Все интервалы должны быть положительными целыми числами")

            # Формируем запрос
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
                    END
            """

            # Выполняем запрос
            await self.execute(query, user_id, enable_reminders, reminder_hours)

            logger.info("Настройки сохранены для user_id=%d: enable=%s, hours=%s",
                        user_id, enable_reminders, reminder_hours)

        except Exception as e:
            logger.error("Ошибка сохранения настроек user_id=%d: %s", user_id, e)
            raise  # Перебрасываем исключение для обработки в хендлере


    async def get_projects_near_deadline(self) -> list[dict]:
        try:
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
                -- Дополнительно проверяем, что интервал rh актуален
                AND p.deadline - (rh * INTERVAL '1 hour') >= NOW()
            ORDER BY p.deadline
            """
            projects = await self.fetch(query)
            logger.info("Найдено проектов для уведомлений: %d", len(projects))
            return projects
        except Exception as e:
            logger.error("Ошибка выборки проектов: %s", e)
            return []


    async def set_last_notification(self, project_id: int, ts: datetime):
        try:
            await self.execute("UPDATE projects SET last_notification_sent = $1 WHERE id = $2", ts, project_id)
            logger.info("last_notification_sent обновлено для project_id=%d", project_id)
        except Exception as e:
            logger.error("Ошибка обновления project_id=%d: %s", project_id, e)
