import os
from dotenv import load_dotenv
from ctrader_open_api import Client, EndPoints, TcpProtocol
from twisted.internet import reactor, defer

load_dotenv()

# ⚙️ Configuración
CLIENT_ID = os.getenv("CTRADER_CLIENT_ID")
CLIENT_SECRET = os.getenv("CTRADER_CLIENT_SECRET")
ACCESS_TOKEN = os.getenv("CTRADER_ACCESS_TOKEN")
REFRESH_TOKEN = os.getenv("CTRADER_REFRESH_TOKEN")
ACCOUNT_ID = int(os.getenv("ACCOUNT_ID"))

print("=== Prueba de autenticación cTrader ===")
print(f"CLIENT_ID: {CLIENT_ID}")
print(f"CLIENT_SECRET: {'*' * len(CLIENT_SECRET) if CLIENT_SECRET else 'NO CONFIGURADO'}")
print(f"ACCESS_TOKEN: {'*' * 10}...{ACCESS_TOKEN[-5:] if ACCESS_TOKEN else 'NO CONFIGURADO'}")
print(f"REFRESH_TOKEN: {'*' * 10}...{REFRESH_TOKEN[-5:] if REFRESH_TOKEN else 'NO CONFIGURADO'}")
print(f"ACCOUNT_ID: {ACCOUNT_ID}")
print("=====================================")

client = None
auth_completed = defer.Deferred()

def on_connected(client_instance):
    """Callback cuando el cliente se conecta"""
    print("[TEST] ✅ Conectado al servidor")
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
    print("[TEST] ✅ Aplicación autenticada correctamente")
    
    # Autenticamos la cuenta
    from ctrader_open_api.messages.OpenApiMessages_pb2 import ProtoOAAccountAuthReq
    request = ProtoOAAccountAuthReq()
    request.ctidTraderAccountId = ACCOUNT_ID
    request.accessToken = ACCESS_TOKEN
    
    # Opcionalmente añadir refresh token
    if REFRESH_TOKEN:
        request.refreshToken = REFRESH_TOKEN
    
    deferred = client.send(request)
    deferred.addCallback(on_account_auth_success)
    deferred.addErrback(on_error)

def on_account_auth_success(response):
    """Callback después de autenticar la cuenta"""
    print(f"[TEST] ✅ Cuenta {ACCOUNT_ID} autenticada correctamente")
    auth_completed.callback(None)

def on_disconnected(client_instance, reason):
    """Callback cuando el cliente se desconecta"""
    print(f"[TEST] ❌ Desconectado: {reason}")
    if not auth_completed.called:
        auth_completed.errback(Exception(f"Desconectado: {reason}"))

def on_message_received(client_instance, message):
    """Callback para procesar mensajes recibidos"""
    from ctrader_open_api import Protobuf
    from ctrader_open_api.messages.OpenApiMessages_pb2 import ProtoOAErrorRes
    
    # Procesar mensajes de error
    if message.payloadType == ProtoOAErrorRes().payloadType:
        error_event = Protobuf.extract(message)
        print(f"[TEST] ⚠️ Error recibido: {error_event}")

def on_error(failure):
    """Callback para manejar errores"""
    print(f"[TEST] ❌ Error: {failure}")
    
    if not auth_completed.called:
        auth_completed.errback(failure)
    
    return failure

def shutdown_test(result=None):
    """Cierra el test y el reactor"""
    print("[TEST] Test completado, cerrando conexión...")
    
    if client:
        client.stopService()
    
    # Usar callLater para dar tiempo a que se limpie la conexión
    reactor.callLater(1, reactor.stop)
    
    if isinstance(result, Exception) or isinstance(result, defer.Failure):
        print("[TEST] ❌ Test fallido!")
        return
    
    print("[TEST] ✅ Test exitoso! Tus credenciales están funcionando correctamente.")

# Inicializar cliente
client = Client(
    EndPoints.PROTOBUF_DEMO_HOST, 
    EndPoints.PROTOBUF_PORT, 
    TcpProtocol
)

# Configurar callbacks
client.setConnectedCallback(on_connected)
client.setDisconnectedCallback(on_disconnected)
client.setMessageReceivedCallback(on_message_received)

# Configurar timeout
def on_timeout():
    if not auth_completed.called:
        print("[TEST] ⚠️ Timeout de conexión! La prueba tomó demasiado tiempo.")
        auth_completed.errback(Exception("Timeout de conexión"))

reactor.callLater(30, on_timeout)  # 30 segundos de timeout

# Añadir callback para cierre
auth_completed.addBoth(shutdown_test)

# Iniciar cliente
print("[TEST] Iniciando conexión...")
client.startService()

# Iniciar reactor
reactor.run()
