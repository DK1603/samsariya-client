# handlers/order.py

import logging
import json
import os
from datetime import datetime, timezone
from telegram import (
    ReplyKeyboardMarkup,
    ForceReply,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ConversationHandler,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)
from config import (
    WORK_START_HOUR,
    WORK_END_HOUR
)
from handlers.common import main_menu, TEXTS, get_text, get_display_name, get_short_name
from .catalog import PRICES, DISPLAY_NAMES, SHORT_NAMES, SAMSA_KEYS, PACKAGING_KEYS
from .mongo import get_orders_collection, get_temp_carts_collection

# Conversation states
ITEM_SELECT, ITEM_EDIT, PACKAGING_SELECT, NAME, PHONE, ADDRESS, DELIVERY, TIME_CHOICE, PAYMENT, VERIFY_PAYMENT, CONFIRM = range(11)

# prices/names imported from catalog

# Orders are stored in MongoDB now


async def remind_unfinished(context):
    # Placeholder for sending reminders about unfinished orders
    pass


async def order_start(update, context):
    try:
        # Temporarily disabled working hours restriction for 24/7 operation
        # now_hour = datetime.now().hour
        # target = update.message or (update.callback_query.message if update.callback_query else None)
        # if not (WORK_START_HOUR <= now_hour < WORK_END_HOUR):
        #     if target:
        #         await target.reply_text(
        #             context.bot_data['texts']['off_hours_preorder'],
        #             reply_markup=context.bot_data['keyb']['main']
        #         )
        #     return
        
        target = update.message or (update.callback_query.message if update.callback_query else None)
        user_id = update.effective_user.id
        
        # Check for existing temp cart
        try:
            temp_cart = await load_temp_cart(user_id)
        except Exception as e:
            logging.error(f"Error loading temp cart in order_start: {e}")
            temp_cart = None
    
        if temp_cart and has_meaningful_cart(temp_cart.get('items', {})):
            # Show choice: continue with previous cart or start fresh
            items = temp_cart.get('items', {})
            samsa_items = {k: v for k, v in items.items() if k in SAMSA_KEYS and v > 0}
            packaging_items = {k: v for k, v in items.items() if k in PACKAGING_KEYS and v > 0}
            
            # Build cart summary with fallback text
            try:
                summary = f"🛒 <b>{get_text(context, 'cart_saved')}</b>\n\n"
                summary += f"<b>🥟 {get_text(context, 'samsa_section')}</b>\n"
                for key, qty in samsa_items.items():
                    summary += f"• {get_short_name(context, key)} — {qty} шт\n"
                
                if packaging_items:
                    summary += f"\n<b>📦 {get_text(context, 'packaging_section')}</b>\n"
                    for key, qty in packaging_items.items():
                        summary += f"• {get_short_name(context, key)} — {qty} шт\n"
                
                total = temp_cart.get('total', 0)
                summary += f"\n💰 <b>{get_text(context, 'total_section')}</b> {total:,} сум\n\n"
                summary += get_text(context, 'what_to_do')
                
                # Show choice buttons
                choice_kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton(f'✅ {get_text(context, "continue_cart")}', callback_data='continue_cart')],
                    [InlineKeyboardButton(f'🆕 {get_text(context, "new_order")}', callback_data='new_cart')]
                ])
            except Exception as text_error:
                logging.error(f"Error building cart summary: {text_error}")
                # Fallback to simple text
                summary = "🛒 <b>Сохраненная корзина</b>\n\n"
                for key, qty in samsa_items.items():
                    summary += f"• {key} — {qty} шт\n"
                if packaging_items:
                    summary += "\n📦 Упаковка:\n"
                    for key, qty in packaging_items.items():
                        summary += f"• {key} — {qty} шт\n"
                total = temp_cart.get('total', 0)
                summary += f"\n💰 Итого: {total:,} сум\n\nЧто хотите сделать?"
                
                choice_kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton('✅ Продолжить заказ', callback_data='continue_cart')],
                    [InlineKeyboardButton('🆕 Новый заказ', callback_data='new_cart')]
                ])
            
            await target.reply_text(summary, reply_markup=choice_kb, parse_mode='HTML')
            return ITEM_SELECT  # Wait for user choice
        else:
            # Start fresh - no saved cart
            context.user_data.clear()
        
        # Debug logging
        logging.info(f"Order start triggered by: {update.message.text if update.message else 'callback'}")
        logging.info(f"Bot data keys: {list(context.bot_data.keys())}")
        logging.info(f"Availability data: {context.bot_data.get('avail', 'NOT_FOUND')}")
        logging.info(f"Conversation handler registered: {hasattr(context, 'conversation_handler')}")
        logging.info(f"Application handlers count: {len(context.application.handlers) if hasattr(context, 'application') else 'No application'}")
        
    # Show menu of samsa types as inline buttons
        # Check if availability data is loaded
        if 'avail' not in context.bot_data:
            await target.reply_text(
                "❌ Меню временно недоступно. Попробуйте позже.",
                reply_markup=context.bot_data.get('keyb', {}).get('main')
            )
            return ConversationHandler.END
        
        # Create menu buttons - one per row for easy clicking
        available_items = [
            [InlineKeyboardButton(f"{get_short_name(context, k)} - {PRICES[k]:,} сум", callback_data=f'samsa:{k}')]
            for k in SAMSA_KEYS if context.bot_data['avail'].get(k, False)
        ]
        
        if not available_items:
            await target.reply_text(
                f"❌ {get_text(context, 'samsa_unavailable')}",
                reply_markup=context.bot_data.get('keyb', {}).get('main')
            )
            return ConversationHandler.END
        
        # Add "Done" button if there are items in cart
        items = context.user_data.get('items', {})
        samsa_items = {k: v for k, v in items.items() if k in SAMSA_KEYS and v > 0}
        if samsa_items:
            available_items.append([InlineKeyboardButton('✅ Готово', callback_data='done_menu')])
        
        menu_kb = InlineKeyboardMarkup(available_items)
        
        # Create a temporary keyboard with "Finish Order" button during ordering
        from telegram import ReplyKeyboardMarkup, KeyboardButton
        ordering_keyboard = ReplyKeyboardMarkup(
            [[KeyboardButton(f'✅ {get_text(context, "finish_order")}'), KeyboardButton(f'🛒 {get_text(context, "cart_button")}'), KeyboardButton(f'❌ {get_text(context, "cancel_order_button")}')]],
            resize_keyboard=True
        )
        
        if target:
            await target.reply_text(f'🥟 {get_text(context, "choose_samsa")}', reply_markup=menu_kb)
            # Send keyboard as a separate message
            await target.reply_text(
                f'💡 <b>{get_text(context, "hint_finish")}</b>',
                reply_markup=ordering_keyboard,
                parse_mode='HTML'
            )
            return ITEM_SELECT
        else:
            await update.callback_query.edit_message_text(f'🥟 {get_text(context, "choose_samsa")}', reply_markup=menu_kb)
            return ITEM_SELECT
            
    except Exception as e:
        logging.error(f"Error in order_start: {e}")
        logging.error(f"Error type: {type(e)}")
        logging.error(f"Error details: {str(e)}")
        import traceback
        logging.error(f"Traceback: {traceback.format_exc()}")
        
        target = update.message or (update.callback_query.message if update.callback_query else None)
        if target:
            await target.reply_text(
                "❌ Произошла ошибка при запуске заказа. Попробуйте позже.",
                reply_markup=context.bot_data.get('keyb', {}).get('main')
            )
        return ConversationHandler.END




# Handler for selecting a samsa type from the menu
async def select_samsa(update, context):
    q = update.callback_query
    await q.answer()
    
    # Debug logging
    logging.info(f"select_samsa called with data: {q.data}")
    logging.info(f"Current conversation state: {context.user_data.get('conversation_state', 'None')}")
    logging.info(f"User data keys: {list(context.user_data.keys())}")
    
    try:
        key = q.data.split(':', 1)[1]
        context.user_data['current_item'] = key
        items = context.user_data.setdefault('items', {})
        qty = items.get(key, 0)
        
        # Calculate total for all items in cart
        cart_total = sum(PRICES.get(k, 0) * v for k, v in items.items() if k in SAMSA_KEYS and v > 0)
        
        caption = (
            f"🥟 <b>{get_display_name(context, key)}</b>\n\n"
            f"💰 {get_text(context, 'price_label')} {PRICES[key]:,} сум\n"
            f"📦 {get_text(context, 'in_cart')} {qty} шт\n"
            f"💵 <b>{get_text(context, 'total_cost')} {cart_total:,} сум</b>\n\n"
            f"💡 <i>Введите количество или прибавляйте кнопками</i>"
        )
    except Exception as e:
        logging.error(f"Error in select_samsa: {e}")
        await q.message.reply_text(f"❌ {get_text(context, 'error_occurred')}")
        return ITEM_SELECT
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton('➖', callback_data=f'dec:{key}'),
            InlineKeyboardButton(f'{qty}', callback_data='noop'),
            InlineKeyboardButton('➕', callback_data=f'inc:{key}')
        ],
        [InlineKeyboardButton(f'✅ {get_text(context, "finish_with_samsa")}', callback_data=f'finish_item:{key}')],
        [InlineKeyboardButton(f'⬅️ {get_text(context, "back_to_menu")}', callback_data='back_to_menu')]
    ])
    
    # Try to send with photo using cached file_id or upload new
    try:
        # Initialize photo cache if not exists
        if 'photo_cache' not in context.bot_data:
            context.bot_data['photo_cache'] = {}
        
        photo_cache = context.bot_data['photo_cache']
        
        # Check if we have cached file_id
        if key in photo_cache:
            try:
                await q.message.reply_photo(
                    photo=photo_cache[key],
                    caption=caption,
                    reply_markup=keyboard,
                    parse_mode='HTML'
                )
                return ITEM_EDIT

            except Exception as cache_error:
                logging.warning(f"Cached photo failed for {key}, will re-upload: {cache_error}")
                # Remove invalid cache entry
                del photo_cache[key]
        
        # Upload photo and cache file_id
        photo_path = f'data/img/{key}.jpg'
        if os.path.exists(photo_path):
            # Check file size to avoid timeouts
            file_size = os.path.getsize(photo_path)
            if file_size > 5 * 1024 * 1024:  # 5MB limit
                logging.warning(f"Photo {key} is too large ({file_size} bytes), using text fallback")
                await q.message.reply_text(caption, reply_markup=keyboard, parse_mode='HTML')
            else:
                with open(photo_path, 'rb') as photo:
                    sent_msg = await q.message.reply_photo(
                        photo=photo,
                        caption=caption,
                        reply_markup=keyboard,
                        parse_mode='HTML'
                    )
                    # Cache the file_id for future use
                    if sent_msg.photo:
                        photo_cache[key] = sent_msg.photo[-1].file_id
                        logging.info(f"Cached photo file_id for {key}")
        else:
            # Fallback to text-only
            await q.message.reply_text(caption, reply_markup=keyboard, parse_mode='HTML')
    except Exception as e:
        logging.error(f"Error sending photo for {key}: {e}")
        # Fallback to text-only
        await q.message.reply_text(caption, reply_markup=keyboard, parse_mode='HTML')
    
    return ITEM_EDIT


