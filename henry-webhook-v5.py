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

# Configuración de límites
MAX_VOLUME = 50  # Volumen máximo permitido por la cuenta
DEFAULT_VOLUME = 0.1  # Volumen predeterminado para pruebas

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
        
        # Obtener y validar el volumen
        try:
            volume = float(data.get("volume", DEFAULT_VOLUME))
        except (ValueError, TypeError):
            volume = DEFAULT_VOLUME

# Limitar el volumen al máximo permitido
        volume = min(volume, MAX_VOLUME)
        
        # Obtener stop loss y take profit en pips si están presentes
        sl_pips = data.get("sl_pips")
        tp_pips = data.get("tp_pips")
        
        # Obtener el color de la vela (para lógica de mantener/cerrar posiciones)
        candle_color = data.get("candle_color")
        
        # Validar los valores de stop loss y take profit
        if sl_pips is not None:
            try:
                sl_pips = float(sl_pips)
                # Si es 0, se ignora el stop loss
                if sl_pips < 0:
                    print(f"⚠️ Valor de stop loss en pips debe ser positivo: {sl_pips}. Se ignora.")
                    sl_pips = 0
            except (ValueError, TypeError):
                print(f"⚠️ Valor de stop loss en pips inválido: {sl_pips}. Se ignora.")
                sl_pips = None
        
        if tp_pips is not None:
            try:
                tp_pips = float(tp_pips)
                # Si es 0, se ignora el take profit
                if tp_pips < 0:
                    print(f"⚠️ Valor de take profit en pips debe ser positivo: {tp_pips}. Se ignora.")
                    tp_pips = 0
            except (ValueError, TypeError):
                print(f"⚠️ Valor de take profit en pips inválido: {tp_pips}. Se ignora.")
                tp_pips = None
        
        # Validar el color de la vela
        if candle_color is not None:
            candle_color = candle_color.upper()
            if candle_color not in ["GREEN", "RED"]:
                print(f"⚠️ Color de vela inválido: {candle_color}. Debe ser 'GREEN' o 'RED'. Se ignora.")
                candle_color = None
        
        if not all([symbol, order_type]):
            return jsonify({
                "error": "Invalid payload - missing required parameters",
                "received": data
            }), 400
        
        # Registrar que se recibió el webhook
        log_message = f"📩 Webhook recibido: {symbol} {order_type} {volume}"
        if sl_pips is not None:
            log_message += f" SL:{sl_pips} pips"
        if tp_pips is not None:
            log_message += f" TP:{tp_pips} pips"
        if candle_color:
            log_message += f" Vela:{candle_color}"
        print(log_message)

# Ejecutar orden (desde el hilo de Twisted)
        def execute_order():
            try:
                d = run_ctrader_order(
                    symbol, 
                    order_type.upper(), 
                    volume, 
                    sl_pips=sl_pips, 
                    tp_pips=tp_pips, 
                    candle_color=candle_color
                )
                
                def on_order_success(result):
                    status = "SUCCESS"
                    # Verificar si el resultado contiene un estado específico (mantenido, cerrado)
                    if isinstance(result, dict) and "status" in result:
                        status = result["status"].upper()
                        message = result.get("message", "")
                        print(f"✅ Operación completada: {status} - {message}")
                    else:
                        print(f"✅ Orden completada: {result}")
                    
                    log_operation(
                        symbol, 
                        order_type, 
                        volume, 
                        status, 
                        sl_pips=sl_pips, 
                        tp_pips=tp_pips, 
                        candle_color=candle_color
                    )
                
                def on_order_error(err):
                    print(f"❌ Error en la orden: {err}")
                    log_operation(
                        symbol, 
                        order_type, 
                        volume, 
                        f"ERROR: {err}", 
                        sl_pips=sl_pips, 
                        tp_pips=tp_pips, 
                        candle_color=candle_color
                    )
                
                d.addCallback(on_order_success)
                d.addErrback(on_order_error)
            except Exception as e:
                print(f"❌ Error al ejecutar orden: {str(e)}")
                traceback.print_exc()
                log_operation(
                    symbol, 
                    order_type, 
                    volume, 
                    f"EXCEPTION: {str(e)}", 
                    sl_pips=sl_pips, 
                    tp_pips=tp_pips, 
                    candle_color=candle_color
                )
        
        # Programamos la ejecución en el reactor de Twisted
        reactor.callFromThread(execute_order)
        
        # Devolvemos respuesta inmediata (la orden se procesa async)
        response_data = {
            "status": "processing", 
            "message": f"Orden enviada a procesar (volumen ajustado a {volume})",
            "details": {
                "symbol": symbol, 
                "side": order_type.upper(), 
                "volume": volume,
            }
        }
        
        # Incluir detalles adicionales si están presentes
        if sl_pips is not None:
            response_data["details"]["sl_pips"] = sl_pips
        if tp_pips is not None:
            response_data["details"]["tp_pips"] = tp_pips
        if candle_color:
            response_data["details"]["candle_color"] = candle_color
            
        return jsonify(response_data), 200
    
    except Exception as e:
        print(f"❌ Error procesando webhook: {str(e)}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

def log_operation(symbol, order_type, volume, status, sl_pips=None, tp_pips=None, candle_color=None):
    """Registra la operación en el archivo de log"""
    try:
        now = datetime.datetime.now(datetime.timezone.utc)
        log_filename = f"{LOGS_DIR}/operations_{now.strftime('%Y-%m')}.csv"
        write_header = not os.path.exists(log_filename)
        
        with open(log_filename, mode="a", newline="") as file:
            writer = csv.writer(file)
            if write_header:
                writer.writerow(["timestamp", "symbol", "order", "volume", "sl_pips", "tp_pips", "candle_color", "status"])
            writer.writerow([
                now.isoformat(),
                symbol,
                order_type.upper(),
                volume,
                sl_pips if sl_pips is not None else "",
                tp_pips if tp_pips is not None else "",
                candle_color if candle_color is not None else "",
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
