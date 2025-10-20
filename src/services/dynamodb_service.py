import boto3
import os
from typing import Dict, List, Optional, Any
from datetime import datetime
from decimal import Decimal


class DynamoDBService:
    def __init__(self):
        self.dynamodb = boto3.resource('dynamodb')
        self.table_name = os.environ.get('DYNAMODB_TABLE', 'portfolio-tracker')
        self.table = self.dynamodb.Table(self.table_name)

    def _serialize_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Convert floats to Decimals for DynamoDB"""
        serialized = {}
        for key, value in item.items():
            if isinstance(value, float):
                serialized[key] = Decimal(str(value))
            elif isinstance(value, dict):
                serialized[key] = self._serialize_item(value)
            elif isinstance(value, list):
                serialized[key] = [self._serialize_item(v) if isinstance(v, dict) else v for v in value]
            elif isinstance(value, datetime):
                serialized[key] = value.isoformat()
            else:
                serialized[key] = value
        return serialized

    def _deserialize_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Convert Decimals back to floats"""
        deserialized = {}
        for key, value in item.items():
            if isinstance(value, Decimal):
                deserialized[key] = float(value)
            elif isinstance(value, dict):
                deserialized[key] = self._deserialize_item(value)
            elif isinstance(value, list):
                deserialized[key] = [self._deserialize_item(v) if isinstance(v, dict) else v for v in value]
            else:
                deserialized[key] = value
        return deserialized

    def put_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Insert or update an item"""
        serialized = self._serialize_item(item)
        self.table.put_item(Item=serialized)
        return item

    def get_item(self, pk: str, sk: str) -> Optional[Dict[str, Any]]:
        """Get a single item by primary key"""
        response = self.table.get_item(Key={'PK': pk, 'SK': sk})
        item = response.get('Item')
        return self._deserialize_item(item) if item else None

    def query(self, pk: str, sk_prefix: Optional[str] = None) -> List[Dict[str, Any]]:
        """Query items by partition key and optional sort key prefix"""
        if sk_prefix:
            response = self.table.query(
                KeyConditionExpression='PK = :pk AND begins_with(SK, :sk)',
                ExpressionAttributeValues={':pk': pk, ':sk': sk_prefix}
            )
        else:
            response = self.table.query(
                KeyConditionExpression='PK = :pk',
                ExpressionAttributeValues={':pk': pk}
            )

        items = response.get('Items', [])
        return [self._deserialize_item(item) for item in items]

    def query_gsi(self, gsi_name: str, gsi_pk: str, gsi_sk_prefix: Optional[str] = None) -> List[Dict[str, Any]]:
        """Query GSI by partition key and optional sort key prefix"""
        if gsi_sk_prefix:
            response = self.table.query(
                IndexName=gsi_name,
                KeyConditionExpression='GSI1PK = :pk AND begins_with(GSI1SK, :sk)',
                ExpressionAttributeValues={':pk': gsi_pk, ':sk': gsi_sk_prefix}
            )
        else:
            response = self.table.query(
                IndexName=gsi_name,
                KeyConditionExpression='GSI1PK = :pk',
                ExpressionAttributeValues={':pk': gsi_pk}
            )

        items = response.get('Items', [])
        return [self._deserialize_item(item) for item in items]

    def delete_item(self, pk: str, sk: str) -> None:
        """Delete an item"""
        self.table.delete_item(Key={'PK': pk, 'SK': sk})

    def update_item(self, pk: str, sk: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update specific attributes of an item"""
        serialized = self._serialize_item(updates)

        update_expression = "SET " + ", ".join([f"#{k} = :{k}" for k in serialized.keys()])
        expression_attribute_names = {f"#{k}": k for k in serialized.keys()}
        expression_attribute_values = {f":{k}": v for k, v in serialized.items()}

        response = self.table.update_item(
            Key={'PK': pk, 'SK': sk},
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expression_attribute_names,
            ExpressionAttributeValues=expression_attribute_values,
            ReturnValues='ALL_NEW'
        )

        return self._deserialize_item(response['Attributes'])
