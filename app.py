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
        
        # Format leads for API response
        formatted_leads = []
        for lead in leads:
            user = users.get(lead['telegram_id'], {})
            formatted_lead = {
                'id': lead['id'],
                'username': user.get('username', 'Аноним'),
                'message': lead['message'],
                'created_at': format_date(lead['created_at'])
            }
            formatted_leads.append(formatted_lead)
        
        return jsonify(formatted_leads)
    except Exception as e:
        logger.error(f'Error in get_leads: {e}')
        raise

if __name__ == '__main__':
    logger.info('Starting Flask server')
    app.run(debug=True, host='0.0.0.0')
