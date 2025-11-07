import asyncio
import os
from dotenv import load_dotenv
import sqlalchemy
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
import redis.asyncio as redis

# 1. 加载 .env 文件
load_dotenv()

async def verify_postgres():
    print("-" * 30)
    print("🔍 正在验证 PostgreSQL 连接...")
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("❌ 错误: 未找到 DATABASE_URL 环境变量")
        return False

    print(f"ℹ️  DATABASE_URL: {db_url.split('@')[-1]}") # 只显示主机部分，隐藏密码

    try:
        # 创建异步引擎 (与实际项目相同的连接方式)
        engine = create_async_engine(db_url, echo=False)
        async with engine.connect() as conn:
            # 执行一个简单的查询
            result = await conn.execute(text("SELECT version();"))
            version = result.scalar()
            print(f"✅ PostgreSQL 连接成功! 版本: {version}")
        await engine.dispose()
        return True
    except Exception as e:
        print(f"❌ PostgreSQL 连接失败: {e}")
        return False

async def verify_redis():
    print("-" * 30)
    print("🔍 正在验证 Redis 连接...")
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        print("❌ 错误: 未找到 REDIS_URL 环境变量")
        return False
        
    print(f"ℹ️  REDIS_URL: {redis_url.split('@')[-1]}") # 隐藏可能存在的密码

    try:
        # 尝试连接 Redis
        r = redis.from_url(redis_url, encoding="utf-8", decode_responses=True)
        if await r.ping():
             print("✅ Redis 连接成功! (PING 返回 PONG)")
        await r.aclose()
        return True
    except Exception as e:
        print(f"❌ Redis 连接失败: {e}")
        return False

async def main():
    print("🚀 开始环境配置验证...")
    
    pg_ok = await verify_postgres()
    redis_ok = await verify_redis()

    print("-" * 30)
    if pg_ok and redis_ok:
        print("🎉 恭喜! 所有核心服务连接配置正确。")
    else:
        print("⚠️  警告: 存在连接问题，请检查 .env 文件和 Docker 容器状态。")

if __name__ == "__main__":
    asyncio.run(main())