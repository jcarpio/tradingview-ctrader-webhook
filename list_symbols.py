import os
from dotenv import load_dotenv
from ctrader_open_api import Client, Protobuf, EndPoints, TcpProtocol
from twisted.internet import reactor, defer

load_dotenv()

# ⚙️ Configuración
CLIENT_ID = os.getenv("CTRADER_CLIENT_ID")
CLIENT_SECRET = os.getenv("CTRADER_CLIENT_SECRET")
ACCESS_TOKEN = os.getenv("CTRADER_ACCESS_TOKEN")
ACCOUNT_ID = int(os.getenv("ACCOUNT_ID"))  # Ahora usando el ID correcto

print("=== Obtener lista de símbolos para la cuenta ===")
print(f"CLIENT_ID: {CLIENT_ID}")
print(f"ACCOUNT_ID: {ACCOUNT_ID}")
print("=====================================")

client = None
symbols_completed = defer.Deferred()

def on_connected(client_instance):
    """Callback cuando el cliente se conecta"""
    print("[TEST] ✅ Conectado al servidor")
    from ctrader_open_api.messages.OpenApiMessages_pb2 import ProtoOAApplicationAuthReq
    
    request = ProtoOAApplicationAuthReq()
    request.clientId = CLIENT_ID
    request.clientSecret = CLIENT_SECRET
    deferred = client_instance.send(request)
    deferred.addCallback(on_app_auth_success)
    deferred.addErrback(on_error)

def on_app_auth_success(response):
    """Callback después de autenticar la aplicación"""
    print("[TEST] ✅ Aplicación autenticada correctamente")
    
    from ctrader_open_api.messages.OpenApiMessages_pb2 import ProtoOAAccountAuthReq
    request = ProtoOAAccountAuthReq()
    request.ctidTraderAccountId = ACCOUNT_ID
    request.accessToken = ACCESS_TOKEN
    
    deferred = client.send(request)
    deferred.addCallback(on_account_auth_success)
    deferred.addErrback(on_error)

def on_account_auth_success(response):
    """Callback después de autenticar la cuenta"""
    print(f"[TEST] ✅ Cuenta {ACCOUNT_ID} autenticada correctamente")
    
    # Solicitar la lista de símbolos
    from ctrader_open_api.messages.OpenApiMessages_pb2 import ProtoOASymbolsListReq
    request = ProtoOASymbolsListReq()
    request.ctidTraderAccountId = ACCOUNT_ID
    
    deferred = client.send(request)
    deferred.addCallback(on_symbols_received)
    deferred.addErrback(on_error)

def on_symbols_received(response):
    """Callback después de recibir la lista de símbolos"""
    from ctrader_open_api import Protobuf
    
    try:
        symbols = Protobuf.extract(response)
        print("\n[TEST] ✅ Lista de símbolos recibida")
        print("\n=== SÍMBOLOS DISPONIBLES ===")
        
        # Crear un diccionario para los símbolos importantes
        common_symbols = {
            "BTCUSD": None,
            "ETHUSD": None,
            "EURUSD": None,
            "XAUUSD": None
        }
        
        if hasattr(symbols, 'symbol') and len(symbols.symbol) > 0:
            print(f"Total de símbolos: {len(symbols.symbol)}")
            
            # Primero buscamos los símbolos comunes
            for symbol in symbols.symbol:
                name = symbol.symbolName
                symbol_id = symbol.symbolId
                
                if name in common_symbols:
                    common_symbols[name] = symbol_id
                    print(f"ID: {symbol_id} - Nombre: {name}")
            
            print("\n--- SÍMBOLOS COMUNES ENCONTRADOS ---")
            for name, symbol_id in common_symbols.items():
                if symbol_id:
                    print(f"  \"{name}\": {symbol_id},")
                else:
                    print(f"  \"{name}\": No encontrado,")
            
            print("\n--- PRIMEROS 20 SÍMBOLOS DE LA LISTA ---")
            for i, symbol in enumerate(symbols.symbol[:20]):
                print(f"ID: {symbol.symbolId} - Nombre: {symbol.symbolName}")
                
        else:
            print("❌ No se encontraron símbolos para esta cuenta")
            
        print("===========================\n")
        
        # Guardar todos los símbolos en un archivo
        with open("symbols.txt", "w") as f:
            f.write("SYMBOLS = {\n")
            for symbol in symbols.symbol:
                f.write(f"    \"{symbol.symbolName}\": {symbol.symbolId},\n")
            f.write("}\n")
        
        print("Lista completa de símbolos guardada en symbols.txt")
        
    except Exception as e:
        print(f"[TEST] ❌ Error procesando símbolos: {e}")
    
    symbols_completed.callback(None)

def on_error(failure):
    """Callback para manejar errores"""
    print(f"[TEST] ❌ Error: {failure}")
    
    if not symbols_completed.called:
        symbols_completed.errback(failure)
    
    return failure

def shutdown_test(result=None):
    """Cierra el test y el reactor"""
    print("[TEST] Test completado, cerrando conexión...")
    
    if client:
        client.stopService()
    
    reactor.callLater(1, reactor.stop)
    
    if isinstance(result, Exception) or isinstance(result, defer.Failure):
        print("[TEST] ❌ Test fallido!")
        return
    
    print("[TEST] ✅ Test exitoso!")

# Inicializar cliente
client = Client(
    EndPoints.PROTOBUF_DEMO_HOST, 
    EndPoints.PROTOBUF_PORT, 
    TcpProtocol
)

# Configurar callbacks
client.setConnectedCallback(on_connected)

# Configurar timeout
def on_timeout():
    if not symbols_completed.called:
        print("[TEST] ⚠️ Timeout de conexión!")
        symbols_completed.errback(Exception("Timeout de conexión"))

reactor.callLater(30, on_timeout)

# Añadir callback para cierre
symbols_completed.addBoth(shutdown_test)

# Iniciar cliente
print("[TEST] Iniciando conexión...")
client.startService()

# Iniciar reactor
reactor.run()
