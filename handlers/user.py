import uuid
import logging
import html
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ButtonStyle, ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from database.db import Database
from config.config import REQUIRED_CHANNEL, REQUIRED_CHANNEL_LINK, ADMIN_LOG_CHANNEL, CARD_NUMBER, CARD_HOLDER, ADMINS
from keyboards.inline import (
    get_main_keyboard,
    get_categories_keyboard,
    get_products_keyboard,
    get_product_details_keyboard,
    get_payment_methods_keyboard,
    get_card_payment_keyboard
)
from utils.zarinpal import ZarinPal

logger = logging.getLogger(__name__)
user_router = Router()
db = Database()

# FSM States
class UserStates(StatesGroup):
    entering_discount = State()
    waiting_for_receipt = State()
    entering_wallet_charge = State()
    entering_ticket = State()

# Immediate Visual Feedback helper
async def show_loading(call: CallbackQuery):
    try:
        await call.message.edit_text("⏳ در حال پردازش...", reply_markup=None)
    except Exception:
        pass

# Welcome Message in HTML
def get_welcome_text(full_name: str) -> str:
    escaped_name = html.escape(full_name)
    return (
        f"🌌 <b>سلام {escaped_name} عزیز! به فروشگاه مدرن ما خوش آمدید</b>\n\n"
        "✨ اینجا می‌توانید انواع اشتراک‌ها، لایسنس‌ها و فیلترشکن‌های باکیفیت را با بهترین قیمت تهیه کنید.\n\n"
        "💎 <b>رابط کاربری ربات تک‌صفحه‌ای است؛</b> با استفاده از دکمه‌های شیشه‌ای رنگارنگ زیر به راحتی و با سرعت بالا خرید خود را نهایی کنید! 👇"
    )

@user_router.message(F.text == "/start")
async def start_cmd(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    username = message.from_user.username or ""
    full_name = message.from_user.full_name or ""

    await db.add_user(user_id, username, full_name)

    await message.answer(
        get_welcome_text(full_name),
        reply_markup=get_main_keyboard(user_id),
        parse_mode=ParseMode.HTML
    )

@user_router.callback_query(F.data == "go_home")
async def go_home_cb(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await show_loading(call)
    user_id = call.from_user.id
    full_name = call.from_user.full_name or ""
    await call.message.edit_text(
        get_welcome_text(full_name),
        reply_markup=get_main_keyboard(user_id),
        parse_mode=ParseMode.HTML
    )

@user_router.callback_query(F.data == "check_membership")
async def check_membership_cb(call: CallbackQuery, bot: Bot):
    user_id = call.from_user.id
    try:
        member = await bot.get_chat_member(chat_id=REQUIRED_CHANNEL, user_id=user_id)
        if member.status not in ["kicked", "left"]:
            await call.answer("🟢 عضویت شما تایید شد! خوش آمدید.", show_alert=True)
            await call.message.edit_text(
                get_welcome_text(call.from_user.full_name),
                reply_markup=get_main_keyboard(user_id),
                parse_mode=ParseMode.HTML
            )
        else:
            await call.answer("❌ هنوز عضو کانال نشده‌اید!", show_alert=True)
    except Exception as e:
        logger.error(f"Error checking membership: {e}")
        await call.answer("⚠️ خطا در بررسی عضویت. لطفاً بعداً تلاش کنید.", show_alert=True)

@user_router.callback_query(F.data == "categories_list")
async def categories_list_cb(call: CallbackQuery):
    await show_loading(call)
    categories = await db.get_categories()
    if not categories:
        await call.message.edit_text(
            "⚠️ هنوز هیچ دسته‌بندی فعالی تعریف نشده است.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 بازگشت به خانه", callback_data="go_home", style=ButtonStyle.DANGER)]
            ])
        )
        return
    await call.message.edit_text(
        "🗂️ <b>دسته‌بندی مورد نظر خود را انتخاب کنید:</b>",
        reply_markup=get_categories_keyboard(categories, call.from_user.id),
        parse_mode=ParseMode.HTML
    )

@user_router.callback_query(F.data.startswith("cat_"))
async def category_products_cb(call: CallbackQuery):
    await show_loading(call)
    category_id = int(call.data.split("_")[1])
    products = await db.get_products_by_category(category_id)
    if not products:
        await call.message.edit_text(
            "⚠️ در این دسته‌بندی هنوز محصولی ثبت نشده است.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 بازگشت به دسته‌بندی‌ها", callback_data="categories_list", style=ButtonStyle.DANGER)]
            ])
        )
        return
    await call.message.edit_text(
        "🛒 <b>محصولات موجود در این بخش:</b>",
        reply_markup=get_products_keyboard(products, category_id),
        parse_mode=ParseMode.HTML
    )

