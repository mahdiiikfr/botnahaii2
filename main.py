import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiohttp import web

from config.config import BOT_TOKEN, ADMINS, ADMIN_LOG_CHANNEL, WEB_PORT
from database.db import Database
from handlers.user import user_router
from handlers.admin import admin_router
from middlewares.antispam import AntiSpamMiddleware
from middlewares.check_join import CheckJoinMiddleware

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# --- Background Subscriptions Task ---
async def check_user_subscriptions_task(bot: Bot, db: Database):
    """Background task to periodically scan expired user subscriptions and alert them."""
    try:
        expired_users = await db.get_expired_users()
        for user_id, username, expires_at in expired_users:
            try:
                alert_text = (
                    "⚠️ **هشدار انقضای اشتراک!**\n\n"
                    f"کاربر گرامی، اشتراک شما در تاریخ `{expires_at}` به پایان رسیده است.\n"
                    "جهت تمدید اشتراک خود و دسترسی مجدد به خدمات، می‌توانید از منوی فروشگاه خرید جدید ثبت کنید."
                )
                await bot.send_message(chat_id=user_id, text=alert_text, parse_mode="Markdown")
                # Clear expires_at so they don't get duplicate alerts until renewed
                async with db._lock:
                    await db.conn.execute("UPDATE users SET expires_at = NULL WHERE id = ?", (user_id,))
                    await db.conn.commit()
                logger.info(f"Sent expiration warning to user {user_id}")
            except Exception as e:
                logger.error(f"Could not send expiration warning to user {user_id}: {e}")
    except Exception as e:
        logger.error(f"Error checking user subscriptions: {e}")

