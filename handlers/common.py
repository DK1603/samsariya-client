# handlers/common.py

import json
from telegram import ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from config import AVAILABILITY_FILE
from .mongo import get_availability_dict, get_availability_collection

LANGUAGES = ['ru', 'uz']

# localized texts & button labels
TEXTS = {
    'ru': {
        'welcome': (
            'Assalomu alaykum!\n'
            'Добро пожаловать в Samsariya — бот для домашней самсы.\n'
            '+998880009099'
        ),
        'off_hours_preorder': 'Сейчас мы не работаем, но Вы можете оформить предзаказ',
        'about': 'Samsariya — это домашняя самса по семейным рецептам, без жира и добавок.',
        'promo': (
            'Акции и новинки:\n'
            '- Самса с тыквой (сезонная)\n'
            '- Скидка 10% при оплате через Payme'
        ),
        'working_hours': 'Заказы принимаем с 9:00 до 17:00. Доставка по Ташкенту — 1–2 часа.',
        'payments': 'Оплатить наличными или картой через Payme (100% предоплата со скидкой).',
        'repeat_unavailable': 'У вас ещё нет предыдущих заказов.',
        'ask_review': 'Оставьте отзыв (текст или голосовое).',
        'thank_review': 'Спасибо! Ваш отзыв отправлен.',
        'show_reviews': 'Отзывы клиентов:',
        # buttons
        'btn_order':    '🛒 Сделать заказ',
        'btn_reviews':  '💬 Отзывы',
        'btn_about':    'ℹ️ О нас',
        'btn_promo':    '🔥 Акции',
        'btn_hours':    '⏰ Время работы',
        'btn_payments': '💳 Оплата',
        'btn_repeat':   '🔁 Повтор заказа',
        'btn_language':'🌐 Язык',
        'btn_help':     '❓ Помощь',
        'btn_back':     '◀️ Назад',
        'btn_contacts': '📞 Контакты',
        'btn_leave_review': '📝 Оставить отзыв',
        'lang_choice_ru': '🇷🇺 Русский',
        'lang_choice_uz': '🇺🇿 O\'zbek',
        'pieces_suffix': 'шт',
        # Order flow texts
        'cart_saved': 'У вас есть сохраненная корзина:',
        'samsa_section': 'Самса:',
        'packaging_section': 'Упаковка:',
        'total_section': 'Итого:',
        'what_to_do': 'Что вы хотите сделать?',
        'continue_cart': 'Продолжить с этой корзиной',
        'new_order': 'Начать новый заказ',
        'menu_unavailable': 'Меню временно недоступно. Попробуйте позже.',
        'samsa_unavailable': 'В данный момент самса недоступна. Попробуйте позже.',
        'choose_samsa': 'Выберите самсу:',
        'hint_finish': 'Подсказка: После выбора самсы нажмите "Завершить заказ"',
        'error_occurred': 'Произошла ошибка. Попробуйте позже.',
        'price_label': 'Цена:',
        'in_cart': 'В корзине:',
        'add_to_cart': 'добавлена в корзину',
        'finish_with_samsa': 'Завершить с этой самсой',
        'back_to_menu': 'Назад к меню',
        'cart_empty': 'Корзина пуста!',
        'add_samsa_first': 'Добавьте самсу для оформления заказа.',
        'back_to_selection': 'Назад к выбору',
        'cart_section': 'Корзина:',
        'total_cost': 'Итого:',
        'now_choose_packaging': 'Теперь выберите упаковку:',
        'packaging_required': 'Упаковка обязательна для оформления заказа',
        'choose_packaging': 'Выберите упаковку для вашего заказа:',
        'back_to_cart': 'Назад к корзине',
        'added_to_cart': 'Добавлено:',
        'proceeding_to_order': 'Переходим к оформлению заказа...',
        'delivery_area': 'Доставка:',
        'enter_contact_details': 'Теперь введите ваше имя, телефон и адрес доставки в одном сообщении.',
        'contact_example': 'Например: Иван, +998901234567, ул. Навои 10, кв. 5',
        'choose_delivery_method': 'Выберите способ получения заказа:',
        'delivery_option': 'Доставка',
        'pickup_option': 'Самовывоз',
        'when_deliver': 'Когда доставить?',
        'asap': 'Как можно скорее',
        'specific_time': 'К конкретному времени',
        'enter_time': 'Введите время (например, 14:30):',
        'choose_payment': 'Выберите способ оплаты:',
        'cash_payment': 'Наличные',
        'card_payment': 'Оплатить по карте',
        'card_payment_details': 'Оплата картой',
        'amount_to_pay': 'Сумма к оплате:',
        'card_number': 'Номер карты:',
        'bank_info': 'Банк: UzCard, OFB',
        'payment_time_limit': 'У вас есть 10 минут на оплату!',
        'payment_instructions': 'После перевода отправьте в этот чат сумму цифрами.',
        'payment_confirmation': 'Сумма оплаты подтверждена!',
        'waiting_admin_confirmation': 'Ожидайте подтверждения от администратора.',
        'order_accepted': 'Ваш заказ принят! С вами скоро свяжутся.',
        'order_summary': 'Ваш заказ:',
        'samsa_items': 'Самса:',
        'packaging_items': 'Упаковка:',
        'sum_total': 'Сумма:',
        'name_field': 'Имя:',
        'phone_field': 'Телефон:',
        'address_field': 'Адрес:',
        'delivery_field': 'Доставка:',
        'time_field': 'Время:',
        'confirm_order': 'Подтвердить',
        'cancel_order': 'Отменить',
        'finish_order': 'Завершить заказ',
        'cart_button': 'Корзина',
        'cancel_order_button': 'Отменить заказ',
        'enter_name': 'Как вас зовут?',
        'enter_name_manually': 'Пожалуйста, напишите своё имя вручную (не используйте кнопки меню)',
        'name_example': 'Например: Иван',
        'name_too_short': 'Имя слишком короткое',
        'enter_full_name': 'Пожалуйста, введите полное имя.',
        'enter_phone': 'Введите ваш номер телефона',
        'enter_phone_manually': 'Пожалуйста, напишите номер вручную (не используйте кнопки меню)',
        'phone_example': 'Например: +998901234567 или 998901234567',
        'phone_too_short': 'Номер телефона слишком короткий',
        'enter_full_phone': 'Пожалуйста, введите полный номер телефона.',
        'enter_address': 'Введите адрес доставки',
        'enter_address_manually': 'Пожалуйста, напишите адрес вручную (не используйте кнопки меню)',
        'address_example': 'Например: ул. Навои 10, кв. 5',
        'address_too_short': 'Адрес слишком короткий',
        'enter_full_address': 'Пожалуйста, введите полный адрес доставки.',
        'delivery_zone': 'Зона доставки:',
        'choose_delivery_method_final': 'Выберите способ получения заказа:',
    },
    'uz': {
        'welcome': (
            'Assalomu alaykum!\n'
            'Samsariya – uy sharoitida pishirilgan somsa botiga xush kelibsiz.\n'
            '+998880009099'
        ),
        'off_hours_preorder': 'Hozir faoliyatimiz to‘xtagan, oldindan buyurtma bera olasiz',
        'about': 'Samsariya oila retsepti bo‘yicha, yog‘siz va qo‘shimchasiz tayyorlangan somsa.',
        'promo': (
            'Aksiya va yangiliklar:\n'
            '- Qovoqli somsa (fasliy)\n'
            '- Payme orqali to‘lovda 10% chegirma'
        ),
        'working_hours': 'Buyurtmalar 9:00–17:00 qabul qilinadi. Toshkent bo‘ylab 1–2 soat ichida yetkazib beramiz.',
        'payments': 'Naqd yoki Payme orqali (100% oldindan to‘lov, chegirma bilan).',
        'repeat_unavailable': 'Avvalgi buyurtmangiz yo‘q.',
        'ask_review': 'Fikr-mulohazangizni matn yoki ovozli xabar sifatida yuboring.',
        'thank_review': 'Rahмат! Fikringiz qabul qilindi.',
        'show_reviews': 'Mijozlar fiqrlari:',
        # buttons
        'btn_order':    '🛒 Buyurtma berish',
        'btn_reviews':  '💬 Sharhlar',
        'btn_about':    'ℹ️ Biz haqimizda',
        'btn_promo':    '🔥 Aksiyalar',
        'btn_hours':    '⏰ Ish vaqti',
        'btn_payments': '💳 To‘lov',
        'btn_repeat':   '🔁 Qayta buyurtma',
        'btn_language':'🌐 Til',
        'btn_help':     '❓ Yordam',
        'btn_back':     '◀️ Orqaga',
        'btn_contacts': '📞 Aloqa',
        'btn_leave_review': '📝 Fikr qoldirish',
        'lang_choice_ru': '🇷🇺 Rus tili',
        'lang_choice_uz': '🇺🇿 O\'zbek tili',
        'pieces_suffix': 'ta',
        # Order flow texts
        'cart_saved': 'Sizda saqlangan savat bor:',
        'samsa_section': 'Somsa:',
        'packaging_section': 'Qadoqlash:',
        'total_section': 'Jami:',
        'what_to_do': 'Nima qilmoqchisiz?',
        'continue_cart': 'Bu savat bilan davom etish',
        'new_order': 'Yangi buyurtma berish',
        'menu_unavailable': 'Menyu vaqtincha mavjud emas. Keyinroq urinib koʻring.',
        'samsa_unavailable': 'Hozir somsa mavjud emas. Keyinroq urinib koʻring.',
        'choose_samsa': 'Somsa tanlang:',
        'hint_finish': 'Maslahat: Somsa tanlaganingizdan keyin "Buyurtmani yakunlash" tugmasini bosing',
        'error_occurred': 'Xatolik yuz berdi. Keyinroq urinib koʻring.',
        'price_label': 'Narx:',
        'in_cart': 'Savatda:',
        'add_to_cart': 'savatga qoʻshildi',
        'finish_with_samsa': 'Bu somsa bilan yakunlash',
        'back_to_menu': 'Menyuga qaytish',
        'cart_empty': 'Savat boʻsh!',
        'add_samsa_first': 'Buyurtma berish uchun somsa qoʻshing.',
        'back_to_selection': 'Tanlovga qaytish',
        'cart_section': 'Savat:',
        'total_cost': 'Jami:',
        'now_choose_packaging': 'Endi qadoqlashni tanlang:',
        'packaging_required': 'Buyurtma berish uchun qadoqlash majburiy',
        'choose_packaging': 'Buyurtmangiz uchun qadoqlashni tanlang:',
        'back_to_cart': 'Savatga qaytish',
        'added_to_cart': 'Qoʻshildi:',
        'proceeding_to_order': 'Buyurtma berishga oʻtamiz...',
        'delivery_area': 'Yetkazib berish:',
        'enter_contact_details': 'Endi ismingiz, telefon raqamingiz va yetkazib berish manzilini bitta xabarda kiriting.',
        'contact_example': 'Masalan: Ivan, +998901234567, Navoi koʻchasi 10, kv. 5',
        'choose_delivery_method': 'Buyurtmani qanday olishni tanlang:',
        'delivery_option': 'Yetkazib berish',
        'pickup_option': 'Oʻz-oʻzidan olib ketish',
        'when_deliver': 'Qachon yetkazib berish kerak?',
        'asap': 'Imkon qadar tezroq',
        'specific_time': 'Muayyan vaqtga',
        'enter_time': 'Vaqtni kiriting (masalan, 14:30):',
        'choose_payment': 'Toʻlov usulini tanlang:',
        'cash_payment': 'Naqd pul',
        'card_payment': 'Karta orqali toʻlash',
        'card_payment_details': 'Karta orqali toʻlov',
        'amount_to_pay': 'Toʻlash summasi:',
        'card_number': 'Karta raqami:',
        'bank_info': 'Bank: UzCard, OFB',
        'payment_time_limit': 'Sizda toʻlov uchun 10 daqiqa bor!',
        'payment_instructions': 'Oʻtkazgandan keyin bu chatga summani raqamlar bilan yuboring.',
        'payment_confirmation': 'Toʻlov summasi tasdiqlandi!',
        'waiting_admin_confirmation': 'Administrator tasdigini kuting.',
        'order_accepted': 'Buyurtmangiz qabul qilindi! Tez orada siz bilan bogʻlanamiz.',
        'order_summary': 'Buyurtmangiz:',
        'samsa_items': 'Somsa:',
        'packaging_items': 'Qadoqlash:',
        'sum_total': 'Summa:',
        'name_field': 'Ism:',
        'phone_field': 'Telefon:',
        'address_field': 'Manzil:',
        'delivery_field': 'Yetkazib berish:',
        'time_field': 'Vaqt:',
        'confirm_order': 'Tasdiqlash',
        'cancel_order': 'Bekor qilish',
        'finish_order': 'Buyurtmani yakunlash',
        'cart_button': 'Savat',
        'cancel_order_button': 'Buyurtmani bekor qilish',
        'enter_name': 'Ismingiz nima?',
        'enter_name_manually': 'Iltimos, ismingizni qoʻlda yozing (menyu tugmalarini ishlatmang)',
        'name_example': 'Masalan: Ivan',
        'name_too_short': 'Ism juda qisqa',
        'enter_full_name': 'Iltimos, toʻliq ismni kiriting.',
        'enter_phone': 'Telefon raqamingizni kiriting',
        'enter_phone_manually': 'Iltimos, raqamni qoʻlda yozing (menyu tugmalarini ishlatmang)',
        'phone_example': 'Masalan: +998901234567 yoki 998901234567',
        'phone_too_short': 'Telefon raqami juda qisqa',
        'enter_full_phone': 'Iltimos, toʻliq telefon raqamini kiriting.',
        'enter_address': 'Yetkazib berish manzilini kiriting',
        'enter_address_manually': 'Iltimos, manzilni qoʻlda yozing (menyu tugmalarini ishlatmang)',
        'address_example': 'Masalan: Navoi koʻchasi 10, kv. 5',
        'address_too_short': 'Manzil juda qisqa',
        'enter_full_address': 'Iltimos, toʻliq yetkazib berish manzilini kiriting.',
        'delivery_zone': 'Yetkazib berish zonasi:',
        'choose_delivery_method_final': 'Buyurtmani qanday olishni tanlang:',
    }
}