@user_router.callback_query(F.data.startswith("prod_"))
async def product_details_cb(call: CallbackQuery):
    await show_loading(call)
    product_id = int(call.data.split("_")[1])
    product = await db.get_product(product_id)
    if not product:
        await call.message.edit_text("❌ محصول یافت نشد.")
        return

    prod_id, category_id, name, description, price, auto_deliver = product
    price_formatted = f"{price:,}"
    delivery_type = "⚡ تحویل خودکار و آنی (بلافاصله بعد تایید)" if auto_deliver else "✍️ تحویل دستی توسط پشتیبانی"

    escaped_name = html.escape(name)
    escaped_desc = html.escape(description) if description else 'توضیحی ثبت نشده است.'

    desc_text = (
        f"🛍️ <b>نام محصول:</b> {escaped_name}\n\n"
        f"📝 <b>توضیحات:</b>\n{escaped_desc}\n\n"
        f"💵 <b>قیمت:</b> {price_formatted} تومان\n"
        f"⚙️ <b>نوع تحویل:</b> {delivery_type}\n\n"
        "آیا قصد خرید این محصول را دارید؟"
    )
    await call.message.edit_text(
        desc_text,
        reply_markup=get_product_details_keyboard(prod_id, category_id),
        parse_mode=ParseMode.HTML
    )

@user_router.callback_query(F.data.startswith("buy_"))
async def initiate_buy_cb(call: CallbackQuery):
    await show_loading(call)
    product_id = int(call.data.split("_")[1])
    product = await db.get_product(product_id)
    if not product:
        await call.message.edit_text("❌ محصول یافت نشد.")
        return

    prod_id, category_id, name, description, price, auto_deliver = product
    order_id = str(uuid.uuid4())[:8]

    await db.create_order(order_id, call.from_user.id, product_id, price, payment_method="card")

    user_balance = await db.get_balance(call.from_user.id)
    allow_wallet = (user_balance >= price)

    price_formatted = f"{price:,}"
    escaped_name = html.escape(name)
    checkout_text = (
        f"💳 <b>پیش‌فاکتور خرید شما</b>\n\n"
        f"📦 <b>محصول:</b> {escaped_name}\n"
        f"🆔 <b>کد پیگیری سفارش:</b> <code>{order_id}</code>\n"
        f"💵 <b>مبلغ قابل پرداخت:</b> {price_formatted} تومان\n"
        f"👛 <b>موجودی کیف پول شما:</b> {user_balance:,} تومان\n\n"
        "لطفاً روش پرداخت خود را انتخاب کنید 👇"
    )
    await call.message.edit_text(
        checkout_text,
        reply_markup=get_payment_methods_keyboard(order_id, product_id, allow_wallet=allow_wallet),
        parse_mode=ParseMode.HTML
    )

