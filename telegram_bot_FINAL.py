#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram бот для персональных сказок - ИСПРАВЛЕННАЯ ВЕРСИЯ
✅ Исправлено дублирование уведомлений админу
✅ Убраны шумные логи httpx
✅ Добавлена дедупликация уведомлений по order_id
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    CallbackQueryHandler, ContextTypes, filters, ConversationHandler
)
import os
import json
import logging
import traceback
from telegram.request import HTTPXRequest

# ✅ ПАТЧ: Отключаем шумные логи httpx
logging.getLogger("httpx").setLevel(logging.WARNING)

# ✅ ПАТЧ СТАБИЛЬНОСТИ: Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ✅ ПАТЧ: Постоянная клавиатура для удобства пользователей
def get_main_keyboard():
    """Возвращает постоянную клавиатуру с основными кнопками"""
    keyboard = [
        [KeyboardButton("🏠 Главное меню"), KeyboardButton("⭐ Создать сказку")],
        [KeyboardButton("📚 Примеры"), KeyboardButton("📞 Поддержка")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# Импортируем модули
from generate_storybook_v2 import create_storybook_v2
from payment import create_payment, is_payment_successful
from database import db

# 📊 АНАЛИТИКА: Счетчики событий
analytics_cache = {
    'start': 0,
    'show_examples': 0, 
    'how_it_works': 0,
    'create_story': 0,
    'theme_chosen': 0,
    'gender_chosen': 0,
    'name_entered': 0,
    'age_entered': 0,
    'photo_uploaded': 0,
    'photo_skipped': 0,
    'payment_created': 0,
    'payment_completed': 0
}

# ✅ ПАТЧ: Кеш отправленных уведомлений админу (чтобы не дублировать)
notified_orders = set()

def log_event(event_name, user_id=None):
    """Логирование события для аналитики"""
    analytics_cache[event_name] = analytics_cache.get(event_name, 0) + 1
    logger.info(f"📊 ANALYTICS: {event_name} | user={user_id}")


# НАСТРОЙКИ
BOT_TOKEN = os.environ.get("BOT_TOKEN")
BOT_USERNAME = os.environ.get("BOT_USERNAME", "Sefirum_storybook_bot")  # Username бота без @

# YooKassa (из переменных окружения)
YOOKASSA_SHOP_ID = os.environ.get("YOOKASSA_SHOP_ID", "")
YOOKASSA_SECRET_KEY = os.environ.get("YOOKASSA_SECRET_KEY", "")
PAYMENT_ENABLED = bool(YOOKASSA_SHOP_ID and YOOKASSA_SECRET_KEY)

# Админ для статистики
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))  # Укажи свой user_id

# Цена
# Цены
BOOK_PRICE_BASE = 290    # Базовая версия
BOOK_PRICE_PREMIUM = 390 # Премиум с анализом фото

# 🎁 БЕСПЛАТНЫЕ КРЕДИТЫ ДЛЯ КОМПЕНСАЦИИ
# Формат: {user_id: количество_бесплатных_книг}
FREE_CREDITS = {
    380684465: 1,   # Клиент 1 - 1 бесплатная книга
    1050991384: 1,  # Клиент 2 - 1 бесплатная книга  
    943674820: 1,   # Клиент 3 - 1 бесплатная книга
    5120925074: 1   # Клиент 4 - 1 бесплатная книга (добавлен 30.01.2026)
}

# ♾️ ТЕСТОВЫЕ АККАУНТЫ С НЕОГРАНИЧЕННЫМИ БЕСПЛАТНЫМИ КНИГАМИ
TEST_UNLIMITED_ACCOUNTS = [
    610820340  # Дима - тестирование (неограниченно)
]

# Состояния разговора
CHOOSING_THEME, CHOOSING_GENDER, GETTING_NAME, GETTING_AGE, CHOOSING_VERSION, GETTING_PHOTO, PAYMENT = range(7)


def decline_name_accusative(name, gender):
    """Склоняет имя в винительный падеж"""
    name_lower = name.lower()
    
    if name_lower.endswith('а') or name_lower.endswith('я'):
        if name_lower.endswith('а'):
            return name[:-1] + 'у'
        else:
            return name[:-1] + 'ю'
    
    if gender == "boy":
        if name_lower.endswith('й'):
            return name[:-1] + 'я'
        elif name_lower.endswith('ь'):
            return name[:-1] + 'я'
        else:
            return name + 'а'
    
    return name


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало работы бота - КРАСИВОЕ ПРИВЕТСТВИЕ"""
    
    # ✅ ПАТЧ: Останавливаем старые jobs проверки оплаты если есть
    payment_id = context.user_data.get('payment_id')
    if payment_id:
        job_name = f"payment_{payment_id}"
        current_jobs = context.job_queue.get_jobs_by_name(job_name)
        for job in current_jobs:
            job.schedule_removal()
            logger.info(f"⏹️ Остановлен job проверки платежа {payment_id} при /start")
    
    # ✅ ПАТЧ: Очищаем user_data для нового флоу
    context.user_data.clear()
    
    # Регистрируем пользователя в БД
    user = update.effective_user
    db.add_user(user.id, user.username, user.first_name, user.last_name)
    log_event('start', user.id)
    
    # Кнопки - ПО ОДНОЙ В РЯД!
    keyboard = [
        [InlineKeyboardButton("⭐ Создать сказку", callback_data="create_story")],
        [InlineKeyboardButton("📚 Посмотреть примеры", callback_data="show_examples")],
        [InlineKeyboardButton("❓ Как это работает?", callback_data="how_it_works")],
        [InlineKeyboardButton("📞 Поддержка", callback_data="support")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # ✅ ПАТЧ: Постоянная клавиатура внизу экрана
    main_keyboard = get_main_keyboard()
    
    # Отправляем welcome картинку С КНОПКАМИ
    welcome_path = 'welcome.jpg'
    if os.path.exists(welcome_path):
        with open(welcome_path, 'rb') as photo:
            await update.message.reply_photo(
                photo=photo,
                caption=(
                    "✨ *Персональная сказка про вашего ребёнка!*\n\n"
                    "Я создам красочную книгу с AI-иллюстрациями Disney/Pixar качества, "
                    "где ваш малыш — главный герой волшебного приключения!\n\n"
                    "📖 *Что вы получите:*\n"
                    "• 10 страниц с иллюстрациями\n"
                    "• 8 увлекательных тем на выбор\n"
                    "• Персонаж похож на вашего ребёнка\n"
                    "• Профессиональное качество\n"
                    "• PDF файл для печати\n\n"
                    f"💰 Цена: {BOOK_PRICE_BASE}₽\n"
                    "⏱️ Готово за 5 минут\n\n"
                    "*Выберите действие:*"
                ),
                parse_mode='Markdown',
                reply_markup=main_keyboard  # Постоянная клавиатура
            )
        # Отправляем inline кнопки отдельным сообщением
        await update.message.reply_text(
            "👇 Или используйте кнопки ниже:",
            reply_markup=reply_markup
        )
    else:
        # Если нет картинки - просто текст с кнопками
        await update.message.reply_text(
            "✨ *Персональная сказка про вашего ребёнка!*\n\n"
            "Я создам красочную книгу с AI-иллюстрациями Disney/Pixar качества, "
            "где ваш малыш — главный герой волшебного приключения!\n\n"
            "📖 *Что вы получите:*\n"
            "• 10 страниц с иллюстрациями\n"
            "• 8 увлекательных тем на выбор\n"
            "• Персонаж похож на вашего ребёнка\n"
            "• Профессиональное качество\n"
            "• PDF файл для печати\n\n"
            f"💰 Цена: {BOOK_PRICE_BASE}₽\n"
            "⏱️ Готово за 5 минут\n\n"
            "*Выберите действие:*",
            parse_mode='Markdown',
            reply_markup=main_keyboard  # Постоянная клавиатура
        )
        # Отправляем inline кнопки отдельным сообщением
        await update.message.reply_text(
            "👇 Или используйте кнопки ниже:",
            reply_markup=reply_markup
        )
    
    # ✅ ПАТЧ: Возвращаем END чтобы сбросить состояние ConversationHandler
    return ConversationHandler.END


async def handle_keyboard_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатий на постоянные кнопки клавиатуры"""
    text = update.message.text
    
    if text == "🏠 Главное меню":
        # Вызываем функцию start
        return await start(update, context)
    
    elif text == "⭐ Создать сказку":
        # Имитируем нажатие callback кнопки
        log_event('create_story', update.effective_user.id)
        
        # Загружаем темы
        with open('all_themes_stories.json', 'r', encoding='utf-8') as f:
            themes = json.load(f)
        
        # Создаём кнопки с темами (по 2 в ряд)
        keyboard = []
        theme_buttons = []
        
        for theme_id, theme_data in themes.items():
            emoji = theme_data.get('emoji', '')
            name = theme_data['name']
            button_text = f"{emoji} {name}".strip() if emoji else name
            
            theme_buttons.append(
                InlineKeyboardButton(
                    button_text, 
                    callback_data=f"theme_{theme_id}"
                )
            )
            
            if len(theme_buttons) == 2:
                keyboard.append(theme_buttons.copy())
                theme_buttons = []
        
        if theme_buttons:
            keyboard.append(theme_buttons)
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🎨 *Выберите тему сказки:*\n\n"
            "Каждая история уникальна и адаптируется под возраст и пол ребёнка!",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        
        return CHOOSING_THEME
    
    elif text == "📚 Примеры":
        log_event('show_examples', update.effective_user.id)
        
        keyboard = [
            [InlineKeyboardButton("🦕 Саша с динозаврами", url="https://drive.google.com/uc?export=view&id=1FIVkCSMI-mjhXX236O8FYhiHCJB4_N_C")],
            [InlineKeyboardButton("🧚 Юлиана в стране фей", url="https://drive.google.com/uc?export=view&id=1CphV74SQA-s4q3NwsBQNW92gHla-DLLS")],
            [InlineKeyboardButton("⭐ Создать свою сказку", callback_data="create_story")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "✨ *Взгляните на примеры наших сказок!*\n\n"
            "Выше — реальные иллюстрации из книг, которые мы создаем. "
            "Каждая история уникальна, а картинки рисуются специально "
            "под сюжет и внешность ребенка. 🎨\n\n"
            "*Хотите увидеть, как выглядит полная книга?*\n\n"
            "Нажмите на кнопки ниже, чтобы открыть PDF-примеры",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    elif text == "📞 Поддержка":
        # Устанавливаем флаг что пользователь в режиме поддержки
        context.user_data['in_support_mode'] = True
        
        await update.message.reply_text(
            "📞 *Техподдержка*\n\n"
            "Напишите ваш вопрос или проблему, и я передам его администратору.\n\n"
            "Вы получите ответ в течение нескольких часов. 💬",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Отменить", callback_data="cancel_support")]
            ])
        )