# --- ZarinPal Callback Web Handler ---
async def handle_zarinpal_callback(request: web.Request) -> web.Response:
    bot: Bot = request.app["bot"]
    db: Database = request.app["db"]

    params = request.query
    status = params.get("Status")
    authority = params.get("Authority")
    order_id = params.get("order_id")

    logger.info(f"Received ZarinPal webhook callback. Status: {status}, Authority: {authority}, OrderID: {order_id}")

    if not order_id or not authority:
        return web.Response(
            text="<html><body style='font-family:tahoma;text-align:center;'><h2>❌ اطلاعات پرداخت نامعتبر است.</h2></body></html>",
            content_type="text/html",
            charset="utf-8"
        )

    order = await db.get_order(order_id)
    if not order:
        return web.Response(
            text="<html><body style='font-family:tahoma;text-align:center;'><h2>❌ سفارش یافت نشد.</h2></body></html>",
            content_type="text/html",
            charset="utf-8"
        )

    user_id = order[1]
    amount = order[3]
    product_name = order[10] if order[10] else "شارژ کیف پول"
    order_status = order[7]

    if order_status != "pending":
        return web.Response(
            text=f"<html><body style='font-family:tahoma;text-align:center;'><h2>📊 این سفارش قبلاً پردازش شده است. وضعیت سفارش: {order_status}</h2></body></html>",
            content_type="text/html",
            charset="utf-8"
        )

    if status == "OK":
        from utils.zarinpal import ZarinPal
        zp = ZarinPal()
        success, ref_id_or_err = await zp.verify_payment(amount, authority)

        if success:
            # Payment verified successfully!

            # 1. Check if this is a wallet charge order!
            if order[2] is None:
                await db.update_order_status(order_id, "approved")
                await db.add_balance(user_id, amount)

                user_text = (
                    f"🔋 **تراکنش شارژ کیف پول با موفقیت تایید شد!**\n\n"
                    f"💵 مبلغ **{amount:,} تومان** به اعتبار کیف پول شما افزوده شد."
                )
                try:
                    await bot.send_message(chat_id=user_id, text=user_text, parse_mode=ParseMode.MARKDOWN)
                except Exception:
                    pass

                admin_text = (
                    f"🔋 **شارژ موفق آنلاین حساب کاربری!**\n\n"
                    f"👤 کاربر: `{user_id}`\n"
                    f"💵 مبلغ شارژ: {amount:,} تومان\n"
                    f"🆔 کد پیگیری سفارش: `{order_id}`\n"
                    f"🧾 شماره تراکنش (Ref ID): `{ref_id_or_err}`"
                )
                try:
                    await bot.send_message(chat_id=ADMIN_LOG_CHANNEL, text=admin_text, parse_mode=ParseMode.MARKDOWN)
                except Exception:
                    pass

                return web.Response(
                    text=f"<html><body style='font-family:tahoma;text-align:center;color:green;'><h2>🎉 کیف پول شما با موفقیت شارژ شد!</h2><p>مبلغ: {amount:,} تومان</p><p>کد پیگیری: {order_id}</p></body></html>",
                    content_type="text/html",
                    charset="utf-8"
                )

            # 2. Otherwise, this is a standard product purchase order
            product = await db.get_product(order[2])
            auto_deliver = product[5] if product else 0

            if auto_deliver:
                content = await db.pop_inventory_item(order[2])
                if content:
                    await db.update_order_status(order_id, "approved", content)

                    user_text = (
                        f"✅ **پرداخت آنلاین شما با موفقیت تایید شد!**\n\n"
                        f"🛍️ **محصول:** {product_name}\n"
                        f"⚡ **محتوای لایسنس / اشتراک شما:**\n\n"
                        f"`{content}`\n\n"
                        "سپاس از خرید شما! مجدداً از منوی اصلی در خدمت شما هستیم."
                    )
                    try:
                        await bot.send_message(chat_id=user_id, text=user_text, parse_mode=ParseMode.MARKDOWN)
                    except Exception:
                        logger.exception("Failed to alert user about automated subscription delivery")

                    admin_text = (
                        f"🟢 **پرداخت موفق آنلاین و تحویل خودکار!**\n\n"
                        f"👤 کاربر: `{user_id}`\n"
                        f"📦 محصول: {product_name}\n"
                        f"💵 مبلغ: {amount:,} تومان\n"
                        f"🆔 کد پیگیری سفارش: `{order_id}`\n"
                        f"🧾 شماره تراکنش (Ref ID): `{ref_id_or_err}`"
                    )
                    try:
                        await bot.send_message(chat_id=ADMIN_LOG_CHANNEL, text=admin_text, parse_mode=ParseMode.MARKDOWN)
                    except Exception:
                        logger.exception("Failed to alert admin log channel")

                    return web.Response(
                        text=f"<html><body style='font-family:tahoma;text-align:center;color:green;'><h2>🎉 پرداخت شما با موفقیت انجام شد!</h2><p>کد پیگیری سفارش: {order_id}</p><p>محتوای محصول خریداری شده در تلگرام برای شما ارسال گردید.</p></body></html>",
                        content_type="text/html",
                        charset="utf-8"
                    )
                else:
                    # Auto deliver but inventory is empty
                    await db.update_order_status(order_id, "approved")
                    user_text = (
                        f"✅ **پرداخت آنلاین شما با موفقیت تایید شد!**\n\n"
                        f"🛍️ **محصول:** {product_name}\n"
                        "✍️ به دلیل اتمام موجودی انبار، محصول شما به زودی توسط مدیریت به صورت دستی برای شما ارسال خواهد شد."
                    )
                    try:
                        await bot.send_message(chat_id=user_id, text=user_text, parse_mode=ParseMode.MARKDOWN)
                    except Exception:
                        pass

                    admin_text = (
                        f"⚠️ **پرداخت موفق آنلاین اما انبار خالی است!**\n\n"
                        f"👤 کاربر: `{user_id}`\n"
                        f"📦 محصول: {product_name}\n"
                        f"💵 مبلغ: {amount:,} تومان\n"
                        f"🆔 کد پیگیری سفارش: `{order_id}`\n\n"
                        "لطفاً محصول را به صورت دستی در پی‌وی کاربر تحویل دهید."
                    )
                    try:
                        await bot.send_message(chat_id=ADMIN_LOG_CHANNEL, text=admin_text, parse_mode=ParseMode.MARKDOWN)
                    except Exception:
                        pass

                    return web.Response(
                        text=f"<html><body style='font-family:tahoma;text-align:center;'><h2>🎉 پرداخت شما موفقیت‌آمیز بود!</h2><p>کد پیگیری: {order_id}</p><p>به دلیل اتمام موقتی موجودی انبار، همکاران ما به زودی لایسنس را در تلگرام برای شما ارسال خواهند کرد.</p></body></html>",
                        content_type="text/html",
                        charset="utf-8"
                    )
            else:
                # Manual delivery
                await db.update_order_status(order_id, "approved")
                user_text = (
                    f"✅ **پرداخت آنلاین شما با موفقیت تایید شد!**\n\n"
                    f"🛍️ **محصول:** {product_name}\n"
                    "✍️ محصول شما به زودی توسط پشتیبانی آماده شده و ارسال خواهد شد. از صبوری شما سپاسگزاریم."
                )
                try:
                    await bot.send_message(chat_id=user_id, text=user_text, parse_mode=ParseMode.MARKDOWN)
                except Exception:
                    pass

                admin_text = (
                    f"📥 **سفارش جدید پرداخت شده آنلاین (تحویل دستی)**\n\n"
                    f"👤 کاربر: `{user_id}`\n"
                    f"📦 محصول: {product_name}\n"
                    f"💵 مبلغ: {amount:,} تومان\n"
                    f"🆔 کد پیگیری سفارش: `{order_id}`\n\n"
                    "لطفاً محصول را آماده کرده و برای کاربر ارسال کنید."
                )
                try:
                    await bot.send_message(chat_id=ADMIN_LOG_CHANNEL, text=admin_text, parse_mode=ParseMode.MARKDOWN)
                except Exception:
                    pass

                return web.Response(
                    text=f"<html><body style='font-family:tahoma;text-align:center;color:green;'><h2>🎉 پرداخت شما موفقیت‌آمیز بود!</h2><p>کد پیگیری سفارش: {order_id}</p><p>پشتیبانی به زودی لایسنس/اشتراک را در تلگرام به شما تحویل خواهد داد.</p></body></html>",
                    content_type="text/html",
                    charset="utf-8"
                )
        else:
            # Verification failed
            await db.update_order_status(order_id, "rejected")

            user_notify_text = (
                f"❌ **پرداخت سفارش `{order_id}` ناموفق بود!**\n\n"
                f"توضیحات خطا: {ref_id_or_err}\n"
                "در صورت کسر وجه از حساب، مبلغ طی ۷۲ ساعت آینده توسط بانک عودت داده می‌شود. مجدداً می‌توانید سفارش ثبت کنید."
            )
            try:
                await bot.send_message(chat_id=user_id, text=user_notify_text, parse_mode=ParseMode.MARKDOWN)
            except Exception:
                pass

            admin_notify_text = (
                f"🔴 **خطا در تایید تراکنش آنلاین!**\n\n"
                f"👤 کاربر: `{user_id}`\n"
                f"📦 محصول: {product_name}\n"
                f"💵 مبلغ: {amount:,} تومان\n"
                f"🆔 کد پیگیری سفارش: `{order_id}`\n"
                f"❌ علت خطا: `{ref_id_or_err}`"
            )
            try:
                await bot.send_message(chat_id=ADMIN_LOG_CHANNEL, text=admin_notify_text, parse_mode=ParseMode.MARKDOWN)
            except Exception:
                pass

            return web.Response(
                text=f"<html><body style='font-family:tahoma;text-align:center;color:red;'><h2>❌ خطا در تایید تراکنش</h2><p>توضیحات خطا: {ref_id_or_err}</p></body></html>",
                content_type="text/html",
                charset="utf-8"
            )
    else:
        # Canceled or failed Status on gateway
        await db.update_order_status(order_id, "rejected")

        user_notify_text = (
            f"❌ **تراکنش سفارش `{order_id}` لغو شد یا با موفقیت انجام نگردید!**\n\n"
            "پرداخت توسط شما لغو شد یا تراکنش ناموفق بود. در صورت تمایل می‌توانید مجدداً از منوی ربات خرید نمایید."
        )
        try:
            await bot.send_message(chat_id=user_id, text=user_notify_text, parse_mode=ParseMode.MARKDOWN)
        except Exception:
            pass

        admin_notify_text = (
            f"🔴 **تراکنش آنلاین لغو شده توسط کاربر**\n\n"
            f"👤 کاربر: `{user_id}`\n"
            f"📦 محصول: {product_name}\n"
            f"💵 مبلغ: {amount:,} تومان\n"
            f"🆔 کد پیگیری سفارش: `{order_id}`"
        )
        try:
            await bot.send_message(chat_id=ADMIN_LOG_CHANNEL, text=admin_notify_text, parse_mode=ParseMode.MARKDOWN)
        except Exception:
            pass

        return web.Response(
            text="<html><body style='font-family:tahoma;text-align:center;'><h2>❌ پرداخت توسط کاربر لغو شد یا ناموفق بود.</h2></body></html>",
            content_type="text/html",
            charset="utf-8"
        )

