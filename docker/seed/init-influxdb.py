#!/usr/bin/env python3
"""InfluxDB 2.x seed data initialization script.

Populates InfluxDB with realistic time-series data for query performance testing.
Creates multiple measurements with various tags and fields to simulate production data.

Data created:
- cpu: CPU usage metrics (100 points)
- memory: Memory usage metrics (100 points)
- disk: Disk I/O metrics (50 points)
- network: Network I/O metrics (100 points)
- query_latency: Query performance metrics (100 points)

Total: 450 data points across 5 measurements
"""

import logging
import os
import sys
from datetime import UTC, datetime, timedelta

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def create_influxdb_data() -> None:
    """Create and write sample time-series data to InfluxDB 2.x."""
    try:
        from influxdb_client import InfluxDBClient, Point
        from influxdb_client.client.write_api import SYNCHRONOUS
    except ImportError:
        logger.error("influxdb-client not installed. Run: pip install influxdb-client")
        sys.exit(1)

    # Get connection parameters from environment or defaults
    host = os.getenv("INFLUXDB_HOST", "localhost")
    port = int(os.getenv("INFLUXDB_PORT", "8086"))
    token = os.getenv("INFLUXDB_TOKEN", "mytoken")
    org = os.getenv("INFLUXDB_ORG", "myorg")
    bucket = os.getenv("INFLUXDB_BUCKET", "query_analyzer")

    url = f"http://{host}:{port}"

    logger.info(f"Connecting to InfluxDB at {url}")

    try:
        client = InfluxDBClient(url=url, token=token, org=org)

        # Test connection
        health = client.health()
        if health.status != "pass":
            logger.error(f"InfluxDB health check failed: {health.message}")
            sys.exit(1)

        logger.info("✅ Connected to InfluxDB")

        write_api = client.write_api(write_options=SYNCHRONOUS)

        # Data generation
        now = datetime.now(UTC)
        points = []

        logger.info("Generating time-series data...")

        # 1. CPU metrics (100 points over 100 minutes)
        logger.info("  - Generating CPU metrics (100 points)...")
        for i in range(100):
            timestamp = now - timedelta(minutes=100 - i)
            host_id = f"host-{(i % 3) + 1}"
            region = ["us-east", "us-west", "eu-central"][i % 3]

            points.append(
                Point("cpu")
                .tag("host", host_id)
                .tag("region", region)
                .field("usage_percent", 30.0 + (i % 40))
                .field("temp_celsius", 45.0 + (i % 25))
                .time(timestamp)
            )

        # 2. Memory metrics (100 points over 100 minutes)
        logger.info("  - Generating Memory metrics (100 points)...")
        for i in range(100):
            timestamp = now - timedelta(minutes=100 - i)
            host_id = f"host-{(i % 3) + 1}"
            mem_type = ["ddr4", "ddr5"][i % 2]

            points.append(
                Point("memory")
                .tag("host", host_id)
                .tag("type", mem_type)
                .field("bytes", 2048 * 1024 * 1024 + (i * 1024 * 1024))
                .field("percent", 40.0 + (i % 30))
                .time(timestamp)
            )

        # 3. Disk metrics (50 points over 100 minutes)
        logger.info("  - Generating Disk metrics (50 points)...")
        for i in range(50):
            timestamp = now - timedelta(minutes=100 - i * 2)
            host_id = f"host-{(i % 3) + 1}"
            mount = ["/", "/data", "/var"][i % 3]

            points.append(
                Point("disk")
                .tag("host", host_id)
                .tag("mount", mount)
                .field("used_bytes", 100 * 1024 * 1024 * 1024 + (i * 1024 * 1024))
                .field("free_bytes", 50 * 1024 * 1024 * 1024 - (i * 1024 * 1024))
                .time(timestamp)
            )

        # 4. Network metrics (100 points over 100 minutes)
        logger.info("  - Generating Network metrics (100 points)...")
        for i in range(100):
            timestamp = now - timedelta(minutes=100 - i)
            host_id = f"host-{(i % 3) + 1}"
            interface = ["eth0", "eth1", "wlan0"][(i // 2) % 3]

            points.append(
                Point("network")
                .tag("host", host_id)
                .tag("interface", interface)
                .field("bytes_in", 1000000 + (i * 5000))
                .field("bytes_out", 500000 + (i * 2500))
                .field("packets_in", 1000 + i)
                .field("packets_out", 500 + (i // 2))
                .time(timestamp)
            )

        # 5. Query latency metrics (100 points over 100 minutes)
        logger.info("  - Generating Query Latency metrics (100 points)...")
        for i in range(100):
            timestamp = now - timedelta(minutes=100 - i)
            query_type = ["SELECT", "INSERT", "UPDATE"][(i // 2) % 3]
            database = ["postgres", "mysql", "influxdb"][(i // 3) % 3]

            points.append(
                Point("query_latency")
                .tag("query_type", query_type)
                .tag("database", database)
                .field("latency_ms", 10.0 + (i % 100))
                .field("rows_affected", 100 + (i * 2))
                .time(timestamp)
            )

        logger.info(f"Total points to write: {len(points)}")

        # Write all points to InfluxDB
        logger.info(f"Writing {len(points)} points to bucket '{bucket}'...")
        write_api.write(bucket=bucket, org=org, records=points)

        logger.info("✅ Successfully wrote all data points to InfluxDB")

        # Verify data was written
        try:
            query_api = client.query_api()
            query = f'from(bucket:"{bucket}") |> range(start: -1000m) |> count()'

            result = query_api.query(query, org=org)

            total_records = 0
            for table in result:
                for record in table.records:
                    total_records = record.values.get("_value", 0)

            logger.info(f"✅ Verification: {total_records} records in InfluxDB")
        except Exception as verify_error:
            logger.warning(f"⚠️  Verification query failed (non-critical): {verify_error}")

        client.close()
        logger.info("✅ Connection closed successfully")

    except Exception as e:
        logger.error(f"❌ Error writing data to InfluxDB: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    create_influxdb_data()