# Handler for continuing with saved cart
async def continue_with_cart(update, context):
    """Continue ordering with saved cart"""
    q = update.callback_query
    await q.answer()
    
    user_id = update.effective_user.id
    temp_cart = await load_temp_cart(user_id)
    
    if temp_cart:
        # Restore cart to context
        context.user_data.update(temp_cart)
        
        # Show cart summary for editing
        await show_cart_summary(update, context)
        return PACKAGING_SELECT
    else:
        await q.edit_message_text(
            "❌ Корзина не найдена. Начните новый заказ.",
            parse_mode='HTML'
        )
        return ConversationHandler.END


# Handler for starting new cart
async def start_new_cart(update, context):
    """Start fresh order, clearing saved cart"""
    q = update.callback_query
    await q.answer()
    
    user_id = update.effective_user.id
    
    # Clear saved cart
    await delete_temp_cart(user_id)
    context.user_data.clear()
    
    # Show samsa menu
    try:
        # Check if availability data is loaded
        if 'avail' not in context.bot_data:
            await q.edit_message_text(
                "❌ Меню временно недоступно. Попробуйте позже.",
                parse_mode='HTML'
            )
            return ConversationHandler.END
        
        # Create menu buttons
        available_items = [
            [InlineKeyboardButton(f"{SHORT_NAMES.get(k, k)} - {PRICES[k]:,} сум", callback_data=f'samsa:{k}')]
            for k in SAMSA_KEYS if context.bot_data['avail'].get(k, False)
        ]
        
        if not available_items:
            await q.edit_message_text(
                "❌ В данный момент самса недоступна. Попробуйте позже.",
                parse_mode='HTML'
            )
            return ConversationHandler.END
        
        menu_kb = InlineKeyboardMarkup(available_items)
        
        # Create ordering keyboard
        from telegram import ReplyKeyboardMarkup, KeyboardButton
        ordering_keyboard = ReplyKeyboardMarkup(
            [[KeyboardButton('✅ Завершить заказ'), KeyboardButton('🛒 Корзина'), KeyboardButton('❌ Отменить заказ')]],
            resize_keyboard=True
        )
        
        await q.edit_message_text('🥟 Выберите самсу:', reply_markup=menu_kb)
        
        # Send keyboard hint
        await update.effective_chat.send_message(
            '💡 <b>Подсказка:</b> После выбора самсы нажмите "✅ Завершить заказ"',
            reply_markup=ordering_keyboard,
            parse_mode='HTML'
        )
        
        return ITEM_SELECT
        
    except Exception as e:
        logging.error(f"Error in start_new_cart: {e}")
        await q.message.reply_text(
            "❌ Произошла ошибка. Попробуйте позже.",
            parse_mode='HTML'
        )
        return ConversationHandler.END


# Handler for + and - in item edit
async def inc_item(update, context):
    q = update.callback_query
    await q.answer()
    key = q.data.split(':', 1)[1]
    items = context.user_data.setdefault('items', {})
    items[key] = items.get(key, 0) + 1
    qty = items[key]
    
    # Calculate total for all items in cart
    cart_total = sum(PRICES.get(k, 0) * v for k, v in items.items() if k in SAMSA_KEYS and v > 0)
    
    caption = (
        f"🥟 <b>{get_display_name(context, key)}</b>\n\n"
        f"💰 {get_text(context, 'price_label')} {PRICES[key]:,} сум\n"
        f"📦 {get_text(context, 'in_cart')} {qty} шт\n"
        f"💵 <b>{get_text(context, 'total_cost')} {cart_total:,} сум</b>\n\n"
        f"💡 <i>Введите количество или прибавляйте кнопками</i>"
    )
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton('➖', callback_data=f'dec:{key}'),
            InlineKeyboardButton(f'{qty}', callback_data='noop'),
            InlineKeyboardButton('➕', callback_data=f'inc:{key}')
        ],
        [InlineKeyboardButton(f'✅ {get_text(context, "finish_with_samsa")}', callback_data=f'finish_item:{key}')],
        [InlineKeyboardButton(f'⬅️ {get_text(context, "back_to_menu")}', callback_data='back_to_menu')]
    ])
    
    try:
        await q.edit_message_caption(caption, reply_markup=keyboard, parse_mode='HTML')
    except Exception as e:
        logging.error(f"Error editing caption: {e}")
        # If edit fails, send new message
        await q.message.reply_text(caption, reply_markup=keyboard, parse_mode='HTML')
    
    return ITEM_EDIT


async def dec_item(update, context):
    q = update.callback_query
    await q.answer()
    key = q.data.split(':', 1)[1]
    items = context.user_data.setdefault('items', {})
    items[key] = max(0, items.get(key, 0) - 1)
    qty = items[key]
    
    # Calculate total for all items in cart
    cart_total = sum(PRICES.get(k, 0) * v for k, v in items.items() if k in SAMSA_KEYS and v > 0)
    
    caption = (
        f"🥟 <b>{get_display_name(context, key)}</b>\n\n"
        f"💰 {get_text(context, 'price_label')} {PRICES[key]:,} сум\n"
        f"📦 {get_text(context, 'in_cart')} {qty} шт\n"
        f"💵 <b>{get_text(context, 'total_cost')} {cart_total:,} сум</b>\n\n"
        f"💡 <i>Введите количество или прибавляйте кнопками</i>"
    )
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton('➖', callback_data=f'dec:{key}'),
            InlineKeyboardButton(f'{qty}', callback_data='noop'),
            InlineKeyboardButton('➕', callback_data=f'inc:{key}')
        ],
        [InlineKeyboardButton(f'✅ {get_text(context, "finish_with_samsa")}', callback_data=f'finish_item:{key}')],
        [InlineKeyboardButton(f'⬅️ {get_text(context, "back_to_menu")}', callback_data='back_to_menu')]
    ])
    
    try:
        await q.edit_message_caption(caption, reply_markup=keyboard, parse_mode='HTML')
    except Exception as e:
        logging.error(f"Error editing caption: {e}")
        # If edit fails, send new message
        await q.message.reply_text(caption, reply_markup=keyboard, parse_mode='HTML')
    
    return ITEM_EDIT


# Handler for finishing with current item
async def finish_item(update, context):
    q = update.callback_query
    await q.answer()
    
    try:
        key = q.data.split(':', 1)[1]
        items = context.user_data.setdefault('items', {})
        qty = items.get(key, 0)
        
        # Save current cart to temp storage
        user_id = update.effective_user.id
        total = sum(PRICES[k] * v for k, v in items.items())
        samsa_items = {k: v for k, v in items.items() if k in SAMSA_KEYS and v > 0}
        packaging_items = {k: v for k, v in items.items() if k in PACKAGING_KEYS and v > 0}
        
        cart_data = {
            'items': items,
            'total': total,
            'has_samsa': len(samsa_items) > 0,
            'has_packaging': len(packaging_items) > 0
        }
        
        await save_temp_cart(user_id, cart_data)
        
        # Delete the item photo message
        try:
            await q.message.delete()
        except Exception as e:
            logging.error(f"Error deleting message in finish_item: {e}")
        
        # Show a simple confirmation message (no buttons needed)
        if qty > 0:
            await update.effective_chat.send_message(
                f"✅ <b>{get_short_name(context, key)}</b> {get_text(context, 'add_to_cart')} ({qty} шт)",
                parse_mode='HTML'
            )
        
        return ITEM_SELECT
        
    except Exception as e:
        logging.error(f"Error in finish_item: {e}")
        await q.message.reply_text("❌ Произошла ошибка при завершении выбора.")
        return ITEM_SELECT


# Handler for back to menu
async def back_to_menu(update, context):
    q = update.callback_query
    await q.answer()
    
    # Show menu of samsa types as inline buttons - one per row for easy clicking
    available_items = [
        [InlineKeyboardButton(f"{SHORT_NAMES.get(k, k)} — {PRICES[k]:,} сум", callback_data=f'samsa:{k}')]
        for k in SAMSA_KEYS if context.bot_data['avail'].get(k, False)
    ]
    
    # Add "Done" button if there are items in cart
    items = context.user_data.get('items', {})
    samsa_items = {k: v for k, v in items.items() if k in SAMSA_KEYS and v > 0}
    if samsa_items:
        available_items.append([InlineKeyboardButton('✅ Готово', callback_data='done_menu')])
    
    menu_kb = InlineKeyboardMarkup(available_items)
    
    try:
        # Check if the message has text (not a photo message)
        if q.message.text:
            # Edit existing text message
            await q.edit_message_text('🥟 Выберите самсу:', reply_markup=menu_kb)
        else:
            # If it's a photo message, delete it and send new text message
            try:
                await q.message.delete()
            except:
                pass
            # Send new menu message
            await update.effective_chat.send_message('🥟 Выберите самсу:', reply_markup=menu_kb)
    except Exception as e:
        logging.error(f"Error editing message in back_to_menu: {e}")
        # Always fallback to new message
        try:
            await update.effective_chat.send_message('🥟 Выберите самсу:', reply_markup=menu_kb)
        except Exception as e2:
            logging.error(f"Error sending fallback menu: {e2}")
    
    return ITEM_SELECT


