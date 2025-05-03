import logging
from flask import Flask, render_template, jsonify, request
import sqlite3
from datetime import datetime
import os
from dotenv import load_dotenv
import re

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Load environment variables
load_dotenv()

def get_db():
    try:
        # Используем абсолютный путь к базе данных
        base_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(base_dir, 'crm.db')
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        logger.error(f'Error connecting to database: {e}')
        raise

def format_date(date_str):
    """Format date string to display format"""
    try:
        # Try to parse as datetime
        date_obj = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
        return date_obj.strftime('%Y-%m-%d %H:%M:%S')
    except:
        # If parsing fails, return original string
        return date_str

@app.route('/')
def index():
    logger.debug('Handling index request')
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Get users
        cursor.execute('SELECT * FROM users')
        users = {user['telegram_id']: user for user in cursor.fetchall()}
        
        # Get leads
        cursor.execute('SELECT * FROM leads ORDER BY created_at DESC')
        leads = cursor.fetchall()
        logger.debug(f'Found {len(leads)} leads')
        
        # Format leads for display
        formatted_leads = []
        for lead in leads:
            formatted_lead = dict(lead)
            user = users.get(lead['telegram_id'], {})
            formatted_lead['username'] = user.get('username', 'Аноним')
            formatted_lead['created_at'] = format_date(lead['created_at'])
            formatted_leads.append(formatted_lead)
        
        return render_template('index.html', leads=formatted_leads)
    except Exception as e:
        logger.error(f'Error in index: {e}')
        raise

@app.route('/leads')
def get_leads():
    logger.debug('Handling leads request')
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Get leads
        cursor.execute('SELECT * FROM leads ORDER BY created_at DESC')
        leads = cursor.fetchall()
        logger.debug(f'Found {len(leads)} leads')
        
        # Создаем словарь для хранения связей между телефонами и заявками
        phone_to_leads = {}
        
        # Форматируем все заявки для API
        formatted_leads = []
        
        for lead in leads:
            # Получаем информацию об исполнителе напрямую из записи
            executor_username = lead['executor_username'] or ''
            executor_first_name = lead['executor_first_name'] or ''
            
            # Форматируем статус
            status = lead['status'] if lead['status'] else 'new'
            
            # Форматируем данные заказа
            order_details = lead['order_details'] if lead['order_details'] else ''
            
            # Нормализуем телефон (если есть)
            phone = lead['phone'] if lead['phone'] else ''
            normalized_phone = ''.join(c for c in phone if c.isdigit() or c == '+') if phone else ''
            
            # Создаем форматированную заявку
            formatted_lead = {
                'id': lead['id'],
                'username': lead['username'] or 'Аноним',
                'message': lead['message'],
                'created_at': format_date(lead['created_at']),
                'status': status,
                
                # Добавляем структурированные поля
                'client_name': lead['client_name'] if lead['client_name'] else '',
                'company': lead['company'] if lead['company'] else '',
                'phone': lead['phone'] if lead['phone'] else '',
                'normalized_phone': normalized_phone,
                'city': lead['city'] if lead['city'] else '',
                'address': lead['address'] if lead['address'] else '',
                'order_details': order_details,
                'total_amount': lead['total_amount'] if lead['total_amount'] else '',
                'order_date': lead['order_date'] if lead['order_date'] else '',
                
                # Источник заявки из БД или по умолчанию
                'source': lead['source'] if lead['source'] else 'сайт',
                
                # Добавляем информацию об исполнителе
                'executor_username': executor_username,
                'executor_first_name': executor_first_name
            }
            
            # Добавляем заявку в массив
            formatted_leads.append(formatted_lead)
            
            # Сохраняем связь между телефоном и заявкой для быстрого поиска
            if normalized_phone:
                if normalized_phone not in phone_to_leads:
                    phone_to_leads[normalized_phone] = []
                phone_to_leads[normalized_phone].append(formatted_lead['id'])
        
        # Добавляем информацию о связанных заявках
        for lead in formatted_leads:
            if lead['normalized_phone'] and lead['normalized_phone'] in phone_to_leads:
                lead['related_leads'] = phone_to_leads[lead['normalized_phone']]
                lead['related_count'] = len(phone_to_leads[lead['normalized_phone']])
            else:
                lead['related_leads'] = [lead['id']]
                lead['related_count'] = 1
        
        return jsonify(formatted_leads)
    except Exception as e:
        logger.error(f'Error in get_leads: {e}')
        raise

@app.route('/stats', methods=['GET'])
def get_stats():
    try:
        # Получаем параметры фильтрации
        start_date = request.args.get('start_date', None)
        end_date = request.args.get('end_date', None)
        
        conn = get_db()
        cursor = conn.cursor()
        
        # Базовый запрос
        query = 'SELECT status, COUNT(*) as count FROM leads'
        params = []
        
        # Добавляем условия фильтрации по дате
        if start_date or end_date:
            query += ' WHERE'
            
            if start_date:
                query += ' created_at >= ?'
                params.append(start_date)
                
            if end_date:
                if start_date:
                    query += ' AND'
                query += ' created_at <= ?'
                params.append(end_date)
        
        # Группируем по статусу
        query += ' GROUP BY status'
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        
        # Форматируем результаты
        stats = {
            'accepted': 0,
            'in_progress': 0,
            'declined': 0,
            'new': 0,
            'total': 0
        }
        
        for row in results:
            status = row['status'] if row['status'] else 'new'
            count = row['count']
            stats[status] = count
            stats['total'] += count
        
        # Получаем общее количество уникальных клиентов
        query = 'SELECT COUNT(DISTINCT phone) as unique_clients FROM leads WHERE phone IS NOT NULL AND phone != ""'
        params = []
        
        if start_date or end_date:
            query += ' AND'
            
            if start_date:
                query += ' created_at >= ?'
                params.append(start_date)
                
            if end_date:
                if start_date:
                    query += ' AND'
                query += ' created_at <= ?'
                params.append(end_date)
        
        cursor.execute(query, params)
        unique_clients = cursor.fetchone()['unique_clients']
        stats['unique_clients'] = unique_clients
        
        # Считаем доход вручную: получаем все total_amount, очищаем и суммируем
        filters = ['status = ?']
        params_amt = ['accepted']
        if start_date:
            filters.append('created_at >= ?')
            params_amt.append(start_date)
        if end_date:
            filters.append('created_at <= ?')
            params_amt.append(end_date)
        query_amt = 'SELECT total_amount FROM leads WHERE ' + ' AND '.join(filters)
        cursor.execute(query_amt, params_amt)
        rows_amt = cursor.fetchall()
        total_revenue = 0.0
        for r in rows_amt:
            s = (r['total_amount'] or '').replace(' ', '').replace('\u00A0', '')
            s = re.sub(r'[^0-9.]', '', s)
            try:
                total_revenue += float(s)
            except:
                continue
        stats['revenue'] = round(total_revenue, 2)
        
        return jsonify(stats)
    except Exception as e:
        logger.error(f'Error in get_stats: {e}')
        return jsonify({'error': str(e)}), 500

@app.route('/reset', methods=['POST'])
def reset_db():
    """Обнуляет таблицу leads"""
    conn = get_db()
    cursor = conn.cursor()
    # Удаляем все лиды и сбрасываем счетчик AUTOINCREMENT
    cursor.execute('DELETE FROM leads')
    cursor.execute("DELETE FROM sqlite_sequence WHERE name='leads'")
    conn.commit()
    conn.close()
    return jsonify({'success': True})

if __name__ == '__main__':
    logger.info('Starting Flask server')
    app.run(debug=True, host='0.0.0.0')
