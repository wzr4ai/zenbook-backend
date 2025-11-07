# ZenBook Backend API

ZenBook 的核心调度引擎。它提供了一套高效、异步的 RESTful API，用于处理复杂的预约可用性计算和资源竞争。

### 🛠️ 技术栈 (Tech Stack)

* **Framework**: FastAPI (Python 3.10+)
* **Database**: PostgreSQL (异步 asyncpg 驱动)
* **ORM**: SQLAlchemy 2.0 (Async)
* **Cache/Lock**: Redis (用于高性能可用性查询与分布式锁)
* **Authentication**: JWT (Role-based: Customer, Technician, Admin)

### 🎯 关键能力

* **⚡ 高性能可用性计算**：在毫秒级内计算出基于现有预约、排班规则和并发限制后的剩余可用时间槽（Time Slots）。
* **🔒 严谨的并发控制**：利用数据库事务与 Redis 锁防止超卖，确保在高并发预约场景下的数据一致性。
* **🧩 灵活的资源模型**：抽象了 `Technician` (资源), `Service` (服务能力), `Location` (场所) 三元组，适应多种业务形态。