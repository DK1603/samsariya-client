# handlers/feedback.py

from telegram import ReplyKeyboardMarkup
from telegram.ext import ConversationHandler, MessageHandler, CommandHandler, filters
from typing import List, Dict, Any
from .mongo import get_reviews_collection
import logging

WRITE_REVIEW, = range(1)

async def get_last_reviews(n: int = 5) -> List[Dict[str, Any]]:
    col = get_reviews_collection()
    cursor = col.find({}, sort=[('_id', -1)], limit=n)
    return [r async for r in cursor]

async def write_review_start(update, context):
    await update.message.reply_text(
        '✍️ Напишите ваш отзыв и отправьте его одним сообщением:'
    )
    return WRITE_REVIEW

async def save_user_review(update, context):
    try:
        user = update.effective_user
        review = {
            'user': user.full_name,
            'text': update.message.text,
        }
        col = get_reviews_collection()
        await col.insert_one(review)
        await update.message.reply_text('Спасибо за ваш отзыв! 🙏')
    except Exception as e:
        logging.error(f"Error saving review: {e}")
        await update.message.reply_text('❌ Произошла ошибка при сохранении отзыва. Попробуйте еще раз.')
    return ConversationHandler.END

async def show_reviews(update, context):
    try:
        reviews = await get_last_reviews()
        if not reviews:
            await update.message.reply_text('Пока нет отзывов.')
            return
        text = '🗣 Последние отзывы:\n\n'
        for r in reviews:
            text += f"<b>{r.get('user','')}</b>: {r.get('text','')}\n\n"
        await update.message.reply_text(text, parse_mode='HTML')
    except Exception as e:
        logging.error(f"Error showing reviews: {e}")
        await update.message.reply_text('❌ Произошла ошибка при загрузке отзывов.')

review_conv_handler = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex('^📝 Оставить отзыв$'), write_review_start)],
    states={
        WRITE_REVIEW: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_user_review)]
    },
    fallbacks=[],
    per_chat=True,
    per_user=True
)
