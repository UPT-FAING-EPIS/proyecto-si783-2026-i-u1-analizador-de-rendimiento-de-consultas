"""Neo4j metrics extraction helper."""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class Neo4jMetricsHelper:
    """Helper for extracting metrics from Neo4j."""

    @staticmethod
    def get_db_stats(driver: Any) -> dict[str, Any]:
        """Get database statistics (node/relationship counts).

        Args:
            driver: Neo4j driver instance

        Returns:
            Dict with 'node_count', 'relationship_count', 'store_size'
        """
        try:
            with driver.session(database="neo4j") as session:
                # Get node count
                result_nodes = session.run("MATCH (n) RETURN count(n) as count")
                node_count = result_nodes.single()["count"] if result_nodes.single() else 0

                # Get relationship count
                result_rels = session.run("MATCH ()-[r]-() RETURN count(r) as count")
                rel_count = result_rels.single()["count"] if result_rels.single() else 0

                return {
                    "node_count": node_count,
                    "relationship_count": rel_count,
                }
        except Exception as e:
            logger.warning(f"Failed to get database stats: {e}")
            return {}

    @staticmethod
    def get_index_stats(driver: Any) -> dict[str, Any]:
        """Get index information and statistics.

        Args:
            driver: Neo4j driver instance

        Returns:
            Dict with index details
        """
        try:
            with driver.session(database="neo4j") as session:
                result = session.run(
                    """
                    CALL db.indexes() YIELD name, state, type, properties
                    RETURN collect({name: name, state: state, type: type,
                                   properties: properties}) as indexes
                    """
                )
                record = result.single()
                if record:
                    return {"indexes": record["indexes"]}
                return {"indexes": []}
        except Exception as e:
            logger.warning(f"Failed to get index stats: {e}")
            return {"indexes": []}

    @staticmethod
    def get_server_info(driver: Any) -> dict[str, Any]:
        """Get Neo4j server version and configuration.

        Args:
            driver: Neo4j driver instance

        Returns:
            Dict with 'version', 'server_address', etc.
        """
        try:
            with driver.session(database="neo4j") as session:
                result = session.run("RETURN dbms.version() as version")
                record = result.single()
                version = record["version"] if record else "unknown"

                # Get server address from driver
                driver_info = driver.get_server_info()
                server_address = driver_info.address if driver_info else "unknown"

                return {
                    "version": version,
                    "server_address": str(server_address),
                    "driver": "neo4j-python",
                }
        except Exception as e:
            logger.warning(f"Failed to get server info: {e}")
            return {
                "version": "unknown",
                "server_address": "unknown",
                "driver": "neo4j-python",
            }

    @staticmethod
    def get_memory_stats(driver: Any) -> dict[str, Any]:
        """Get JVM memory statistics (if available).

        Args:
            driver: Neo4j driver instance

        Returns:
            Dict with memory info or empty dict if unavailable
        """
        try:
            with driver.session(database="neo4j") as session:
                # Try to get memory info via JMX
                result = session.run(
                    """
                    CALL dbms.queryJmx('java.lang:type=Memory') YIELD attributes
                    RETURN attributes
                    """
                )
                # This may not be available in all Neo4j configurations
                record = result.single()
                if record:
                    return {"memory_info": "available"}
                return {}
        except Exception:
            # JMX queries may not be available
            return {}

    @staticmethod
    def check_constraint_available(driver: Any) -> bool:
        """Check if constraints can be queried.

        Args:
            driver: Neo4j driver instance

        Returns:
            True if constraints are available, False otherwise
        """
        try:
            with driver.session(database="neo4j") as session:
                session.run("CALL db.constraints() YIELD name LIMIT 1")
                return True
        except Exception:
            return False

    @staticmethod
    def get_label_stats(driver: Any) -> dict[str, Any]:
        """Get statistics about node labels.

        Args:
            driver: Neo4j driver instance

        Returns:
            Dict with label information
        """
        try:
            with driver.session(database="neo4j") as session:
                result = session.run(
                    """
                    CALL db.labels() YIELD label
                    MATCH (n:`label`)
                    RETURN label, count(n) as count
                    ORDER BY count DESC
                    """
                )
                labels = {}
                for record in result:
                    labels[record["label"]] = record["count"]
                return {"labels": labels}
        except Exception as e:
            logger.warning(f"Failed to get label stats: {e}")
            return {"labels": {}}