async def show_examples_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_event('show_examples', update.effective_user.id)
    """Показываем примеры работ - КНОПКИ СО ССЫЛКАМИ!"""
    query = update.callback_query
    await query.answer()
    
    # Кнопки с примерами
    keyboard = [
        [InlineKeyboardButton("🦕 Саша с динозаврами", url="https://drive.google.com/uc?export=view&id=1FIVkCSMI-mjhXX236O8FYhiHCJB4_N_C")],
        [InlineKeyboardButton("🧚 Юлиана в стране фей", url="https://drive.google.com/uc?export=view&id=1CphV74SQA-s4q3NwsBQNW92gHla-DLLS")],
        [InlineKeyboardButton("⭐ Создать свою сказку", callback_data="create_story")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=(
            "✨ *Взгляните на примеры наших сказок!*\n\n"
            "Выше — реальные иллюстрации из книг, которые мы создаем. "
            "Каждая история уникальна, а картинки рисуются специально "
            "под сюжет и внешность ребенка. 🎨\n\n"
            "*Хотите увидеть, как выглядит полная книга?*\n\n"
            "Нажмите на кнопки ниже, чтобы открыть PDF-примеры"
        ),
        parse_mode='Markdown',
        reply_markup=reply_markup
    )


async def how_it_works_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_event('how_it_works', update.effective_user.id)
    """Показываем как работает бот"""
    query = update.callback_query
    await query.answer()
    
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=(
            "❓ *Как это работает?*\n\n"
            "Создание персональной сказки — это просто!\n\n"
            "*Шаг 1. Выберите тему* 🎨\n"
            "8 волшебных историй на выбор:\n"
            "• Динозавры 🦕\n"
            "• Космос 🚀\n"
            "• Море и пираты 🏴‍☠️\n"
            "• Феи и волшебство 🧚\n"
            "• Принцессы и рыцари 👸\n"
            "• Животные и природа 🦁\n"
            "• Супергерои 🦸\n"
            "• Зимняя сказка ❄️\n\n"
            "*Шаг 2. Расскажите о ребёнке* 👶\n"
            "Имя, возраст, пол\n\n"
            "*Шаг 3. Загрузите фото (опционально)* 📸\n"
            "Персонаж будет похож на вашего малыша!\n\n"
            "*Шаг 4. Оплатите и получите книгу* 📖\n"
            f"Стоимость: {BOOK_PRICE_BASE}₽ — готово за 5 минут!\n\n"
            "Нажмите *«Создать сказку»* чтобы начать! ✨"
        ),
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⭐ Создать сказку", callback_data="create_story")]
        ])
    )


async def support_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Кнопка поддержки"""
    query = update.callback_query
    await query.answer()
    
    # Устанавливаем флаг что пользователь в режиме поддержки
    context.user_data['in_support_mode'] = True
    
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=(
            "📞 *Техподдержка*\n\n"
            "Напишите ваш вопрос или проблему, и я передам его администратору.\n\n"
            "Вы получите ответ в течение нескольких часов. 💬"
        ),
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Отменить", callback_data="cancel_support")]
        ])
    )


async def cancel_support_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена режима поддержки"""
    query = update.callback_query
    await query.answer()
    
    # Убираем флаг поддержки
    context.user_data['in_support_mode'] = False
    
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text="✅ Режим поддержки отменён. Нажмите /start чтобы продолжить."
    )


async def handle_support_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка сообщений в режиме поддержки и ответов админа"""
    
    user = update.effective_user
    message_text = update.message.text
    
    # ✅ СЛУЧАЙ 1: Админ отвечает пользователю
    if user.id == ADMIN_ID:
        # Проверяем есть ли активный диалог
        if 'admin_dialogs' not in context.bot_data:
            context.bot_data['admin_dialogs'] = {}
        
        target_user_id = context.bot_data['admin_dialogs'].get(ADMIN_ID)
        
        if target_user_id:
            try:
                # Отправляем ответ пользователю
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text=f"💬 *Ответ от поддержки:*\n\n{message_text}",
                    parse_mode='Markdown'
                )
                
                # Подтверждаем админу
                await update.message.reply_text(
                    f"✅ Отправлено пользователю\n\n"
                    f"Чтобы закрыть диалог, напишите /closesupport"
                )
                
                logger.info(f"📤 Админ ответил пользователю {target_user_id}")
                
            except Exception as e:
                logger.error(f"Ошибка отправки ответа: {e}")
                await update.message.reply_text(f"❌ Ошибка отправки: {e}")
        
        return  # Админ не может писать самому себе в поддержку
    
    # ✅ СЛУЧАЙ 2: Обычный пользователь пишет в поддержку
    if not context.user_data.get('in_support_mode', False):
        return  # Не в режиме поддержки - пропускаем
    
    # Отправляем админу
    if ADMIN_ID and ADMIN_ID > 0:
        try:
            # Экранируем спецсимволы для Markdown
            safe_name = str(user.first_name or 'Аноним').replace('*', '\\*').replace('_', '\\_').replace('[', '\\[').replace(']', '\\]').replace('`', '\\`')
            safe_username = str(user.username or 'нет').replace('*', '\\*').replace('_', '\\_')
            safe_message = str(message_text).replace('*', '\\*').replace('_', '\\_').replace('[', '\\[').replace(']', '\\]').replace('`', '\\`')
            
            admin_text = f"""📩 *СООБЩЕНИЕ В ПОДДЕРЖКУ*

👤 От: {safe_name}
📱 Username: @{safe_username}

💬 Сообщение:
{safe_message}

