"""
Утилиты для отправки уведомлений пользователям.
"""

from typing import Optional
from aiogram import Bot
from ...config import settings


async def notify_user(user_id: int, message: str, parse_mode: str = "HTML") -> bool:
    """Отправить уведомление пользователю."""
    try:
        bot = Bot(token=settings.telegram.bot_token)
        await bot.send_message(
            chat_id=user_id,
            text=message,
            parse_mode=parse_mode
        )
        await bot.session.close()
        return True
    except Exception as e:
        print(f"Failed to notify user {user_id}: {e}")
        return False



