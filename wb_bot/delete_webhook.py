#!/usr/bin/env python3
"""
Script to delete Telegram webhook.

This script will delete any existing webhook for the bot
and allow polling mode to work correctly.
"""

import asyncio
import sys
from aiogram import Bot
from .app.config import get_settings

async def delete_webhook():
    """Delete webhook for the bot."""
    settings = get_settings()
    
    bot = Bot(token=settings.telegram.bot_token)
    
    try:
        print("Deleting webhook...")
        
        # Get current webhook info
        webhook_info = await bot.get_webhook_info()
        print(f"Current webhook: {webhook_info.url}")
        
        if webhook_info.url:
            # Delete webhook
            result = await bot.delete_webhook(drop_pending_updates=True)
            if result:
                print("✅ Webhook deleted successfully!")
                print("✅ Pending updates dropped")
            else:
                print("❌ Failed to delete webhook")
        else:
            print("ℹ️ No webhook is currently set")
            
        # Verify webhook is deleted
        webhook_info = await bot.get_webhook_info()
        print(f"Webhook after deletion: {webhook_info.url or 'None'}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    finally:
        await bot.session.close()
    
    return True

if __name__ == "__main__":
    try:
        success = asyncio.run(delete_webhook())
        if success:
            print("\n🎉 You can now run the bot in polling mode!")
            print("Run: python -m app.main")
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n❌ Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)