_Просто напишите ответ в этот чат_"""
            
            # Кнопка для быстрых ответов
            keyboard = [
                [InlineKeyboardButton("✅ Решено", callback_data=f"quick_resolved_{user.id}")],
                [InlineKeyboardButton("🕐 Позже", callback_data=f"quick_later_{user.id}")]
            ]
            
            # ✅ АВТОМАТИЧЕСКИ устанавливаем диалог с пользователем
            if 'admin_dialogs' not in context.bot_data:
                context.bot_data['admin_dialogs'] = {}
            context.bot_data['admin_dialogs'][ADMIN_ID] = user.id
            
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=admin_text,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
            # Подтверждаем пользователю
            await update.message.reply_text(
                "✅ Ваше сообщение отправлено в поддержку!\n\n"
                "Мы ответим вам прямо в этом чате. 💬"
            )
            
            # НЕ выходим из режима поддержки - оставляем диалог открытым
            logger.info(f"📨 Сообщение в поддержку от {user.id}: {message_text[:50]}")
            
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения админу: {e}")
            logger.error(traceback.format_exc())
            await update.message.reply_text(
                "❌ Произошла ошибка при отправке сообщения.\n\n"
                "Попробуйте ещё раз через минуту или напишите /start для возврата в меню."
            )


async def quick_reply_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Быстрые ответы админа"""
    query = update.callback_query
    await query.answer()
    
    # Парсим callback_data
    parts = query.data.split('_')
    action = parts[1]  # resolved или later
    user_id = int(parts[2])
    
    if action == 'resolved':
        message = "✅ Ваш вопрос решён! Если есть ещё вопросы - пишите."
    elif action == 'later':
        message = "🕐 Мы получили ваше сообщение и ответим позже. Спасибо за ожидание!"
    
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=message
        )
        await query.message.reply_text(f"✅ Отправлено пользователю {user_id}")
    except Exception as e:
        await query.message.reply_text(f"❌ Ошибка: {e}")


async def reply_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /closesupport для закрытия диалога (для админа)"""
    user_id = update.effective_user.id
    
    # Только админ может использовать
    if user_id != ADMIN_ID:
        return
    
    # Закрываем диалог
    if 'admin_dialogs' not in context.bot_data:
        context.bot_data['admin_dialogs'] = {}
    
    if ADMIN_ID in context.bot_data['admin_dialogs']:
        closed_user = context.bot_data['admin_dialogs'][ADMIN_ID]
        del context.bot_data['admin_dialogs'][ADMIN_ID]
        await update.message.reply_text(
            f"✅ Диалог с пользователем закрыт.\n\n"
            f"Следующее сообщение в поддержку автоматически откроет новый диалог."
        )
    else:
        await update.message.reply_text("ℹ️ Нет активного диалога")


async def closesupport_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /closesupport - алиас для reply_command"""
    return await reply_command(update, context)


async def create_story_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_event('create_story', update.effective_user.id)
    """Начало создания сказки"""
    query = update.callback_query
    await query.answer()
    
    # Загружаем темы
    with open('all_themes_stories.json', 'r', encoding='utf-8') as f:
        themes = json.load(f)
    
    # Создаём кнопки с темами (по 2 в ряд)
    keyboard = []
    theme_buttons = []
    
    for theme_id, theme_data in themes.items():
        # Используем emoji если есть, иначе просто название
        emoji = theme_data.get('emoji', '')
        name = theme_data['name']
        button_text = f"{emoji} {name}".strip() if emoji else name
        
        theme_buttons.append(
            InlineKeyboardButton(
                button_text, 
                callback_data=f"theme_{theme_id}"
            )
        )
        
        # Когда набралось 2 кнопки - добавляем ряд
        if len(theme_buttons) == 2:
            keyboard.append(theme_buttons.copy())
            theme_buttons = []
    
    # Если осталась одна кнопка - добавляем отдельным рядом
    if theme_buttons:
        keyboard.append(theme_buttons)
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=(
            "🎨 *Выберите тему сказки:*\n\n"
            "Каждая история уникальна и адаптируется под возраст и пол ребёнка!"
        ),
        parse_mode='Markdown',
        reply_markup=reply_markup
    )
    
    return CHOOSING_THEME


async def theme_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_event('theme_chosen', update.effective_user.id)
    """Пользователь выбрал тему"""
    query = update.callback_query
    await query.answer()
    
    # Сохраняем выбранную тему
    theme_id = query.data.replace('theme_', '')
    context.user_data['theme'] = theme_id
    
    # Загружаем название темы
    with open('all_themes_stories.json', 'r', encoding='utf-8') as f:
        themes = json.load(f)
    theme_name = themes[theme_id]["name"]
    
    # Кнопки выбора пола
    keyboard = [
        [
            InlineKeyboardButton("👦 Мальчик", callback_data="gender_boy"),
            InlineKeyboardButton("👧 Девочка", callback_data="gender_girl")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=(
            f"✅ Отлично! Тема: *{theme_name}*\n\n"
            "👶 Теперь выберите пол ребёнка:"
        ),
        parse_mode='Markdown',
        reply_markup=reply_markup
    )
    
    return CHOOSING_GENDER


async def gender_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_event('gender_chosen', update.effective_user.id)
    """Пользователь выбрал пол"""
    query = update.callback_query
    await query.answer()
    
    # Сохраняем пол
    gender = query.data.replace('gender_', '')
    context.user_data['gender'] = gender
    
    gender_text = "мальчика" if gender == "boy" else "девочки"
    
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=(
            f"👶 Книга для {gender_text}!\n\n"
            "✍️ Как зовут ребёнка?\n\n"
            "Напишите имя (например: Саша, Маша, Артём)"
        ),
        parse_mode='Markdown'
    )
    
    return GETTING_NAME


async def name_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_event('name_entered', update.effective_user.id)
    """Получено имя ребёнка"""
    name = update.message.text.strip()
    
    # Проверка на длину
    if len(name) < 2 or len(name) > 20:
        await update.message.reply_text(
            "⚠️ Имя должно быть от 2 до 20 символов. Попробуйте ещё раз:"
        )
        return GETTING_NAME
    
    # Сохраняем имя
    context.user_data['name'] = name
    
    await update.message.reply_text(
        f"✅ Отлично, {name}!\n\n"
        "🔢 Сколько лет ребёнку?\n\n"
        "Напишите число (например: 3, 5, 7)"
    )
    
    return GETTING_AGE


