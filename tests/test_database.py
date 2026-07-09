import asyncio
import os
from database.db import Database

async def test_db():
    print("Testing database operations asynchronously...")
    db = Database()
    await db.connect()

    # 1. Clean DB state for testing
    async with db._lock:
        await db.conn.execute("DELETE FROM categories;")
        await db.conn.execute("DELETE FROM products;")
        await db.conn.execute("DELETE FROM discount_codes;")
        await db.conn.commit()

    # 2. Add category
    assert await db.add_category("VPN") == True
    assert await db.add_category("VPN") == False # Duplicate should return False

    categories = await db.get_categories()
    print("Categories:", categories)
    assert len(categories) == 1
    cat_id = categories[0][0]

    # 3. Add product
    await db.add_product(cat_id, "vless subscription", "High speed 1 month", 50000, 1)
    products = await db.get_products_by_category(cat_id)
    print("Products:", products)
    assert len(products) == 1
    prod_id = products[0][0]

    # 4. Inventory testing
    await db.add_inventory_item(prod_id, "VLESS://license-code-123456")
    inv_count = await db.get_inventory_count(prod_id)
    print("Inventory count:", inv_count)
    assert inv_count == 1

    # 5. Discount testing
    await db.add_discount_code("OFF50", 50, 2)
    percent = await db.use_discount_code(123456, "OFF50")
    print("Applied discount percent:", percent)
    assert percent == 50

    # Duplicate use of discount code by the same user should return None
    dup_percent = await db.use_discount_code(123456, "OFF50")
    assert dup_percent is None

    # 6. Orders testing
    await db.create_order("test_ord", 123456, prod_id, 25000, "OFF50", "zarinpal")
    order = await db.get_order("test_ord")
    print("Order details:", order)
    assert order is not None
    assert order[3] == 25000 # Correct amount

    # 7. Asynchronous secure hot backup testing
    backup_file = "database/store_backup.db"
    if os.path.exists(backup_file):
        os.remove(backup_file)

    await db.backup(backup_file)
    assert os.path.exists(backup_file) == True
    print("Hot backup file generated successfully.")
    os.remove(backup_file)

    await db.disconnect()
    print("🎉 All asynchronous database tests passed successfully!")

if __name__ == "__main__":
    asyncio.run(test_db())
