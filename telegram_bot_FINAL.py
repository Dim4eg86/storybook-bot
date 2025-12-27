#!/usr/bin/env python3
"""
Telegram бот для создания персонализированных детских книг
✅ С ПАТЧЕМ СТАБИЛЬНОСТИ для высоких нагрузок (40k+ охват)
"""

import os
import sqlite3
from datetime import datetime
import asyncio

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import (
    Application, 
    CommandHandler, 
    CallbackQueryHandler, 
    MessageHandler, 
    PreCheckoutQueryHandler,
    filters, 
    ContextTypes,
    ConversationHandler
)

# ✅ ПАТЧ СТАБИЛЬНОСТИ: Импорты для устойчивости к ошибкам
from telegram.request import HTTPXRequest
import logging
import traceback

# ✅ ПАТЧ СТАБИЛЬНОСТИ: Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Переменные окружения
BOT_TOKEN = os.getenv('BOT_TOKEN')
YOOKASSA_SECRET_KEY = os.getenv('YOOKASSA_SECRET_KEY')
YOOKASSA_SHOP_ID = os.getenv('YOOKASSA_SHOP_ID')
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
REPLICATE_API_TOKEN = os.getenv('REPLICATE_API_TOKEN')

# Состояния conversation
WAITING_NAME, WAITING_AGE, WAITING_THEME, WAITING_PHOTO = range(4)

# Темы для книг
THEMES = {
    'princess': '👸 Принцесса',
    'space': '🚀 Космос',
    'ocean': '🌊 Океан',
    'forest': '🌲 Лес',
    'city': '🏙️ Город',
    'magic': '✨ Магия'
}

