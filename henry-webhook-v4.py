import os
import logging
from dotenv import load_dotenv
from ctrader_open_api import protocol_pb2
from ctrader_open_api.client import SpotwareClient
from ctrader_open_api.listener import SpotwareListener

load_dotenv()

class CTraderSDK:
    def __init__(self):
        self.client_id = os.getenv("CTRADER_CLIENT_ID")
        self.client_secret = os.getenv("CTRADER_CLIENT_SECRET")
        self.account_id = int(os.getenv("ACCOUNT_ID"))
        self.refresh_token = os.getenv("CTRADER_REFRESH_TOKEN")
        self.client = None
        self.connected = False

    def start(self):
        if not all([self.client_id, self.client_secret, self.refresh_token]):
            raise Exception("⚠️ Faltan variables de entorno para conectar con cTrader API")

        self.client = SpotwareClient(
            client_id=self.client_id,
            client_secret=self.client_secret,
            refresh_token=self.refresh_token,
            environment="demo"  # o "live" si fuese necesario
        )

        self.client.add_listener(SpotwareListener(self.client))
        self.client.connect()
        self.connected = True
        logging.info("[cTrader SDK] ✅ Cliente conectado con éxito")

    def stop(self):
        if self.client:
            self.client.close()
            self.connected = False
            logging.info("[cTrader SDK] 🔌 Conexión cerrada correctamente")

    def send_market_order(self, symbol_id: int, side: str, volume: int):
        if not self.connected:
            self.start()

        order_side_enum = protocol_pb2.OAOrderSide.BUY if side.upper() == "BUY" else protocol_pb2.OAOrderSide.SELL

        self.client.send_request(
            payload_type=protocol_pb2.OA_NEW_ORDER_REQ,
            payload={
                "accountId": self.account_id,
                "symbolId": symbol_id,
                "orderType": protocol_pb2.OAOrderType.MARKET,
                "orderSide": order_side_enum,
                "volume": volume,
                "timeInForce": protocol_pb2.OATimeInForce.FOK,
                "comment": "Order from TradingView Webhook"
            }
        )
        logging.info(f"[cTrader SDK] ✅ Orden de mercado enviada: {side.upper()} {volume} (symbolId: {symbol_id})")