# --- Direct Wallet Payment ---
@user_router.callback_query(F.data.startswith("pay_wallet_"))
async def pay_wallet_cb(call: CallbackQuery, bot: Bot):
    await show_loading(call)
    order_id = call.data.split("pay_wallet_")[1]
    order = await db.get_order(order_id)
    if not order:
        await call.message.edit_text("❌ سفارش یافت نشد.")
        return

    user_id = call.from_user.id
    price = order[3]
    product_id = order[2]
    product_name = order[10]

    escaped_prod_name = html.escape(product_name)

    success = await db.deduct_balance(user_id, price)
    if success:
        product = await db.get_product(product_id)
        auto_deliver = product[5] if product else 0

        if auto_deliver:
            content = await db.pop_inventory_item(product_id)
            if content:
                await db.update_order_status(order_id, "approved", content)

                escaped_content = html.escape(content)
                user_text = (
                    f"🎉 <b>پرداخت موفقیت‌آمیز با کیف پول!</b>\n\n"
                    f"🛍️ <b>محصول:</b> {escaped_prod_name}\n"
                    f"⚡ <b>محتوای لایسنس / اشتراک شما:</b>\n\n"
                    f"<code>{escaped_content}</code>\n\n"
                    "امیدواریم از کیفیت خرید خود نهایت رضایت را داشته باشید!"
                )
                await call.message.edit_text(
                    user_text,
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🔙 بازگشت به خانه", callback_data="go_home", style=ButtonStyle.PRIMARY)]
                    ]),
                    parse_mode=ParseMode.HTML
                )

                admin_text = (
                    f"🟢 <b>خرید موفق با موجودی کیف پول و تحویل خودکار!</b>\n\n"
                    f"👤 کاربر: <code>{user_id}</code>\n"
                    f"📦 محصول: {escaped_prod_name}\n"
                    f"💵 مبلغ: {price:,} تومان\n"
                    f"🆔 کد پیگیری سفارش: <code>{order_id}</code>"
                )
                try:
                    await bot.send_message(chat_id=ADMIN_LOG_CHANNEL, text=admin_text, parse_mode=ParseMode.HTML)
                except Exception as e_log:
                    logger.warning(f"Failed to post to admin log channel: {e_log}")
                    if ADMINS:
                        try:
                            await bot.send_message(chat_id=ADMINS[0], text=admin_text, parse_mode=ParseMode.HTML)
                        except Exception:
                            pass
            else:
                await db.update_order_status(order_id, "approved")
                user_text = (
                    f"🎉 <b>پرداخت موفقیت‌آمیز با کیف پول!</b>\n\n"
                    f"🛍️ <b>محصول:</b> {escaped_prod_name}\n"
                    "✍️ به دلیل اتمام موقتی موجودی انبار، لایسنس شما به زودی توسط مدیریت به صورت دستی تحویل می‌گردد."
                )
                await call.message.edit_text(
                    user_text,
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🔙 بازگشت به خانه", callback_data="go_home", style=ButtonStyle.PRIMARY)]
                    ]),
                    parse_mode=ParseMode.HTML
                )

                admin_text = (
                    f"⚠️ <b>خرید موفق با کیف پول اما انبار خالی است!</b>\n\n"
                    f"👤 کاربر: <code>{user_id}</code>\n"
                    f"📦 محصول: {escaped_prod_name}\n"
                    f"💵 مبلغ: {price:,} تومان\n"
                    f"🆔 کد پیگیری سفارش: <code>{order_id}</code>\n\n"
                    "لطفاً محصول را به صورت دستی تحویل دهید."
                )
                try:
                    await bot.send_message(chat_id=ADMIN_LOG_CHANNEL, text=admin_text, parse_mode=ParseMode.HTML)
                except Exception:
                    if ADMINS:
                        try:
                            await bot.send_message(chat_id=ADMINS[0], text=admin_text, parse_mode=ParseMode.HTML)
                        except Exception:
                            pass
        else:
            await db.update_order_status(order_id, "approved")
            user_text = (
                f"🎉 <b>پرداخت موفقیت‌آمیز با کیف پول!</b>\n\n"
                f"🛍️ <b>محصول:</b> {escaped_prod_name}\n"
                "✍️ محصول شما ثبت گردید و به زودی توسط پشتیبانان ارسال خواهد شد."
            )
            await call.message.edit_text(
                user_text,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 بازگشت به خانه", callback_data="go_home", style=ButtonStyle.PRIMARY)]
                ]),
                parse_mode=ParseMode.HTML
            )

            admin_text = (
                f"📥 <b>سفارش جدید پرداخت شده با کیف پول (تحویل دستی)</b>\n\n"
                f"👤 کاربر: <code>{user_id}</code>\n"
                f"📦 محصول: {escaped_prod_name}\n"
                f"💵 مبلغ: {price:,} تومان\n"
                f"🆔 کد پیگیری سفارش: <code>{order_id}</code>\n\n"
                "لطفاً محصول را آماده کرده و تحویل دهید."
            )
            try:
                await bot.send_message(chat_id=ADMIN_LOG_CHANNEL, text=admin_text, parse_mode=ParseMode.HTML)
            except Exception:
                if ADMINS:
                    try:
                        await bot.send_message(chat_id=ADMINS[0], text=admin_text, parse_mode=ParseMode.HTML)
                    except Exception:
                        pass
    else:
        await call.answer("❌ موجودی کیف پول شما کافی نیست!", show_alert=True)

# Apply Discount Code Handler
@user_router.callback_query(F.data.startswith("apply_discount_"))
async def apply_discount_prompt_cb(call: CallbackQuery, state: FSMContext):
    order_id = call.data.split("apply_discount_")[1]
    await state.update_data(order_id=order_id, message_id=call.message.message_id)
    await state.set_state(UserStates.entering_discount)

    await call.message.edit_text(
        "🎟️ <b>لطفاً کد تخفیف خود را تایپ و ارسال کنید:</b>\n\n"
        "<i>(پس از ارسال پیام متنی، پیام شما پاک شده و همین منو آپدیت می‌شود)</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 انصراف", callback_data=f"back_to_pay_{order_id}", style=ButtonStyle.DANGER)]
        ]),
        parse_mode=ParseMode.HTML
    )

