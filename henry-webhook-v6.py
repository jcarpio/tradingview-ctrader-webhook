import os
import csv
import datetime
import traceback
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from twisted.internet import reactor, defer
from threading import Thread
from ctrader import run_ctrader_order, initialize_client

# Importaciones corregidas para la API de cTrader
from ctrader_open_api.messages.OpenApiMessages_pb2 import ProtoOAReconcileReq, ProtoOAClosePositionReq
from ctrader_open_api.messages.OpenApiModelMessages_pb2 import ProtoOATradeData

# Cargar variables de entorno
load_dotenv()
SECRET_TOKEN = os.getenv("SECRET_TOKEN")
ACCOUNT_ID = int(os.getenv("ACCOUNT_ID"))

# Configuración de límites
MAX_VOLUME = 50  # Volumen máximo permitido por la cuenta
DEFAULT_VOLUME = 0.1  # Volumen predeterminado para pruebas

# Inicializar servidor Flask
app = Flask(__name__)

# Crear carpeta de logs si no existe
LOGS_DIR = "logs"
os.makedirs(LOGS_DIR, exist_ok=True)

# Variable global para almacenar posiciones abiertas
open_positions = []

def get_open_positions():
    """
    Obtiene todas las posiciones abiertas para la cuenta
    """
    print("[cTrader] 🔍 Obteniendo posiciones abiertas...")
    client = initialize_client()[0]
    
    request = ProtoOAReconcileReq()
    request.ctidTraderAccountId = ACCOUNT_ID
    
    positions_deferred = defer.Deferred()
    
    def handle_positions(response):
        global open_positions
        # Resetear la lista de posiciones
        open_positions = []
        
        # Extraer posiciones del mensaje de reconciliación
        for position in response.position:
            # Solo almacenamos las posiciones abiertas
            if position.HasField('closeTime') == False:
                open_positions.append({
                    'positionId': position.positionId,
                    'symbolId': position.symbolId,
                    'volume': position.volume,
                    'tradeSide': position.tradeSide
                })
        
        print(f"[cTrader] ✅ Se encontraron {len(open_positions)} posiciones abiertas")
        positions_deferred.callback(open_positions)
        return open_positions
    
    def handle_error(error):
        print(f"[cTrader] ❌ Error al obtener posiciones: {error}")
        positions_deferred.errback(error)
        return error
    
    d = client.send(request)
    d.addCallback(handle_positions)
    d.addErrback(handle_error)
    
    return positions_deferred

