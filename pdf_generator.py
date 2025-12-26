#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDF генератор - версия для бота
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import textwrap
import os

# Регистрируем шрифт с поддержкой кириллицы
fonts_registered = False
font_regular = 'Helvetica'
font_bold = 'Helvetica-Bold'

print("🔤 Загружаю шрифт с поддержкой кириллицы...")

# Пути к шрифтам (в порядке приоритета)
FONT_PATHS = [
    # Liberation Sans - ТОЧНО есть на Railway!
    ('/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
     '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf'),
    # DejaVu Sans (запасной)
    ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 
     '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'),
    # Windows Arial (для локальной разработки)
    ('C:/Windows/Fonts/arial.ttf', 'C:/Windows/Fonts/arialbd.ttf'),
]

for regular_path, bold_path in FONT_PATHS:
    try:
        if os.path.exists(regular_path) and os.path.exists(bold_path):
            # Регистрируем шрифты
            pdfmetrics.registerFont(TTFont('BookFont', regular_path))
            pdfmetrics.registerFont(TTFont('BookFont-Bold', bold_path))
            
            # Регистрируем семейство
            pdfmetrics.registerFontFamily('BookFont',
                                         normal='BookFont',
                                         bold='BookFont-Bold')
            
            font_regular = 'BookFont'
            font_bold = 'BookFont-Bold'
            fonts_registered = True
            
            font_name = os.path.basename(regular_path).replace('.ttf', '')
            print(f"✅ Загружен шрифт: {font_name}")
            break
    except Exception as e:
        print(f"⚠️ Не удалось загрузить {regular_path}: {e}")
        continue

if not fonts_registered:
    print("❌ КРИТИЧЕСКАЯ ОШИБКА: Шрифты с кириллицей не найдены!")
    print("❌ Используется Helvetica - текст будет КВАДРАТАМИ!")
    print("❌ Свяжитесь с разработчиком!")

def draw_smooth_gradient(c, width, height, overlay_height):
    """Плавный ТЁМНЫЙ градиент для хорошей читаемости"""
    for i in range(300):
        y_pos = (overlay_height / 300) * i
        strip_height = (overlay_height / 300) + 0.5
        progress = i / 300
        alpha = 0.95 * (1 - progress) ** 1.2  # Было 0.85, стало 0.95 - ТЕМНЕЕ!
        
        c.setFillColor(HexColor('#000000'))
        c.setFillAlpha(alpha)
        c.rect(0, y_pos, width, strip_height, fill=1, stroke=0)
    
    c.setFillAlpha(1.0)

def draw_text_with_outline(c, x, y, text, font, size):
    """Текст с ТОЛСТОЙ обводкой для детской книги"""
    c.setFont(font, size)
    
    # Обводка - ТОЛЩЕ для лучшей читаемости!
    c.setFillColor(HexColor('#000000'))
    offsets = [
        (-3, -3), (-1, -3), (1, -3), (3, -3),
        (-3, -1),           (1, -1), (3, -1),
        (-3,  1),           (1,  1), (3,  1),
        (-3,  3), (-1,  3), (1,  3), (3,  3)
    ]
    
    for dx, dy in offsets:
        c.drawCentredString(x + dx, y + dy, text)
    
    # Основной текст - белый
    c.setFillColor(HexColor('#ffffff'))
    c.drawCentredString(x, y, text)

