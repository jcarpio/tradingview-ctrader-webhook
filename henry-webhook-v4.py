import os
import csv
import datetime
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from twisted.internet import reactor
from ctrader import run_ctrader_order

# Cargar variables de entorno
load_dotenv()

SECRET_TOKEN = os.getenv("SECRET_TOKEN")

# Inicializar servidor Flask
app = Flask(__name__)

# Crear carpeta de logs si no existe
LOGS_DIR = "logs"
os.makedirs(LOGS_DIR, exist_ok=True)

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        token = request.json.get("token", "")
        if token != SECRET_TOKEN:
            return jsonify({"error": "Unauthorized"}), 401

        data = request.json
        symbol = data.get("symbol")
        order_type = data.get("order")
        volume = data.get("volume")

        if not all([symbol, order_type, volume]):
            return jsonify({"error": "Invalid payload"}), 400

        # Ejecutar orden usando el reactor de Twisted
        run_ctrader_order(symbol, order_type.upper(), int(volume))

        # Registrar operación
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
                "-"  # No se recibe order_id en esta versión aún
            ])

        return jsonify({"status": "success", "symbol": symbol, "side": order_type, "volume": volume}), 200

    except Exception as e:
        print("❌ Error procesando webhook:", str(e))
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    from threading import Thread

    def run_flask():
        app.run(host="0.0.0.0", port=5001, debug=True)

    Thread(target=run_flask).start()
    reactor.run()
