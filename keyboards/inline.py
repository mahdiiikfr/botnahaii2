from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ButtonStyle
from config.config import ADMINS, CARD_NUMBER, CARD_HOLDER

def get_main_keyboard(user_id: int) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="🛍️ فروشگاه", callback_data="categories_list", style=ButtonStyle.PRIMARY)
        ],
        [
            InlineKeyboardButton(text="📥 سفارشات من", callback_data="my_orders", style=ButtonStyle.PRIMARY),
            InlineKeyboardButton(text="👛 کیف پول من", callback_data="my_wallet", style=ButtonStyle.PRIMARY)
        ],
        [
            InlineKeyboardButton(text="👥 کسب درآمد (دعوت)", callback_data="referral_program", style=ButtonStyle.SUCCESS),
            InlineKeyboardButton(text="🎁 تست رایگان", callback_data="free_test_account", style=ButtonStyle.SUCCESS)
        ],
        [
            InlineKeyboardButton(text="🎫 ثبت تیکت پشتیبانی", callback_data="support_info", style=ButtonStyle.PRIMARY)
        ],
        [
            InlineKeyboardButton(text="👤 حساب کاربری", callback_data="user_profile", style=ButtonStyle.PRIMARY)
        ]
    ]
    # Add Admin Panel button if the user is an admin
    if user_id in ADMINS:
        buttons.append([
            InlineKeyboardButton(text="⚙️ پنل مدیریت ربات", callback_data="admin_panel", style=ButtonStyle.DANGER)
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_categories_keyboard(categories: list, user_id: int) -> InlineKeyboardMarkup:
    buttons = []
    # Dynamic categories layout: 2 columns
    for i in range(0, len(categories), 2):
        row = []
        cat1 = categories[i]
        row.append(InlineKeyboardButton(text=f"📂 {cat1[1]}", callback_data=f"cat_{cat1[0]}"))
        if i + 1 < len(categories):
            cat2 = categories[i+1]
            row.append(InlineKeyboardButton(text=f"📂 {cat2[1]}", callback_data=f"cat_{cat2[0]}"))
        buttons.append(row)

    buttons.append([InlineKeyboardButton(text="🔙 بازگشت به خانه", callback_data="go_home", style=ButtonStyle.DANGER)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_products_keyboard(products: list, category_id: int) -> InlineKeyboardMarkup:
    buttons = []
    for prod in products:
        price_formatted = f"{prod[3]:,}"
        buttons.append([
            InlineKeyboardButton(text=f"🔹 {prod[1]} - {price_formatted} تومان", callback_data=f"prod_{prod[0]}")
        ])
    buttons.append([
        InlineKeyboardButton(text="🔙 بازگشت به دسته‌بندی‌ها", callback_data="categories_list", style=ButtonStyle.DANGER)
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_product_details_keyboard(product_id: int, category_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💳 خرید و پرداخت", callback_data=f"buy_{product_id}", style=ButtonStyle.SUCCESS)
        ],
        [
            InlineKeyboardButton(text="🔙 بازگشت به محصولات", callback_data=f"cat_{category_id}", style=ButtonStyle.DANGER)
        ]
    ])

def get_payment_methods_keyboard(order_id: str, product_id: int, allow_wallet: bool = False) -> InlineKeyboardMarkup:
    buttons = []
    if allow_wallet:
        buttons.append([
            InlineKeyboardButton(text="👛 پرداخت سریع با موجودی کیف پول", callback_data=f"pay_wallet_{order_id}", style=ButtonStyle.SUCCESS)
        ])

    buttons.append([
        InlineKeyboardButton(text="🔗 پرداخت آنلاین زرین‌پال", callback_data=f"pay_zarinpal_{order_id}", style=ButtonStyle.PRIMARY)
    ])
    buttons.append([
        InlineKeyboardButton(text="💳 کارت به کارت (آپلود رسید)", callback_data=f"pay_card_{order_id}", style=ButtonStyle.PRIMARY)
    ])
    buttons.append([
        InlineKeyboardButton(text="🎟️ اعمال کد تخفیف", callback_data=f"apply_discount_{order_id}", style=ButtonStyle.SUCCESS)
    ])
    buttons.append([
        InlineKeyboardButton(text="🔙 انصراف و بازگشت", callback_data="categories_list", style=ButtonStyle.DANGER)
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_card_payment_keyboard(order_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📤 آپلود عکس رسید پرداخت", callback_data=f"upload_receipt_{order_id}", style=ButtonStyle.SUCCESS)
        ],
        [
            InlineKeyboardButton(text="🔙 بازگشت", callback_data=f"cancel_order_{order_id}", style=ButtonStyle.DANGER)
        ]
    ])

# Admin keyboard generator
def get_admin_panel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📁 مدیریت دسته‌بندی‌ها", callback_data="admin_manage_categories"),
            InlineKeyboardButton(text="🛍️ مدیریت محصولات", callback_data="admin_manage_products")
        ],
        [
            InlineKeyboardButton(text="🎟️ ساخت کد تخفیف", callback_data="admin_create_discount"),
            InlineKeyboardButton(text="📊 آمار کلی فروشگاه", callback_data="admin_stats")
        ],
        [
            InlineKeyboardButton(text="📢 ارسال پیام همگانی", callback_data="admin_broadcast"),
            InlineKeyboardButton(text="💾 پشتیبان‌گیری دیتابیس", callback_data="admin_db_backup")
        ],
        [
            InlineKeyboardButton(text="📥 مدیریت تیکت‌ها", callback_data="admin_tickets"),
            InlineKeyboardButton(text="🎁 مدیریت اکانت‌های تست", callback_data="admin_test_accounts")
        ],
        [
            InlineKeyboardButton(text="🔙 بازگشت به منوی اصلی", callback_data="go_home", style=ButtonStyle.DANGER)
        ]
    ])
