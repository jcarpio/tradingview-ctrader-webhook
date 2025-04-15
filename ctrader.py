import os
import time
from dotenv import load_dotenv
from ctrader_open_api import Client, Protobuf, EndPoints, TcpProtocol
from twisted.internet import reactor, defer

load_dotenv()

# Diccionario de símbolos conocidos con su symbolId
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

# Estado de posiciones abiertas
open_positions = {}  # Formato: {symbol: {"position_id": id, "side": "BUY/SELL", "candle_color": "GREEN/RED"}}

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
    
    # Primero autenticamos la aplicación
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
    
    # Obtener posiciones abiertas
    get_open_positions()
    
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
        process_execution_event(execution_event)

def process_execution_event(event):
    """Procesa eventos de ejecución para actualizar el estado de posiciones"""
    global open_positions
    
    print(f"[cTrader] ✅ Evento de ejecución recibido: {event.executionType}")
    
    # Actualizar estado de posiciones basado en el evento
    if hasattr(event, 'position') and event.position:
        position = event.position
        symbol_id = position.tradeData.symbolId
        position_id = position.positionId
        
        # Buscar el símbolo basado en el symbolId
        symbol = None
        for sym, sym_id in SYMBOLS.items():
            if sym_id == symbol_id:
                symbol = sym
                break
        
        if not symbol:
            print(f"[cTrader] ⚠️ No se encontró símbolo para ID {symbol_id}")
            return
        
        # Actualizar posiciones abiertas
        if event.executionType == 'ORDER_FILLED' and position.positionStatus == 'POSITION_STATUS_OPEN':
            trade_side = position.tradeData.tradeSide
            print(f"[cTrader] 📈 Nueva posición abierta: {symbol} {trade_side} (ID: {position_id})")
            open_positions[symbol] = {
                "position_id": position_id,
                "side": trade_side
            }
        
        # Actualizar cuando una posición se cierra
        elif position.positionStatus == 'POSITION_STATUS_CLOSED':
            if symbol in open_positions and open_positions[symbol]["position_id"] == position_id:
                print(f"[cTrader] 📉 Posición cerrada: {symbol} (ID: {position_id})")
                if symbol in open_positions:
                    del open_positions[symbol]

def on_error(failure):
    """Callback para manejar errores"""
    global connection_ready
    
    print(f"[cTrader] ❌ Error: {failure}")
    
    # En caso de error, notificar a cualquier deferred pendiente
    if not connection_ready.called:
        connection_ready.errback(failure)
    
    return failure

def get_symbol_info(symbol_id):
    """
    Obtiene información sobre un símbolo, incluyendo el valor de un pip
    
    Args:
        symbol_id: ID del símbolo
        
    Returns:
        Un deferred que se resolverá con la información del símbolo
    """
    try:
        from ctrader_open_api.messages.OpenApiMessages_pb2 import ProtoOASymbolByIdReq
        
        # Crear solicitud para obtener información del símbolo
        request = ProtoOASymbolByIdReq()
        request.ctidTraderAccountId = ACCOUNT_ID
        request.symbolId = symbol_id  # Este es el campo que causa el problema
        
        # Crear un deferred para esperar la respuesta
        response_deferred = defer.Deferred()
        
        # Función para manejar la respuesta
        def on_symbol_info_received(msg):
            from ctrader_open_api import Protobuf
            from ctrader_open_api.messages.OpenApiMessages_pb2 import ProtoOASymbolByIdRes
            
            # Solo procesar mensajes de tipo ProtoOASymbolByIdRes
            if msg.payloadType == ProtoOASymbolByIdRes().payloadType:
                symbol_info = Protobuf.extract(msg)
                response_deferred.callback(symbol_info)
                return True  # Indica que se ha manejado el mensaje
            return False
        
        # Registrar manejador temporal para la respuesta
        orig_handler = client.messageReceivedCallback
        
        def temp_handler(client, msg):
            if not on_symbol_info_received(msg) and orig_handler:
                orig_handler(client, msg)
        
        client.setMessageReceivedCallback(temp_handler)
        
        # Enviar la solicitud
        send_deferred = client.send(request)
        
        # Restaurar el manejador original después de un tiempo
        def restore_handler():
            if client.messageReceivedCallback == temp_handler:
                client.setMessageReceivedCallback(orig_handler)
        
        reactor.callLater(5, restore_handler)
        
        # Manejar errores
        def on_error(failure):
            print(f"[cTrader] ❌ Error obteniendo información del símbolo: {failure}")
            if not response_deferred.called:
                response_deferred.errback(failure)
            restore_handler()
            return failure
        
        send_deferred.addErrback(on_error)
        
        # Esperar respuesta
        return response_deferred
    
    except Exception as e:
        print(f"[cTrader] ❌ Error en get_symbol_info: {str(e)}")
        return defer.fail(e)

