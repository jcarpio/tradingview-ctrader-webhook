import os
from dotenv import load_dotenv
from ctrader_open_api import Client, Protobuf, EndPoints, TcpProtocol
from twisted.internet import reactor, defer

load_dotenv()

# ⚙️ Configuración
CLIENT_ID = os.getenv("CTRADER_CLIENT_ID")
CLIENT_SECRET = os.getenv("CTRADER_CLIENT_SECRET")
ACCESS_TOKEN = os.getenv("CTRADER_ACCESS_TOKEN")

print("=== Listar cuentas disponibles para este token ===")
print(f"CLIENT_ID: {CLIENT_ID}")
print(f"CLIENT_SECRET: {'*' * len(CLIENT_SECRET) if CLIENT_SECRET else 'NO CONFIGURADO'}")
print(f"ACCESS_TOKEN: {'*' * 10}...{ACCESS_TOKEN[-5:] if ACCESS_TOKEN else 'NO CONFIGURADO'}")
print("=====================================")

client = None
list_completed = defer.Deferred()

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
    
    # Solicitamos la lista de cuentas para este token
    from ctrader_open_api.messages.OpenApiMessages_pb2 import ProtoOAGetAccountListByAccessTokenReq
    request = ProtoOAGetAccountListByAccessTokenReq()
    request.accessToken = ACCESS_TOKEN
    
    deferred = client.send(request)
    deferred.addCallback(on_account_list_success)
    deferred.addErrback(on_error)

def on_account_list_success(response):
    """Callback después de recibir la lista de cuentas"""
    from ctrader_open_api import Protobuf
    
    try:
        account_list = Protobuf.extract(response)
        print("\n[TEST] ✅ Lista de cuentas recibida")
        print("\n=== CUENTAS DISPONIBLES ===")
        
        if hasattr(account_list, 'ctidTraderAccount') and len(account_list.ctidTraderAccount) > 0:
            for account in account_list.ctidTraderAccount:
                print(f"ID: {account.ctidTraderAccountId}")
                # Mostrar todos los atributos disponibles
                for field in dir(account):
                    if not field.startswith('_') and field != 'ctidTraderAccountId':
                        try:
                            value = getattr(account, field)
                            if not callable(value):  # Solo mostrar atributos, no métodos
                                print(f"  - {field}: {value}")
                        except Exception as e:
                            pass
                print("-------------------")
        else:
            print("❌ No se encontraron cuentas para este token de acceso")
            # Mostrar la respuesta completa para depuración
            print("Respuesta completa:")
            print(account_list)
            
        print("===========================\n")
    except Exception as e:
        print(f"[TEST] ❌ Error procesando lista de cuentas: {e}")
        print("Respuesta original:")
        print(response)
    
    list_completed.callback(None)

def on_disconnected(client_instance, reason):
    """Callback cuando el cliente se desconecta"""
    print(f"[TEST] ❌ Desconectado: {reason}")
    if not list_completed.called:
        list_completed.errback(Exception(f"Desconectado: {reason}"))

def on_error(failure):
    """Callback para manejar errores"""
    print(f"[TEST] ❌ Error: {failure}")
    
    if not list_completed.called:
        list_completed.errback(failure)
    
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
    
    print("[TEST] ✅ Test exitoso! Comprueba la lista de cuentas disponibles.")

# Inicializar cliente
client = Client(
    EndPoints.PROTOBUF_DEMO_HOST, 
    EndPoints.PROTOBUF_PORT, 
    TcpProtocol
)

# Configurar callbacks
client.setConnectedCallback(on_connected)
client.setDisconnectedCallback(on_disconnected)

# Configurar timeout
def on_timeout():
    if not list_completed.called:
        print("[TEST] ⚠️ Timeout de conexión! La prueba tomó demasiado tiempo.")
        list_completed.errback(Exception("Timeout de conexión"))

reactor.callLater(30, on_timeout)  # 30 segundos de timeout

# Añadir callback para cierre
list_completed.addBoth(shutdown_test)

# Iniciar cliente
print("[TEST] Iniciando conexión...")
client.startService()

# Iniciar reactor
reactor.run()
