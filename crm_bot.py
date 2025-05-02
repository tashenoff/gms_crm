import os
import json
import sqlite3
import time
import logging
from datetime import datetime
from dotenv import load_dotenv
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
TELEGRAM_API_URL = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}'

# Database setup
def init_db():
    conn = sqlite3.connect('crm.db')
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create leads table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            username TEXT,
            message TEXT,
            status TEXT DEFAULT 'new',
            executor_id INTEGER,
            executor_username TEXT,
            executor_first_name TEXT,
            
            client_name TEXT,
            company TEXT,
            phone TEXT,
            city TEXT,
            address TEXT,
            order_details TEXT,
            total_amount TEXT,
            order_date TEXT,
            
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (telegram_id) REFERENCES users (telegram_id)
        )
    ''')
    
    # Add columns if they don't exist
    try:
        cursor.execute('ALTER TABLE leads ADD COLUMN executor_id INTEGER')
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        cursor.execute('ALTER TABLE leads ADD COLUMN executor_username TEXT')
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        cursor.execute('ALTER TABLE leads ADD COLUMN executor_first_name TEXT')
    except sqlite3.OperationalError:
        pass  # Column already exists
        
    # Add new structured fields if they don't exist
    try:
        cursor.execute('ALTER TABLE leads ADD COLUMN client_name TEXT')
    except sqlite3.OperationalError:
        pass  # Column already exists
        
    try:
        cursor.execute('ALTER TABLE leads ADD COLUMN company TEXT')
    except sqlite3.OperationalError:
        pass  # Column already exists
        
    try:
        cursor.execute('ALTER TABLE leads ADD COLUMN phone TEXT')
    except sqlite3.OperationalError:
        pass  # Column already exists
        
    try:
        cursor.execute('ALTER TABLE leads ADD COLUMN city TEXT')
    except sqlite3.OperationalError:
        pass  # Column already exists
        
    try:
        cursor.execute('ALTER TABLE leads ADD COLUMN address TEXT')
    except sqlite3.OperationalError:
        pass  # Column already exists
        
    try:
        cursor.execute('ALTER TABLE leads ADD COLUMN order_details TEXT')
    except sqlite3.OperationalError:
        pass  # Column already exists
        
    try:
        cursor.execute('ALTER TABLE leads ADD COLUMN total_amount TEXT')
    except sqlite3.OperationalError:
        pass  # Column already exists
        
    try:
        cursor.execute('ALTER TABLE leads ADD COLUMN order_date TEXT')
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    conn.commit()
    conn.close()

init_db()

def get_sender_info(message):
    """Extract sender information from message"""
    # Check for channel post
    sender_chat = message.get('sender_chat')
    if sender_chat:
        return {
            'id': sender_chat.get('id'),
            'username': sender_chat.get('username', 'Аноним')
        }
    
    # Check for regular message
    sender = message.get('from')
    if sender:
        return {
            'id': sender.get('id'),
            'username': sender.get('username', 'Аноним')
        }
    
    return None

def create_status_buttons(lead_id):
    """Create buttons for lead status updates"""
    return [
        [{'text': 'Принято', 'callback_data': f'status_accepted|{lead_id}'},
         {'text': 'В работе', 'callback_data': f'status_in_progress|{lead_id}'},
         {'text': 'Отказ', 'callback_data': f'status_declined|{lead_id}'}]
    ]

def parse_message_text(text):
    """
    Parse message text into structured fields
    Expected format может быть разным, включая:
    
    1. Простой формат:
    Клиент: Иван Иванов
    Телефон: +7 (123) 456-78-90
    
    2. Формат с эмодзи:
    👤 Клиент: Иван Иванов
    📞 Телефон: +7 (123) 456-78-90
    
    3. Сложный формат с вложенной структурой:
    👤 Клиент: Менеджер
    📞 Телефон: Имя клиента
    📍 Адрес: +7 (123) 456-78-90
    📦 Заказ: Город
    💰 Сумма: Адрес
    📅 Дата: 🆕 Новый заказ! 👤 Клиент: Реальное имя клиента...
    """
    parsed_data = {
        'client_name': '',
        'company': '',
        'phone': '',
        'city': '',
        'address': '',
        'order_details': '',
        'total_amount': '',
        'order_date': ''
    }
    
    # Default to original text if parsing fails
    parsed_data['original_text'] = text
    
    # Try to parse structured fields
    try:
        # Словарь соответствия эмодзи полям
        emoji_mappings = {
            '👤': 'client_name',   # Клиент
            '🏢': 'company',       # Компания
            '📱': 'phone',         # Телефон (альтернативный)
            '📞': 'phone',         # Телефон
            '🏙️': 'city',          # Город
            '📍': 'address',       # Адрес
            '📦': 'order_details', # Заказ
            '💰': 'total_amount',  # Сумма
            '🕒': 'order_date',    # Время (альтернативный)
            '📅': 'order_date'     # Дата
        }
        
        # Словарь соответствия ключевых слов полям
        key_mappings = {
            'клиент': 'client_name',
            'имя': 'client_name',
            'фио': 'client_name',
            'компания': 'company',
            'организация': 'company',
            'фирма': 'company',
            'телефон': 'phone',
            'тел': 'phone',
            'номер': 'phone',
            'город': 'city',
            'населенный пункт': 'city',
            'адрес': 'address',
            'местоположение': 'address',
            'заказ': 'order_details',
            'товар': 'order_details',
            'услуга': 'order_details',
            'описание': 'order_details',
            'сумма': 'total_amount',
            'общая сумма': 'total_amount',
            'цена': 'total_amount',
            'стоимость': 'total_amount',
            'дата': 'order_date',
            'время': 'order_date',
            'срок': 'order_date'
        }
        
        # Проверяем, есть ли в сообщении строка с "🆕 Новый заказ!"
        # Если есть, то это сложная структура с вложенной информацией
        complex_format = False
        nested_data_start = None
        
        lines = text.split('\n')
        for i, line in enumerate(lines):
            if '🆕 Новый заказ!' in line:
                complex_format = True
                nested_data_start = i
                break
        
        # Проверяем, есть ли в сообщении строки с "шт. x" - это признак заказа
        order_lines = []
        for i, line in enumerate(lines):
            if 'шт. x' in line and '₸' in line:
                order_lines.append(line.strip())
        
        # Если это сложная структура, обрабатываем её отдельно
        if complex_format and nested_data_start is not None:
            # Сначала обрабатываем первую часть сообщения (до "🆕 Новый заказ!")
            first_part_lines = lines[:nested_data_start]
            
            # Затем обрабатываем вторую часть (после "🆕 Новый заказ!")
            second_part = ' '.join(lines[nested_data_start:])
            
            # Извлекаем информацию из второй части (она содержит реальные данные клиента)
            # Ищем все поля с эмодзи во второй части
            for emoji, field in emoji_mappings.items():
                if emoji in second_part:
                    parts = second_part.split(emoji)
                    for i in range(1, len(parts)):
                        part = parts[i].strip()
                        if ':' in part:
                            value = part.split(':', 1)[1].strip()
                            # Обрезаем значение до следующего эмодзи, если оно есть
                            for e in emoji_mappings.keys():
                                if e in value:
                                    value = value.split(e)[0].strip()
                            
                            # Если это поле заказа, сохраняем всё, что идёт после него до следующего эмодзи
                            if field == 'order_details':
                                if order_lines:
                                    parsed_data[field] = '\n'.join(order_lines)
                                else:
                                    parsed_data[field] = value
                            else:
                                parsed_data[field] = value
            
            # Если не нашли некоторые поля во второй части, ищем их в первой части
            for i, line in enumerate(first_part_lines):
                line = line.strip()
                if not line:
                    continue
                
                # Проверяем наличие эмодзи в начале строки
                for emoji, field in emoji_mappings.items():
                    if emoji in line and not parsed_data[field]:
                        parts = line.split(emoji, 1)[1].strip()
                        if ':' in parts:
                            value = parts.split(':', 1)[1].strip()
                            parsed_data[field] = value
                            break
            
            # Если общая сумма не найдена, ищем её специально
            if not parsed_data['total_amount']:
                for line in lines:
                    if '💰 Общая сумма:' in line:
                        parsed_data['total_amount'] = line.split('💰 Общая сумма:', 1)[1].strip()
                        break
            
            # Если дата не найдена, ищем её специально
            if not parsed_data['order_date']:
                for line in lines:
                    if '🕒 Дата:' in line:
                        parsed_data['order_date'] = line.split('🕒 Дата:', 1)[1].strip()
                        break
        else:
            # Обычная обработка для простой структуры
            # Сначала извлекаем все поля с эмодзи
            extracted_fields = {}
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Проверяем наличие эмодзи в начале строки
                for emoji, field in emoji_mappings.items():
                    if emoji in line:
                        parts = line.split(emoji, 1)[1].strip()
                        if ':' in parts:
                            value = parts.split(':', 1)[1].strip()
                            extracted_fields[field] = value
                            break
            
            # Если найдены строки заказа, сохраняем их
            if order_lines:
                extracted_fields['order_details'] = '\n'.join(order_lines)
            
            # Проверяем, есть ли смещение полей (случай с менеджером Catzilla)
            if 'client_name' in extracted_fields and extracted_fields.get('client_name') == 'Catzilla':
                # Это менеджер, а не клиент - происходит смещение полей
                # Правильная структура:
                # client_name = phone (alex)
                # phone = address (+77761604911)
                # address = order_details (абая 8)
                # order_details = order_lines (Заглушка...)
                
                # Сохраняем оригинальные значения
                manager_name = extracted_fields.get('client_name', '')
                client_name = extracted_fields.get('phone', '')
                phone = extracted_fields.get('address', '')
                city = extracted_fields.get('order_details', '')
                address = extracted_fields.get('total_amount', '')
                
                # Проверяем, что телефон похож на телефон (содержит + и цифры)
                if phone and ('+' in phone or any(c.isdigit() for c in phone)):
                    # Это похоже на смещение полей, применяем коррекцию
                    parsed_data['client_name'] = client_name
                    parsed_data['phone'] = phone
                    parsed_data['city'] = city
                    parsed_data['address'] = address
                    
                    # Сохраняем информацию о менеджере
                    logger.info(f'Detected message from manager: {manager_name}')
                    
                    # Если есть строки заказа, используем их
                    if order_lines:
                        parsed_data['order_details'] = '\n'.join(order_lines)
                else:
                    # Если не похоже на смещение, используем оригинальные значения
                    parsed_data.update(extracted_fields)
            else:
                # Нет смещения, используем извлеченные поля как есть
                parsed_data.update(extracted_fields)
                
                # Проверяем наличие ключевых слов для полей, которые не были найдены
                for line in lines:
                    line = line.strip()
                    if not line or ':' not in line:
                        continue
                    
                    key, value = line.split(':', 1)
                    key = key.strip().lower()
                    value = value.strip()
                    
                    for keyword, field in key_mappings.items():
                        if keyword in key and not parsed_data[field]:
                            parsed_data[field] = value
                            break
        
        # Проверяем, что все поля заполнены корректно
        # Телефон должен содержать цифры и быть длиннее 5 символов
        if parsed_data['phone'] and (len(parsed_data['phone']) < 5 or not any(c.isdigit() for c in parsed_data['phone'])):
            # Это может быть не телефон, ищем настоящий телефон в других полях
            for field in ['address', 'city', 'client_name']:
                if parsed_data[field] and ('+' in parsed_data[field] or any(c.isdigit() for c in parsed_data[field])):
                    # Нашли похожий на телефон текст в другом поле
                    real_phone = parsed_data[field]
                    # Если это поле клиента, сохраняем значение телефона в поле телефона
                    if field == 'client_name':
                        parsed_data['phone'] = real_phone
                    else:
                        # Меняем местами значения
                        parsed_data['phone'], parsed_data[field] = real_phone, parsed_data['phone']
        
        # Проверяем, что имя клиента не содержит телефон
        if parsed_data['client_name'] and '+' in parsed_data['client_name'] and any(c.isdigit() for c in parsed_data['client_name']):
            # Это может быть телефон, а не имя клиента
            if not parsed_data['phone']:
                parsed_data['phone'] = parsed_data['client_name']
                parsed_data['client_name'] = ''
        
        # Если город и адрес перепутаны (город обычно короче адреса)
        if parsed_data['city'] and parsed_data['address'] and len(parsed_data['city']) > len(parsed_data['address']):
            parsed_data['city'], parsed_data['address'] = parsed_data['address'], parsed_data['city']
        
        # Если заказ содержит только одно слово, это может быть не заказ
        if parsed_data['order_details'] and len(parsed_data['order_details'].split()) == 1:
            # Проверяем, может ли это быть город
            if not parsed_data['city'] and parsed_data['order_details'].isalpha():
                parsed_data['city'] = parsed_data['order_details']
                parsed_data['order_details'] = ''
                
    except Exception as e:
        logger.error(f'Error parsing message text: {e}')
    
    return parsed_data

def save_message(message):
    """Save message to database and create lead with buttons"""
    try:
        logger.info('Saving message to database')
        
        # Get sender information
        sender_info = get_sender_info(message)
        if not sender_info:
            logger.warning('No sender information in message')
            return
        
        sender_id = sender_info['id']
        username = sender_info['username']
        
        # Get message text
        text = message.get('text')
        if not text:
            logger.warning('No text in message')
            return
            
        # Parse message text into structured fields
        parsed_data = parse_message_text(text)
        
        # Save to database
        conn = sqlite3.connect('crm.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO leads (
                telegram_id, username, message, 
                client_name, company, phone, city, address, 
                order_details, total_amount, order_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            sender_id, username, text,
            parsed_data['client_name'], parsed_data['company'], 
            parsed_data['phone'], parsed_data['city'], 
            parsed_data['address'], parsed_data['order_details'], 
            parsed_data['total_amount'], parsed_data['order_date']
        ))
        
        lead_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        logger.info(f'Message saved with lead_id: {lead_id}')
        
        # Delete original message
        message_id = message.get('message_id')
        if message_id:
            delete_message(TELEGRAM_CHAT_ID, message_id)
        
        # Format structured message
        structured_text = f"Новая заявка от {username} (ID: {sender_id})\n\n"
        
        if parsed_data['client_name']:
            structured_text += f"👤 Клиент: {parsed_data['client_name']}\n"
        if parsed_data['company']:
            structured_text += f"🏢 Компания: {parsed_data['company']}\n"
        if parsed_data['phone']:
            structured_text += f"📞 Телефон: {parsed_data['phone']}\n"
        if parsed_data['city']:
            structured_text += f"🏙️ Город: {parsed_data['city']}\n"
        if parsed_data['address']:
            structured_text += f"📍 Адрес: {parsed_data['address']}\n"
        if parsed_data['order_details']:
            structured_text += f"📦 Заказ: {parsed_data['order_details']}\n"
        if parsed_data['total_amount']:
            structured_text += f"💰 Сумма: {parsed_data['total_amount']}\n"
        if parsed_data['order_date']:
            structured_text += f"📅 Дата: {parsed_data['order_date']}\n"
            
        # If no structured fields were parsed, use original text
        if structured_text == f"Новая заявка от {username} (ID: {sender_id})\n\n":
            structured_text += text
        
        # Send new message with buttons
        buttons = create_status_buttons(lead_id)
        send_message(TELEGRAM_CHAT_ID, structured_text, buttons)
        
    except Exception as e:
        logger.error(f'Error saving message: {e}')
        send_message(TELEGRAM_CHAT_ID, f'Ошибка при сохранении заявки: {str(e)}')

def get_updates(offset=None):
    """Get updates from Telegram API"""
    try:
        url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates'
        params = {
            'timeout': 100,
            'offset': offset,
            'allowed_updates': ['message', 'channel_post', 'callback_query']
        }
        
        response = requests.get(url, params=params)
        
        if response.status_code == 409:
            logger.warning('Conflict error, retrying...')
            time.sleep(10)  # Increased delay
            return get_updates(offset)
        
        response.raise_for_status()
        result = response.json()
        if result.get('ok'):
            return result
        else:
            logger.error(f'Error in updates response: {result.get("description", "Unknown error")}')
            return {'ok': False, 'description': 'Error in response'}
    except Exception as e:
        logger.error(f'Error getting updates: {e}')
        return {'ok': False, 'description': str(e)}

def answer_callback_query(callback_query_id, text=None, show_alert=True):
    """Send callback query answer to Telegram without logging to CRM"""
    url = f"{TELEGRAM_API_URL}/answerCallbackQuery"
    payload = {"callback_query_id": callback_query_id, "text": text, "show_alert": show_alert}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        logger.error(f"Error answering callback query: {e}")

def send_message(chat_id, text, buttons=None):
    """Send message to Telegram chat with optional buttons"""
    try:
        data = {
            'chat_id': chat_id,
            'text': text
        }

        if buttons:
            data['reply_markup'] = {
                'inline_keyboard': buttons
            }

        response = requests.post(f'{TELEGRAM_API_URL}/sendMessage', json=data)
        response.raise_for_status()

        logger.info(f'Sent message with ID: {response.json().get("result", {}).get("message_id")}')
        
    except Exception as e:
        logger.error(f'Error sending message: {e}')

def edit_message(chat_id, message_id, text, buttons=None):
    """Edit message in Telegram chat"""
    try:
        data = {
            'chat_id': chat_id,
            'message_id': message_id,
            'text': text
        }

        if buttons:
            data['reply_markup'] = {
                'inline_keyboard': buttons
            }

        response = requests.post(f'{TELEGRAM_API_URL}/editMessageText', json=data)
        response.raise_for_status()
        
        logger.info(f'Edited message: {message_id}')
        
    except Exception as e:
        logger.error(f'Error editing message: {e}')

def delete_message(chat_id, message_id):
    """Delete message from Telegram chat"""
    try:
        response = requests.post(f'{TELEGRAM_API_URL}/deleteMessage', json={
            'chat_id': chat_id,
            'message_id': message_id
        })
        response.raise_for_status()
        
        logger.info(f'Deleted message: {message_id}')
        
    except Exception as e:
        logger.error(f'Error deleting message: {e}')

def parse_callback_data(data):
    """Parse callback data from button click"""
    try:
        # First try to split by '|'
        parts = data.split('|')
        if len(parts) == 2:
            status, lead_id = parts
            status = status.replace('status_', '')
            return status, lead_id
        else:
            # If that doesn't work, try to extract lead_id from the end
            lead_id = data.split('|')[-1]
            if 'accepted' in data:
                status = 'accepted'
            elif 'declined' in data:
                status = 'declined'
            else:
                status = 'in_progress'
            return status, lead_id
    except Exception as e:
        logger.error(f'Error parsing callback data: {e}')
        return None, None

def get_status_text(status):
    """Get human-readable status text"""
    return {
        'accepted': 'Принято',
        'in_progress': 'В работе',
        'declined': 'Отказ'
    }.get(status, 'Неизвестный статус')

def update_lead_status(lead_id, status, executor_info):
    """Update lead status in database"""
    conn = sqlite3.connect('crm.db')
    cursor = conn.cursor()
    
    # Update lead status and add executor
    cursor.execute('''
        UPDATE leads 
        SET status = ?, executor_id = ?, executor_username = ?, executor_first_name = ?
        WHERE id = ?
    ''', (status, executor_info['id'], executor_info['username'], 
          executor_info['first_name'], int(lead_id)))
    
    conn.commit()
    conn.close()
    
    logger.info(f'Updated lead status: lead_id={lead_id}, status={status}, executor={executor_info["username"]}')

def get_lead_by_id(lead_id):
    """Get lead information from database"""
    conn = sqlite3.connect('crm.db')
    # Возвращаем строки как словари для доступа по ключу
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM leads WHERE id = ?', (int(lead_id),))
    lead = cursor.fetchone()
    conn.close()
    return lead

def handle_callback_query(callback_query):
    """Handle callback query from button click"""
    try:
        logger.info('=== START handle_callback_query ===')
        
        # Get message ID from callback query
        message_id = callback_query.get('message', {}).get('message_id')
        if not message_id:
            logger.warning('No message ID in callback query')
            return
            
        data = callback_query.get('data', '')
        if not data:
            logger.warning('No callback data')
            return
            
        # Parse callback data
        status, lead_id = parse_callback_data(data)
        if not status or not lead_id:
            return
            
        logger.info(f'Parsed status: {status}, lead_id: {lead_id}, message_id: {message_id}')
        
        # Get executor information
        executor_info = {
            'id': callback_query.get('from', {}).get('id'),
            'username': callback_query.get('from', {}).get('username'),
            'first_name': callback_query.get('from', {}).get('first_name')
        }
        
        # Get lead information before update
        lead = get_lead_by_id(lead_id)
        if not lead:
            logger.error(f'Lead not found: {lead_id}')
            return
            
        # Ограничение: только исполнитель, принявший заявку, может менять статус далее
        existing_executor = lead['executor_id']
        if existing_executor and existing_executor != executor_info['id']:
            # Оповещаем, что изменить статус может только тот, кто принял заявку
            answer_callback_query(callback_query.get('id'), 'Изменять статус может только исполнитель задачи.')
            return
        
        # Сохраняем оригинальный текст сообщения, чтобы не потерять структуру
        original_message_text = callback_query.get('message', {}).get('text', '')
        
        # Update lead status
        update_lead_status(lead_id, status, executor_info)
        
        # Get updated lead information
        updated_lead = get_lead_by_id(lead_id)
        if updated_lead:
            # Format status text
            status_text = get_status_text(status)
            
            # Создаем новый текст сообщения, сохраняя структуру оригинального сообщения
            # Удаляем старую информацию о статусе и исполнителе, если она есть
            new_text = original_message_text
            
            # Удаляем старую информацию о статусе и исполнителе
            status_index = new_text.find('\n📊 Статус:')
            if status_index != -1:
                new_text = new_text[:status_index]
            
            # Добавляем новую информацию о статусе и исполнителе
            new_text += f'\n\n📊 Статус: {status_text}\n👨‍💼 Исполнитель: {updated_lead[7]} (@{updated_lead[6]})'
            
            # Edit message with new text and keep buttons
            buttons = create_status_buttons(lead_id)
            edit_message(TELEGRAM_CHAT_ID, message_id, new_text, buttons)
        
        logger.info('=== END handle_callback_query ===')
            
    except Exception as e:
        logger.error(f'Error handling callback query: {e}')
        send_message(TELEGRAM_CHAT_ID, f'Ошибка при обновлении статуса: {str(e)}')

def process_callback_query(update, last_update_id):
    """Process callback query from button click"""
    callback_query = update.get('callback_query')
    if not callback_query:
        return last_update_id, False
        
    logger.info('=== CALLBACK QUERY RECEIVED ===')
    logger.info(f'Callback data: {callback_query.get("data", "No data")}')
    
    handle_callback_query(callback_query)
    return update['update_id'] + 1, True

def process_message(update, last_update_id):
    """Process regular message or channel post"""
    # Check if it's a regular message or channel post
    message = update.get('message') or update.get('channel_post')
    if not message:
        logger.warning('No message found in update')
        return last_update_id, False
    
    chat_id = message.get('chat', {}).get('id')
    if not chat_id:
        logger.warning('No chat ID in message')
        return last_update_id, False
    
    logger.info(f'Received message from chat {chat_id}')
    
    # Check if message is from target chat
    if str(chat_id) == TELEGRAM_CHAT_ID:
        logger.info('Message is from target chat')
        save_message(message)
    else:
        logger.info(f'Message is from different chat: {chat_id}')
    
    return update['update_id'] + 1, True

def main():
    """Start the bot"""
    logger.info('Starting CRM bot')
    logger.info(f'Using chat ID: {TELEGRAM_CHAT_ID}')
    
    # Send startup message without buttons
    try:
        send_message(TELEGRAM_CHAT_ID, 'CRM бот запущен и готов принимать заявки!')
        logger.info('Startup message sent successfully')
    except Exception as e:
        logger.error(f'Error sending startup message: {e}')
        return
    
    last_update_id = None
    
    while True:
        try:
            # Get updates from Telegram API
            updates = get_updates(last_update_id)
            update_count = len(updates.get("result", []))
            
            if update_count > 0:
                logger.info(f'Received {update_count} updates')
            
            if updates.get('ok', False):
                for update in updates.get('result', []):
                    # Process callback queries (button clicks)
                    new_id, processed = process_callback_query(update, last_update_id)
                    if processed:
                        last_update_id = new_id
                        continue
                    
                    # Process regular messages and channel posts
                    new_id, processed = process_message(update, last_update_id)
                    if processed:
                        last_update_id = new_id
            else:
                error_msg = updates.get("description", "Unknown error")
                logger.error(f'Error in updates response: {error_msg}')
                time.sleep(10)  
                
        except Exception as e:
            logger.error(f'Error in main loop: {e}')
            time.sleep(10)  
            
        time.sleep(5)

if __name__ == '__main__':
    main()