# Handler for done_menu (proceed to cart review)
async def finish_menu(update, context):
    q = update.callback_query
    await q.answer()
    
    # Debug logging
    logging.info(f"finish_menu called with data: {q.data}")
    
    items = context.user_data.get('items', {})
    
    # Check if cart has any samsa items
    samsa_items = {k: v for k, v in items.items() if k in SAMSA_KEYS and v > 0}
    if not samsa_items:
        await q.edit_message_text(
            f"❌ <b>{get_text(context, 'cart_empty')}</b>\n\n{get_text(context, 'add_samsa_first')}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(f"⬅️ {get_text(context, 'back_to_selection')}", callback_data="back_to_menu")]
            ]),
            parse_mode='HTML'
        )
        return ITEM_SELECT
    
    # Recalculate total
    total = sum(PRICES[k] * v for k, v in items.items())
    context.user_data['total'] = total
    
    # Show cart summary first
    lines = [f"• {get_display_name(context, k)} — {v} шт" for k, v in samsa_items.items()]
    receipt = "\n".join(lines)
    text = (
        f"🛒 <b>{get_text(context, 'cart_section')}</b>\n"
        f"{receipt}\n\n"
        f"💰 <b>{get_text(context, 'total_section')}</b> {total:,} сум"
    )
    
    # Delete or edit the current message
    try:
        await q.message.delete()
    except Exception as e:
        logging.error(f"Error deleting message: {e}")
    
    # Send cart summary
    await update.effective_chat.send_message(text, parse_mode='HTML')
    
    # Now show packaging menu with image
    return await show_packaging_menu(update, context)


# Handler for packaging selection
async def show_packaging_menu(update, context):
    # Handle both callback queries and direct calls
    if hasattr(update, 'callback_query') and update.callback_query:
        q = update.callback_query
        await q.answer()
        target = q.message
        # Delete the previous message if it exists
        try:
            await q.message.delete()
        except Exception as e:
            logging.error(f"Error deleting previous message: {e}")
    else:
        target = update.message
    
    # Create packaging menu with all options as inline buttons
    packaging_buttons = []
    for key in PACKAGING_KEYS:
        if context.bot_data['avail'].get(key, False):
            packaging_buttons.append([InlineKeyboardButton(
                f"{get_short_name(context, key)} (+{PRICES[key]:,} сум)", 
                callback_data=f'packaging:{key}'
            )])
    
    # Add back button
    packaging_buttons.append([InlineKeyboardButton(f'⬅️ {get_text(context, "back_to_cart")}', callback_data='back_to_cart')])
    
    menu_kb = InlineKeyboardMarkup(packaging_buttons)
    
    text = f"📦 <b>{get_text(context, 'choose_packaging')}</b>\n\n{get_text(context, 'packaging_required')}"
    
    # Try to send with packaging image
    try:
        # Use cached file_id for the packaging menu image
        file_id = context.bot_data.get('packaging_file_ids', {}).get('menu')
        
        if file_id:
            # Use cached image
            await update.effective_chat.send_photo(
                photo=file_id,
                caption=text,
                reply_markup=menu_kb,
        parse_mode='HTML'
    )
        else:
            # Fallback to loading from file
            photo_path = 'data/img/packaging_пакет.jpg'
            if os.path.exists(photo_path):
                file_size = os.path.getsize(photo_path)
                if file_size < 5 * 1024 * 1024:  # Less than 5MB
                    with open(photo_path, 'rb') as photo:
                        msg = await update.effective_chat.send_photo(
                            photo=photo,
                            caption=text,
                            reply_markup=menu_kb,
                            parse_mode='HTML'
                        )
                        # Cache the file_id for next time
                        if 'packaging_file_ids' not in context.bot_data:
                            context.bot_data['packaging_file_ids'] = {}
                        context.bot_data['packaging_file_ids']['menu'] = msg.photo[-1].file_id
                else:
                    # File too large, send text only
                    await update.effective_chat.send_message(text, reply_markup=menu_kb, parse_mode='HTML')
            else:
                # No photo, send text only
                await update.effective_chat.send_message(text, reply_markup=menu_kb, parse_mode='HTML')
    except Exception as e:
        logging.error(f"Error sending packaging photo: {e}")
        # Fallback to text only
        await update.effective_chat.send_message(text, reply_markup=menu_kb, parse_mode='HTML')
    
    return PACKAGING_SELECT


async def select_packaging(update, context):
    q = update.callback_query
    await q.answer()
    
    key = q.data.split(':', 1)[1]
    
    # Add to cart
    items = context.user_data.setdefault('items', {})
    items[key] = items.get(key, 0) + 1
    
    # IMPORTANT: Recalculate total to include packaging cost
    total = sum(PRICES[k] * v for k, v in items.items())
    context.user_data['total'] = total
    
    # Delete the packaging menu message (might be photo or text)
    try:
        await q.message.delete()
    except Exception as e:
        logging.error(f"Error deleting packaging message: {e}")
    
    # Show confirmation and automatically proceed to order
    await update.effective_chat.send_message(
        f"✅ {get_text(context, 'added_to_cart')} {get_short_name(context, key)}\n\n{get_text(context, 'proceeding_to_order')}",
        parse_mode='HTML'
    )
    
    # Automatically proceed to order confirmation
    return await confirm_cart(update, context)


async def back_to_cart(update, context):
    """Go back to cart summary from editing"""
    # Check if it's from callback query or direct call
    if hasattr(update, 'callback_query') and update.callback_query:
        q = update.callback_query
        await q.answer()
    
    # Recalculate total
    items = context.user_data.get('items', {})
    total = sum(PRICES[k] * v for k, v in items.items())
    context.user_data['total'] = total
    
    # Show cart summary
    await show_cart_summary(update, context)
    return PACKAGING_SELECT


async def confirm_cart(update, context):
    q = update.callback_query
    await q.answer()
    
    # Save temp cart before proceeding to contact info
    user_id = update.effective_user.id
    items = context.user_data.get('items', {})
    total = context.user_data.get('total', 0)
    
    # Check if cart has meaningful content
    samsa_items = {k: v for k, v in items.items() if k in SAMSA_KEYS and v > 0}
    packaging_items = {k: v for k, v in items.items() if k in PACKAGING_KEYS and v > 0}
    
    cart_data = {
        'items': items,
        'total': total,
        'has_samsa': len(samsa_items) > 0,
        'has_packaging': len(packaging_items) > 0
    }
    
    await save_temp_cart(user_id, cart_data)
    
    # Start with asking for customer name
    name_prompt = (
        f"👤 <b>{get_text(context, 'enter_name')}</b>\n\n"
        f"⚠️ <i>{get_text(context, 'enter_name_manually')}</i>\n\n"
        f"<i>{get_text(context, 'name_example')}</i>"
    )
    
    await q.message.reply_text(name_prompt, parse_mode='HTML', reply_markup=ForceReply(selective=True))
    return NAME


async def edit_cart(update, context):
    q = update.callback_query
    await q.answer()
    
    # Show cart items for editing
    return await edit_cart_items(update, context)


async def clear_cart(update, context):
    """Clear the cart and delete temp cart"""
    q = update.callback_query
    await q.answer()
    
    user_id = update.effective_user.id
    
    # Clear context
    context.user_data.clear()
    
    # Delete temp cart
    await delete_temp_cart(user_id)
    
    # Delete the cart message
    try:
        await q.message.delete()
    except Exception as e:
        logging.error(f"Error deleting cart message: {e}")
    
    # Send new message with main keyboard
    await update.effective_chat.send_message(
        "🗑️ <b>Корзина очищена</b>\n\n"
        "Начните новый заказ, когда будете готовы!",
        reply_markup=context.bot_data['keyb']['main'],
        parse_mode='HTML'
    )
    
    return ConversationHandler.END


async def handle_name_input(update, context):
    """Handle customer name input"""
    text = update.message.text.strip()
    
    # Block keyboard button text
    blocked_keywords = [
        '✅ Завершить заказ', '🛒 Корзина', '❌ Отменить заказ',
        '💬 Отзывы', 'ℹ️ О нас', '🔥 Акции', '⏰ Время работы',
        '🌐 Язык', '❓ Помощь', '📞 Контакты', '📝 Оставить отзыв',
        '🇷🇺 Русский', '🇺🇿 O\'zbek'
    ]
    
    if text in blocked_keywords or text.startswith('/'):
        await update.message.reply_text(
            f"⚠️ <b>{get_text(context, 'enter_name_manually')}</b>\n\n"
            f"Не используйте кнопки меню. Просто напишите своё имя.\n\n"
            f"<i>{get_text(context, 'name_example')}</i>",
            parse_mode='HTML',
            reply_markup=ForceReply(selective=True)
        )
        return NAME
    
    # Validate name (at least 2 characters)
    if len(text) < 2:
        await update.message.reply_text(
            f"⚠️ <b>{get_text(context, 'name_too_short')}</b>\n\n"
            f"{get_text(context, 'enter_full_name')}\n\n"
            f"<i>{get_text(context, 'name_example')}</i>",
            parse_mode='HTML',
            reply_markup=ForceReply(selective=True)
        )
        return NAME
    
    # Save name
    context.user_data['customer_name'] = text
    
    # Ask for phone number
    phone_prompt = (
        f"📱 <b>{get_text(context, 'enter_phone')}</b>\n\n"
        f"⚠️ <i>{get_text(context, 'enter_phone_manually')}</i>\n\n"
        f"<i>{get_text(context, 'phone_example')}</i>"
    )
    
    await update.message.reply_text(phone_prompt, parse_mode='HTML', reply_markup=ForceReply(selective=True))
    return PHONE


