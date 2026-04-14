"""NoSQL Adapters - Drivers para bases de datos NoSQL (MongoDB, DynamoDB, etc)."""

from .dynamodb import DynamoDBAdapter
from .mongodb import MongoDBAdapter

__all__ = ["MongoDBAdapter", "DynamoDBAdapter"]