async def age_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_event('age_entered', update.effective_user.id)
    """Получен возраст"""
    try:
        age = int(update.message.text.strip())
        
        if age < 1 or age > 12:
            await update.message.reply_text(
                "⚠️ Пожалуйста, укажите возраст от 1 до 12 лет:"
            )
            return GETTING_AGE
        
        context.user_data['age'] = age
        
        # Кнопки выбора версии
        keyboard = [
            [InlineKeyboardButton(
                f"📖 Базовая версия - {BOOK_PRICE_BASE}₽", 
                callback_data="version_base"
            )],
            [InlineKeyboardButton(
                f"⭐ Премиум с анализом фото - {BOOK_PRICE_PREMIUM}₽", 
                callback_data="version_premium"
            )]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"✅ Понял, {age} лет!\n\n"
            "💎 *Выберите версию книги:*\n\n"
            f"📖 *Базовая ({BOOK_PRICE_BASE}₽):*\n"
            "• Персонаж на основе описания\n"
            "• Disney/Pixar стиль иллюстраций\n"
            "• 10 страниц с картинками\n\n"
            f"⭐ *Премиум ({BOOK_PRICE_PREMIUM}₽):*\n"
            "• Анализ фото ребёнка с AI\n"
            "• Персонаж ОЧЕНЬ похож на ребёнка\n"
            "• 10 страниц с картинками\n"
            "• Disney/Pixar стиль иллюстраций",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        
        return CHOOSING_VERSION
        
    except ValueError:
        await update.message.reply_text(
            "⚠️ Пожалуйста, напишите число (например: 3, 5, 7):"
        )
        return GETTING_AGE


async def version_base_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбрана базовая версия"""
    query = update.callback_query
    await query.answer()
    
    context.user_data['version'] = 'base'
    context.user_data['price'] = BOOK_PRICE_BASE
    
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=(
            f"✅ Базовая версия выбрана ({BOOK_PRICE_BASE}₽)\n\n"
            "Переходим к оплате... 💳"
        )
    )
    
    # Переходим сразу к оплате
    return await create_payment_step(update, context)


async def version_premium_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбрана премиум версия"""
    query = update.callback_query
    await query.answer()
    
    context.user_data['version'] = 'premium'
    context.user_data['price'] = BOOK_PRICE_PREMIUM
    
    # Кнопки для загрузки фото
    keyboard = [
        [InlineKeyboardButton("📸 Загрузить фото", callback_data="want_photo")],
        [InlineKeyboardButton(
            f"⬅️ Базовая версия ({BOOK_PRICE_BASE}₽)", 
            callback_data="downgrade_to_base"
        )]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=(
            f"⭐ Премиум версия выбрана ({BOOK_PRICE_PREMIUM}₽)\n\n"
            "📸 *Загрузите фото ребёнка:*\n\n"
            "• Лицо хорошо видно\n"
            "• Чёткое освещение\n"
            "• Без фильтров\n\n"
            "Это поможет AI создать максимально похожего персонажа!"
        ),
        parse_mode='Markdown',
        reply_markup=reply_markup
    )
    
    return GETTING_PHOTO


async def want_photo_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пользователь готов загрузить фото"""
    query = update.callback_query
    await query.answer()
    
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=(
            "📸 Отлично! Загрузите фото ребёнка.\n\n"
            "Фото должно быть:\n"
            "• С хорошим освещением\n"
            "• Лицо видно чётко\n"
            "• Без фильтров"
        )
    )
    
    return GETTING_PHOTO


async def downgrade_to_base_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пользователь передумал и выбрал базовую версию"""
    query = update.callback_query
    await query.answer()
    
    context.user_data['version'] = 'base'
    context.user_data['price'] = BOOK_PRICE_BASE
    
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=(
            f"✅ Хорошо, базовая версия ({BOOK_PRICE_BASE}₽)\n\n"
            "Переходим к оплате... 💳"
        )
    )
    
    # Переходим к оплате
    return await create_payment_step(update, context)


async def skip_photo_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_event('photo_skipped', update.effective_user.id)
    """Пользователь пропустил загрузку фото"""
    query = update.callback_query
    await query.answer()
    
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text="✅ Хорошо, создам персонажа на основе описания!\n\nПереходим к оплате... 💳"
    )
    
    return await create_payment_step(update, context)


async def photo_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_event('photo_uploaded', update.effective_user.id)
    """Получено фото"""
    
    # Скачиваем фото
    photo = update.message.photo[-1]  # Берём самое большое
    file = await context.bot.get_file(photo.file_id)
    
    # Сохраняем во временную папку
    photo_path = f"temp_photos/{update.effective_user.id}.jpg"
    os.makedirs("temp_photos", exist_ok=True)
    await file.download_to_drive(photo_path)
    
    context.user_data['photo_path'] = photo_path
    
    await update.message.reply_text(
        "✅ Фото получено!\n\nПереходим к оплате... 💳"
    )
    
    return await create_payment_step(update, context)


async def create_payment_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_event('payment_created', update.effective_user.id)
    """Создание платежа"""
    
    # Получаем данные
    name = context.user_data['name']
    age = context.user_data['age']
    theme = context.user_data['theme']
    price = context.user_data.get('price', BOOK_PRICE_BASE)
    
    user_id = update.effective_user.id
    
    # Загружаем тему
    with open('all_themes_stories.json', 'r', encoding='utf-8') as f:
        themes = json.load(f)
    theme_name = themes[theme]["name"]
    
    # ✅ ПАТЧ: Проверяем бесплатные кредиты
    if user_id in TEST_UNLIMITED_ACCOUNTS:
        # Неограниченный тестовый аккаунт
        await context.bot.send_message(
            chat_id=user_id,
            text="🎁 *Тестовый аккаунт - бесплатная генерация!*\n\nЗапускаю создание книги...",
            parse_mode='Markdown'
        )
        
        # Создаём заказ в БД
        order_id = db.create_order(
            user_id=user_id,
            theme=theme,
            child_name=name,
            child_age=age,
            gender=context.user_data['gender'],
            photo_description=context.user_data.get('photo_description')
        )
        context.user_data['order_id'] = order_id
        db.update_order_status(order_id, 'paid')
        
        # Сразу запускаем генерацию
        return await start_generation(update, context)
    
    elif user_id in FREE_CREDITS and FREE_CREDITS[user_id] > 0:
        # Есть бесплатный кредит
        FREE_CREDITS[user_id] -= 1
        
        await context.bot.send_message(
            chat_id=user_id,
            text=f"🎁 *У вас есть бесплатная книга!*\n\nОсталось: {FREE_CREDITS[user_id]}\n\nЗапускаю создание...",
            parse_mode='Markdown'
        )
        
        # Создаём заказ в БД
        order_id = db.create_order(
            user_id=user_id,
            theme=theme,
            child_name=name,
            child_age=age,
            gender=context.user_data['gender'],
            photo_description=context.user_data.get('photo_description')
        )
        context.user_data['order_id'] = order_id
        db.update_order_status(order_id, 'paid')
        
        # Сразу запускаем генерацию
        return await start_generation(update, context)
    
    # Обычный платёж
    if not PAYMENT_ENABLED:
        await context.bot.send_message(
            chat_id=user_id,
            text="⚠️ Оплата временно недоступна. Попробуйте позже."
        )
        return ConversationHandler.END
    
    # Создаём заказ в БД
    order_id = db.create_order(
        user_id=user_id,
        theme=theme,
        child_name=name,
        child_age=age,
        gender=context.user_data['gender'],
        photo_description=context.user_data.get('photo_description')
    )
    
    context.user_data['order_id'] = order_id
    
    # Создаём платеж
    payment_data = create_payment(
        amount=price,
        description=f"Персональная сказка - {theme_name}",
        return_url=f"https://t.me/{BOT_USERNAME}"
    )
    
    if not payment_data:
        await context.bot.send_message(
            chat_id=user_id,
            text="❌ Ошибка создания платежа. Попробуйте позже."
        )
        return ConversationHandler.END
    
    # Сохраняем payment_id
    context.user_data['payment_id'] = payment_data['id']
    
    # Сохраняем платёж в БД
    db.create_payment(
        payment_id=payment_data['id'],
        order_id=order_id,
        user_id=user_id,
        amount=price,
        payment_url=payment_data['confirmation_url']
    )
    
    # Отправляем ссылку на оплату
    keyboard = [
        [InlineKeyboardButton("💳 Оплатить", url=payment_data['confirmation_url'])]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Определяем chat_id
    if hasattr(update, 'callback_query') and update.callback_query:
        chat_id = update.callback_query.message.chat_id
    elif hasattr(update, 'message') and update.message:
        chat_id = update.message.chat_id
    else:
        chat_id = user_id
    
    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            f"💳 *Оплата {price}₽*\n\n"
            f"📖 Заказ #{order_id}\n"
            f"✨ {theme_name}\n"
            f"👶 {name}, {age} лет\n\n"
            "Нажмите кнопку ниже для оплаты:"
        ),
        parse_mode='Markdown',
        reply_markup=reply_markup
    )
    
    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            "⏳ Ожидаю оплату...\n\n"
            "После оплаты нажмите /check чтобы проверить статус.\n"
            "Или просто подождите - я проверю автоматически!"
        )
    )
    
    # ✅ ПАТЧ: Запускаем автопроверку с уникальным именем
    job_name = f"payment_{payment_data['id']}"
    
    # Удаляем старую задачу если она есть
    current_jobs = context.job_queue.get_jobs_by_name(job_name)
    for job in current_jobs:
        job.schedule_removal()
    
    # Создаём новую задачу автопроверки
    context.job_queue.run_repeating(
        check_payment_status,
        interval=10,
        first=10,
        data={
            'payment_id': payment_data['id'],
            'chat_id': user_id,
            'user_data': context.user_data.copy(),
            'order_id': order_id,
            'attempts': 0,  # ✅ ПАТЧ: Счётчик попыток
            'max_attempts': 60  # ✅ ПАТЧ: Максимум 10 минут (60 * 10 сек)
        },
        name=job_name
    )
    
    return PAYMENT