async def handle_phone_input(update, context):
    """Handle customer phone number input"""
    text = update.message.text.strip()
    
    # Block keyboard button text
    blocked_keywords = [
        '✅ Завершить заказ', '🛒 Корзина', '❌ Отменить заказ',
        '💬 Отзывы', 'ℹ️ О нас', '🔥 Акции', '⏰ Время работы',
        '🌐 Язык', '❓ Помощь', '📞 Контакты', '📝 Оставить отзыв',
        '🇷🇺 Русский', '🇺🇿 O\'zbek'
    ]
    
    if text in blocked_keywords or text.startswith('/'):
        await update.message.reply_text(
            f"⚠️ <b>{get_text(context, 'enter_phone_manually')}</b>\n\n"
            f"Не используйте кнопки меню. Просто напишите номер телефона.\n\n"
            f"<i>{get_text(context, 'phone_example')}</i>",
            parse_mode='HTML',
            reply_markup=ForceReply(selective=True)
        )
        return PHONE
    
    # Basic phone validation (contains digits and reasonable length)
    digits = ''.join(filter(str.isdigit, text))
    if len(digits) < 9:
        await update.message.reply_text(
            f"⚠️ <b>{get_text(context, 'phone_too_short')}</b>\n\n"
            f"{get_text(context, 'enter_full_phone')}\n\n"
            f"<i>{get_text(context, 'phone_example')}</i>",
            parse_mode='HTML',
            reply_markup=ForceReply(selective=True)
        )
        return PHONE
    
    # Save phone
    context.user_data['customer_phone'] = text
    
    # Ask for delivery address
    address_prompt = (
        f"📍 <b>{get_text(context, 'enter_address')}</b>\n\n"
        f"⚠️ <i>{get_text(context, 'enter_address_manually')}</i>\n\n"
        f"<i>{get_text(context, 'address_example')}</i>\n"
        f"или: Чиланзар, 12 квартал, дом 3"
    )
    
    await update.message.reply_text(address_prompt, parse_mode='HTML', reply_markup=ForceReply(selective=True))
    return ADDRESS


