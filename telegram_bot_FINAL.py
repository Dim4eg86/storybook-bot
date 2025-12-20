#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram бот для персональных сказок - ФИНАЛЬНАЯ ВЕРСИЯ
8 тем + YooKassa оплата
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    CallbackQueryHandler, ContextTypes, filters, ConversationHandler
)
import os
import json

# Импортируем генератор
from generate_storybook_v2 import create_storybook_v2

# НАСТРОЙКИ
BOT_TOKEN = "8558194892:AAFC_hreFvCX3PoqOYekUCkUhJFakDHqY9E"

# YooKassa (вставь свои ключи после регистрации)
YOOKASSA_SHOP_ID = "ТВОЙ_SHOP_ID"  # Получишь на yookassa.ru
YOOKASSA_SECRET_KEY = "ТВОЙ_SECRET_KEY"  # Получишь на yookassa.ru
PAYMENT_ENABLED = False  # Пока False, после регистрации YooKassa = True

# Цена
BOOK_PRICE = 449  # рублей

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
    
    # Кнопки - ПО ОДНОЙ В РЯД!
    keyboard = [
        [InlineKeyboardButton("⭐ Создать сказку", callback_data="create_story")],
        [InlineKeyboardButton("📚 Посмотреть примеры", callback_data="show_examples")],
        [InlineKeyboardButton("❓ Как это работает?", callback_data="how_it_works")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Отправляем welcome картинку С КНОПКАМИ (тогда ширина будет одинаковая!)
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
    """Показываем примеры работ - КНОПКИ СО ССЫЛКАМИ!"""
    query = update.callback_query
    await query.answer()
    
    # Кнопки с примерами (ПРАВИЛЬНЫЕ ССЫЛКИ!)
    keyboard = [
        [InlineKeyboardButton("🦕 Саша с динозаврами", url="https://drive.google.com/file/d/1FIVkCSMI-mjhXX236O8FYhiHCJB4_N_C/preview")],
        [InlineKeyboardButton("🧚 Юлиана в стране фей", url="https://drive.google.com/file/d/1CphV74SQA-s4q3NwsBQNW92gHla-DLLS/preview")],
        [InlineKeyboardButton("⭐ Создать свою сказку", callback_data="create_story")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Отправляем с кнопками
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
    """Показываем как работает бот"""
    query = update.callback_query
    await query.answer()
    
    # Не редактируем картинку - просто отправляем новое сообщение!
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
    
    # Кнопка создать
    keyboard = [[InlineKeyboardButton("⭐ Создать сказку", callback_data="create_story")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text="Готовы создать сказку?",
        reply_markup=reply_markup
    )

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
    
    # Отправляем новое сообщение (не редактируем картинку!)
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
    
    # Отправляем новое сообщение вместо редактирования
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=f"✅ Тема: {theme_name}\n\n👶 Кто будет главным героем?",
        reply_markup=reply_markup
    )
    
    return CHOOSING_GENDER

async def gender_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пол выбран - переходим к имени (БЕЗ ПРИМЕРОВ!)"""
    query = update.callback_query
    await query.answer()
    
    gender = "boy" if query.data == "gender_boy" else "girl"
    context.user_data['gender'] = gender
    
    gender_ru = "мальчик" if gender == "boy" else "девочка"
    
    # Отправляем новое сообщение
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=f"Отлично! Герой — {gender_ru} 👍\n\n📝 *Напишите имя ребёнка:*",
        parse_mode='Markdown'
    )
    
    return GETTING_NAME

async def name_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получено имя - просим возраст (ЛЮБОЙ!)"""
    name = update.message.text.strip()
    
    # Проверка имени (минимальная)
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
    """Получен возраст (любая цифра!)"""
    age_text = update.message.text.strip()
    
    # Проверяем что это цифра (любая от 1 до 12)
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
    
    # Переходим к оплате
    await process_payment(update, context)
    return PAYMENT

async def skip_photo_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пользователь пропустил фото"""
    query = update.callback_query
    await query.answer()
    
    context.user_data['photo_path'] = None
    
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text="Хорошо! Создам персонажа без фото."
    )
    
    # Переходим к оплате
    await process_payment(update, context)
    return PAYMENT

async def process_payment(update, context):
    """Обработка оплаты"""
    
    name = context.user_data['name']
    
    if not PAYMENT_ENABLED:
        # Пока оплата выключена - генерируем сразу
        await update.message.reply_text(
            "⚠️ *ТЕСТОВЫЙ РЕЖИМ*\n"
            "Оплата отключена. Генерирую книгу бесплатно...",
            parse_mode='Markdown'
        ) if update.message else await update.callback_query.message.reply_text(
            "⚠️ *ТЕСТОВЫЙ РЕЖИМ*\n"
            "Оплата отключена. Генерирую книгу бесплатно...",
            parse_mode='Markdown'
        )
        
        await start_generation(update, context)
        return ConversationHandler.END
    
    # TODO: Здесь будет YooKassa оплата
    # Пока заглушка
    
    await start_generation(update, context)
    return ConversationHandler.END

async def start_generation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запускает генерацию книги"""
    
    # Получаем данные
    name = context.user_data['name']
    age = context.user_data['age']
    gender = context.user_data['gender']
    theme = context.user_data['theme']
    photo_path = context.user_data.get('photo_path')
    
    # Склоняем имя
    name_accusative = decline_name_accusative(name, gender)
    
    # Загружаем название темы
    with open('all_themes_stories.json', 'r', encoding='utf-8') as f:
        themes = json.load(f)
    theme_name = themes[theme]["name"]
    
    # Отправляем сообщение о начале
    if update.callback_query:
        chat_id = update.callback_query.message.chat_id
    else:
        chat_id = update.message.chat_id
    
    status_message = await context.bot.send_message(
        chat_id=chat_id,
        text=f"⏳ *Создаю сказку про {name_accusative}...*\n\n"
             f"📖 Тема: {theme_name}\n"
             f"✅ Выбрана история\n"
             f"🎨 Рисую 10 иллюстраций...\n"
             f"📄 Соберу PDF книгу\n\n"
             f"_Это займёт примерно 30-40 минут_",
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

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена создания"""
    await update.message.reply_text(
        "Создание отменено. Напишите /start чтобы начать заново."
    )
    return ConversationHandler.END

def main():
    """Запуск бота"""
    
    print("🤖 Запускаю Telegram бота с 8 темами...")
    
    # Увеличиваем таймауты для медленного интернета
    from telegram.request import HTTPXRequest
    request = HTTPXRequest(
        connect_timeout=30.0,
        read_timeout=30.0,
        write_timeout=30.0
    )
    
    application = Application.builder().token(BOT_TOKEN).request(request).build()
    
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
    
    # Handlers для примеров и инструкции (вне conversation)
    application.add_handler(CallbackQueryHandler(show_examples_callback, pattern='^show_examples$'))
    application.add_handler(CallbackQueryHandler(how_it_works_callback, pattern='^how_it_works$'))
    
    print("✅ Бот с 8 темами запущен!")
    application.run_polling()

if __name__ == '__main__':
    main()
