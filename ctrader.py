import asyncio
import json
import time
import aiohttp
import websockets
import os
from dotenv import load_dotenv

load_dotenv()

class CTrader:
    def __init__(self):
        self.client_id = os.getenv("CTRADER_CLIENT_ID")
        self.client_secret = os.getenv("CTRADER_CLIENT_SECRET")
        self.refresh_token = os.getenv("CTRADER_REFRESH_TOKEN")
        self.account_id = int(os.getenv("ACCOUNT_ID"))
        self.access_token = None
        self.ws = None

    async def refresh_access_token(self):
        url = "https://api.spotware.com/connect/token"
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': self.refresh_token,
            'client_id': self.client_id,
            'client_secret': self.client_secret
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data) as resp:
                result = await resp.json()
                self.access_token = result["access_token"]
                print("[cTrader SDK] ✅ Access token refreshed")

    async def connect(self):
        await self.refresh_access_token()
        self.ws = await websockets.connect("wss://openapi.ctrader.com:5035")
        await self.authenticate()

    async def authenticate(self):
        auth_msg = {
            "payloadType": "ProtoOAPayloadType.OAUTH_TOKEN",
            "payload": {
                "accessToken": self.access_token
            }
        }
        await self.send(auth_msg)
        print("[cTrader SDK] ✅ Autenticado correctamente")

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
                "orderSide": side.upper(),  # BUY or SELL
                "volume": int(volume),
                "timeInForce": "FILL_OR_KILL",
                "comment": "Order from TradingView Webhook"
            }
        }
        await self.send(order_msg)
        print(f"[cTrader SDK] ✅ Orden enviada: {side.upper()} {volume} de {symbol}")

# Ejemplo de uso:
# async def main():
#     bot = CTrader()
#     await bot.connect()
#     await bot.place_market_order("BTCUSD", "BUY", 100000)
#
# asyncio.run(main())