# Инициализация базы данных
def init_db():
    """Создание таблиц базы данных"""
    conn = sqlite3.connect('storybook_bot.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            order_id TEXT PRIMARY KEY,
            user_id INTEGER,
            child_name TEXT,
            child_age INTEGER,
            theme TEXT,
            photo_path TEXT,
            status TEXT DEFAULT 'pending',
            amount REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    
    conn.commit()
    conn.close()

# Сохранение пользователя
def save_user(user_id: int, username: str = None, first_name: str = None):
    """Сохранение информации о пользователе"""
    conn = sqlite3.connect('storybook_bot.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT OR IGNORE INTO users (user_id, username, first_name)
        VALUES (?, ?, ?)
    ''', (user_id, username, first_name))
    
    conn.commit()
    conn.close()

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    save_user(user.id, user.username, user.first_name)
    
    keyboard = [
        [InlineKeyboardButton("📚 Создать книгу", callback_data='create_storybook')],
        [InlineKeyboardButton("ℹ️ О боте", callback_data='about')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"👋 Привет, {user.first_name}!\n\n"
        "🎨 Я создаю персонализированные детские книги с иллюстрациями!\n\n"
        "✨ Особенности:\n"
        "• Ребёнок - главный герой\n"
        "• Профессиональные иллюстрации Disney/Pixar\n"
        "• Уникальная история\n"
        "• PDF формат для печати\n\n"
        "💰 Цена: 449₽",
        reply_markup=reply_markup
    )

# Начало создания книги
async def create_storybook_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало процесса создания книги"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "📝 Как зовут ребёнка?\n\n"
        "Напишите имя (например: Маша, Саша, Артём)"
    )
    
    return WAITING_NAME

# Получение имени
async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение имени ребёнка"""
    context.user_data['child_name'] = update.message.text.strip()
    
    await update.message.reply_text(
        "👶 Сколько лет ребёнку?\n\n"
        "Напишите возраст (например: 5)"
    )
    
    return WAITING_AGE

# Получение возраста
async def receive_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение возраста ребёнка"""
    try:
        age = int(update.message.text.strip())
        if age < 1 or age > 12:
            await update.message.reply_text(
                "❌ Возраст должен быть от 1 до 12 лет.\n"
                "Попробуйте ещё раз:"
            )
            return WAITING_AGE
        
        context.user_data['child_age'] = age
        
        # Показываем темы
        keyboard = []
        for theme_id, theme_name in THEMES.items():
            keyboard.append([InlineKeyboardButton(theme_name, callback_data=f'theme_{theme_id}')])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🎨 Выберите тему книги:",
            reply_markup=reply_markup
        )
        
        return WAITING_THEME
        
    except ValueError:
        await update.message.reply_text(
            "❌ Введите число.\n"
            "Попробуйте ещё раз:"
        )
        return WAITING_AGE

# Получение темы
async def receive_theme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение темы книги"""
    query = update.callback_query
    await query.answer()
    
    theme = query.data.replace('theme_', '')
    context.user_data['theme'] = theme
    
    await query.edit_message_text(
        "📸 Загрузите фото ребёнка\n\n"
        "• Фото лица крупным планом\n"
        "• Хорошее освещение\n"
        "• Анфас (прямо в камеру)\n\n"
        "Отправьте фото:"
    )
    
    return WAITING_PHOTO

# Получение фото
async def receive_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение фото ребёнка"""
    if not update.message.photo:
        await update.message.reply_text(
            "❌ Пожалуйста, отправьте фото.\n"
            "Попробуйте ещё раз:"
        )
        return WAITING_PHOTO
    
    # Сохраняем фото
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    
    photo_path = f"photos/{update.effective_user.id}_{datetime.now().timestamp()}.jpg"
    os.makedirs('photos', exist_ok=True)
    await file.download_to_drive(photo_path)
    
    context.user_data['photo_path'] = photo_path
    
    # Показываем счёт на оплату
    await show_invoice(update, context)
    
    return ConversationHandler.END

# Показ счёта
async def show_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправка счёта на оплату"""
    child_name = context.user_data['child_name']
    child_age = context.user_data['child_age']
    theme = THEMES[context.user_data['theme']]
    
    # Создаём заказ в базе
    order_id = f"order_{update.effective_user.id}_{datetime.now().timestamp()}"
    
    conn = sqlite3.connect('storybook_bot.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO orders (order_id, user_id, child_name, child_age, theme, photo_path, amount)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (order_id, update.effective_user.id, child_name, child_age, 
          context.user_data['theme'], context.user_data['photo_path'], 449))
    conn.commit()
    conn.close()
    
    context.user_data['order_id'] = order_id
    
    # Отправляем счёт
    await context.bot.send_invoice(
        chat_id=update.effective_user.id,
        title="Персонализированная детская книга",
        description=f"Книга для {child_name}, {child_age} лет\nТема: {theme}",
        payload=order_id,
        provider_token=YOOKASSA_SECRET_KEY,
        currency='RUB',
        prices=[LabeledPrice("Книга", 44900)],  # в копейках
        start_parameter='create_storybook'
    )

# Pre-checkout
async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверка перед оплатой"""
    query = update.pre_checkout_query
    await query.answer(ok=True)

# Успешная оплата
async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка успешной оплаты"""
    payment = update.message.successful_payment
    order_id = payment.invoice_payload
    
    # Обновляем статус заказа
    conn = sqlite3.connect('storybook_bot.db')
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE orders SET status = 'paid' WHERE order_id = ?
    ''', (order_id,))
    conn.commit()
    
    # Получаем данные заказа
    cursor.execute('''
        SELECT child_name, child_age, theme, photo_path 
        FROM orders WHERE order_id = ?
    ''', (order_id,))
    child_name, child_age, theme, photo_path = cursor.fetchone()
    conn.close()
    
    await update.message.reply_text(
        "✅ Оплата прошла успешно!\n\n"
        "🎨 Начинаю создавать книгу...\n"
        "⏱️ Это займёт 5-7 минут.\n\n"
        "Я пришлю готовую книгу в этот чат!"
    )
    
    # Запускаем создание книги в фоне
    asyncio.create_task(generate_book(update, context, order_id, child_name, child_age, theme, photo_path))

# Генерация книги (заглушка - нужно подключить твою функцию)
async def generate_book(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                       order_id: str, child_name: str, child_age: int, theme: str, photo_path: str):
    """Генерация книги"""
    try:
        # ВАЖНО: Здесь нужно вызвать твою функцию create_storybook_v2
        # Раскомментируй и адаптируй:
        # 
        # from generate_storybook_v2 import create_storybook_v2
        # pdf_path = await create_storybook_v2(child_name, child_age, theme, photo_path)
        # 
        # await context.bot.send_document(
        #     chat_id=update.effective_user.id,
        #     document=open(pdf_path, 'rb'),
        #     caption=f"📚 Готово! Книга для {child_name}!"
        # )
        
        # Временная заглушка:
        await asyncio.sleep(5)
        await context.bot.send_message(
            chat_id=update.effective_user.id,
            text=f"📚 Книга готова! (это заглушка, подключи generate_storybook_v2.py)"
        )
        
    except Exception as e:
        logger.error(f"Error generating book: {e}")
        logger.error(traceback.format_exc())
        await context.bot.send_message(
            chat_id=update.effective_user.id,
            text="❌ Произошла ошибка при создании книги. Свяжитесь с поддержкой."
        )

# О боте
async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Информация о боте"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data='back_to_start')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "ℹ️ **О боте**\n\n"
        "Я создаю персонализированные детские книги!\n\n"
        "✨ **Что я умею:**\n"
        "• Генерирую уникальную историю\n"
        "• Создаю 10 иллюстраций Disney/Pixar\n"
        "• Делаю ребёнка главным героем\n"
        "• Формирую PDF для печати\n\n"
        "💰 **Цена:** 449₽\n"
        "⏱️ **Время создания:** 5-7 минут",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# Возврат в главное меню
async def back_to_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат в главное меню"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("📚 Создать книгу", callback_data='create_storybook')],
        [InlineKeyboardButton("ℹ️ О боте", callback_data='about')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "👋 Главное меню\n\n"
        "Выберите действие:",
        reply_markup=reply_markup
    )

# Отмена
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена создания книги"""
    await update.message.reply_text(
        "❌ Создание книги отменено.\n\n"
        "Отправьте /start чтобы начать заново."
    )
    return ConversationHandler.END

# ✅ ПАТЧ СТАБИЛЬНОСТИ: Глобальный обработчик ошибок
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Глобальный обработчик ошибок
    Предотвращает падение бота при сетевых ошибках и высоких нагрузках
    """
    logger.error(f"Exception while handling an update: {context.error}")
    
    # Логируем полный traceback для debugging
    logger.error("".join(traceback.format_exception(None, context.error, context.error.__traceback__)))
    
    # Если есть сообщение от пользователя - отвечаем
    if update and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "⚠️ Произошла временная ошибка. Попробуйте через минуту или напишите /start"
            )
        except Exception as e:
            logger.error(f"Could not send error message to user: {e}")
    
    # НЕ падаем - просто логируем и продолжаем работу
    return