async def handle_address_input(update, context):
    """Handle customer address input"""
    text = update.message.text.strip()
    
    # Block keyboard button text
    blocked_keywords = [
        '✅ Завершить заказ', '🛒 Корзина', '❌ Отменить заказ',
        '💬 Отзывы', 'ℹ️ О нас', '🔥 Акции', '⏰ Время работы',
        '🌐 Язык', '❓ Помощь', '📞 Контакты', '📝 Оставить отзыв',
        '🇷🇺 Русский', '🇺🇿 O\'zbek'
    ]
    
    if text in blocked_keywords or text.startswith('/'):
        await update.message.reply_text(
            f"⚠️ <b>{get_text(context, 'enter_address_manually')}</b>\n\n"
            f"Не используйте кнопки меню. Просто напишите адрес.\n\n"
            f"<i>{get_text(context, 'address_example')}</i>",
            parse_mode='HTML',
            reply_markup=ForceReply(selective=True)
        )
        return ADDRESS
    
    # Validate address (at least 5 characters)
    if len(text) < 5:
        await update.message.reply_text(
            f"⚠️ <b>{get_text(context, 'address_too_short')}</b>\n\n"
            f"{get_text(context, 'enter_full_address')}\n\n"
            f"<i>{get_text(context, 'address_example')}</i>",
            parse_mode='HTML',
            reply_markup=ForceReply(selective=True)
        )
        return ADDRESS
    
    # Save address
    context.user_data['customer_address'] = text
    
    # Now ask for delivery method
    from config import DELIVERY_AREA
    delivery_info = (
        f"🚚 <b>{get_text(context, 'delivery_zone')}</b> {DELIVERY_AREA}\n\n"
        f"{get_text(context, 'choose_delivery_method_final')}"
    )
    
    kb = ReplyKeyboardMarkup([[f"🚚 {get_text(context, 'delivery_option')}", f"🏃 {get_text(context, 'pickup_option')}"]], one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(delivery_info, reply_markup=kb, parse_mode='HTML')
    return DELIVERY


async def order_contact(update, context):
    context.user_data['delivery'] = update.message.text
    
    # If self-pickup, send address and location first
    if update.message.text == "🏃 Самовывоз":
        # Send address information
        from config import BUSINESS_NAME, BUSINESS_ADDRESS, BUSINESS_LANDMARK, BUSINESS_HOURS
        address_message = (
            f"📍 <b>Вы можете забрать заказ самостоятельно, мы находимся по адресу:</b>\n\n"
            f"🏪 <b>{BUSINESS_NAME}</b>\n"
            f"📍 {BUSINESS_ADDRESS}\n"
            f"🏟️ {BUSINESS_LANDMARK}\n"
            f"⏰ Время работы: {BUSINESS_HOURS}\n\n"
            "💡 <b>Как добраться:</b>\n"
            "• Нажмите на локацию ниже для навигации\n"
            "• Или скопируйте адрес в навигатор\n"
            "• Чтобы было удобнее - вот наша локация на карте:"
        )
        
        await update.message.reply_text(address_message, parse_mode='HTML')
        
        # Send location using configuration
        from config import BUSINESS_LATITUDE, BUSINESS_LONGITUDE, BUSINESS_ADDRESS, BUSINESS_NAME
        latitude = BUSINESS_LATITUDE
        longitude = BUSINESS_LONGITUDE
        
        await update.message.reply_location(
            latitude=latitude,
            longitude=longitude
        )
        
        # Then ask for time
        await update.message.reply_text(
            "⏰ Для самовывоза необходимо указать время получения.\n\nВведите время (например, 14:30):",
            reply_markup=ForceReply()
        )
        return TIME_CHOICE
    
    # For delivery, show time options
    kb = ReplyKeyboardMarkup([["⏰ Как можно скорее", "🕒 К конкретному времени"]], one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text('Когда доставить?', reply_markup=kb)
    return TIME_CHOICE


async def order_time(update, context):
    choice = update.message.text
    if choice == '🕒 К конкретному времени':
        await update.message.reply_text('Введите время (например, 14:30):', reply_markup=ForceReply())
        return TIME_CHOICE
    context.user_data['time'] = choice
    kb = ReplyKeyboardMarkup([["💵 Наличные", "💳 Оплатить по карте"]], one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text('Выберите способ оплаты:', reply_markup=kb)
    return PAYMENT


async def order_payment(update, context):
    method = update.message.text
    context.user_data['method'] = method
    total = context.user_data.get('total', 0)

    if method == '💳 Оплатить по карте':
        # Store payment start time for 10-minute timer
        context.user_data['payment_start_time'] = datetime.now()
        
        await update.message.reply_text(
            f"💳 <b>Оплата картой</b>\n\n"
            f"💰 Сумма к оплате: <b>{total:,} сум</b>\n"
            f"🏦 Номер карты: <b>5614 6829 1638 2346</b>\n"
            f"🏛️ Банк: UzCard, OFB\n\n"
            f"⏰ <b>У вас есть 10 минут на оплату!</b>\n\n"
            f"После перевода отправьте в этот чат сумму цифрами.\n"
            f"Заказ будет подтвержден администратором после проверки оплаты.",
            parse_mode='HTML'
        )
        return VERIFY_PAYMENT

    # Cash path: skip to summary
    await show_summary_and_confirm(update, context)
    return CONFIRM


async def verify_payment(update, context):
    text = update.message.text or ''
    try:
        paid = int(text)
    except ValueError:
        await update.message.reply_text("Введите сумму цифрами (например, 10000).")
        return VERIFY_PAYMENT

    total = context.user_data.get('total', 0)
    if paid != total:
        await update.message.reply_text(f"Сумма не совпадает ({paid} ≠ {total}). Попробуйте ещё раз.")
        return VERIFY_PAYMENT

    # Check if 10 minutes have passed
    payment_start_time = context.user_data.get('payment_start_time')
    if payment_start_time:
        time_diff = datetime.now() - payment_start_time
        if time_diff.total_seconds() > 600:  # 10 minutes = 600 seconds
            await update.message.reply_text(
                "⏰ Время оплаты истекло (10 минут).\n\n"
                "Пожалуйста, начните заказ заново или выберите оплату наличными.",
                reply_markup=ReplyKeyboardMarkup([["💵 Наличные"]], one_time_keyboard=True, resize_keyboard=True)
            )
            return PAYMENT

    # Payment amount is correct and within time limit
    await update.message.reply_text(
        "✅ <b>Сумма оплаты подтверждена!</b>\n\n"
        "⏳ Ожидайте подтверждения от администратора.\n"
        "После проверки оплаты ваш заказ будет принят в обработку.",
        parse_mode='HTML'
    )
    
    # Store order as pending admin confirmation
    context.user_data['payment_verified'] = True
    context.user_data['payment_amount'] = paid
    
    # Show summary for final confirmation
    await show_summary_and_confirm(update, context)
    return CONFIRM


async def show_summary_and_confirm(update, context):
    total = context.user_data.get('total', 0)
    items = context.user_data.get('items', {})
    
    # Separate samsa and packaging items
    samsa_items = []
    packaging_items = []
    
    for key, qty in items.items():
        if qty > 0:
            if key in SAMSA_KEYS:
                samsa_items.append(f"• {get_display_name(context, key)} — {qty} шт")
            elif key in PACKAGING_KEYS:
                packaging_items.append(f"• {get_display_name(context, key)} — {qty} шт")
    
    summary = "🧾 <b>Ваш заказ:</b>\n\n"
    
    if samsa_items:
        summary += "<b>🥟 Самса:</b>\n" + "\n".join(samsa_items) + "\n\n"
    
    if packaging_items:
        summary += "<b>📦 Упаковка:</b>\n" + "\n".join(packaging_items) + "\n\n"
    
    # Get customer details
    customer_name = context.user_data.get('customer_name', '—')
    customer_phone = context.user_data.get('customer_phone', '—')
    customer_address = context.user_data.get('customer_address', '—')
    
    summary += (
        f"💰 <b>Сумма:</b> {total:,} сум\n\n"
        f"👤 <b>Имя:</b> {customer_name}\n"
        f"📱 <b>Телефон:</b> {customer_phone}\n"
        f"📍 <b>Адрес:</b> {customer_address}\n\n"
        f"🚚 <b>{context.user_data.get('delivery', '—')}</b>\n"
        f"⏰ <b>{context.user_data.get('time', '—')}</b>"
    )
    context.user_data['summary'] = summary
    kb = ReplyKeyboardMarkup([["Подтвердить", "Отменить"]], one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(summary, reply_markup=kb, parse_mode='HTML')


async def order_confirm(update, context):
    text = (update.message.text or "").strip().lower()
    if text in ['подтвердить', '✅ подтвердить']:
        try:
            uid = str(update.effective_user.id)
            
            # Determine order status based on payment method
            payment_method = context.user_data.get('method')
            if payment_method == '💳 Оплатить по карте':
                if context.user_data.get('payment_verified'):
                    order_status = 'pending_admin_confirmation'
                    status_message = '⏳ Заказ отправлен на подтверждение администратором. Ожидайте проверки оплаты.'
                else:
                    order_status = 'payment_failed'
                    status_message = '❌ Ошибка оплаты. Пожалуйста, попробуйте еще раз.'
            else:
                order_status = 'new'
                status_message = '🎉 Ваш заказ принят! С вами скоро свяжутся.'
            
            # Check if MongoDB is available
            if context.bot_data.get('mongodb_available', True):
                # Persist to MongoDB
                from datetime import datetime, timezone
                
                # Check if this is a preorder (night time order)
                current_hour = datetime.now().hour
                is_preorder = current_hour >= 22 or current_hour <= 6  # Night time: 10 PM to 6 AM
                
                order_doc = {
                    'user_id': int(uid) if uid.isdigit() else uid,
                    'items': context.user_data.get('items', {}),
                    'total': context.user_data.get('total', 0),
                    # New separate customer details fields
                    'customer_name': context.user_data.get('customer_name'),
                    'customer_phone': context.user_data.get('customer_phone'),
                    'customer_address': context.user_data.get('customer_address'),
                    # Keep old contact field for backward compatibility (deprecated)
                    'contact': context.user_data.get('contact'),
                    'delivery': context.user_data.get('delivery'),
                    'time': context.user_data.get('time'),
                    'method': payment_method,
                    'summary': context.user_data.get('summary'),
                    'status': order_status,
                    'payment_verified': context.user_data.get('payment_verified', False),
                    'payment_amount': context.user_data.get('payment_amount', 0),
                    'is_preorder': is_preorder,
                    'created_at': datetime.now(timezone.utc),
                }
                col = get_orders_collection()
                await col.insert_one(order_doc)
                
                # Admin notifications are handled by admin bot
                # Client bot only saves orders to MongoDB
            else:
                # Fallback to local storage
                import json
                from datetime import datetime
                order_data = {
                    'user_id': uid,
                    'items': context.user_data.get('items', {}),
                    'total': context.user_data.get('total', 0),
                    'contact': context.user_data.get('contact'),
                    'delivery': context.user_data.get('delivery'),
                    'time': context.user_data.get('time'),
                    'method': payment_method,
                    'summary': context.user_data.get('summary'),
                    'status': order_status,
                    'payment_verified': context.user_data.get('payment_verified', False),
                    'payment_amount': context.user_data.get('payment_amount', 0),
                    'created_at': datetime.now().isoformat(),
                }
                
                # Load existing orders
                orders_file = 'data/orders.json'
                try:
                    with open(orders_file, 'r', encoding='utf-8') as f:
                        orders = json.load(f)
                except (FileNotFoundError, json.JSONDecodeError):
                    orders = []
                
                orders.append(order_data)
                
                # Save back to file
                with open(orders_file, 'w', encoding='utf-8') as f:
                    json.dump(orders, f, ensure_ascii=False, indent=2)

            await update.message.reply_text(status_message)
        except Exception as e:
            logging.error(f"Error saving order: {e}")
            await update.message.reply_text('❌ Произошла ошибка при сохранении заказа. Попробуйте еще раз.')
    else:
        await update.message.reply_text('❌ Заказ отменён.')
    return ConversationHandler.END


# Function to update order status (called by admin bot)
async def update_order_status(order_id: str, new_status: str, user_id: int, bot):
    """Update order status and notify client with message editing"""
    try:
        from datetime import datetime, timezone
        from .mongo import get_notifications_collection, get_orders_collection
        
        # Create status update notification with message editing capability
        status_messages = {
            'preparing': '🔄 Ваш заказ готовится!',
            'ready': '✅ Ваш заказ готов!',
            'delivered': '🎉 Заказ доставлен!',
            'cancelled': '❌ Заказ отменен',
            'confirmed': '✅ Оплата подтверждена! Заказ принят в обработку.'
        }
        
        message = status_messages.get(new_status, f'📋 Статус заказа: {new_status}')
        
        # Get order details for message editing
        orders_col = get_orders_collection()
        order = await orders_col.find_one({'_id': order_id})
        
        if order:
            # Create enhanced notification with order details for message editing
            enhanced_message = await create_status_update_message(order, new_status, message)
            
            notification_doc = {
                'user_id': user_id,
                'order_id': order_id,
                'status': new_status,
                'message': enhanced_message,
                'original_message': message,
                'edit_message': True,  # Flag to indicate this should edit existing message
                'sent': False,
                'created_at': datetime.now(timezone.utc)
            }
        else:
            # Fallback to simple notification
            notification_doc = {
                'user_id': user_id,
                'order_id': order_id,
                'status': new_status,
                'message': message,
                'edit_message': False,
                'sent': False,
                'created_at': datetime.now(timezone.utc)
            }
        
        notifications_col = get_notifications_collection()
        await notifications_col.insert_one(notification_doc)
        
        # Update the order status in orders collection
        await orders_col.update_one(
            {'_id': order_id},
            {'$set': {'status': new_status, 'updated_at': datetime.now(timezone.utc)}}
        )
        
        logging.info(f"Order {order_id} status updated to {new_status}")
        
    except Exception as e:
        logging.error(f"Error updating order status: {e}")


async def create_status_update_message(order: dict, new_status: str, status_message: str) -> str:
    """Create a complete order status message for editing"""
    try:
        # Extract order details
        order_id = order.get('_id', 'Unknown')
        total = order.get('total', 0)
        delivery = order.get('delivery', '—')
        time = order.get('time', '—')
        contact = order.get('contact', '—')
        items = order.get('items', {})
        
        # Build order composition
        samsa_items = []
        packaging_items = []
        
        for key, qty in items.items():
            if qty > 0:
                if key in SAMSA_KEYS:
                    # Use Russian names for admin notifications
                    samsa_items.append(f"• {DISPLAY_NAMES['ru'][key]} — {qty} шт")
                elif key in PACKAGING_KEYS:
                    # Use Russian names for admin notifications
                    packaging_items.append(f"• {DISPLAY_NAMES['ru'][key]} — {qty} шт")
        
        # Create the complete message
        message = f"🆔 Заказ #{order_id}\n"
        message += f"💰 Сумма: {total:,} сум\n"
        message += f"📍 Доставка: {delivery}\n"
        message += f"⏰ Время: {time}\n"
        message += f"💳 Оплата: {order.get('method', '—')}\n\n"
        
        if samsa_items:
            message += "Состав заказа:\n" + "\n".join(samsa_items) + "\n\n"
        
        if packaging_items:
            message += "Упаковка:\n" + "\n".join(packaging_items) + "\n\n"
        
        # Add status message
        message += f"📋 <b>Статус:</b> {status_message}"
        
        return message
        
    except Exception as e:
        logging.error(f"Error creating status message: {e}")
        return status_message


# Admin notification functions removed from client bot
# These should only exist in the admin bot

# Handler for noop (does nothing, just answers callback query)
async def noop(update, context):
    await update.callback_query.answer()


# Temporary cart functions
async def save_temp_cart(user_id: int, cart_data: dict) -> bool:
    """Save temporary cart to MongoDB"""
    try:
        temp_carts_col = get_temp_carts_collection()
        cart_doc = {
            'user_id': user_id,
            'items': cart_data.get('items', {}),
            'total': cart_data.get('total', 0),
            'has_samsa': cart_data.get('has_samsa', False),
            'has_packaging': cart_data.get('has_packaging', False),
            'created_at': datetime.now(timezone.utc),
            'updated_at': datetime.now(timezone.utc)
        }
        
        # Upsert (update if exists, insert if not)
        await temp_carts_col.update_one(
            {'user_id': user_id},
            {'$set': cart_doc},
            upsert=True
        )
        return True
    except Exception as e:
        logging.error(f"Error saving temp cart: {e}")
        return False


async def load_temp_cart(user_id: int) -> dict:
    """Load temporary cart from MongoDB"""
    try:
        temp_carts_col = get_temp_carts_collection()
        cart = await temp_carts_col.find_one({'user_id': user_id})
        if cart:
            return {
                'items': cart.get('items', {}),
                'total': cart.get('total', 0),
                'has_samsa': cart.get('has_samsa', False),
                'has_packaging': cart.get('has_packaging', False)
            }
        return {}
    except Exception as e:
        logging.error(f"Error loading temp cart: {e}")
        return {}


async def delete_temp_cart(user_id: int) -> bool:
    """Delete temporary cart from MongoDB"""
    try:
        temp_carts_col = get_temp_carts_collection()
        await temp_carts_col.delete_one({'user_id': user_id})
        return True
    except Exception as e:
        logging.error(f"Error deleting temp cart: {e}")
        return False


def has_meaningful_cart(items: dict) -> bool:
    """Check if cart has meaningful content (samsa or packaging)"""
    samsa_items = {k: v for k, v in items.items() if k in SAMSA_KEYS and v > 0}
    packaging_items = {k: v for k, v in items.items() if k in PACKAGING_KEYS and v > 0}
    return len(samsa_items) > 0 or len(packaging_items) > 0


async def show_cart_summary(update, context):
    """Show cart summary for temp cart restoration"""
    # Debug logging to track duplicate calls
    logging.info(f"show_cart_summary called - has callback_query: {hasattr(update, 'callback_query') and update.callback_query is not None}, has message: {hasattr(update, 'message') and update.message is not None}")
    
    items = context.user_data.get('items', {})
    total = context.user_data.get('total', 0)
    
    # Build cart summary
    samsa_items = {k: v for k, v in items.items() if k in SAMSA_KEYS and v > 0}
    packaging_items = {k: v for k, v in items.items() if k in PACKAGING_KEYS and v > 0}
    
    summary = "🛒 <b>Ваша корзина:</b>\n\n"
    
    if samsa_items:
        summary += "<b>🥟 Самса:</b>\n"
        for key, qty in samsa_items.items():
            summary += f"• {get_display_name(context, key)} — {qty} шт\n"
        summary += "\n"
    
    if packaging_items:
        summary += "<b>📦 Упаковка:</b>\n"
        for key, qty in packaging_items.items():
            summary += f"• {get_display_name(context, key)} — {qty} шт\n"
        summary += "\n"
    
    summary += f"💰 <b>Итого:</b> {total:,} сум"
    
    # Add buttons based on cart state
    buttons = []
    
    if not samsa_items:
        # Empty cart - only show option to add items
        buttons.append([InlineKeyboardButton("➕ Добавить самсу", callback_data="back_to_menu")])
        buttons.append([InlineKeyboardButton("🗑️ Очистить корзину", callback_data="clear_cart")])
    elif samsa_items and not packaging_items:
        # Has samsa but no packaging - show option to add more samsa or proceed to packaging
        buttons.append([InlineKeyboardButton("➕ Добавить еще самсу", callback_data="back_to_menu")])
        buttons.append([InlineKeyboardButton("✏️ Изменить количество", callback_data="edit_cart")])
        buttons.append([InlineKeyboardButton("✅ Выбрать упаковку", callback_data="done_menu")])
        buttons.append([InlineKeyboardButton("🗑️ Очистить корзину", callback_data="clear_cart")])
    elif samsa_items and packaging_items:
        # Has both - show option to edit or proceed
        buttons.append([InlineKeyboardButton("✏️ Изменить корзину", callback_data="edit_cart")])
        buttons.append([InlineKeyboardButton("✅ Продолжить заказ", callback_data="confirm_cart")])
        buttons.append([InlineKeyboardButton("🗑️ Очистить корзину", callback_data="clear_cart")])
    
    kb = InlineKeyboardMarkup(buttons)
    
    # Only send one message - check if it's from a callback or message
    # Priority: callback_query > message (to avoid duplicates)
    if hasattr(update, 'callback_query') and update.callback_query:
        # It's from a callback button - try to edit the existing message
        try:
            await update.callback_query.edit_message_text(summary, reply_markup=kb, parse_mode='HTML')
        except Exception as e:
            logging.error(f"Error editing cart message: {e}")
            # If edit fails, send a new message
            try:
                await update.callback_query.message.reply_text(summary, reply_markup=kb, parse_mode='HTML')
            except Exception as e2:
                logging.error(f"Error sending fallback cart message: {e2}")
    elif hasattr(update, 'message') and update.message:
        # It's from a text message/keyboard button - send a new message
        try:
            await update.message.reply_text(summary, reply_markup=kb, parse_mode='HTML')
        except Exception as e:
            logging.error(f"Error sending cart message: {e}")
    
    return PACKAGING_SELECT  # Return to packaging state for cart management


async def edit_cart_items(update, context):
    """Show cart items for editing"""
    q = update.callback_query
    await q.answer()
    
    items = context.user_data.get('items', {})
    samsa_items = {k: v for k, v in items.items() if k in SAMSA_KEYS and v > 0}
    
    if not samsa_items:
        await q.edit_message_text(
            "❌ <b>Корзина пуста!</b>\n\nДобавьте самсу для редактирования.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Назад к меню", callback_data="back_to_menu")]
            ]),
            parse_mode='HTML'
        )
        return ITEM_SELECT
    
    # Show items with edit buttons
    summary = "✏️ <b>Редактировать корзину:</b>\n\n"
    buttons = []
    
    for key, qty in samsa_items.items():
        summary += f"• {get_short_name(context, key)} — {qty} шт\n"
        buttons.append([
            InlineKeyboardButton(f"✏️ {get_short_name(context, key)} ({qty} шт)", callback_data=f'edit_item:{key}'),
            InlineKeyboardButton(f"🗑️", callback_data=f'remove:{key}')
        ])
    
    buttons.append([InlineKeyboardButton("⬅️ Назад к корзине", callback_data="back_to_cart")])
    
    kb = InlineKeyboardMarkup(buttons)
    
    try:
        # Check if the message has text (not a photo message)
        if q.message.text:
            await q.edit_message_text(summary, reply_markup=kb, parse_mode='HTML')
        else:
            # If it's a photo message, send a new text message
            await q.message.reply_text(summary, reply_markup=kb, parse_mode='HTML')
    except Exception as e:
        logging.error(f"Error editing message in edit_cart_items: {e}")
        # Always fallback to new message
        await q.message.reply_text(summary, reply_markup=kb, parse_mode='HTML')
    
    return ITEM_EDIT


