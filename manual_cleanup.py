import sqlite3
import os
import logging
from datetime import datetime

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_db():
    """Подключение к базе данных"""
    conn = sqlite3.connect('crm.db')
    conn.row_factory = sqlite3.Row
    return conn

def show_all_leads():
    """Показать все заявки в базе данных"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Получаем все заявки, отсортированные по телефону и дате
        cursor.execute('''
            SELECT * FROM leads 
            ORDER BY phone, created_at DESC
        ''')
        leads = cursor.fetchall()
        
        print(f"\n{'='*80}")
        print(f"{'ID':<5} {'Телефон':<15} {'Клиент':<15} {'Адрес':<15} {'Дата':<20} {'Статус':<10}")
        print(f"{'-'*80}")
        
        current_phone = None
        for lead in leads:
            phone = lead['phone'] if lead['phone'] else 'Нет'
            client = lead['client_name'] if lead['client_name'] else 'Нет'
            address = lead['address'] if lead['address'] else 'Нет'
            status = lead['status'] if lead['status'] else 'new'
            created_at = lead['created_at']
            
            # Выделяем группы по телефону
            if current_phone != phone:
                print(f"{'-'*80}")
                current_phone = phone
            
            print(f"{lead['id']:<5} {phone[:15]:<15} {client[:15]:<15} {address[:15]:<15} {created_at[:20]:<20} {status:<10}")
            
            # Показываем детали заказа
            order_details = lead['order_details'] if lead['order_details'] else 'Нет'
            if order_details != 'Нет':
                print(f"    Заказ: {order_details[:60]}...")
        
        print(f"{'='*80}")
        return leads
    except Exception as e:
        logger.error(f"Ошибка при получении заявок: {e}")
        return []

def delete_lead(lead_id):
    """Удалить заявку по ID"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Проверяем, существует ли заявка
        cursor.execute('SELECT * FROM leads WHERE id = ?', (lead_id,))
        lead = cursor.fetchone()
        
        if not lead:
            print(f"Заявка с ID {lead_id} не найдена")
            return False
        
        # Удаляем заявку
        cursor.execute('DELETE FROM leads WHERE id = ?', (lead_id,))
        conn.commit()
        
        print(f"Заявка с ID {lead_id} успешно удалена")
        return True
    except Exception as e:
        logger.error(f"Ошибка при удалении заявки: {e}")
        conn.rollback()
        return False

def main():
    """Основная функция"""
    while True:
        print("\nМеню:")
        print("1. Показать все заявки")
        print("2. Удалить заявку по ID")
        print("3. Выход")
        
        choice = input("Выберите действие (1-3): ")
        
        if choice == '1':
            show_all_leads()
        elif choice == '2':
            lead_id = input("Введите ID заявки для удаления: ")
            try:
                lead_id = int(lead_id)
                delete_lead(lead_id)
            except ValueError:
                print("Некорректный ID. Пожалуйста, введите число.")
        elif choice == '3':
            print("Выход из программы")
            break
        else:
            print("Некорректный выбор. Пожалуйста, выберите 1, 2 или 3.")

if __name__ == "__main__":
    logger.info("Запуск программы ручной очистки базы данных...")
    main()
    logger.info("Программа ручной очистки завершена.")
