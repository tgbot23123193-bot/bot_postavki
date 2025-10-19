"""
Extension management handlers.

This module handles commands for linking and managing Chrome extension.
"""

from datetime import datetime

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from sqlalchemy import select

from ...database import get_session
from ...database.models import ExtensionLink, User
from ...api.extension_api import generate_link_key
from ...utils.logger import get_logger

logger = get_logger(__name__)

router = Router(name='extension_router')


@router.message(Command('extension'))
async def cmd_extension(message: Message):
    """
    Handle /extension command.
    Generates link key for extension or shows existing link status.
    """
    user_id = message.from_user.id
    
    try:
        async with get_session() as session:
            # Get or create user
            result = await session.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                # Create user
                user = User(
                    id=user_id,
                    username=message.from_user.username,
                    first_name=message.from_user.first_name,
                    last_name=message.from_user.last_name
                )
                session.add(user)
                await session.flush()
            
            # Check if extension link exists
            result = await session.execute(
                select(ExtensionLink)
                .where(ExtensionLink.user_id == user_id)
                .where(ExtensionLink.is_active == True)
            )
            ext_link = result.scalar_one_or_none()
            
            # Если ключа нет - создаем
            if not ext_link:
                link_key = generate_link_key()
                ext_link = ExtensionLink(
                    user_id=user_id,
                    link_key=link_key,
                    is_active=True
                )
                session.add(ext_link)
                await session.commit()
                logger.info(f"Created extension link key for user {user_id}")
            
            # Формируем сообщение в зависимости от статуса
            if ext_link.linked_at:
                # Уже привязано
                status_text = (
                    "✅ <b>Расширение привязано</b>\n\n"
                    f"📅 Дата привязки: {ext_link.linked_at.strftime('%d.%m.%Y %H:%M')}\n"
                    f"📊 Последняя активность: {ext_link.last_activity.strftime('%d.%m.%Y %H:%M') if ext_link.last_activity else 'Нет данных'}\n\n"
                )
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(
                        text="🔓 Отвязать расширение",
                        callback_data="extension_unlink"
                    )],
                    [InlineKeyboardButton(
                        text="🔄 Создать новый ключ",
                        callback_data="extension_new_key"
                    )]
                ])
            else:
                # Ещё не привязано
                status_text = "🔑 <b>Ваш ключ привязки</b>\n\n"
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(
                        text="📖 Инструкция",
                        callback_data="extension_help"
                    )]
                ])
            
            # Всегда показываем ключ для удобного копирования
            await message.answer(
                f"{status_text}"
                f"🔑 <b>Ключ для копирования:</b>\n"
                f"<code>{ext_link.link_key}</code>\n\n"
                f"💡 <i>Нажмите на ключ, чтобы скопировать</i>",
                reply_markup=keyboard
            )
    
    except Exception as e:
        logger.error(f"Error in extension command: {e}")
        await message.answer(
            "❌ Произошла ошибка при создании ключа.\n"
            "Попробуйте позже или обратитесь в поддержку."
        )


@router.callback_query(F.data == "extension_unlink")
async def callback_extension_unlink(callback: CallbackQuery):
    """Handle extension unlink callback."""
    user_id = callback.from_user.id
    
    try:
        async with get_session() as session:
            result = await session.execute(
                select(ExtensionLink)
                .where(ExtensionLink.user_id == user_id)
            )
            ext_link = result.scalar_one_or_none()
            
            if ext_link:
                ext_link.is_active = False
                await session.commit()
                
                await callback.message.edit_text(
                    "✅ <b>Расширение отвязано</b>\n\n"
                    "Вы можете создать новый ключ командой /extension"
                )
                logger.info(f"Extension unlinked for user {user_id}")
            else:
                await callback.answer("Расширение не найдено", show_alert=True)
    
    except Exception as e:
        logger.error(f"Error unlinking extension: {e}")
        await callback.answer("Ошибка при отвязке расширения", show_alert=True)


@router.callback_query(F.data == "extension_new_key")
async def callback_extension_new_key(callback: CallbackQuery):
    """Handle new key creation callback."""
    user_id = callback.from_user.id
    
    try:
        async with get_session() as session:
            # Deactivate old link
            result = await session.execute(
                select(ExtensionLink)
                .where(ExtensionLink.user_id == user_id)
            )
            old_link = result.scalar_one_or_none()
            
            if old_link:
                old_link.is_active = False
            
            # Create new link
            link_key = generate_link_key()
            new_link = ExtensionLink(
                user_id=user_id,
                link_key=link_key,
                is_active=True
            )
            session.add(new_link)
            await session.commit()
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="📖 Инструкция",
                    callback_data="extension_help"
                )]
            ])
            
            await callback.message.edit_text(
                "🔑 <b>Новый ключ создан!</b>\n\n"
                f"🔑 <b>Ключ для копирования:</b>\n"
                f"<code>{link_key}</code>\n\n"
                f"💡 <i>Нажмите на ключ, чтобы скопировать</i>",
                reply_markup=keyboard
            )
            logger.info(f"Created new extension link key for user {user_id}")
    
    except Exception as e:
        logger.error(f"Error creating new key: {e}")
        await callback.answer("Ошибка при создании ключа", show_alert=True)


