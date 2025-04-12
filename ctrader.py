import os
import asyncio
from dotenv import load_dotenv
from openapi_client import Client, ProtoOAOrderType, ProtoOATimeInForce, ProtoOAOrderSide, ProtoOADealStatus
from openapi_client.messages_pb2 import ProtoOAApplicationAuthRes, ProtoOASubscribeSpotsRes, ProtoOADealListRes, ProtoOANewOrderRes, ProtoOANewOrderReq

load_dotenv()

SYMBOLS = {
    "BTCUSD": 6080842,
    "ETHUSD": 6080843,
    "EURUSD": 1,
    "XAUUSD": 2,
}

class CTrader:
    def __init__(self):
        self.client_id = os.getenv("CTRADER_CLIENT_ID")
        self.client_secret = os.getenv("CTRADER_CLIENT_SECRET")
        self.access_token = os.getenv("CTRADER_ACCESS_TOKEN")
        self.account_id = int(os.getenv("ACCOUNT_ID"))
        self.client = None

    async def connect(self):
        self.client = Client()
        await self.client.connect()

        await self.client.send_application_auth_req(
            client_id=self.client_id,
            client_secret=self.client_secret
        )
        print("[cTrader SDK] ✅ Autenticado correctamente")

        await self.client.send_account_auth_req(
            ctid_trader_account_id=self.account_id,
            access_token=self.access_token
        )
        print(f"[cTrader SDK] ✅ Cuenta autenticada correctamente (ID: {self.account_id})")

    async def place_market_order(self, symbol: str, side: str, volume: int):
        if symbol not in SYMBOLS:
            raise Exception(f"❌ El símbolo {symbol} no está en la lista local. Añádelo a SYMBOLS.")

        symbol_id = SYMBOLS[symbol]
        print(f"[cTrader SDK] ✅ Enviando orden: {side.upper()} {volume} de {symbol} (symbolId: {symbol_id})")

        try:
            request = ProtoOANewOrderReq(
                ctid_trader_account_id=self.account_id,
                symbol_id=symbol_id,
                order_type=ProtoOAOrderType.MARKET,
                order_side=ProtoOAOrderSide.BUY if side.upper() == "BUY" else ProtoOAOrderSide.SELL,
                volume=volume,
                time_in_force=ProtoOATimeInForce.FILL_OR_KILL,
                comment="Order from TradingView Webhook"
            )

            response = await self.client.send(request)

            if isinstance(response, ProtoOANewOrderRes):
                print(f"[cTrader SDK] ✅ Orden aceptada por el servidor. Order ID: {response.order_id}")
            else:
                print(f"[cTrader SDK] ❓ Respuesta inesperada del servidor: {type(response)}")

        except Exception as e:
            print(f"⚠️ Error al enviar la orden: {str(e)}")
        finally:
            await self.client.close()
            print("[cTrader SDK] 🔌 Conexión cerrada correctamente")

# Ejemplo para probar:
# if __name__ == '__main__':
#     async def main():
#         trader = CTrader()
#         await trader.connect()
#         await trader.place_market_order("BTCUSD", "BUY", 100000)
#     asyncio.run(main())