@user_router.message(UserStates.entering_discount)
async def process_discount_msg(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    order_id = data.get("order_id")
    menu_message_id = data.get("message_id")
    discount_code = message.text.strip()

    try:
        await message.delete()
    except Exception:
        pass

    order = await db.get_order(order_id)
    if not order:
        await state.clear()
        return

    percent = await db.use_discount_code(message.from_user.id, discount_code)
    escaped_prod_name = html.escape(order[10])
    if percent is not None:
        original_price = order[3]
        discount_amount = int(original_price * (percent / 100))
        new_price = original_price - discount_amount

        async with db._lock:
            await db.conn.execute("UPDATE orders SET amount = ?, discount_code = ? WHERE id = ?", (new_price, discount_code, order_id))
            await db.conn.commit()

        user_balance = await db.get_balance(message.from_user.id)
        allow_wallet = (user_balance >= new_price)

        success_text = (
            f"🎉 <b>کد تخفیف با موفقیت اعمال شد! ({percent}% تخفیف)</b>\n\n"
            f"📦 <b>محصول:</b> {escaped_prod_name}\n"
            f"💵 <b>مبلغ قبلی:</b> {original_price:,} تومان\n"
            f"🔥 <b>مبلغ جدید قابل پرداخت:</b> {new_price:,} تومان\n"
            f"🆔 <b>کد پیگیری سفارش:</b> <code>{order_id}</code>\n\n"
            "لطفاً روش پرداخت خود را انتخاب کنید 👇"
        )
        await state.clear()
        await bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=menu_message_id,
            text=success_text,
            reply_markup=get_payment_methods_keyboard(order_id, order[2], allow_wallet=allow_wallet),
            parse_mode=ParseMode.HTML
        )
    else:
        user_balance = await db.get_balance(message.from_user.id)
        allow_wallet = (user_balance >= order[3])

        fail_text = (
            f"❌ <b>کد تخفیف وارد شده نامعتبر، منقضی شده یا قبلاً استفاده شده است!</b>\n\n"
            f"📦 <b>محصول:</b> {escaped_prod_name}\n"
            f"💵 <b>مبلغ قابل پرداخت:</b> {order[3]:,} تومان\n"
            f"👛 <b>موجودی کیف پول شما:</b> {user_balance:,} تومان\n"
            f"🆔 <b>کد پیگیری سفارش:</b> <code>{order_id}</code>\n\n"
            "لطفاً روش پرداخت خود را انتخاب کنید 👇"
        )
        await state.clear()
        await bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=menu_message_id,
            text=fail_text,
            reply_markup=get_payment_methods_keyboard(order_id, order[2], allow_wallet=allow_wallet),
            parse_mode=ParseMode.HTML
        )

@user_router.callback_query(F.data.startswith("back_to_pay_"))
async def back_to_pay_cb(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await show_loading(call)
    order_id = call.data.split("back_to_pay_")[1]
    order = await db.get_order(order_id)
    if not order:
        await call.message.edit_text("❌ سفارش یافت نشد.")
        return

    user_balance = await db.get_balance(call.from_user.id)
    allow_wallet = (user_balance >= order[3])

    escaped_prod_name = html.escape(order[10])
    checkout_text = (
        f"💳 <b>پیش‌فاکتور خرید شما</b>\n\n"
        f"📦 <b>محصول:</b> {escaped_prod_name}\n"
        f"🆔 <b>کد پیگیری سفارش:</b> <code>{order_id}</code>\n"
        f"💵 <b>مبلغ قابل پرداخت:</b> {order[3]:,} تومان\n"
        f"👛 <b>موجودی کیف پول شما:</b> {user_balance:,} تومان\n\n"
        "لطفاً روش پرداخت خود را انتخاب کنید 👇"
    )
    await call.message.edit_text(
        checkout_text,
        reply_markup=get_payment_methods_keyboard(order_id, order[2], allow_wallet=allow_wallet),
        parse_mode=ParseMode.HTML
    )

# --- Online ZarinPal Payment Handler ---
@user_router.callback_query(F.data.startswith("pay_zarinpal_"))
async def pay_zarinpal_cb(call: CallbackQuery):
    await show_loading(call)
    order_id = call.data.split("pay_zarinpal_")[1]
    order = await db.get_order(order_id)
    if not order:
        await call.message.edit_text("❌ سفارش یافت نشد.")
        return

    amount_toman = order[3]
    product_name = order[10] if order[10] else "شارژ کیف پول"
    escaped_prod_name = html.escape(product_name)

    zp = ZarinPal()
    success, result = await zp.request_payment(
        amount_toman=amount_toman,
        description=f"خرید {product_name} - سفارش {order_id}",
        order_id=order_id
    )

    if success:
        async with db._lock:
            await db.conn.execute("UPDATE orders SET payment_method = 'zarinpal' WHERE id = ?", (order_id,))
            await db.conn.commit()

        zp_text = (
            f"🔗 <b>لینک پرداخت آنلاین زرین‌پال ایجاد شد!</b>\n\n"
            f"📦 <b>محصول:</b> {escaped_prod_name}\n"
            f"💵 <b>مبلغ قابل پرداخت:</b> {amount_toman:,} تومان\n\n"
            "جهت پرداخت روی دکمه زیر کلیک کنید. پس از پرداخت موفق، اشتراک یا شارژ شما فعال می‌شود."
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 ورود به درگاه پرداخت", url=result)],
            [InlineKeyboardButton(text="🔙 بازگشت به پیش‌فاکتور", callback_data=f"back_to_pay_{order_id}", style=ButtonStyle.DANGER)]
        ])
        await call.message.edit_text(zp_text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    else:
        await call.message.edit_text(
            f"❌ <b>خطا در اتصال به درگاه پرداخت:</b>\n<code>{html.escape(result)}</code>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 بازگشت و تلاش مجدد", callback_data=f"back_to_pay_{order_id}", style=ButtonStyle.DANGER)]
            ]),
            parse_mode=ParseMode.HTML
        )