def pips_to_price(symbol_id, pips, side, is_sl=True):
    """
    Convierte pips a precio basado en el símbolo y el lado de la operación
    
    Args:
        symbol_id: ID del símbolo
        pips: Número de pips
        side: Lado de la operación (BUY o SELL)
        is_sl: True si es stop loss, False si es take profit
        
    Returns:
        Un deferred que se resolverá con el precio calculado
    """
    result_deferred = defer.Deferred()
    
    # Si pips es 0, no establecer SL/TP
    if pips == 0:
        result_deferred.callback(None)
        return result_deferred
    
    # Obtener información del símbolo
    symbol_info_deferred = get_symbol_info(symbol_id)
    
    def calculate_price(symbol_info):
        try:
            # Obtener el valor de un pip para este símbolo
            digits = symbol_info.symbol.digits
            pip_position = 10 ** (digits - 1)  # Posición del pip (10^(dígitos-1))
            pip_value = 1.0 / pip_position  # Valor de 1 pip
            
            # Obtener el precio actual
            from ctrader_open_api.messages.OpenApiMessages_pb2 import ProtoOASubscribeSpotsReq
            
            # Suscribirse a spots para obtener el precio actual
            spots_request = ProtoOASubscribeSpotsReq()
            spots_request.ctidTraderAccountId = ACCOUNT_ID
            # Corregir aquí: symbolId es un campo repetido, debe usar append
            spots_request.symbolId.append(symbol_id)  # Usar append en lugar de asignación directa
            
            spots_deferred = client.send(spots_request)
            
            # Esperar a recibir un spot
            spot_price_deferred = defer.Deferred()
            
            # Función para manejar spots recibidos
            def on_spot_received(msg):
                from ctrader_open_api import Protobuf
                from ctrader_open_api.messages.OpenApiMessages_pb2 import ProtoOASpotEvent
                
                if msg.payloadType == ProtoOASpotEvent().payloadType:
                    spot = Protobuf.extract(msg)
                    if spot.symbolId == symbol_id:
                        # Cancelar suscripción a spots
                        from ctrader_open_api.messages.OpenApiMessages_pb2 import ProtoOAUnsubscribeSpotsReq
                        unsub_request = ProtoOAUnsubscribeSpotsReq()
                        unsub_request.ctidTraderAccountId = ACCOUNT_ID
                        # Corregir aquí también
                        unsub_request.symbolId.append(symbol_id)  # Usar append en lugar de asignación directa
                        client.send(unsub_request)
                        
                        # Resolver con el precio del spot
                        if not spot_price_deferred.called:
                            bid_price = spot.bid
                            ask_price = spot.ask
                            
                            # Para BUY: 
                            # - El stop loss se coloca por debajo del precio de entrada (ask - sl_pips)
                            # - El take profit se coloca por encima del precio de entrada (ask + tp_pips)
                            # Para SELL:
                            # - El stop loss se coloca por encima del precio de entrada (bid + sl_pips)
                            # - El take profit se coloca por debajo del precio de entrada (bid - tp_pips)
                            price = 0.0
                            
                            if side.upper() == "BUY":
                                if is_sl:  # Stop Loss para BUY
                                    price = ask_price - (pips * pip_value)
                                else:  # Take Profit para BUY
                                    price = ask_price + (pips * pip_value)
                            else:  # SELL
                                if is_sl:  # Stop Loss para SELL
                                    price = bid_price + (pips * pip_value)
                                else:  # Take Profit para SELL
                                    price = bid_price - (pips * pip_value)
                            
                            # Redondear al número correcto de decimales
                            price = round(price, digits)
                            
                            spot_price_deferred.callback(price)
                        return True
                return False
            
            # Registrar manejador temporal para spots
            orig_handler = client.messageReceivedCallback
            
            def temp_handler(client, msg):
                if not on_spot_received(msg) and orig_handler:
                    orig_handler(client, msg)
            
            client.setMessageReceivedCallback(temp_handler)
            
            # Restaurar el manejador original después de un tiempo
            def restore_handler():
                if client.messageReceivedCallback == temp_handler:
                    client.setMessageReceivedCallback(orig_handler)
            
            reactor.callLater(5, restore_handler)
            
            # Timeout para recibir spot
            def on_timeout():
                if not spot_price_deferred.called:
                    restore_handler()
                    spot_price_deferred.errback(Exception("Timeout esperando precio actual"))
            
            reactor.callLater(3, on_timeout)
            
            # Manejar errores de suscripción
            def on_sub_error(failure):
                print(f"[cTrader] ❌ Error suscribiéndose a spots: {failure}")
                restore_handler()
                if not spot_price_deferred.called:
                    spot_price_deferred.errback(failure)
                return failure
            
            spots_deferred.addErrback(on_sub_error)
            
            # Devolver el precio calculado
            spot_price_deferred.addCallbacks(
                lambda price: result_deferred.callback(price),
                lambda failure: result_deferred.errback(failure)
            )
            
        except Exception as e:
            print(f"[cTrader] ❌ Error calculando precio: {str(e)}")
            result_deferred.errback(e)
    
    # Manejar errores
    def on_symbol_info_error(failure):
        print(f"[cTrader] ❌ Error obteniendo información del símbolo: {failure}")
        result_deferred.errback(failure)
        return failure
    
    symbol_info_deferred.addCallbacks(calculate_price, on_symbol_info_error)
    
    return result_deferred

    # Manejar errores
    def on_symbol_info_error(failure):
        print(f"[cTrader] ❌ Error obteniendo información del símbolo: {failure}")
        result_deferred.errback(failure)
        return failure
    
    symbol_info_deferred.addCallbacks(calculate_price, on_symbol_info_error)
    
    return result_deferred