async def check_payment_status(context: ContextTypes.DEFAULT_TYPE):
    """Автоматическая проверка статуса платежа"""
    from telegram.error import Forbidden
    
    job = context.job
    payment_id = job.data['payment_id']
    chat_id = job.data['chat_id']
    user_data = job.data['user_data']
    order_id = job.data['order_id']
    
    # ✅ ПАТЧ: Проверяем таймаут
    attempts = job.data.get('attempts', 0)
    max_attempts = job.data.get('max_attempts', 60)
    
    # Увеличиваем счётчик
    job.data['attempts'] = attempts + 1
    
    # Если превышен таймаут - останавливаем
    if attempts >= max_attempts:
        logger.info(f"⏱️ Таймаут автопроверки для payment_id={payment_id} (превышено {max_attempts} попыток)")
        job.schedule_removal()
        return
    
    try:
        # Проверяем статус
        if is_payment_successful(payment_id):
            # Оплата прошла!
            await context.bot.send_message(
                chat_id=chat_id,
                text="✅ *Оплата получена!*\n\nЗапускаю генерацию книги...",
                parse_mode='Markdown'
            )
            
            # Обновляем статусы в БД
            db.update_payment_status(payment_id, 'succeeded')
            db.update_order_status(order_id, 'paid')
            db.update_daily_stats(revenue=BOOK_PRICE_BASE)
            
            # ✅ ПАТЧ: Уведомляем админа ТОЛЬКО ОДИН РАЗ
            if order_id not in notified_orders:
                user_name = user_data.get('name', 'Аноним')
                user_id = chat_id
                await notify_admin_payment(context, user_id, user_name, order_id, BOOK_PRICE_BASE)
                notified_orders.add(order_id)  # Помечаем что уведомление отправлено
                logger.info(f"✅ Админ уведомлён о заказе #{order_id}")
            else:
                logger.info(f"⏭️ Пропускаю дублирующее уведомление для заказа #{order_id}")
            
            # Останавливаем проверку
            job.schedule_removal()
            logger.info(f"⏹️ Автопроверка остановлена для payment_id={payment_id}")
            
            # Запускаем генерацию
            # Создаём временный объект для передачи в start_generation
            class TempUpdate:
                def __init__(self, chat_id):
                    self.effective_user = type('obj', (object,), {'id': chat_id})
                    self.callback_query = None
                    self.message = type('obj', (object,), {'chat_id': chat_id})
            
            class TempContext:
                def __init__(self, bot, user_data):
                    self.bot = bot
                    self.user_data = user_data
            
            temp_update = TempUpdate(chat_id)
            temp_context = TempContext(context.bot, user_data)
            
            logger.info(f"📤 Запускаю генерацию для заказа #{order_id}, user={user_id}")
            await start_generation(temp_update, temp_context)
            logger.info(f"✅ Генерация завершена для заказа #{order_id}")
    
    except Forbidden:
        # Пользователь заблокировал бота - останавливаем проверку
        logger.info(f"Пользователь {chat_id} заблокировал бота. Останавливаем проверку оплаты {payment_id}")
        job.schedule_removal()
    except Exception as e:
        # Другие ошибки - логируем
        logger.error(f"Ошибка проверки оплаты {payment_id}: {e}")


async def start_generation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запускает генерацию книги"""
    
    logger.info("🚀 start_generation вызвана")
    
    # Получаем данные
    name = context.user_data['name']
    age = context.user_data['age']
    gender = context.user_data['gender']
    theme = context.user_data['theme']
    photo_path = context.user_data.get('photo_path')
    order_id = context.user_data.get('order_id')
    
    # Склоняем имя
    name_accusative = decline_name_accusative(name, gender)
    
    # Загружаем название темы
    with open('all_themes_stories.json', 'r', encoding='utf-8') as f:
        themes = json.load(f)
    theme_name = themes[theme]["name"]
    
    # Определяем chat_id
    if hasattr(update, 'callback_query') and update.callback_query:
        chat_id = update.callback_query.message.chat_id
    elif hasattr(update, 'message') and update.message:
        chat_id = update.message.chat_id
    else:
        chat_id = update.effective_user.id
    
    status_message = await context.bot.send_message(
        chat_id=chat_id,
        text=f"⏳ *Создаю сказку про {name_accusative}...*\n\n"
             f"📖 Тема: {theme_name}\n"
             f"✅ Выбрана история\n"
             f"🎨 Рисую 10 иллюстраций...\n"
             f"📄 Соберу PDF книгу\n\n"
             f"_Это займёт примерно 5 минут_",
        parse_mode='Markdown'
    )
    
    try:
        # Определяем plan из user_data
        version = context.user_data.get('version', 'base')
        plan = 'premium' if version == 'premium' else 'standard'
        
        logger.info(f"🎨 Генерация: plan={plan}, photo={'есть' if photo_path else 'нет'}")
        
        # ГЕНЕРИРУЕМ КНИГУ
        pdf_path = create_storybook_v2(
            child_name=name,
            child_age=age,
            gender=gender,
            theme_id=theme,
            photo_path=photo_path,
            plan=plan  # ✅ ПЕРЕДАЁМ ПЛАН ДЛЯ PREMIUM ПЕРСОНАЖА
        )
        
        # Обновляем заказ в БД
        if order_id:
            db.update_order_status(order_id, 'completed', pdf_path)
            db.update_daily_stats(completed_orders=1)
        
        # Удаляем статусное сообщение
        logger.info(f"🗑️ Удаляю статусное сообщение для chat_id={chat_id}")
        await status_message.delete()
        
        # Отправляем PDF
        logger.info(f"📤 Отправляю PDF: {pdf_path} для chat_id={chat_id}")
        with open(pdf_path, 'rb') as pdf_file:
            await context.bot.send_document(
                chat_id=chat_id,
                document=pdf_file,
                filename=f"{name}_сказка.pdf",
                caption=f"🎉 *Ваша сказка готова!*\n\n"
                        f"📖 \"{name} - {theme_name}\"\n\n"
                        f"Расскажите друзьям! 🎁",
                parse_mode='Markdown'
            )
        logger.info(f"✅ PDF отправлен успешно для chat_id={chat_id}")
        
        # Удаляем временное фото если было
        if photo_path and os.path.exists(photo_path):
            os.remove(photo_path)
        
    except Exception as e:
        logger.error(f"❌ Ошибка в start_generation: {e}")
        logger.error(f"Traceback:", exc_info=True)
        
        error_details = str(e)
        is_overloaded = "529" in error_details or "overloaded" in error_details.lower()
        
        # ✅ ВАЖНО: Помечаем заказ как неудачный
        if order_id:
            db.update_order_status(order_id, 'failed')
            logger.info(f"❌ Заказ #{order_id} помечен как failed")
        
        # ✅ Если ошибка 529 - автоматически даём бесплатный кредит
        if is_overloaded:
            user_id = context.user_data.get('user_id') or chat_id
            if user_id in FREE_CREDITS:
                FREE_CREDITS[user_id] += 1
            else:
                FREE_CREDITS[user_id] = 1
            logger.info(f"🎁 Автоматически выдан бесплатный кредит пользователю {user_id} из-за перегрузки")
        
        # ✅ Уведомляем админа о проблеме
        if ADMIN_ID and ADMIN_ID > 0:
            try:
                if is_overloaded:
                    admin_message = (
                        f"⚠️ *ОШИБКА: СЕРВЕР ПЕРЕГРУЖЕН (529)*\n\n"
                        f"👤 Пользователь: {name}\n"
                        f"📝 Заказ: #{order_id}\n"
                        f"❌ Ошибка: Anthropic API перегружен\n\n"
                        f"✅ *Автоматически выдан бесплатный кредит*\n"
                        f"Пользователь может попробовать позже бесплатно."
                    )
                else:
                    admin_message = (
                        f"⚠️ *ОШИБКА ГЕНЕРАЦИИ*\n\n"
                        f"👤 Пользователь: {name}\n"
                        f"📝 Заказ: #{order_id}\n"
                        f"❌ Ошибка: `{error_details[:200]}`\n\n"
                        f"_Нужно вернуть деньги вручную!_"
                    )
                
                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=admin_message,
                    parse_mode='Markdown'
                )
            except Exception as notify_error:
                logger.error(f"Ошибка уведомления админа: {notify_error}")
        
        # Удаляем статусное сообщение
        try:
            await status_message.delete()
        except:
            pass
        
        # Сообщаем пользователю
        if is_overloaded:
            user_message = (
                f"⚠️ *Сервер временно перегружен*\n\n"
                f"Извините! Наши серверы не смогли обработать запрос.\n\n"
                f"🎁 *Мы подарили вам бесплатную книгу!*\n\n"
                f"Попробуйте создать книгу ещё раз через 5-10 минут.\n"
                f"Оплата не потребуется!"
            )
        else:
            user_message = (
                f"❌ Произошла ошибка при создании книги:\n\n`{error_details}`\n\n"
                f"⚠️ *Мы вернём вам деньги в течение 24 часов.*\n\n"
                f"Извините за неудобства! Напишите в поддержку если есть вопросы."
            )
        
        await context.bot.send_message(
            chat_id=chat_id,
            text=user_message,
            parse_mode='Markdown'
        )


async def check_payment_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверка статуса оплаты вручную - команда /check"""
    
    payment_id = context.user_data.get('payment_id')
    
    if not payment_id:
        await update.message.reply_text("❌ Нет активного платежа")
        return
    
    if is_payment_successful(payment_id):
        await update.message.reply_text(
            "✅ Оплата получена! Запускаю генерацию..."
        )
        
        # Обновляем БД
        order_id = context.user_data.get('order_id')
        if order_id:
            db.update_payment_status(payment_id, 'succeeded')
            db.update_order_status(order_id, 'paid')
            db.update_daily_stats(revenue=BOOK_PRICE_BASE)
            
            # ✅ ПАТЧ: Уведомляем админа ТОЛЬКО ОДИН РАЗ
            if order_id not in notified_orders:
                user_name = update.effective_user.first_name or update.effective_user.username or "Аноним"
                await notify_admin_payment(context, update.effective_user.id, user_name, order_id, BOOK_PRICE_BASE)
                notified_orders.add(order_id)
                logger.info(f"✅ Админ уведомлён о заказе #{order_id} (manual check)")
            else:
                logger.info(f"⏭️ Пропускаю дублирующее уведомление для заказа #{order_id} (manual check)")
        
        await start_generation(update, context)
    else:
        await update.message.reply_text(
            "⏳ Платёж ещё не завершён. Пожалуйста, завершите оплату."
        )


