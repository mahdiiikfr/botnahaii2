import logging
from aiogram import Bot
from aiogram.enums import ParseMode
from database.db import Database

logger = logging.getLogger(__name__)

async def process_referral_reward(bot: Bot, db: Database, order_id: str):
    """
    Checks if the order has a referral reward eligible, rewards the referrer,
    and sends a private message notification to the referrer.
    """
    try:
        reward_res = await db.reward_referrer_if_eligible(order_id)
        if reward_res:
            referrer_id, new_balance = reward_res
            reward_msg = (
                f"🎉 <b>تبریک! یکی از دوستان دعوت‌شده شما خرید انجام داد!</b>\n\n"
                f"💵 مبلغ <b>۱۰,۰۰۰ تومان</b> هدیه به کیف پول شما اضافه شد.\n"
                f"👛 موجودی جدید کیف پول شما: <b>{new_balance:,} تومان</b>"
            )
            try:
                await bot.send_message(chat_id=referrer_id, text=reward_msg, parse_mode=ParseMode.HTML)
                logger.info(f"Successfully rewarded and notified referrer {referrer_id} for order {order_id}")
            except Exception as e_msg:
                logger.warning(f"Failed to send referral reward notification to {referrer_id}: {e_msg}")
    except Exception as e:
        logger.error(f"Error in process_referral_reward: {e}")
