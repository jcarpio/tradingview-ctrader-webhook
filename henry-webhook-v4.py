import os
import csv
import datetime
import traceback
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
        # Verificar si es una solicitud JSON
        if not request.is_json:
            # TradingView a veces envía datos como x-www-form-urlencoded
            data = request.form.to_dict()
            if not data:
                # Si no hay datos en form, intenta obtener de los parámetros de la URL
                data = request.args.to_dict()
                if not data:
                    # Último recurso: intentar parsear el body como texto
                    try:
                        import json
                        data = json.loads(request.data.decode('utf-8'))
                    except:
                        pass
        else:
            data = request.json
        
        print(f"📩 Webhook recibido con datos: {data}")
        
        # Verificar token si está configurado
        token = data.get("token", "")
        if SECRET_TOKEN and token != SECRET_TOKEN:
            return jsonify({"error": "Unauthorized"}), 401
        
        # Obtener parámetros de la orden
        symbol = data.get("symbol")
        order_type = data.get("order")
        volume = data.get("volume")
        
        if not all([symbol, order_type, volume]):
            return jsonify({
                "error": "Invalid payload - missing required parameters",
                "received": data
            }), 400
        
        # Registrar que se recibió el webhook
        print(f"📩 Webhook recibido: {symbol} {order_type} {volume}")
        
        # Ejecutar orden (desde el hilo de Twisted)
        def execute_order():
            try:
                d = run_ctrader_order(symbol, order_type.upper(), int(volume))
                
                def on_order_success(result):
                    print(f"✅ Orden completada: {result}")
                    log_operation(symbol, order_type, volume, "SUCCESS")
                
                def on_order_error(err):
                    print(f"❌ Error en la orden: {err}")
                    log_operation(symbol, order_type, volume, f"ERROR: {err}")
                
                d.addCallback(on_order_success)
                d.addErrback(on_order_error)
            except Exception as e:
                print(f"❌ Error al ejecutar orden: {str(e)}")
                traceback.print_exc()
                log_operation(symbol, order_type, volume, f"EXCEPTION: {str(e)}")
        
        # Programamos la ejecución en el reactor de Twisted
        reactor.callFromThread(execute_order)
        
        # Devolvemos respuesta inmediata (la orden se procesa async)
        return jsonify({
            "status": "processing", 
            "message": "Orden enviada a procesar",
            "details": {
                "symbol": symbol, 
                "side": order_type.upper(), 
                "volume": volume
            }
        }), 200
    
    except Exception as e:
        print(f"❌ Error procesando webhook: {str(e)}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

def log_operation(symbol, order_type, volume, status):
    """Registra la operación en el archivo de log"""
    try:
        now = datetime.datetime.now(datetime.timezone.utc)
        log_filename = f"{LOGS_DIR}/operations_{now.strftime('%Y-%m')}.csv"
        write_header = not os.path.exists(log_filename)
        
        with open(log_filename, mode="a", newline="") as file:
            writer = csv.writer(file)
            if write_header:
                writer.writerow(["timestamp", "symbol", "order", "volume", "status"])
            writer.writerow([
                now.isoformat(),
                symbol,
                order_type.upper(),
                volume,
                status
            ])
    except Exception as e:
        print(f"❌ Error al registrar operación: {str(e)}")

if __name__ == "__main__":
    # Inicializar el cliente de cTrader y obtener el deferred
    client, connection_ready = initialize_client()
    
    # Registrar un callback para saber cuando la conexión está lista
    def on_connection_ready(_):
        print("✅ Conexión cTrader establecida y lista para recibir órdenes")
    
    def on_connection_failed(failure):
        print(f"❌ Error al establecer conexión cTrader: {failure}")
    
    connection_ready.addCallback(on_connection_ready)
    connection_ready.addErrback(on_connection_failed)
    
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