async def notify_admin_payment(context, user_id, user_name, order_id, amount):
    """Отправить уведомление админу о новой покупке"""
    if ADMIN_ID and ADMIN_ID > 0:
        try:
            # ✅ ПАТЧ: Экранируем спецсимволы Markdown
            safe_user_name = str(user_name).replace('*', '\\*').replace('_', '\\_').replace('[', '\\[').replace(']', '\\]').replace('`', '\\`')
            
            notification_text = f"""🎉 *НОВАЯ ПОКУПКА!*

👤 Покупатель: {safe_user_name} (ID: {user_id})
📝 Заказ: #{order_id}
💰 Сумма: {amount}₽

🎨 Генерация началась автоматически!"""
            
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=notification_text,
                parse_mode='Markdown'
            )
            logger.info(f"✅ Уведомление админу отправлено о заказе #{order_id}")
        except Exception as e:
            logger.error(f"❌ Ошибка отправки уведомления админу: {e}")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статистика бота - только для админа"""
    user_id = update.effective_user.id
    
    # Проверка на админа
    if ADMIN_ID and user_id != ADMIN_ID:
        await update.message.reply_text("⛔ Эта команда только для администратора")
        return
    
    try:
        # Подключаемся к БД
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # Статистика пользователей
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        
        # Статистика заказов
        cursor.execute("SELECT COUNT(*) FROM orders")
        total_orders = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM orders WHERE status = 'paid' OR status = 'completed'")
        paid_orders = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM orders WHERE status = 'pending'")
        pending_orders = cursor.fetchone()[0]
        
        # ✅ НОВОЕ: Проблемные заказы
        cursor.execute("SELECT COUNT(*) FROM orders WHERE status = 'failed'")
        failed_orders = cursor.fetchone()[0]
        
        # Доход - считаем количество оплаченных × цена
        # Предполагаем что все заказы по базовой цене 290₽
        revenue = paid_orders * BOOK_PRICE_BASE
        
        cursor.close()
        conn.close()
        
        # Конверсии
        conv_order = (total_orders / total_users * 100) if total_users > 0 else 0
        conv_payment = (paid_orders / total_orders * 100) if total_orders > 0 else 0
        
        # Формируем текст
        stats_text = f"""📊 *СТАТИСТИКА БОТА*

👥 *Пользователи:*
• Всего: {total_users}

📦 *Заказы:*
• Всего: {total_orders}
• Оплачено: {paid_orders}
• Ожидают оплату: {pending_orders}
• ⚠️ Проблемные: {failed_orders}

💰 *Доход:* {revenue:,.0f}₽

📈 *Конверсия:*
• Пользователи → Заказы: {conv_order:.1f}%
• Заказы → Оплата: {conv_payment:.1f}%"""
        
        # ✅ Кнопка для просмотра проблемных заказов
        keyboard = []
        if failed_orders > 0:
            keyboard.append([InlineKeyboardButton(
                f"⚠️ Посмотреть проблемные ({failed_orders})",
                callback_data="view_failed_orders"
            )])
        
        reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
        await update.message.reply_text(
            stats_text, 
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error(f"Ошибка в stats_command: {e}")
        logger.error(traceback.format_exc())
        await update.message.reply_text(f"❌ Ошибка получения статистики: {e}")


async def myid_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать свой user_id"""
    user_id = update.effective_user.id
    await update.message.reply_text(f"🆔 Ваш ID: `{user_id}`", parse_mode='Markdown')