def get_open_positions():
    """
    Obtiene todas las posiciones abiertas actualmente para actualizar el estado
    """
    global open_positions
    
    from ctrader_open_api.messages.OpenApiMessages_pb2 import ProtoOAReconcileReq
    
    result_deferred = defer.Deferred()
   
    try:
        # Solicitud para reconciliar posiciones
        request = ProtoOAReconcileReq()
        request.ctidTraderAccountId = ACCOUNT_ID
        
        # Guardar el manejador original (usar getMessageReceivedCallback)
        original_handler = client.getMessageReceivedCallback()
        
        # Función para manejar la respuesta (MUEVE ESTA DEFINICIÓN AQUÍ)
        def on_reconcile_received(msg):
            from ctrader_open_api import Protobuf
            from ctrader_open_api.messages.OpenApiMessages_pb2 import ProtoOAReconcileRes
            
            # Solo procesar mensajes de tipo ProtoOAReconcileRes
            if msg.payloadType == ProtoOAReconcileRes().payloadType:
                # resto de la implementación...
                return True
            return False
        
        # Establecer un manejador temporal
        def temp_handler(client_instance, msg):
            if not on_reconcile_received(msg):
                # Si no procesamos este mensaje, pasarlo al manejador original
                if original_handler:
                    original_handler(client_instance, msg)
        
        client.setMessageReceivedCallback(temp_handler)
             
        # Función para manejar la respuesta
        def on_reconcile_received(msg):
            from ctrader_open_api import Protobuf
            from ctrader_open_api.messages.OpenApiMessages_pb2 import ProtoOAReconcileRes
            
            # Solo procesar mensajes de tipo ProtoOAReconcileRes
            if msg.payloadType == ProtoOAReconcileRes().payloadType:
                reconcile_data = Protobuf.extract(msg)
                
                # Reiniciar el registro de posiciones abiertas
                open_positions.clear()
                
                # Procesar posiciones
                if hasattr(reconcile_data, 'position') and reconcile_data.position:
                    for position in reconcile_data.position:
                        symbol_id = position.tradeData.symbolId
                        position_id = position.positionId
                        trade_side = position.tradeData.tradeSide
                        
                        # Buscar el símbolo correspondiente
                        symbol = None
                        for sym, sym_id in SYMBOLS.items():
                            if sym_id == symbol_id:
                                symbol = sym
                                break
                        
                        if symbol:
                            open_positions[symbol] = {
                                "position_id": position_id,
                                "side": trade_side
                            }
                            print(f"[cTrader] 📊 Posición abierta encontrada: {symbol} {trade_side} (ID: {position_id})")
                
                print(f"[cTrader] 📊 Posiciones abiertas: {len(open_positions)}")
                
                # No necesitamos seguir procesando este tipo de mensajes
                client.setMessageReceivedCallback(original_handler)
                
                result_deferred.callback(open_positions)
                return True
            return False
        
        # Guardar el manejador original
        original_handler = client.messageReceivedCallback
        
        # Establecer un manejador temporal
        def temp_handler(client_instance, msg):
            if not on_reconcile_received(msg):
                # Si no procesamos este mensaje, pasarlo al manejador original
                if original_handler:
                    original_handler(client_instance, msg)
        
        client.setMessageReceivedCallback(temp_handler)
        
        # Enviar la solicitud
        send_deferred = client.send(request)
        
        # Configurar un timeout para restaurar el manejador original
        def timeout_handler():
            if not result_deferred.called:
                print("[cTrader] ⚠️ Timeout esperando posiciones abiertas")
                # Restaurar el manejador original
                client.setMessageReceivedCallback(original_handler)
                # Devolver un diccionario vacío en caso de timeout
                result_deferred.callback({})
        
        reactor.callLater(5, timeout_handler)
        
        # Manejar errores en el envío
        def on_error(failure):
            print(f"[cTrader] ❌ Error obteniendo posiciones abiertas: {failure}")
            # Restaurar el manejador original
            client.setMessageReceivedCallback(original_handler)
            
            if not result_deferred.called:
                result_deferred.errback(failure)
            return failure
        
        send_deferred.addErrback(on_error)
        
        return result_deferred
    
    except Exception as e:
        print(f"[cTrader] ❌ Error en get_open_positions: {str(e)}")
        if not result_deferred.called:
            result_deferred.errback(e)
        return result_deferred

