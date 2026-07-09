import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ButtonStyle, ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from database.db import Database
from config.config import ADMINS, ADMIN_LOG_CHANNEL
from keyboards.inline import get_admin_panel_keyboard

logger = logging.getLogger(__name__)
admin_router = Router()
db = Database()

# Secure Access Control: Admin only middlewares for admin_router
@admin_router.message.outer_middleware()
async def admin_msg_middleware(handler, event: Message, data: dict):
    if event.from_user.id not in ADMINS:
        return
    return await handler(event, data)

@admin_router.callback_query.outer_middleware()
async def admin_call_middleware(handler, event: CallbackQuery, data: dict):
    if event.from_user.id not in ADMINS:
        await event.answer("❌ شما دسترسی به این بخش را ندارید!", show_alert=True)
        return
    return await handler(event, data)

# FSM States for Admin Panel
class AdminStates(StatesGroup):
    adding_category = State()
    adding_product_name = State()
    adding_product_desc = State()
    adding_product_price = State()
    adding_product_auto_deliver = State()

    adding_inventory_content = State()

    creating_discount_code = State()
    creating_discount_percent = State()
    creating_discount_max_uses = State()

    manual_delivery_content = State()
    rejecting_order_reason = State()

# Inline Loading feedback
async def show_loading(call: CallbackQuery):
    try:
        await call.message.edit_text("⏳ در حال پردازش...", reply_markup=None)
    except Exception:
        pass

# Admin auth helper
def is_admin(user_id: int) -> bool:
    return user_id in ADMINS

# --- Main Admin Panel ---
@admin_router.callback_query(F.data == "admin_panel")
async def admin_panel_cb(call: CallbackQuery, state: FSMContext):
    await state.clear()
    if not is_admin(call.from_user.id):
        await call.answer("❌ شما دسترسی به پنل مدیریت ندارید!", show_alert=True)
        return
    await show_loading(call)
    await call.message.edit_text(
        "⚙️ **به پنل مدیریت ربات خوش آمدید**\n\n"
        "از منوی زیر می‌توانید بخش‌های مختلف ربات را به صورت داینامیک و تک‌صفحه‌ای مدیریت کنید 👇",
        reply_markup=get_admin_panel_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )

# --- Category Management ---
@admin_router.callback_query(F.data == "admin_manage_categories")
async def admin_manage_categories_cb(call: CallbackQuery):
    await show_loading(call)
    categories = await db.get_categories()

    text = "📁 **مدیریت دسته‌بندی‌ها**\n\n"
    keyboard_buttons = []

    if categories:
        for cat_id, cat_name in categories:
            text += f"🔹 {cat_name} (شناسه: `{cat_id}`)\n"
            keyboard_buttons.append([
                InlineKeyboardButton(text=f"❌ حذف {cat_name}", callback_data=f"adm_delcat_{cat_id}", style=ButtonStyle.DANGER)
            ])
    else:
        text += "⚠️ هیچ دسته‌بندی وجود ندارد."

    keyboard_buttons.append([InlineKeyboardButton(text="➕ افزودن دسته‌بندی جدید", callback_data="adm_addcat", style=ButtonStyle.SUCCESS)])
    keyboard_buttons.append([InlineKeyboardButton(text="🔙 بازگشت به پنل مدیریت", callback_data="admin_panel", style=ButtonStyle.DANGER)])

    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons), parse_mode=ParseMode.MARKDOWN)

@admin_router.callback_query(F.data == "adm_addcat")
async def adm_addcat_prompt_cb(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.adding_category)
    await state.update_data(message_id=call.message.message_id)
    await call.message.edit_text(
        "📝 **لطفاً نام دسته‌بندی جدید را ارسال کنید:**\n\n"
        "_(پس از ارسال، پیام متنی شما به صورت خودکار برای تمیزی صفحه چت حذف می‌شود)_",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 انصراف", callback_data="admin_manage_categories", style=ButtonStyle.DANGER)]
        ]),
        parse_mode=ParseMode.MARKDOWN
    )

