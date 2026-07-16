import os
import logging
import html
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.enums import ButtonStyle, ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from database.db import Database
from config.config import ADMINS, ADMIN_LOG_CHANNEL
from keyboards.inline import get_admin_panel_keyboard
from utils.referral import process_referral_reward

logger = logging.getLogger(__name__)
admin_router = Router()
db = Database()

# Secure Access Control: Admin only filters for admin_router
# This ensures non-admin messages and callback queries are not blocked globally
# and can safely propagate to other routers like user_router.
admin_router.message.filter(F.from_user.id.in_(ADMINS))
admin_router.callback_query.filter(F.from_user.id.in_(ADMINS))

# FSM States for Admin Panel
class AdminStates(StatesGroup):
    manual_delivery_content = State()
    rejecting_order_reason = State()
    replying_ticket = State()
    bulk_adding_test_accounts = State()

# Inline Loading feedback
async def show_loading(call: CallbackQuery):
    try:
        await call.message.edit_text("⏳ در حال پردازش...", reply_markup=None)
    except Exception:
        pass

# Admin auth helper
def is_admin(user_id: int) -> bool:
    return user_id in ADMINS

# --- Bulk Test Accounts Adding State & Commands ---
@admin_router.message(F.text == "/addtest", F.from_user.id.in_(ADMINS))
async def addtest_cmd(message: Message, state: FSMContext):
    await state.set_state(AdminStates.bulk_adding_test_accounts)
    await message.reply(
        "🎁 **وارد کردن انبوه اکانت تست آغاز شد.**\n\n"
        "لطفاً اکانت‌های تست خود را تک‌به‌تک به صورت پیام ارسال کنید. "
        "هر پیامی که بفرستید فوراً به عنوان یک اکانت تست ذخیره می‌شود.\n\n"
        "پس از اتمام کار، دستور `/endaddtest` را ارسال کنید تا فرآیند خاتمه یابد."
    )

@admin_router.message(AdminStates.bulk_adding_test_accounts, F.from_user.id.in_(ADMINS))
async def process_bulk_adding_test_accounts(message: Message, state: FSMContext):
    text = message.text.strip() if message.text else ""
    if text == "/endaddtest":
        await state.clear()
        count = await db.get_test_accounts_count()
        await message.reply(f"✅ **وارد کردن انبوه به پایان رسید.**\n\nتعداد کل اکانت‌های تست موجود در انبار: **{count} عدد**")
        return

    if not text:
        await message.reply("⚠️ محتوای پیام خالی است یا پشتیبانی نمی‌شود. لطفاً فقط متن بفرستید.")
        return

    await db.add_test_account(text)
    await message.reply("✅ اکانت تست با موفقیت ذخیره شد. بعدی را بفرستید:")


@admin_router.callback_query(F.data.startswith("adm_reply_tkt_"))
async def adm_reply_ticket_cb(call: CallbackQuery, state: FSMContext):
    ticket_id = int(call.data.split("_")[3])
    await state.update_data(ticket_id=ticket_id, message_id=call.message.message_id)
    await state.set_state(AdminStates.replying_ticket)

    await call.message.edit_text(
        f"✍️ **ارسال پاسخ به تیکت شماره {ticket_id}:**\n\n"
        "لطفاً پاسخ خود را تایپ و ارسال کنید:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 انصراف", callback_data="admin_tickets", style=ButtonStyle.DANGER)]
        ]),
        parse_mode=ParseMode.MARKDOWN
    )

