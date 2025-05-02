import sqlite3
import os
import logging
from collections import defaultdict

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_db():
    """Подключение к базе данных"""
    conn = sqlite3.connect('crm.db')
    conn.row_factory = sqlite3.Row
    return conn

def remove_duplicate_leads():
    """Удаление дублирующих заявок из базы данных"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Получаем общее количество заявок до очистки
        cursor.execute('SELECT COUNT(*) FROM leads')
        total_before = cursor.fetchone()[0]
        logger.info(f"Всего заявок до удаления дубликатов: {total_before}")
        
        # Получаем все заявки
        cursor.execute('SELECT * FROM leads ORDER BY created_at DESC')
        leads = cursor.fetchall()
        
        # Группируем заявки по номеру телефона и содержанию заказа
        duplicates_count = 0
        processed_ids = set()
        
        # Сначала группируем по телефону
        phone_groups = defaultdict(list)
        for lead in leads:
            phone = lead['phone'] if lead['phone'] else ''
            
            # Если телефон пустой, пропускаем
            if not phone:
                continue
                
            # Нормализуем телефон (убираем пробелы, тире и т.д.)
            normalized_phone = ''.join(c for c in phone if c.isdigit() or c == '+')
            phone_groups[normalized_phone].append(lead)
        
        # Теперь для каждой группы телефонов ищем дубликаты по заказу
        for normalized_phone, group in phone_groups.items():
            # Группируем по содержанию заказа
            order_groups = defaultdict(list)
            for lead in group:
                order = lead['order_details'] if lead['order_details'] else ''
                client = lead['client_name'] if lead['client_name'] else ''
                address = lead['address'] if lead['address'] else ''
                
                # Создаем ключ для группировки: заказ + клиент + адрес
                order_key = f"{order}|{client}|{address}"
                order_groups[order_key].append(lead)
            
            # Для каждой группы заказов оставляем только самую новую заявку
            for order_key, order_group in order_groups.items():
                if len(order_group) > 1:
                    # Сортируем по дате (новые сверху)
                    sorted_group = sorted(order_group, key=lambda x: x['created_at'], reverse=True)
                    
                    # Оставляем самую новую заявку, остальные удаляем
                    for duplicate in sorted_group[1:]:
                        if duplicate['id'] not in processed_ids:
                            cursor.execute('DELETE FROM leads WHERE id = ?', (duplicate['id'],))
                            duplicates_count += 1
                            processed_ids.add(duplicate['id'])
                            logger.debug(f"Удален дубликат ID: {duplicate['id']}, телефон: {normalized_phone}")
        
        # Сохраняем изменения
        conn.commit()
        
        # Получаем общее количество заявок после очистки
        cursor.execute('SELECT COUNT(*) FROM leads')
        total_after = cursor.fetchone()[0]
        
        # Выводим статистику
        logger.info(f"Удалено дубликатов: {duplicates_count}")
        logger.info(f"Всего заявок после удаления дубликатов: {total_after}")
        
        return duplicates_count
    except Exception as e:
        logger.error(f"Ошибка при удалении дубликатов: {e}")
        conn.rollback()
        return 0
    finally:
        conn.close()

if __name__ == "__main__":
    logger.info("Запуск удаления дублирующих заявок...")
    deleted = remove_duplicate_leads()
    logger.info(f"Удаление дубликатов завершено. Удалено {deleted} дублирующих заявок.")
