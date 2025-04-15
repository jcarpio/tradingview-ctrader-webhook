import os
import time
from dotenv import load_dotenv
from ctrader_open_api import Client, Protobuf, EndPoints, TcpProtocol
from twisted.internet import reactor, defer

load_dotenv()

# Diccionario de símbolos conocidos con su symbolId en la demo de cTrader
SYMBOLS = {
    "BTCUSD": 22395,
    "ETHUSD": 22397,
    "EURUSD": 1,
    "XAUUSD": 41,
    # Puedes añadir más aquí si los necesitas
}

# ⚙️ Configuración
CLIENT_ID = os.getenv("CTRADER_CLIENT_ID")
CLIENT_SECRET = os.getenv("CTRADER_CLIENT_SECRET")
ACCESS_TOKEN = os.getenv("CTRADER_ACCESS_TOKEN")
REFRESH_TOKEN = os.getenv("CTRADER_REFRESH_TOKEN")
ACCOUNT_ID = int(os.getenv("ACCOUNT_ID"))

# Cliente global
client = None
account_authorized = False
connection_ready = defer.Deferred()

def initialize_client():
    """
    Inicializa y retorna un cliente cTrader
    """
    global client, connection_ready
    
    if client is None or not getattr(client, 'transport', None) or not client.transport.connected:
        print("[cTrader] 🔄 Inicializando cliente...")
        
        # Si hay un cliente anterior, intentar cerrarlo limpiamente
        if client is not None:
            try:
                client.stopService()
                print("[cTrader] ⚠️ Cliente anterior cerrado")
            except:
                pass
            
        # Crear un nuevo deferred para la conexión
        connection_ready = defer.Deferred()
        
        # Crear cliente usando el protocolo correcto
        client = Client(
            EndPoints.PROTOBUF_DEMO_HOST, 
            EndPoints.PROTOBUF_PORT, 
            TcpProtocol
        )
        # Configuramos los callbacks básicos
        client.setConnectedCallback(on_connected)
        client.setDisconnectedCallback(on_disconnected)
        client.setMessageReceivedCallback(on_message_received)
        # Iniciamos el servicio
        client.startService()
    
    return client, connection_ready

def on_connected(client_instance):
    """Callback cuando el cliente se conecta"""
    print("[cTrader] ✅ Conectado al servidor")
    
    # Siguiendo el enfoque del hilo, primero autenticamos la aplicación
    from ctrader_open_api.messages.OpenApiMessages_pb2 import ProtoOAApplicationAuthReq
    
    request = ProtoOAApplicationAuthReq()
    request.clientId = CLIENT_ID
    request.clientSecret = CLIENT_SECRET
    deferred = client_instance.send(request)
    deferred.addCallback(on_app_auth_success)
    deferred.addErrback(on_error)

def on_app_auth_success(response):
    """Callback después de autenticar la aplicación"""
    print("[cTrader] ✅ Aplicación autenticada correctamente")
    
    # Ahora autenticamos la cuenta
    from ctrader_open_api.messages.OpenApiMessages_pb2 import ProtoOAAccountAuthReq
    
    request = ProtoOAAccountAuthReq()
    request.ctidTraderAccountId = ACCOUNT_ID
    request.accessToken = ACCESS_TOKEN
    deferred = client.send(request)
    deferred.addCallback(on_account_auth_success)
    deferred.addErrback(on_error)
    
    return response

def on_account_auth_success(response):
    """Callback después de autenticar la cuenta"""
    global account_authorized, connection_ready
    
    print(f"[cTrader] ✅ Cuenta {ACCOUNT_ID} autenticada correctamente")
    account_authorized = True
    
    # Notificar que la conexión está lista
    if not connection_ready.called:
        connection_ready.callback(None)
    
    return response

def on_disconnected(client_instance, reason):
    """Callback cuando el cliente se desconecta"""
    global account_authorized, connection_ready
    
    print(f"[cTrader] ❌ Desconectado: {reason}")
    account_authorized = False
    
    # Reiniciar el deferred para la próxima conexión
    if connection_ready.called:
        connection_ready = defer.Deferred()
    
    # Programar reconexión automática después de un tiempo
    reactor.callLater(5, initialize_client)

def on_message_received(client_instance, message):
    """Callback para procesar mensajes recibidos"""
    from ctrader_open_api import Protobuf
    from ctrader_open_api.messages.OpenApiMessages_pb2 import ProtoOAExecutionEvent, ProtoOAErrorRes
    
    # Procesar mensajes de error
    if message.payloadType == ProtoOAErrorRes().payloadType:
        error_event = Protobuf.extract(message)
        print(f"[cTrader] ⚠️ Error recibido: {error_event}")
        
        # Si el error es de autorización, intentar reautenticar
        if "not authorized" in str(error_event).lower():
            print("[cTrader] 🔄 Reiniciando autenticación debido a error de autorización...")
            global account_authorized
            account_authorized = False
            on_connected(client)
    
    # Procesar mensajes de ejecución
    elif message.payloadType == ProtoOAExecutionEvent().payloadType:
        execution_event = Protobuf.extract(message)
        print(f"[cTrader] ✅ Evento de ejecución recibido: {execution_event}")

