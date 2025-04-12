from flask import Flask, request, jsonify
# from openapi_client import ApiClient, Configuration
# from openapi_client.api import trading_api
import csv
import os
import datetime

app = Flask(__name__)

# Configuración de cTrader Open API
client_id = '14142_djlb7UtWxzhlNaWXphdzfvn6VW96IK4BKDOnxzRwlL6KeByF35'
client_secret = 'cV8zSl6jTbnOgcJc20iEiuCFyNiGzFetEy1zgArunjOWnBUZGV'
access_token = 'TU_ACCESS_TOKEN'  # Obtenido tras la autenticación
account_id = '5150591'      # ID de la cuenta de trading

# configuration = Configuration(
#    host="https://api.spotware.com",
#    access_token=access_token
# )
# api_client = ApiClient(configuration)
# trading = trading_api.TradingApi(api_client)

# Token secreto para validar las solicitudes entrantes
SECRET_TOKEN = '3mXOWS5pGisyuOITUTkb3mtUElInZOkyJxWxHImfrSA='

# Ruta del directorio de logs
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

def log_trade(data):
    now = datetime.datetime.utcnow()
    filename = f"operations_{now.strftime('%Y-%m')}.csv"
    filepath = os.path.join(LOG_DIR, filename)

    write_header = not os.path.exists(filepath)
    with open(filepath, mode='a', newline='') as file:
        writer = csv.writer(file)
        if write_header:
            writer.writerow(["timestamp", "symbol", "order", "volume"])
        writer.writerow([
            now.strftime('%Y-%m-%d %H:%M:%S'),
            data.get('symbol'),
            data.get('order'),
            data.get('volume')
        ])

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    if not data or data.get("token") != SECRET_TOKEN:
        return jsonify({'error': 'Unauthorized'}), 403

    symbol = data.get("symbol")
    order = data.get("order")
    volume = data.get("volume")

    # Aquí conectarías con la API de cTrader para lanzar la orden real
    print(f"Ejecutando orden: {order} {volume} de {symbol}")

    # Registrar la operación en CSV
    log_trade(data)

    return jsonify({'status': 'success', 'message': 'Orden procesada correctamente'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)


