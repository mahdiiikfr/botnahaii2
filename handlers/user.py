import uuid
import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ButtonStyle, ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from database.db import Database
from config.config import REQUIRED_CHANNEL, REQUIRED_CHANNEL_LINK, ADMIN_LOG_CHANNEL, CARD_NUMBER, CARD_HOLDER
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

# Immediate Visual Feedback helper
async def show_loading(call: CallbackQuery):
    try:
        await call.message.edit_text("⏳ در حال پردازش...", reply_markup=None)
    except Exception:
        pass

# Welcome Message
def get_welcome_text(full_name: str) -> str:
    return (
        f"🌌 **سلام {full_name} عزیز! به فروشگاه مدرن ما خوش آمدید**\n\n"
        "✨ اینجا می‌توانید انواع اشتراک‌ها، لایسنس‌ها و فیلترشکن‌های باکیفیت را با بهترین قیمت تهیه کنید.\n\n"
        "💎 **رابط کاربری ربات تک‌صفحه‌ای است؛** با استفاده از دکمه‌های شیشه‌ای رنگارنگ زیر به راحتی و با سرعت بالا خرید خود را نهایی کنید! 👇"
    )

@user_router.message(F.text == "/start")
async def start_cmd(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    username = message.from_user.username or ""
    full_name = message.from_user.full_name or ""

    await db.add_user(user_id, username, full_name)

    # Send welcome message (we don't delete /start message, but future operations will use edits)
    await message.answer(
        get_welcome_text(full_name),
        reply_markup=get_main_keyboard(user_id),
        parse_mode=ParseMode.MARKDOWN
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
        parse_mode=ParseMode.MARKDOWN
    )

@user_router.callback_query(F.data == "check_membership")
async def check_membership_cb(call: CallbackQuery, bot: Bot):
    user_id = call.from_user.id
    try:
        member = await bot.get_chat_member(chat_id=REQUIRED_CHANNEL, user_id=user_id)
        if member.status not in ["kicked", "left"]:
            await call.answer("🟢 عضویت شما تایید شد! خوش آمدید.", show_alert=True)
            # Send home page
            await call.message.edit_text(
                get_welcome_text(call.from_user.full_name),
                reply_markup=get_main_keyboard(user_id),
                parse_mode=ParseMode.MARKDOWN
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
        "🗂️ **دسته‌بندی مورد نظر خود را انتخاب کنید:**",
        reply_markup=get_categories_keyboard(categories, call.from_user.id),
        parse_mode=ParseMode.MARKDOWN
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
        "🛒 **محصولات موجود در این بخش:**",
        reply_markup=get_products_keyboard(products, category_id),
        parse_mode=ParseMode.MARKDOWN
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

    desc_text = (
        f"🛍️ **نام محصول:** {name}\n\n"
        f"📝 **توضیحات:**\n{description or 'توضیحی ثبت نشده است.'}\n\n"
        f"💵 **قیمت:** {price_formatted} تومان\n"
        f"⚙️ **نوع تحویل:** {delivery_type}\n\n"
        "آیا قصد خرید این محصول را دارید؟"
    )
    await call.message.edit_text(
        desc_text,
        reply_markup=get_product_details_keyboard(prod_id, category_id),
        parse_mode=ParseMode.MARKDOWN
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
    order_id = str(uuid.uuid4())[:8] # Unique short order id

    # Store dynamic order in sqlite
    await db.create_order(order_id, call.from_user.id, product_id, price, payment_method="card")

    price_formatted = f"{price:,}"
    checkout_text = (
        f"💳 **پیش‌فاکتور خرید شما**\n\n"
        f"📦 **محصول:** {name}\n"
        f"🆔 **کد پیگیری سفارش:** `{order_id}`\n"
        f"💵 **مبلغ قابل پرداخت:** {price_formatted} تومان\n\n"
        "لطفاً روش پرداخت خود را انتخاب کنید 👇"
    )
    await call.message.edit_text(
        checkout_text,
        reply_markup=get_payment_methods_keyboard(order_id, product_id),
        parse_mode=ParseMode.MARKDOWN
    )

# Apply Discount Code Handler
@user_router.callback_query(F.data.startswith("apply_discount_"))
async def apply_discount_prompt_cb(call: CallbackQuery, state: FSMContext):
    order_id = call.data.split("apply_discount_")[1]
    await state.update_data(order_id=order_id, message_id=call.message.message_id)
    await state.set_state(UserStates.entering_discount)

    # Keep interface single-page: update text with prompt to type code
    await call.message.edit_text(
        "🎟️ **لطفاً کد تخفیف خود را تایپ و ارسال کنید:**\n\n"
        "_(پس از ارسال پیام متنی، پیام شما پاک شده و همین منو آپدیت می‌شود)_",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 انصراف", callback_data=f"back_to_pay_{order_id}", style=ButtonStyle.DANGER)]
        ]),
        parse_mode=ParseMode.MARKDOWN
    )

@user_router.message(UserStates.entering_discount)
async def process_discount_msg(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    order_id = data.get("order_id")
    menu_message_id = data.get("message_id")
    discount_code = message.text.strip()

    # Delete user's incoming message immediately to maintain single-page cleanliness
    try:
        await message.delete()
    except Exception:
        pass

    order = await db.get_order(order_id)
    if not order:
        await state.clear()
        return

    # Check discount validness
    percent = await db.use_discount_code(message.from_user.id, discount_code)
    if percent is not None:
        # Calculate discount
        original_price = order[3]
        discount_amount = int(original_price * (percent / 100))
        new_price = original_price - discount_amount

        # Update order with new price and discount code in db
        # We need an update order amount in database
        async with db._lock:
            await db.conn.execute("UPDATE orders SET amount = ?, discount_code = ? WHERE id = ?", (new_price, discount_code, order_id))
            await db.conn.commit()

        success_text = (
            f"🎉 **کد تخفیف با موفقیت اعمال شد! ({percent}% تخفیف)**\n\n"
            f"📦 **محصول:** {order[10]}\n"
            f"💵 **مبلغ قبلی:** {original_price:,} تومان\n"
            f"🔥 **مبلغ جدید قابل پرداخت:** {new_price:,} تومان\n"
            f"🆔 **کد پیگیری سفارش:** `{order_id}`\n\n"
            "لطفاً روش پرداخت خود را انتخاب کنید 👇"
        )
        await state.clear()
        await bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=menu_message_id,
            text=success_text,
            reply_markup=get_payment_methods_keyboard(order_id, order[2]),
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        # Invalid or already used
        fail_text = (
            f"❌ **کد تخفیف وارد شده نامعتبر، منقضی شده یا قبلاً توسط شما استفاده شده است!**\n\n"
            f"📦 **محصول:** {order[10]}\n"
            f"💵 **مبلغ قابل پرداخت:** {order[3]:,} تومان\n"
            f"🆔 **کد پیگیری سفارش:** `{order_id}`\n\n"
            "لطفاً روش پرداخت خود را انتخاب کنید 👇"
        )
        await state.clear()
        await bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=menu_message_id,
            text=fail_text,
            reply_markup=get_payment_methods_keyboard(order_id, order[2]),
            parse_mode=ParseMode.MARKDOWN
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

    checkout_text = (
        f"💳 **پیش‌فاکتور خرید شما**\n\n"
        f"📦 **محصول:** {order[10]}\n"
        f"🆔 **کد پیگیری سفارش:** `{order_id}`\n"
        f"💵 **مبلغ قابل پرداخت:** {order[3]:,} تومان\n\n"
        "لطفاً روش پرداخت خود را انتخاب کنید 👇"
    )
    await call.message.edit_text(
        checkout_text,
        reply_markup=get_payment_methods_keyboard(order_id, order[2]),
        parse_mode=ParseMode.MARKDOWN
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
    product_name = order[10]

    zp = ZarinPal()
    success, result = await zp.request_payment(
        amount_toman=amount_toman,
        description=f"خرید {product_name} - سفارش {order_id}",
        order_id=order_id
    )

    if success:
        # Update order payment method
        async with db._lock:
            await db.conn.execute("UPDATE orders SET payment_method = 'zarinpal' WHERE id = ?", (order_id,))
            await db.conn.commit()

        zp_text = (
            f"🔗 **لینک پرداخت آنلاین زرین‌پال ایجاد شد!**\n\n"
            f"📦 **محصول:** {product_name}\n"
            f"💵 **مبلغ قابل پرداخت:** {amount_toman:,} تومان\n\n"
            "جهت پرداخت روی دکمه زیر کلیک کنید. پس از پرداخت موفق، اشتراک شما فعال می‌شود."
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 ورود به درگاه پرداخت", url=result)],
            [InlineKeyboardButton(text="🔙 بازگشت به پیش‌فاکتور", callback_data=f"back_to_pay_{order_id}", style=ButtonStyle.DANGER)]
        ])
        await call.message.edit_text(zp_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    else:
        await call.message.edit_text(
            f"❌ **خطا در اتصال به درگاه پرداخت:**\n`{result}`",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 بازگشت و تلاش مجدد", callback_data=f"back_to_pay_{order_id}", style=ButtonStyle.DANGER)]
            ]),
            parse_mode=ParseMode.MARKDOWN
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
        f"💳 **روش کارت به کارت (آپلود رسید)**\n\n"
        f"لطفاً مبلغ **{amount_toman:,} تومان** را به شماره کارت زیر واریز کنید:\n\n"
        f"💳 شماره کارت:\n`{CARD_NUMBER}`\n"
        f"👤 به نام: **{CARD_HOLDER}**\n\n"
        f"سپس روی دکمه زیر کلیک کنید تا رسید خود را آپلود نمایید 👇"
    )
    await call.message.edit_text(card_text, reply_markup=get_card_payment_keyboard(order_id), parse_mode=ParseMode.MARKDOWN)

@user_router.callback_query(F.data.startswith("upload_receipt_"))
async def upload_receipt_prompt_cb(call: CallbackQuery, state: FSMContext):
    order_id = call.data.split("upload_receipt_")[1]
    await state.update_data(order_id=order_id, message_id=call.message.message_id)
    await state.set_state(UserStates.waiting_for_receipt)

    await call.message.edit_text(
        "📸 **لطفاً تصویر فیش واریزی خود را ارسال کنید:**\n\n"
        "_(به محض ارسال عکس رسید، پیام ارسالی شما برای تمیز ماندن چت پاک شده و ربات آپدیت می‌شود)_",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 انصراف", callback_data=f"pay_card_{order_id}", style=ButtonStyle.DANGER)]
        ]),
        parse_mode=ParseMode.MARKDOWN
    )

