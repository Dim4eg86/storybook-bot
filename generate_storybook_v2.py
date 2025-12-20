#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Генератор персональных сказок - ГОРОД РОБОТОВ
С анализом фото и подстановкой данных
"""

import json
import random
import replicate
import os
import base64
from anthropic import Anthropic
import pymorphy3

# API ключи
REPLICATE_API_TOKEN = "r8_cHLoTr0IAZ1D39T8XIZTf3d7vn04cLv269jLg"
ANTHROPIC_API_KEY = "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"

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

def analyze_photo(photo_path):
    """
    Анализирует фото ребёнка через Claude
    Возвращает: словарь с характеристиками
    """
    print("📸 Анализирую фото ребёнка...")
    
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
    
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=500,
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
                    "text": """Проанализируй фото ребёнка и опиши его внешность для создания персонажа.

Ответь ТОЛЬКО в формате JSON (без markdown):
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
    
    print(f"✅ Анализ: {analysis['hair_color_ru']} волосы, {analysis['eye_color_ru']} глаза")
    if analysis['features_ru']:
        print(f"   Особенности: {', '.join(analysis['features_ru'])}")
    
    return analysis

def generate_illustration_flux(prompt, output_path):
    """Генерирует через Flux (3 попытки)"""
    import requests
    import time
    from PIL import Image
    
    max_attempts = 3
    
    for attempt in range(1, max_attempts + 1):
        try:
            if attempt > 1:
                print(f"   🔄 Flux попытка {attempt}/{max_attempts}...")
            
            output = replicate.run(
                "black-forest-labs/flux-1.1-pro",
                input={
                    "prompt": prompt,
                    "aspect_ratio": "9:16",
                    "output_format": "png",
                    "output_quality": 100,
                    "safety_tolerance": 6
                }
            )
            
            if isinstance(output, str):
                image_url = output
            elif isinstance(output, list):
                image_url = output[0]
            else:
                image_url = str(output)
            
            print(f"   📥 Скачиваю...")
            response = requests.get(image_url, timeout=60, stream=True)
            response.raise_for_status()
            
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            file_size = os.path.getsize(output_path)
            print(f"   💾 Сохранено {file_size} байт")
            
            time.sleep(0.5)
            img = Image.open(output_path)
            img.load()
            width, height = img.size
            
            if attempt > 1:
                print(f"   ✅ Flux успех! {width}x{height} (попытка {attempt})")
            else:
                print(f"   ✅ Flux успех! {width}x{height}")
            
            return True  # Успех!
            
        except Exception as e:
            error_str = str(e)
            
            if "NSFW" in error_str:
                if attempt < max_attempts:
                    print(f"   ⚠️ Flux NSFW блок (seed неудачный)")
                    time.sleep(2)
                    continue
                else:
                    # Все попытки провалились
                    return False  # Не удалось
            else:
                # Другая ошибка - пробрасываем
                raise RuntimeError(f"Flux ошибка: {error_str}")
    
    return False  # Не удалось


def generate_illustration_sdxl(prompt, output_path):
    """Генерирует через SDXL (100% работает)"""
    import requests
    import time
    from PIL import Image
    
    try:
        output = replicate.run(
            "stability-ai/sdxl:39ed52f2a78e934b3ba6e2a89f5b1c712de7dfea535525255b1aa35c5565e08b",
            input={
                "prompt": prompt,
                "width": 768,
                "height": 1344,
                "num_outputs": 1,
                "scheduler": "K_EULER",
                "num_inference_steps": 30,
                "guidance_scale": 7.5
            }
        )
        
        if isinstance(output, list):
            image_url = output[0]
        else:
            image_url = output
        
        print(f"   📥 Скачиваю...")
        response = requests.get(image_url, timeout=60, stream=True)
        response.raise_for_status()
        
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        file_size = os.path.getsize(output_path)
        print(f"   💾 Сохранено {file_size} байт")
        
        time.sleep(0.5)
        img = Image.open(output_path)
        img.load()
        width, height = img.size
        print(f"   ✅ SDXL успех! {width}x{height}")
        
        return True
        
    except Exception as e:
        raise RuntimeError(f"SDXL ошибка: {e}")


