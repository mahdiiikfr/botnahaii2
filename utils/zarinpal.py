import aiohttp
import json
import logging
from config.config import ZARINPAL_MERCHANT_ID, ZARINPAL_CALLBACK_URL, ZARINPAL_SANDBOX

logger = logging.getLogger(__name__)

class ZarinPal:
    def __init__(self):
        self.merchant_id = ZARINPAL_MERCHANT_ID
        self.callback_url = ZARINPAL_CALLBACK_URL

        # We will dynamically try these endpoints in sequence for fault-tolerance (routing/timeout fixes)
        if ZARINPAL_SANDBOX:
            self.request_endpoints = ["https://sandbox.zarinpal.com/pg/v4/payment/request.json"]
            self.verify_endpoints = ["https://sandbox.zarinpal.com/pg/v4/payment/verify.json"]
            self.gateway_url = "https://sandbox.zarinpal.com/pg/StartPay/"
        else:
            self.request_endpoints = [
                "https://api.zarinpal.com/pg/v4/payment/request.json",
                "https://payment.zarinpal.com/pg/v4/payment/request.json",
                "https://de.zarinpal.com/pg/v4/payment/request.json"
            ]
            self.verify_endpoints = [
                "https://api.zarinpal.com/pg/v4/payment/verify.json",
                "https://payment.zarinpal.com/pg/v4/payment/verify.json",
                "https://de.zarinpal.com/pg/v4/payment/verify.json"
            ]
            self.gateway_url = "https://www.zarinpal.com/pg/StartPay/"

    async def request_payment(self, amount_toman: int, description: str, order_id: str) -> tuple[bool, str | None]:
        """
        Request payment gateway.
        Utilizes multiple ZarinPal mirrors sequentially in case of network timeouts or routing blocks.
        Returns: (success_bool, payment_url_or_error_message)
        """
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        payload = {
            "merchant_id": self.merchant_id,
            "amount": int(amount_toman),
            "callback_url": f"{self.callback_url}?order_id={order_id}",
            "description": description,
            "metadata": {
                "order_id": order_id
            }
        }

        last_error = ""
        # Try mirrors one by one to achieve maximum reliability and bypass routing timeouts
        for url in self.request_endpoints:
            try:
                logger.info(f"Attempting ZarinPal payment request via endpoint: {url}")
                async with aiohttp.ClientSession() as session:
                    # Timeout set to 8 seconds to allow quick failover to other mirrors if connection blocks
                    async with session.post(url, json=payload, headers=headers, timeout=8) as response:
                        res_data = await response.json()
                        if response.status == 200 or (res_data.get("data") and res_data["data"].get("code") == 100):
                            authority = res_data["data"]["authority"]
                            payment_link = f"{self.gateway_url}{authority}"
                            logger.info(f"Successfully requested payment link: {payment_link}")
                            return True, payment_link
                        else:
                            errors = res_data.get("errors")
                            last_error = f"API Error: {errors}"
                            logger.error(f"ZarinPal mirror {url} returned API error: {errors}")
            except Exception as e:
                last_error = f"Network Exception: {str(e)}"
                logger.warning(f"ZarinPal endpoint failed: {url}. Error: {str(e)}")

        logger.error(f"All ZarinPal endpoints failed to respond. Last error: {last_error}")
        return False, f"خطا در اتصال به کلیه سرورهای زرین‌پال. علت: {last_error}"

    async def verify_payment(self, amount_toman: int, authority: str) -> tuple[bool, str | None]:
        """
        Verify payment after user redirects back.
        Uses sequential mirror failover to ensure stable verification.
        Returns: (success_bool, ref_id_or_error)
        """
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        payload = {
            "merchant_id": self.merchant_id,
            "amount": int(amount_toman),
            "authority": authority
        }

        last_error = ""
        for url in self.verify_endpoints:
            try:
                logger.info(f"Attempting ZarinPal verification via endpoint: {url}")
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, json=payload, headers=headers, timeout=8) as response:
                        res_data = await response.json()
                        if response.status == 200 and res_data.get("data"):
                            code = res_data["data"].get("code")
                            if code in [100, 101]:
                                ref_id = res_data["data"]["ref_id"]
                                logger.info(f"Successfully verified payment. Ref ID: {ref_id}")
                                return True, str(ref_id)
                        errors = res_data.get("errors")
                        last_error = f"API Error: {errors}"
                        logger.error(f"ZarinPal verification mirror {url} returned API error: {errors}")
            except Exception as e:
                last_error = f"Network Exception: {str(e)}"
                logger.warning(f"ZarinPal verification endpoint failed: {url}. Error: {str(e)}")

        logger.error(f"All ZarinPal verification endpoints failed. Last error: {last_error}")
        return False, last_error
