import os
from dotenv import load_dotenv
import requests
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
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            username TEXT,
            message TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def save_message(message):
    """Save message to database"""
    try:
        conn = sqlite3.connect('crm.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO leads (telegram_id, username, message)
            VALUES (?, ?, ?)
        ''', (
            message['from']['id'],
            message['from'].get('username', ''),
            message['text']
        ))
        conn.commit()
        conn.close()
        logger.info(f'Saved message from user {message["from"]["id"]}')
    except Exception as e:
        logger.error(f'Error saving message: {e}')

def get_updates(offset=None):
    """Get updates from Telegram API"""
    try:
        params = {'timeout': 100}
        if offset:
            params['offset'] = offset
        response = requests.get(f'{TELEGRAM_API_URL}/getUpdates', params=params)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f'Error getting updates: {e}')
        return {'result': []}

def send_message(chat_id, text):
    """Send message to Telegram chat"""
    try:
        data = {
            'chat_id': chat_id,
            'text': text
        }
        response = requests.post(f'{TELEGRAM_API_URL}/sendMessage', json=data)
        response.raise_for_status()
    except Exception as e:
        logger.error(f'Error sending message: {e}')

def main():
    """Start the bot"""
    logger.info('Starting CRM bot')
    
    # Send startup message
    try:
        send_message(TELEGRAM_CHAT_ID, 'CRM бот запущен и готов принимать заявки!')
    except Exception as e:
        logger.error(f'Error sending startup message: {e}')
        return
    
    last_update_id = None
    
    while True:
        try:
            updates = get_updates(last_update_id)
            logger.info(f'Received updates: {len(updates.get("result", []))}')
            
            for update in updates.get('result', []):
                message = update.get('message')
                if not message:
                    continue
                
                logger.info(f'Received message from chat {message["chat"]["id"]}')
                
                if str(message['chat']['id']) == TELEGRAM_CHAT_ID:
                    save_message(message)
                
                last_update_id = update['update_id'] + 1
                
        except Exception as e:
            logger.error(f'Error in main loop: {e}')
            time.sleep(5)  # Wait longer on error
            
        time.sleep(1)

if __name__ == '__main__':
    main()
