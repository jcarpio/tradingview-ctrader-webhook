import os
import csv
import datetime
import asyncio
from flask import Flask, request, jsonify
from ctrader import CTrader  # Cliente WebSocket con refresh token
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv()

SECRET_TOKEN = os.getenv("SECRET_TOKEN")
ACCOUNT_ID = os.getenv("ACCOUNT_ID")
REFRESH_TOKEN = os.getenv("REFRESH_TOKEN")

# Inicializar cliente de cTrader con refresh token
ctrader = CTrader(refresh_token=REFRESH_TOKEN)

# Inicializar servidor Flask
app = Flask(__name__)

# Crear carpeta de logs si no existe
LOGS_DIR = "logs"
os.makedirs(LOGS_DIR, exist_ok=True)

@app.route("/webhook", methods=["POST"])
def webhook():
    # Validar token secreto desde el cuerpo del mensaje (para compatibilidad con TradingView)
    token = request.json.get("token", "")
    if token != SECRET_TOKEN:
       return jsonify({"error": "Unauthorized"}), 401

    # Leer datos JSON del body
    data = request.json
    symbol = data.get("symbol")
    order_type = data.get("order")
    volume = data.get("volume")

    if not all([symbol, order_type, volume]):
        return jsonify({"error": "Invalid payload"}), 400

    try:
        async def execute_order():
            await ctrader.connect()
            await ctrader.place_market_order(symbol, order_type, volume)

        asyncio.run(execute_order())

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
                "-"  # El SDK actual no devuelve order_id, pero se puede extender
            ])

        return jsonify({"status": "success", "symbol": symbol, "side": order_type, "volume": volume}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
