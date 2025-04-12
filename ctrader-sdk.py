import os
from dotenv import load_dotenv
from ctrader_open_api import CTraderOpenApiClient, ProtoOAOrderType, ProtoOAOrderSide, ProtoOATimeInForce

load_dotenv()

SYMBOLS = {
    "BTCUSD": 6080842,
    "ETHUSD": 6080843,
    "EURUSD": 1,
    "XAUUSD": 2,
    # Puedes añadir más
}

async def run_sdk_bot(symbol, side, volume):
    client_id = os.getenv("CTRADER_CLIENT_ID")
    client_secret = os.getenv("CTRADER_CLIENT_SECRET")
    access_token = os.getenv("CTRADER_ACCESS_TOKEN")
    refresh_token = os.getenv("CTRADER_REFRESH_TOKEN")
    account_id = int(os.getenv("ACCOUNT_ID"))

    if symbol not in SYMBOLS:
        raise Exception(f"❌ Símbolo {symbol} no reconocido. Añádelo a la lista.")

    symbol_id = SYMBOLS[symbol]

    async with CTraderOpenApiClient() as client:
        await client.connect()

        await client.authenticate(
            client_id=client_id,
            client_secret=client_secret,
            access_token=access_token,
            refresh_token=refresh_token,
        )

        await client.authenticate_account(account_id=account_id)

        print("[cTrader SDK] ✅ Conectado y autenticado con SDK oficial")

        order_id = await client.place_order(
            account_id=account_id,
            symbol_id=symbol_id,
            order_type=ProtoOAOrderType.MARKET,
            order_side=ProtoOAOrderSide.BUY if side.upper() == "BUY" else ProtoOAOrderSide.SELL,
            volume=int(volume),
            time_in_force=ProtoOATimeInForce.FILL_OR_KILL,
            comment="Order from TradingView Webhook"
        )

        print(f"[cTrader SDK] ✅ Orden de mercado ejecutada: {side.upper()} {volume} de {symbol} (symbolId: {symbol_id})")
        return order_id
