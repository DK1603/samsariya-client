# bot.py

import logging
import json
from datetime import datetime
from telegram import ReplyKeyboardMarkup, BotCommand
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    JobQueue,
    filters,
)
from handlers.common import (
    init_bot_data,
    help_command,
    set_language,
    main_menu,
    handle_language_choice,
    TEXTS,
)
from handlers.order import (
    order_conv_handler,
    remind_unfinished,
    order_start,
    cart_command,
)
from handlers.feedback import (
    review_conv_handler,
    show_reviews,
)
from config import BOT_TOKEN, WORK_START_HOUR, WORK_END_HOUR, ADMIN_ID
from handlers.mongo import initialize_database, close_client
from handlers.notification import NotificationChecker
from handlers.catalog import SAMSA_KEYS, PACKAGING_KEYS
import os

logging.basicConfig(level=logging.INFO)


async def preload_images(bot, bot_data):
    """Pre-upload all samsa and packaging images to Telegram and cache their file_ids"""
    logging.info("🖼️ Starting image preload...")
    photo_cache = {}
    packaging_cache = {}
    
    # Send to admin to get file_ids
    try:
        # Preload samsa images
        for key in SAMSA_KEYS:
            photo_path = f'data/img/{key}.jpg'
            if os.path.exists(photo_path):
                try:
                    # Check file size
                    file_size = os.path.getsize(photo_path)
                    if file_size > 5 * 1024 * 1024:  # 5MB limit
                        logging.warning(f"⚠️ Photo {key} is too large ({file_size} bytes), skipping")
                        continue
                    
                    # Upload photo to Telegram by sending to admin
                    with open(photo_path, 'rb') as photo:
                        # Send to admin to get file_id
                        message = await bot.send_photo(
                            chat_id=ADMIN_ID,
                            photo=photo,
                            caption=f"🖼️ Preloading samsa: {key}"
                        )
                        
                        if message.photo:
                            file_id = message.photo[-1].file_id
                            photo_cache[key] = file_id
                            logging.info(f"✅ Cached samsa {key}: {file_id[:20]}...")
                            
                            # Delete the message after a short delay
                            try:
                                await message.delete()
                            except:
                                pass
                except Exception as e:
                    logging.error(f"❌ Error preloading samsa {key}: {e}")
            else:
                logging.warning(f"⚠️ Photo not found: {photo_path}")
        
        # Preload packaging menu image (only пакет image)
        packaging_photo_path = 'data/img/packaging_пакет.jpg'
        if os.path.exists(packaging_photo_path):
            try:
                # Check file size
                file_size = os.path.getsize(packaging_photo_path)
                if file_size < 5 * 1024 * 1024:  # 5MB limit
                    # Upload photo to Telegram by sending to admin
                    with open(packaging_photo_path, 'rb') as photo:
                        # Send to admin to get file_id
                        message = await bot.send_photo(
                            chat_id=ADMIN_ID,
                            photo=photo,
                            caption=f"🖼️ Preloading packaging menu"
                        )
                        
                        if message.photo:
                            file_id = message.photo[-1].file_id
                            packaging_cache['menu'] = file_id
                            logging.info(f"✅ Cached packaging menu: {file_id[:20]}...")
                            
                            # Delete the message after a short delay
                            try:
                                await message.delete()
                            except:
                                pass
                else:
                    logging.warning(f"⚠️ Packaging photo is too large ({file_size} bytes), skipping")
            except Exception as e:
                logging.error(f"❌ Error preloading packaging menu: {e}")
        else:
            logging.warning(f"⚠️ Packaging photo not found: {packaging_photo_path}")
        
        bot_data['photo_cache'] = photo_cache
        bot_data['packaging_file_ids'] = packaging_cache
        logging.info(f"✅ Image preload complete! Cached {len(photo_cache)} samsa images and {len(packaging_cache)} packaging images")
    except Exception as e:
        logging.error(f"❌ Image preload failed: {e}")
        bot_data['photo_cache'] = {}
        bot_data['packaging_file_ids'] = {}
    
    return photo_cache


