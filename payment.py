#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль для работы с YooKassa
Создание платежей, проверка статуса
"""

import os
from yookassa import Configuration, Payment
import uuid

# Настройки YooKassa
SHOP_ID = os.environ.get("YOOKASSA_SHOP_ID", "")
SECRET_KEY = os.environ.get("YOOKASSA_SECRET_KEY", "")

# Настраиваем YooKassa
if SHOP_ID and SECRET_KEY:
    Configuration.account_id = SHOP_ID
    Configuration.secret_key = SECRET_KEY
    print(f"✅ YooKassa настроена (Shop ID: {SHOP_ID})")
else:
    print("⚠️ YooKassa НЕ настроена (нет ключей)")


def create_payment(amount: int, description: str, return_url: str = None) -> dict:
    """
    Создать платеж
    
    Args:
        amount: Сумма в рублях
        description: Описание платежа
        return_url: URL для возврата после оплаты
    
    Returns:
        {
            'id': 'payment_id',
            'status': 'pending',
            'confirmation_url': 'https://...',
            'paid': False
        }
    """
    
    # Генерируем уникальный ключ идемпотентности
    idempotence_key = str(uuid.uuid4())
    
    try:
        # Создаём платеж
        payment = Payment.create({
            "amount": {
                "value": str(amount),
                "currency": "RUB"
            },
            "confirmation": {
                "type": "redirect",
                "return_url": return_url or "https://t.me/your_bot"
            },
            "capture": True,
            "description": description,
            "receipt": {
                "items": [
                    {
                        "description": description,
                        "quantity": "1.00",
                        "amount": {
                            "value": str(amount),
                            "currency": "RUB"
                        },
                        "vat_code": 1,  # НДС не облагается
                        "payment_mode": "full_payment",
                        "payment_subject": "service"
                    }
                ]
            },
            "metadata": {
                "order_description": description
            }
        }, idempotence_key)
        
        print(f"✅ Создан платеж {payment.id} на {amount}₽")
        
        return {
            'id': payment.id,
            'status': payment.status,
            'confirmation_url': payment.confirmation.confirmation_url,
            'paid': payment.paid
        }
        
    except Exception as e:
        print(f"❌ Ошибка создания платежа: {e}")
        return None


def check_payment(payment_id: str) -> dict:
    """
    Проверить статус платежа
    
    Args:
        payment_id: ID платежа
    
    Returns:
        {
            'id': 'payment_id',
            'status': 'succeeded',
            'paid': True
        }
    """
    
    try:
        payment = Payment.find_one(payment_id)
        
        return {
            'id': payment.id,
            'status': payment.status,
            'paid': payment.paid
        }
        
    except Exception as e:
        print(f"❌ Ошибка проверки платежа: {e}")
        return None


def is_payment_successful(payment_id: str) -> bool:
    """
    Проверить успешно ли оплачен платёж
    
    Args:
        payment_id: ID платежа
    
    Returns:
        True если оплачен, False если нет
    """
    
    payment = check_payment(payment_id)
    
    if payment:
        return payment['status'] == 'succeeded' and payment['paid']
    
    return False


# Тестирование
if __name__ == "__main__":
    print("🧪 Тестирование YooKassa модуля...")
    
    if SHOP_ID and SECRET_KEY:
        # Создаём тестовый платеж
        payment = create_payment(
            amount=449,
            description="Тестовый платеж - Персональная сказка"
        )
        
        if payment:
            print(f"✅ Платеж создан!")
            print(f"   ID: {payment['id']}")
            print(f"   Статус: {payment['status']}")
            print(f"   Ссылка: {payment['confirmation_url']}")
    else:
        print("⚠️ Для теста нужны YOOKASSA_SHOP_ID и YOOKASSA_SECRET_KEY")