# --- Card-to-Card Payment Handler ---
@user_router.callback_query(F.data.startswith("pay_card_"))
async def pay_card_cb(call: CallbackQuery):
    await show_loading(call)
    order_id = call.data.split("pay_card_")[1]
    order = await db.get_order(order_id)
    if not order:
        await call.message.edit_text("❌ سفارش یافت نشد.")
        return

    amount_toman = order[3]
    card_text = (
        f"💳 <b>روش کارت به کارت (آپلود رسید)</b>\n\n"
        f"لطفاً مبلغ <b>{amount_toman:,} تومان</b> را به شماره کارت زیر واریز کنید:\n\n"
        f"💳 شماره کارت:\n<code>{CARD_NUMBER}</code>\n"
        f"👤 به نام: <b>{CARD_HOLDER}</b>\n\n"
        f"سپس روی دکمه زیر کلیک کنید تا رسید خود را آپلود نمایید 👇"
    )
    await call.message.edit_text(card_text, reply_markup=get_card_payment_keyboard(order_id), parse_mode=ParseMode.HTML)

@user_router.callback_query(F.data.startswith("upload_receipt_"))
async def upload_receipt_prompt_cb(call: CallbackQuery, state: FSMContext):
    order_id = call.data.split("upload_receipt_")[1]
    await state.update_data(order_id=order_id, message_id=call.message.message_id)
    await state.set_state(UserStates.waiting_for_receipt)

    await call.message.edit_text(
        "📸 <b>لطفاً تصویر فیش واریزی خود را ارسال کنید:</b>\n\n"
        "<i>(به محض ارسال عکس رسید، پیام ارسالی شما برای تمیز ماندن چت پاک شده و ربات آپدیت می‌شود)</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 انصراف", callback_data=f"pay_card_{order_id}", style=ButtonStyle.DANGER)]
        ]),
        parse_mode=ParseMode.HTML
    )

@user_router.message(UserStates.waiting_for_receipt, F.photo)
async def process_receipt_photo(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    order_id = data.get("order_id")
    menu_message_id = data.get("message_id")

    file_id = message.photo[-1].file_id

    try:
        await message.delete()
    except Exception:
        pass

    await state.clear()

    async with db._lock:
        await db.conn.execute(
            "UPDATE orders SET receipt_file_id = ?, payment_method = 'card', status = 'pending' WHERE id = ?",
            (file_id, order_id)
        )
        await db.conn.commit()

    order = await db.get_order(order_id)
    prod_name = order[10] if order[10] else "شارژ کیف پول"
    escaped_prod_name = html.escape(prod_name)

    success_text = (
        "⏳ <b>رسید پرداخت شما با موفقیت دریافت شد!</b>\n\n"
        "✅ وضعیت: <b>در حال بررسی رسید پرداخت توسط مدیریت...</b>\n"
        f"🆔 کد پیگیری سفارش: <code>{order_id}</code>\n\n"
        "به محض تایید یا رد پرداخت توسط مدیریت، از طریق ربات به شما اطلاع‌رسانی خواهد شد. سپاس از صبوری شما 🙏"
    )
    await bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=menu_message_id,
        text=success_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 بازگشت به خانه", callback_data="go_home", style=ButtonStyle.PRIMARY)]
        ]),
        parse_mode=ParseMode.HTML
    )

    # HTML Escaping user entries to prevent Telegram entity parsing errors completely!
    user_fullname = html.escape(message.from_user.full_name or "کاربر تلگرام")
    username_str = f"@{html.escape(message.from_user.username)}" if message.from_user.username else "بدون یوزرنیم"

    admin_notify_text = (
        f"📥 <b>رسید پرداخت جدید ثبت شد!</b>\n\n"
        f"👤 <b>کاربر:</b> {user_fullname} ({username_str})\n"
        f"🆔 <b>شناسه کاربری:</b> <code>{message.from_user.id}</code>\n"
        f"📦 <b>محصول:</b> {escaped_prod_name}\n"
        f"💵 <b>مبلغ پرداختی:</b> {order[3]:,} تومان\n"
        f"🆔 <b>کد پیگیری:</b> <code>{order_id}</code>\n"
        f"💳 <b>روش پرداخت:</b> کارت به کارت\n\n"
        "لطفاً با زدن دکمه‌های زیر، رسید را تایید یا رد کنید 👇"
    )

    admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🟢 تایید رسید و تحویل", callback_data=f"adm_approve_{order_id}", style=ButtonStyle.SUCCESS),
            InlineKeyboardButton(text="🔴 رد رسید", callback_data=f"adm_reject_{order_id}", style=ButtonStyle.DANGER)
        ]
    ])

    sent_successfully = False
    try:
        await bot.send_photo(
            chat_id=ADMIN_LOG_CHANNEL,
            photo=file_id,
            caption=admin_notify_text,
            reply_markup=admin_keyboard,
            parse_mode=ParseMode.HTML
        )
        sent_successfully = True
    except Exception as e_channel:
        logger.error(f"Failed to post to dedicated admin log channel {ADMIN_LOG_CHANNEL}: {e_channel}")

    if not sent_successfully:
        if ADMINS:
            try:
                fallback_text = (
                    admin_notify_text +
                    "\n\n⚠️ <b>توجه سیستم: ارسال به کانال لاگ با خطا مواجه شد و این رسید به عنوان پشتیبان به پی‌وی شما فرستاده شد.</b>"
                )
                await bot.send_photo(
                    chat_id=ADMINS[0],
                    photo=file_id,
                    caption=fallback_text,
                    reply_markup=admin_keyboard,
                    parse_mode=ParseMode.HTML
                )
                logger.info(f"Fallback successful: delivered receipt {order_id} directly to main admin {ADMINS[0]}")
            except Exception as e_admin:
                logger.error(f"Failed fallback delivery of receipt {order_id} to main admin {ADMINS[0]} PV: {e_admin}")

