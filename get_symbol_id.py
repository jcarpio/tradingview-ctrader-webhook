from ctrader_open_api import Client, Protobuf, TcpProtocol, EndPoints
from ctrader_open_api.messages.OpenApiMessages_pb2 import ProtoOAGetSymbolBySymbolNameReq
from dotenv import load_dotenv
import os
from twisted.internet import reactor

load_dotenv()

ACCOUNT_ID = int(os.getenv("ACCOUNT_ID"))
ACCESS_TOKEN = os.getenv("CTRADER_ACCESS_TOKEN")
SYMBOL_NAME = "US30"

client = Client(EndPoints.PROTOBUF_DEMO_HOST, EndPoints.PROTOBUF_PORT, TcpProtocol)

def on_connected(client):
    print("Connected to cTrader. Requesting symbol info...")
    request = ProtoOAGetSymbolBySymbolNameReq()
    request.ctidTraderAccountId = ACCOUNT_ID
    request.accessToken = ACCESS_TOKEN
    request.symbolName = SYMBOL_NAME
    client.send(request)

def on_message(client, message):
    print("Response received:")
    print(Protobuf.extract(message))
    reactor.stop()

def on_disconnected(client, reason):
    print("Disconnected:", reason)

client.setConnectedCallback(on_connected)
client.setMessageReceivedCallback(on_message)
client.setDisconnectedCallback(on_disconnected)
client.startService()
reactor.run()
