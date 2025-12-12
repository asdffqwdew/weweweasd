import logging
import json
import requests
import time
import socket
import re
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ChatMember
)
from telegram.ext import (
    Updater,
    CommandHandler,
    CallbackQueryHandler,
    CallbackContext
)

# Настройкиа
TOKEN = "8335606271:AAGWSY4BpCKwZ9UPHUVcY8nPudjjYbMLodk"
CHANNEL_LINK = "https://t.me/+QeSLygupCgkxNDRi"  # Канал
GROUP_LINK = "https://t.me/+TlNJqaczMRUwYzcy"     # Группа

# ID каналов (из вашего сообщения)
CHANNEL_ID = -1003323875997  # Канал
GROUP_ID = -1003467838280    # Группа

# Настройки платежной системы @send
SEND_API_TOKEN = "498452:AAx1Yu4snuXoSmE43q4oaeyHhcyRSVh11NF"
# Используем домен https://pay.crypt.bot/api как указано
CRYPTO_BOT_API_URL = "https://pay.crypt.bot/api"
# Формируем URL для API
SEND_CREATE_INVOICE_URL = f"{CRYPTO_BOT_API_URL}/createInvoice"
SEND_CHECK_INVOICE_URL = f"{CRYPTO_BOT_API_URL}/getInvoices"

# Ссылка на функции чита
CHEAT_FUNCTIONS_LINK = "https://t.me/c/3323875997/6"

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Функция для очистки текста от символов Markdown
def clean_markdown_text(text: str) -> str:
    """Очищает текст от символов Markdown, которые могут вызвать ошибку парсинга"""
    if not text:
        return ""
    # Удаляем все специальные символы Markdown
    text = re.sub(r'[*_`\[\]~>#\+\-=|{}\.!]', ' ', text)
    # Заменяем множественные пробелы на один
    text = re.sub(r'\s+', ' ', text)
    # Обрезаем пробелы по краям
    return text.strip()

# Функция для безопасной отправки сообщений без Markdown ошибок
def safe_reply_text(message, text: str, **kwargs):
    """Безопасно отправляет текст, убирая Markdown при ошибках"""
    try:
        # Сначала пробуем с Markdown
        return message.reply_text(text, parse_mode='Markdown', **kwargs)
    except Exception as e:
        if "Can't parse entities" in str(e):
            logger.warning(f"Markdown ошибка, отправляю как обычный текст: {e}")
            # Убираем Markdown и отправляем снова
            clean_text = clean_markdown_text(text)
            return message.reply_text(clean_text, parse_mode=None, **kwargs)
        else:
            raise

# Функция для конвертации USD в USDT (по курсу ~1:1 для простоты)
def usd_to_usdt(usd_amount: float) -> float:
    """Конвертирует USD в USDT"""
    return usd_amount  # Простая конвертация 1:1

# Функция для удаления предыдущего сообщения
def delete_previous_message(update: Update, context: CallbackContext):
    """Удаляет предыдущее сообщение бота"""
    if 'last_message_id' in context.user_data and 'last_chat_id' in context.user_data:
        try:
            context.bot.delete_message(
                chat_id=context.user_data['last_chat_id'],
                message_id=context.user_data['last_message_id']
            )
        except Exception as e:
            logger.error(f"Ошибка при удалении сообщения: {e}")

# Функция для сохранения ID последнего сообщения
def save_message_info(message, context: CallbackContext):
    """Сохраняет информацию о последнем отправленном сообщении"""
    context.user_data['last_message_id'] = message.message_id
    context.user_data['last_chat_id'] = message.chat_id

