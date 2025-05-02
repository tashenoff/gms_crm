import sqlite3
import os
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_db():
    """Подключение к базе данных"""
    conn = sqlite3.connect('crm.db')
    conn.row_factory = sqlite3.Row
    return conn

def clean_empty_leads():
    """Удаление пустых заявок из базы данных"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Получаем общее количество заявок до очистки
        cursor.execute('SELECT COUNT(*) FROM leads')
        total_before = cursor.fetchone()[0]
        logger.info(f"Всего заявок до очистки: {total_before}")
        
        # Удаляем заявки без телефона и без текста сообщения
        cursor.execute('''
            DELETE FROM leads 
            WHERE (phone IS NULL OR phone = '') 
            AND (message IS NULL OR message = '' OR message = 'None')
        ''')
        
        # Удаляем заявки без телефона и без клиента
        cursor.execute('''
            DELETE FROM leads 
            WHERE (phone IS NULL OR phone = '') 
            AND (client_name IS NULL OR client_name = '')
        ''')
        
        # Получаем общее количество заявок после очистки
        cursor.execute('SELECT COUNT(*) FROM leads')
        total_after = cursor.fetchone()[0]
        
        # Сохраняем изменения
        conn.commit()
        
        # Выводим статистику
        deleted = total_before - total_after
        logger.info(f"Удалено пустых заявок: {deleted}")
        logger.info(f"Всего заявок после очистки: {total_after}")
        
        return deleted
    except Exception as e:
        logger.error(f"Ошибка при очистке базы данных: {e}")
        conn.rollback()
        return 0
    finally:
        conn.close()

if __name__ == "__main__":
    logger.info("Запуск очистки базы данных от пустых заявок...")
    deleted = clean_empty_leads()
    logger.info(f"Очистка завершена. Удалено {deleted} пустых заявок.")