async def init_bot_data(app):
    lang = 'ru'
    app.bot_data['lang'] = lang
    app.bot_data['texts'] = TEXTS[lang]
    
    # Try to get availability from MongoDB, fallback to local file
    try:
        if app.bot_data.get('mongodb_available', True):
            app.bot_data['avail'] = await get_availability_dict()
        else:
            # Fallback to local file
            app.bot_data['avail'] = load_local_availability()
    except Exception as e:
        print(f"⚠️ Error loading availability: {e}")
        # Fallback to local file
        app.bot_data['avail'] = load_local_availability()
    
    t = app.bot_data['texts']
    # build keyboards - 2 buttons per row layout
    main_keyboard = [
        [t['btn_order'], t['btn_contacts']],
        [t['btn_hours'], t['btn_promo']],
        [t['btn_reviews'], t['btn_leave_review']],
        [t['btn_help'], t['btn_language']],
    ]
    app.bot_data['keyb'] = {
        'main': ReplyKeyboardMarkup(main_keyboard, resize_keyboard=True),
        'back': ReplyKeyboardMarkup([[t['btn_back']]], resize_keyboard=True),
    }

def load_local_availability():
    """Load availability from local JSON file as fallback"""
    try:
        with open(AVAILABILITY_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, dict) and 'items' in data:
                return data['items']
            else:
                # Return default availability for all items
                from .catalog import ALL_KEYS
                return {key: True for key in ALL_KEYS}
    except (FileNotFoundError, json.JSONDecodeError):
        # Return default availability for all items
        from .catalog import ALL_KEYS
        return {key: True for key in ALL_KEYS}