@admin_router.message(AdminStates.adding_category)
async def process_add_category_msg(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    menu_message_id = data.get("message_id")
    cat_name = message.text.strip()

    try:
        await message.delete()
    except Exception:
        pass

    success = await db.add_category(cat_name)
    await state.clear()

    if success:
        result_text = f"✅ دسته‌بندی **«{cat_name}»** با موفقیت افزوده شد."
    else:
        result_text = f"❌ دسته‌بندی با نام **«{cat_name}»** از قبل وجود دارد!"

    await bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=menu_message_id,
        text=result_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 بازگشت به مدیریت دسته‌بندی‌ها", callback_data="admin_manage_categories", style=ButtonStyle.PRIMARY)]
        ]),
        parse_mode=ParseMode.MARKDOWN
    )

@admin_router.callback_query(F.data.startswith("adm_delcat_"))
async def adm_delcat_cb(call: CallbackQuery):
    await show_loading(call)
    cat_id = int(call.data.split("_")[2])
    await db.delete_category(cat_id)
    await call.message.edit_text(
        "✅ دسته‌بندی مورد نظر با موفقیت حذف شد.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 بازگشت به مدیریت دسته‌بندی‌ها", callback_data="admin_manage_categories", style=ButtonStyle.PRIMARY)]
        ])
    )

# --- Product Management ---
@admin_router.callback_query(F.data == "admin_manage_products")
async def admin_manage_products_cb(call: CallbackQuery):
    await show_loading(call)
    categories = await db.get_categories()

    if not categories:
        await call.message.edit_text(
            "⚠️ ابتدا باید حداقل یک دسته‌بندی ایجاد کنید تا بتوانید محصول اضافه نمایید.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 بازگشت به پنل", callback_data="admin_panel", style=ButtonStyle.DANGER)]
            ])
        )
        return

    text = "🛍️ **مدیریت محصولات**\n\nجهت مدیریت یا افزودن محصول، دسته‌بندی مورد نظر را انتخاب کنید:"
    keyboard_buttons = []
    for cat_id, cat_name in categories:
        keyboard_buttons.append([
            InlineKeyboardButton(text=f"📁 محصولات {cat_name}", callback_data=f"adm_list_prod_{cat_id}")
        ])
    keyboard_buttons.append([InlineKeyboardButton(text="🔙 بازگشت به پنل مدیریت", callback_data="admin_panel", style=ButtonStyle.DANGER)])
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons), parse_mode=ParseMode.MARKDOWN)

@admin_router.callback_query(F.data.startswith("adm_list_prod_"))
async def adm_list_products_in_cat_cb(call: CallbackQuery):
    await show_loading(call)
    cat_id = int(call.data.split("_")[3])
    products = await db.get_products_by_category(cat_id)

    text = f"🛍️ **محصولات فعال در این دسته‌بندی:**\n\n"
    keyboard_buttons = []

    if products:
        for prod_id, name, desc, price, auto in products:
            delivery_type = "⚡ خودکار" if auto else "✍️ دستی"
            inventory_str = ""
            if auto:
                count = await db.get_inventory_count(prod_id)
                inventory_str = f" (موجودی: {count})"

            text += f"🔹 **{name}** | قیمت: {price:,} تومان | تحویل: {delivery_type}{inventory_str}\n"

            row = [
                InlineKeyboardButton(text="❌ حذف", callback_data=f"adm_delprod_{prod_id}_{cat_id}", style=ButtonStyle.DANGER)
            ]
            if auto:
                row.append(InlineKeyboardButton(text="➕ موجودی", callback_data=f"adm_addinv_{prod_id}_{cat_id}", style=ButtonStyle.SUCCESS))
            keyboard_buttons.append(row)
    else:
        text += "⚠️ هیچ محصولی در این بخش ثبت نشده است."

    keyboard_buttons.append([
        InlineKeyboardButton(text="➕ افزودن محصول جدید", callback_data=f"adm_addprod_{cat_id}", style=ButtonStyle.SUCCESS)
    ])
    keyboard_buttons.append([
        InlineKeyboardButton(text="🔙 بازگشت به دسته‌بندی‌ها", callback_data="admin_manage_products", style=ButtonStyle.DANGER)
    ])

    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons), parse_mode=ParseMode.MARKDOWN)

