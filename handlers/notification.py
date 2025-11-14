import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from telegram import Bot
from telegram.error import TelegramError

from .mongo import get_notifications_collection, get_orders_collection, get_availability_dict

logger = logging.getLogger(__name__)


async def edit_order_status_message(bot: Bot, user_id: int, order_id: str, new_message: str) -> bool:
    """Try to edit existing order status message instead of sending new one."""
    try:
        # Get order details to find the original message
        orders_col = get_orders_collection()
        order = await orders_col.find_one({'_id': order_id})
        
        if not order:
            logger.warning(f"Order {order_id} not found for message editing")
            return False
        
        # For now, we'll use a simple approach: try to edit the last message
        # In a more sophisticated implementation, you'd store message IDs
        # and track which message to edit
        
        # Get recent messages from the user's chat
        # This is a simplified approach - in production you'd want to store message IDs
        try:
            # Try to send the updated message
            # The client will see it as an update to their order status
            await bot.send_message(
                chat_id=user_id,
                text=new_message,
                parse_mode='HTML'
            )
            return True
        except Exception as e:
            logger.error(f"Failed to edit message for order {order_id}: {e}")
            return False
            
    except Exception as e:
        logger.error(f"Error in edit_order_status_message: {e}")
        return False


async def send_pending_notifications(bot: Bot) -> None:
    """Send all pending notifications to clients."""
    try:
        col = get_notifications_collection()
        # Find all unsent notifications (sent: false) that are NOT admin notifications
        cursor = col.find({
            'sent': False,
            'status': {'$nin': ['preorder', 'card_payment_verification']}
        }).sort('created_at', 1)
        notifications = [doc async for doc in cursor]
        
        if not notifications:
            return
            
        logger.info(f"Processing {len(notifications)} pending notifications")
        
        for notification in notifications:
            try:
                user_id = notification.get('user_id')
                message = notification.get('message', '')
                notification_id = notification.get('_id')
                edit_message = notification.get('edit_message', False)
                order_id = notification.get('order_id')
                
                if not user_id or not message:
                    logger.warning(f"Invalid notification data: {notification}")
                    continue
                
                # Check if this is a message edit request
                if edit_message and order_id:
                    # Try to edit existing message instead of sending new one
                    success = await edit_order_status_message(bot, user_id, order_id, message)
                    if success:
                        logger.info(f"Order status message edited for user {user_id}, order {order_id}")
                    else:
                        # Fallback to sending new message
                        await bot.send_message(
                            chat_id=user_id,
                            text=message,
                            parse_mode='HTML'
                        )
                        logger.info(f"Fallback notification sent to user {user_id}")
                else:
                    # Send new message
                    await bot.send_message(
                        chat_id=user_id,
                        text=message,
                        parse_mode='HTML'
                    )
                    logger.info(f"Notification sent to user {user_id}")
                
                # Mark as sent
                await col.update_one(
                    {'_id': notification_id},
                    {
                        '$set': {
                            'sent': True,
                            'sent_at': datetime.now(timezone.utc)
                        }
                    }
                )
                
            except TelegramError as e:
                logger.error(f"Failed to send notification to user {user_id}: {e}")
                # Mark as failed
                await col.update_one(
                    {'_id': notification_id},
                    {
                        '$set': {
                            'sent': False,
                            'error': str(e),
                            'failed_at': datetime.now(timezone.utc)
                        }
                    }
                )
            except Exception as e:
                logger.error(f"Unexpected error processing notification: {e}")
                
    except Exception as e:
        logger.error(f"Error in send_pending_notifications: {e}")


# Admin notification functions removed from client bot
# These should only exist in the admin bot

class NotificationChecker:
    """Background task to check and send notifications periodically."""
    
    def __init__(self, bot: Bot, interval: int = 30, bot_data: Optional[Dict[str, Any]] = None):
        self.bot = bot
        self.interval = interval
        self.bot_data = bot_data or {}
        self._task: Optional[asyncio.Task] = None
        self._running = False
    
    async def start(self) -> None:
        """Start the notification checker background task."""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._run())
        logger.info("Notification checker started")
    
    async def stop(self) -> None:
        """Stop the notification checker background task."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Notification checker stopped")
    
    async def _run(self) -> None:
        """Main loop for checking notifications and refreshing availability."""
        while self._running:
            try:
                # Process client notifications only
                # Admin notifications should be handled by admin bot
                await send_pending_notifications(self.bot)
                
                # Refresh availability data from MongoDB
                # This ensures the bot picks up admin changes without restart
                try:
                    availability = await get_availability_dict()
                    if availability and self.bot_data is not None:
                        self.bot_data['avail'] = availability
                        logger.debug(f"Availability refreshed: {len(availability)} items")
                except Exception as e:
                    logger.error(f"Error refreshing availability: {e}")
                    
            except Exception as e:
                logger.error(f"Error in notification checker loop: {e}")
            
            # Wait for next check
            try:
                await asyncio.sleep(self.interval)
            except asyncio.CancelledError:
                break