async def edit_specific_item(update, context):
    """Edit a specific item in the cart"""
    q = update.callback_query
    await q.answer()
    
    try:
        key = q.data.split(':', 1)[1]
        items = context.user_data.setdefault('items', {})
        qty = items.get(key, 0)
        
        caption = f"✏️ <b>Редактировать:</b>\n\n🥟 {get_display_name(context, key)}\n💰 {get_text(context, 'price_label')} {PRICES[key]:,} сум\n📦 {get_text(context, 'in_cart')} {qty} шт"
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton('➖', callback_data=f'dec:{key}'),
                InlineKeyboardButton(f'{qty}', callback_data='noop'),
                InlineKeyboardButton('➕', callback_data=f'inc:{key}')
            ],
            [InlineKeyboardButton('🗑️ Удалить', callback_data=f'remove:{key}')],
            [InlineKeyboardButton('⬅️ Назад к корзине', callback_data='back_to_cart')]
        ])
        
        # Try to send with photo using cached file_id or upload new
        try:
            # Initialize photo cache if not exists
            if 'photo_cache' not in context.bot_data:
                context.bot_data['photo_cache'] = {}
            
            photo_cache = context.bot_data['photo_cache']
            
            # Check if we have cached file_id
            if key in photo_cache:
                try:
                    await q.message.reply_photo(
                        photo=photo_cache[key],
                        caption=caption,
                        reply_markup=keyboard,
                        parse_mode='HTML'
                    )
                    return ITEM_EDIT
                except Exception as cache_error:
                    logging.warning(f"Cached photo failed for {key}, will re-upload: {cache_error}")
                    del photo_cache[key]
            
            # Upload photo and cache file_id
            photo_path = f'data/img/{key}.jpg'
            if os.path.exists(photo_path):
                file_size = os.path.getsize(photo_path)
                if file_size > 5 * 1024 * 1024:  # 5MB limit
                    logging.warning(f"Photo {key} is too large ({file_size} bytes), using text fallback")
                    await q.message.reply_text(caption, reply_markup=keyboard, parse_mode='HTML')
                else:
                    with open(photo_path, 'rb') as photo:
                        sent_msg = await q.message.reply_photo(
                            photo=photo,
                            caption=caption,
                            reply_markup=keyboard,
                            parse_mode='HTML'
                        )
                        if sent_msg.photo:
                            photo_cache[key] = sent_msg.photo[-1].file_id
            else:
                await q.message.reply_text(caption, reply_markup=keyboard, parse_mode='HTML')
        except Exception as e:
            logging.error(f"Error sending photo for {key}: {e}")
            await q.message.reply_text(caption, reply_markup=keyboard, parse_mode='HTML')
        
        return ITEM_EDIT
        
    except Exception as e:
        logging.error(f"Error in edit_specific_item: {e}")
        await q.message.reply_text("❌ Произошла ошибка при редактировании.")
        return ITEM_EDIT


async def remove_item(update, context):
    """Remove an item from cart"""
    q = update.callback_query
    await q.answer()
    
    try:
        key = q.data.split(':', 1)[1]
        items = context.user_data.setdefault('items', {})
        
        if key in items:
            del items[key]
            # Recalculate total
            total = sum(PRICES[k] * v for k, v in items.items())
            context.user_data['total'] = total
            
            # Save to temp cart
            user_id = update.effective_user.id
            samsa_items = {k: v for k, v in items.items() if k in SAMSA_KEYS and v > 0}
            packaging_items = {k: v for k, v in items.items() if k in PACKAGING_KEYS and v > 0}
            
            cart_data = {
                'items': items,
                'total': total,
                'has_samsa': len(samsa_items) > 0,
                'has_packaging': len(packaging_items) > 0
            }
            
            await save_temp_cart(user_id, cart_data)
            
            # Delete the message (photo or text)
            try:
                await q.message.delete()
            except Exception as e:
                logging.error(f"Error deleting message in remove_item: {e}")
            
            # Send confirmation and go back to cart
            await update.effective_chat.send_message(
                f"🗑️ <b>{get_short_name(context, key)}</b> удален из корзины.",
                parse_mode='HTML'
            )
            
            # Show updated cart
            return await back_to_cart(update, context)
        else:
            try:
                # Check if the message has text (not a photo message)
                if q.message.text:
                    await q.edit_message_text("❌ Товар не найден в корзине.")
                else:
                    # If it's a photo message, send a new text message
                    await q.message.reply_text("❌ Товар не найден в корзине.")
            except Exception as e:
                logging.error(f"Error editing message in remove_item (not found): {e}")
                # Always fallback to new message
                await q.message.reply_text("❌ Товар не найден в корзине.")
        
        return ITEM_EDIT
        
    except Exception as e:
        logging.error(f"Error in remove_item: {e}")
        await q.message.reply_text("❌ Произошла ошибка при удалении.")
        return ITEM_EDIT