# Delete product
@admin_router.callback_query(F.data.startswith("adm_delprod_"))
async def adm_del_product_cb(call: CallbackQuery):
    await show_loading(call)
    parts = call.data.split("_")
    prod_id = int(parts[2])
    cat_id = int(parts[3])
    await db.delete_product(prod_id)
    await call.message.edit_text(
        "✅ محصول مورد نظر با موفقیت حذف شد.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 بازگشت به لیست محصولات", callback_data=f"adm_list_prod_{cat_id}", style=ButtonStyle.PRIMARY)]
        ])
    )

# Add Product wizard flow
@admin_router.callback_query(F.data.startswith("adm_addprod_"))
async def adm_addprod_start_cb(call: CallbackQuery, state: FSMContext):
    cat_id = int(call.data.split("_")[2])
    await state.update_data(cat_id=cat_id, message_id=call.message.message_id)
    await state.set_state(AdminStates.adding_product_name)
    await call.message.edit_text(
        "📝 **مرحله ۱ از ۴:**\nلطفاً **نام محصول** را ارسال کنید:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 انصراف", callback_data=f"adm_list_prod_{cat_id}", style=ButtonStyle.DANGER)]
        ]),
        parse_mode=ParseMode.MARKDOWN
    )

@admin_router.message(AdminStates.adding_product_name)
async def process_prod_name_msg(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    menu_message_id = data.get("message_id")
    cat_id = data.get("cat_id")
    prod_name = message.text.strip()

    try:
        await message.delete()
    except Exception:
        pass

    await state.update_data(prod_name=prod_name)
    await state.set_state(AdminStates.adding_product_desc)
    await bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=menu_message_id,
        text="📝 **مرحله ۲ از ۴:**\nلطفاً **توضیحات محصول** را ارسال کنید:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 انصراف", callback_data=f"adm_list_prod_{cat_id}", style=ButtonStyle.DANGER)]
        ]),
        parse_mode=ParseMode.MARKDOWN
    )

@admin_router.message(AdminStates.adding_product_desc)
async def process_prod_desc_msg(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    menu_message_id = data.get("message_id")
    cat_id = data.get("cat_id")
    prod_desc = message.text.strip()

    try:
        await message.delete()
    except Exception:
        pass

    await state.update_data(prod_desc=prod_desc)
    await state.set_state(AdminStates.adding_product_price)
    await bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=menu_message_id,
        text="💵 **مرحله ۳ از ۴:**\nلطفاً **قیمت محصول (به تومان و به صورت عدد خام)** را وارد کنید:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 انصراف", callback_data=f"adm_list_prod_{cat_id}", style=ButtonStyle.DANGER)]
        ]),
        parse_mode=ParseMode.MARKDOWN
    )

@admin_router.message(AdminStates.adding_product_price)
async def process_prod_price_msg(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    menu_message_id = data.get("message_id")
    cat_id = data.get("cat_id")
    price_str = message.text.strip()

    try:
        await message.delete()
    except Exception:
        pass

    if not price_str.isdigit():
        await bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=menu_message_id,
            text="⚠️ **قیمت باید فقط شامل عدد باشد!**\nلطفاً قیمت معتبر وارد کنید:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 انصراف", callback_data=f"adm_list_prod_{cat_id}", style=ButtonStyle.DANGER)]
            ])
        )
        return

    await state.update_data(prod_price=int(price_str))
    await state.set_state(AdminStates.adding_product_auto_deliver)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚡ تحویل خودکار (پیش‌فرض دیتابیس)", callback_data="type_auto", style=ButtonStyle.SUCCESS),
            InlineKeyboardButton(text="✍️ تحویل دستی توسط ادمین", callback_data="type_manual", style=ButtonStyle.PRIMARY)
        ],
        [
            InlineKeyboardButton(text="🔙 انصراف", callback_data=f"adm_list_prod_{cat_id}", style=ButtonStyle.DANGER)
        ]
    ])
    await bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=menu_message_id,
        text="⚙️ **مرحله ۴ از ۴:**\nنوع تحویل محصول به چه صورت باشد؟",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