# Функция для создания счета через API
def create_invoice(user_id: int, amount: float, description: str, platform: str, tariff: str) -> dict:
    """Создает счет для оплаты"""
    try:
        # Конвертируем USD в USDT
        usdt_amount = usd_to_usdt(amount)
        
        # Очищаем описание от символов Markdown
        clean_description = clean_markdown_text(f"VisionWare Cheat for {platform} - {tariff}")
        
        # Формируем данные для запроса для Crypto Bot API
        payload = {
            "asset": "USDT",  # Используем USDT
            "amount": str(usdt_amount),
            "description": clean_description,
            "hidden_message": f"Platform: {platform}, Tariff: {tariff}, UserID: {user_id}",
            "paid_btn_name": "viewItem",
            "paid_btn_url": "https://t.me/OnWareBot",
            "payload": f"visionware_{user_id}_{int(time.time())}",
            "allow_comments": False,
            "allow_anonymous": False
        }
        
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Crypto-Pay-API-Token': SEND_API_TOKEN
        }
        
        logger.info(f"Отправка запроса на создание счета: {json.dumps(payload, ensure_ascii=False)}")
        logger.info(f"URL: {SEND_CREATE_INVOICE_URL}")
        
        # Отправляем запрос к API
        response = requests.post(
            SEND_CREATE_INVOICE_URL, 
            json=payload, 
            headers=headers, 
            timeout=30
        )
        
        logger.info(f"Ответ от API: статус {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            logger.info(f"Данные ответа: {json.dumps(data, ensure_ascii=False)}")
            
            if data.get('ok'):
                result = data.get('result', {})
                # Получаем ссылку на оплату
                invoice_link = result.get('pay_url') or result.get('bot_invoice_url') or result.get('invoice_url')
                invoice_id = result.get('invoice_id')
                
                logger.info(f"Счет создан: ID={invoice_id}, ссылка={invoice_link}")
                
                return {
                    'success': True,
                    'invoice_link': invoice_link,
                    'invoice_id': invoice_id,
                    'bot_invoice_url': result.get('bot_invoice_url')
                }
            else:
                error_msg = data.get('error', {}).get('name', 'Unknown error')
                logger.error(f"Ошибка создания счета: {error_msg}")
                return {'success': False, 'error': error_msg}
        else:
            error_text = response.text[:200] if response.text else "No response text"
            logger.error(f"HTTP ошибка {response.status_code}: {error_text}")
            return {'success': False, 'error': f'HTTP {response.status_code}: {error_text}'}
            
    except socket.gaierror as e:
        logger.error(f"Ошибка DNS/сети: {e}")
        return {'success': False, 'error': f'Ошибка сети: {e}. Проверьте подключение к интернету.'}
    except requests.exceptions.Timeout:
        logger.error("Таймаут при подключении к API")
        return {'success': False, 'error': 'Таймаут подключения к платежной системе'}
    except Exception as e:
        logger.error(f"Ошибка создания счета: {e}")
        return {'success': False, 'error': str(e)}

# Функция для проверки статуса оплаты через API
def check_invoice_status(invoice_id: str) -> dict:
    """Проверяет статус счета через API"""
    try:
        if not invoice_id:
            return {'success': False, 'error': 'Invoice ID not provided'}
        
        logger.info(f"Проверка статуса счета: {invoice_id}")
        
        # Основной метод проверки - получение всех счетов и фильтрация
        payload = {"count": 50, "offset": 0}
        
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Crypto-Pay-API-Token': SEND_API_TOKEN
        }
        
        response = requests.post(
            SEND_CHECK_INVOICE_URL, 
            json=payload, 
            headers=headers, 
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('ok'):
                items = data.get('result', {}).get('items', [])
                
                # Ищем счет по ID
                for item in items:
                    if str(item.get('invoice_id')) == str(invoice_id):
                        status = item.get('status', 'unknown')
                        
                        logger.info(f"Счет найден! ID={invoice_id}, статус={status}")
                        
                        # Маппинг статусов
                        status_map = {
                            'active': 'pending',
                            'paid': 'paid',
                            'expired': 'expired'
                        }
                        
                        mapped_status = status_map.get(status, status)
                        
                        return {
                            'success': True,
                            'status': mapped_status,
                            'paid': mapped_status == 'paid',
                            'invoice_data': item
                        }
                
                logger.warning(f"Счет {invoice_id} не найден в списке счетов")
                return {'success': False, 'error': 'Invoice not found'}
            else:
                error_msg = data.get('error', {}).get('name', 'Unknown error')
                logger.error(f"Ошибка API при проверке: {error_msg}")
                return {'success': False, 'error': error_msg}
        else:
            logger.error(f"HTTP ошибка при проверке: {response.status_code} - {response.text[:200]}")
            return {'success': False, 'error': f'HTTP {response.status_code}'}
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка сети при проверке статуса: {e}")
        return {'success': False, 'error': f'Ошибка сети: {e}'}
    except Exception as e:
        logger.error(f"Ошибка проверки статуса счета: {e}")
        return {'success': False, 'error': str(e)}

# Проверка подписки на канал и группу
def check_subscription(user_id: int, context: CallbackContext) -> bool:
    try:
        # Проверяем подписку на канал
        try:
            channel_member = context.bot.get_chat_member(
                chat_id=CHANNEL_ID,
                user_id=user_id
            )
            channel_status = channel_member.status in ['member', 'administrator', 'creator', 'restricted']
            logger.info(f"Статус канала для пользователя {user_id}: {channel_member.status}")
        except Exception as e:
            logger.error(f"Ошибка проверки канала: {e}")
            channel_status = False
        
        # Проверяем подписку на группу
        try:
            group_member = context.bot.get_chat_member(
                chat_id=GROUP_ID,
                user_id=user_id
            )
            group_status = group_member.status in ['member', 'administrator', 'creator', 'restricted']
            logger.info(f"Статус группы для пользователя {user_id}: {group_member.status}")
        except Exception as e:
            logger.error(f"Ошибка проверки группы: {e}")
            group_status = False
        
        return channel_status and group_status
    except Exception as e:
        logger.error(f"Общая ошибка проверки подписки: {e}")
        return False

# Команда /start
def start(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    logger.info(f"Пользователь {user_id} запустил бота")
    
    # Проверяем подписку
    if not check_subscription(user_id, context):
        # Кнопки для обязательной подписки
        keyboard = [
            [InlineKeyboardButton("🎮 VisionWare | So2", url=CHANNEL_LINK)],
            [InlineKeyboardButton("🚦 VisionWare traffic", url=GROUP_LINK)],
            [InlineKeyboardButton("✅ Проверить подписку", callback_data="check_subscription")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = update.message.reply_text(
            "🔒 Для использования бота необходимо:\n\n"
            "1️⃣ 🎮 Подписаться на VisionWare | So2\n"
            "2️⃣ 🚦 Вступить в VisionWare traffic\n\n"
            "📌 После подписки нажмите кнопку проверки ⤵️",
            reply_markup=reply_markup,
            parse_mode=None
        )
        save_message_info(message, context)
        return
    
    # Если подписан - показываем главное меню
    show_main_menu(update, context)

# Показ главного меню (после успешной подписки)
def show_main_menu(update: Update, context: CallbackContext) -> None:
    # Удаляем предыдущее сообщение
    if update.callback_query:
        delete_previous_message(update, context)
    
    keyboard = [
        [InlineKeyboardButton("🛒 Купить чит", callback_data="buy_cheat")],
        [InlineKeyboardButton("📊 Функции чита", url=CHEAT_FUNCTIONS_LINK)],
        [InlineKeyboardButton("⭐ Отзывы", url="https://t.me/VisionWar")],
        [InlineKeyboardButton("🏪 О магазине", callback_data="about_store")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Отправляем фото с меню
    try:
        with open('menu.png', 'rb') as photo:
            if update.callback_query:
                message = update.callback_query.message.reply_photo(
                    photo=photo,
                    caption="💎 VisionWare - приватные читы\n\n"
                           "🧠 Здесь вы можете приобрести лучшие читы по самой выгодной цене.\n\n"
                           "✨ Также вы найдёте подробную информацию о магазине, реальные отзывы клиентов и сможете следить за обновлениями.\n\n"
                           "📣 Следите за новостями в нашем канале - @prhdVis",
                    reply_markup=reply_markup,
                    parse_mode=None
                )
            else:
                message = update.message.reply_photo(
                    photo=photo,
                    caption="💎 VisionWare - приватные читы\n\n"
                           "🧠 Здесь вы можете приобрести лучшие читы по самой выгодной цене.\n\n"
                           "✨ Также вы найдёте подробную информацию о магазине, реальные отзывы клиентов и сможете следить за обновлениями.\n\n"
                           "📣 Следите за новостями в нашем канале - @prhdVis",
                    reply_markup=reply_markup,
                    parse_mode=None
                )
    except FileNotFoundError:
        if update.callback_query:
            message = update.callback_query.message.reply_text(
                "💎 VisionWare - приватные читы\n\n"
                "🧠 Здесь вы можете приобрести лучшие читы по самой выгодной цене.\n\n"
                "✨ Также вы найдёте подробную информацию о магазине, реальные отзывы клиентов и сможете следить за обновлениями.\n\n"
                "📣 Следите за новостями в нашем канале - @prhdVis",
                reply_markup=reply_markup,
                parse_mode=None
            )
        else:
            message = update.message.reply_text(
                "💎 VisionWare - приватные читы\n\n"
                "🧠 Здесь вы можете приобрести лучшие читы по самой выгодной цене.\n\n"
                "✨ Также вы найдёте подробную информацию о магазине, реальные отзывы клиентов и сможете следить за обновлениями.\n\n"
                "📣 Следите за новостями в нашем канале -  @prhdVis",
                reply_markup=reply_markup,
                parse_mode=None
            )
    
    save_message_info(message, context)

# Обработка нажатий кнопок
def button_handler(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()
    
    user_id = query.from_user.id
    
    # Проверяем подписку для всех действий кроме проверки подписки
    if query.data != "check_subscription" and not check_subscription(user_id, context):
        # Кнопки для обязательной подписки
        keyboard = [
            [InlineKeyboardButton("🎮 VisionWare | So2", url=CHANNEL_LINK)],
            [InlineKeyboardButton("🚦 VisionWare traffic", url=GROUP_LINK)],
            [InlineKeyboardButton("✅ Проверить подписку", callback_data="check_subscription")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = query.edit_message_text(
            "🔒 Для использования бота необходимо:\n\n"
            "1️⃣ 🎮 Подписаться на VisionWare | So2\n"
            "2️⃣ 🚦 Вступить в VisionWare traffic\n\n"
            "📌 После подписки нажмите кнопку проверки ⤵️",
            reply_markup=reply_markup,
            parse_mode=None
        )
        save_message_info(message, context)
        return
    
    # Обработка различных кнопок
    if query.data == "check_subscription":
        if check_subscription(user_id, context):
            show_main_menu(update, context)
        else:
            keyboard = [
                [InlineKeyboardButton("🎮 VisionWare | So2", url=CHANNEL_LINK)],
                [InlineKeyboardButton("🚦 VisionWare traffic", url=GROUP_LINK)],
                [InlineKeyboardButton("✅ Проверить подписку", callback_data="check_subscription")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            message = query.edit_message_text(
                "❌ Вы не подписаны на все необходимые каналы!\n\n"
                "📌 Пожалуйста, подпишитесь и нажмите кнопку проверки еще раз:",
                reply_markup=reply_markup,
                parse_mode=None
            )
            save_message_info(message, context)
    
    elif query.data == "buy_cheat":
        select_platform(update, context)
    
    elif query.data == "about_store":
        about_store(update, context)
    
    elif query.data in ["ios", "pc", "android"]:
        context.user_data["platform"] = query.data
        select_currency(update, context)
    
    elif query.data == "usd":
        select_tariff(update, context)
    
    elif query.data in ["7_days", "30_days", "forever"]:
        context.user_data["tariff"] = query.data
        process_payment(update, context)
    
    elif query.data == "back_to_main":
        show_main_menu(update, context)
    
    elif query.data == "check_payment":
        check_payment_status(update, context)

# Выбор платформы
def select_platform(update: Update, context: CallbackContext) -> None:
    delete_previous_message(update, context)
    
    keyboard = [
        [InlineKeyboardButton("📱 iOS", callback_data="ios")],
        [InlineKeyboardButton("💻 PC", callback_data="pc")],
        [InlineKeyboardButton("🤖 Android", callback_data="android")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        with open('menu.png', 'rb') as photo:
            message = update.callback_query.message.reply_photo(
                photo=photo,
                caption="🛒 Выберите платформу",
                reply_markup=reply_markup,
                parse_mode=None
            )
    except FileNotFoundError:
        message = update.callback_query.message.reply_text(
            "🛒 Выберите платформу",
            reply_markup=reply_markup,
            parse_mode=None
        )
    
    save_message_info(message, context)

# Выбор валюты
def select_currency(update: Update, context: CallbackContext) -> None:
    delete_previous_message(update, context)
    
    keyboard = [
        [InlineKeyboardButton("💵 USDT ", callback_data="usd")],
        [InlineKeyboardButton("💰 Голда", url="https://t.me/+E6JNAt-Ell5kZjMy")],
        [InlineKeyboardButton("⭐ Звезды", url="https://t.me/+nPXqLTvSddZmYzc6")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        with open('menu.png', 'rb') as photo:
            message = update.callback_query.message.reply_photo(
                photo=photo,
                caption="💰 Выберите валюту\n\n",
                reply_markup=reply_markup,
                parse_mode=None
            )
    except FileNotFoundError:
        message = update.callback_query.message.reply_text(
            "💰 Выберите валюту\n\n",
            reply_markup=reply_markup,
            parse_mode=None
        )
    
    save_message_info(message, context)

# Выбор тарифа (только для USD)
def select_tariff(update: Update, context: CallbackContext) -> None:
    delete_previous_message(update, context)
    
    keyboard = [
        [InlineKeyboardButton("📅 7 дней - 4.5 USDT", callback_data="7_days")],
        [InlineKeyboardButton("📅 30 дней - 7 USDT", callback_data="30_days")],
        [InlineKeyboardButton("🎯 Навсегда - 10 USDT", callback_data="forever")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        with open('menu.png', 'rb') as photo:
            message = update.callback_query.message.reply_photo(
                photo=photo,
                caption="📊 Выберите тариф\n\n",
                reply_markup=reply_markup,
                parse_mode=None
            )
    except FileNotFoundError:
        message = update.callback_query.message.reply_text(
            "📊 Выберите тариф\n\n"
            "📅 7 дней - 4.5 USDT\n"
            "📅 30 дней - 7 USDT\n"
            "🎯 Навсегда - 10 USDT\n\n"
            "💡 Оплата принимается в криптовалюте USDT",
            reply_markup=reply_markup,
            parse_mode=None
        )
    
    save_message_info(message, context)

# О магазине
def about_store(update: Update, context: CallbackContext) -> None:
    delete_previous_message(update, context)
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        with open('menu.png', 'rb') as photo:
            message = update.callback_query.message.reply_photo(
                photo=photo,
                caption="🏪 О магазине VisionWare\n\n"
                       "✨ Добро пожаловать в наш официальный магазин!\n\n"
                       "🔹 Мгновенная доставка — все ключи и инструкции выдаются сразу после покупки.\n"
                       "🔹 Поддержка 24/7 — оперативно решаем любые вопросы, всегда на связи.\n"
                       "🔹 Надёжность — сотни довольных покупателей и реальных отзывов.\n\n"
                       "💰 Мы ценим каждого клиента.\n"
                       "📦 Следите за обновлениями — мы регулярно добавляем новые продукты и функции!\n\n"
                       "📣 Наш Telegram-канал: @prhdVis\n"
                       "✉️ Поддержка: @fucksekirov",
                reply_markup=reply_markup,
                parse_mode=None
            )
    except FileNotFoundError:
        message = update.callback_query.message.reply_text(
            "🏪 О магазине VisionWare\n\n"
            "✨ Добро пожаловать в наш официальный магазин!\n\n"
            "🔹 Мгновенная доставка — все ключи и инструкции выдаются сразу после покупки.\n"
            "🔹 Поддержка 24/7 — оперативно решаем любые вопросы, всегда на связи.\n"
            "🔹 Надёжность — сотни довольных покупателей и реальных отзывов.\n\n"
            "💰 Мы ценим каждого клиента.\n"
            "📦 Следите за обновлениями — мы регулярно добавляем новые продукты и функции!\n\n"
            "📣 Наш Telegram-канал: @prhdVis\n"
            "✉️ Поддержка: @fucksekirov",
            reply_markup=reply_markup,
            parse_mode=None
        )
    
    save_message_info(message, context)

# Обработка оплаты
def process_payment(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()
    
    delete_previous_message(update, context)
    
    # Тарифы и цены
    tariff_prices = {
        "7_days": {"name": "7 дней", "price": 4.5},
        "30_days": {"name": "30 дней", "price": 7.0},
        "forever": {"name": "Навсегда", "price": 10.0}
    }
    
    # Получаем информацию о выбранном тарифе
    tariff = context.user_data.get("tariff", "")
    platform = context.user_data.get("platform", "")
    tariff_info = tariff_prices.get(tariff, {})
    
    if not tariff_info:
        query.message.reply_text("❌ Ошибка: тариф не выбран")
        return
    
    # Создаем счет через API
    user_id = query.from_user.id
    description = f"Чит VisionWare для {platform} - {tariff_info['name']}"
    
    logger.info(f"Создание счета для пользователя {user_id}: {description} - {tariff_info['price']}$")
    
    invoice_result = create_invoice(
        user_id=user_id,
        amount=tariff_info['price'],
        description=description,
        platform=platform,
        tariff=tariff_info['name']
    )
    
    if invoice_result['success']:
        # Сохраняем информацию о счете
        context.user_data['invoice_id'] = invoice_result.get('invoice_id')
        context.user_data['invoice_link'] = invoice_result.get('invoice_link') or invoice_result.get('bot_invoice_url')
        context.user_data['last_invoice_time'] = time.time()
        
        # Используем доступную ссылку
        payment_link = invoice_result.get('invoice_link') or invoice_result.get('bot_invoice_url') or "#"
        
        keyboard = [
            [InlineKeyboardButton("💳 Оплатить счет", url=payment_link)],
            [InlineKeyboardButton("✅ Проверить оплату", callback_data="check_payment")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = safe_reply_text(
            query.message,
            f"💳 Счет на оплату сформирован!\n\n"
            f"📋 Детали заказа:\n"
            f"• Платформа: {platform}\n"
            f"• Тариф: {tariff_info['name']}\n"
            f"• Цена: {tariff_info['price']} USDT\n\n"
            f"⏳ Счет действителен 15 минут\n"
            f"✅ После оплаты нажмите кнопку проверки оплаты\n\n"
            f"💡 Оплата производится криптовалютой USDT через Crypto Bot",
            reply_markup=reply_markup
        )
    else:
        # Если не удалось создать счет через API, показываем альтернативный вариант
        logger.error(f"Ошибка создания счета: {invoice_result.get('error')}")
        
        keyboard = [
            [InlineKeyboardButton("📞 Связаться с поддержкой", url="https://t.me/fucksekirov")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        error_msg = invoice_result.get('error', 'Неизвестная ошибка')
        message = safe_reply_text(
            query.message,
            f"❌ Не удалось сформировать счет автоматически\n\n"
            f"⚠️ Ошибка: {error_msg}\n\n"
            f"📋 Детали заказа:\n"
            f"• Платформа: {platform}\n"
            f"• Тариф: {tariff_info['name']}\n"
            f"• Цена: {tariff_info['price']} USDT\n\n"
            f"📞 Для ручной оплаты свяжитесь с поддержкой: @fucksekirov",
            reply_markup=reply_markup
        )
    
    save_message_info(message, context)

# Проверка статуса оплаты
def check_payment_status(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()
    
    invoice_id = context.user_data.get('invoice_id')
    
    if not invoice_id:
        message = safe_reply_text(
            query.message,
            "❌ Ошибка: Счет не найден. Пожалуйста, создайте новый заказ."
        )
        save_message_info(message, context)
        return
    
    # Проверяем статус счета через API
    logger.info(f"Проверка статуса счета {invoice_id}")
    status_result = check_invoice_status(invoice_id)
    
    if not status_result['success']:
        # Ошибка при проверке статуса
        keyboard = [
            [InlineKeyboardButton("🔄 Повторить проверку", callback_data="check_payment")],
            [InlineKeyboardButton("📞 Поддержка", url="https://t.me/fucksekirov")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        error_msg = status_result.get('error', 'Неизвестная ошибка')
        message = safe_reply_text(
            query.message,
            f"⚠️ Не удалось проверить статус оплаты\n\n"
            f"Ошибка: {error_msg}\n"
            f"Пожалуйста, попробуйте еще раз через минуту.\n"
            f"Если проблема сохраняется, свяжитесь с поддержкой.",
            reply_markup=reply_markup
        )
    
    elif status_result['paid']:
        # Оплата прошла успешно!
        keyboard = [
            [InlineKeyboardButton("📦 Получить товар", url="https://t.me/OnWareBot")],
            [InlineKeyboardButton("🏠 В главное меню", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Получаем информацию о заказе
        platform = context.user_data.get("platform", "")
        tariff = context.user_data.get("tariff", "")
        
        message = safe_reply_text(
            query.message,
            f"✅ Оплата успешно подтверждена!\n\n"
            f"🎉 Поздравляем с покупкой!\n\n"
            f"📋 Ваш заказ:\n"
            f"• Чит: VisionWare\n"
            f"• Платформа: {platform}\n"
            f"• Тариф: {tariff}\n\n"
            f"📦 Для получения товара обратитесь в: @OnWareBot\n"
            f"📞 Техническая поддержка: @fucksekirov\n\n"
            f"✨ Спасибо за покупку!",
            reply_markup=reply_markup
        )
        
        # Очищаем данные о счете после успешной оплаты
        if 'invoice_id' in context.user_data:
            del context.user_data['invoice_id']
        if 'invoice_link' in context.user_data:
            del context.user_data['invoice_link']
    
    else:
        # Оплата еще не прошла
        status_text = status_result.get('status', 'unknown')
        status_messages = {
            'pending': "⏳ Ожидание оплаты\n\nСчет ожидает оплаты. Пожалуйста, произведите оплату.",
            'active': "⏳ Счет активен\n\nСчет ожидает оплаты. Пожалуйста, произведите оплату.",
            'expired': "❌ Счет просрочен\n\nСрок действия счета истек. Пожалуйста, создайте новый заказ.",
            'cancelled': "❌ Оплата отменена\n\nСчет был отменен. Пожалуйста, создайте новый заказ.",
            'failed': "❌ Ошибка оплаты\n\nПри оплате произошла ошибка. Пожалуйста, попробуйте еще раз.",
        }
        
        message_text = status_messages.get(status_text, 
            f"⚠️ Статус оплаты: {status_text}\n\nОплата еще не подтверждена.")
        
        keyboard = [
            [InlineKeyboardButton("🔄 Проверить еще раз", callback_data="check_payment")],
            [InlineKeyboardButton("💳 Оплатить", url=context.user_data.get('invoice_link', ''))],
            [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = safe_reply_text(
            query.message,
            f"{message_text}\n\n"
            f"📋 Детали заказа:\n"
            f"• Платформа: {context.user_data.get('platform', 'Не выбрана')}\n"
            f"• Тариф: {context.user_data.get('tariff', 'Не выбран')}\n\n"
            f"💡 Если вы уже оплатили, подождите несколько минут и проверьте снова.",
            reply_markup=reply_markup
        )
    
    save_message_info(message, context)

# Основная функция
def main() -> None:
    # Создаем updater и передаем токен
    updater = Updater(TOKEN, use_context=True)
    
    # Получаем диспетчер для регистрации обработчиков
    dp = updater.dispatcher
    
    # Обработчики команд
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(button_handler))
    
    # Запуск бота
    updater.start_polling()
    
    # Выводим информацию для отладки
    logger.info(f"Бот запущен")
    logger.info(f"ID канала: {CHANNEL_ID}")
    logger.info(f"ID группы: {GROUP_ID}")
    logger.info(f"Платежная система: Crypto Bot API")
    logger.info(f"API URL: {CRYPTO_BOT_API_URL}")
    logger.info(f"Ссылка на функции чита: {CHEAT_FUNCTIONS_LINK}")
    
    updater.idle()

if __name__ == '__main__':
    main()