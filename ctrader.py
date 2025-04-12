import asyncio
import json
import websockets
import os
from dotenv import load_dotenv
from websockets.exceptions import ConnectionClosedOK

load_dotenv()

class CTrader:
    def __init__(self):
        self.access_token = os.getenv("CTRADER_ACCESS_TOKEN")
        self.account_id = int(os.getenv("ACCOUNT_ID"))
        self.ws = None

    async def connect(self):
        self.ws = await websockets.connect("wss://demo.ctraderapi.com:5035")
        await self.authenticate()
        await self.authenticate_account()

    async def authenticate(self):
        auth_msg = {
            "payloadType": "ProtoOAPayloadType.OAUTH_TOKEN",
            "payload": {
                "accessToken": self.access_token
            }
        }
        await self.send(auth_msg)
        print("[cTrader SDK] ✅ Autenticado correctamente")

    async def authenticate_account(self):
        auth_msg = {
            "payloadType": "ProtoOAPayloadType.OA_ACCOUNT_AUTH_REQ",
            "payload": {
                "ctidTraderAccountId": self.account_id,
                "accessToken": self.access_token
            }
        }
        await self.send(auth_msg)
        print(f"[cTrader SDK] ✅ Cuenta autenticada correctamente (ID: {self.account_id})")

    async def send(self, message):
        await self.ws.send(json.dumps(message))

    async def receive(self):
        response = await self.ws.recv()
        return json.loads(response)

    async def place_market_order(self, symbol, side, volume):
        order_msg = {
            "payloadType": "ProtoOAPayloadType.OA_NEW_ORDER_REQ",
            "payload": {
                "accountId": self.account_id,
                "symbolName": symbol,
                "orderType": "MARKET",
                "orderSide": side.upper(),  # BUY o SELL
                "volume": int(volume),
                "timeInForce": "FILL_OR_KILL",
                "comment": "Order from TradingView Webhook"
            }
        }

        await self.send(order_msg)
        print(f"[cTrader SDK] ✅ Orden enviada: {side.upper()} {volume} de {symbol}")

        try:
            response = await asyncio.wait_for(self.receive(), timeout=3)
            print(f"[cTrader SDK] 📩 Respuesta del servidor:", response)
        except asyncio.TimeoutError:
            print("⚠️ No se recibió respuesta de la orden. Puede que el servidor haya cerrado la conexión.")
        except ConnectionClosedOK:
            print("⚠️ Conexión cerrada después del intento de orden. Verifica volumen y formato del mensaje.")
        finally:
            await self.ws.close()
            print("[cTrader SDK] 🔌 Conexión cerrada correctamente")

# Ejemplo de uso:
# async def main():
#     bot = CTrader()
#     await bot.connect()
#     await bot.place_market_order("BTCUSD", "BUY", 100000)
#
# asyncio.run(main())