def close_all_positions():
    """
    Cierra todas las posiciones abiertas en la cuenta
    """
    print("[cTrader] 🔒 Cerrando todas las posiciones abiertas...")
    
    # Primero obtenemos todas las posiciones abiertas
    get_positions_deferred = get_open_positions()
    close_all_deferred = defer.Deferred()
    
    def close_positions(positions):
        if not positions:
            print("[cTrader] ℹ️ No hay posiciones abiertas para cerrar")
            close_all_deferred.callback([])
            return
        
        client = initialize_client()[0]
        pending_closes = len(positions)
        results = []
        
        # Función para actualizar el contador y notificar cuando se completen todos los cierres
        def update_pending(result=None, error=None):
            nonlocal pending_closes
            if result:
                results.append(result)
            if error:
                results.append(f"Error: {error}")
            
            pending_closes -= 1
            if pending_closes <= 0:
                print(f"[cTrader] ✅ Todas las posiciones han sido procesadas")
                close_all_deferred.callback(results)
        
        # Cerrar cada posición
        for position in positions:
            # Usar la clase correcta ProtoOAClosePositionReq en lugar de ProtoOAPositionCloseReq
            close_request = ProtoOAClosePositionReq()
            close_request.ctidTraderAccountId = ACCOUNT_ID
            close_request.positionId = position['positionId']
            
            print(f"[cTrader] 🔒 Cerrando posición ID: {position['positionId']}")
            
            d = client.send(close_request)
            
            def on_close_success(response, pos_id=position['positionId']):
                print(f"[cTrader] ✅ Posición {pos_id} cerrada correctamente")
                return update_pending(result=f"Posición {pos_id} cerrada")
            
            def on_close_error(error, pos_id=position['positionId']):
                print(f"[cTrader] ❌ Error al cerrar posición {pos_id}: {error}")
                return update_pending(error=f"Error al cerrar posición {pos_id}: {error}")
            
            d.addCallback(on_close_success)
            d.addErrback(on_close_error)
    
    def on_get_positions_error(error):
        print(f"[cTrader] ❌ Error al obtener posiciones: {error}")
        close_all_deferred.errback(error)
    
    get_positions_deferred.addCallback(close_positions)
    get_positions_deferred.addErrback(on_get_positions_error)
    
    return close_all_deferred

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
        
        # Usar un volumen pequeño para prueba si es muy grande
        if volume > 10:
            print(f"⚠️ Volumen {volume} es grande, considere reducirlo para evitar errores de saldo")
        
        if not all([symbol, order_type]):
            return jsonify({
                "error": "Invalid payload - missing required parameters",
                "received": data
            }), 400
        
        # Registrar que se recibió el webhook
        print(f"📩 Webhook recibido: {symbol} {order_type} {volume}")
        
        # Ejecutar orden (desde el hilo de Twisted)
        def execute_order():
            try:
                # Primero cerramos todas las posiciones abiertas
                print("[cTrader] 🔄 Cerrando posiciones antes de abrir nueva orden...")
                d_close = close_all_positions()
                
                def on_positions_closed(result):
                    print(f"[cTrader] ✅ Posiciones cerradas: {result}")
                    log_operation("ALL", "CLOSE", 0, "SUCCESS")
                    
                    # Ahora ejecutamos la nueva orden
                    print(f"[cTrader] 🔄 Ejecutando nueva orden {order_type} para {symbol}...")
                    d_order = run_ctrader_order(symbol, order_type.upper(), volume)
                    
                    def on_order_success(result):
                        print(f"[cTrader] ✅ Nueva orden completada: {result}")
                        log_operation(symbol, order_type, volume, "SUCCESS")
                    
                    def on_order_error(err):
                        print(f"[cTrader] ❌ Error en la nueva orden: {err}")
                        log_operation(symbol, order_type, volume, f"ERROR: {err}")
                    
                    d_order.addCallback(on_order_success)
                    d_order.addErrback(on_order_error)
                
                def on_positions_close_error(err):
                    print(f"[cTrader] ⚠️ Error al cerrar posiciones: {err}")
                    log_operation("ALL", "CLOSE", 0, f"ERROR: {err}")
                    
                    # A pesar del error, intentamos ejecutar la orden
                    print(f"[cTrader] 🔄 Intentando ejecutar orden a pesar del error al cerrar posiciones...")
                    d_order = run_ctrader_order(symbol, order_type.upper(), volume)
                    
                    def on_order_success(result):
                        print(f"[cTrader] ✅ Orden completada a pesar del error previo: {result}")
                        log_operation(symbol, order_type, volume, "SUCCESS (after close error)")
                    
                    def on_order_error(err):
                        print(f"[cTrader] ❌ Error en la orden: {err}")
                        log_operation(symbol, order_type, volume, f"ERROR: {err}")
                    
                    d_order.addCallback(on_order_success)
                    d_order.addErrback(on_order_error)
                
                d_close.addCallback(on_positions_closed)
                d_close.addErrback(on_positions_close_error)
                
            except Exception as e:
                print(f"❌ Error al ejecutar el proceso de cerrar y abrir: {str(e)}")
                traceback.print_exc()
                log_operation(symbol, order_type, volume, f"EXCEPTION: {str(e)}")
        
        # Programamos la ejecución en el reactor de Twisted
        reactor.callFromThread(execute_order)
        
        # Devolvemos respuesta inmediata (la orden se procesa async)
        return jsonify({
            "status": "processing", 
            "message": f"Orden enviada a procesar (cerrando posiciones y abriendo {symbol} {order_type}, volumen: {volume})",
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