async def start(update, context):
    try:
        # Temporarily disabled working hours restriction for 24/7 operation
        # now = datetime.now().hour
        # if not (WORK_START_HOUR <= now < WORK_END_HOUR):
        #     return await update.message.reply_text(
        #         context.bot_data['texts']['off_hours_preorder'],
        #         reply_markup=context.bot_data['keyb']['main']
        #     )
        kb = ReplyKeyboardMarkup([['ru', 'uz']], one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text('Выберите язык / Tilni tanlang', reply_markup=kb)
    except Exception as e:
        logging.error(f"Error in start command: {e}")
        await update.message.reply_text('Произошла ошибка. Попробуйте еще раз.')

# About Us
async def about_handler(update, context):
    try:
        await context.bot.send_message(
            update.effective_chat.id,
            context.bot_data['texts']['about'],
            reply_markup=context.bot_data['keyb']['main']
        )
    except Exception as e:
        logging.error(f"Error in about_handler: {e}")

# Promo
async def promo_handler(update, context):
    try:
        await context.bot.send_message(
            update.effective_chat.id,
            context.bot_data['texts']['promo'],
            reply_markup=context.bot_data['keyb']['main']
        )
    except Exception as e:
        logging.error(f"Error in promo_handler: {e}")

# Working hours
async def hours_handler(update, context):
    try:
        await context.bot.send_message(
            update.effective_chat.id,
            context.bot_data['texts']['working_hours'],
            reply_markup=context.bot_data['keyb']['main']
        )
    except Exception as e:
        logging.error(f"Error in hours_handler: {e}")



async def contact_handler(update, context):
    try:
        from config import (
            BUSINESS_PHONE_MAIN, BUSINESS_PHONE_EXTRA, BUSINESS_TELEGRAM, 
            BUSINESS_HOURS, BUSINESS_NAME, BUSINESS_ADDRESS, BUSINESS_LANDMARK,
            BUSINESS_LATITUDE, BUSINESS_LONGITUDE, DELIVERY_AREA
        )
        
        contact_info = (
            "📞 <b>Наши контакты:</b>\n\n"
            f"📱 <b>Основной номер:</b> {BUSINESS_PHONE_MAIN}\n"
            f"📱 <b>Дополнительный:</b> {BUSINESS_PHONE_EXTRA}\n\n"
            f"💬 <b>Telegram:</b> {BUSINESS_TELEGRAM}\n\n"
            f"⏰ <b>Время работы:</b> {BUSINESS_HOURS}\n\n"
            f"🚚 <b>Доставка:</b> {DELIVERY_AREA}\n\n"
            "📍 <b>Адрес для самовывоза:</b>\n"
            f"🏪 {BUSINESS_NAME}\n"
            f"📍 {BUSINESS_ADDRESS}\n"
            f"🏟️ {BUSINESS_LANDMARK}\n\n"
            "💡 <b>Как добраться:</b>\n"
            "• Нажмите на локацию для навигации\n"
            "• Чтобы было удобнее - вот наша локация на карте:"
        )
        
        await context.bot.send_message(
            update.effective_chat.id,
            contact_info,
            reply_markup=context.bot_data['keyb']['main'],
            parse_mode='HTML'
        )
        
        # Send location
        await context.bot.send_location(
            chat_id=update.effective_chat.id,
            latitude=BUSINESS_LATITUDE,
            longitude=BUSINESS_LONGITUDE
        )
        
    except Exception as e:
        logging.error(f"Error in contact_handler: {e}")

def main():
    # 1) init texts, keyboards, availability (after DB init)
    async def _startup(application):
        try:
            await initialize_database()
            print("✅ MongoDB initialized successfully")
        except Exception as e:
            print(f"⚠️ MongoDB initialization failed: {e}")
            print("🔄 Bot will run in fallback mode with limited functionality")
            # Set a flag to indicate fallback mode
            application.bot_data['mongodb_available'] = False
        else:
            application.bot_data['mongodb_available'] = True
            
        await init_bot_data(application)
        
        # Set bot commands (blue menu) - only essential commands
        try:
            commands = [
                BotCommand("start", "🏠 Главное меню"),
                BotCommand("order", "🛒 Сделать заказ"),
                BotCommand("cart", "🛒 Посмотреть корзину"),
            ]
            await application.bot.set_my_commands(commands)
            print("✅ Bot commands set successfully")
        except Exception as e:
            print(f"⚠️ Failed to set bot commands: {e}")
        
        # Preload images for instant loading
        try:
            await preload_images(application.bot, application.bot_data)
        except Exception as e:
            print(f"⚠️ Image preload failed: {e}")
            print("🔄 Images will be loaded on-demand")
            application.bot_data['photo_cache'] = {}
        
        # Start notification checker only if MongoDB is available
        if application.bot_data.get('mongodb_available', False):
            try:
                notification_checker = NotificationChecker(application.bot, interval=30)
                await notification_checker.start()
                # Store reference for cleanup
                application.notification_checker = notification_checker
                print("✅ Notification checker started")
            except Exception as e:
                print(f"⚠️ Notification checker failed to start: {e}")
        else:
            print("⚠️ Notification checker disabled - MongoDB not available")

    async def _shutdown(application):
        # Stop notification checker
        if hasattr(application, 'notification_checker'):
            await application.notification_checker.stop()
        
        # Close MongoDB client
        close_client()
        print("✅ MongoDB client closed")

    app = ApplicationBuilder().token(BOT_TOKEN).post_init(_startup).post_shutdown(_shutdown).build()

    import logging
    logging.info(f"Admin ID loaded as: {ADMIN_ID} (type: {type(ADMIN_ID)})") # tg id debug

    tr = TEXTS['ru']                          # russian labels
    uz = TEXTS['uz']                          # uzbek labels

    # 2) register conversation handler first (group=0)
    app.add_handler(order_conv_handler, group=0)
    app.add_handler(review_conv_handler, group=0)

    # 3) wire buttons → handlers (group=1)
    # removed due to duplicate commands

    app.add_handler(MessageHandler(
        filters.Regex(f'^({tr["btn_reviews"]}|{uz["btn_reviews"]})$'),
        show_reviews
    ), group=1)

    # About Us
    app.add_handler(MessageHandler(
        filters.Regex(f'^({tr["btn_about"]}|{uz["btn_about"]})$'),
        about_handler
    ), group=1)

    # Promo
    app.add_handler(MessageHandler(
        filters.Regex(f'^({tr["btn_promo"]}|{uz["btn_promo"]})$'),
        promo_handler
    ), group=1)

    # Working hours
    app.add_handler(MessageHandler(
        filters.Regex(f'^({tr["btn_hours"]}|{uz["btn_hours"]})$'),
        hours_handler
    ), group=1)

    # Language switch
    app.add_handler(MessageHandler(
        filters.Regex(f'^({tr["btn_language"]}|{uz["btn_language"]})$'),
        set_language
    ), group=1)
    app.add_handler(MessageHandler(
        filters.Regex('^(ru|uz)$'),
        handle_language_choice
    ), group=1)

    # Help
    app.add_handler(MessageHandler(
        filters.Regex(f'^({tr["btn_help"]}|{uz["btn_help"]})$'),
        help_command
    ), group=1)
    
    # Contact handler
    app.add_handler(MessageHandler(
        filters.Regex('^📞 Контакты$'),
        contact_handler
    ), group=1)
    app.add_handler(MessageHandler(
        filters.Regex('^🛒 Корзина$'),
        cart_command
    ), group=1)

    # Keep old slash commands if you like
    app.add_handler(CommandHandler('start', start), group=1)
    app.add_handler(CommandHandler('cart', cart_command), group=1)

    # Feedback conversation
    # app.add_handler(feedback_handler, group=1) # This line is removed as per the edit hint.

    # Reminder job
    jq: JobQueue = app.job_queue
    if jq:
        jq.run_repeating(remind_unfinished, interval=7*24*3600, first=7*24*3600)
        print("✅ Reminder job scheduled")
    else:
        print("⚠️ JobQueue not available, reminder job disabled")

    app.run_polling()

if __name__ == '__main__':
    main()
