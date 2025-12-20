#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
База данных для Storybook Bot
PostgreSQL на Railway (как в Sefirum!)
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from typing import Optional, Dict, List

# Подключение к PostgreSQL
DATABASE_URL = os.environ.get("DATABASE_URL", "")

class Database:
    """Класс для работы с PostgreSQL базой данных"""
    
    def __init__(self):
        self.database_url = DATABASE_URL
        self.init_database()
    
    def get_connection(self):
        """Получить подключение к PostgreSQL"""
        if not self.database_url:
            raise Exception("❌ DATABASE_URL не установлен!")
        return psycopg2.connect(self.database_url)
    
    def init_database(self):
        """Создать таблицы если не существуют"""
        if not self.database_url:
            print("⚠️ PostgreSQL не настроена (нет DATABASE_URL)")
            return
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Таблица пользователей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username VARCHAR(255),
                first_name VARCHAR(255),
                last_name VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица заказов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                order_id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                theme VARCHAR(100) NOT NULL,
                child_name VARCHAR(100) NOT NULL,
                child_age INTEGER NOT NULL,
                gender VARCHAR(10) NOT NULL,
                photo_description TEXT,
                status VARCHAR(50) DEFAULT 'pending',
                pdf_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')
        
        # Таблица платежей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS payments (
                payment_id VARCHAR(255) PRIMARY KEY,
                order_id INTEGER NOT NULL,
                user_id BIGINT NOT NULL,
                amount INTEGER NOT NULL,
                status VARCHAR(50) DEFAULT 'pending',
                payment_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                paid_at TIMESTAMP,
                FOREIGN KEY (order_id) REFERENCES orders(order_id),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')
        
        # Таблица статистики
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stats (
                date DATE PRIMARY KEY,
                new_users INTEGER DEFAULT 0,
                total_orders INTEGER DEFAULT 0,
                completed_orders INTEGER DEFAULT 0,
                revenue INTEGER DEFAULT 0
            )
        ''')
        
        conn.commit()
        cursor.close()
        conn.close()
        print("✅ PostgreSQL база данных инициализирована!")
    
    # ===== РАБОТА С ПОЛЬЗОВАТЕЛЯМИ =====
    
    def add_user(self, user_id: int, username: str = None, 
                 first_name: str = None, last_name: str = None):
        """Добавить пользователя (если нет) или обновить last_active"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO users (user_id, username, first_name, last_name)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE SET
                username = EXCLUDED.username,
                first_name = EXCLUDED.first_name,
                last_name = EXCLUDED.last_name,
                last_active = CURRENT_TIMESTAMP
        ''', (user_id, username, first_name, last_name))
        
        conn.commit()
        cursor.close()
        conn.close()
    
    def get_user(self, user_id: int) -> Optional[Dict]:
        """Получить пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute('SELECT * FROM users WHERE user_id = %s', (user_id,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    def get_user_stats(self, user_id: int) -> Dict:
        """Статистика пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute('''
            SELECT 
                COUNT(*) as total_orders,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_orders,
                SUM(CASE WHEN status = 'paid' THEN 1 ELSE 0 END) as paid_orders
            FROM orders WHERE user_id = %s
        ''', (user_id,))
        
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        
        return dict(row) if row else {}
    
    # ===== РАБОТА С ЗАКАЗАМИ =====
    
    def create_order(self, user_id: int, theme: str, child_name: str, 
                    child_age: int, gender: str, photo_description: str = None) -> int:
        """Создать заказ"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO orders (user_id, theme, child_name, child_age, gender, photo_description)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING order_id
        ''', (user_id, theme, child_name, child_age, gender, photo_description))
        
        order_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"✅ Создан заказ #{order_id} для user {user_id}")
        return order_id
    
    def get_order(self, order_id: int) -> Optional[Dict]:
        """Получить заказ"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute('SELECT * FROM orders WHERE order_id = %s', (order_id,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    def update_order_status(self, order_id: int, status: str, pdf_path: str = None):
        """Обновить статус заказа"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if status == 'completed':
            cursor.execute('''
                UPDATE orders 
                SET status = %s, pdf_path = %s, completed_at = CURRENT_TIMESTAMP
                WHERE order_id = %s
            ''', (status, pdf_path, order_id))
        else:
            cursor.execute('''
                UPDATE orders 
                SET status = %s
                WHERE order_id = %s
            ''', (status, order_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"✅ Заказ #{order_id} → статус: {status}")
    
    def get_user_orders(self, user_id: int, limit: int = 10) -> List[Dict]:
        """Получить заказы пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute('''
            SELECT * FROM orders 
            WHERE user_id = %s 
            ORDER BY created_at DESC 
            LIMIT %s
        ''', (user_id, limit))
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return [dict(row) for row in rows]
    
    # ===== РАБОТА С ПЛАТЕЖАМИ =====
    
    def create_payment(self, payment_id: str, order_id: int, 
                      user_id: int, amount: int, payment_url: str = None):
        """Создать платёж"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO payments (payment_id, order_id, user_id, amount, payment_url)
            VALUES (%s, %s, %s, %s, %s)
        ''', (payment_id, order_id, user_id, amount, payment_url))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"✅ Создан платёж {payment_id} для заказа #{order_id}")
    
    def update_payment_status(self, payment_id: str, status: str):
        """Обновить статус платежа"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if status == 'succeeded':
            cursor.execute('''
                UPDATE payments 
                SET status = %s, paid_at = CURRENT_TIMESTAMP
                WHERE payment_id = %s
            ''', (status, payment_id))
        else:
            cursor.execute('''
                UPDATE payments 
                SET status = %s
                WHERE payment_id = %s
            ''', (status, payment_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"✅ Платёж {payment_id} → статус: {status}")
    
    def get_payment(self, payment_id: str) -> Optional[Dict]:
        """Получить платёж"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute('SELECT * FROM payments WHERE payment_id = %s', (payment_id,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    # ===== СТАТИСТИКА =====
    
    def update_daily_stats(self, new_users: int = 0, total_orders: int = 0, 
                          completed_orders: int = 0, revenue: int = 0):
        """Обновить статистику за день"""
        today = datetime.now().date()
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO stats (date, new_users, total_orders, completed_orders, revenue)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (date) DO UPDATE SET
                new_users = stats.new_users + EXCLUDED.new_users,
                total_orders = stats.total_orders + EXCLUDED.total_orders,
                completed_orders = stats.completed_orders + EXCLUDED.completed_orders,
                revenue = stats.revenue + EXCLUDED.revenue
        ''', (today, new_users, total_orders, completed_orders, revenue))
        
        conn.commit()
        cursor.close()
        conn.close()
    
    def get_stats(self, days: int = 7) -> List[Dict]:
        """Получить статистику за N дней"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute('''
            SELECT * FROM stats 
            ORDER BY date DESC 
            LIMIT %s
        ''', (days,))
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_total_stats(self) -> Dict:
        """Общая статистика"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Всего пользователей
        cursor.execute('SELECT COUNT(*) as total_users FROM users')
        total_users = cursor.fetchone()['total_users']
        
        # Всего заказов
        cursor.execute('SELECT COUNT(*) as total_orders FROM orders')
        total_orders = cursor.fetchone()['total_orders']
        
        # Завершённых заказов
        cursor.execute("SELECT COUNT(*) as completed FROM orders WHERE status = 'completed'")
        completed = cursor.fetchone()['completed']
        
        # Выручка
        cursor.execute("SELECT COALESCE(SUM(amount), 0) as revenue FROM payments WHERE status = 'succeeded'")
        revenue = cursor.fetchone()['revenue']
        
        cursor.close()
        conn.close()
        
        return {
            'total_users': total_users,
            'total_orders': total_orders,
            'completed_orders': completed,
            'revenue': revenue,
            'conversion': (completed / total_orders * 100) if total_orders > 0 else 0
        }


# Создаём глобальный экземпляр БД
db = Database()

if __name__ == "__main__":
    # Тестирование
    print("🧪 Тестирование PostgreSQL базы данных...")
    
    if DATABASE_URL:
        print(f"✅ DATABASE_URL установлен")
        print("✅ База данных готова к работе!")
    else:
        print("⚠️ DATABASE_URL не установлен!")
        print("   Добавьте PostgreSQL в Railway и переменную DATABASE_URL")