async def cart_command(update, context):
    """Handle /cart command to view and manage temporary cart"""
    try:
        # Debug logging
        logging.info(f"cart_command called by user {update.effective_user.id}")
        
        user_id = update.effective_user.id
        
        # First, check if we have items in current context (during active ordering)
        current_items = context.user_data.get('items', {})
        
        # If we have items in context, use them (we're in an active conversation)
        if has_meaningful_cart(current_items):
            # Save current state to temp cart first
            total = sum(PRICES[k] * v for k, v in current_items.items())
            samsa_items = {k: v for k, v in current_items.items() if k in SAMSA_KEYS and v > 0}
            packaging_items = {k: v for k, v in current_items.items() if k in PACKAGING_KEYS and v > 0}
            
            cart_data = {
                'items': current_items,
                'total': total,
                'has_samsa': len(samsa_items) > 0,
                'has_packaging': len(packaging_items) > 0
            }
            
            await save_temp_cart(user_id, cart_data)
            context.user_data['total'] = total
            
            # Check if we're in order details phase (NAME, PHONE, ADDRESS, DELIVERY, etc.)
            # In these states, just show read-only cart info without changing state
            if context.user_data.get('customer_name') or context.user_data.get('customer_phone') or context.user_data.get('customer_address') or context.user_data.get('delivery') or context.user_data.get('method'):
                # Show read-only cart summary during order details phase
                summary = "🛒 <b>Ваша корзина:</b>\n\n"
                
                summary += "<b>🥟 Самса:</b>\n"
                for key, qty in samsa_items.items():
                    summary += f"• {get_display_name(context, key)} — {qty} шт\n"
                summary += "\n"
                
                if packaging_items:
                    summary += "<b>📦 Упаковка:</b>\n"
                    for key, qty in packaging_items.items():
                        summary += f"• {get_display_name(context, key)} — {qty} шт\n"
                    summary += "\n"
                
                summary += f"💰 <b>Итого:</b> {total:,} сум\n\n"
                summary += "💡 Чтобы изменить корзину, нажмите '❌ Отменить заказ' и начните заново"
                
                await update.message.reply_text(
                    summary,
                    parse_mode='HTML'
                )
                
                # Return None to stay in current state (don't change conversation state)
                return None
            
            # Otherwise, show interactive cart summary (can edit)
            await show_cart_summary(update, context)
            # Don't return any state - we're not in a conversation when called from main menu
            return None
        
        # Otherwise, try to load from temp cart (cart command outside conversation)
        temp_cart = await load_temp_cart(user_id)
        
        if not temp_cart or not has_meaningful_cart(temp_cart.get('items', {})):
            await update.message.reply_text(
                "🛒 <b>Ваша корзина пуста</b>\n\n"
                "Начните оформление заказа, чтобы добавить товары в корзину.",
                reply_markup=context.bot_data['keyb']['main'],
                parse_mode='HTML'
            )
            # Don't return any state - we're not in a conversation
            return None
        
        # Show saved cart info (read-only view outside conversation)
        items = temp_cart.get('items', {})
        total = temp_cart.get('total', 0)
        
        samsa_items = {k: v for k, v in items.items() if k in SAMSA_KEYS and v > 0}
        packaging_items = {k: v for k, v in items.items() if k in PACKAGING_KEYS and v > 0}
        
        summary = "🛒 <b>Ваша сохраненная корзина:</b>\n\n"
        
        if samsa_items:
            summary += "<b>🥟 Самса:</b>\n"
            for key, qty in samsa_items.items():
                summary += f"• {get_display_name(context, key)} — {qty} шт\n"
            summary += "\n"
        
        if packaging_items:
            summary += "<b>📦 Упаковка:</b>\n"
            for key, qty in packaging_items.items():
                summary += f"• {get_display_name(context, key)} — {qty} шт\n"
            summary += "\n"
        
        summary += f"💰 <b>Итого:</b> {total:,} сум\n\n"
        summary += "💡 Используйте /order чтобы продолжить заказ"
        
        await update.message.reply_text(
            summary,
            reply_markup=context.bot_data['keyb']['main'],
            parse_mode='HTML'
        )
        
        # Don't return any state - we're showing info only
        return None
        
    except Exception as e:
        logging.error(f"Error in cart_command: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка при загрузке корзины.\n\n"
            "Попробуйте начать новый заказ.",
            reply_markup=context.bot_data['keyb']['main'],
            parse_mode='HTML'
        )
        return None


async def cart_from_main_menu(update, context):
    """Handle cart button from main menu - should NOT start order conversation"""
    try:
        user_id = update.effective_user.id
        
        # Try to load from temp cart
        temp_cart = await load_temp_cart(user_id)
        
        if not temp_cart or not has_meaningful_cart(temp_cart.get('items', {})):
            await update.message.reply_text(
                "🛒 <b>Ваша корзина пуста</b>\n\n"
                "Начните оформление заказа, чтобы добавить товары в корзину.",
                reply_markup=context.bot_data['keyb']['main'],
                parse_mode='HTML'
            )
            return
        
        # Show saved cart info (read-only view)
        items = temp_cart.get('items', {})
        total = temp_cart.get('total', 0)
        
        samsa_items = {k: v for k, v in items.items() if k in SAMSA_KEYS and v > 0}
        packaging_items = {k: v for k, v in items.items() if k in PACKAGING_KEYS and v > 0}
        
        summary = "🛒 <b>Ваша сохраненная корзина:</b>\n\n"
        
        if samsa_items:
            summary += "<b>🥟 Самса:</b>\n"
            for key, qty in samsa_items.items():
                summary += f"• {get_display_name(context, key)} — {qty} шт\n"
            summary += "\n"
        
        if packaging_items:
            summary += "<b>📦 Упаковка:</b>\n"
            for key, qty in packaging_items.items():
                summary += f"• {get_display_name(context, key)} — {qty} шт\n"
            summary += "\n"
        
        summary += f"💰 <b>Итого:</b> {total:,} сум\n\n"
        summary += "💡 Используйте '🛒 Сделать заказ' чтобы продолжить заказ"
        
        await update.message.reply_text(
            summary,
            reply_markup=context.bot_data['keyb']['main'],
            parse_mode='HTML'
        )
        
    except Exception as e:
        logging.error(f"Error in cart_from_main_menu: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка при загрузке корзины. Попробуйте позже.",
            reply_markup=context.bot_data['keyb']['main']
        )


async def handle_order_interruption(update, context):
    """Handle when user clicks other commands during ordering"""
    try:
        user_id = update.effective_user.id
        items = context.user_data.get('items', {})
        
        # Only save if cart has meaningful content
        if has_meaningful_cart(items):
            total = context.user_data.get('total', 0)
            samsa_items = {k: v for k, v in items.items() if k in SAMSA_KEYS and v > 0}
            packaging_items = {k: v for k, v in items.items() if k in PACKAGING_KEYS and v > 0}
            
            cart_data = {
                'items': items,
                'total': total,
                'has_samsa': len(samsa_items) > 0,
                'has_packaging': len(packaging_items) > 0
            }
            
            # Save cart with timeout protection
            try:
                await save_temp_cart(user_id, cart_data)
            except Exception as save_error:
                logging.error(f"Error saving temp cart: {save_error}")
                # Continue even if save fails
            
            # Clear user data to prevent state conflicts
            context.user_data.clear()
            
            # Send response with timeout protection
            try:
                await update.message.reply_text(
                    "⏸️ <b>Заказ приостановлен</b>\n\n"
                    "Ваша корзина сохранена. Вы можете продолжить оформление заказа в любое время, "
                    "используя команду /cart или кнопку \"🛒 Корзина\".",
                    reply_markup=context.bot_data.get('keyb', {}).get('main'),
                    parse_mode='HTML'
                )
            except Exception as reply_error:
                logging.error(f"Error sending interruption message: {reply_error}")
                # Try simple fallback
                await update.message.reply_text("⏸️ Заказ приостановлен. Ваша корзина сохранена.")
        else:
            # Clear empty cart and user data
            try:
                await delete_temp_cart(user_id)
            except Exception as delete_error:
                logging.error(f"Error deleting temp cart: {delete_error}")
            
            context.user_data.clear()
            
            try:
                await update.message.reply_text(
                    "✅ Вы вышли из режима заказа.\n\n"
                    "Начните новый заказ, когда будете готовы!",
                    reply_markup=context.bot_data.get('keyb', {}).get('main'),
                    parse_mode='HTML'
                )
            except Exception as reply_error:
                logging.error(f"Error sending exit message: {reply_error}")
                await update.message.reply_text("✅ Вы вышли из режима заказа.")
        
        # Force conversation to end
        return ConversationHandler.END
        
    except Exception as e:
        logging.error(f"Critical error in handle_order_interruption: {e}")
        # Emergency cleanup
        try:
            context.user_data.clear()
            await update.message.reply_text("✅ Вы вышли из режима заказа.")
        except Exception as emergency_error:
            logging.error(f"Emergency cleanup failed: {emergency_error}")
        return ConversationHandler.END


# Handler for "Finish Order" button from keyboard
async def finish_menu_from_keyboard(update, context):
    """Handle the 'Finish Order' button from reply keyboard"""
    items = context.user_data.get('items', {})
    
    # Check if cart has any samsa items
    samsa_items = {k: v for k, v in items.items() if k in SAMSA_KEYS and v > 0}
    if not samsa_items:
        await update.message.reply_text(
            "❌ <b>Корзина пуста!</b>\n\nДобавьте хотя бы одну самсу для оформления заказа.",
            parse_mode='HTML'
        )
        return ITEM_SELECT
    
    # Calculate total
    total = sum(PRICES[k] * v for k, v in items.items())
    context.user_data['total'] = total
    
    # Show cart summary
    lines = [f"• {get_display_name(context, k)} — {v} шт" for k, v in samsa_items.items()]
    receipt = "\n".join(lines)
    text = (
        "🛒 <b>Корзина:</b>\n"
        f"{receipt}\n\n"
        f"💰 <b>Итого:</b> {total:,} сум"
    )
    
    await update.message.reply_text(text, parse_mode='HTML')
    
    # Now show packaging menu with image
    return await show_packaging_menu(update, context)


