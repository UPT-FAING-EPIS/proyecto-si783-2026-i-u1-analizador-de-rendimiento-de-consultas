"""DynamoDB query parser for performance analysis.

Parses JSON DynamoDB queries, extracts operation types (Query vs Scan),
detects anti-patterns, and handles ConsumedCapacity metrics from responses.
"""

import json
from typing import Any, Literal


class DynamoDBParser:
    """Parser for DynamoDB Query and Scan operations."""

    @staticmethod
    def parse_query_string(query_json: str) -> dict[str, Any]:
        """Parse JSON string to dict, validate it's valid JSON.

        Args:
            query_json: JSON string representing a DynamoDB Query or Scan

        Returns:
            Parsed dictionary with DynamoDB operation parameters

        Raises:
            ValueError: If JSON is invalid
            KeyError: If required fields are missing
        """
        try:
            query_dict = json.loads(query_json)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in query: {e}") from e

        if not isinstance(query_dict, dict):
            raise ValueError("Query must be a JSON object (dict)")

        if "TableName" not in query_dict:
            raise ValueError("Missing required field: TableName")

        return query_dict

    @staticmethod
    def extract_operation_type(query_dict: dict[str, Any]) -> Literal["Query", "Scan"]:
        """Determine if it's a Query or Scan operation.

        Logic:
        - Query: Has KeyConditionExpression
        - Scan: No KeyConditionExpression

        Args:
            query_dict: Parsed DynamoDB operation dictionary

        Returns:
            Either "Query" or "Scan"
        """
        if "KeyConditionExpression" in query_dict:
            return "Query"
        return "Scan"

    @staticmethod
    def extract_table_name(query_dict: dict[str, Any]) -> str:
        """Extract TableName from query.

        Args:
            query_dict: Parsed DynamoDB operation dictionary

        Returns:
            Table name string

        Raises:
            KeyError: If TableName is missing
        """
        table_name = query_dict["TableName"]
        if not isinstance(table_name, str):
            raise ValueError("TableName must be a string")
        return table_name

    @staticmethod
    def has_partition_key_condition(query_dict: dict[str, Any]) -> bool:
        """Check if KeyConditionExpression is present and valid.

        Args:
            query_dict: Parsed DynamoDB operation dictionary

        Returns:
            True if KeyConditionExpression exists, False otherwise
        """
        return "KeyConditionExpression" in query_dict

    @staticmethod
    def extract_consumed_capacity(response: dict[str, Any]) -> dict[str, Any]:
        """Extract ConsumedCapacity, Count, ScannedCount from boto3 response.

        Args:
            response: Response dict from boto3 DynamoDB client

        Returns:
            Dictionary with metrics:
                - read_capacity_units: float or 0
                - item_count: int or 0
                - scanned_count: int or 0
        """
        consumed_capacity = response.get("ConsumedCapacity", {})
        read_capacity_units = 0.0

        if isinstance(consumed_capacity, dict):
            read_capacity_units = consumed_capacity.get("CapacityUnits", 0.0)
        elif isinstance(consumed_capacity, (int, float)):
            read_capacity_units = float(consumed_capacity)

        return {
            "read_capacity_units": read_capacity_units,
            "item_count": response.get("Count", 0),
            "scanned_count": response.get("ScannedCount", 0),
        }

    @staticmethod
    def normalize_query(query_dict: dict[str, Any]) -> dict[str, Any]:
        """Standardize query structure for analysis.

        Ensures consistent structure and adds defaults for optional fields.

        Args:
            query_dict: Parsed DynamoDB operation dictionary

        Returns:
            Normalized query dict
        """
        normalized = query_dict.copy()

        # Ensure operation type is marked
        if "KeyConditionExpression" not in normalized:
            normalized["_operation_type"] = "Scan"
        else:
            normalized["_operation_type"] = "Query"

        # Ensure table name exists
        if "TableName" not in normalized:
            raise ValueError("TableName is required")

        return normalized
