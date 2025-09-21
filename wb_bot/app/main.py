"""
Main application entry point.

This module initializes and runs the Telegram bot with all necessary
components including database, Redis, monitoring service, and handlers.
"""

import asyncio
import signal
import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web, ClientSession
try:
    import redis.asyncio as aioredis
except ImportError:
    import aioredis

from .config import get_settings
from .database import init_database, close_database
from .services.monitoring import start_monitoring_service, stop_monitoring_service
from .services.browser_manager import BrowserManager
from .services.multi_booking_manager import MultiBookingManager
from .utils.logger import setup_logging, get_logger
from .bot.handlers import routers

# Initialize logger
setup_logging()
logger = get_logger(__name__)

# Глобальные переменные для доступа к менеджерам
app_instance = None

def get_browser_manager() -> BrowserManager:
    """Возвращает экземпляр BrowserManager."""
    if app_instance is None:
        raise RuntimeError("Приложение не инициализировано")
    return app_instance.browser_manager

def get_multi_booking_manager() -> MultiBookingManager:
    """Возвращает экземпляр MultiBookingManager."""
    if app_instance is None:
        raise RuntimeError("Приложение не инициализировано")
    return app_instance.multi_booking_manager


class BotApplication:
    """
    Main bot application class.
    
    Manages the complete lifecycle of the bot including:
    - Database initialization
    - Redis connection
    - Monitoring service
    - Bot and dispatcher setup
    - Graceful shutdown
    """
    
    def __init__(self):
        """Initialize bot application."""
        self.settings = get_settings()
        
        # Создаем синглтон менеджеры для мультибронирования
        self.browser_manager = BrowserManager()
        self.multi_booking_manager = MultiBookingManager(self.browser_manager)
        self.bot: Bot = None
        self.dp: Dispatcher = None
        self.redis: aioredis.Redis = None
        self.monitoring_task: asyncio.Task = None
        self.is_running = False
    
    async def initialize(self) -> None:
        """Initialize all application components."""
        logger.info("Initializing bot application...")
        
        try:
            # Initialize database
            logger.info("Initializing database...")
            await init_database()
            
            # Using PostgreSQL database only (no Redis)
            self.redis = None
            
            # Initialize bot
            logger.info("Initializing bot...")
            self.bot = Bot(
                token=self.settings.telegram.bot_token,
                default=DefaultBotProperties(
                    parse_mode=ParseMode.HTML,
                    link_preview_is_disabled=True
                )
            )
            
            # Initialize dispatcher with appropriate storage
            if self.redis:
                from aiogram.fsm.storage.redis import RedisStorage
                storage = RedisStorage(self.redis)
                logger.info("Using Redis storage for FSM")
            else:
                storage = MemoryStorage()
                logger.info("Using Memory storage for FSM")
            
            self.dp = Dispatcher(storage=storage)
            
            # Register handlers
            logger.info("Registering handlers...")
            for router in routers:
                self.dp.include_router(router)
                logger.info(f"Registered router: {router}")
            
            logger.info(f"Total routers registered: {len(routers)}")
            
            # Set up middlewares
            await self._setup_middlewares()
            
            logger.info("Bot application initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize application: {e}")
            await self.cleanup()
            raise
    
    async def _setup_middlewares(self) -> None:
        """Set up bot middlewares."""
        # Add logging middleware
        @self.dp.message.outer_middleware()
        async def logging_middleware(handler, event, data):
            user_id = event.from_user.id if event.from_user else None
            logger.info(f"Message from user {user_id}: {event.text[:100] if event.text else 'No text'}")
            return await handler(event, data)
        
        @self.dp.callback_query.outer_middleware()
        async def callback_logging_middleware(handler, event, data):
            user_id = event.from_user.id if event.from_user else None
            logger.info(f"Callback from user {user_id}: {event.data}")
            return await handler(event, data)
        
        # Add error handling middleware
        @self.dp.error.middleware()
        async def error_middleware(handler, event, data):
            try:
                return await handler(event, data)
            except Exception as e:
                logger.error(f"Error handling update: {e}", exc_info=True)
                # Don't re-raise to prevent bot from stopping
                return None
    
    async def start_polling(self) -> None:
        """Start bot in polling mode."""
        if self.is_running:
            logger.warning("Bot is already running")
            return
        
        self.is_running = True
        logger.info("Starting bot in polling mode...")
        
        try:
            # Delete any existing webhook before starting polling
            logger.info("Checking for existing webhook...")
            webhook_info = await self.bot.get_webhook_info()
            if webhook_info.url:
                logger.info(f"Found existing webhook: {webhook_info.url}")
                logger.info("Deleting webhook to enable polling...")
                await self.bot.delete_webhook(drop_pending_updates=True)
                logger.info("Webhook deleted successfully, pending updates dropped")
            else:
                logger.info("No existing webhook found")
            
            # Start monitoring service in background
            logger.info("Starting monitoring service...")
            self.monitoring_task = asyncio.create_task(start_monitoring_service())
            
            # Start polling
            await self.dp.start_polling(
                self.bot,
                allowed_updates=self.dp.resolve_used_update_types()
            )
            
        except Exception as e:
            logger.error(f"Error during polling: {e}")
            raise
        finally:
            self.is_running = False
    
    async def start_webhook(self) -> None:
        """Start bot in webhook mode."""
        if not self.settings.telegram.webhook_url:
            raise ValueError("Webhook URL not configured")
        
        if self.is_running:
            logger.warning("Bot is already running")
            return
        
        self.is_running = True
        logger.info("Starting bot in webhook mode...")
        
        try:
            # Start monitoring service in background
            logger.info("Starting monitoring service...")
            self.monitoring_task = asyncio.create_task(start_monitoring_service())
            
            # Set webhook
            webhook_url = f"{self.settings.telegram.webhook_url}{self.settings.telegram.webhook_path}"
            await self.bot.set_webhook(
                url=webhook_url,
                secret_token=self.settings.telegram.webhook_secret,
                max_connections=self.settings.telegram.max_connections
            )
            
            # Create web application
            app = web.Application()
            
            # Setup webhook handler
            webhook_handler = SimpleRequestHandler(
                dispatcher=self.dp,
                bot=self.bot,
                secret_token=self.settings.telegram.webhook_secret
            )
            webhook_handler.register(app, path=self.settings.telegram.webhook_path)
            
            # Add health check endpoint
            async def health_check(request):
                return web.json_response({"status": "healthy", "service": "wb-bot"})
            
            app.router.add_get("/health", health_check)
            
            # Setup and start web server
            setup_application(app, self.dp, bot=self.bot)
            
            runner = web.AppRunner(app)
            await runner.setup()
            
            site = web.TCPSite(runner, "0.0.0.0", 8080)
            await site.start()
            
            logger.info(f"Webhook started at {webhook_url}")
            
            # Keep running
            while self.is_running:
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"Error during webhook: {e}")
            raise
        finally:
            self.is_running = False
    
    async def stop(self) -> None:
        """Stop bot gracefully."""
        if not self.is_running:
            return
        
        logger.info("Stopping bot...")
        self.is_running = False
        
        # Stop monitoring service
        if self.monitoring_task and not self.monitoring_task.done():
            logger.info("Stopping monitoring service...")
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
            
            await stop_monitoring_service()
        
        # Close bot session
        if self.bot:
            await self.bot.session.close()
        
        logger.info("Bot stopped")
    
    async def cleanup(self) -> None:
        """Cleanup all resources."""
        logger.info("Cleaning up resources...")
        
        await self.stop()
        
        # Close Redis connection
        if self.redis:
            await self.redis.close()
        
        # Close database connections
        await close_database()
        
        logger.info("Cleanup completed")


# Global application instance
app = BotApplication()
app_instance = app  # Устанавливаем глобальную ссылку


def setup_signal_handlers() -> None:
    """Set up signal handlers for graceful shutdown."""
    
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, initiating shutdown...")
        # Don't use asyncio.create_task in signal handler
        # The main loop will handle shutdown
        app.is_running = False
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


async def main() -> None:
    """Main application entry point."""
    try:
        # Setup signal handlers
        setup_signal_handlers()
        
        # Initialize application
        await app.initialize()
        
        # Start bot based on configuration
        if app.settings.telegram.webhook_url:
            logger.info("Starting in webhook mode")
            await app.start_webhook()
        else:
            logger.info("Starting in polling mode")
            await app.start_polling()
            
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Application error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        await app.cleanup()


if __name__ == "__main__":
    # Check Python version
    if sys.version_info < (3, 11):
        print("Python 3.11+ is required")
        sys.exit(1)
    
    # Run application
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutdown completed")
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)