def on_error(failure):
    """Callback para manejar errores"""
    global connection_ready
    
    print(f"[cTrader] ❌ Error: {failure}")
    
    # En caso de error, notificar a cualquier deferred pendiente
    if not connection_ready.called:
        connection_ready.errback(failure)
    
    return failure

def send_market_order(symbol, side, volume):
    """
    Envía una orden de mercado
    
    Args:
        symbol: Símbolo a operar (ej. "EURUSD")
        side: Lado de la operación ("BUY" o "SELL")
        volume: Volumen en lotes
    """
    global account_authorized
    
    # Verificar que la cuenta esté autorizada
    if not account_authorized:
        raise Exception("Cuenta no autorizada. No se puede enviar la orden.")
    
    from ctrader_open_api.messages.OpenApiMessages_pb2 import ProtoOANewOrderReq
    from ctrader_open_api.messages.OpenApiModelMessages_pb2 import ProtoOAOrderType, ProtoOATradeSide
    
    if symbol not in SYMBOLS:
        raise Exception(f"❌ El símbolo {symbol} no está en la lista local. Añádelo a SYMBOLS.")
    
    symbol_id = SYMBOLS[symbol]
    
    # Configurar la orden
    request = ProtoOANewOrderReq()
    request.ctidTraderAccountId = ACCOUNT_ID
    request.symbolId = symbol_id
    request.orderType = ProtoOAOrderType.MARKET
    
    # Determinar el lado de la operación
    if side.upper() == "BUY":
        request.tradeSide = ProtoOATradeSide.BUY
    elif side.upper() == "SELL":
        request.tradeSide = ProtoOATradeSide.SELL
    else:
        raise ValueError(f"Lado de operación inválido: {side}. Debe ser 'BUY' o 'SELL'")
    
    # Convertir el volumen a centilotes (x100)
    # Para volúmenes pequeños como 0.01, esto se convierte en 1 centilote
    volume_in_centilotes = int(float(volume) * 100)
    
    # Asegurarnos de que el volumen sea al menos 1 centilote
    if volume_in_centilotes < 1:
        volume_in_centilotes = 1
        print(f"[cTrader] ⚠️ Volumen ajustado al mínimo: 0.01 lotes (1 centilote)")
    
    request.volume = volume_in_centilotes
    request.comment = "Order from TradingView Webhook"
    
    print(f"[cTrader] 🚀 Enviando orden {side} para {symbol} con volumen {volume} ({volume_in_centilotes} centilotes)")
    
    # Enviar la orden
    order_deferred = client.send(request)
    order_deferred.addCallback(on_order_sent)
    order_deferred.addErrback(on_order_error)
    
    return order_deferred

def on_order_sent(response):
    """Callback después de enviar una orden"""
    print(f"[cTrader] ✅ Orden enviada correctamente: {response}")
    return response

def on_order_error(failure):
    """Maneja errores al enviar órdenes"""
    print(f"[cTrader] ❌ Error al enviar orden: {failure}")
    
    # Si es un error de autorización, intentamos reautenticar
    if "not authorized" in str(failure).lower():
        global account_authorized
        account_authorized = False
        print("[cTrader] ⚠️ Error de autorización al enviar orden. Reiniciando autenticación...")
        on_connected(client)
    
    return failure

def run_ctrader_order(symbol, side, volume):
    """
    Función para ser llamada desde el webhook para ejecutar una orden
    
    Args:
        symbol: Símbolo a operar (ej. "EURUSD")
        side: Lado de la operación ("BUY" o "SELL")
        volume: Volumen en lotes
    """
    global client, account_authorized, connection_ready
    
    # Creamos un nuevo deferred para el resultado de esta operación
    result_deferred = defer.Deferred()
    
    try:
        # Inicializar cliente si no existe
        if client is None:
            client, connection_ready = initialize_client()
        
        # Función que envía la orden cuando la conexión está lista
        def send_order_when_ready(_=None):
            try:
                order_deferred = send_market_order(symbol, side, volume)
                
                def on_success(response):
                    if not result_deferred.called:
                        result_deferred.callback(response)
                    return response
                
                def on_failure(error):
                    if not result_deferred.called:
                        result_deferred.errback(error)
                    return error
                
                order_deferred.addCallback(on_success)
                order_deferred.addErrback(on_failure)
            except Exception as e:
                print(f"[cTrader] ❌ Error enviando orden: {str(e)}")
                if not result_deferred.called:
                    result_deferred.errback(e)
        
        # Función para manejar errores de conexión
        def on_connection_error(error):
            print(f"[cTrader] ❌ Error de conexión: {error}")
            if not result_deferred.called:
                result_deferred.errback(error)
            return error
        
        # Si la conexión ya está lista y la cuenta está autorizada
        if connection_ready.called and account_authorized:
            reactor.callLater(0, send_order_when_ready)
        # Si la conexión no está lista aún
        else:
            print("[cTrader] ⏳ Esperando a que la conexión esté lista...")
            connection_ready.addCallback(send_order_when_ready)
            connection_ready.addErrback(on_connection_error)
        
        return result_deferred
    
    except Exception as e:
        print(f"[cTrader SDK] ❌ Error ejecutando orden: {str(e)}")
        if not result_deferred.called:
            result_deferred.errback(e)
        return result_deferred
