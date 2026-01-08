from datetime import datetime
from typing import List

class Project:
    def __init__(self, id: int, title: str, deadline: datetime, next_notification: datetime = None):
        self.id = id
        self.title = title
        self.deadline = deadline
        self.next_notification = next_notification

class UserNotificationSettings:
    def __init__(self, user_id: int, enable_reminders: bool, reminder_hours: List[int]):
        self.user_id = user_id
        self.enable_reminders = enable_reminders
        self.reminder_hours = reminder_hours
