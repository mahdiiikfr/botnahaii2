import logging
from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from database.db import Database

logger = logging.getLogger(__name__)

class CleanupPendingMiddleware(BaseMiddleware):
    """
    Middleware that silently deletes any pending orders if a user takes an action
    outside of the active order checkout process (e.g., clicking on main menu,
    starting again, or other flows).
    """
    def __init__(self):
        super().__init__()
        self.db = Database()

    async def __call__(
        self,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: Dict[str, Any]
    ) -> Any:
        user_id = None
        is_outside_flow = False

        if isinstance(event, Message):
            user_id = event.from_user.id
            text = event.text or ""
            # Any non-checkout state/command, like /start or main text entries triggers a silent cleanup
            # Wait states are checked. If user is entering discount code or waiting for receipt, we do NOT cleanup.
            state = data.get("state")
            current_state = await state.get_state() if state else None

            # If they are in wait states for payment/discount/receipt, they are inside the flow.
            # If they are not in those states, or if they explicitly sent /start, they are outside the flow.
            if current_state not in ["UserStates:entering_discount", "UserStates:waiting_for_receipt"]:
                is_outside_flow = True
            if text.startswith("/start"):
                is_outside_flow = True

        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
            callback_data = event.data or ""

            # List of callback queries that are part of the checkout process.
            # If the callback query is NOT in this list, they are going somewhere else, so cleanup pending orders.
            checkout_callbacks = [
                "buy_", "pay_wallet_", "apply_discount_", "back_to_pay_",
                "pay_zarinpal_", "pay_card_", "upload_receipt_", "cancel_order_"
            ]

            # Check if callback_data starts with any checkout keywords
            is_checkout = any(callback_data.startswith(prefix) for prefix in checkout_callbacks)
            if not is_checkout:
                is_outside_flow = True

        if user_id and is_outside_flow:
            try:
                # Silently delete all pending orders for this user
                await self.db.delete_pending_orders(user_id)
            except Exception as e:
                logger.error(f"Error silently cleaning up pending orders for user {user_id}: {e}")

        return await handler(event, data)