@admin_router.callback_query(AdminStates.adding_product_auto_deliver, F.data.startswith("type_"))
async def process_prod_type_cb(call: CallbackQuery, state: FSMContext):
    await show_loading(call)
    data = await state.get_data()
    cat_id = data.get("cat_id")
    name = data.get("prod_name")
    desc = data.get("prod_desc")
    price = data.get("prod_price")

    auto_deliver = 1 if call.data == "type_auto" else 0

    await db.add_product(cat_id, name, desc, price, auto_deliver)
    await state.clear()

    await call.message.edit_text(
        f"✅ محصول **«{name}»** با موفقیت در این دسته‌بندی تعریف شد.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 بازگشت به لیست محصولات", callback_data=f"adm_list_prod_{cat_id}", style=ButtonStyle.PRIMARY)]
        ]),
        parse_mode=ParseMode.MARKDOWN
    )

# Add Inventory/License key to auto-delivery products
@admin_router.callback_query(F.data.startswith("adm_addinv_"))
async def adm_addinv_cb(call: CallbackQuery, state: FSMContext):
    parts = call.data.split("_")
    prod_id = int(parts[2])
    cat_id = int(parts[3])

    await state.update_data(prod_id=prod_id, cat_id=cat_id, message_id=call.message.message_id)
    await state.set_state(AdminStates.adding_inventory_content)

    await call.message.edit_text(
        "🗝️ **افزودن محتوا به انبار محصول خودکار:**\n\n"
        "لطفاً اکانت، لایسنس، لینک یا کد اشتراک مورد نظر را ارسال کنید تا در انبار ذخیره شود:\n\n"
        "_(پس از ارسال، به صورت کاملاً خودکار پیام شما برای تمیزی چت حذف می‌شود)_",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 انصراف", callback_data=f"adm_list_prod_{cat_id}", style=ButtonStyle.DANGER)]
        ]),
        parse_mode=ParseMode.MARKDOWN
    )

@admin_router.message(AdminStates.adding_inventory_content)
async def process_inventory_content(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    prod_id = data.get("prod_id")
    cat_id = data.get("cat_id")
    menu_message_id = data.get("message_id")

    content = message.text.strip()
    try:
        await message.delete()
    except Exception:
        pass

    await db.add_inventory_item(prod_id, content)
    await state.clear()

    await bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=menu_message_id,
        text="✅ محتوا با موفقیت به انبار محصول افزوده شد و هم‌اکنون آماده تحویل خودکار به خریداران است.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 بازگشت به لیست محصولات", callback_data=f"adm_list_prod_{cat_id}", style=ButtonStyle.PRIMARY)]
        ])
    )

# --- Create Discount Codes ---
@admin_router.callback_query(F.data == "admin_create_discount")
async def admin_create_discount_cb(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.creating_discount_code)
    await state.update_data(message_id=call.message.message_id)
    await call.message.edit_text(
        "🎟️ **ایجاد کد تخفیف جدید**\n\n"
        "لطفاً **کد مورد نظر** را تایپ و ارسال کنید (مثال: OFF50):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 انصراف", callback_data="admin_panel", style=ButtonStyle.DANGER)]
        ]),
        parse_mode=ParseMode.MARKDOWN
    )

