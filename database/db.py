import asyncio
import aiosqlite
import logging
from config.config import DB_FILE

logger = logging.getLogger(__name__)

class Database:
    _instance = None
    _lock = asyncio.Lock()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(Database, cls).__new__(cls, *args, **kwargs)
            cls._instance.conn = None
        return cls._instance

    async def connect(self):
        async with self._lock:
            if not self.conn:
                self.conn = await aiosqlite.connect(DB_FILE)
                # Optimize database performance using WAL mode and synchronous settings
                await self.conn.execute("PRAGMA journal_mode=WAL;")
                await self.conn.execute("PRAGMA synchronous=NORMAL;")
                await self.conn.commit()
                await self._create_tables()
                logger.info("Successfully connected to SQLite database in WAL mode.")

    async def disconnect(self):
        async with self._lock:
            if self.conn:
                await self.conn.close()
                self.conn = None
                logger.info("Disconnected from SQLite database.")

    async def _seed_static_products(self):
        # Clean up any potential leftover products and categories to ensure fresh layout
        await self.conn.execute("DELETE FROM products;")
        await self.conn.execute("DELETE FROM categories;")

        # Seed the 5 custom categories
        categories = [
            (1, "🌐 ثبت دامنه"),
            (2, "🛡️ فیلترشکن"),
            (3, "⚙️ خدمات پنل و سرور"),
            (4, "🤖 هوش مصنوعی (Gemini)"),
            (5, "🤝 پنل همکاری")
        ]
        for c_id, name in categories:
            await self.conn.execute("INSERT OR REPLACE INTO categories (id, name) VALUES (?, ?)", (c_id, name))

        static_products = [
            (1, 1, "دامنه ملی .ir", "ثبت و تمدید دامنه ملی دات آی‌آر با بهترین قیمت", 400000, 0),
            (2, 1, "دامنه .xyz", "ثبت و تمدید دامنه بین‌المللی دات ایکس‌وای‌زد (.xyz) با بهترین قیمت", 1000000, 0),
            (3, 1, "دامنه .shop", "ثبت و تمدید دامنه بین‌المللی دات شاپ (.shop) با بهترین قیمت", 1000000, 0),
            (4, 2, "فیلترشکن نامحدوده تک کاربره", "فیلترشکن فوق‌العاده پرسرعت و بدون محدودیت حجم ویژه تک کاربره", 150000, 0),
            (5, 3, "ساخت و کانفیگ پنل سنایی", "نصب، راه‌اندازی و کانفیگ حرفه‌ای پنل سنایی روی سرور مجازی", 500000, 0),
            (6, 3, "سرور ایران مشخصات رم 2 سی پی یو 1 حافظه 40", "سرور ایران با مشخصات فوق‌العاده قوی و پایدار.\n\n⚠️ برای مشخصات قوی‌تر به پشتیبانی پیام بدهید یا تیکت بزنید.", 1500000, 0),
            (7, 3, "سرور ایران ۲ هسته ۴ گیگ ۴۰ گیگابایت", "سرور مجازی ایران با عملکرد و سرعت بسیار عالی.\n\n⚠️ برای مشخصات قوی‌تر به پشتیبانی پیام بدهید یا تیکت بزنید.", 2200000, 0),
            (8, 3, "سرور ایران ۴ هسته ۸ گیگ ۴۰ گیگ حافظه", "سرور مجازی ایران فوق‌العاده قدرتمند مخصوص کارهای سنگین.\n\n⚠️ برای مشخصات قوی‌تر به پشتیبانی پیام بدهید یا تیکت بزنید.", 3200000, 0),
            (9, 4, "اشتراک جیمینای 12 ماهه", "خرید اشتراک ۱۲ ماهه هوش مصنوعی گوگل جیمینای (Gemini) با دسترسی کامل به امکانات ویژه", 2000000, 0),
            (10, 4, "اشتراک جیمینای 18 ماهه", "خرید اشتراک ۱۸ ماهه هوش مصنوعی گوگل جیمینای (Gemini) با دسترسی کامل به امکانات ویژه", 2500000, 0),
            (11, 3, "راهنمایی و رفع مشکلات مرتبط با پنل‌ها و فیلترشکن", "حل و رفع تمامی ارورها، عیب‌یابی و مشکلات مربوط به راه‌اندازی پنل‌های فیلترشکن", 250000, 0),
            (12, 5, "دامنه .ir (پنل همکاری)", "ثبت و تمدید دامنه ملی دات آی‌آر با تعرفه ویژه پنل همکاری و نمایندگی", 300000, 0),
            (13, 5, "فیلترشکن نامحدود (پنل همکاری)", "فیلترشکن فوق‌العاده پرسرعت و بدون محدودیت حجم ویژه نمایندگان و همکاران گرامی", 50000, 0)
        ]

        for p_id, cat_id, name, desc, price, auto_deliver in static_products:
            await self.conn.execute(
                "INSERT OR REPLACE INTO products (id, category_id, name, description, price, auto_deliver) VALUES (?, ?, ?, ?, ?, ?)",
                (p_id, cat_id, name, desc, price, auto_deliver)
            )
        await self.conn.commit()

    async def _create_tables(self):
        # Create users table with wallet balance, test_account_used, and referred_by columns
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP DEFAULT NULL,
                balance INTEGER DEFAULT 0,
                test_account_used INTEGER DEFAULT 0,
                referred_by INTEGER DEFAULT NULL
            )
        """)

        # Create categories table
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            )
        """)

        # Create products table
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY,
                category_id INTEGER,
                name TEXT NOT NULL,
                description TEXT,
                price INTEGER NOT NULL,
                auto_deliver INTEGER DEFAULT 0,
                FOREIGN KEY (category_id) REFERENCES categories (id) ON DELETE CASCADE
            )
        """)

        # Create inventory table for auto delivery (license codes, links, accounts)
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER,
                content TEXT NOT NULL,
                is_used INTEGER DEFAULT 0,
                FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE
            )
        """)

        # Create orders table
        # payment_method: 'zarinpal', 'card', or 'wallet'
        # status: 'pending', 'approved', 'rejected'
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id TEXT PRIMARY KEY,
                user_id INTEGER,
                product_id INTEGER, -- Can be NULL for wallet charges
                amount INTEGER NOT NULL,
                discount_code TEXT,
                payment_method TEXT NOT NULL,
                receipt_file_id TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                delivered_content TEXT,
                referral_rewarded INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (product_id) REFERENCES products (id)
            )
        """)

        # Create discount_codes table
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS discount_codes (
                code TEXT PRIMARY KEY,
                percent INTEGER NOT NULL,
                max_uses INTEGER,
                used_count INTEGER DEFAULT 0
            )
        """)

        # Create user_discount_usages table to prevent duplicate usage of discount codes
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS discount_usages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                code TEXT,
                used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, code)
            )
        """)

        # Create tickets table
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                message TEXT NOT NULL,
                status TEXT DEFAULT 'pending', -- 'pending' or 'replied'
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reply_message TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)

        # Create test_accounts table for free test subscription trials
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS test_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                is_used INTEGER DEFAULT 0
            )
        """)

        # Migrations to ensure columns exist in case db already exists
        try:
            await self.conn.execute("ALTER TABLE users ADD COLUMN balance INTEGER DEFAULT 0;")
            await self.conn.commit()
        except Exception:
            pass
        try:
            await self.conn.execute("ALTER TABLE users ADD COLUMN test_account_used INTEGER DEFAULT 0;")
            await self.conn.commit()
        except Exception:
            pass
        try:
            await self.conn.execute("ALTER TABLE users ADD COLUMN referred_by INTEGER DEFAULT NULL;")
            await self.conn.commit()
        except Exception:
            pass
        try:
            await self.conn.execute("ALTER TABLE orders ADD COLUMN referral_rewarded INTEGER DEFAULT 0;")
            await self.conn.commit()
        except Exception:
            pass

        # Indexes for fast querying
        await self.conn.execute("CREATE INDEX IF NOT EXISTS idx_users_id ON users (id);")
        try:
            await self.conn.execute("CREATE INDEX IF NOT EXISTS idx_orders_referral_rewarded ON orders (referral_rewarded);")
        except Exception:
            pass
        await self.conn.execute("CREATE INDEX IF NOT EXISTS idx_products_category_id ON products (category_id);")
        await self.conn.execute("CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders (user_id);")
        await self.conn.commit()

        # Seed static products on table creation/connection init
        await self._seed_static_products()

    # --- Secure Hot Backup Asynchronously ---
    async def backup(self, backup_filepath: str):
        """Perform a hot backup of the sqlite database safely and asynchronously."""
        if not self.conn:
            raise RuntimeError("Database connection is not initialized.")
        async with self._lock:
            async with aiosqlite.connect(backup_filepath) as backup_conn:
                # Under aiosqlite, connection.backup expects a raw standard sqlite3.Connection instance (._conn)
                await self.conn.backup(backup_conn._conn)
            logger.info(f"Asynchronous hot backup completed successfully to: {backup_filepath}")

    # --- Database Operations Helper Methods ---

    # User operations
    async def add_user(self, user_id: int, username: str, full_name: str, referred_by: int = None):
        async with self._lock:
            # Check if user already exists
            async with self.conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)) as cursor:
                exists = await cursor.fetchone()

            if not exists:
                # Insert brand-new user with referral source
                # Ensure referred_by is not the user themselves to prevent self-referral
                ref_id = referred_by if referred_by and referred_by != user_id else None
                await self.conn.execute(
                    "INSERT INTO users (id, username, full_name, referred_by) VALUES (?, ?, ?, ?)",
                    (user_id, username, full_name, ref_id)
                )
                await self.conn.commit()
            else:
                # Update existing user profile if username or full_name changes
                await self.conn.execute(
                    "UPDATE users SET username = ?, full_name = ? WHERE id = ?",
                    (username, full_name, user_id)
                )
                await self.conn.commit()

    async def get_referred_count(self, user_id: int) -> int:
        async with self._lock:
            async with self.conn.execute("SELECT COUNT(*) FROM users WHERE referred_by = ?", (user_id,)) as cursor:
                res = await cursor.fetchone()
                return res[0] if res else 0

    async def get_user(self, user_id: int):
        async with self._lock:
            async with self.conn.execute("SELECT id, username, full_name, joined_at, expires_at, balance, test_account_used, referred_by FROM users WHERE id = ?", (user_id,)) as cursor:
                return await cursor.fetchone()

    async def get_all_users_count(self):
        async with self._lock:
            async with self.conn.execute("SELECT COUNT(*) FROM users") as cursor:
                res = await cursor.fetchone()
                return res[0] if res else 0

    async def get_all_users(self):
        async with self._lock:
            async with self.conn.execute("SELECT id, username, full_name FROM users") as cursor:
                return await cursor.fetchall()

    # Wallet operations
    async def get_balance(self, user_id: int) -> int:
        async with self._lock:
            async with self.conn.execute("SELECT balance FROM users WHERE id = ?", (user_id,)) as cursor:
                res = await cursor.fetchone()
                return res[0] if res else 0

    async def add_balance(self, user_id: int, amount: int):
        async with self._lock:
            await self.conn.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (amount, user_id))
            await self.conn.commit()

    async def deduct_balance(self, user_id: int, amount: int) -> bool:
        async with self._lock:
            async with self.conn.execute("SELECT balance FROM users WHERE id = ?", (user_id,)) as cursor:
                res = await cursor.fetchone()
                current_balance = res[0] if res else 0
                if current_balance >= amount:
                    await self.conn.execute("UPDATE users SET balance = balance - ? WHERE id = ?", (amount, user_id))
                    await self.conn.commit()
                    return True
                return False

    # Category operations
    async def add_category(self, name: str):
        async with self._lock:
            try:
                await self.conn.execute("INSERT INTO categories (name) VALUES (?)", (name,))
                await self.conn.commit()
                return True
            except aiosqlite.IntegrityError:
                return False

    async def get_categories(self):
        async with self._lock:
            async with self.conn.execute("SELECT id, name FROM categories") as cursor:
                return await cursor.fetchall()

    async def delete_category(self, category_id: int):
        async with self._lock:
            await self.conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))
            await self.conn.commit()

    # Product operations
    async def add_product(self, category_id: int, name: str, description: str, price: int, auto_deliver: int):
        async with self._lock:
            await self.conn.execute(
                "INSERT INTO products (category_id, name, description, price, auto_deliver) VALUES (?, ?, ?, ?, ?)",
                (category_id, name, description, price, auto_deliver)
            )
            await self.conn.commit()

    async def get_products_by_category(self, category_id: int):
        async with self._lock:
            async with self.conn.execute("SELECT id, name, description, price, auto_deliver FROM products WHERE category_id = ?", (category_id,)) as cursor:
                return await cursor.fetchall()

    async def get_product(self, product_id: int):
        async with self._lock:
            async with self.conn.execute("SELECT id, category_id, name, description, price, auto_deliver FROM products WHERE id = ?", (product_id,)) as cursor:
                return await cursor.fetchone()

    async def update_product_price(self, product_id: int, new_price: int):
        async with self._lock:
            await self.conn.execute("UPDATE products SET price = ? WHERE id = ?", (new_price, product_id))
            await self.conn.commit()

    async def update_product_description(self, product_id: int, new_desc: str):
        async with self._lock:
            await self.conn.execute("UPDATE products SET description = ? WHERE id = ?", (new_desc, product_id))
            await self.conn.commit()

    async def delete_product(self, product_id: int):
        async with self._lock:
            await self.conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
            await self.conn.commit()

    # Inventory operations
    async def add_inventory_item(self, product_id: int, content: str):
        async with self._lock:
            await self.conn.execute("INSERT INTO inventory (product_id, content) VALUES (?, ?)", (product_id, content))
            await self.conn.commit()

    async def get_inventory_count(self, product_id: int):
        async with self._lock:
            async with self.conn.execute("SELECT COUNT(*) FROM inventory WHERE product_id = ? AND is_used = 0", (product_id,)) as cursor:
                res = await cursor.fetchone()
                return res[0] if res else 0

    async def pop_inventory_item(self, product_id: int):
        async with self._lock:
            async with self.conn.execute("SELECT id, content FROM inventory WHERE product_id = ? AND is_used = 0 LIMIT 1", (product_id,)) as cursor:
                item = await cursor.fetchone()
                if item:
                    item_id, content = item
                    await self.conn.execute("UPDATE inventory SET is_used = 1 WHERE id = ?", (item_id,))
                    await self.conn.commit()
                    return content
                return None

    # Discount operations
    async def add_discount_code(self, code: str, percent: int, max_uses: int):
        async with self._lock:
            try:
                await self.conn.execute(
                    "INSERT INTO discount_codes (code, percent, max_uses) VALUES (?, ?, ?)",
                    (code, percent, max_uses)
                )
                await self.conn.commit()
                return True
            except aiosqlite.IntegrityError:
                return False

    async def get_discount_code(self, code: str):
        async with self._lock:
            async with self.conn.execute("SELECT code, percent, max_uses, used_count FROM discount_codes WHERE code = ?", (code,)) as cursor:
                return await cursor.fetchone()

    async def use_discount_code(self, user_id: int, code: str):
        async with self._lock:
            # Check usage limit
            async with self.conn.execute("SELECT percent, max_uses, used_count FROM discount_codes WHERE code = ?", (code,)) as cursor:
                discount = await cursor.fetchone()
                if not discount:
                    return None
                percent, max_uses, used_count = discount
                if max_uses is not None and used_count >= max_uses:
                    return None

            # Check user duplicate usage
            try:
                await self.conn.execute("INSERT INTO discount_usages (user_id, code) VALUES (?, ?)", (user_id, code))
                await self.conn.execute("UPDATE discount_codes SET used_count = used_count + 1 WHERE code = ?", (code,))
                await self.conn.commit()
                return percent
            except aiosqlite.IntegrityError:
                return None  # Already used by this user

    # Order operations
    async def create_order(self, order_id: str, user_id: int, product_id: int, amount: int, discount_code: str = None, payment_method: str = "card"):
        async with self._lock:
            await self.conn.execute(
                "INSERT INTO orders (id, user_id, product_id, amount, discount_code, payment_method) VALUES (?, ?, ?, ?, ?, ?)",
                (order_id, user_id, product_id, amount, discount_code, payment_method)
            )
            await self.conn.commit()

    async def get_order(self, order_id: str):
        async with self._lock:
            async with self.conn.execute(
                """SELECT o.id, o.user_id, o.product_id, o.amount, o.discount_code, o.payment_method, o.receipt_file_id, o.status, o.created_at, o.delivered_content, p.name
                   FROM orders o LEFT JOIN products p ON o.product_id = p.id WHERE o.id = ?""",
                (order_id,)
            ) as cursor:
                return await cursor.fetchone()

    async def update_order_receipt(self, order_id: str, file_id: str):
        async with self._lock:
            await self.conn.execute("UPDATE orders SET receipt_file_id = ? WHERE id = ?", (file_id, order_id))
            await self.conn.commit()

    async def update_order_status(self, order_id: str, status: str, delivered_content: str = None):
        async with self._lock:
            await self.conn.execute(
                "UPDATE orders SET status = ?, delivered_content = ? WHERE id = ?",
                (status, delivered_content, order_id)
            )
            await self.conn.commit()

    async def reward_referrer_if_eligible(self, order_id: str) -> tuple[int, int] | None:
        """
        Rewards the referrer with 10,000 Tomans if the order gets approved,
        returning (referrer_id, referrer_new_balance) if rewarded, else None.
        """
        async with self._lock:
            # Check if order is approved and find user_id (only reward for actual product purchases, product_id is not null)
            async with self.conn.execute("SELECT user_id, status, product_id FROM orders WHERE id = ?", (order_id,)) as cursor:
                order = await cursor.fetchone()
                if not order or order[1] != 'approved' or order[2] is None:
                    return None
                user_id = order[0]

            # Find if this user was referred by someone
            async with self.conn.execute("SELECT referred_by FROM users WHERE id = ?", (user_id,)) as cursor:
                user_record = await cursor.fetchone()
                if not user_record or user_record[0] is None:
                    return None
                referrer_id = user_record[0]

            # Check if this order has already processed referral reward to avoid double payout
            # We can use a unique combination in a new or existing table, or just add a column,
            # but since we don't have a specific column, let's store it or verify if we have already rewarded.
            # To do this safely and simply without a schema change, let's keep an in-db flag,
            # or add a column `referral_rewarded` in orders. Let's run a migration to add `referral_rewarded` to orders.
            # Let's perform a migration try/except first to ensure the column is there.
            try:
                await self.conn.execute("ALTER TABLE orders ADD COLUMN referral_rewarded INTEGER DEFAULT 0;")
                await self.conn.commit()
            except Exception:
                pass

            async with self.conn.execute("SELECT referral_rewarded FROM orders WHERE id = ?", (order_id,)) as cursor:
                res = await cursor.fetchone()
                if res and res[0] == 1:
                    return None # Already rewarded for this order

            # Perform the reward
            await self.conn.execute("UPDATE users SET balance = balance + 10000 WHERE id = ?", (referrer_id,))
            await self.conn.execute("UPDATE orders SET referral_rewarded = 1 WHERE id = ?", (order_id,))
            await self.conn.commit()

            # Get new balance of referrer
            async with self.conn.execute("SELECT balance FROM users WHERE id = ?", (referrer_id,)) as cursor:
                bal_res = await cursor.fetchone()
                new_balance = bal_res[0] if bal_res else 0
                return (referrer_id, new_balance)

    async def get_user_orders(self, user_id: int):
        async with self._lock:
            async with self.conn.execute(
                "SELECT o.id, p.name, o.amount, o.status, o.created_at FROM orders o JOIN products p ON o.product_id = p.id WHERE o.user_id = ? AND o.status != 'rejected' ORDER BY o.created_at DESC",
                (user_id,)
            ) as cursor:
                return await cursor.fetchall()

    async def delete_order(self, order_id: str):
        """Deletes a specific order from the database permanently."""
        async with self._lock:
            await self.conn.execute("DELETE FROM orders WHERE id = ?", (order_id,))
            await self.conn.commit()

    async def delete_pending_orders(self, user_id: int):
        """Silently deletes all pending orders for a given user, optimized to avoid redundant locks."""
        async with self._lock:
            # Query if there are actually any pending orders first, using a fast SELECT
            async with self.conn.execute(
                "SELECT 1 FROM orders WHERE user_id = ? AND status = 'pending' LIMIT 1",
                (user_id,)
            ) as cursor:
                has_pending = await cursor.fetchone()

            if has_pending:
                # Only execute DELETE and commit if pending orders actually exist
                await self.conn.execute("DELETE FROM orders WHERE user_id = ? AND status = 'pending'", (user_id,))
                await self.conn.commit()

    async def extend_user_subscription(self, user_id: int, days: int = 30):
        async with self._lock:
            async with self.conn.execute("SELECT expires_at FROM users WHERE id = ?", (user_id,)) as cursor:
                res = await cursor.fetchone()
                current_expiry = res[0] if res else None

            from datetime import datetime, timedelta
            now = datetime.now()
            if current_expiry:
                try:
                    expiry_dt = datetime.strptime(current_expiry, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    expiry_dt = now
                if expiry_dt < now:
                    new_expiry = now + timedelta(days=days)
                else:
                    new_expiry = expiry_dt + timedelta(days=days)
            else:
                new_expiry = now + timedelta(days=days)

            new_expiry_str = new_expiry.strftime("%Y-%m-%d %H:%M:%S")
            await self.conn.execute("UPDATE users SET expires_at = ? WHERE id = ?", (new_expiry_str, user_id))
            await self.conn.commit()
            return new_expiry_str

    async def get_expired_users(self):
        async with self._lock:
            from datetime import datetime
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            async with self.conn.execute("SELECT id, username, expires_at FROM users WHERE expires_at < ? AND expires_at IS NOT NULL", (now_str,)) as cursor:
                return await cursor.fetchall()

    # Support Tickets operations
    async def create_ticket(self, user_id: int, message: str) -> int:
        async with self._lock:
            async with self.conn.execute(
                "INSERT INTO tickets (user_id, message) VALUES (?, ?) RETURNING id",
                (user_id, message)
            ) as cursor:
                res = await cursor.fetchone()
                await self.conn.commit()
                return res[0] if res else 0

    async def get_pending_tickets(self):
        async with self._lock:
            async with self.conn.execute(
                "SELECT t.id, t.user_id, t.message, t.created_at, u.full_name, u.username FROM tickets t JOIN users u ON t.user_id = u.id WHERE t.status = 'pending'"
            ) as cursor:
                return await cursor.fetchall()

    async def reply_ticket(self, ticket_id: int, reply_message: str):
        async with self._lock:
            await self.conn.execute(
                "UPDATE tickets SET status = 'replied', reply_message = ? WHERE id = ?",
                (reply_message, ticket_id)
            )
            await self.conn.commit()

    async def get_ticket(self, ticket_id: int):
        async with self._lock:
            async with self.conn.execute("SELECT id, user_id, message, status, reply_message FROM tickets WHERE id = ?", (ticket_id,)) as cursor:
                return await cursor.fetchone()

    # Free Test Accounts operations
    async def add_test_account(self, content: str):
        async with self._lock:
            await self.conn.execute("INSERT INTO test_accounts (content) VALUES (?)", (content,))
            await self.conn.commit()

    async def get_test_accounts_count(self) -> int:
        async with self._lock:
            async with self.conn.execute("SELECT COUNT(*) FROM test_accounts WHERE is_used = 0") as cursor:
                res = await cursor.fetchone()
                return res[0] if res else 0

    async def pop_test_account(self, user_id: int) -> str | None:
        async with self._lock:
            # Check if user already used test trial
            async with self.conn.execute("SELECT test_account_used FROM users WHERE id = ?", (user_id,)) as cursor:
                res = await cursor.fetchone()
                used = res[0] if res else 0
                if used == 1:
                    return "ALREADY_USED"

            # Fetch and pop an available test account
            async with self.conn.execute("SELECT id, content FROM test_accounts WHERE is_used = 0 LIMIT 1") as cursor:
                item = await cursor.fetchone()
                if item:
                    item_id, content = item
                    await self.conn.execute("UPDATE test_accounts SET is_used = 1 WHERE id = ?", (item_id,))
                    await self.conn.execute("UPDATE users SET test_account_used = 1 WHERE id = ?", (user_id,))
                    await self.conn.commit()
                    return content
                return None
