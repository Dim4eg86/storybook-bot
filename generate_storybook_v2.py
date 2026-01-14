#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Генератор персональных сказок - ГОРОД РОБОТОВ
С анализом фото и подстановкой данных
✅ ИСПРАВЛЕНО: Вертикальный формат изображений 3:4 (768x1024)
"""

import json
import random
import replicate
import os
import base64
from anthropic import Anthropic
import pymorphy3

# API ключи из переменных окружения
REPLICATE_API_TOKEN = os.environ.get("REPLICATE_API_TOKEN", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

if not ANTHROPIC_API_KEY:
    print("❌ ANTHROPIC_API_KEY не установлен!")
else:
    # Показываем первые и последние символы для проверки
    key_preview = f"{ANTHROPIC_API_KEY[:20]}...{ANTHROPIC_API_KEY[-10:]}"
    print(f"✅ ANTHROPIC_API_KEY загружен: {key_preview}")
    
if not REPLICATE_API_TOKEN:
    print("⚠️ REPLICATE_API_TOKEN не установлен!")

os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_TOKEN

# Морфологический анализатор для склонения имён
morph = pymorphy3.MorphAnalyzer()

def decline_name(name, case='accs'):
    """
    Склоняет русское имя
    
    Падежи:
    - nomn: именительный (кто?) Саша
    - gent: родительный (кого?) Саши
    - datv: дательный (кому?) Саше
    - accs: винительный (кого?) Сашу
    - ablt: творительный (кем?) Сашей
    - loct: предложный (о ком?) Саше
    """
    try:
        parsed = morph.parse(name)[0]
        inflected = parsed.inflect({case})
        if inflected:
            result = inflected.word
            # Сохраняем заглавную букву
            if name[0].isupper():
                result = result.capitalize()
            return result
    except:
        pass
    
    # Если не получилось - возвращаем как есть
    return name

def analyze_photo(photo_path, premium=False):
    """
    Анализирует фото ребёнка через Claude
    
    Args:
        photo_path: путь к фото
        premium: если True - делает СУПЕР-детальный анализ
    
    Возвращает: словарь с характеристиками
    """
    analysis_type = "ПРЕМИУМ (супер-детальный)" if premium else "стандартный"
    print(f"📸 Анализирую фото ребёнка ({analysis_type})...")
    
    # Читаем фото
    with open(photo_path, 'rb') as f:
        photo_data = base64.b64encode(f.read()).decode('utf-8')
    
    # Определяем тип файла
    ext = photo_path.lower().split('.')[-1]
    
    # Маппинг расширений на правильные media_type
    media_type_map = {
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'png': 'image/png',
        'gif': 'image/gif',
        'webp': 'image/webp'
    }
    
    media_type = media_type_map.get(ext, 'image/jpeg')
    
    # Запрос к Claude
    client = Anthropic(api_key=ANTHROPIC_API_KEY)
    
    # Для премиума - СУПЕР-детальный промпт
    if premium:
        prompt_text = """Проанализируй фото ребёнка МАКСИМАЛЬНО ДЕТАЛЬНО для создания 3D Pixar персонажа с высокой похожестью.

Ответь ТОЛЬКО в формате JSON (без markdown):
{
  "hair_color": "blonde/brown/red/dark/light brown",
  "hair_color_ru": "светлые/русые/рыжие/тёмные/светло-русые",
  "hair_style": "straight/curly/wavy/short/long",
  "hair_style_ru": "прямые/кудрявые/волнистые/короткие/длинные",
  "eye_color": "blue/brown/green/gray/hazel",
  "eye_color_ru": "голубые/карие/зелёные/серые/ореховые",
  "eye_shape": "round/almond/wide",
  "eye_shape_ru": "круглые/миндалевидные/большие",
  "face_shape": "round/oval/heart-shaped",
  "face_shape_ru": "круглое/овальное/сердечком",
  "skin_tone": "light/medium/tan/dark",
  "skin_tone_ru": "светлая/средняя/смуглая/тёмная",
  "nose_type": "small/button/normal",
  "cheeks": "chubby/normal/defined",
  "cheeks_ru": "пухлые/обычные/выраженные",
  "features": ["freckles", "dimples", "glasses", "big smile"],
  "features_ru": ["веснушки", "ямочки", "очки", "большая улыбка"],
  "age_estimate": 5,
  "overall_impression": "cheerful cute baby with bright eyes"
}

