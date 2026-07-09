import asyncio
import os
from database.db import Database

async def test_db():
    print("Testing upgraded database operations asynchronously...")
    db = Database()
    print("Connecting to DB...")
    await db.connect()
    print("Connected to DB.")

    # 1. Clean DB state for testing
    async with db._lock:
        await db.conn.execute("DELETE FROM categories;")
        await db.conn.execute("DELETE FROM products;")
        await db.conn.execute("DELETE FROM discount_codes;")
        await db.conn.execute("DELETE FROM tickets;")
        await db.conn.execute("DELETE FROM test_accounts;")
        await db.conn.execute("DELETE FROM orders;")
        await db.conn.execute("DELETE FROM users;")
        await db.conn.commit()

    # 2. Add user
    await db.add_user(123456, "test_user", "Test Name")
    user = await db.get_user(123456)
    assert user is not None
    assert user[5] == 0 # Balance should be 0 by default
    assert user[6] == 0 # Test account used should be 0 by default

    # 3. Wallet Balance Testing
    await db.add_balance(123456, 15000)
    bal = await db.get_balance(123456)
    print("Wallet balance after addition:", bal)
    assert bal == 15000

    # Deduct wallet balance
    deduct_success = await db.deduct_balance(123456, 10000)
    assert deduct_success == True
    bal = await db.get_balance(123456)
    print("Wallet balance after deduction:", bal)
    assert bal == 5000

    # Try to deduct more than balance
    fail_deduct = await db.deduct_balance(123456, 20000)
    assert fail_deduct == False

    # 4. Support Tickets Testing
    tkt_id = await db.create_ticket(123456, "Hello, I need help with my connection.")
    print("Created support ticket ID:", tkt_id)
    assert tkt_id > 0

    pending_tkts = await db.get_pending_tickets()
    print("Pending tickets:", pending_tkts)
    assert len(pending_tkts) == 1
    assert pending_tkts[0][2] == "Hello, I need help with my connection."

    # Reply to ticket
    await db.reply_ticket(tkt_id, "We have fixed the server.")
    tkt = await db.get_ticket(tkt_id)
    print("Ticket after reply:", tkt)
    assert tkt[3] == "replied"
    assert tkt[4] == "We have fixed the server."

    # 5. Free Test Accounts Testing
    await db.add_test_account("VLESS-TEST-KEY-XYZ")
    count = await db.get_test_accounts_count()
    print("Available test accounts count:", count)
    assert count == 1

    # Pop trial first time
    test_key = await db.pop_test_account(123456)
    print("Popped test account:", test_key)
    assert test_key == "VLESS-TEST-KEY-XYZ"

    # Try to pop trial second time (should be blocked as already used)
    second_pop = await db.pop_test_account(123456)
    print("Second pop trial result:", second_pop)
    assert second_pop == "ALREADY_USED"

    # 6. Referral Connections and Rewards Testing
    print("Testing referral system...")
    await db.add_user(999, "referrer_user", "Referrer User")
    await db.add_user(888, "referred_user", "Referred User", referred_by=999)

    referrer = await db.get_user(999)
    referred = await db.get_user(888)

    assert referred[7] == 999  # referred_by should be 999

    ref_count = await db.get_referred_count(999)
    assert ref_count == 1

    # Create an order for referred user (with product_id = 123)
    await db.create_order("REFORD1", 888, 123, 50000, payment_method="card")
    await db.update_order_status("REFORD1", "approved")

    # Reward referrer
    reward_res = await db.reward_referrer_if_eligible("REFORD1")
    assert reward_res is not None
    ref_id, new_bal = reward_res
    assert ref_id == 999
    assert new_bal == 10000

    # Ensure duplicate reward is blocked
    second_reward_res = await db.reward_referrer_if_eligible("REFORD1")
    assert second_reward_res is None

    # Check database backup
    backup_file = "database/store_backup.db"
    if os.path.exists(backup_file):
        os.remove(backup_file)

    await db.backup(backup_file)
    assert os.path.exists(backup_file) == True
    print("Hot backup file generated successfully.")
    os.remove(backup_file)

    await db.disconnect()
    print("🎉 All upgraded asynchronous database tests passed successfully!")

if __name__ == "__main__":
    asyncio.run(test_db())
