import os
from dotenv import load_dotenv
import requests
import json

# Load environment variables first
load_dotenv()
import sqlite3
from datetime import datetime
import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
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

def save_message(message):
    """Save message to database"""
    try:
        logger.info('Saving message to database')
        logger.info(f'Message content: {message}')
        logger.info(f'Message type: {type(message)}')
        logger.info(f'Message keys: {message.keys()}')
        
        # Get sender information for channel post
        sender_chat = message.get('sender_chat')
        if sender_chat:
            sender_id = sender_chat.get('id')
            username = sender_chat.get('username', 'Аноним')
        else:
            # Get sender information for regular message
            sender = message.get('from')
            if not sender:
                logger.warning('No sender information in message')
                return
                
            sender_id = sender.get('id')
            username = sender.get('username', 'Аноним')
        
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
        
        # Send confirmation message with buttons
        buttons = [
            [{'text': 'Принято', 'callback_data': f'status_accepted|{lead_id}'},
             {'text': 'В работе', 'callback_data': f'status_in_progress|{lead_id}'},
             {'text': 'Отказ', 'callback_data': f'status_declined|{lead_id}'}]
        ]
        
        send_message(TELEGRAM_CHAT_ID, f'Новая заявка от {username} (ID: {sender_id})\n\n{text}', buttons)
        
        # Notify user about new lead
        send_message(sender_id, f'Ваша заявка принята!\n\n{text}\n\nСтатус: новый')
        
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
        return response.json()
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

def delete_message(chat_id, message_id):
    """Delete message from Telegram chat"""
    try:
        data = {
            'chat_id': chat_id,
            'message_id': message_id
        }
        response = requests.post(f'{TELEGRAM_API_URL}/deleteMessage', json=data)
        response.raise_for_status()
        logger.info(f'Message deleted: {message_id}')
    except Exception as e:
        logger.error(f'Error deleting message: {e}')

def handle_callback_query(callback_query):
    """Handle callback query from button click"""
    try:
        logger.info('=== START handle_callback_query ===')
        logger.info(f'Full callback query: {callback_query}')
        logger.info(f'Callback query type: {type(callback_query)}')
        logger.info(f'Callback query keys: {callback_query.keys()}')
        
        # Log callback query details
        logger.info(f'Callback query details: {callback_query}')
        logger.info(f'Callback data: {callback_query.get("data", "No data")}')
        
        # Get message ID from callback query
        message_id = callback_query.get('message', {}).get('message_id')
        if not message_id:
            logger.warning('No message ID in callback query')
            return
            
        data = callback_query.get('data', '')
        if not data:
            logger.warning('No callback data')
            return
            
        # Log raw data before parsing
        logger.info(f'Raw callback data: {data}')
        
        # Try to parse callback data
        try:
            # First try to split by '|'
            parts = data.split('|')
            if len(parts) == 2:
                status, lead_id = parts
                status = status.replace('status_', '')
            else:
                # If that doesn't work, try to extract lead_id from the end
                lead_id = data.split('|')[-1]
                status = 'accepted' if 'accepted' in data else 'declined' if 'declined' in data else 'in_progress'
                
            # Log parsed data
            logger.info(f'Parsed status: {status}, lead_id: {lead_id}, message_id: {message_id}')
            
            # Update lead status in database
            conn = sqlite3.connect('crm.db')
            cursor = conn.cursor()
            
            # Get user who clicked the button
            user_id = callback_query.get('from', {}).get('id')
            username = callback_query.get('from', {}).get('username')
            first_name = callback_query.get('from', {}).get('first_name')
            
            # Get lead information
            cursor.execute('SELECT * FROM leads WHERE id = ?', (int(lead_id),))
            lead = cursor.fetchone()
            if not lead:
                logger.error(f'Lead not found: {lead_id}')
                return
                
            # Update lead status and add executor
            cursor.execute('''
                UPDATE leads 
                SET status = ?, executor_id = ?, executor_username = ?, executor_first_name = ?
                WHERE id = ?
            ''', (status, user_id, username, first_name, int(lead_id)))
            
            conn.commit()
            conn.close()
            
            logger.info(f'Updated lead status: lead_id={lead_id}, status={status}, executor_id={user_id}, executor_username={username}, executor_first_name={first_name}')
            
            # Notify user about status change
            send_message(lead[1], f'Ваша заявка обработана!\n\nСтатус: {status}\n\nИсполнитель: {first_name} (@{username})')
            
            # Send confirmation message to channel
            send_message(TELEGRAM_CHAT_ID, f'Статус заявки обновлен: {status}. Исполнитель: {first_name} (@{username})')
            
            # Delete old message with buttons
            delete_message(TELEGRAM_CHAT_ID, message_id)
            
            # Answer callback query
            answer_callback_query(callback_query.get('id'), f'Статус: {status}')
            
            logger.info('=== END handle_callback_query ===')
            
        except Exception as e:
            logger.error(f'Error parsing callback data: {e}')
            return
            
    except Exception as e:
        logger.error(f'Error handling callback query: {e}')
        send_message(TELEGRAM_CHAT_ID, f'Ошибка при обновлении статуса: {str(e)}')
        answer_callback_query(callback_query.get('id'), 'Ошибка при обновлении статуса')

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
            logger.info('Checking for updates...')
            updates = get_updates(last_update_id)
            logger.info(f'Received updates: {len(updates.get("result", []))}')
            
            if updates.get('ok', False):
                for update in updates.get('result', []):
                    logger.info(f'Raw update: {update}')
                    
                    # Check for callback query (button click)
                    callback_query = update.get('callback_query')
                    if callback_query:
                        logger.info('=== CALLBACK QUERY RECEIVED ===')
                        logger.info(f'Callback query: {callback_query}')
                        logger.info(f'Callback query type: {type(callback_query)}')
                        logger.info(f'Callback query keys: {callback_query.keys()}')
                        logger.info(f'Callback data: {callback_query.get("data", "No data")}')
                        logger.info(f'Callback query ID: {callback_query.get("id")}')
                        
                        handle_callback_query(callback_query)
                        last_update_id = update['update_id'] + 1
                        continue
                    
                    # Check if it's a channel post
                    message = update.get('message')
                    if not message:
                        message = update.get('channel_post')
                    if not message:
                        logger.warning('No message found in update')
                        continue
                    
                    logger.info(f'Received message from chat {message["chat"]["id"]}')
                    logger.info(f'Message content: {message.get("text", "No text")}')
                    
                    # Log message details
                    logger.info(f'Message type: {type(message)}')
                    logger.info(f'Message keys: {message.keys()}')
                    logger.info(f'Message text type: {type(message.get("text"))}')
                    
                    if str(message['chat']['id']) == TELEGRAM_CHAT_ID:
                        logger.info('Message is from target chat')
                        save_message(message)
                    else:
                        logger.info(f'Message is from different chat: {message["chat"]["id"]}')
                    
                    last_update_id = update['update_id'] + 1
            else:
                logger.error(f'Error in updates response: {updates.get("description", "Unknown error")}')
                time.sleep(10)  
                
        except Exception as e:
            logger.error(f'Error in main loop: {e}')
            time.sleep(10)  
            
        time.sleep(5)  

if __name__ == '__main__':
    main()
