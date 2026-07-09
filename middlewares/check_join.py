from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ButtonStyle
from aiogram.exceptions import TelegramBadRequest
from config.config import REQUIRED_CHANNEL, REQUIRED_CHANNEL_LINK, ADMINS

class CheckJoinMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: Dict[str, Any]
    ) -> Any:
        user_id = None
        if isinstance(event, Message):
            user_id = event.from_user.id
            # Allow /start without checking join, to let them see start msg or handle deep link
            if event.text and event.text.startswith("/start"):
                return await handler(event, data)
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
            if event.data == "check_membership":
                pass  # We handle check_membership button explicitly in user.py

        if user_id:
            # Skip join check for admins
            if user_id in ADMINS:
                return await handler(event, data)

            bot = data["bot"]
            try:
                member = await bot.get_chat_member(chat_id=REQUIRED_CHANNEL, user_id=user_id)
                if member.status in ["kicked", "left"]:
                    return await self._show_join_message(event, bot)
            except TelegramBadRequest:
                # If bot cannot check channel membership (e.g. not admin), proceed anyway
                return await handler(event, data)
            except Exception:
                # Fallback for any other errors
                return await handler(event, data)

        return await handler(event, data)

    async def _show_join_message(self, event: Any, bot: Any):
        text = (
            "🔴 **برای استفاده از تمامی امکانات ربات، ابتدا باید عضو کانال ما شوید!**\n\n"
            "پس از عضویت در کانال، دکمه‌ی زیر را برای بررسی مجدد کلیک کنید 👇"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 عضویت در کانال ما", url=REQUIRED_CHANNEL_LINK)],
            [InlineKeyboardButton(text="🟢 بررسی عضویت و ورود", callback_data="check_membership", style=ButtonStyle.SUCCESS)]
        ])

        if isinstance(event, Message):
            await event.answer(text, reply_markup=keyboard, parse_mode="Markdown")
        elif isinstance(event, CallbackQuery):
            try:
                # Edit message cleanly to stay single-page
                await event.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
            except Exception:
                await event.answer("⚠️ لطفاً ابتدا در کانال عضو شوید!", show_alert=True)
        return