@admin_router.message(AdminStates.creating_discount_code)
async def process_discount_code_msg(message: Message, state: FSMContext, bot: Bot):
    code = message.text.strip().upper()
    data = await state.get_data()
    menu_message_id = data.get("message_id")

    try:
        await message.delete()
    except Exception:
        pass

    await state.update_data(discount_code=code)
    await state.set_state(AdminStates.creating_discount_percent)

    await bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=menu_message_id,
        text="🔥 **درصد تخفیف را وارد کنید:**\n\nعدد خام بین ۱ تا ۱۰۰ باشد:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 انصراف", callback_data="admin_panel", style=ButtonStyle.DANGER)]
        ]),
        parse_mode=ParseMode.MARKDOWN
    )

@admin_router.message(AdminStates.creating_discount_percent)
async def process_discount_percent_msg(message: Message, state: FSMContext, bot: Bot):
    percent_str = message.text.strip()
    data = await state.get_data()
    menu_message_id = data.get("message_id")

    try:
        await message.delete()
    except Exception:
        pass

    if not percent_str.isdigit() or not (1 <= int(percent_str) <= 100):
        await bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=menu_message_id,
            text="⚠️ **درصد باید عددی معتبر بین ۱ تا ۱۰۰ باشد!**\nلطفاً درصد معتبر وارد کنید:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 انصراف", callback_data="admin_panel", style=ButtonStyle.DANGER)]
            ])
        )
        return

    await state.update_data(discount_percent=int(percent_str))
    await state.set_state(AdminStates.creating_discount_max_uses)

    await bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=menu_message_id,
        text="📊 **حداکثر دفعات مجاز استفاده از کد را وارد کنید:**\n\nاگر نامحدود است عدد 0 را بفرستید:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 انصراف", callback_data="admin_panel", style=ButtonStyle.DANGER)]
        ]),
        parse_mode=ParseMode.MARKDOWN
    )

@admin_router.message(AdminStates.creating_discount_max_uses)
async def process_discount_max_uses_msg(message: Message, state: FSMContext, bot: Bot):
    max_uses_str = message.text.strip()
    data = await state.get_data()
    menu_message_id = data.get("message_id")
    code = data.get("discount_code")
    percent = data.get("discount_percent")

    try:
        await message.delete()
    except Exception:
        pass

    if not max_uses_str.isdigit():
        await bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=menu_message_id,
            text="⚠️ **تعداد استفاده باید عدد باشد!**\nلطفاً تعداد مجاز معتبر ارسال کنید:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 انصراف", callback_data="admin_panel", style=ButtonStyle.DANGER)]
            ])
        )
        return

    max_uses = int(max_uses_str)
    actual_max = None if max_uses == 0 else max_uses

    success = await db.add_discount_code(code, percent, actual_max)
    await state.clear()

    if success:
        result_text = f"✅ کد تخفیف **«{code}»** با تخفیف **{percent}%** و دفعات استفاده **{max_uses or 'نامحدود'}** با موفقیت ساخته شد."
    else:
        result_text = f"❌ کد تخفیف **«{code}»** از قبل در سیستم وجود دارد!"

    await bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=menu_message_id,
        text=result_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 بازگشت به پنل مدیریت", callback_data="admin_panel", style=ButtonStyle.PRIMARY)]
        ]),
        parse_mode=ParseMode.MARKDOWN
    )

# --- Admin Statistics ---
@admin_router.callback_query(F.data == "admin_stats")
async def admin_stats_cb(call: CallbackQuery):
    await show_loading(call)
    total_users = await db.get_all_users_count()

    # Calculate some general sales stats
    async with db._lock:
        async with db.conn.execute("SELECT COUNT(*), SUM(amount) FROM orders WHERE status = 'approved'") as cursor:
            res = await cursor.fetchone()
            total_sales = res[0] if res and res[0] else 0
            total_income = res[1] if res and res[1] else 0

    stats_text = (
        f"📊 **آمار کلی فروشگاه و ربات**\n\n"
        f"👤 تعداد کل کاربران ربات: **{total_users} نفر**\n"
        f"🛍️ تعداد سفارشات موفق: **{total_sales} عدد**\n"
        f"💵 درآمد ناخالص کل: **{total_income:,} تومان**"
    )
    await call.message.edit_text(
        stats_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 بازگشت به پنل مدیریت", callback_data="admin_panel", style=ButtonStyle.DANGER)]
        ]),
        parse_mode=ParseMode.MARKDOWN
    )


