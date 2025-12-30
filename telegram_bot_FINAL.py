#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram бот для персональных сказок - ФИНАЛЬНАЯ ВЕРСИЯ
8 тем + YooKassa оплата + База данных
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    CallbackQueryHandler, ContextTypes, filters, ConversationHandler
)
import os
import json
import logging
import traceback
from telegram.request import HTTPXRequest

# ✅ ПАТЧ СТАБИЛЬНОСТИ: Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

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
BOOK_PRICE = 299  # рублей

# Состояния разговора
CHOOSING_THEME, CHOOSING_GENDER, GETTING_NAME, GETTING_AGE, GETTING_PHOTO, PAYMENT = range(6)


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
                    f"💰 Цена: {BOOK_PRICE}₽\n"
                    "⏱️ Готово за 5 минут\n\n"
                    "*Выберите действие:*"
                ),
                parse_mode='Markdown',
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
            f"💰 Цена: {BOOK_PRICE}₽\n"
            "⏱️ Готово за 5 минут\n\n"
            "*Выберите действие:*",
            parse_mode='Markdown',
            reply_markup=reply_markup
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
            "• 🤖 Город роботов\n"
            "• 🚀 Космическое приключение\n"
            "• 🦕 Долина динозавров\n"
            "• 🌊 Подводное царство\n"
            "• 🧚 Страна фей\n"
            "• 👑 Королевство принцесс\n"
            "• 🦄 Волшебные единороги\n"
            "• 🏰 Рыцарь и дракон\n\n"
            "*Шаг 2. Укажите пол героя* 👦👧\n"
            "Мальчик или девочка?\n\n"
            "*Шаг 3. Напишите имя* ✍️\n"
            "Ваш ребёнок станет главным героем!\n\n"
            "*Шаг 4. Укажите возраст* 🎂\n"
            "Просто цифра (любой возраст)\n\n"
            "*Шаг 5. Загрузите фото (опционально)* 📸\n"
            "Я проанализирую внешность:\n"
            "• Цвет волос\n"
            "• Цвет глаз\n"
            "• Особенности (веснушки, очки)\n"
            "Можно пропустить — создам типичного персонажа.\n\n"
            "*Шаг 6. Оплатите* 💳\n"
            f"Цена: {BOOK_PRICE}₽\n\n"
            "*Шаг 7. Получите книгу!* 📖\n"
            "⏱️ Готово за 5 минут\n"
            "• 10 страниц с иллюстрациями\n"
            "• Disney/Pixar качество\n"
            "• PDF файл для печати или чтения\n\n"
            "Всё просто! Начнём? 😊"
        ),
        parse_mode='Markdown'
    )
    
    keyboard = [[InlineKeyboardButton("⭐ Создать сказку", callback_data="create_story")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text="Готовы создать сказку?",
        reply_markup=reply_markup
    )


async def support_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запускаем режим поддержки - пользователь пишет прямо в бота"""
    query = update.callback_query
    await query.answer()
    
    context.user_data['support_mode'] = True
    print(f"📞 Включен режим поддержки для пользователя {query.from_user.id}")
    
    keyboard = [[InlineKeyboardButton("❌ Отменить", callback_data="cancel_support")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=(
            "📞 *Служба поддержки*\n\n"
            "Напишите ваш вопрос или проблему, и я передам его администратору.\n\n"
            "*Мы отвечаем:*\n"
            "• По вопросам оплаты — моментально\n"
            "• Технические вопросы — в течение часа\n"
            "• Общие вопросы — в течение 2-3 часов\n\n"
            "✍️ Напишите сообщение:"
        ),
        parse_mode='Markdown',
        reply_markup=reply_markup
    )


async def cancel_support_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отменяем режим поддержки"""
    query = update.callback_query
    await query.answer()
    
    context.user_data['support_mode'] = False
    print(f"❌ Отменен режим поддержки для пользователя {query.from_user.id}")
    
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text="✅ Отменено. Используйте /start для возврата в главное меню."
    )


