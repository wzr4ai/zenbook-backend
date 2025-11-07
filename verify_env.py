import asyncio
import os

from dotenv import load_dotenv
import redis.asyncio as redis
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from src.core.database import resolve_async_database_url

# 1. 加载 .env 文件
load_dotenv()

DB_LABELS = {
    "postgresql": "PostgreSQL",
    "mysql": "MySQL",
    "sqlite": "SQLite (测试)",
}

HEALTH_QUERIES = {
    "postgresql": "SELECT version();",
    "mysql": "SELECT VERSION();",
}


async def verify_database():
    print("-" * 30)
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("❌ 错误: 未找到 DATABASE_URL 环境变量")
        return False

    try:
        async_url = resolve_async_database_url(db_url)
        url = make_url(async_url)
    except Exception as exc:  # noqa: BLE001 - surface clear setup errors
        print(f"❌ 数据库配置不支持: {exc}")
        return False

    backend = url.get_backend_name()
    label = DB_LABELS.get(backend, backend)
    print(f"🔍 正在验证 {label} 连接...")
    print(f"ℹ️  DSN: {url.render_as_string(hide_password=True)}")

    query = HEALTH_QUERIES.get(backend, "SELECT 1")

    try:
        engine = create_async_engine(async_url, echo=False)
        async with engine.connect() as conn:
            result = await conn.execute(text(query))
            version = result.scalar()
            print(f"✅ {label} 连接成功! 返回: {version}")
        await engine.dispose()
        return True
    except Exception as e:  # noqa: BLE001 - surface connection failure
        print(f"❌ {label} 连接失败: {e}")
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
    
    db_ok = await verify_database()
    redis_ok = await verify_redis()

    print("-" * 30)
    if db_ok and redis_ok:
        print("🎉 恭喜! 所有核心服务连接配置正确。")
    else:
        print("⚠️  警告: 存在连接问题，请检查 .env 文件和 Docker 容器状态。")

if __name__ == "__main__":
    asyncio.run(main())