@user_router.callback_query(F.data.startswith("cancel_order_"))
async def cancel_order_cb(call: CallbackQuery):
    await show_loading(call)
    order_id = call.data.split("cancel_order_")[1]
    async with db._lock:
        await db.conn.execute("DELETE FROM orders WHERE id = ?", (order_id,))
        await db.conn.commit()
    await call.message.edit_text(
        "❌ <b>سفارش شما لغو شد.</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 بازگشت به خانه", callback_data="go_home", style=ButtonStyle.PRIMARY)]
        ]),
        parse_mode=ParseMode.HTML
    )

# --- Profile, Orders and Support Info ---
@user_router.callback_query(F.data == "user_profile")
async def user_profile_cb(call: CallbackQuery):
    await show_loading(call)
    user_id = call.from_user.id
    user = await db.get_user(user_id)
    if not user:
        await call.message.edit_text("❌ حساب کاربری شما یافت نشد.")
        return

    joined_at = user[3]
    expiry = user[4] or "🔴 غیرفعال / بدون اشتراک"
    balance = user[5]

    profile_text = (
        f"👤 <b>پروفایل کاربری شما</b>\n\n"
        f"🆔 شناسه عددی شما: <code>{user_id}</code>\n"
        f"👛 موجودی کیف پول: <b>{balance:,} تومان</b>\n"
        f"🗓️ تاریخ عضویت: {joined_at}\n"
        f"⌛ وضعیت اشتراک فعال: <b>{expiry}</b>\n\n"
        "می‌توانید سفارشات قبلی خود را از دکمه زیر بررسی کنید 👇"
    )
    await call.message.edit_text(
        profile_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📥 سفارشات من", callback_data="my_orders", style=ButtonStyle.PRIMARY)],
            [InlineKeyboardButton(text="🔙 بازگشت به منوی اصلی", callback_data="go_home", style=ButtonStyle.DANGER)]
        ]),
        parse_mode=ParseMode.HTML
    )

@user_router.callback_query(F.data == "my_orders")
async def my_orders_cb(call: CallbackQuery):
    await show_loading(call)
    orders = await db.get_user_orders(call.from_user.id)
    if not orders:
        await call.message.edit_text(
            "📭 شما هنوز هیچ سفارشی ثبت نکرده‌اید.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 بازگشت به خانه", callback_data="go_home", style=ButtonStyle.DANGER)]
            ])
        )
        return

    orders_text = "📥 <b>سفارشات اخیر شما:</b>\n\n"
    for ord_id, prod_name, amount, status, created_at in orders[:5]:
        status_emoji = "🟡 در انتظار" if status == "pending" else ("🟢 تایید شده" if status == "approved" else "🔴 رد شده")
        orders_text += (
            f"🔹 <b>سفارش:</b> <code>{ord_id}</code> | <b>محصول:</b> {html.escape(prod_name)}\n"
            f"💵 مبلغ: {amount:,} تومان | وضعیت: {status_emoji}\n"
            f"🗓️ تاریخ: {created_at}\n\n"
        )

    await call.message.edit_text(
        orders_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 بازگشت به خانه", callback_data="go_home", style=ButtonStyle.DANGER)]
        ]),
        parse_mode=ParseMode.HTML
    )

