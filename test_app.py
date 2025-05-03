from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route('/test')
def test():
    return jsonify({'message': 'Test endpoint works!'})

@app.route('/lead_details/<int:lead_id>')
def get_lead_details(lead_id):
    # Простой тестовый ответ
    return jsonify({
        'id': lead_id,
        'client_name': 'Тестовый клиент',
        'phone': '+7 123 456 7890',
        'email': 'test@example.com',
        'source': 'Тестовый источник',
        'status': 'accepted',
        'executor_username': 'Тестовый исполнитель',
        'message': 'Тестовое сообщение',
        'created_at': '2023-01-01 12:00:00',
        'order_details': 'Тестовые детали заказа',
        'total_amount': '10 000 ₸',
        'related_leads': [],
        'related_count': 1
    })

if __name__ == "__main__":
    print("Starting test Flask server on port 5001...")
    app.run(host="0.0.0.0", port=5001, debug=True)