Будь максимально детальным - это для ПРЕМИУМ версии!"""
    else:
        # Стандартный анализ
        prompt_text = """Проанализируй фото ребёнка и опиши его внешность для создания персонажа.

Ответ ТОЛЬКО в формате JSON (без markdown):
{
  "hair_color": "blonde/brown/red/dark",
  "hair_color_ru": "светлые/русые/рыжие/тёмные",
  "eye_color": "blue/brown/green/gray",
  "eye_color_ru": "голубые/карие/зелёные/серые",
  "features": ["freckles", "glasses"] или [],
  "features_ru": ["веснушки", "очки"] или [],
  "age_estimate": 5-8
}

Если что-то не видно - используй "unknown"."""
    
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=800 if premium else 500,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": photo_data
                    }
                },
                {
                    "type": "text",
                    "text": prompt_text
                }
            ]
        }]
    )
    
    # Парсим ответ
    analysis_text = response.content[0].text.strip()
    # Убираем возможные markdown блоки
    if '```' in analysis_text:
        analysis_text = analysis_text.split('```')[1]
        if analysis_text.startswith('json'):
            analysis_text = analysis_text[4:]
        analysis_text = analysis_text.strip()
    
    analysis = json.loads(analysis_text)
    
    if premium:
        print(f"✅ ПРЕМИУМ анализ:")
        print(f"   Волосы: {analysis.get('hair_color_ru', 'н/д')} ({analysis.get('hair_style_ru', '')})")
        print(f"   Глаза: {analysis.get('eye_color_ru', 'н/д')} ({analysis.get('eye_shape_ru', '')})")
        print(f"   Лицо: {analysis.get('face_shape_ru', 'н/д')}, кожа: {analysis.get('skin_tone_ru', 'н/д')}")
        print(f"   Щёчки: {analysis.get('cheeks_ru', 'н/д')}")
        if analysis.get('features_ru'):
            print(f"   Особенности: {', '.join(analysis['features_ru'])}")
    else:
        print(f"✅ Анализ: {analysis['hair_color_ru']} волосы, {analysis['eye_color_ru']} глаза")
        if analysis.get('features_ru'):
            print(f"   Особенности: {', '.join(analysis['features_ru'])}")
    
    return analysis

def generate_illustration(prompt, output_path, photo_path=None, use_pulid=False):
    """
    Генерирует иллюстрацию через Flux Pro или PuLID
    ✅ ИСПРАВЛЕНО: Использует вертикальный формат 3:4 (768x1024)
    ✅ ДОБАВЛЕНО: Автоматическая обработка rate limit
    ✅ НОВОЕ: Поддержка PuLID для максимальной похожести
    
    Args:
        prompt: текстовый промпт для генерации
        output_path: путь куда сохранить изображение
        photo_path: путь к фото ребёнка (для PuLID)
        use_pulid: использовать ли PuLID (True для premium тарифа)
    """
    if use_pulid and photo_path and os.path.exists(photo_path):
        print(f"   🎭 Генерирую с PuLID (максимальная похожесть)...")
    else:
        print(f"   🎨 Генерирую иллюстрацию в формате 3:4...")
    
    import requests
    import time
    from PIL import Image
    
    max_retries = 5  # Максимум попыток
    retry_delay = 10  # Начальная задержка в секундах
    
    for attempt in range(max_retries):
        try:
            # ✅ ПРЕМИУМ: Используем Flux Kontext Pro с фото
            if use_pulid and photo_path and os.path.exists(photo_path):
                print(f"   🎭 Используем Flux Kontext Pro (премиум с сохранением лица)...")
                
                # Читаем фото
                with open(photo_path, "rb") as f:
                    photo_data = f.read()
                
                # Конвертируем в data URI для Kontext
                import base64
                photo_base64 = base64.b64encode(photo_data).decode('utf-8')
                photo_uri = f"data:image/jpeg;base64,{photo_base64}"
                
                output = replicate.run(
                    "black-forest-labs/flux-kontext-pro",
                    input={
                        "input_image": photo_uri,
                        "prompt": prompt + ". Transform this person into a Pixar 3D animated character while keeping the same facial features, maintain the face identity, preserve facial characteristics",
                        "aspect_ratio": "3:4",
                        "num_outputs": 1,
                        "output_format": "png",
                        "output_quality": 100,
                        "safety_tolerance": 2
                    }
                )
            else:
                # ✅ СТАНДАРТ: Обычный Flux Pro без фото
                output = replicate.run(
                    "black-forest-labs/flux-1.1-pro",
                    input={
                        "prompt": prompt,
                        "aspect_ratio": "3:4",  # ✅ ВЕРТИКАЛЬНЫЙ ФОРМАТ (768x1024)
                        "num_outputs": 1,
                        "output_format": "png",
                        "output_quality": 100,
                        "safety_tolerance": 5,
                        "guidance": 3.5,
                        "num_inference_steps": 28
                    }
                )
            
            # Получаем URL
            if isinstance(output, list):
                image_url = output[0]
            else:
                image_url = output
            
            print(f"   📥 Скачиваю изображение...")
            
            # Скачиваем
            response = requests.get(image_url, timeout=60, stream=True)
            response.raise_for_status()
            
            # Сохраняем
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            file_size = os.path.getsize(output_path)
            print(f"   💾 Сохранено {file_size} байт")
            
            # Проверяем целостность и размеры
            time.sleep(0.5)
            
            try:
                img = Image.open(output_path)
                img.load()
                width, height = img.size
                print(f"   ✅ Проверено: {width}x{height} пикселей")
                
                # Проверяем, что получили вертикальное изображение
                if width > height:
                    print(f"   ⚠️ ВНИМАНИЕ: Изображение {width}x{height} горизонтальное!")
                else:
                    ratio = height / width
                    print(f"   📐 Соотношение сторон: {ratio:.2f} (ожидается ~1.33 для 3:4)")
                    
            except Exception as e:
                raise ValueError(f"Файл повреждён: {e}")
            
            # ✅ Успех! Выходим из цикла retry
            return
                
        except Exception as e:
            error_str = str(e)
            
            # Проверяем rate limit ошибку
            if "429" in error_str or "throttled" in error_str.lower() or "rate limit" in error_str.lower():
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (attempt + 1)
                    print(f"   ⏳ Rate limit! Жду {wait_time} секунд... (попытка {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"   ❌ Превышен лимит попыток после {max_retries} попыток")
                    raise RuntimeError(
                        f"❌ Ошибка rate limit Replicate.\n"
                        f"Решение:\n"
                        f"1. Пополни баланс на https://replicate.com/account/billing (минимум $10)\n"
                        f"2. Или подожди несколько минут и попробуй снова\n\n"
                        f"Детали: {error_str}"
                    )
            else:
                # Другая ошибка - не пытаемся повторить
                raise RuntimeError(f"Ошибка генерации Flux Pro: {e}")

def create_storybook_v2(
    child_name,
    child_age,
    gender,  # "boy" или "girl"
    theme_id='robot_city',  # ID темы
    photo_path=None,
    story_id=None,
    plan='standard'  # ✅ НОВОЕ: 'standard' или 'premium'
):
    """
    Создаёт персональную книгу - ВЕРСИЯ 2 (все темы)
    ✅ ОБНОВЛЕНО: Изображения теперь в вертикальном формате 3:4
    ✅ НОВОЕ: Поддержка тарифов (standard/premium с PuLID)
    
    Параметры:
    - child_name: имя ребёнка
    - child_age: возраст
    - gender: "boy" или "girl"
    - theme_id: ID темы (robot_city, space, dinosaurs, underwater, fairy_land, princess, unicorns, knight)
    - photo_path: путь к фото (опционально для standard, обязательно для premium)
    - story_id: ID конкретной истории или None (случайная)
    - plan: 'standard' (обычный Flux) или 'premium' (PuLID с максимальной похожестью)
    """
    
    # Загружаем все темы
    with open('all_themes_stories.json', 'r', encoding='utf-8') as f:
        all_themes = json.load(f)
    
    # Проверяем тему
    if theme_id not in all_themes:
        raise ValueError(f"Тема '{theme_id}' не найдена!")
    
    theme_data = all_themes[theme_id]
    theme_name = theme_data['name']
    story_data = theme_data['story']
    
    plan_name = "СКАЗКА-ДВОЙНИК (ПРЕМИУМ)" if plan == "premium" else "СКАЗКА (СТАНДАРТ)"
    
    print("="*60)
    print(f"СОЗДАНИЕ: {plan_name}")
    print(f"Ребёнок: {child_name}")
    print(f"Тема: {theme_name}")
    print(f"📐 Формат изображений: 3:4 (вертикальный)")
    if plan == "premium":
        print(f"🎭 Режим: PuLID (максимальная похожесть)")
    else:
        print(f"📚 Режим: Стандартный Flux")
    print("="*60)
    print()
    
    # Для robot_city используем старую структуру
    if theme_id == 'robot_city':
        if story_id:
            story = next(s for s in story_data['stories'] if s['id'] == story_id)
        else:
            story = random.choice(story_data['stories'])
        scenes = story['scenes']
        story_title = story['title']
    else:
        # Для остальных тем - прямо scenes
        scenes = story_data['scenes']
        story_title = story_data['title']
    
    print(f"📖 История: {story_title}")
    print()
    
    # Анализируем фото если есть
    if photo_path and os.path.exists(photo_path):
        # ✅ Для премиума - СУПЕР-детальный анализ
        is_premium = (plan == 'premium')
        analysis = analyze_photo(photo_path, premium=is_premium)
        
        hair_color = analysis.get('hair_color', 'brown') + "-haired"
        hair_color_ru = analysis.get('hair_color_ru', 'русые')
        
        # Дополнительные детали
        features = ""
        if "freckles" in analysis.get('features', []):
            features += ", with freckles"
        if "glasses" in analysis.get('features', []):
            features += ", wearing glasses"
        
        # ✅ ПРЕМИУМ: используем ВСЕ детали из анализа
        if is_premium:
            if analysis.get('hair_style'):
                features += f", {analysis['hair_style']} hair"
            if analysis.get('eye_shape'):
                features += f", {analysis['eye_shape']} eyes"
            if analysis.get('face_shape'):
                features += f", {analysis['face_shape']} face"
            if analysis.get('cheeks') == 'chubby':
                features += ", chubby cheeks"
            if "dimples" in analysis.get('features', []):
                features += ", cute dimples"
            if "big smile" in analysis.get('features', []):
                features += ", big smile"
    else:
        # Без фото - типичные характеристики
        if gender == "boy":
            hair_color = "brown-haired"
            hair_color_ru = "русые"
        else:
            hair_color = "blonde"
            hair_color_ru = "светлые"
        features = ""
    
    # Переменные для подстановки
    vars_map = {
        "name": child_name,  # Именительный: Саша
        "name_acc": decline_name(child_name, 'accs'),  # Винительный: Сашу
        "name_dat": decline_name(child_name, 'datv'),  # Дательный: Саше
        "name_gen": decline_name(child_name, 'gent'),  # Родительный: Саши
        "age": str(child_age),
        "gender": gender,
        "hair_color": hair_color,
        "shirt_color": "rainbow-striped",
        "он_она": "он" if gender == "boy" else "она",
        "Он_Она": "Он" if gender == "boy" else "Она",
        "его_её": "его" if gender == "boy" else "её",
        "ему_ей": "ему" if gender == "boy" else "ей"
    }
    
    # Создаём папку для результатов
    output_dir = f"storybook_{child_name}_{theme_id}"
    os.makedirs(output_dir, exist_ok=True)
    
    # Генерируем иллюстрации
    print("🎨 Генерирую 10 вертикальных иллюстраций 3:4 (это займёт ~20 минут)...")
    print()
    
    scenes_data = []
    
    for scene in scenes:
        scene_num = scene['number']
        scene_title = scene.get('title', f'Сцена {scene_num}')
        print(f"Сцена {scene_num}/10: {scene_title}")
        
        # Подставляем переменные в текст
        text = scene['text']
        for var, value in vars_map.items():
            text = text.replace(f"{{{var}}}", value)
        
        # Подставляем переменные в промпт
        prompt = scene['image_prompt'] + features
        for var, value in vars_map.items():
            prompt = prompt.replace(f"{{{var}}}", value)
        
        # ✅ УЛУЧШЕННЫЙ ПРОМПТ для вертикального формата
        # Указываем AI, что нужна вертикальная композиция
        prompt += """, Disney Pixar animation style, 3D rendered, professional children's book illustration, 
        VERTICAL COMPOSITION, full-height portrait, character centered in frame, 
        vibrant colors, perfect faces, detailed character design, smooth skin, expressive eyes, 
        anatomically correct hands, five fingers per hand, proper hand anatomy, 
        showing character from head to toe in vertical frame,
        high quality, masterpiece"""
        
        # Генерируем иллюстрацию
        image_filename = f"scene_{scene_num:02d}.png"
        image_path = os.path.join(output_dir, image_filename)
        
        # ✅ Генерируем с учётом тарифа
        use_pulid = (plan == 'premium')
        generate_illustration(prompt, image_path, photo_path=photo_path, use_pulid=use_pulid)
        
        scenes_data.append({
            "number": scene_num,
            "title": scene_title,
            "text": text,
            "image": image_path
        })
        
        # ✅ Задержка между запросами для избежания rate limit
        # Если баланс Replicate < $5, лимит 6 запросов/минуту
        # Значит нужна пауза 10+ секунд между запросами
        if scene_num < len(scenes):  # Не ждём после последней сцены
            import time
            delay = 12 if not use_pulid else 15  # PuLID чуть медленнее
            print(f"   ⏳ Пауза {delay} секунд перед следующей генерацией...")
            time.sleep(delay)
        
        print()
    
    # Создаём PDF
    print("📄 Создаю PDF книгу с вертикальными изображениями...")
    from pdf_generator import create_book_from_data
    
    # Название файла зависит от темы
    theme_names_ru = {
        'robot_city': 'в_городе_роботов',
        'space': 'в_космосе',
        'dinosaurs': 'с_динозаврами',
        'underwater': 'под_водой',
        'fairy_land': 'в_стране_фей',
        'princess': 'в_королевстве',
        'unicorns': 'с_единорогами',
        'knight': 'рыцарь'
    }
    
    # Названия для обложки (заглавными буквами, 2-3 строки)
    theme_titles = {
        'robot_city': 'В ГОРОДЕ\nРОБОТОВ',
        'space': 'В КОСМОСЕ',
        'dinosaurs': 'С ДИНОЗАВРАМИ',
        'underwater': 'ПОД ВОДОЙ',
        'fairy_land': 'В СТРАНЕ\nФЕЙ',
        'princess': 'В КОРОЛЕВСТВЕ\nПРИНЦЕСС',
        'unicorns': 'С ЕДИНОРОГАМИ',
        'knight': 'РЫЦАРЬ'
    }
    
    theme_suffix = theme_names_ru.get(theme_id, theme_id)
    theme_title = theme_titles.get(theme_id, theme_id.upper())
    
    pdf_path = os.path.join(output_dir, f"{child_name}_{theme_suffix}.pdf")
    create_book_from_data(child_name, child_age, scenes_data, pdf_path, theme_title)
    
    print()
    print("="*60)
    print("✅ КНИГА ГОТОВА!")
    print("="*60)
    print()
    print(f"📁 Папка: {output_dir}/")
    print(f"📄 PDF: {pdf_path}")
    print(f"📐 Формат изображений: 3:4 (768x1024) - вертикальный")
    print()
    print(f"💰 Себестоимость: ~151₽ (Flux Pro + Claude)")
    print(f"   - Flux Pro: ~120₽ (10 иллюстраций 3:4)")
    print(f"   - Claude Sonnet: ~31₽ (текст + анализ)")
    print(f"💵 Цена продажи: 449₽")
    print(f"💸 Чистая прибыль: ~298₽")
    print()
    print("🎉 Изображения теперь вертикальные - никакого сжатия на телефонах!")
    print()
    
    return pdf_path

if __name__ == "__main__":
    # ПРИМЕР ИСПОЛЬЗОВАНИЯ
    
    # С фото
    # create_storybook_v2(
    #     child_name="Саша",
    #     child_age=6,
    #     gender="boy",
    #     theme_id="robot_city",
    #     photo_path="photo.jpg"
    # )
    
    # Без фото
    create_storybook_v2(
        child_name="Маша",
        child_age=5,
        gender="girl",
        theme_id="robot_city",
        photo_path=None
    )
