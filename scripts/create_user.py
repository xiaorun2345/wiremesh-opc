"""
创建用户脚本

用法：
    python scripts/create_user.py --username admin --password yourpassword
"""
import sys
import asyncio
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


async def main():
    parser = argparse.ArgumentParser(description="创建 OpenSpec 用户")
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    args = parser.parse_args()

    from app.utils.db import init_db, AsyncSessionLocal
    from app.utils.auth import hash_password
    from app.models.user import User
    from sqlalchemy import select
    import uuid

    await init_db()

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.username == args.username))
        if result.scalar_one_or_none():
            print(f"用户 '{args.username}' 已存在")
            return

        user = User(
            id=str(uuid.uuid4()),
            username=args.username,
            password_hash=hash_password(args.password),
        )
        db.add(user)
        await db.commit()
        print(f"用户 '{args.username}' 创建成功，ID: {user.id}")


if __name__ == "__main__":
    asyncio.run(main())
