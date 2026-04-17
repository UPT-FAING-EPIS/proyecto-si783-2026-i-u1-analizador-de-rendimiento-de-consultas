#!/usr/bin/env python3
"""Redis seed script - Populates Redis with test data for query analyzer.

This script demonstrates various Redis data structures and patterns:
- Strings: Simple key-value pairs
- Hashes: Structured objects
- Lists: Ordered collections
- Sets: Unique collections
- Sorted Sets: Ranked data with scores
- Expires: TTL (time-to-live) for temporary keys

Patterns designed to demonstrate:
1. Performance characteristics (O(1) vs O(N) operations)
2. Memory usage patterns
3. Dangerous command detection (FLUSHDB, KEYS, SMEMBERS, etc.)
"""

import os
import sys
import time
from datetime import datetime

import redis

# Fix for Windows encoding issues
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Redis connection configuration (matches docker-compose.yml)
REDIS_HOST = "localhost"
REDIS_PORT = int(os.environ.get("DB_REDIS_PORT", "6379"))
REDIS_DB = 0


def connect_redis() -> redis.Redis:
    """Connect to Redis with retry logic."""
    for attempt in range(5):
        try:
            client = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=REDIS_DB,
                decode_responses=True,
                socket_timeout=5,
            )
            client.ping()
            print(f"[OK] Connected to Redis at {REDIS_HOST}:{REDIS_PORT}")
            return client
        except Exception:
            print(f"[RETRY] Attempt {attempt + 1}/5: Connection failed, retrying...")
            time.sleep(2)

    raise Exception("Failed to connect to Redis after 5 attempts")


def seed_strings(r: redis.Redis) -> None:
    """Populate string keys for basic testing."""
    print("\n[SEED] Seeding String keys...")

    # Simple key-value pairs (different sizes)
    strings = {
        "key:simple": "value",
        "key:medium": "This is a medium-length value for testing query analysis " * 2,
        "key:large": "Large value: " + "x" * 1000,
        "config:api_key": "sk-1234567890abcdef",
        "config:db_host": "db.example.com",
        "cache:user:1001": '{"id": 1001, "name": "Alice", "email": "alice@example.com"}',
        "cache:user:1002": '{"id": 1002, "name": "Bob", "email": "bob@example.com"}',
        "counter:requests": "42",
        "counter:errors": "5",
        "session:sess_abc123": "user_id=1001&auth_token=xyz789",
    }

    for key, value in strings.items():
        r.set(key, value)

    print(f"[OK] Created {len(strings)} string keys")


def seed_hashes(r: redis.Redis) -> None:
    """Populate hash keys (structured objects)."""
    print("\n[SEED] Seeding Hash keys (objects)...")

    # User profiles
    for i in range(1, 11):
        r.hset(
            f"user:{i:03d}",
            mapping={
                "id": str(i),
                "username": f"user{i}",
                "email": f"user{i}@example.com",
                "created_at": datetime.now().isoformat(),
                "last_login": datetime.now().isoformat(),
                "active": "true" if i % 2 == 0 else "false",
            },
        )

    # Product data
    for i in range(1, 6):
        r.hset(
            f"product:{i:03d}",
            mapping={
                "id": str(i),
                "name": f"Product {i}",
                "price": str(9.99 * i),
                "stock": str(100 - i * 10),
                "category": ["Electronics", "Clothing", "Books", "Food", "Toys"][i - 1],
            },
        )

    print("[OK] Created 15 hash keys (10 users + 5 products)")


def seed_lists(r: redis.Redis) -> None:
    """Populate list keys (ordered collections)."""
    print("\n[SEED] Seeding List keys...")

    # Event logs (most recent first with LPUSH)
    events = [
        "user_login:1001",
        "order_created:5001",
        "payment_processed:5001",
        "user_logout:1001",
        "query_executed:SELECT * FROM large_table",
        "index_updated:orders_idx",
        "backup_completed",
        "error_occurred:timeout",
    ]

    for event in events:
        r.lpush("events:log", event)

    # Queue for processing
    tasks = ["task:1", "task:2", "task:3", "task:4", "task:5"]
    for task in tasks:
        r.rpush("queue:pending", task)

    # Leaderboard (similar to sorted set, but using lists)
    r.rpush("feed:user:1001", "post:101", "post:102", "post:103", "post:104", "post:105")

    print("[OK] Created 3 list keys (events, queue, feed)")


def seed_sets(r: redis.Redis) -> None:
    """Populate set keys (unique collections)."""
    print("\n[SEED] Seeding Set keys...")

    # User tags/interests
    r.sadd("tags:user:1001", "python", "redis", "docker", "performance")
    r.sadd("tags:user:1002", "java", "sql", "kubernetes")
    r.sadd("tags:user:1003", "python", "golang", "performance", "devops")

    # Active sessions
    active_sessions = [f"session:{i:03d}" for i in range(1, 21)]
    r.sadd("sessions:active", *active_sessions)

    # Unique IP addresses
    ips = ["192.168.1.1", "192.168.1.2", "192.168.1.3", "10.0.0.1", "10.0.0.2"]
    r.sadd("ips:whitelist", *ips)

    # Feature flags enabled
    r.sadd("features:enabled", "feature_new_ui", "feature_analytics", "feature_beta")

    print("[OK] Created 6 set keys (tags, sessions, IPs, features)")


