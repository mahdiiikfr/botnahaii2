import aiohttp
import json
import logging
from config.config import ZARINPAL_MERCHANT_ID, ZARINPAL_CALLBACK_URL, ZARINPAL_SANDBOX

logger = logging.getLogger(__name__)

class ZarinPal:
    def __init__(self):
        self.merchant_id = ZARINPAL_MERCHANT_ID
        self.callback_url = ZARINPAL_CALLBACK_URL
        if ZARINPAL_SANDBOX:
            self.request_url = "https://sandbox.zarinpal.com/pg/v4/payment/request.json"
            self.verify_url = "https://sandbox.zarinpal.com/pg/v4/payment/verify.json"
            self.gateway_url = "https://sandbox.zarinpal.com/pg/StartPay/"
        else:
            self.request_url = "https://api.zarinpal.com/pg/v4/payment/request.json"
            self.verify_url = "https://api.zarinpal.com/pg/v4/payment/verify.json"
            self.gateway_url = "https://www.zarinpal.com/pg/StartPay/"

    async def request_payment(self, amount_toman: int, description: str, order_id: str) -> tuple[bool, str | None]:
        """
        Request payment gateway.
        ZarinPal API requires amount in IRR (Rials) or Toman depending on the version. V4 uses Toman.
        Returns: (success_bool, payment_url_or_error_message)
        """
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        # In ZarinPal V4, the amount is in TOMAN
        payload = {
            "merchant_id": self.merchant_id,
            "amount": int(amount_toman),
            "callback_url": f"{self.callback_url}?order_id={order_id}",
            "description": description,
            "metadata": {
                "order_id": order_id
            }
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.request_url, json=payload, headers=headers, timeout=15) as response:
                    res_data = await response.json()
                    if response.status == 200 or (res_data.get("data") and res_data["data"].get("code") == 100):
                        authority = res_data["data"]["authority"]
                        payment_link = f"{self.gateway_url}{authority}"
                        return True, payment_link
                    else:
                        errors = res_data.get("errors")
                        logger.error(f"ZarinPal request failed: {errors} - Status: {response.status}")
                        return False, str(errors)
        except Exception as e:
            logger.exception("Error requesting payment from ZarinPal")
            return False, str(e)

    async def verify_payment(self, amount_toman: int, authority: str) -> tuple[bool, str | None]:
        """
        Verify payment after user redirects back.
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
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.verify_url, json=payload, headers=headers, timeout=15) as response:
                    res_data = await response.json()
                    # A code of 100 indicates success, 101 indicates already verified
                    if response.status == 200 and res_data.get("data"):
                        code = res_data["data"].get("code")
                        if code in [100, 101]:
                            ref_id = res_data["data"]["ref_id"]
                            return True, str(ref_id)
                    errors = res_data.get("errors")
                    logger.error(f"ZarinPal verification failed: {errors} - Status: {response.status}")
                    return False, str(errors)
        except Exception as e:
            logger.exception("Error verifying payment from ZarinPal")
            return False, str(e)
