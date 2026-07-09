import time
from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery

class AntiSpamMiddleware(BaseMiddleware):
    def __init__(self, limit: float = 0.5):
        super().__init__()
        self.limit = limit
        self.last_action = {}

    async def __call__(
        self,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: Dict[str, Any]
    ) -> Any:
        user_id = None
        if isinstance(event, Message):
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id

        if user_id:
            now = time.time()
            if user_id in self.last_action:
                delta = now - self.last_action[user_id]
                if delta < self.limit:
                    if isinstance(event, CallbackQuery):
                        await event.answer("⚠️ لطفاً کمی صبر کنید! سرعت کلیک شما بسیار بالاست.", show_alert=True)
                    return
            self.last_action[user_id] = now

        return await handler(event, data)
