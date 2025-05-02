import sqlite3
import os
import logging
import hashlib
import json
from collections import defaultdict

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_db():
    """Подключение к базе данных"""
    conn = sqlite3.connect('crm.db')
    conn.row_factory = sqlite3.Row
    return conn

def get_lead_hash(lead):
    """Создает хеш заявки на основе ее содержимого"""
    # Создаем словарь с ключевыми полями заявки
    lead_dict = {
        'client_name': lead['client_name'] if lead['client_name'] else '',
        'phone': lead['phone'] if lead['phone'] else '',
        'city': lead['city'] if lead['city'] else '',
        'address': lead['address'] if lead['address'] else '',
        'order_details': lead['order_details'] if lead['order_details'] else '',
        'status': lead['status'] if lead['status'] else ''
    }
    
    # Создаем хеш на основе JSON-представления словаря
    lead_json = json.dumps(lead_dict, sort_keys=True)
    return hashlib.md5(lead_json.encode()).hexdigest()

def remove_exact_duplicates():
    """Удаление точных дубликатов заявок из базы данных"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Получаем общее количество заявок до очистки
        cursor.execute('SELECT COUNT(*) FROM leads')
        total_before = cursor.fetchone()[0]
        logger.info(f"Всего заявок до удаления точных дубликатов: {total_before}")
        
        # Получаем все заявки
        cursor.execute('SELECT * FROM leads ORDER BY created_at DESC')
        leads = cursor.fetchall()
        
        # Группируем заявки по хешу их содержимого
        hash_groups = defaultdict(list)
        for lead in leads:
            lead_hash = get_lead_hash(lead)
            hash_groups[lead_hash].append(lead)
        
        # Удаляем дубликаты, оставляя только самую новую заявку в каждой группе
        duplicates_count = 0
        for lead_hash, group in hash_groups.items():
            if len(group) > 1:
                # Сортируем по дате (новые сверху)
                sorted_group = sorted(group, key=lambda x: x['created_at'], reverse=True)
                
                # Выводим информацию о группе дубликатов
                first_lead = sorted_group[0]
                logger.info(f"Найдена группа из {len(group)} дубликатов:")
                logger.info(f"  Клиент: {first_lead['client_name']}, Телефон: {first_lead['phone']}")
                logger.info(f"  Адрес: {first_lead['address']}, Статус: {first_lead['status']}")
                
                # Оставляем самую новую заявку, остальные удаляем
                for duplicate in sorted_group[1:]:
                    cursor.execute('DELETE FROM leads WHERE id = ?', (duplicate['id'],))
                    duplicates_count += 1
                    logger.info(f"  Удален дубликат ID: {duplicate['id']}, дата: {duplicate['created_at']}")
        
        # Сохраняем изменения
        conn.commit()
        
        # Получаем общее количество заявок после очистки
        cursor.execute('SELECT COUNT(*) FROM leads')
        total_after = cursor.fetchone()[0]
        
        # Выводим статистику
        logger.info(f"Удалено точных дубликатов: {duplicates_count}")
        logger.info(f"Всего заявок после удаления дубликатов: {total_after}")
        
        return duplicates_count
    except Exception as e:
        logger.error(f"Ошибка при удалении дубликатов: {e}")
        conn.rollback()
        return 0
    finally:
        conn.close()

if __name__ == "__main__":
    logger.info("Запуск удаления точных дубликатов заявок...")
    deleted = remove_exact_duplicates()
    logger.info(f"Удаление точных дубликатов завершено. Удалено {deleted} дублирующих заявок.")
