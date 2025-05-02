import logging
from flask import Flask, render_template, jsonify
import sqlite3
from datetime import datetime
import os
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Load environment variables
load_dotenv()

def get_db():
    try:
        conn = sqlite3.connect('crm.db')
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
        
        # Get users
        cursor.execute('SELECT * FROM users')
        users = {user['telegram_id']: user for user in cursor.fetchall()}
        
        # Get leads
        cursor.execute('SELECT * FROM leads ORDER BY created_at DESC')
        leads = cursor.fetchall()
        logger.debug(f'Found {len(leads)} leads')
        
        # Группировка заявок по номеру телефона
        phone_groups = {}
        
        for lead in leads:
            phone = lead['phone'] if lead['phone'] else ''
            
            # Если телефон пустой, не группируем
            if not phone:
                continue
                
            # Нормализуем телефон (убираем пробелы, тире и т.д.)
            normalized_phone = ''.join(c for c in phone if c.isdigit() or c == '+')
            
            if normalized_phone not in phone_groups:
                phone_groups[normalized_phone] = []
                
            phone_groups[normalized_phone].append(lead)
        
        # Format leads for API response
        formatted_leads = []
        
        # Сначала обрабатываем группы
        for normalized_phone, group in phone_groups.items():
            # Считаем количество уникальных заявок по содержанию заказа
            unique_orders = set()
            for lead in group:
                order = lead['order_details'] if lead['order_details'] else ''
                unique_orders.add(order)
            
            # Берем самую новую заявку из группы (она уже отсортирована по дате)
            latest_lead = group[0]
            
            # Получаем информацию об исполнителе
            executor_id = latest_lead['executor_id'] if latest_lead['executor_id'] else None
            executor_username = ''
            executor_first_name = ''
            
            if executor_id and executor_id in users:
                executor_username = users[executor_id]['username'] if users[executor_id]['username'] else ''
                executor_first_name = users[executor_id]['first_name'] if 'first_name' in users[executor_id] else ''
            
            # Форматируем статус
            status = latest_lead['status'] if latest_lead['status'] else 'new'
            
            # Форматируем данные заказа
            order_details = latest_lead['order_details'] if latest_lead['order_details'] else ''
            
            # Создаем форматированную заявку
            formatted_lead = {
                'id': latest_lead['id'],
                'username': latest_lead['username'] or 'Аноним',
                'message': latest_lead['message'],
                'created_at': format_date(latest_lead['created_at']),
                'status': status,
                'grouped': True,
                'group_count': len(unique_orders),  # Количество уникальных заказов
                'group_ids': [l['id'] for l in group],
                
                # Добавляем структурированные поля
                'client_name': latest_lead['client_name'] if latest_lead['client_name'] else '',
                'company': latest_lead['company'] if latest_lead['company'] else '',
                'phone': latest_lead['phone'] if latest_lead['phone'] else '',
                'city': latest_lead['city'] if latest_lead['city'] else '',
                'address': latest_lead['address'] if latest_lead['address'] else '',
                'order_details': order_details,
                'total_amount': latest_lead['total_amount'] if latest_lead['total_amount'] else '',
                'order_date': latest_lead['order_date'] if latest_lead['order_date'] else '',
                
                # Добавляем информацию об исполнителе
                'executor_username': executor_username,
                'executor_first_name': executor_first_name
            }
            formatted_leads.append(formatted_lead)
        
        # Затем добавляем все заявки для полного списка (нужно для модального окна)
        for lead in leads:
            # Получаем информацию об исполнителе
            executor_id = lead['executor_id'] if lead['executor_id'] else None
            executor_username = ''
            executor_first_name = ''
            
            if executor_id and executor_id in users:
                executor_username = users[executor_id]['username'] if users[executor_id]['username'] else ''
                executor_first_name = users[executor_id]['first_name'] if 'first_name' in users[executor_id] else ''
            
            # Форматируем статус
            status = lead['status'] if lead['status'] else 'new'
            
            # Форматируем данные заказа
            order_details = lead['order_details'] if lead['order_details'] else ''
            
            # Создаем форматированную заявку
            formatted_lead = {
                'id': lead['id'],
                'username': lead['username'] or 'Аноним',
                'message': lead['message'],
                'created_at': format_date(lead['created_at']),
                'status': status,
                'grouped': False,
                'group_count': 1,
                
                # Добавляем структурированные поля
                'client_name': lead['client_name'] if lead['client_name'] else '',
                'company': lead['company'] if lead['company'] else '',
                'phone': lead['phone'] if lead['phone'] else '',
                'city': lead['city'] if lead['city'] else '',
                'address': lead['address'] if lead['address'] else '',
                'order_details': order_details,
                'total_amount': lead['total_amount'] if lead['total_amount'] else '',
                'order_date': lead['order_date'] if lead['order_date'] else '',
                
                # Добавляем информацию об исполнителе
                'executor_username': executor_username,
                'executor_first_name': executor_first_name
            }
            formatted_leads.append(formatted_lead)
        
        return jsonify(formatted_leads)
    except Exception as e:
        logger.error(f'Error in get_leads: {e}')
        raise

if __name__ == '__main__':
    logger.info('Starting Flask server')
    app.run(debug=True, host='0.0.0.0')
