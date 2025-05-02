"""
Скрипт для проверки суммы выручки по accepted заявкам из базы CRM.
"""
import sqlite3
import re
import os

def main():
    # Путь к базе относительно этого скрипта
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, 'crm.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    rows = cursor.execute("SELECT total_amount FROM leads WHERE status='accepted'").fetchall()
    total = 0.0
    for row in rows:
        amt_str = row['total_amount'] or ''
        # Убираем пробелы и неразрывные пробелы
        clean = amt_str.replace(' ', '').replace('\u00A0', '')
        # Оставляем только цифры и точку
        clean = re.sub(r'[^0-9.]', '', clean)
        if clean:
            try:
                total += float(clean)
            except ValueError:
                continue
    print(f"Total revenue from accepted orders: {total}")

if __name__ == '__main__':
    main()