# Handler for "Cancel Order" button
async def cancel_order(update, context):
    """Handle the 'Cancel Order' button - clear cart and exit"""
    user_id = update.effective_user.id
    
    # Delete temp cart
    await delete_temp_cart(user_id)
    
    # Clear user data
    context.user_data.clear()
    
    await update.message.reply_text(
        "❌ <b>Заказ отменён</b>\n\nВаша корзина очищена.",
        reply_markup=context.bot_data['keyb']['main'],
        parse_mode='HTML'
    )
    
    return ConversationHandler.END


# Handler to block side buttons during active ordering
async def block_side_buttons(update, context):
    """Block side buttons during active ordering - only allow Cancel Order"""
    await update.message.reply_text(
        "⚠️ <b>Вы в процессе оформления заказа</b>\n\n"
        "Пожалуйста, завершите текущий заказ или нажмите '❌ Отменить заказ' чтобы вернуться в главное меню.",
        parse_mode='HTML'
    )
    # Stay in the current state
    return None  # Don't change state


order_conv_handler = ConversationHandler(
    entry_points=[
        CommandHandler('order', order_start),
        MessageHandler(
            filters.Regex(f'^({TEXTS["ru"]["btn_order"]}|{TEXTS["uz"]["btn_order"]})$'),
            order_start
        ),
    ],
    states={
        ITEM_SELECT: [
            CallbackQueryHandler(continue_with_cart, pattern=r'^continue_cart$'),
            CallbackQueryHandler(start_new_cart, pattern=r'^new_cart$'),
            CallbackQueryHandler(select_samsa, pattern=r'^samsa:'),
            CallbackQueryHandler(finish_menu, pattern=r'^done_menu$'),
            # Handle keyboard buttons during item selection
            MessageHandler(filters.Regex('^✅ (Завершить заказ|Buyurtmani yakunlash)$'), finish_menu_from_keyboard),
            MessageHandler(filters.Regex('^❌ (Отменить заказ|Buyurtmani bekor qilish)$'), cancel_order),
            MessageHandler(filters.Regex('^🛒 (Корзина|Savat)$'), cart_command),
            # Block all other side buttons
            MessageHandler(
                filters.Regex('^(💬 Отзывы|ℹ️ О нас|🔥 Акции|⏰ Время работы|🌐 Язык|❓ Помощь|📞 Контакты|📝 Оставить отзыв|🇷🇺 Русский|🇺🇿 O\'zbek)$'),
                block_side_buttons
            ),
        ],
        ITEM_EDIT: [
            CallbackQueryHandler(inc_item, pattern=r'^inc:'),
            CallbackQueryHandler(dec_item, pattern=r'^dec:'),
            CallbackQueryHandler(back_to_menu, pattern=r'^back_to_menu$'),
            CallbackQueryHandler(finish_item, pattern=r'^finish_item:'),
            CallbackQueryHandler(edit_specific_item, pattern=r'^edit_item:'),
            CallbackQueryHandler(remove_item, pattern=r'^remove:'),
            CallbackQueryHandler(back_to_cart, pattern=r'^back_to_cart$'),
            CallbackQueryHandler(noop, pattern=r'^noop$'),
            # Handle keyboard buttons during item editing
            MessageHandler(filters.Regex('^✅ (Завершить заказ|Buyurtmani yakunlash)$'), finish_menu_from_keyboard),
            MessageHandler(filters.Regex('^❌ (Отменить заказ|Buyurtmani bekor qilish)$'), cancel_order),
            MessageHandler(filters.Regex('^🛒 (Корзина|Savat)$'), cart_command),
            # Block all other side buttons
            MessageHandler(
                filters.Regex('^(💬 Отзывы|ℹ️ О нас|🔥 Акции|⏰ Время работы|🌐 Язык|❓ Помощь|📞 Контакты|📝 Оставить отзыв|🇷🇺 Русский|🇺🇿 O\'zbek)$'),
                block_side_buttons
            ),
        ],
        PACKAGING_SELECT: [
            CallbackQueryHandler(select_packaging, pattern=r'^packaging:'),
            CallbackQueryHandler(back_to_cart, pattern=r'^back_to_cart$'),
            CallbackQueryHandler(confirm_cart, pattern='^confirm_cart$'),
            CallbackQueryHandler(edit_cart_items, pattern='^edit_cart$'),
            CallbackQueryHandler(clear_cart, pattern='^clear_cart$'),
            CallbackQueryHandler(back_to_menu, pattern=r'^back_to_menu$'),
            CallbackQueryHandler(finish_menu, pattern=r'^done_menu$'),
            # Handle keyboard buttons
            MessageHandler(filters.Regex('^❌ Отменить заказ$'), cancel_order),
            MessageHandler(filters.Regex('^🛒 (Корзина|Savat)$'), cart_command),
            # Block all other side buttons
            MessageHandler(
                filters.Regex('^(💬 Отзывы|ℹ️ О нас|🔥 Акции|⏰ Время работы|🌐 Язык|❓ Помощь|📞 Контакты|📝 Оставить отзыв|🇷🇺 Русский|🇺🇿 O\'zbek|✅ Завершить заказ)$'),
                block_side_buttons
            ),
        ],
        NAME:       [
            MessageHandler(filters.Regex('^❌ Отменить заказ$'), cancel_order),
            MessageHandler(filters.Regex('^🛒 (Корзина|Savat)$'), cart_command),
            MessageHandler(
                filters.Regex('^(💬 Отзывы|ℹ️ О нас|🔥 Акции|⏰ Время работы|🌐 Язык|❓ Помощь|📞 Контакты|📝 Оставить отзыв|🇷🇺 Русский|🇺🇿 O\'zbek|✅ Завершить заказ)$'),
                block_side_buttons
            ),
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_name_input)
        ],
        PHONE:       [
            MessageHandler(filters.Regex('^❌ Отменить заказ$'), cancel_order),
            MessageHandler(filters.Regex('^🛒 (Корзина|Savat)$'), cart_command),
            MessageHandler(
                filters.Regex('^(💬 Отзывы|ℹ️ О нас|🔥 Акции|⏰ Время работы|🌐 Язык|❓ Помощь|📞 Контакты|📝 Оставить отзыв|🇷🇺 Русский|🇺🇿 O\'zbek|✅ Завершить заказ)$'),
                block_side_buttons
            ),
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_phone_input)
        ],
        ADDRESS:       [
            MessageHandler(filters.Regex('^❌ Отменить заказ$'), cancel_order),
            MessageHandler(filters.Regex('^🛒 (Корзина|Savat)$'), cart_command),
            MessageHandler(
                filters.Regex('^(💬 Отзывы|ℹ️ О нас|🔥 Акции|⏰ Время работы|🌐 Язык|❓ Помощь|📞 Контакты|📝 Оставить отзыв|🇷🇺 Русский|🇺🇿 O\'zbek|✅ Завершить заказ)$'),
                block_side_buttons
            ),
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_address_input)
        ],
        DELIVERY:      [
            MessageHandler(filters.Regex('^❌ Отменить заказ$'), cancel_order),
            MessageHandler(filters.Regex('^🛒 (Корзина|Savat)$'), cart_command),
            MessageHandler(
                filters.Regex('^(💬 Отзывы|ℹ️ О нас|🔥 Акции|⏰ Время работы|🌐 Язык|❓ Помощь|📞 Контакты|📝 Оставить отзыв|🇷🇺 Русский|🇺🇿 O\'zbek)$'),
                block_side_buttons
            ),
            MessageHandler(filters.TEXT & ~filters.COMMAND, order_contact)
        ],
        TIME_CHOICE:   [
            MessageHandler(filters.Regex('^❌ Отменить заказ$'), cancel_order),
            MessageHandler(filters.Regex('^🛒 (Корзина|Savat)$'), cart_command),
            MessageHandler(
                filters.Regex('^(💬 Отзывы|ℹ️ О нас|🔥 Акции|⏰ Время работы|🌐 Язык|❓ Помощь|📞 Контакты|📝 Оставить отзыв|🇷🇺 Русский|🇺🇿 O\'zbek)$'),
                block_side_buttons
            ),
            MessageHandler(filters.TEXT & ~filters.COMMAND, order_time)
        ],
        PAYMENT:       [
            MessageHandler(filters.Regex('^❌ Отменить заказ$'), cancel_order),
            MessageHandler(filters.Regex('^🛒 (Корзина|Savat)$'), cart_command),
            MessageHandler(
                filters.Regex('^(💬 Отзывы|ℹ️ О нас|🔥 Акции|⏰ Время работы|🌐 Язык|❓ Помощь|📞 Контакты|📝 Оставить отзыв|🇷🇺 Русский|🇺🇿 O\'zbek)$'),
                block_side_buttons
            ),
            MessageHandler(filters.Regex('^(💵 Наличные|💳 Оплатить по карте)$'), order_payment)
        ],
        VERIFY_PAYMENT:[
            MessageHandler(filters.Regex('^❌ Отменить заказ$'), cancel_order),
            MessageHandler(filters.Regex('^🛒 (Корзина|Savat)$'), cart_command),
            MessageHandler(
                filters.Regex('^(💬 Отзывы|ℹ️ О нас|🔥 Акции|⏰ Время работы|🌐 Язык|❓ Помощь|📞 Контакты|📝 Оставить отзыв|🇷🇺 Русский|🇺🇿 O\'zbek)$'),
                block_side_buttons
            ),
            MessageHandler(filters.TEXT & ~filters.COMMAND, verify_payment)
        ],
        CONFIRM:       [
            MessageHandler(filters.Regex('^❌ Отменить заказ$'), cancel_order),
            MessageHandler(filters.Regex('^🛒 (Корзина|Savat)$'), cart_command),
            MessageHandler(
                filters.Regex('^(💬 Отзывы|ℹ️ О нас|🔥 Акции|⏰ Время работы|🌐 Язык|❓ Помощь|📞 Контакты|📝 Оставить отзыв|🇷🇺 Русский|🇺🇿 O\'zbek)$'),
                block_side_buttons
            ),
            MessageHandler(filters.TEXT & ~filters.COMMAND, order_confirm)
        ],
    },
    fallbacks=[
        CommandHandler('main', main_menu),
        # Cart command is handled within conversation states, not as fallback
    ],
    per_chat=True,
    per_user=True,
    per_message=False
)