@user_router.callback_query(F.data == "support_info")
async def support_info_cb(call: CallbackQuery):
    await show_loading(call)
    support_text = (
        "📞 <b>پشتیبانی و ثبت تیکت</b>\n\n"
        "همکاران ما به صورت ۲۴ ساعته پاسخگوی شما خواهند بود. علاوه بر پی‌وی، می‌توانید تیکت خود را مستقیماً از داخل ربات ثبت کنید تا مدیریت به آن پاسخ دهد.\n\n"
        "💬 ایدی پشتیبانی اصلی: @support_user\n\n"
        "جهت ارسال تیکت مستقیم روی دکمه زیر کلیک کنید 👇"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎫 ثبت تیکت جدید", callback_data="submit_new_ticket", style=ButtonStyle.SUCCESS)],
        [InlineKeyboardButton(text="🔙 بازگشت به منوی اصلی", callback_data="go_home", style=ButtonStyle.DANGER)]
    ])
    await call.message.edit_text(support_text, reply_markup=keyboard, parse_mode=ParseMode.HTML)

# Submit Support Ticket
@user_router.callback_query(F.data == "submit_new_ticket")
async def submit_new_ticket_cb(call: CallbackQuery, state: FSMContext):
    await state.update_data(message_id=call.message.message_id)
    await state.set_state(UserStates.entering_ticket)
    await call.message.edit_text(
        "📝 <b>لطفاً پیام تیکت خود را ارسال کنید:</b>\n\n"
        "توضیحات مشکل یا سوال خود را بنویسید. به محض ارسال، پیام شما برای تمیز ماندن چت حذف می‌شود.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 انصراف", callback_data="support_info", style=ButtonStyle.DANGER)]
        ]),
        parse_mode=ParseMode.HTML
    )

@user_router.message(UserStates.entering_ticket)
async def process_ticket_message(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    menu_message_id = data.get("message_id")
    ticket_msg = message.text.strip()

    try:
        await message.delete()
    except Exception:
        pass

    await state.clear()

    ticket_id = await db.create_ticket(message.from_user.id, ticket_msg)

    user_fullname = html.escape(message.from_user.full_name or "کاربر تلگرام")
    username_str = f"@{html.escape(message.from_user.username)}" if message.from_user.username else "بدون یوزرنیم"
    escaped_ticket_msg = html.escape(ticket_msg)

    admin_alert = (
        f"🎫 <b>تیکت پشتیبانی جدید دریافت شد!</b>\n\n"
        f"👤 <b>کاربر:</b> {user_fullname} ({username_str})\n"
        f"🆔 <b>شناسه کاربر:</b> <code>{message.from_user.id}</code>\n"
        f"🆔 <b>شناسه تیکت:</b> <code>{ticket_id}</code>\n\n"
        f"📝 <b>متن تیکت:</b>\n<code>{escaped_ticket_msg}</code>\n\n"
        "جهت پاسخ دادن به تیکت، از بخش «مدیریت تیکت‌ها» در پنل مدیریت ربات اقدام کنید."
    )

    sent_successfully = False
    try:
        await bot.send_message(chat_id=ADMIN_LOG_CHANNEL, text=admin_alert, parse_mode=ParseMode.HTML)
        sent_successfully = True
    except Exception as e_chan:
        logger.error(f"Failed to post support ticket to channel {ADMIN_LOG_CHANNEL}: {e_chan}")

    if not sent_successfully:
        if ADMINS:
            try:
                fallback_alert = (
                    admin_alert +
                    "\n\n⚠️ <b>توجه سیستم: ارسال به کانال لاگ با خطا مواجه شد و این تیکت به صورت مستقیم به پی‌وی شما فوروارد شد.</b>"
                )
                await bot.send_message(chat_id=ADMINS[0], text=fallback_alert, parse_mode=ParseMode.HTML)
                logger.info(f"Fallback successful: delivered ticket {ticket_id} directly to main admin {ADMINS[0]}")
            except Exception as e_pv:
                logger.error(f"Failed fallback delivery of ticket {ticket_id} to main admin {ADMINS[0]}: {e_pv}")

    success_text = (
        f"✅ <b>تیکت شما با شناسه <code>{ticket_id}</code> با موفقیت ثبت شد.</b>\n\n"
        "پاسخ پشتیبانی به زودی از طریق ربات به شما ابلاغ خواهد شد. با تشکر."
    )
    await bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=menu_message_id,
        text=success_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 بازگشت به خانه", callback_data="go_home", style=ButtonStyle.PRIMARY)]
        ]),
        parse_mode=ParseMode.HTML
    )

# --- User Wallet Management ---
@user_router.callback_query(F.data == "my_wallet")
async def my_wallet_cb(call: CallbackQuery):
    await show_loading(call)
    user_id = call.from_user.id
    balance = await db.get_balance(user_id)

    wallet_text = (
        f"👛 <b>کیف پول دیجیتال شما</b>\n\n"
        f"💵 موجودی فعلی: <b>{balance:,} تومان</b>\n\n"
        "با شارژ کیف پول خود، می‌توانید به صورت آنی و بدون فوت وقت تمامی محصولات را بدون معطلی بررسی فیش خریداری کنید!"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔋 شارژ کیف پول", callback_data="charge_wallet_prompt", style=ButtonStyle.SUCCESS)],
        [InlineKeyboardButton(text="🔙 بازگشت به منوی اصلی", callback_data="go_home", style=ButtonStyle.DANGER)]
    ])
    await call.message.edit_text(wallet_text, reply_markup=keyboard, parse_mode=ParseMode.HTML)