@admin_router.message(AdminStates.replying_ticket)
async def process_reply_ticket_message(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    ticket_id = data.get("ticket_id")
    menu_message_id = data.get("message_id")
    reply_msg = message.text.strip()

    try:
        await message.delete()
    except Exception:
        pass

    await state.clear()

    ticket = await db.get_ticket(ticket_id)
    if not ticket:
        return

    user_id = ticket[1]
    user_orig_msg = ticket[2]

    # Save reply in db
    await db.reply_ticket(ticket_id, reply_msg)

    # Send notification to user
    user_notify_text = (
        f"🎫 **پاسخ تیکت شماره `{ticket_id}` شما ارسال شد!**\n\n"
        f"❓ **متن تیکت شما:**\n`{user_orig_msg}`\n\n"
        f"💬 **پاسخ پشتیبان:**\n**{reply_msg}**"
    )
    try:
        await bot.send_message(chat_id=user_id, text=user_notify_text)
    except Exception:
        logger.exception(f"Failed to deliver ticket reply to user {user_id}")

    await message.reply(
        "✅ پاسخ تیکت با موفقیت ثبت و برای کاربر ارسال گردید."
    )


# --- Order Verification & Delivery Mechanisms ---

@admin_router.callback_query(F.data.startswith("adm_approve_"))
async def adm_approve_order_cb(call: CallbackQuery, bot: Bot, state: FSMContext):
    order_id = call.data.split("_")[2]
    order = await db.get_order(order_id)
    if not order:
        await call.answer("❌ این سفارش دیگر وجود ندارد!", show_alert=True)
        return

    status = order[7]
    if status != 'pending':
        await call.answer(f"❌ این سفارش قبلاً پردازش شده است! وضعیت: {status}", show_alert=True)
        try:
            await call.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        return

    user_id = order[1]
    product_id = order[2]
    amount = order[3]
    product_name = order[10]

    if product_id is None:
        # This is a wallet charge order!
        await db.update_order_status(order_id, "approved")
        await db.add_balance(user_id, amount)

        user_notify_text = (
            f"🔋 <b>تراکنش شارژ حساب شما تایید شد!</b>\n\n"
            f"💵 مبلغ <b>{amount:,} تومان</b> به موجودی کیف پول دیجیتال شما افزوده گردید."
        )
        try:
            await bot.send_message(chat_id=user_id, text=user_notify_text, parse_mode=ParseMode.HTML)
        except Exception:
            pass

        # Update log message directly in active Admin PV
        await call.message.edit_caption(
            caption=f"🟢 <b>شارژ حساب <code>{order_id}</code> تایید و مبلغ {amount:,} تومان به کیف پول کاربر <code>{user_id}</code> واریز شد!</b>",
            reply_markup=None,
            parse_mode=ParseMode.HTML
        )
        await call.answer("🟢 شارژ حساب با موفقیت تایید و واریز شد.", show_alert=True)
        return

    product = await db.get_product(product_id)
    auto_deliver = product[5] if product else 0

    if auto_deliver:
        content = await db.pop_inventory_item(product_id)
        if content:
            await db.update_order_status(order_id, "approved", content)
            await process_referral_reward(bot, db, order_id)

            user_notify_text = (
                f"✅ <b>پرداخت سفارش <code>{order_id}</code> شما توسط مدیریت تایید شد!</b>\n\n"
                f"🛍️ <b>محصول:</b> {html.escape(product_name)}\n"
                f"⚡ <b>محتوای لایسنس / اشتراک شما:</b>\n\n"
                f"<code>{html.escape(content)}</code>\n\n"
                "کانفیگ یا اکانت بالا هم‌اکنون فعال است. سپاس از خرید شما!"
            )
            try:
                await bot.send_message(chat_id=user_id, text=user_notify_text, parse_mode=ParseMode.HTML)
            except Exception:
                logger.exception(f"Failed to send delivery message to user {user_id}")

            await call.message.edit_caption(
                caption=f"🟢 <b>سفارش <code>{order_id}</code> با موفقیت تایید و به صورت خودکار تحویل شد!</b>\n\n👤 کاربر: <code>{user_id}</code>\n💵 مبلغ: {amount:,} تومان",
                reply_markup=None,
                parse_mode=ParseMode.HTML
            )
        else:
            await call.answer("⚠️ انبار این محصول خالی است! باید تحویل دستی انجام دهید.", show_alert=True)
            await ask_manual_delivery(call, bot, state, order_id, user_id, product_name)
    else:
        await ask_manual_delivery(call, bot, state, order_id, user_id, product_name)

async def ask_manual_delivery(call: CallbackQuery, bot: Bot, state: FSMContext, order_id: str, user_id: int, product_name: str):
    await state.update_data(
        order_id=order_id,
        user_id=user_id,
        product_name=product_name,
        admin_chat_id=call.message.chat.id,
        admin_msg_id=call.message.message_id
    )
    await state.set_state(AdminStates.manual_delivery_content)

    admin_id = call.from_user.id
    await bot.send_message(
        chat_id=admin_id,
        text=(
            f"✍️ <b>تحویل دستی سفارش <code>{order_id}</code></b>\n\n"
            f"👤 کاربر مقصد: <code>{user_id}</code>\n"
            f"📦 محصول خریداری شده: <b>{html.escape(product_name)}</b>\n\n"
            "لطفاً فایل، متن لایسنس، عکس یا مشخصات اکانت را جهت ارسال برای کاربر در پی‌وی بفرستید:"
        ),
        parse_mode=ParseMode.HTML
    )
    await call.answer("📝 دستورالعمل تحویل دستی به پی‌وی شما ارسال شد.", show_alert=True)

@admin_router.message(AdminStates.manual_delivery_content)
async def process_manual_delivery_content(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    order_id = data.get("order_id")
    user_id = data.get("user_id")
    product_name = data.get("product_name")
    admin_chat_id = data.get("admin_chat_id", message.chat.id)
    admin_msg_id = data.get("admin_msg_id")

    await db.update_order_status(order_id, "approved", message.text or "[محتوای مدیا]")
    await process_referral_reward(bot, db, order_id)

    user_notify_prefix = (
        f"✅ <b>پرداخت سفارش <code>{order_id}</code> شما تایید شد!</b>\n"
        f"🛍️ <b>محصول:</b> {html.escape(product_name)}\n"
        "📦 <b>محتوای ارسال شده توسط پشتیبانی:</b>\n\n"
    )

    try:
        if message.text:
            await bot.send_message(chat_id=user_id, text=user_notify_prefix + html.escape(message.text), parse_mode=ParseMode.HTML)
        elif message.photo:
            await bot.send_photo(chat_id=user_id, photo=message.photo[-1].file_id, caption=user_notify_prefix, parse_mode=ParseMode.HTML)
        elif message.document:
            await bot.send_document(chat_id=user_id, document=message.document.file_id, caption=user_notify_prefix, parse_mode=ParseMode.HTML)
        elif message.video:
            await bot.send_video(chat_id=user_id, video=message.video.file_id, caption=user_notify_prefix, parse_mode=ParseMode.HTML)

        await message.reply("✅ محصول با موفقیت به کاربر تحویل داده شد و لاگ تکمیل گردید.")

        user_info = await bot.get_chat(user_id)
        pv_link = f"https://t.me/{user_info.username}" if user_info.username else f"tg://user?id={user_id}"
        escaped_full_name = html.escape(user_info.full_name or "کاربر تلگرام")

        if admin_msg_id:
            await bot.edit_message_caption(
                chat_id=admin_chat_id,
                message_id=admin_msg_id,
                caption=(
                    f"🟢 <b>سفارش <code>{order_id}</code> به صورت دستی تحویل داده شد!</b>\n\n"
                    f"👤 کاربر: <a href='{pv_link}'>{escaped_full_name}</a>\n"
                    f"📦 محصول: {html.escape(product_name)}"
                ),
                reply_markup=None,
                parse_mode=ParseMode.HTML
            )
    except Exception as e:
        logger.error(f"Error in manual delivery: {e}")
        await message.reply(f"❌ خطا در ارسال محصول به کاربر: {e}")

    await state.clear()


# Reject payment receipt
@admin_router.callback_query(F.data.startswith("adm_reject_"))
async def adm_reject_order_cb(call: CallbackQuery, bot: Bot, state: FSMContext):
    order_id = call.data.split("_")[2]
    order = await db.get_order(order_id)
    if not order:
        await call.answer("❌ سفارش یافت نشد.", show_alert=True)
        return

    status = order[7]
    if status != 'pending':
        await call.answer(f"❌ این سفارش قبلاً پردازش شده است! وضعیت: {status}", show_alert=True)
        try:
            await call.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        return

    user_id = order[1]
    admin_id = call.from_user.id

    await state.update_data(
        order_id=order_id,
        user_id=user_id,
        admin_chat_id=call.message.chat.id,
        admin_msg_id=call.message.message_id
    )
    await state.set_state(AdminStates.rejecting_order_reason)

    await bot.send_message(
        chat_id=admin_id,
        text=(
            f"🔴 <b>رد کردن سفارش <code>{order_id}</code></b>\n\n"
            "لطفاً دلیل رد کردن این رسید پرداخت را ارسال کنید تا برای کاربر فرستاده شود:"
        ),
        parse_mode=ParseMode.HTML
    )
    await call.answer("📝 درخواست ثبت دلیل رد رسید به پی‌وی شما ارسال شد.", show_alert=True)

@admin_router.message(AdminStates.rejecting_order_reason)
async def process_reject_reason(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    order_id = data.get("order_id")
    user_id = data.get("user_id")
    admin_chat_id = data.get("admin_chat_id", message.chat.id)
    admin_msg_id = data.get("admin_msg_id")
    reason = message.text.strip()

    # Permanently delete the order from the database instead of marking it 'rejected'
    await db.delete_order(order_id)

    user_notify_text = (
        f"🔴 <b>رسید پرداخت سفارش <code>{order_id}</code> شما توسط مدیریت رد شد!</b>\n\n"
        f"❌ <b>علت رد شدن:</b> {html.escape(reason)}\n\n"
        "در صورت بروز اشتباه، مجدداً می‌توانید خرید جدید ثبت کنید یا با پشتیبانی ارتباط برقرار نمایید."
    )

    try:
        await bot.send_message(chat_id=user_id, text=user_notify_text, parse_mode=ParseMode.HTML)
        await message.reply("✅ سفارش رد شد و دلیل آن به کاربر ابلاغ گردید.")

        if admin_msg_id:
            await bot.edit_message_caption(
                chat_id=admin_chat_id,
                message_id=admin_msg_id,
                caption=(
                    f"🔴 <b>سفارش <code>{order_id}</code> رد و به طور کامل حذف شد!</b>\n\n"
                    f"👤 شناسه کاربر: <code>{user_id}</code>\n"
                    f"❌ علت رد شدن: {html.escape(reason)}"
                ),
                reply_markup=None,
                parse_mode=ParseMode.HTML
            )
    except Exception as e:
        logger.error(f"Error in rejecting order: {e}")
        await message.reply(f"❌ خطا در ابلاغ رد سفارش: {e}")

    await state.clear()