def close_position(symbol):
    """
    Cierra una posición abierta para el símbolo especificado
    
    Args:
        symbol: Símbolo de la posición a cerrar
        
    Returns:
        Un deferred que se resolverá cuando se complete la operación
    """
    global open_positions
    
    if symbol not in open_positions:
        print(f"[cTrader] ⚠️ No hay posición abierta para {symbol}")
        return defer.succeed(None)
    
    from ctrader_open_api.messages.OpenApiMessages_pb2 import ProtoOAClosePositionReq
    
    result_deferred = defer.Deferred()
    
    try:
        position_id = open_positions[symbol]["position_id"]
        
        # Solicitud para cerrar la posición
        request = ProtoOAClosePositionReq()
        request.ctidTraderAccountId = ACCOUNT_ID
        request.positionId = position_id
        
        print(f"[cTrader] 🔄 Cerrando posición para {symbol} (ID: {position_id})")
        
        # Enviar la solicitud
        send_deferred = client.send(request)
        
        def on_success(response):
            print(f"[cTrader] ✅ Solicitud de cierre enviada para {symbol}")
            # La respuesta real vendrá a través de un evento de ejecución
            result_deferred.callback(response)
            return response
        
        def on_error(failure):
            print(f"[cTrader] ❌ Error cerrando posición para {symbol}: {failure}")
            result_deferred.errback(failure)
            return failure
        
        send_deferred.addCallbacks(on_success, on_error)
        
        return result_deferred
    
    except Exception as e:
        print(f"[cTrader] ❌ Error en close_position: {str(e)}")
        result_deferred.errback(e)
        return result_deferred


