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
            
        # Save to database
        conn = sqlite3.connect('crm.db')
        cursor = conn.cursor()
        
        cursor.execute('INSERT INTO leads (telegram_id, username, message) VALUES (?, ?, ?)',
                      (sender_id, username, text))
        
        lead_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        logger.info(f'Message saved with lead_id: {lead_id}')
        
        # Delete original message
        message_id = message.get('message_id')
        if message_id:
            delete_message(TELEGRAM_CHAT_ID, message_id)
        
        # Send new message with buttons
        buttons = create_status_buttons(lead_id)
        send_message(TELEGRAM_CHAT_ID, f'Новая заявка от {username} (ID: {sender_id})\n\n{text}', buttons)
        
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

def answer_callback_query(callback_query_id, text=None):
    """Answer callback query"""
    try:
        payload = {
            'callback_query_id': callback_query_id
        }
        if text:
            payload['text'] = text
            payload['show_alert'] = False

        response = requests.post(f'{TELEGRAM_API_URL}/answerCallbackQuery', json=payload)
        response.raise_for_status()
        logger.info('Answered callback query')
    except Exception as e:
        logger.error(f'Error answering callback query: {e}')

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
            
        # Update lead status
        update_lead_status(lead_id, status, executor_info)
        
        # Get updated lead information
        updated_lead = get_lead_by_id(lead_id)
        if updated_lead:
            # Format status text
            status_text = get_status_text(status)
            
            # Create message text
            new_text = f'Заявка от {updated_lead[2]} (ID: {updated_lead[1]})\n\n{updated_lead[3]}\n\nСтатус: {status_text}\nИсполнитель: {updated_lead[7]} (@{updated_lead[6]})'
            
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