async def admin_reply_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Админ нажал кнопку 'Свой ответ' - включаем режим ответа"""
    query = update.callback_query
    await query.answer()
    
    # Проверка что это админ
    if query.from_user.id != ADMIN_ID:
        return
    
    # Извлекаем user_id из callback_data
    user_id = int(query.data.split('_')[2])
    
    # Сохраняем в контекст что админ отвечает этому пользователю
    context.user_data['admin_replying_to'] = user_id
    
    await query.edit_message_text(
        text=query.message.text + "\n\n<b>✍️ Напишите ваш ответ:</b>",
        parse_mode='HTML'
    )


async def handle_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатываем текст ответа от админа"""
    
    # Проверяем что это админ и он в режиме ответа
    if update.effective_user.id != ADMIN_ID:
        return
    
    user_id = context.user_data.get('admin_replying_to')
    if not user_id:
        return
    
    reply_text = update.message.text
    
    # Отключаем режим ответа
    context.user_data['admin_replying_to'] = None
    
    # Экранируем HTML
    safe_reply = reply_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    
    try:
        # Отправляем ответ пользователю
        await context.bot.send_message(
            chat_id=user_id,
            text=(
                f"📞 <b>Ответ от поддержки:</b>\n\n"
                f"{safe_reply}\n\n"
                f"<i>Если у вас ещё есть вопросы, используйте /start → 📞 Поддержка</i>"
            ),
            parse_mode='HTML'
        )
        
        # Подтверждение админу
        await update.message.reply_text(f"✅ Ответ отправлен пользователю {user_id}")
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка отправки: {e}")