# Главная функция
def main():
    """Запуск бота"""
    logger.info("🔧 Инициализация бота...")
    
    # Проверяем обязательные переменные окружения
    if not BOT_TOKEN:
        logger.error("❌ КРИТИЧЕСКАЯ ОШИБКА: BOT_TOKEN не установлен!")
        logger.error("   Установите переменную окружения BOT_TOKEN в Railway")
        return
    
    if not YOOKASSA_SECRET_KEY:
        logger.error("❌ КРИТИЧЕСКАЯ ОШИБКА: YOOKASSA_SECRET_KEY не установлен!")
        logger.error("   Установите переменную окружения YOOKASSA_SECRET_KEY в Railway")
        return
    
    if not ANTHROPIC_API_KEY:
        logger.warning("⚠️ ВНИМАНИЕ: ANTHROPIC_API_KEY не установлен!")
        logger.warning("   Генерация историй не будет работать")
    
    if not REPLICATE_API_TOKEN:
        logger.warning("⚠️ ВНИМАНИЕ: REPLICATE_API_TOKEN не установлен!")
        logger.warning("   Генерация иллюстраций не будет работать")
    
    # Инициализация БД
    init_db()
    logger.info("✅ База данных инициализирована")
    
    # ✅ ПАТЧ СТАБИЛЬНОСТИ: Настраиваем увеличенные таймауты для высоких нагрузок
    logger.info("🔧 Настройка увеличенных таймаутов для высоких нагрузок...")
    request = HTTPXRequest(
        connection_pool_size=30,     # Больше одновременных соединений (было 8)
        read_timeout=30.0,           # Увеличено с 5 до 30 секунд
        write_timeout=30.0,          # Увеличено с 5 до 30 секунд
        connect_timeout=15.0,        # Увеличено с 5 до 15 секунд
        pool_timeout=15.0            # Таймаут для получения соединения из пула
    )
    
    # Создаём приложение с кастомными настройками
    logger.info("🔧 Создание приложения с патчем стабильности...")
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .request(request)
        .build()
    )
    
    # Conversation handler для создания книги
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(create_storybook_start, pattern='^create_storybook$')],
        states={
            WAITING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)],
            WAITING_AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_age)],
            WAITING_THEME: [CallbackQueryHandler(receive_theme, pattern='^theme_')],
            WAITING_PHOTO: [MessageHandler(filters.PHOTO, receive_photo)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    # Регистрация обработчиков
    logger.info("🔧 Регистрация обработчиков...")
    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(about, pattern='^about$'))
    application.add_handler(CallbackQueryHandler(back_to_start, pattern='^back_to_start$'))
    application.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))
    
    # ✅ ПАТЧ СТАБИЛЬНОСТИ: Регистрируем глобальный обработчик ошибок
    logger.info("🛡️ Регистрация глобального обработчика ошибок...")
    application.add_error_handler(error_handler)
    
    logger.info("=" * 60)
    logger.info("🚀 БОТ ЗАПУЩЕН С ПАТЧЕМ СТАБИЛЬНОСТИ!")
    logger.info("=" * 60)
    logger.info("✅ Error handler: включён")
    logger.info("✅ Таймауты: 30 сек (read/write), 15 сек (connect)")
    logger.info("✅ Connection pool: 30 соединений")
    logger.info("✅ Drop pending updates: включено")
    logger.info("=" * 60)
    
    # ✅ ПАТЧ СТАБИЛЬНОСТИ: Запускаем с параметрами для стабильности
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,  # Игнорируем старые сообщения после перезапуска
        timeout=30                   # Увеличенный таймаут для long polling
    )

if __name__ == '__main__':
    main()