async def view_failed_orders_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать проблемные заказы (для админа)"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if user_id != ADMIN_ID:
        return
    
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # Получаем failed заказы
        cursor.execute("""
            SELECT o.id, o.user_id, o.created_at, u.first_name
            FROM orders o
            LEFT JOIN users u ON o.user_id = u.id
            WHERE o.status = 'failed'
            ORDER BY o.created_at DESC
            LIMIT 10
        """)
        
        failed_orders = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if not failed_orders:
            await query.message.reply_text("✅ Нет проблемных заказов!")
            return
        
        # Формируем список
        text = "⚠️ *ПРОБЛЕМНЫЕ ЗАКАЗЫ*\n\n"
        text += "_Нужно вернуть деньги вручную:_\n\n"
        
        for order in failed_orders:
            order_id, user_id, created_at, user_name = order
            text += f"📝 Заказ #{order_id}\n"
            text += f"👤 {user_name or 'Аноним'} (ID: {user_id})\n"
            text += f"💰 {BOOK_PRICE_BASE}₽\n"
            text += f"📅 {created_at[:16]}\n"
            text += f"_Команда:_ `/refund {order_id}`\n\n"
        
        await query.message.reply_text(text, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Ошибка в view_failed_orders: {e}")
        await query.message.reply_text(f"❌ Ошибка: {e}")


async def refund_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /refund <order_id> - пометить что деньги возвращены"""
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        return
    
    if not context.args:
        await update.message.reply_text("❌ Используйте: /refund <order_id>")
        return
    
    try:
        order_id = int(context.args[0])
        
        # Обновляем статус заказа
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # Проверяем что заказ существует и failed
        cursor.execute("SELECT user_id, status FROM orders WHERE id = ?", (order_id,))
        result = cursor.fetchone()
        
        if not result:
            await update.message.reply_text(f"❌ Заказ #{order_id} не найден")
            cursor.close()
            conn.close()
            return
        
        user_id_order, status = result
        # Используем базовую цену
        price = BOOK_PRICE_BASE
        
        if status != 'failed':
            await update.message.reply_text(f"❌ Заказ #{order_id} не в статусе 'failed' (текущий: {status})")
            cursor.close()
            conn.close()
            return
        
        # Помечаем как возвращено
        cursor.execute("UPDATE orders SET status = 'refunded' WHERE id = ?", (order_id,))
        conn.commit()
        cursor.close()
        conn.close()
        
        # Уведомляем админа
        await update.message.reply_text(
            f"✅ Заказ #{order_id} помечен как возвращён!\n\n"
            f"💰 Сумма: {price}₽\n"
            f"👤 Пользователь: {user_id_order}\n\n"
            f"_Не забудь вернуть деньги через YooKassa!_"
        )
        
        # Уведомляем пользователя
        try:
            await context.bot.send_message(
                chat_id=user_id_order,
                text=f"✅ *Возврат средств*\n\n"
                     f"Мы вернули {price}₽ за заказ #{order_id}.\n\n"
                     f"Деньги поступят на карту в течение 3-5 рабочих дней.\n\n"
                     f"Извините за неудобства! 🙏",
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Не удалось уведомить пользователя {user_id_order}: {e}")
        
    except ValueError:
        await update.message.reply_text("❌ Неверный формат. Используйте: /refund <order_id>")
    except Exception as e:
        logger.error(f"Ошибка в refund_command: {e}")
        await update.message.reply_text(f"❌ Ошибка: {e}")


async def getpdf_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /getpdf <order_id> - получить PDF файл заказа (для админа)"""
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        return
    
    if not context.args:
        await update.message.reply_text("❌ Используйте: /getpdf <order_id>\n\nПример: /getpdf 270")
        return
    
    try:
        order_id = int(context.args[0])
        
        # Ищем заказ в БД
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT user_id, child_name, theme, status FROM orders WHERE id = %s",
            (order_id,)
        )
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not result:
            await update.message.reply_text(f"❌ Заказ #{order_id} не найден")
            return
        
        user_id_order, child_name, theme, status = result
        
        # Формируем путь к PDF
        theme_folders = {
            'robot_city': 'robot_city',
            'space': 'space',
            'dinosaurs': 'dinosaurs',
            'underwater': 'underwater',
            'fairy_land': 'fairy_land',
            'princess': 'princess',
            'unicorns': 'unicorns',
            'knight': 'knight'
        }
        
        theme_names = {
            'robot_city': 'в_городе_роботов',
            'space': 'в_космосе',
            'dinosaurs': 'с_динозаврами',
            'underwater': 'под_водой',
            'fairy_land': 'в_стране_фей',
            'princess': 'в_королевстве',
            'unicorns': 'с_единорогами',
            'knight': 'с_рыцарем'
        }
        
        folder_name = f"storybook_{child_name}_{theme_folders.get(theme, theme)}"
        pdf_filename = f"{child_name}_{theme_names.get(theme, theme)}.pdf"
        pdf_path = f"{folder_name}/{pdf_filename}"
        
        # Проверяем существование файла
        import os
        if not os.path.exists(pdf_path):
            await update.message.reply_text(
                f"❌ PDF не найден!\n\n"
                f"Заказ: #{order_id}\n"
                f"Статус: {status}\n"
                f"Ожидаемый путь: {pdf_path}"
            )
            return
        
        # Отправляем PDF
        file_size_mb = os.path.getsize(pdf_path) / 1024 / 1024
        await update.message.reply_text(f"📤 Отправляю PDF заказа #{order_id}...")
        
        with open(pdf_path, 'rb') as pdf_file:
            await context.bot.send_document(
                chat_id=ADMIN_ID,
                document=pdf_file,
                filename=pdf_filename,
                caption=f"📚 Заказ #{order_id}\n"
                        f"👤 User: {user_id_order}\n"
                        f"📖 {child_name} - {theme}\n"
                        f"💾 Размер: {file_size_mb:.1f} MB\n"
                        f"📊 Статус: {status}"
            )
        
        logger.info(f"✅ PDF заказа #{order_id} отправлен админу")
        
    except ValueError:
        await update.message.reply_text("❌ Неверный формат. Используйте: /getpdf <order_id>")
    except Exception as e:
        logger.error(f"Ошибка в getpdf_command: {e}")
        await update.message.reply_text(f"❌ Ошибка: {e}")


async def gift_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /gift <user_id> - подарить пользователю бесплатную книгу (для админа)"""
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        return
    
    if not context.args:
        await update.message.reply_text(
            "❌ Используйте: `/gift <user_id>`\n\n"
            "Пример: `/gift 893901117`\n\n"
            "Это даст пользователю 1 бесплатный кредит на создание книги.",
            parse_mode='Markdown'
        )
        return
    
    try:
        target_user_id = int(context.args[0])
        
        # Добавляем бесплатный кредит
        if target_user_id in FREE_CREDITS:
            FREE_CREDITS[target_user_id] += 1
        else:
            FREE_CREDITS[target_user_id] = 1
        
        # Уведомляем админа
        await update.message.reply_text(
            f"🎁 *Бесплатный кредит выдан!*\n\n"
            f"👤 Пользователь: {target_user_id}\n"
            f"✨ Бесплатных книг: {FREE_CREDITS[target_user_id]}\n\n"
            f"Пользователь может создать книгу без оплаты.",
            parse_mode='Markdown'
        )
        
        # Уведомляем пользователя
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=f"🎁 *Подарок от администрации!*\n\n"
                     f"Вам подарена **бесплатная книга**!\n\n"
                     f"Нажмите /start и создайте книгу - оплата не потребуется.\n\n"
                     f"Доступно бесплатных книг: {FREE_CREDITS[target_user_id]} 📚",
                parse_mode='Markdown'
            )
            logger.info(f"🎁 Выдан бесплатный кредит пользователю {target_user_id}")
        except Exception as e:
            logger.error(f"Не удалось уведомить пользователя {target_user_id}: {e}")
            await update.message.reply_text(
                f"⚠️ Кредит выдан, но не удалось уведомить пользователя.\n"
                f"Возможно, он не запускал бота."
            )
        
    except ValueError:
        await update.message.reply_text("❌ Неверный формат. Используйте: /gift <user_id>")
    except Exception as e:
        logger.error(f"Ошибка в gift_command: {e}")
        logger.error(traceback.format_exc())
        await update.message.reply_text(f"❌ Ошибка: {e}")



async def analytics_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Аналитика бота - только для админа"""
    user_id = update.effective_user.id
    
    # Проверка на админа
    if ADMIN_ID and user_id != ADMIN_ID:
        await update.message.reply_text("⛔ Эта команда только для администратора")
        return
    
    try:
        # Подключаемся к БД
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # Статистика пользователей
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        
        # Статистика заказов
        cursor.execute("SELECT COUNT(*) FROM orders")
        total_orders = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM orders WHERE status = 'paid' OR status = 'completed'")
        paid_orders = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM orders WHERE status = 'pending'")
        pending_orders = cursor.fetchone()[0]
        
        # Доход - считаем количество оплаченных × цена
        revenue = paid_orders * BOOK_PRICE_BASE
        
        cursor.close()
        conn.close()
        
        # Конверсии
        conv_order = (total_orders / total_users * 100) if total_users > 0 else 0
        conv_payment = (paid_orders / total_orders * 100) if total_orders > 0 else 0
        
        # Формируем текст
        stats_text = f"""📊 *АНАЛИТИКА БОТА*

👥 *База данных:*
• Всего пользователей: {total_users}
• Всего заказов: {total_orders}
• Оплачено: {paid_orders}
• Ожидают оплату: {pending_orders}
• Доход: {revenue:,.0f}₽

📈 *Конверсия:*
• Пользователи → Заказы: {conv_order:.1f}%
• Заказы → Оплата: {conv_payment:.1f}%

🔥 *Текущая сессия:*
• /start: {analytics_cache.get('start', 0)}
• 📚 Примеры: {analytics_cache.get('show_examples', 0)}
• ❓ Как работает: {analytics_cache.get('how_it_works', 0)}
• ⭐ Начали создание: {analytics_cache.get('create_story', 0)}
• 🎨 Выбрали тему: {analytics_cache.get('theme_chosen', 0)}
• 👦👧 Выбрали пол: {analytics_cache.get('gender_chosen', 0)}
• ✍️ Ввели имя: {analytics_cache.get('name_entered', 0)}
• 🔢 Ввели возраст: {analytics_cache.get('age_entered', 0)}
• 📸 Загрузили фото: {analytics_cache.get('photo_uploaded', 0)}
• ⏭️ Пропустили фото: {analytics_cache.get('photo_skipped', 0)}
• 💰 Создали платеж: {analytics_cache.get('payment_created', 0)}

💡 *Воронка (текущая сессия):*
"""
        
        # Воронка конверсии
        funnel_start = analytics_cache.get('start', 0)
        if funnel_start > 0:
            stats_text += f"• {funnel_start} открыли бота (100%)\n"
            
            examples = analytics_cache.get('show_examples', 0)
            if examples > 0:
                stats_text += f"• {examples} посмотрели примеры ({examples/funnel_start*100:.0f}%)\n"
            
            create = analytics_cache.get('create_story', 0)
            if create > 0:
                stats_text += f"• {create} начали создание ({create/funnel_start*100:.0f}%)\n"
            
            payment = analytics_cache.get('payment_created', 0)
            if payment > 0:
                stats_text += f"• {payment} дошли до оплаты ({payment/funnel_start*100:.0f}%)\n"
            
            if paid_orders > 0:
                stats_text += f"• {paid_orders} оплатили (всего)\n"
        else:
            stats_text += "• Нет данных в текущей сессии\n"
        
        await update.message.reply_text(stats_text, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Ошибка в analytics_command: {e}")
        logger.error(traceback.format_exc())
        await update.message.reply_text(f"❌ Ошибка получения статистики: {e}")


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена текущего разговора"""
    await update.message.reply_text(
        "❌ Создание сказки отменено.\n\nНажмите /start чтобы начать заново."
    )
    return ConversationHandler.END


# ✅ ПАТЧ СТАБИЛЬНОСТИ: Глобальный обработчик ошибок
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Предотвращает падение бота при сетевых ошибках"""
    logger.error(f"Exception while handling an update: {context.error}")
    logger.error("".join(traceback.format_exception(None, context.error, context.error.__traceback__)))
    
    if update and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "⚠️ Произошла временная ошибка. Попробуйте через минуту или напишите /start"
            )
        except Exception as e:
            logger.error(f"Could not send error message to user: {e}")
    return