# --- Order Verification & Delivery Mechanisms ---

@admin_router.callback_query(F.data.startswith("adm_approve_"))
async def adm_approve_order_cb(call: CallbackQuery, bot: Bot, state: FSMContext):
    # This handler is called from the Admin Log Channel
    order_id = call.data.split("_")[2]
    order = await db.get_order(order_id)
    if not order:
        await call.answer("❌ این سفارش دیگر وجود ندارد!", show_alert=True)
        return

    user_id = order[1]
    product_id = order[2]
    amount = order[3]
    payment_method = order[5]
    product_name = order[10]

    # Check if the product is auto-delivery
    product = await db.get_product(product_id)
    auto_deliver = product[5] if product else 0

    if auto_deliver:
        # Deliver auto inventory
        content = await db.pop_inventory_item(product_id)
        if content:
            # Deliver to user
            await db.update_order_status(order_id, "approved", content)

            user_notify_text = (
                f"✅ **پرداخت سفارش `{order_id}` شما توسط مدیریت تایید شد!**\n\n"
                f"🛍️ **محصول:** {product_name}\n"
                f"⚡ **محتوای لایسنس / اشتراک شما:**\n\n"
                f"`{content}`\n\n"
                "سپاس از خرید شما! مجدداً از منوی اصلی در خدمت شما هستیم."
            )
            try:
                await bot.send_message(chat_id=user_id, text=user_notify_text, parse_mode=ParseMode.MARKDOWN)
            except Exception:
                logger.exception(f"Failed to send delivery message to user {user_id}")

            # Update the message in the Admin Log Channel to show finalized state
            await call.message.edit_caption(
                caption=f"🟢 **سفارش `{order_id}` با موفقیت تایید و به صورت خودکار تحویل شد!**\n\n👤 کاربر: `{user_id}`\n💵 مبلغ: {amount:,} تومان",
                reply_markup=None,
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            # No content in inventory! Notify admin to do manual delivery
            await call.answer("⚠️ انبار این محصول خالی است! باید تحویل دستی انجام دهید.", show_alert=True)
            await ask_manual_delivery(call, bot, state, order_id, user_id, product_name)
    else:
        # Manual delivery required
        await ask_manual_delivery(call, bot, state, order_id, user_id, product_name)

async def ask_manual_delivery(call: CallbackQuery, bot: Bot, state: FSMContext, order_id: str, user_id: int, product_name: str):
    await state.update_data(order_id=order_id, user_id=user_id, product_name=product_name, admin_msg_id=call.message.message_id)
    await state.set_state(AdminStates.manual_delivery_content)

    # Instruct admin in their direct messages
    admin_id = call.from_user.id
    await bot.send_message(
        chat_id=admin_id,
        text=(
            f"✍️ **تحویل دستی سفارش `{order_id}`**\n\n"
            f"👤 کاربر مقصد: `{user_id}`\n"
            f"📦 محصول خریداری شده: **{product_name}**\n\n"
            "لطفاً فایل، متن لایسنس، عکس یا مشخصات اکانت را جهت ارسال برای کاربر در پی‌وی بفرستید:"
        )
    )
    # Temporary answer to channel callback
    await call.answer("📝 دستورالعمل تحویل دستی به پی‌وی شما ارسال شد.", show_alert=True)

@admin_router.message(AdminStates.manual_delivery_content)
async def process_manual_delivery_content(message: Message, state: FSMContext, bot: Bot):
    # This runs in admin's private chat
    data = await state.get_data()
    order_id = data.get("order_id")
    user_id = data.get("user_id")
    product_name = data.get("product_name")
    admin_msg_id = data.get("admin_msg_id")

    # We can send any content types (photo, video, document, text) directly to user
    await db.update_order_status(order_id, "approved", message.text or "[محتوای مدیا]")

    user_notify_prefix = (
        f"✅ **پرداخت سفارش `{order_id}` شما تایید شد!**\n"
        f"🛍️ **محصول:** {product_name}\n"
        "📦 **محتوای ارسال شده توسط پشتیبانی:**\n\n"
    )

    try:
        if message.text:
            await bot.send_message(chat_id=user_id, text=user_notify_prefix + message.text)
        elif message.photo:
            await bot.send_photo(chat_id=user_id, photo=message.photo[-1].file_id, caption=user_notify_prefix)
        elif message.document:
            await bot.send_document(chat_id=user_id, document=message.document.file_id, caption=user_notify_prefix)
        elif message.video:
            await bot.send_video(chat_id=user_id, video=message.video.file_id, caption=user_notify_prefix)

        await message.reply("✅ محصول با موفقیت به کاربر تحویل داده شد و لاگ تکمیل گردید.")

        # Update Channel log to show approved state with a PV link to user
        user_info = await bot.get_chat(user_id)
        pv_link = f"https://t.me/{user_info.username}" if user_info.username else f"tg://user?id={user_id}"

        await bot.edit_message_caption(
            chat_id=ADMIN_LOG_CHANNEL,
            message_id=admin_msg_id,
            caption=(
                f"🟢 **سفارش `{order_id}` به صورت دستی تحویل داده شد!**\n\n"
                f"👤 کاربر: [{user_info.full_name}]({pv_link})\n"
                f"📦 محصول: {product_name}"
            ),
            reply_markup=None,
            parse_mode=ParseMode.MARKDOWN
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

    user_id = order[1]
    admin_id = call.from_user.id

    await state.update_data(order_id=order_id, user_id=user_id, admin_msg_id=call.message.message_id)
    await state.set_state(AdminStates.rejecting_order_reason)

    await bot.send_message(
        chat_id=admin_id,
        text=(
            f"🔴 **رد کردن سفارش `{order_id}`**\n\n"
            "لطفاً دلیل رد کردن این رسید پرداخت را ارسال کنید تا برای کاربر فرستاده شود:"
        )
    )
    await call.answer("📝 درخواست ثبت دلیل رد رسید به پی‌وی شما ارسال شد.", show_alert=True)

@admin_router.message(AdminStates.rejecting_order_reason)
async def process_reject_reason(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    order_id = data.get("order_id")
    user_id = data.get("user_id")
    admin_msg_id = data.get("admin_msg_id")
    reason = message.text.strip()

    await db.update_order_status(order_id, "rejected")

    user_notify_text = (
        f"🔴 **رسید پرداخت سفارش `{order_id}` شما توسط مدیریت رد شد!**\n\n"
        f"❌ **علت رد شدن:** {reason}\n\n"
        "در صورت بروز اشتباه، مجدداً می‌توانید خرید جدید ثبت کنید یا با پشتیبانی ارتباط برقرار نمایید."
    )

    try:
        await bot.send_message(chat_id=user_id, text=user_notify_text)
        await message.reply("✅ سفارش رد شد و دلیل آن به کاربر ابلاغ گردید.")

        # Update channel log
        await bot.edit_message_caption(
            chat_id=ADMIN_LOG_CHANNEL,
            message_id=admin_msg_id,
            caption=(
                f"🔴 **سفارش `{order_id}` رد شد!**\n\n"
                f"👤 شناسه کاربر: `{user_id}`\n"
                f"❌ علت رد شدن: {reason}"
            ),
            reply_markup=None,
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.error(f"Error in rejecting order: {e}")
        await message.reply(f"❌ خطا در ابلاغ رد سفارش: {e}")

    await state.clear()
