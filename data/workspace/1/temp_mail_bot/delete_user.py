import sys
import asyncio
import aiosqlite
from database import DB_PATH, delete_user_completely, delete_user_email

async def main():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT user_id, username, email, provider, created_at FROM users") as cursor:
            users = await cursor.fetchall()
    
    if not users:
        print("Database me koi user nahi hai.")
        return

    print("\n--- Current Users in Database ---")
    for idx, u in enumerate(users, 1):
        print(f"[{idx}] User ID: {u['user_id']} | Username: @{u['username']} | Email: {u['email']} | Provider: {u['provider']}")

    target_id = None
    if len(sys.argv) > 1:
        try:
            target_id = int(sys.argv[1])
        except ValueError:
            print("Invalid User ID provided via CLI argument.")
            return
    else:
        # Prompt user or default to test / given user
        try:
            choice = input("\nKis user ko delete karna hai? (User ID ya [Index Number] dalein): ").strip()
            if not choice:
                return
            if choice.isdigit() and int(choice) <= len(users):
                target_id = users[int(choice) - 1]["user_id"]
            else:
                target_id = int(choice)
        except Exception:
            print("Action cancelled.")
            return

    if target_id:
        await delete_user_completely(target_id)
        print(f"\n[SUCCESS] User ID {target_id} ka poora data (User Record + Received Messages) delete kar diya gaya hai!")

if __name__ == "__main__":
    asyncio.run(main())