def seed_sorted_sets(r: redis.Redis) -> None:
    """Populate sorted set keys (ranked data)."""
    print("\n[SEED] Seeding Sorted Set keys...")

    # Leaderboard (user scores)
    scores: dict[str, float] = {
        "user:1001": 1000.0,
        "user:1002": 850.0,
        "user:1003": 920.0,
        "user:1004": 780.0,
        "user:1005": 1050.0,
    }
    r.zadd("leaderboard:scores", scores)  # type: ignore[arg-type]

    # Trending posts (by views, most recent first)
    trending: dict[str, float] = {
        "post:101": 5000.0,
        "post:102": 4200.0,
        "post:103": 3800.0,
        "post:104": 2100.0,
        "post:105": 1900.0,
    }
    r.zadd("trending:posts:views", trending)  # type: ignore[arg-type]

    # Hot keys by access frequency
    hotkeys: dict[str, float] = {
        "cache:user:1001": 2500.0,
        "cache:user:1002": 2100.0,
        "config:api_key": 1800.0,
        "counter:requests": 1500.0,
    }
    r.zadd("hotkeys:frequency", hotkeys)  # type: ignore[arg-type]

    print("[OK] Created 3 sorted set keys (leaderboard, trending, hotkeys)")


def seed_with_expiry(r: redis.Redis) -> None:
    """Populate keys with TTL (expiry)."""
    print("\n[SEED] Seeding keys with TTL...")

    # Session tokens (expire in 1 hour)
    r.setex("token:user:1001", 3600, "auth_token_1001_xyz")
    r.setex("token:user:1002", 3600, "auth_token_1002_abc")

    # OTP codes (expire in 5 minutes)
    r.setex("otp:1001", 300, "123456")
    r.setex("otp:1002", 300, "654321")

    # Rate limit counters (expire in 1 minute)
    for i in range(1, 4):
        r.setex(f"ratelimit:ip:192.168.1.{i}", 60, str(i * 10))

    # Cache with 30 seconds TTL
    r.setex("cache:expensive_query", 30, '{"result": "cached_data"}')

    print("[OK] Created 8 keys with expiry/TTL")


def seed_performance_patterns(r: redis.Redis) -> None:
    """Create patterns that demonstrate performance characteristics."""
    print("\n[SEED] Seeding performance test patterns...")

    # O(1) operations - Direct key access (fast)
    r.set("perf:o1:lookup", "Fast - direct key access")

    # O(N) operations - Full collection scan
    # SMEMBERS, KEYS, LRANGE etc. are O(N)
    large_set = [f"item:{i:05d}" for i in range(1, 501)]
    r.sadd("perf:on:large_set", *large_set)

    # Large sorted set (good for range queries)
    large_zset: dict[str, float] = {f"item:{i:05d}": float(i) for i in range(1, 501)}
    r.zadd("perf:on:large_zset", large_zset)  # type: ignore[arg-type]

    print("[OK] Created performance pattern keys (1 O(1) + 2 O(N) with 500 members)")


def seed_dangerous_patterns(r: redis.Redis) -> None:
    """Create patterns that trigger dangerous command warnings."""
    print("\n[SEED] Seeding dangerous command patterns...")

    # Keys that might be scanned with KEYS command
    r.set("dangerous:pattern:1", "value1")
    r.set("dangerous:pattern:2", "value2")
    r.set("dangerous:pattern:3", "value3")

    # Collection for SMEMBERS demonstration
    r.sadd("dangerous:collection", *[f"member_{i}" for i in range(1, 101)])

    # Large list for LRANGE * demonstration
    r.rpush("dangerous:list", *[f"item_{i}" for i in range(1, 101)])

    print("[OK] Created dangerous command pattern keys")


def verify_seeding(r: redis.Redis) -> None:
    """Verify that seeding was successful."""
    print("\n[VERIFY] Verification:")

    # Count keys
    total_keys = r.dbsize()

    print(f"   Total keys in database: {total_keys}")

    # Sample keys by pattern
    patterns = ["key:*", "cache:*", "user:*", "product:*", "perf:*", "token:*"]
    for pattern in patterns:
        count = len(r.keys(pattern))
        if count > 0:
            print(f"   - {pattern}: {count} keys")

    # Show server info
    server_info = r.info("server")
    print(f"   Redis version: {server_info.get('redis_version', 'unknown')}")
    print(f"   Connected clients: {r.info('clients').get('connected_clients', 0)}")


if __name__ == "__main__":
    try:
        # Connect to Redis
        redis_client = connect_redis()

        # Clear existing data for clean seed
        redis_client.flushdb()
        print("[CLEAR] Cleared existing data from Redis")

        # Seed different data structures
        seed_strings(redis_client)
        seed_hashes(redis_client)
        seed_lists(redis_client)
        seed_sets(redis_client)
        seed_sorted_sets(redis_client)
        seed_with_expiry(redis_client)
        seed_performance_patterns(redis_client)
        seed_dangerous_patterns(redis_client)

        # Verify
        verify_seeding(redis_client)

        print("\n[SUCCESS] Redis seeding completed successfully!")
        redis_client.close()

    except Exception as e:
        print(f"\n[ERROR] Error during seeding: {e}")
        sys.exit(1)