def send_market_order(symbol, side, volume, sl_pips=None, tp_pips=None, candle_color=None):
    """
    Envía una orden de mercado con stop loss y take profit en pips
    
    Args:
        symbol: Símbolo a operar (ej. "EURUSD")
        side: Lado de la operación ("BUY" o "SELL")
        volume: Volumen en lotes
        sl_pips: Stop loss en pips (opcional)
        tp_pips: Take profit en pips (opcional)
        candle_color: Color de la vela ("GREEN" o "RED")
    """
    global account_authorized, open_positions
    
    # Verificar que la cuenta esté autorizada
    if not account_authorized:
        raise Exception("Cuenta no autorizada. No se puede enviar la orden.")
    
    from ctrader_open_api.messages.OpenApiMessages_pb2 import ProtoOANewOrderReq
    from ctrader_open_api.messages.OpenApiModelMessages_pb2 import ProtoOAOrderType, ProtoOATradeSide
    
    if symbol not in SYMBOLS:
        raise Exception(f"❌ El símbolo {symbol} no está en la lista local. Añádelo a SYMBOLS.")
    
    symbol_id = SYMBOLS[symbol]
    
    # Deferred para el resultado final
    result_deferred = defer.Deferred()
    
    # Función para procesar la nueva orden
    def process_new_order():
        # Calcular precios basados en pips si se especifican
        sl_deferred = defer.succeed(None)
        tp_deferred = defer.succeed(None)
        
        # Calcular precio de stop loss si se especifica y no es cero
        if sl_pips is not None and sl_pips != 0:
            sl_deferred = pips_to_price(symbol_id, float(sl_pips), side, is_sl=True)
        
        # Calcular precio de take profit si se especifica y no es cero
        if tp_pips is not None and tp_pips != 0:
            tp_deferred = pips_to_price(symbol_id, float(tp_pips), side, is_sl=False)
        
        # Esperar a que ambos cálculos terminen
        def handle_prices(results):
            sl_price, tp_price = results
            send_order(sl_price, tp_price)
        
        def handle_error(failure):
            print(f"[cTrader] ❌ Error calculando precios: {failure}")
            result_deferred.errback(failure)
            return failure
        
        # Combinar ambos deferreds
        defer.gatherResults([sl_deferred, tp_deferred]).addCallbacks(handle_prices, handle_error)
    
    # Función para enviar la orden una vez calculados los precios
    def send_order(sl_price=None, tp_price=None):
        try:
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
            volume_in_centilotes = int(float(volume) * 100)
            
            # Asegurarnos de que el volumen sea al menos 1 centilote
            if volume_in_centilotes < 1:
                volume_in_centilotes = 1
                print(f"[cTrader] ⚠️ Volumen ajustado al mínimo: 0.01 lotes (1 centilote)")
            
            request.volume = volume_in_centilotes
            request.comment = "Order from TradingView Webhook"
            
            # Añadir stop loss si está calculado
            if sl_price is not None:
                request.stopLoss = sl_price
                print(f"[cTrader] 🛑 Stop Loss establecido a {sl_price} ({sl_pips} pips)")
            
            # Añadir take profit si está calculado
            if tp_price is not None:
                request.takeProfit = tp_price
                print(f"[cTrader] 🎯 Take Profit establecido a {tp_price} ({tp_pips} pips)")
            
            print(f"[cTrader] 🚀 Enviando orden {side} para {symbol} con volumen {volume} ({volume_in_centilotes} centilotes)")
            
            # Enviar la orden
            order_deferred = client.send(request)
            
            def on_order_success(response):
                print(f"[cTrader] ✅ Orden enviada correctamente: {response}")
                result_deferred.callback(response)
                return response
            
            def on_order_error(failure):
                print(f"[cTrader] ❌ Error al enviar orden: {failure}")
                result_deferred.errback(failure)
                return failure
            
            order_deferred.addCallbacks(on_order_success, on_order_error)
            
        except Exception as e:
            print(f"[cTrader] ❌ Error enviando orden: {str(e)}")
            result_deferred.errback(e)
    
    # Verificar si ya hay una posición abierta para este símbolo
    if symbol in open_positions:
        current_side = open_positions[symbol]["side"]
        
        # Si la posición existente tiene el mismo lado que la nueva orden, verificar el color de la vela
        if current_side == side.upper():
            # Para BUY: mantener mientras las velas cierren verdes
            # Para SELL: mantener mientras las velas cierren rojas
            valid_color = "GREEN" if side.upper() == "BUY" else "RED"
            
            if candle_color and candle_color != valid_color:
                # Cerrar la posición existente ya que la vela cerró en color opuesto
                print(f"[cTrader] 🔄 Cerrando posición {side.upper()} para {symbol} debido a cambio de tendencia")
                close_deferred = close_position(symbol)
                
                def on_close_success(_):
                    # Esperar un poco para asegurar que la posición se cerró
                    reactor.callLater(1, lambda: result_deferred.callback({"status": "closed", "message": f"Posición {side.upper()} cerrada para {symbol}"}))
                
                def on_close_error(failure):
                    result_deferred.errback(failure)
                
                close_deferred.addCallbacks(on_close_success, on_close_error)
                return result_deferred
            else:
                # Mantener la posición abierta
                print(f"[cTrader] ℹ️ Manteniendo posición {side.upper()} abierta para {symbol}")
                result_deferred.callback({"status": "maintained", "message": f"Posición {side.upper()} mantenida para {symbol}"})
                return result_deferred
        else:
            # La posición existente tiene lado diferente, cerrarla primero
            print(f"[cTrader] 🔄 Cerrando posición {current_side} para abrir nueva posición {side.upper()}")
            close_deferred = close_position(symbol)
            
            # Después de cerrar, continuar con la apertura de la nueva posición
            def continue_with_order(_):
                # Esperar un poco para asegurar que la posición se cerró
                reactor.callLater(1, lambda: process_new_order())
            
            def on_close_error(failure):
                result_deferred.errback(failure)
            
            close_deferred.addCallbacks(continue_with_order, on_close_error)
    else:
        # No hay posición abierta, proceder directamente
        process_new_order()
    
    return result_deferred

    
    # Función para procesar la nueva orden
    def process_new_order():
        # Calcular precios basados en pips si se especifican
        sl_deferred = defer.succeed(None)
        tp_deferred = defer.succeed(None)
        
        # Calcular precio de stop loss si se especifica y no es cero
        if sl_pips is not None and sl_pips != 0:
            sl_deferred = pips_to_price(symbol_id, float(sl_pips), side, is_sl=True)
        
        # Calcular precio de take profit si se especifica y no es cero
        if tp_pips is not None and tp_pips != 0:
            tp_deferred = pips_to_price(symbol_id, float(tp_pips), side, is_sl=False)
        
        # Esperar a que ambos cálculos terminen
        def handle_prices(results):
            sl_price, tp_price = results
            send_order(sl_price, tp_price)
        
        def handle_error(failure):
            print(f"[cTrader] ❌ Error calculando precios: {failure}")
            result_deferred.errback(failure)
            return failure
        
        # Combinar ambos deferreds
        defer.gatherResults([sl_deferred, tp_deferred]).addCallbacks(handle_prices, handle_error)
    
    # Función para enviar la orden una vez calculados los precios
    def send_order(sl_price=None, tp_price=None):
        try:
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
            volume_in_centilotes = int(float(volume) * 100)
            
            # Asegurarnos de que el volumen sea al menos 1 centilote
            if volume_in_centilotes < 1:
                volume_in_centilotes = 1
                print(f"[cTrader] ⚠️ Volumen ajustado al mínimo: 0.01 lotes (1 centilote)")
            
            request.volume = volume_in_centilotes
            request.comment = "Order from TradingView Webhook"
            
            # Añadir stop loss si está calculado
            if sl_price is not None:
                request.stopLoss = sl_price
                print(f"[cTrader] 🛑 Stop Loss establecido a {sl_price} ({sl_pips} pips)")
            
            # Añadir take profit si está calculado
            if tp_price is not None:
                request.takeProfit = tp_price
                print(f"[cTrader] 🎯 Take Profit establecido a {tp_price} ({tp_pips} pips)")
            
            print(f"[cTrader] 🚀 Enviando orden {side} para {symbol} con volumen {volume} ({volume_in_centilotes} centilotes)")
            
            # Enviar la orden
            order_deferred = client.send(request)
            
            def on_order_success(response):
                print(f"[cTrader] ✅ Orden enviada correctamente: {response}")
                result_deferred.callback(response)
                return response
            
            def on_order_error(failure):
                print(f"[cTrader] ❌ Error al enviar orden: {failure}")
                result_deferred.errback(failure)
                return failure
            
            order_deferred.addCallbacks(on_order_success, on_order_error)
            
        except Exception as e:
            print(f"[cTrader] ❌ Error enviando orden: {str(e)}")
            result_deferred.errback(e)
    
    return result_deferred

def run_ctrader_order(symbol, side, volume, sl_pips=None, tp_pips=None, candle_color=None):
    """
    Función para ser llamada desde el webhook para ejecutar una orden
    
    Args:
        symbol: Símbolo a operar (ej. "EURUSD")
        side: Lado de la operación ("BUY" o "SELL")
        volume: Volumen en lotes
        sl_pips: Stop loss en pips (opcional)
        tp_pips: Take profit en pips (opcional)
        candle_color: Color de la vela ("GREEN" o "RED")
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
                order_deferred = send_market_order(
                    symbol, 
                    side, 
                    volume, 
                    sl_pips=sl_pips, 
                    tp_pips=tp_pips, 
                    candle_color=candle_color
                )
                
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
