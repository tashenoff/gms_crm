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
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create leads table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            message TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (telegram_id) REFERENCES users (telegram_id)
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
        
        # Get sender ID and username
        sender_id = message.get('sender_chat', {}).get('id', 0)
        if not sender_id:
            sender_id = message.get('chat', {}).get('id', 0)
        
        username = message.get('sender_chat', {}).get('username', 'Аноним')
        if not username:
            username = message.get('chat', {}).get('username', 'Аноним')
        
        # Get message text
        text = message.get('text', '')
        if not text:
            text = message.get('caption', '')
        
        if not text:
            logger.warning('No text found in message')
            return
        
        # Save message
        cursor.execute('''
            INSERT INTO leads (telegram_id, username, message)
            VALUES (?, ?, ?)
        ''', (
            sender_id,
            username,
            text
        ))
        
        # Get last inserted ID
        lead_id = cursor.lastrowid
        logger.info(f'Saved lead with ID: {lead_id}')
        
        # Verify the lead was saved
        cursor.execute('SELECT * FROM leads WHERE id = ?', (lead_id,))
        lead = cursor.fetchone()
        logger.info(f'Saved lead info: {lead}')
        
        conn.commit()
        conn.close()
        logger.info(f'Successfully saved message from channel {sender_id}')
        
        # Send confirmation message
        send_message(TELEGRAM_CHAT_ID, f'Сообщение сохранено!\nОтправитель: {username}\nТекст: {text}')
        
    except Exception as e:
        logger.error(f'Error saving message: {e}')
        logger.error(f'Message data: {message}')
        send_message(TELEGRAM_CHAT_ID, f'Ошибка при сохранении сообщения: {str(e)}')

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
    logger.info(f'Using chat ID: {TELEGRAM_CHAT_ID}')
    
    # Send startup message
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
