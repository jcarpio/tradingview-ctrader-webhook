import os
from dotenv import load_dotenv
from ctrader_open_api import Client

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

# ✅ Función principal para ejecutar una orden
def run_ctrader_order(symbol, side, volume):
    if symbol not in SYMBOLS:
        raise Exception(f"❌ El símbolo {symbol} no está en la lista local. Añádelo a SYMBOLS.")
    
    symbol_id = SYMBOLS[symbol]

    # Crear cliente
    client = Client(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        access_token=ACCESS_TOKEN,
        refresh_token=REFRESH_TOKEN,
        account_id=ACCOUNT_ID,
        is_demo=True
    )

    try:
        print("[cTrader SDK] 🚀 Ejecutando operación...")
        order = client.trade.open_market_order(
            symbol_id=symbol_id,
            side=side.upper(),  # BUY o SELL
            volume=int(volume),
            comment="Order from TradingView Webhook"
        )

        if order.get("status") == "FILLED":
            print(f"[cTrader SDK] ✅ ORDEN FILLED: {side.upper()} {volume} {symbol} (ID: {order['orderId']})")
        else:
            print(f"[cTrader SDK] ⚠️ ORDEN ENVIADA pero con estado: {order.get('status')}")
        
        return order

    except Exception as e:
        print("❌ Error enviando orden:", str(e))
        raise