@user_router.callback_query(F.data == "charge_wallet_prompt")
async def charge_wallet_prompt_cb(call: CallbackQuery, state: FSMContext):
    await state.update_data(message_id=call.message.message_id)
    await state.set_state(UserStates.entering_wallet_charge)
    await call.message.edit_text(
        "🔋 <b>شارژ کیف پول</b>\n\n"
        "لطفاً <b>مبلغ مورد نظر برای شارژ (به تومان و عدد خام)</b> را ارسال کنید:\n"
        "مثال: 50000\n\n"
        "<i>(به محض ارسال پیام، پیام شما پاک شده و صفحه آپدیت می‌گردد)</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 انصراف", callback_data="my_wallet", style=ButtonStyle.DANGER)]
        ]),
        parse_mode=ParseMode.HTML
    )

@user_router.message(UserStates.entering_wallet_charge)
async def process_wallet_charge_msg(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    menu_message_id = data.get("message_id")
    amount_str = message.text.strip()

    try:
        await message.delete()
    except Exception:
        pass

    if not amount_str.isdigit() or int(amount_str) <= 0:
        await bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=menu_message_id,
            text="⚠️ <b>مبلغ وارد شده معتبر نیست!</b>\nلطفاً فقط عدد خام بزرگتر از صفر وارد کنید:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 انصراف", callback_data="my_wallet", style=ButtonStyle.DANGER)]
            ]),
            parse_mode=ParseMode.HTML
        )
        return

    await state.clear()
    charge_amount = int(amount_str)
    order_id = str(uuid.uuid4())[:8]

    await db.create_order(order_id, message.from_user.id, None, charge_amount, payment_method="card")

    checkout_text = (
        f"🔋 <b>پیش‌فاکتور شارژ کیف پول</b>\n\n"
        f"💵 <b>مبلغ افزایش اعتبار:</b> {charge_amount:,} تومان\n"
        f"🆔 <b>کد پیگیری سفارش:</b> <code>{order_id}</code>\n\n"
        "روش پرداخت را برای شارژ انتخاب کنید 👇"
    )
    await bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=menu_message_id,
        text=checkout_text,
        reply_markup=get_payment_methods_keyboard(order_id, 0, allow_wallet=False),
        parse_mode=ParseMode.HTML
    )

# --- Free Test Accounts Handler ---
@user_router.callback_query(F.data == "free_test_account")
async def free_test_account_cb(call: CallbackQuery):
    await show_loading(call)
    user_id = call.from_user.id

    result = await db.pop_test_account(user_id)
    if result == "ALREADY_USED":
        await call.message.edit_text(
            "⚠️ <b>شما قبلاً یک بار هدیه اکانت تست رایگان خود را دریافت کرده‌اید!</b>\n\n"
            "تست رایگان برای هر کاربر فقط یک بار مجاز است. جهت دریافت اشتراک دائمی، لطفاً محصولات را بررسی کنید.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🛍️ دسته‌ب بندی محصولات", callback_data="categories_list", style=ButtonStyle.PRIMARY)],
                [InlineKeyboardButton(text="🔙 بازگشت به خانه", callback_data="go_home", style=ButtonStyle.DANGER)]
            ]),
            parse_mode=ParseMode.HTML
        )
    elif result is None:
        await call.message.edit_text(
            "💔 <b>متأسفانه موجودی اکانت‌های تست رایگان موقتاً به اتمام رسیده است!</b>\n\n"
            "به زودی انبار اکانت‌های تست توسط ادمین شارژ خواهد شد. لطفاً بعداً مجدداً بررسی کنید.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 بازگشت به خانه", callback_data="go_home", style=ButtonStyle.DANGER)]
            ]),
            parse_mode=ParseMode.HTML
        )
    else:
        escaped_result = html.escape(result)
        await call.message.edit_text(
            f"🎁 <b>تبریک! اکانت تست رایگان شما آماده شد:</b>\n\n"
            f"<code>{escaped_result}</code>\n\n"
            "امیدواریم از کیفیت اشتراک ما راضی باشید! جهت تمدید یا خرید اشتراک‌های پرسرعت‌تر، از منوی دسته‌بندی محصولات استفاده کنید.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🛍️ خرید اشتراک‌های پرسرعت", callback_data="categories_list", style=ButtonStyle.SUCCESS)],
                [InlineKeyboardButton(text="🔙 بازگشت به خانه", callback_data="go_home", style=ButtonStyle.DANGER)]
            ]),
            parse_mode=ParseMode.HTML
        )