# --- Main Bootstrapping Runner ---
async def main():
    logger.info("Initializing bot and database...")

    # Initialize DB
    db = Database()
    await db.connect()

    # Initialize Bot and Dispatcher
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    # Register Middlewares
    dp.message.middleware(AntiSpamMiddleware(limit=0.5))
    dp.callback_query.middleware(AntiSpamMiddleware(limit=0.5))

    dp.message.middleware(CheckJoinMiddleware())
    dp.callback_query.middleware(CheckJoinMiddleware())

    # Register Routers
    dp.include_router(admin_router)
    dp.include_router(user_router)

    # Initialize Scheduler for background subscription check
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        check_user_subscriptions_task,
        "interval",
        hours=12,
        args=[bot, db]
    )
    scheduler.start()
    logger.info("Background subscription scheduler task started.")

    # Setup AIOHTTP Web Server for ZarinPal callbacks running side-by-side
    app = web.Application()
    app["bot"] = bot
    app["db"] = db
    app.router.add_get("/", handle_zarinpal_callback)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", WEB_PORT)
    await site.start()
    logger.info(f"AIOHTTP Web server for ZarinPal callbacks listening on port {WEB_PORT}...")

    # Start Polling
    try:
        logger.info("Starting Telegram bot polling...")
        await dp.start_polling(bot, skip_updates=True)
    finally:
        scheduler.shutdown()
        await runner.cleanup()
        await db.disconnect()
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
