import os
import logging
from ctrader_open_api import Client, Protobuf, TcpProtocol, Auth, EndPoints
from ctrader_open_api.messages.OpenApiMessages_pb2 import ProtoOAApplicationAuthReq, ProtoOAAccountAuthReq, ProtoOANewOrderReq
from ctrader_open_api.messages.OpenApiModelMessages_pb2 import ProtoOAOrderType, ProtoOATradeSide
from dotenv import load_dotenv
from twisted.internet import reactor

class CTraderBot:
    def __init__(self):
        load_dotenv()
        self.client_id = os.getenv("CTRADER_CLIENT_ID")
        self.client_secret = os.getenv("CTRADER_CLIENT_SECRET")
        self.access_token = os.getenv("CTRADER_ACCESS_TOKEN")
        self.account_id = int(os.getenv("ACCOUNT_ID"))
        self.environment = os.getenv("CTRADER_ENV", "demo").lower()
        self.client = None

    def connect(self):
        host = EndPoints.PROTOBUF_LIVE_HOST if self.environment == "live" else EndPoints.PROTOBUF_DEMO_HOST
        self.client = Client(host, EndPoints.PROTOBUF_PORT, TcpProtocol)
        self.client.setConnectedCallback(self._on_connected)
        self.client.setDisconnectedCallback(self._on_disconnected)
        self.client.setMessageReceivedCallback(self._on_message)
        self.client.startService()
        reactor.run()

    def _on_connected(self, client):
        print("✅ Connected to cTrader API")
        request = ProtoOAApplicationAuthReq()
        request.clientId = self.client_id
        request.clientSecret = self.client_secret
        self.client.send(request)

        auth_req = ProtoOAAccountAuthReq()
        auth_req.ctidTraderAccountId = self.account_id
        auth_req.accessToken = self.access_token
        self.client.send(auth_req)

    def _on_disconnected(self, client, reason):
        print("⚠️ Disconnected:", reason)

    def _on_message(self, client, message):
        if message.payloadType == 2105:
            print("✅ Account authenticated")
        elif message.payloadType == 2205:
            print("✅ Order placed successfully")
        else:
            print("📩 Message received:", Protobuf.extract(message))

    def send_market_order(self, symbol_id: int, side: str, volume: float):
        order = ProtoOANewOrderReq()
        order.ctidTraderAccountId = self.account_id
        order.symbolId = symbol_id
        order.orderType = ProtoOAOrderType.MARKET
        order.tradeSide = ProtoOATradeSide.BUY if side.upper() == "BUY" else ProtoOATradeSide.SELL
        order.volume = int(volume * 100)  # Convert to cents
        self.client.send(order)

# Test script if run standalone
if __name__ == "__main__":
    bot = CTraderBot()
    bot.connect()
    # Order can be triggered later by an external message
