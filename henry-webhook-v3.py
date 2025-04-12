import os
import csv
import datetime
from flask import Flask, request, jsonify
from ctrader import CTrader  # Asegúrate de tener este archivo listo en el mismo directorio
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv()

SECRET_TOKEN = os.getenv("SECRET_TOKEN")
CLIENT_ID = os.getenv("CTRADER_CLIENT_ID")
CLIENT_SECRET = os.getenv("CTRADER_CLIENT_SECRET")
ACCESS_TOKEN = os.getenv("CTRADER_ACCESS_TOKEN")
ACCOUNT_ID = os.getenv("CTRADER_ACCOUNT_ID")

# Inicializar cliente de cTrader
ctrader = CTrader(client_id=CLIENT_ID, client_secret=CLIENT_SECRET, access_token=ACCESS_TOKEN)

# Inicializar servidor Flask
app = Flask(__name__)

# Crear carpeta de logs si no existe
LOGS_DIR = "logs"
os.makedirs(LOGS_DIR, exist_ok=True)

@app.route("/webhook", methods=["POST"])
def webhook():
    # Validar token secreto desde header Authorization
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer ") or auth.split(" ")[1] != SECRET_TOKEN:
        return jsonify({"error": "Unauthorized"}), 401

    # Leer datos JSON del body
    data = request.json
    symbol = data.get("symbol")
    order_type = data.get("order")
    volume = data.get("volume")

    if not all([symbol, order_type, volume]):
        return jsonify({"error": "Invalid payload"}), 400

    try:
        # Ejecutar orden BUY o SELL
        if order_type.upper() == "BUY":
            response = ctrader.place_market_order(ACCOUNT_ID, symbol, "buy", volume)
        elif order_type.upper() == "SELL":
            response = ctrader.place_market_order(ACCOUNT_ID, symbol, "sell", volume)
        else:
            return jsonify({"error": "Unknown order type"}), 400

        # Registrar operación en logs mensuales
        now = datetime.datetime.now(datetime.timezone.utc)
        log_filename = f"{LOGS_DIR}/operations_{now.strftime('%Y-%m')}.csv"
        write_header = not os.path.exists(log_filename)

        with open(log_filename, mode="a", newline="") as file:
            writer = csv.writer(file)
            if write_header:
                writer.writerow(["timestamp", "symbol", "order", "volume", "order_id"])
            writer.writerow([
                now.isoformat(),
                symbol,
                order_type.upper(),
                volume,
                response.get("order_id", "N/A")
            ])

        return jsonify({"status": "success", "order": response}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