async def quick_reply_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатываем быстрые ответы (кнопки)"""
    query = update.callback_query
    await query.answer()
    
    # Проверка что это админ
    if query.from_user.id != ADMIN_ID:
        return
    
    # Извлекаем тип ответа и user_id
    parts = query.data.split('_')
    reply_type = parts[1]
    user_id = int(parts[2])
    
    # Готовые ответы
    quick_replies = {
        'paid': '✅ Ваш платёж получен! Книга отправляется сейчас.',
        'wait': '⏳ Ваша книга генерируется. Это займёт 3-5 минут. Пожалуйста, подождите!',
        'error': '❌ Произошла ошибка. Мы уже работаем над решением. Напишите мне через несколько минут.',
        'howto': '👌 Создание сказки простое: нажмите /start → ⭐ Создать сказку → следуйте инструкциям. Цена 449₽.',
        'balance': '💰 Проверяю ваш платёж... Один момент!',
        'quality': '🎨 Все иллюстрации создаются с помощью AI Disney/Pixar качества. Гарантируем высокое качество!'
    }
    
    reply_text = quick_replies.get(reply_type, 'Спасибо за обращение!')
    
    try:
        # Отправляем ответ пользователю
        await context.bot.send_message(
            chat_id=user_id,
            text=(
                f"📞 <b>Ответ от поддержки:</b>\n\n"
                f"{reply_text}\n\n"
                f"<i>Если у вас ещё есть вопросы, используйте /start → 📞 Поддержка</i>"
            ),
            parse_mode='HTML'
        )
        
        # Обновляем сообщение админу
        await query.edit_message_text(
            text=query.message.text + f"\n\n<b>✅ Отправлен быстрый ответ: {reply_type}</b>",
            parse_mode='HTML'
        )
        
    except Exception as e:
        await query.message.reply_text(f"❌ Ошибка отправки: {e}")


async def handle_support_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатываем сообщение в режиме поддержки"""
    
    # Если это админ в режиме ответа - обрабатываем отдельно
    if update.effective_user.id == ADMIN_ID and context.user_data.get('admin_replying_to'):
        await handle_admin_reply(update, context)
        return
    
    # Проверяем режим поддержки
    support_mode = context.user_data.get('support_mode', False)
    print(f"📝 Получено сообщение. Support mode: {support_mode}")
    
    if not support_mode:
        return
    
    user = update.effective_user
    user_message = update.message.text
    
    print(f"📩 Обрабатываем сообщение в поддержку от {user.id}: {user_message}")
    
    # Отключаем режим поддержки
    context.user_data['support_mode'] = False
    
    # Отправляем подтверждение пользователю
    await update.message.reply_text(
        "✅ Ваше сообщение отправлено в поддержку!\n\n"
        "Мы ответим вам в ближайшее время прямо здесь, в боте.\n\n"
        "Используйте /start для возврата в главное меню."
    )
    
    # Пересылаем админу
    if ADMIN_ID:
        # Экранируем HTML символы
        safe_name = (user.first_name or 'Без имени').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        safe_username = (user.username or 'нет').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        safe_message = user_message.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        
        admin_text = (
            f"📩 <b>Новое обращение в поддержку</b>\n\n"
            f"👤 User ID: {user.id}\n"
            f"👤 Username: @{safe_username}\n"
            f"💬 Сообщение:\n{safe_message}"
        )
        
        # Кнопки для ответа
        keyboard = [
            [InlineKeyboardButton("✍️ Свой ответ", callback_data=f"admin_reply_{user.id}")],
            [
                InlineKeyboardButton("✅ Оплачено", callback_data=f"quick_paid_{user.id}"),
                InlineKeyboardButton("⏳ Ждите", callback_data=f"quick_wait_{user.id}")
            ],
            [
                InlineKeyboardButton("❌ Ошибка", callback_data=f"quick_error_{user.id}"),
                InlineKeyboardButton("👌 Как работает?", callback_data=f"quick_howto_{user.id}")
            ],
            [InlineKeyboardButton("💰 Баланс", callback_data=f"quick_balance_{user.id}")],
            [InlineKeyboardButton("🎨 Качество", callback_data=f"quick_quality_{user.id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=admin_text,
                parse_mode='HTML',
                reply_markup=reply_markup
            )
            print(f"✅ Сообщение отправлено админу {ADMIN_ID}")
        except Exception as e:
            print(f"❌ Ошибка отправки админу: {e}")


async def reply_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для ответа пользователю: /reply USER_ID текст"""
    
    # Проверка что это админ
    if update.effective_user.id != ADMIN_ID:
        return
    
    # Проверяем аргументы
    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ Использование: /reply USER_ID текст ответа\n\n"
            "Пример: /reply 123456789 Здравствуйте! Ваш вопрос решён."
        )
        return
    
    try:
        user_id = int(context.args[0])
        reply_text = ' '.join(context.args[1:])
        
        # Экранируем HTML символы
        safe_reply = reply_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        
        # Отправляем ответ пользователю
        await context.bot.send_message(
            chat_id=user_id,
            text=(
                f"📞 <b>Ответ от поддержки:</b>\n\n"
                f"{safe_reply}\n\n"
                f"<i>Если у вас ещё есть вопросы, используйте /start → 📞 Поддержка</i>"
            ),
            parse_mode='HTML'
        )
        
        # Подтверждение админу
        await update.message.reply_text(
            f"✅ Ответ отправлен пользователю {user_id}"
        )
        
    except ValueError:
        await update.message.reply_text("❌ Неверный ID пользователя")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка отправки: {e}")


async def create_story_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показываем выбор темы - ВСЕ 8 ТЕМ СРАЗУ"""
    query = update.callback_query
    await query.answer()
    
    # Загружаем темы
    with open('all_themes_stories.json', 'r', encoding='utf-8') as f:
        themes = json.load(f)
    
    # Создаём кнопки - ВСЕ 8 ТЕМ (2 в ряду)
    keyboard = [
        [InlineKeyboardButton(themes["robot_city"]["name"], callback_data="theme_robot_city"),
         InlineKeyboardButton(themes["space"]["name"], callback_data="theme_space")],
        [InlineKeyboardButton(themes["dinosaurs"]["name"], callback_data="theme_dinosaurs"),
         InlineKeyboardButton(themes["underwater"]["name"], callback_data="theme_underwater")],
        [InlineKeyboardButton(themes["fairy_land"]["name"], callback_data="theme_fairy_land"),
         InlineKeyboardButton(themes["princess"]["name"], callback_data="theme_princess")],
        [InlineKeyboardButton(themes["unicorns"]["name"], callback_data="theme_unicorns"),
         InlineKeyboardButton(themes["knight"]["name"], callback_data="theme_knight")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=(
            "🎨 *Выбери тему сказки:*\n\n"
            "📖 8 волшебных историй на выбор!"
        ),
        parse_mode='Markdown',
        reply_markup=reply_markup
    )
    
    return CHOOSING_THEME


async def theme_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Тема выбрана, спрашиваем пол"""
    query = update.callback_query
    await query.answer()
    
    theme_id = query.data.replace("theme_", "")
    context.user_data['theme'] = theme_id
    
    # Загружаем название темы
    with open('all_themes_stories.json', 'r', encoding='utf-8') as f:
        themes = json.load(f)
    theme_name = themes[theme_id]["name"]
    
    keyboard = [
        [InlineKeyboardButton("👦 Мальчик", callback_data="gender_boy")],
        [InlineKeyboardButton("👧 Девочка", callback_data="gender_girl")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=f"✅ Тема: {theme_name}\n\n👶 Кто будет главным героем?",
        reply_markup=reply_markup
    )
    
    return CHOOSING_GENDER


async def gender_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пол выбран - переходим к имени"""
    query = update.callback_query
    await query.answer()
    
    gender = "boy" if query.data == "gender_boy" else "girl"
    context.user_data['gender'] = gender
    
    gender_ru = "мальчик" if gender == "boy" else "девочка"
    
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=f"Отлично! Герой — {gender_ru} 👍\n\n📝 *Напишите имя ребёнка:*",
        parse_mode='Markdown'
    )
    
    return GETTING_NAME


async def name_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получено имя - просим возраст"""
    name = update.message.text.strip()
    
    # Проверка имени
    if len(name) < 2 or len(name) > 20:
        await update.message.reply_text(
            "⚠️ Имя должно быть от 2 до 20 символов.\n"
            "Попробуйте ещё раз:"
        )
        return GETTING_NAME
    
    context.user_data['name'] = name
    
    await update.message.reply_text(
        f"Замечательно, {name}! 😊\n\n"
        f"🎂 *Сколько лет {name}?*\n\n"
        f"Напишите возраст (просто цифру)",
        parse_mode='Markdown'
    )
    
    return GETTING_AGE


async def age_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получен возраст"""
    age_text = update.message.text.strip()
    
    # Проверяем что это цифра
    try:
        age = int(age_text)
        if age < 1 or age > 12:
            raise ValueError
    except:
        await update.message.reply_text(
            "⚠️ Пожалуйста, напишите возраст цифрой от 1 до 12.\n"
            "Например: 5"
        )
        return GETTING_AGE
    
    context.user_data['age'] = age
    
    # Переходим к фото
    keyboard = [
        [InlineKeyboardButton("📸 Загрузить фото", callback_data="want_photo")],
        [InlineKeyboardButton("⏭️ Пропустить", callback_data="skip_photo")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"📸 *Хотите, чтобы герой был похож на вашего ребёнка?*\n\n"
        f"Загрузите фото, и я проанализирую внешность:\n"
        f"• Цвет волос\n"
        f"• Цвет глаз\n"
        f"• Особенности (веснушки, очки)\n\n"
        f"Или пропустите — создам типичного персонажа.",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )
    
    return GETTING_PHOTO


async def want_photo_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пользователь хочет загрузить фото"""
    query = update.callback_query
    await query.answer()
    
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=(
            "📸 Отлично! Загрузите фото ребёнка.\n\n"
            "💡 Для лучшего результата:\n"
            "• Фото анфас (лицом к камере)\n"
            "• Хорошее освещение\n"
            "• Ребёнок один на фото"
        )
    )
    
    return GETTING_PHOTO


async def photo_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получено фото"""
    photo_file = await update.message.photo[-1].get_file()
    
    # Сохраняем фото
    user_id = update.effective_user.id
    photo_path = f"temp_photo_{user_id}.jpg"
    await photo_file.download_to_drive(photo_path)
    
    context.user_data['photo_path'] = photo_path
    log_event('photo_uploaded', update.effective_user.id)
    
    # Переходим к оплате
    await process_payment(update, context)
    return PAYMENT


async def skip_photo_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пользователь пропустил фото"""
    query = update.callback_query
    await query.answer()
    log_event('photo_skipped', update.effective_user.id)
    
    context.user_data['photo_path'] = None
    
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text="Хорошо! Создам персонажа без фото."
    )
    
    # Переходим к оплате
    await process_payment(update, context)
    return PAYMENT


async def process_payment(update, context):
    """Обработка оплаты - YOOKASSA ИНТЕГРАЦИЯ"""
    
    # Получаем данные
    name = context.user_data['name']
    age = context.user_data['age']
    gender = context.user_data['gender']
    theme = context.user_data['theme']
    user_id = update.effective_user.id
    
    # Создаём заказ в БД
    order_id = db.create_order(
        user_id=user_id,
        theme=theme,
        child_name=name,
        child_age=age,
        gender=gender,
        photo_description=context.user_data.get('photo_description')
    )
    context.user_data['order_id'] = order_id
    
    # Обновляем статистику
    db.update_daily_stats(total_orders=1)
    
    if not PAYMENT_ENABLED:
        # Тестовый режим - генерируем сразу
        if update.message:
            await update.message.reply_text(
                "⚠️ *ТЕСТОВЫЙ РЕЖИМ*\n"
                "Оплата отключена. Генерирую книгу бесплатно...",
                parse_mode='Markdown'
            )
        else:
            await update.callback_query.message.reply_text(
                "⚠️ *ТЕСТОВЫЙ РЕЖИМ*\n"
                "Оплата отключена. Генерирую книгу бесплатно...",
                parse_mode='Markdown'
            )
        
        await start_generation(update, context)
        return ConversationHandler.END
    
    # 💰 СПЕЦИАЛЬНАЯ ЦЕНА ДЛЯ ВЛАДЕЛЬЦА
    user_username = update.effective_user.username
    if user_username and user_username.lower() == "dim4eg86":
        price = 5  # Тестовая цена для владельца
    else:
        price = BOOK_PRICE  # Обычная цена 299₽
    
    # СОЗДАЁМ ПЛАТЁЖ YOOKASSA
    payment_data = create_payment(
        amount=price,
        description=f"Персональная сказка про {name}",
        return_url=f"https://t.me/{BOT_USERNAME}",
        customer_email="noreply@storybook.ru"  # Фиктивный email для чека
    )
    
    if not payment_data:
        # Ошибка создания платежа
        chat_id = update.callback_query.message.chat_id if update.callback_query else update.message.chat_id
        await context.bot.send_message(
            chat_id=chat_id,
            text="❌ Ошибка создания платежа. Попробуйте позже или напишите @your_support"
        )
        return ConversationHandler.END
    
    # Сохраняем платёж в БД
    db.create_payment(
        payment_id=payment_data['id'],
        order_id=order_id,
        user_id=user_id,
        amount=price,  # Используем персональную цену
        payment_url=payment_data['confirmation_url']
    )
    
    context.user_data['payment_id'] = payment_data['id']
    log_event('payment_created', user_id)
    
    # ОТПРАВЛЯЕМ КНОПКУ ОПЛАТЫ
    keyboard = [[InlineKeyboardButton(
        f"💳 Оплатить {price}₽",  # Используем персональную цену
        url=payment_data['confirmation_url']
    )]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    chat_id = update.callback_query.message.chat_id if update.callback_query else update.message.chat_id
    
    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            f"💰 *Стоимость: {price}₽*\n\n"  # Используем персональную цену
            f"📖 Сказка про {name}\n"
            f"🎨 10 страниц с иллюстрациями Disney/Pixar качества\n"
            f"📄 PDF файл для печати\n\n"
            f"После оплаты книга будет готова через 5 минут!"
        ),
        parse_mode='Markdown',
        reply_markup=reply_markup
    )
    
    # Ждём оплату
    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            "⏳ Ожидаю оплату...\n\n"
            "После оплаты нажмите /check чтобы проверить статус.\n"
            "Или просто подождите - я проверю автоматически!"
        )
    )
    
    # Запускаем автопроверку оплаты (каждые 10 секунд, макс 10 минут)
    context.job_queue.run_repeating(
        check_payment_status,
        interval=10,
        first=10,
        data={
            'payment_id': payment_data['id'],
            'chat_id': user_id,
            'user_data': context.user_data.copy()
        },
        name=f"payment_{payment_data['id']}"
    )
    
    return PAYMENT


async def check_payment_status(context: ContextTypes.DEFAULT_TYPE):
    """Автоматическая проверка статуса платежа"""
    job = context.job
    payment_id = job.data['payment_id']
    chat_id = job.data['chat_id']
    user_data = job.data['user_data']
    
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
        db.update_order_status(user_data['order_id'], 'paid')
        db.update_daily_stats(revenue=BOOK_PRICE)
        
        # Останавливаем проверку
        job.schedule_removal()
        
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
        
        await start_generation(temp_update, temp_context)


async def start_generation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запускает генерацию книги"""
    
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
        # ГЕНЕРИРУЕМ КНИГУ
        pdf_path = create_storybook_v2(
            child_name=name,
            child_age=age,
            gender=gender,
            theme_id=theme,
            photo_path=photo_path
        )
        
        # Обновляем заказ в БД
        if order_id:
            db.update_order_status(order_id, 'completed', pdf_path)
            db.update_daily_stats(completed_orders=1)
        
        # Удаляем статусное сообщение
        await status_message.delete()
        
        # Отправляем PDF
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
        
        # Удаляем временное фото если было
        if photo_path and os.path.exists(photo_path):
            os.remove(photo_path)
        
    except Exception as e:
        await status_message.delete()
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ Произошла ошибка при создании книги:\n\n`{str(e)}`\n\n"
                 "Попробуйте ещё раз или обратитесь в поддержку.",
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
            db.update_daily_stats(revenue=BOOK_PRICE)
        
        await start_generation(update, context)
    else:
        await update.message.reply_text(
            "⏳ Платёж ещё не оплачен.\n\n"
            "Пожалуйста, завершите оплату по ссылке выше."
        )


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статистика бота - только для админа"""
    user_id = update.effective_user.id
    
    # Проверка на админа
    if ADMIN_ID and user_id != ADMIN_ID:
        await update.message.reply_text("⛔ Доступ запрещён")
        return
    
    # Получаем статистику
    stats = db.get_total_stats()
    stats_7d = db.get_stats(days=7)
    
    text = (
        "📊 *Статистика бота:*\n\n"
        f"👥 Всего пользователей: {stats['total_users']}\n"
        f"📦 Всего заказов: {stats['total_orders']}\n"
        f"✅ Завершённых: {stats['completed_orders']}\n"
        f"💰 Выручка: {stats['revenue']}₽\n"
        f"📈 Конверсия: {stats['conversion']:.1f}%\n\n"
        "*Последние 7 дней:*\n"
    )
    
    for day in stats_7d:
        text += (
            f"\n{day['date']}:\n"
            f"  Новых: {day['new_users']} | "
            f"Заказов: {day['total_orders']} | "
            f"Выручка: {day['revenue']}₽"
        )
    
    await update.message.reply_text(text, parse_mode='Markdown')


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена разговора"""
    await update.message.reply_text(
        "Операция отменена. Напишите /start чтобы начать заново."
    )
    return ConversationHandler.END




async def myid_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать свой user_id"""
    user_id = update.effective_user.id
    username = update.effective_user.username or "нет username"
    first_name = update.effective_user.first_name or ""
    
    await update.message.reply_text(
        f"👤 *Твои данные:*\n\n"
        f"🆔 User ID: `{user_id}`\n"
        f"📝 Username: @{username}\n"
        f"👋 Имя: {first_name}",
        parse_mode='Markdown'
    )


async def analytics_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать аналитику (только для админа)"""
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Эта команда только для администратора")
        return
    
    try:
        import psycopg2
        import os
        
        # Подключаемся к PostgreSQL напрямую
        conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
        cursor = conn.cursor()
        
        # Статистика из БД
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM orders")
        total_orders = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM orders WHERE status = 'paid'")
        paid_orders = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM orders WHERE status = 'pending'")
        pending_orders = cursor.fetchone()[0]
        
        # Доход - сумма всех payments (туда попадают только созданные платежи)
        cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM payments")
        result = cursor.fetchone()
        revenue = int(result[0]) if result and result[0] else 0
        
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
        write_timeout=30.0,          # Таймаут записи
        pool_timeout=15.0            # Таймаут получения соединения
    )
    
    application = Application.builder().token(BOT_TOKEN).request(request).build()
    
    # Handler для сообщений в поддержку (ПЕРВЫМ! group=-1)
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
            GETTING_PHOTO: [
                CallbackQueryHandler(want_photo_callback, pattern='^want_photo$'),
                CallbackQueryHandler(skip_photo_callback, pattern='^skip_photo$'),
                MessageHandler(filters.PHOTO, photo_received)
            ],
            PAYMENT: []
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    application.add_handler(conv_handler)
    
    # Handlers для примеров, инструкции и поддержки (вне conversation)
    application.add_handler(CallbackQueryHandler(show_examples_callback, pattern='^show_examples$'))
    application.add_handler(CallbackQueryHandler(how_it_works_callback, pattern='^how_it_works$'))
    application.add_handler(CallbackQueryHandler(support_callback, pattern='^support$'))
    application.add_handler(CallbackQueryHandler(cancel_support_callback, pattern='^cancel_support$'))
    
    # Handlers для кнопок админа в поддержке
    application.add_handler(CallbackQueryHandler(admin_reply_callback, pattern='^admin_reply_'))
    application.add_handler(CallbackQueryHandler(quick_reply_callback, pattern='^quick_'))
    
    # Команды
    application.add_handler(CommandHandler('check', check_payment_command))
    application.add_handler(CommandHandler('stats', stats_command))
    application.add_handler(CommandHandler('myid', myid_command))
    application.add_handler(CommandHandler('analytics', analytics_command))
    application.add_handler(CommandHandler('reply', reply_command))  # Для админа
    
    # ✅ ПАТЧ СТАБИЛЬНОСТИ: Регистрируем глобальный обработчик ошибок
    application.add_error_handler(error_handler)
    
    logger.info("=" * 60)
    logger.info("🚀 БОТ ЗАПУЩЕН С ПАТЧЕМ СТАБИЛЬНОСТИ!")
    logger.info("=" * 60)
    logger.info("✅ Error handler: включён")
    logger.info("✅ Таймауты: 30 сек (read/write), 15 сек (connect)")
    logger.info("✅ Connection pool: 30 соединений")
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