@user_router.message(UserStates.waiting_for_receipt, F.photo)
async def process_receipt_photo(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    order_id = data.get("order_id")
    menu_message_id = data.get("message_id")

    file_id = message.photo[-1].file_id

    # Delete the user's uploaded photo immediately to keep the Single-Page chat interface perfectly clean
    try:
        await message.delete()
    except Exception:
        pass

    await state.clear()

    # Update DB with receipt file ID and change payment method
    async with db._lock:
        await db.conn.execute(
            "UPDATE orders SET receipt_file_id = ?, payment_method = 'card', status = 'pending' WHERE id = ?",
            (file_id, order_id)
        )
        await db.conn.commit()

    order = await db.get_order(order_id)

    # Update user's screen in single-page mode
    success_text = (
        "⏳ **رسید پرداخت شما با موفقیت دریافت شد!**\n\n"
        "✅ وضعیت: **در حال بررسی رسید پرداخت توسط مدیریت...**\n"
        f"🆔 کد پیگیری سفارش: `{order_id}`\n\n"
        "به محض تایید یا رد پرداخت توسط مدیریت، از طریق ربات به شما اطلاع‌رسانی خواهد شد. سپاس از صبوری شما 🙏"
    )
    await bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=menu_message_id,
        text=success_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 بازگشت به خانه", callback_data="go_home", style=ButtonStyle.PRIMARY)]
        ]),
        parse_mode=ParseMode.MARKDOWN
    )

    # Route logs to the private Admin Log Channel
    username_str = f"@{message.from_user.username}" if message.from_user.username else "بدون یوزرنیم"
    admin_notify_text = (
        f"📥 **رسید پرداخت جدید ثبت شد!**\n\n"
        f"👤 **کاربر:** {message.from_user.full_name} ({username_str})\n"
        f"🆔 **شناسه کاربری:** `{message.from_user.id}`\n"
        f"📦 **محصول:** {order[10]}\n"
        f"💵 **مبلغ پرداختی:** {order[3]:,} تومان\n"
        f"🆔 **کد پیگیری:** `{order_id}`\n"
        f"💳 **روش پرداخت:** کارت به کارت\n\n"
        "لطفاً با زدن دکمه‌های زیر، رسید را تایید یا رد کنید 👇"
    )

    admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🟢 تایید رسید و تحویل", callback_data=f"adm_approve_{order_id}", style=ButtonStyle.SUCCESS),
            InlineKeyboardButton(text="🔴 رد رسید", callback_data=f"adm_reject_{order_id}", style=ButtonStyle.DANGER)
        ]
    ])

    # Send the log with the photo to the dedicated Admin Log Channel
    await bot.send_photo(
        chat_id=ADMIN_LOG_CHANNEL,
        photo=file_id,
        caption=admin_notify_text,
        reply_markup=admin_keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

@user_router.callback_query(F.data.startswith("cancel_order_"))
async def cancel_order_cb(call: CallbackQuery):
    await show_loading(call)
    order_id = call.data.split("cancel_order_")[1]
    # Simple order cleanup
    async with db._lock:
        await db.conn.execute("DELETE FROM orders WHERE id = ?", (order_id,))
        await db.conn.commit()
    await call.message.edit_text(
        "❌ **سفارش شما لغو شد.**",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 بازگشت به خانه", callback_data="go_home", style=ButtonStyle.PRIMARY)]
        ]),
        parse_mode=ParseMode.MARKDOWN
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

    # user details
    joined_at = user[3]
    expiry = user[4] or "🔴 غیرفعال / بدون اشتراک"

    profile_text = (
        f"👤 **پروفایل کاربری شما**\n\n"
        f"🆔 شناسه عددی شما: `{user_id}`\n"
        f"🗓️ تاریخ عضویت: {joined_at}\n"
        f"⌛ وضعیت اشتراک فعال: **{expiry}**\n\n"
        "می‌توانید سفارشات قبلی خود را از دکمه زیر بررسی کنید 👇"
    )
    await call.message.edit_text(
        profile_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📥 سفارشات من", callback_data="my_orders", style=ButtonStyle.PRIMARY)],
            [InlineKeyboardButton(text="🔙 بازگشت به منوی اصلی", callback_data="go_home", style=ButtonStyle.DANGER)]
        ]),
        parse_mode=ParseMode.MARKDOWN
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

    orders_text = "📥 **سفارشات اخیر شما:**\n\n"
    for ord_id, prod_name, amount, status, created_at in orders[:5]:
        status_emoji = "🟡 در انتظار" if status == "pending" else ("🟢 تایید شده" if status == "approved" else "🔴 رد شده")
        orders_text += (
            f"🔹 **سفارش:** `{ord_id}` | **محصول:** {prod_name}\n"
            f"💵 مبلغ: {amount:,} تومان | وضعیت: {status_emoji}\n"
            f"🗓️ تاریخ: {created_at}\n\n"
        )

    await call.message.edit_text(
        orders_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 بازگشت به خانه", callback_data="go_home", style=ButtonStyle.DANGER)]
        ]),
        parse_mode=ParseMode.MARKDOWN
    )

@user_router.callback_query(F.data == "support_info")
async def support_info_cb(call: CallbackQuery):
    await show_loading(call)
    support_text = (
        "📞 **پشتیبانی فروشگاه**\n\n"
        "در صورت بروز هرگونه مشکل در خرید، پرداخت یا تحویل سفارش، همکاران ما در پی‌وی پاسخگوی شما هستند.\n\n"
        "💬 ایدی پشتیبانی اصلی: @support_user\n"
        "💬 ایدی پشتیبانی دوم: @support_user_2"
    )
    await call.message.edit_text(
        support_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 بازگشت به خانه", callback_data="go_home", style=ButtonStyle.DANGER)]
        ]),
        parse_mode=ParseMode.MARKDOWN
    )
