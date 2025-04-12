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

def initialize_client():
    """
    Inicializa y retorna un cliente cTrader
    """
    global client
    if client is None:
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
    
    return client

def on_connected(client_instance):
    """Callback cuando el cliente se conecta"""
    print("[cTrader] ✅ Conectado al servidor")
    from ctrader_open_api.messages.OpenApiMessages_pb2 import ProtoOAApplicationAuthReq
    
    # Autenticamos la aplicación
    request = ProtoOAApplicationAuthReq()
    request.clientId = CLIENT_ID
    request.clientSecret = CLIENT_SECRET
    deferred = client_instance.send(request)
    deferred.addCallback(on_app_auth_success)
    deferred.addErrback(on_error)

def on_app_auth_success(response):
    """Callback después de autenticar la aplicación"""
    print("[cTrader] ✅ Aplicación autenticada correctamente")
    
    # Autenticamos la cuenta
    from ctrader_open_api.messages.OpenApiMessages_pb2 import ProtoOAAccountAuthReq
    request = ProtoOAAccountAuthReq()
    request.ctidTraderAccountId = ACCOUNT_ID
    request.accessToken = ACCESS_TOKEN
    deferred = client.send(request)
    deferred.addCallback(on_account_auth_success)
    deferred.addErrback(on_error)

def on_account_auth_success(response):
    """Callback después de autenticar la cuenta"""
    print(f"[cTrader] ✅ Cuenta {ACCOUNT_ID} autenticada correctamente")

def on_disconnected(client_instance, reason):
    """Callback cuando el cliente se desconecta"""
    print(f"[cTrader] ❌ Desconectado: {reason}")

def on_message_received(client_instance, message):
    """Callback para procesar mensajes recibidos"""
    from ctrader_open_api import Protobuf
    from ctrader_open_api.messages.OpenApiMessages_pb2 import ProtoOAExecutionEvent
    
    # Solo procesamos mensajes de ejecución
    if message.payloadType == ProtoOAExecutionEvent().payloadType:
        execution_event = Protobuf.extract(message)
        print(f"[cTrader] ✅ Evento de ejecución recibido: {execution_event}")

def on_error(failure):
    """Callback para manejar errores"""
    print(f"[cTrader] ❌ Error: {failure}")

def send_market_order(symbol, side, volume):
    """
    Envía una orden de mercado
    
    Args:
        symbol: Símbolo a operar (ej. "EURUSD")
        side: Lado de la operación ("BUY" o "SELL")
        volume: Volumen en lotes
    """
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
    deferred = client.send(request)
    deferred.addCallback(on_order_sent)
    deferred.addErrback(on_error)
    
    return deferred

def on_order_sent(response):
    """Callback después de enviar una orden"""
    print(f"[cTrader] ✅ Orden enviada correctamente: {response}")
    return response

def run_ctrader_order(symbol, side, volume):
    """
    Función para ser llamada desde el webhook para ejecutar una orden
    
    Args:
        symbol: Símbolo a operar (ej. "EURUSD")
        side: Lado de la operación ("BUY" o "SELL")
        volume: Volumen en lotes
    """
    try:
        global client
        
        # Inicializar cliente si no existe
        if client is None:
            initialize_client()
        
        # Enviamos la orden y esperamos un momento para que se procese
        d = defer.Deferred()
        
        # Función para ejecutar la orden cuando el cliente esté listo
        def do_send_order():
            try:
                send_market_order(symbol, side, volume).chainDeferred(d)
            except Exception as e:
                d.errback(e)
        
        # Programamos la ejecución después de un breve retraso para asegurar que el cliente está listo
        reactor.callLater(1, do_send_order)
        
        return d
    except Exception as e:
        print(f"[cTrader SDK] ❌ Error ejecutando orden: {str(e)}")
        raise e
