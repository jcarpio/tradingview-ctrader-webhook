import os
from dotenv import load_dotenv
from ctrader_open_api import Client, EndPoints, TcpProtocol
from twisted.internet import reactor, defer

load_dotenv()

# Diccionario de símbolos conocidos con su symbolId en la demo de cTrader
SYMBOLS = {
    "BTCUSD": 6080842,
    "ETHUSD": 6080843,
    "EURUSD": 1,
    "XAUUSD": 2,
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

# Contador de reintentos de autenticación
auth_attempts = 0
MAX_AUTH_ATTEMPTS = 3

# Añadimos un flag para ignorar el error específico
ignore_account_not_found = True  # Cambiar a False si quieres que el error detenga el proceso

def initialize_client():
    """
    Inicializa y retorna un cliente cTrader
    """
    global client, connection_ready, auth_attempts, account_authorized
    
    # Reiniciar contador de intentos
    auth_attempts = 0
    
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
        account_authorized = False
        
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
    elif not connection_ready.called:
        # Si el cliente existe pero el deferred no ha sido llamado, creamos uno nuevo
        connection_ready = defer.Deferred()
        # Y forzamos reconexión
        on_connected(client)
    else:
        # Si ya hay un cliente conectado y el deferred ya fue llamado
        # Verificamos si la cuenta está autorizada
        if not account_authorized:
            # Creamos un nuevo deferred y forzamos reconexión
            connection_ready = defer.Deferred()
            on_connected(client)
    
    return client, connection_ready

def on_connected(client_instance):
    """Callback cuando el cliente se conecta"""
    global auth_attempts
    
    print("[cTrader] ✅ Conectado al servidor")
    auth_attempts += 1
    
    if auth_attempts > MAX_AUTH_ATTEMPTS:
        print(f"[cTrader] ⚠️ Demasiados intentos de autenticación ({auth_attempts}). Forzando reconexión completa...")
        reactor.callLater(0, force_reconnect)
        return
    
    from ctrader_open_api.messages.OpenApiMessages_pb2 import ProtoOAApplicationAuthReq
    
    # Autenticamos la aplicación
    request = ProtoOAApplicationAuthReq()
    request.clientId = CLIENT_ID
    request.clientSecret = CLIENT_SECRET
    deferred = client_instance.send(request)
    deferred.addCallback(on_app_auth_success)
    deferred.addErrback(on_app_auth_error)

def on_app_auth_success(response):
    """Callback después de autenticar la aplicación"""
    print("[cTrader] ✅ Aplicación autenticada correctamente")
    
    # Autenticamos la cuenta
    from ctrader_open_api.messages.OpenApiMessages_pb2 import ProtoOAAccountAuthReq
    request = ProtoOAAccountAuthReq()
    request.ctidTraderAccountId = ACCOUNT_ID
    request.accessToken = ACCESS_TOKEN
    
    # En el caso de que queramos implementar el token de actualización:
    if REFRESH_TOKEN:
        request.refreshToken = REFRESH_TOKEN
    
    deferred = client.send(request)
    deferred.addCallback(on_account_auth_success)
    deferred.addErrback(on_account_auth_error)
    
    return response

def on_app_auth_error(failure):
    """Maneja errores de autenticación de la aplicación"""
    global connection_ready
    
    print(f"[cTrader] ❌ Error autenticando aplicación: {failure}")
    
    # Notificar el error a cualquier espera por la conexión
    if not connection_ready.called:
        connection_ready.errback(failure)
    
    return failure

def on_account_auth_success(response):
    """Callback después de autenticar la cuenta"""
    global account_authorized, connection_ready, auth_attempts
    
    print(f"[cTrader] ✅ Cuenta {ACCOUNT_ID} autenticada correctamente")
    account_authorized = True
    auth_attempts = 0  # Resetear contador de intentos
    
    # Notificar que la conexión está lista
    if not connection_ready.called:
        connection_ready.callback(None)
    
    return response

def on_account_auth_error(failure):
    """Maneja errores de autenticación de la cuenta"""
    global connection_ready, auth_attempts, account_authorized
    
    print(f"[cTrader] ❌ Error autenticando cuenta: {failure}")
    
    # Si estamos ignorando el error específico y parece ser ese error
    if ignore_account_not_found and "CH_CTID_TRADER_ACCOUNT_NOT_FOUND" in str(failure):
        print("[cTrader] ⚠️ Cuenta no encontrada, pero continuamos por configuración.")
        account_authorized = True  # Marcamos como autorizada a pesar del error
        
        # Notificar que la conexión está lista (a pesar del error)
        if not connection_ready.called:
            connection_ready.callback(None)
        
        return failure
    
    if auth_attempts >= MAX_AUTH_ATTEMPTS:
        print(f"[cTrader] ⚠️ Demasiados intentos fallidos ({auth_attempts}).")
        
        # Notificar el error a cualquier espera por la conexión
        if not connection_ready.called:
            connection_ready.errback(failure)
    else:
        # Intentar de nuevo después de un tiempo
        print(f"[cTrader] 🔄 Reintentando autenticación (intento {auth_attempts}/{MAX_AUTH_ATTEMPTS})...")
        reactor.callLater(2, on_connected, client)
    
    return failure

def force_reconnect():
    """Fuerza una reconexión completa"""
    global client, account_authorized, connection_ready
    
    print("[cTrader] 🔄 Forzando reconexión completa...")
    
    # Reiniciar estado
    account_authorized = False
    
    # Si hay un cliente, cerrarlo
    if client is not None:
        try:
            client.stopService()
        except:
            pass
        client = None
    
    # Inicializar nuevo cliente
    new_client, new_connection = initialize_client()
    return new_client, new_connection

def on_disconnected(client_instance, reason):
    """Callback cuando el cliente se desconecta"""
    global account_authorized, connection_ready
    
    print(f"[cTrader] ❌ Desconectado: {reason}")
    account_authorized = False
    
    # Reiniciar el deferred para la próxima conexión
    if connection_ready.called:
        connection_ready = defer.Deferred()

def on_message_received(client_instance, message):
    """Callback para procesar mensajes recibidos"""
    from ctrader_open_api import Protobuf
    from ctrader_open_api.messages.OpenApiMessages_pb2 import ProtoOAExecutionEvent, ProtoOAErrorRes
    
    # Procesar mensajes de error
    if message.payloadType == ProtoOAErrorRes().payloadType:
        error_event = Protobuf.extract(message)
        print(f"[cTrader] ⚠️ Error recibido: {error_event}")
        
        # Si el error es específico de cuenta no encontrada y estamos configurados para ignorarlo
        if ignore_account_not_found and "CH_CTID_TRADER_ACCOUNT_NOT_FOUND" in str(error_event):
            print("[cTrader] ⚠️ Ignorando error de cuenta no encontrada por configuración")
            return
        
        # Si el error es de autorización y no es el específico que estamos ignorando
        if "not authorized" in str(error_event).lower():
            print("[cTrader] 🔄 Reiniciando autenticación debido a error de autorización...")
            global account_authorized
            account_authorized = False
            reactor.callLater(1, on_connected, client)
    
    # Procesar mensajes de ejecución
    elif message.payloadType == ProtoOAExecutionEvent().payloadType:
        execution_event = Protobuf.extract(message)
        print(f"[cTrader] ✅ Evento de ejecución recibido: {execution_event}")

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
    
    # Configurar volumen (multiplicado por 100 según el ejemplo que compartiste)
    request.volume = int(volume) * 100
    request.comment = "Order from TradingView Webhook"
    
    print(f"[cTrader] 🚀 Enviando orden {side} para {symbol} con volumen {volume}...")
    
    # Enviar la orden
    order_deferred = client.send(request)
    order_deferred.addCallback(process_order_response)
    order_deferred.addErrback(on_order_error)
    
    return order_deferred

def process_order_response(response):
    """Procesa la respuesta de la orden"""
    print(f"[cTrader] Respuesta recibida: {response}")
    
    # Verificar si hay un mensaje de error en la respuesta
    if "not authorized" in str(response).lower():
        global account_authorized
        account_authorized = False
        print("[cTrader] ⚠️ Detectado error de autorización en respuesta. Reiniciando autenticación...")
        reactor.callLater(0, on_connected, client)
        raise Exception("Cuenta no autorizada. Reiniciando autenticación.")
    
    # Verificar si es el error específico que estamos ignorando
    if ignore_account_not_found and "CH_CTID_TRADER_ACCOUNT_NOT_FOUND" in str(response):
        print("[cTrader] ⚠️ Error de cuenta no encontrada en la respuesta, pero continuamos por configuración.")
        return response
        
    print(f"[cTrader] ✅ Orden enviada correctamente")
    return response

def on_order_error(failure):
    """Maneja errores al enviar órdenes"""
    global account_authorized
    
    print(f"[cTrader] ❌ Error al enviar orden: {failure}")
    
    # Si estamos ignorando el error específico y parece ser ese error
    if ignore_account_not_found and "CH_CTID_TRADER_ACCOUNT_NOT_FOUND" in str(failure):
        print("[cTrader] ⚠️ Error de cuenta no encontrada, pero continuamos por configuración.")
        return failure
    
    # Si es un error de autorización, intentamos reautenticar
    if "not authorized" in str(failure).lower():
        account_authorized = False
        print("[cTrader] ⚠️ Error de autorización al enviar orden. Reiniciando autenticación...")
        reactor.callLater(0, on_connected, client)
    
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
            
            # Si estamos ignorando el error específico y parece ser ese error
            if ignore_account_not_found and "CH_CTID_TRADER_ACCOUNT_NOT_FOUND" in str(error):
                print("[cTrader] ⚠️ Error de cuenta no encontrada, pero continuamos por configuración.")
                # Intentamos enviar la orden a pesar del error
                reactor.callLater(0, send_order_when_ready)
                return error
            
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