async def set_availability_item(key: str, is_enabled: bool) -> None:
    col = get_availability_collection()
    await col.update_one({'_id': 'availability'}, {'$set': {f'items.{key}': bool(is_enabled)}})

async def get_availability() -> dict:
    return await get_availability_dict()

async def set_language(update, context: ContextTypes.DEFAULT_TYPE):
    kb = ReplyKeyboardMarkup([['ru', 'uz']], one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text('Выберите язык / Tilni tanlang', reply_markup=kb)

async def handle_language_choice(update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text
    if choice not in LANGUAGES:
        return await update.message.reply_text('Пожалуйста, выберите "ru" или "uz".')
    context.bot_data['lang'] = choice
    context.bot_data['texts'] = TEXTS[choice]
    # rebuild keyboards - 2 buttons per row layout
    t = context.bot_data['texts']
    main_keyboard = [
        [t['btn_order'], t['btn_contacts']],
        [t['btn_hours'], t['btn_promo']],
        [t['btn_reviews'], t['btn_leave_review']],
        [t['btn_help'], t['btn_language']],
    ]
    context.bot_data['keyb'] = {
        'main': ReplyKeyboardMarkup(main_keyboard, resize_keyboard=True),
        'back': ReplyKeyboardMarkup([[t['btn_back']]], resize_keyboard=True),
    }
    await main_menu(update, context)

async def help_command(update, context: ContextTypes.DEFAULT_TYPE):
    t = context.bot_data['texts']
    lang = context.bot_data.get('lang', 'ru')
    
    if lang == 'ru':
        help_text = """🤖 <b>Помощь по боту Samsariya</b>

<b>📱 Меню бота:</b>
🛒 <b>Сделать заказ</b> — Начать новый заказ самсы
📞 <b>Контакты</b> — Наши телефоны, адрес и время работы
⏰ <b>Время работы</b> — Когда мы принимаем заказы (9:00-17:00)
🔥 <b>Акции</b> — Текущие скидки и специальные предложения
💬 <b>Отзывы</b> — Читать отзывы других клиентов
📝 <b>Оставить отзыв</b> — Поделиться своим мнением
❓ <b>Помощь</b> — Эта справка
🌐 <b>Язык</b> — Переключить на русский/узбекский

<b>🛒 Как заказать:</b>
1️⃣ Нажмите "Сделать заказ"
2️⃣ Выберите самсу и количество
3️⃣ Добавьте упаковку (обязательно)
4️⃣ Укажите свои данные (имя, телефон, адрес)
5️⃣ Выберите способ получения
6️⃣ Выберите время доставки
7️⃣ Выберите способ оплаты
8️⃣ Подтвердите заказ

<b>📊 Статусы заказа:</b>
✅ <b>Принят</b> — Ваш заказ получен и обрабатывается
🔄 <b>В процессе</b> — Самса готовится
🍽️ <b>Готов</b> — Заказ готов к выдаче/доставке
✅ <b>Завершен</b> — Заказ доставлен/выдан
❌ <b>Отменен</b> — Заказ отменен

<b>💡 Полезные советы:</b>
• Заказы принимаем с 9:00 до 17:00
• Доставка по Ташкенту 1-2 часа
• Оплата наличными или картой
• Скидка 10% при оплате через Payme"""
    else:  # uz
        help_text = """🤖 <b>Samsariya bot yordami</b>

<b>📱 Bot menyusi:</b>
🛒 <b>Buyurtma berish</b> — Yangi somsa buyurtmasi
📞 <b>Aloqa</b> — Telefon raqamlarimiz, manzil va ish vaqti
⏰ <b>Ish vaqti</b> — Buyurtma qabul qilish vaqti (9:00-17:00)
🔥 <b>Aksiyalar</b> — Joriy chegirmalar va maxsus takliflar
💬 <b>Sharhlar</b> — Boshqa mijozlarning fikrlari
📝 <b>Sharh qoldirish</b> — O'z fikringizni bildiring
❓ <b>Yordam</b> — Bu yordam
🌐 <b>Til</b> — Rus/ozbek tiliga o'tish

<b>🛒 Qanday buyurtma berish:</b>
1️⃣ "Buyurtma berish"ni bosing
2️⃣ Somsa va miqdorni tanlang
3️⃣ Ompordagi qo'shing 
4️⃣ Ma'lumotlaringizni kiriting (ism, telefon, manzil)
5️⃣ Olish usulini tanlang
6️⃣ Yetkazib berish vaqtini tanlang
7️⃣ To'lov usulini tanlang
8️⃣ Buyurtmani tasdiqlang

<b>📊 Buyurtma holatlari:</b>
✅ <b>Qabul qilindi</b> — Buyurtmangiz qabul qilindi va qayta ishlanmoqda
🔄 <b>Jarayonda</b> — Somsa tayyorlanmoqda
🍽️ <b>Tayyor</b> — Buyurtma berish/etkazib berish uchun tayyor
✅ <b>Yakunlandi</b> — Buyurtma yetkazib berildi/berildi
❌ <b>Bekor qilindi</b> — Buyurtma bekor qilindi

<b>💡 Foydali maslahatlar:</b>
• Buyurtmalar 9:00-17:00 qabul qilinadi
• Toshkent bo'ylab 1-2 soat ichida yetkazib beramiz
• Naqd yoki karta orqali to'lov
• Payme orqali to'lovda 10% chegirma"""
    
    await update.message.reply_text(help_text, parse_mode='HTML', reply_markup=context.bot_data['keyb']['main'])

async def main_menu(update, context: ContextTypes.DEFAULT_TYPE):
    t = context.bot_data['texts']
    await update.message.reply_text(t['welcome'], reply_markup=context.bot_data['keyb']['main'])

def get_text(context, key):
    """Get localized text by key"""
    return context.bot_data['texts'].get(key, key)

def get_display_name(context, item_key):
    """Get localized display name for item"""
    lang = context.bot_data.get('lang', 'ru')
    from .catalog import DISPLAY_NAMES
    return DISPLAY_NAMES[lang].get(item_key, item_key)

def get_short_name(context, item_key):
    """Get localized short name for item"""
    lang = context.bot_data.get('lang', 'ru')
    from .catalog import SHORT_NAMES
    return SHORT_NAMES[lang].get(item_key, item_key)


def get_current_language(context) -> str:
    """Return current language code (ru/uz)."""
    return context.bot_data.get('lang', 'ru')


def get_lang_text(context, ru_text: str, uz_text: str) -> str:
    """Return text based on active language."""
    return ru_text if get_current_language(context) == 'ru' else uz_text