def create_book_from_data(child_name, child_age, scenes_data, output_path, theme_title="ГОРОДЕ РОБОТОВ"):
    """
    Создаёт PDF из готовых данных
    
    Параметры:
    - child_name: имя ребёнка
    - child_age: возраст
    - scenes_data: список сцен с image, text
    - output_path: путь для сохранения PDF
    - theme_title: название темы для обложки (например, "ГОРОДЕ РОБОТОВ")
    """
    
    print(f"📄 Создаю PDF: {output_path}")
    print(f"🔤 Используемый шрифт: {font_regular}")
    
    # Проверяем что все файлы существуют
    from PIL import Image
    for scene in scenes_data:
        if not os.path.exists(scene['image']):
            raise FileNotFoundError(f"Файл не найден: {scene['image']}")
        
        # Проверяем что файл валидный
        try:
            img = Image.open(scene['image'])
            img.verify()
        except Exception as e:
            raise ValueError(f"Повреждён файл {scene['image']}: {e}")
    
    c = canvas.Canvas(output_path, pagesize=A4)
    width, height = A4
    
    # ========================================================================
    # ТИТУЛЬНАЯ
    # ========================================================================
    
    # Фон - первая иллюстрация (растянуть на всю страницу БЕЗ серых полос!)
    c.drawImage(scenes_data[0]['image'], 0, 0, 
                width=width, height=height,
                preserveAspectRatio=False)  # Растягиваем!
    
    # Градиент сверху (УМЕНЬШЕН с 12см до 8см - не закрывает лицо!)
    gradient_height = 8*cm  # Было 12*cm
    for i in range(300):
        y_pos = height - (i * (gradient_height / 300))
        strip_height = (gradient_height / 300) + 0.5
        progress = i / 300
        alpha = 0.75 * (progress ** 1.5)
        
        c.setFillColor(HexColor('#000000'))
        c.setFillAlpha(alpha)
        c.rect(0, y_pos, width, strip_height, fill=1, stroke=0)
    
    c.setFillAlpha(1.0)
    
    # Заголовок - ДИНАМИЧЕСКИЙ!
    # Разбиваем theme_title на строки (если длинный)
    title_lines = theme_title.split('\n') if '\n' in theme_title else [theme_title]
    
    y_start = height - 4*cm  # Чуть выше (было 5cm)
    
    # Первая строка - имя
    draw_text_with_outline(c, width/2, y_start, f"{child_name.upper()}", 
                          font_bold, 56)
    
    # Остальные строки - название темы
    for i, line in enumerate(title_lines):
        y_pos = y_start - (1.8*cm * (i + 1))
        draw_text_with_outline(c, width/2, y_pos, line.upper(),
                              font_bold, 56)
    
    # ========================================================================
    # СЦЕНЫ
    # ========================================================================
    
    for scene in scenes_data:
        c.showPage()
        
        # Фон - растягиваем на всю страницу БЕЗ серых полос!
        c.drawImage(scene['image'], 0, 0, 
                   width=width, height=height,
                   preserveAspectRatio=False)  # Растягиваем!
        
        # Градиент снизу (выше чтобы текст было видно лучше)
        draw_smooth_gradient(c, width, height, 10*cm)  # Было 9cm, стало 10cm
        
        # Текст с обводкой (КРУПНЫЙ детский шрифт!)
        lines = textwrap.wrap(scene['text'], width=40)  # Было 45, стало 40 для крупного шрифта
        
        y_offset = 10*cm - 2.5*cm  # Было 9cm
        for line in lines[:7]:  # Было 8, стало 7 строк из-за крупного шрифта
            draw_text_with_outline(c, width/2, y_offset, line, font_regular, 22)  # Было 20, стало 22!
            y_offset -= 1.1*cm  # Увеличил межстрочный интервал (было 1.0cm)
    
    # ========================================================================
    # ФИНАЛ
    # ========================================================================
    
    c.showPage()
    
    # Градиент
    for i in range(100):
        progress = i / 100
        r = int(10 + (30 - 10) * progress)
        g = int(20 + (50 - 20) * progress)
        b = int(40 + (80 - 40) * progress)
        c.setFillColor(HexColor(f'#{r:02x}{g:02x}{b:02x}'))
        c.rect(0, height * (1 - progress), width, height/100, fill=1, stroke=0)
    
    # Звёзды
    c.setFillColor(HexColor('#FFD700'))
    import random
    random.seed(42)
    for _ in range(30):
        x = random.randint(0, int(width))
        y = random.randint(0, int(height))
        c.circle(x, y, random.choice([2, 3, 4]), fill=1, stroke=0)
    
    # Месяц
    c.setFillColor(HexColor('#FFE5B4'))
    c.circle(width - 4*cm, height - 5*cm, 1.5*cm, fill=1, stroke=0)
    c.setFillColor(HexColor('#1a3050'))
    c.circle(width - 3.3*cm, height - 5*cm, 1.5*cm, fill=1, stroke=0)
    
    # Текст
    c.setFillColor(HexColor('#FFE5B4'))
    c.setFont(font_bold, 52)
    c.drawCentredString(width/2, height/2 + 1*cm, "Конец")
    c.drawCentredString(width/2, height/2 - 1.5*cm, "сказки!")
    
    c.save()
    print(f"✅ PDF готов: {output_path}")
