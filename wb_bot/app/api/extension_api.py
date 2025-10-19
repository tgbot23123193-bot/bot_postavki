"""
API endpoints for Chrome Extension integration.

This module provides REST API endpoints for linking and managing
Chrome extension connections to the bot.
"""

import secrets
from datetime import datetime
from typing import Optional

from aiohttp import web
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database.models import ExtensionLink, User
from ..database.connection import get_session
from ..utils.logger import get_logger

logger = get_logger(__name__)

# Store active bot instance for sending messages
_bot_instance = None


def set_bot_instance(bot):
    """Set bot instance for sending messages."""
    global _bot_instance
    _bot_instance = bot


def generate_link_key() -> str:
    """Generate unique link key for extension."""
    return f"EXT_{secrets.token_urlsafe(32)}"


async def link_extension(request: web.Request) -> web.Response:
    """
    Link extension to user account.
    
    POST /api/extension/link
    Body: {"linkKey": "EXT_..."}
    Returns: {"success": true, "userId": 123456, "botToken": "..."}
    """
    try:
        data = await request.json()
        link_key = data.get('linkKey')
        
        if not link_key:
            return web.json_response({
                'success': False,
                'error': 'Link key is required'
            }, status=400)
        
        # Find extension link by key
        async with get_session() as session:
            result = await session.execute(
                select(ExtensionLink)
                .where(ExtensionLink.link_key == link_key)
                .where(ExtensionLink.is_active == True)
            )
            ext_link = result.scalar_one_or_none()
            
            if not ext_link:
                return web.json_response({
                    'success': False,
                    'error': 'Invalid or expired link key'
                }, status=404)
            
            # Check if already linked
            if ext_link.linked_at:
                return web.json_response({
                    'success': False,
                    'error': 'This key has already been used'
                }, status=400)
            
            # Update link status
            ext_link.linked_at = datetime.utcnow()
            ext_link.last_activity = datetime.utcnow()
            await session.commit()
            
            # Send notification to user
            if _bot_instance:
                try:
                    await _bot_instance.send_message(
                        ext_link.user_id,
                        "✅ <b>Расширение успешно привязано!</b>\n\n"
                        "Теперь вы будете получать уведомления о бронированиях "
                        "и перераспределениях прямо в Telegram."
                    )
                except Exception as e:
                    logger.error(f"Failed to send link notification: {e}")
            
            logger.info(f"Extension linked for user {ext_link.user_id}")
            
            return web.json_response({
                'success': True,
                'userId': ext_link.user_id,
                'botToken': 'linked'  # Don't expose actual bot token
            })
            
    except Exception as e:
        logger.error(f"Error linking extension: {e}")
        return web.json_response({
            'success': False,
            'error': 'Internal server error'
        }, status=500)


async def send_notification(request: web.Request) -> web.Response:
    """
    Receive notification from extension and send to user.
    
    POST /api/extension/notify
    Body: {
        "userId": 123456,
        "linkKey": "EXT_...",
        "notification": {
            "title": "...",
            "message": "...",
            "data": {...}
        }
    }
    """
    try:
        data = await request.json()
        user_id = data.get('userId')
        link_key = data.get('linkKey')
        notification = data.get('notification', {})
        
        if not user_id or not link_key:
            return web.json_response({
                'success': False,
                'error': 'userId and linkKey are required'
            }, status=400)
        
        # Verify link key
        async with get_session() as session:
            result = await session.execute(
                select(ExtensionLink)
                .where(ExtensionLink.user_id == user_id)
                .where(ExtensionLink.link_key == link_key)
                .where(ExtensionLink.is_active == True)
            )
            ext_link = result.scalar_one_or_none()
            
            if not ext_link:
                return web.json_response({
                    'success': False,
                    'error': 'Invalid credentials'
                }, status=401)
            
            # Update last activity
            ext_link.last_activity = datetime.utcnow()
            await session.commit()
        
        # Send notification to user via Telegram
        if _bot_instance:
            try:
                title = notification.get('title', 'Уведомление от расширения')
                message = notification.get('message', '')
                
                # Format notification message
                text = f"🔔 <b>{title}</b>\n\n{message}"
                
                await _bot_instance.send_message(user_id, text)
                logger.info(f"Notification sent to user {user_id}: {title}")
                
            except Exception as e:
                logger.error(f"Failed to send notification to user {user_id}: {e}")
                return web.json_response({
                    'success': False,
                    'error': 'Failed to send notification'
                }, status=500)
        else:
            logger.error("Bot instance not set, cannot send notification")
            return web.json_response({
                'success': False,
                'error': 'Bot not available'
            }, status=503)
        
        return web.json_response({'success': True})
        
    except Exception as e:
        logger.error(f"Error processing notification: {e}")
        return web.json_response({
            'success': False,
            'error': 'Internal server error'
        }, status=500)


async def cors_middleware(app, handler):
    """Add CORS headers to all responses."""
    async def middleware_handler(request):
        # Handle preflight requests
        if request.method == 'OPTIONS':
            response = web.Response()
        else:
            response = await handler(request)
        
        # Add CORS headers
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'POST, GET, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        response.headers['Access-Control-Max-Age'] = '3600'
        
        return response
    
    return middleware_handler


def setup_routes(app: web.Application):
    """Setup API routes for extension."""
    # Add CORS middleware
    app.middlewares.append(cors_middleware)
    
    app.router.add_post('/api/extension/link', link_extension)
    app.router.add_post('/api/extension/notify', send_notification)
    logger.info("Extension API routes configured")