def main():
    """Запуск бота"""
    
    print("🤖 Запускаю Telegram бота...")
    print(f"💳 Оплата: {'✅ ВКЛЮЧЕНА' if PAYMENT_ENABLED else '⚠️ ВЫКЛЮЧЕНА'}")
    
    # Получаем настройки для webhook
    PORT = int(os.environ.get('PORT', '8080'))
    USE_WEBHOOK = os.environ.get('USE_WEBHOOK', 'false').lower() == 'true'
    RAILWAY_DOMAIN = os.environ.get('RAILWAY_PUBLIC_DOMAIN', '')
    
    WEBHOOK_URL = ""
    if USE_WEBHOOK and RAILWAY_DOMAIN:
        WEBHOOK_URL = f"https://{RAILWAY_DOMAIN}"
    
    print(f"🌐 Webhook режим: {'ВКЛЮЧЕН' if USE_WEBHOOK else 'ВЫКЛЮЧЕН'}")
    if WEBHOOK_URL:
        print(f"🔗 Webhook URL: {WEBHOOK_URL}")
    print(f"🔌 PORT: {PORT}")
    
    # Увеличиваем таймауты
    # ✅ ПАТЧ СТАБИЛЬНОСТИ: Улучшенные таймауты
    request = HTTPXRequest(
        connection_pool_size=30,     # Больше одновременных соединений
        connect_timeout=15.0,        # Таймаут подключения
        read_timeout=30.0,           # Таймаут чтения
        write_timeout=60.0,          # Таймаут записи (увеличен для больших PDF)
        pool_timeout=15.0            # Таймаут получения соединения
    )
    
    application = Application.builder().token(BOT_TOKEN).request(request).build()
    
    # ✅ ПАТЧ: Handler для постоянных кнопок клавиатуры (group=-2, самый первый!)
    application.add_handler(
        MessageHandler(
            filters.TEXT & filters.Regex('^(🏠 Главное меню|⭐ Создать сказку|📚 Примеры|📞 Поддержка)$'),
            handle_keyboard_buttons
        ),
        group=-2
    )
    
    # Handler для сообщений в поддержку (ВТОРЫМ! group=-1)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_support_message), group=-1)
    
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),
            CallbackQueryHandler(create_story_callback, pattern='^create_story$')
        ],
        states={
            CHOOSING_THEME: [
                CallbackQueryHandler(theme_chosen, pattern='^theme_')
            ],
            CHOOSING_GENDER: [
                CallbackQueryHandler(gender_chosen, pattern='^gender_')
            ],
            GETTING_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, name_received)
            ],
            GETTING_AGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, age_received)
            ],
            CHOOSING_VERSION: [
                CallbackQueryHandler(version_base_callback, pattern='^version_base$'),
                CallbackQueryHandler(version_premium_callback, pattern='^version_premium$')
            ],
            GETTING_PHOTO: [
                CallbackQueryHandler(want_photo_callback, pattern='^want_photo$'),
                CallbackQueryHandler(downgrade_to_base_callback, pattern='^downgrade_to_base$'),
                CallbackQueryHandler(skip_photo_callback, pattern='^skip_photo$'),
                MessageHandler(filters.PHOTO, photo_received)
            ],
            PAYMENT: []
        },
        fallbacks=[
            CommandHandler('cancel', cancel),
            CommandHandler('start', start)  # ✅ ПАТЧ: Позволяет начать заново в любой момент
        ]
    )
    
    application.add_handler(conv_handler)
    
    # Handlers для примеров, инструкции и поддержки (вне conversation)
    application.add_handler(CallbackQueryHandler(show_examples_callback, pattern='^show_examples$'))
    application.add_handler(CallbackQueryHandler(how_it_works_callback, pattern='^how_it_works$'))
    application.add_handler(CallbackQueryHandler(support_callback, pattern='^support$'))
    application.add_handler(CallbackQueryHandler(cancel_support_callback, pattern='^cancel_support$'))
    
    # Handlers для кнопок админа в поддержке
    application.add_handler(CallbackQueryHandler(quick_reply_callback, pattern='^quick_'))
    
    # Команды
    application.add_handler(CommandHandler('check', check_payment_command))
    application.add_handler(CommandHandler('stats', stats_command))
    application.add_handler(CommandHandler('refund', refund_command))  # Возврат денег
    application.add_handler(CommandHandler('gift', gift_command))  # Подарить книгу
    application.add_handler(CommandHandler('getpdf', getpdf_command))  # Получить PDF заказа
    application.add_handler(CallbackQueryHandler(view_failed_orders_callback, pattern='^view_failed_orders$'))
    application.add_handler(CommandHandler('myid', myid_command))
    application.add_handler(CommandHandler('analytics', analytics_command))
    application.add_handler(CommandHandler('reply', reply_command))  # Для админа (закрытие диалога)
    application.add_handler(CommandHandler('closesupport', closesupport_command))  # Алиас
    
    # ✅ ПАТЧ СТАБИЛЬНОСТИ: Регистрируем глобальный обработчик ошибок
    application.add_error_handler(error_handler)
    
    logger.info("=" * 60)
    logger.info("🚀 БОТ ЗАПУЩЕН С ПАТЧЕМ СТАБИЛЬНОСТИ!")
    logger.info("=" * 60)
    logger.info("✅ Error handler: включён")
    logger.info("✅ Таймауты: write_timeout=60 сек (для больших PDF), read=30 сек, connect=15 сек")
    logger.info("✅ Connection pool: 30 соединений")
    logger.info("✅ Дедупликация уведомлений: включена")
    logger.info("✅ Шумные httpx логи: отключены")
    logger.info("✅ Команда /getpdf: доступна для получения PDF заказов")
    logger.info("=" * 60)
    
    print("✅ Бот с YooKassa и БД запущен!")
    
    # WEBHOOK режим (устраняет конфликты!)
    if WEBHOOK_URL:
        print("🔗 Запуск в WEBHOOK режиме (конфликтов НЕ БУДЕТ!)")
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path="",
            webhook_url=WEBHOOK_URL
        )
    else:
        print("📡 Запуск в POLLING режиме")
        # ✅ ПАТЧ СТАБИЛЬНОСТИ: Параметры для стабильности
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,  # Игнорируем старые сообщения
            timeout=30                   # Увеличенный таймаут
        )


if __name__ == '__main__':
    main()