def generate_illustration(prompt, output_path):
    """ГИБРИД: Пробует Flux → если не получается → SDXL"""
    print(f"   🎨 Генерирую (Flux → SDXL fallback)...")
    
    # Пробуем Flux
    flux_success = generate_illustration_flux(prompt, output_path)
    
    if flux_success:
        return "flux"  # Вернули что использовали Flux
    
    # Flux не сработал - пробуем SDXL
    print(f"   🔄 Flux не сработал, переключаюсь на SDXL...")
    generate_illustration_sdxl(prompt, output_path)
    return "sdxl"  # Вернули что использовали SDXL

def create_storybook_v2(
    child_name,
    child_age,
    gender,  # "boy" или "girl"
    theme_id='robot_city',  # ID темы
    photo_path=None,
    story_id=None
):
    """
    Создаёт персональную книгу - FLUX ВЕРСИЯ (с обходом NSFW)
    
    Параметры:
    - child_name: имя ребёнка
    - child_age: возраст
    - gender: "boy" или "girl"
    - theme_id: ID темы
    - photo_path: путь к фото (опционально)
    - story_id: ID конкретной истории или None (случайная)
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
    
    print("="*60)
    print(f"СОЗДАНИЕ СКАЗКИ: {child_name}")
    print(f"Тема: {theme_name}")
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
        analysis = analyze_photo(photo_path)
        hair_color = analysis['hair_color'] + "-haired"
        hair_color_ru = analysis['hair_color_ru']
        
        # Дополнительные детали
        features = ""
        if "freckles" in analysis['features']:
            features += ", with freckles"
        if "glasses" in analysis['features']:
            features += ", wearing glasses"
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
    print("🎨 Генерирую 10 иллюстраций (Flux → SDXL fallback)...")
    print()
    
    scenes_data = []
    model_stats = {"flux": 0, "sdxl": 0}  # Статистика моделей
    
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
        
        # Добавляем стиль для качества
        prompt += ", high quality, detailed, professional children's book illustration, vibrant colors, Pixar animation style"
        
        # Генерируем иллюстрацию (ГИБРИД)
        image_filename = f"scene_{scene_num:02d}.png"
        image_path = os.path.join(output_dir, image_filename)
        
        model_used = generate_illustration(prompt, image_path)
        model_stats[model_used] += 1  # Собираем статистику
        
        scenes_data.append({
            "number": scene_num,
            "title": scene_title,
            "text": text,
            "image": image_path
        })
        
        print()
    
    # Создаём PDF
    print("📄 Создаю PDF книгу...")
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
    print()
    
    # Показываем статистику моделей
    print(f"📊 СТАТИСТИКА ГЕНЕРАЦИИ:")
    print(f"   🎨 Flux: {model_stats['flux']} сцен")
    print(f"   🎨 SDXL: {model_stats['sdxl']} сцен")
    print()
    
    # Считаем себестоимость
    flux_cost = model_stats['flux'] * 15  # 15₽ за Flux картинку
    sdxl_cost = model_stats['sdxl'] * 1.1  # 1.1₽ за SDXL картинку
    claude_cost = 5  # Claude анализ
    total_cost = flux_cost + sdxl_cost + claude_cost
    profit = 449 - 12.6 - total_cost  # Цена - YooKassa - себестоимость
    
    print(f"💰 ЭКОНОМИКА:")
    print(f"   Flux: {model_stats['flux']} × 15₽ = {flux_cost:.0f}₽")
    print(f"   SDXL: {model_stats['sdxl']} × 1.1₽ = {sdxl_cost:.1f}₽")
    print(f"   Claude: {claude_cost}₽")
    print(f"   Себестоимость: {total_cost:.1f}₽")
    print(f"   Цена продажи: 449₽")
    print(f"   YooKassa: -12.6₽")
    print(f"   💸 Прибыль: {profit:.1f}₽")
    print()
    
    return pdf_path

if __name__ == "__main__":
    # ТЕСТ ГИБРИДНОЙ ВЕРСИИ
    print("🎨 Гибридная версия: Flux → SDXL fallback")
    print("Готова к использованию!")