@router.callback_query(F.data == "extension_help")
async def callback_extension_help(callback: CallbackQuery):
    """Show extension setup instructions."""
    await callback.message.answer(
        "📖 <b>Подробная инструкция</b>\n\n"
        "<b>1. Установка расширения:</b>\n"
        "• Скачайте архив с расширением\n"
        "• Распакуйте в удобную папку\n"
        "• Откройте Chrome и перейдите в chrome://extensions/\n"
        "• Включите \"Режим разработчика\" (переключатель справа сверху)\n"
        "• Нажмите \"Загрузить распакованное расширение\"\n"
        "• Выберите папку с расширением\n\n"
        "<b>2. Привязка к боту:</b>\n"
        "• Откройте расширение (иконка в панели Chrome)\n"
        "• Перейдите во вкладку \"Привязка\"\n"
        "• Вставьте ключ из бота\n"
        "• Нажмите \"Привязать расширение\"\n\n"
        "<b>3. Использование:</b>\n"
        "• <b>Автоловля</b> - автоматическое нажатие на кнопку бронирования\n"
        "• <b>Перераспределение</b> - автоматическое перераспределение товаров\n\n"
        "После успешной операции вы получите уведомление в этом боте! 🎉"
    )
    await callback.answer()


@router.callback_query(F.data == "extension_info")
async def callback_extension_info(callback: CallbackQuery):
    """Show extension information from main menu."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🔑 Получить ключ привязки",
            callback_data="extension_get_key"
        )],
        [InlineKeyboardButton(
            text="📥 Скачать расширение",
            url="https://github.com/YOUR_REPO/releases/latest"  # TODO: Add actual link
        )],
        [InlineKeyboardButton(
            text="📖 Инструкция",
            callback_data="extension_help"
        )],
        [InlineKeyboardButton(
            text="🔙 Назад в меню",
            callback_data="main_menu"
        )]
    ])
    
    await callback.message.edit_text(
        "🔌 <b>Расширение Chrome для WB</b>\n\n"
        "Расширение позволяет автоматизировать:\n"
        "• 🎯 <b>Автоловлю поставок</b> - автоматическое нажатие на кнопку бронирования\n"
        "• 🔄 <b>Перераспределение</b> - автоматическое перераспределение товаров между складами\n\n"
        "✅ Все уведомления приходят в этот бот!\n\n"
        "<b>Для начала работы:</b>\n"
        "1. Получите ключ привязки\n"
        "2. Скачайте и установите расширение\n"
        "3. Привяжите расширение через ключ\n\n"
        "💡 После привязки расширение будет работать самостоятельно "
        "и присылать вам уведомления о всех успешных операциях!",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data == "extension_get_key")
async def callback_extension_get_key(callback: CallbackQuery):
    """Quick link to get extension key."""
    user_id = callback.from_user.id
    
    try:
        async with get_session() as session:
            # Check if key already exists
            result = await session.execute(
                select(ExtensionLink)
                .where(ExtensionLink.user_id == user_id)
                .where(ExtensionLink.is_active == True)
            )
            ext_link = result.scalar_one_or_none()
            
            # Если ключа нет - создаем
            if not ext_link:
                link_key = generate_link_key()
                ext_link = ExtensionLink(
                    user_id=user_id,
                    link_key=link_key,
                    is_active=True
                )
                session.add(ext_link)
                await session.commit()
                logger.info(f"Created extension link key for user {user_id}")
            
            # Показываем ключ
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="📖 Инструкция",
                    callback_data="extension_help"
                )],
                [InlineKeyboardButton(
                    text="🔙 Назад",
                    callback_data="extension_info"
                )]
            ])
            
            status = "✅ Привязано" if ext_link.linked_at else "⏳ Ожидает привязки"
            
            await callback.message.edit_text(
                f"🔑 <b>Ваш ключ привязки</b>\n\n"
                f"Статус: {status}\n\n"
                f"🔑 <b>Ключ для копирования:</b>\n"
                f"<code>{ext_link.link_key}</code>\n\n"
                f"💡 <i>Нажмите на ключ, чтобы скопировать</i>",
                reply_markup=keyboard
            )
            
    except Exception as e:
        logger.error(f"Error getting extension key: {e}")
        await callback.answer("Ошибка получения ключа", show_alert=True)

