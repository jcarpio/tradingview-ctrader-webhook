import os
from dotenv import load_dotenv
from openapi_client import Client
from openapi_client.exceptions import ClientException
from openapi_client.models import ProtoOAOrderType, ProtoOATimeInForce, ProtoOAOrderSide, ProtoOADealStatus

load_dotenv()

class CTrader:
    def __init__(self):
        self.client_id = os.getenv("CLIENT_ID")
        self.client_secret = os.getenv("CLIENT_SECRET")
        self.account_id = int(os.getenv("ACCOUNT_ID"))
        self.access_token = os.getenv("CTRADER_ACCESS_TOKEN")
        self.refresh_token = os.getenv("CTRADER_REFRESH_TOKEN")
        self.client = None

    def connect(self):
        try:
            self.client = Client()
            self.client.connect()
            print("[cTrader SDK] 🔌 Conectado correctamente")
            
            # Autenticarse
            self.client.authenticate_by_refresh_token(
                refresh_token=self.refresh_token,
                client_id=self.client_id,
                client_secret=self.client_secret,
            )
            print("[cTrader SDK] ✅ Autenticado correctamente")

            # Autorizar cuenta
            self.client.authorize_trading_account(
                ctid_trader_account_id=self.account_id,
                access_token=self.client.access_token,
            )
            print(f"[cTrader SDK] ✅ Cuenta autenticada correctamente (ID: {self.account_id})")

        except ClientException as e:
            print("❌ Error conectando o autenticando con cTrader:", e)
            raise e

    def place_market_order(self, symbol_id, side, volume):
        try:
            response = self.client.send_market_order(
                account_id=self.account_id,
                symbol_id=int(symbol_id),
                order_type=ProtoOAOrderType.MARKET,
                order_side=ProtoOAOrderSide.BUY if side.upper() == "BUY" else ProtoOAOrderSide.SELL,
                volume=int(volume),
                time_in_force=ProtoOATimeInForce.FILL_OR_KILL,
                comment="Order from TradingView Webhook",
            )

            if response.deal_status == ProtoOADealStatus.FILLED:
                print(f"[cTrader SDK] ✅ Orden ejecutada correctamente (orderId: {response.order_id})")
            else:
                print(f"⚠️ Orden enviada pero no fue ejecutada (status: {response.deal_status})")

        except ClientException as e:
            print("❌ Error al enviar orden de mercado:", e)
            raise e
        finally:
            self.client.stop()
            print("[cTrader SDK] 🔌 Conexión cerrada correctamente")
