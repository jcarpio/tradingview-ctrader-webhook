import os
import csv
import datetime
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from twisted.internet import reactor
from threading import Thread
from ctrader import run_ctrader_order, initialize_client

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
        data = request.json
        token = data.get("token", "")
        
        if token != SECRET_TOKEN:
            return jsonify({"error": "Unauthorized"}), 401
        
        symbol = data.get("symbol")
        order_type = data.get("order")
        volume = data.get("volume")
        
        if not all([symbol, order_type, volume]):
            return jsonify({"error": "Invalid payload"}), 400
        
        # Registrar que se recibió el webhook
        print(f"📩 Webhook recibido: {symbol} {order_type} {volume}")
        
        # Ejecutar orden (desde el hilo de Twisted)
        def execute_order():
            try:
                d = run_ctrader_order(symbol, order_type.upper(), int(volume))
                d.addCallback(lambda result: print(f"Orden completada: {result}"))
                d.addErrback(lambda err: print(f"Error en la orden: {err}"))
            except Exception as e:
                print(f"Error al ejecutar orden: {str(e)}")
        
        # Programamos la ejecución en el reactor de Twisted
        reactor.callFromThread(execute_order)
        
        # Registrar operación en el log
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
        
        return jsonify({
            "status": "success", 
            "message": "Orden enviada a cTrader",
            "details": {
                "symbol": symbol, 
                "side": order_type.upper(), 
                "volume": volume
            }
        }), 200
    except Exception as e:
        print(f"❌ Error procesando webhook: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    # Inicializar el cliente de cTrader 
    initialize_client()
    
    # Ejecutar Flask en un hilo separado
    def run_flask():
        app.run(host="0.0.0.0", port=5001, debug=False, use_reloader=False)
    
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    # Imprimir mensaje de inicio
    print(f"🚀 Servidor webhook iniciado en http://0.0.0.0:5001/webhook")
    
    # Iniciar el reactor de Twisted en el hilo principal
    reactor.run()
