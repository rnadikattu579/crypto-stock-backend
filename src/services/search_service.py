"""
Global Search Service
Provides search across assets, transactions, and notes
"""
import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Any, Optional
import uuid

from boto3.dynamodb.conditions import Key, Attr
from utils.db import get_table

logger = logging.getLogger()


class SearchService:
    """Service for global search and filtering"""

    def global_search(
        self,
        user_id: str,
        query: str,
        search_types: Optional[List[str]] = None,
        limit: int = 50
    ) -> Dict[str, Any]:
        """
        Search across assets, transactions, and notes

        Args:
            user_id: User ID
            query: Search query string
            search_types: List of types to search ('assets', 'transactions', 'goals')
            limit: Maximum results per type
        """
        if not query:
            return {
                'status': 'error',
                'message': 'Search query is required'
            }

        query_lower = query.lower()
        search_types = search_types or ['assets', 'transactions', 'goals']

        results = {
            'assets': [],
            'transactions': [],
            'goals': [],
            'total_results': 0
        }

        table = get_table()

        # Search assets
        if 'assets' in search_types:
            asset_results = self._search_assets(table, user_id, query_lower, limit)
            results['assets'] = asset_results

        # Search transactions
        if 'transactions' in search_types:
            transaction_results = self._search_transactions(table, user_id, query_lower, limit)
            results['transactions'] = transaction_results

        # Search goals
        if 'goals' in search_types:
            goal_results = self._search_goals(table, user_id, query_lower, limit)
            results['goals'] = goal_results

        results['total_results'] = (
            len(results['assets']) +
            len(results['transactions']) +
            len(results['goals'])
        )

        return {
            'status': 'success',
            'query': query,
            'results': results
        }

    def _search_assets(self, table, user_id: str, query: str, limit: int) -> List[Dict]:
        """Search assets by symbol or name"""
        response = table.query(
            KeyConditionExpression=Key('PK').eq(f'USER#{user_id}') & Key('SK').begins_with('ASSET#')
        )

        results = []
        for item in response.get('Items', []):
            symbol = item.get('symbol', '').lower()
            name = (item.get('name') or '').lower()

            if query in symbol or query in name:
                results.append({
                    'asset_id': item.get('asset_id'),
                    'symbol': item.get('symbol'),
                    'name': item.get('name'),
                    'asset_type': item.get('asset_type'),
                    'quantity': float(item.get('quantity', 0)),
                    'match_field': 'symbol' if query in symbol else 'name'
                })

            if len(results) >= limit:
                break

        return results

    def _search_transactions(self, table, user_id: str, query: str, limit: int) -> List[Dict]:
        """Search transactions by symbol or notes"""
        response = table.query(
            KeyConditionExpression=Key('PK').eq(f'USER#{user_id}') & Key('SK').begins_with('TRANSACTION#')
        )

        results = []
        for item in response.get('Items', []):
            symbol = item.get('symbol', '').lower()
            notes = (item.get('notes') or '').lower()

            if query in symbol or query in notes:
                results.append({
                    'transaction_id': item.get('transaction_id'),
                    'symbol': item.get('symbol'),
                    'transaction_type': item.get('transaction_type'),
                    'quantity': float(item.get('quantity', 0)),
                    'price': float(item.get('price', 0)),
                    'transaction_date': item.get('transaction_date'),
                    'notes': item.get('notes'),
                    'match_field': 'symbol' if query in symbol else 'notes'
                })

            if len(results) >= limit:
                break

        return results

    def _search_goals(self, table, user_id: str, query: str, limit: int) -> List[Dict]:
        """Search goals by name or notes"""
        response = table.query(
            KeyConditionExpression=Key('PK').eq(f'USER#{user_id}') & Key('SK').begins_with('GOAL#')
        )

        results = []
        for item in response.get('Items', []):
            goal_name = item.get('goal_name', '').lower()
            notes = (item.get('notes') or '').lower()

            if query in goal_name or query in notes:
                results.append({
                    'goal_id': item.get('goal_id'),
                    'goal_name': item.get('goal_name'),
                    'target_amount': float(item.get('target_amount', 0)),
                    'target_date': item.get('target_date'),
                    'match_field': 'goal_name' if query in goal_name else 'notes'
                })

            if len(results) >= limit:
                break

        return results

    def save_filter(
        self,
        user_id: str,
        filter_name: str,
        filter_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Save a custom filter configuration"""
        table = get_table()
        filter_id = str(uuid.uuid4())

        item = {
            'PK': f'USER#{user_id}',
            'SK': f'FILTER#{filter_id}',
            'filter_id': filter_id,
            'user_id': user_id,
            'filter_name': filter_name,
            'filter_config': filter_config,
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat()
        }

        table.put_item(Item=item)

        return {
            'status': 'success',
            'filter': {
                'filter_id': filter_id,
                'filter_name': filter_name,
                'filter_config': filter_config
            }
        }

    def get_saved_filters(self, user_id: str) -> Dict[str, Any]:
        """Get all saved filters for a user"""
        table = get_table()

        response = table.query(
            KeyConditionExpression=Key('PK').eq(f'USER#{user_id}') & Key('SK').begins_with('FILTER#')
        )

        filters = []
        for item in response.get('Items', []):
            filters.append({
                'filter_id': item.get('filter_id'),
                'filter_name': item.get('filter_name'),
                'filter_config': item.get('filter_config', {}),
                'created_at': item.get('created_at')
            })

        return {
            'status': 'success',
            'filters': filters
        }

    def delete_filter(self, user_id: str, filter_id: str) -> Dict[str, Any]:
        """Delete a saved filter"""
        table = get_table()

        table.delete_item(
            Key={
                'PK': f'USER#{user_id}',
                'SK': f'FILTER#{filter_id}'
            }
        )

        return {'status': 'success', 'message': 'Filter deleted'}

    def add_tag(
        self,
        user_id: str,
        asset_id: str,
        tag: str
    ) -> Dict[str, Any]:
        """Add a tag to an asset"""
        table = get_table()

        # Get current asset
        response = table.get_item(
            Key={
                'PK': f'USER#{user_id}',
                'SK': f'ASSET#{asset_id}'
            }
        )

        if 'Item' not in response:
            return {'status': 'error', 'message': 'Asset not found'}

        item = response['Item']
        tags = item.get('tags', [])

        if tag not in tags:
            tags.append(tag)

        # Update asset with new tag
        table.update_item(
            Key={
                'PK': f'USER#{user_id}',
                'SK': f'ASSET#{asset_id}'
            },
            UpdateExpression='SET tags = :tags, updated_at = :updated_at',
            ExpressionAttributeValues={
                ':tags': tags,
                ':updated_at': datetime.utcnow().isoformat()
            }
        )

        return {
            'status': 'success',
            'asset_id': asset_id,
            'tags': tags
        }

    def remove_tag(
        self,
        user_id: str,
        asset_id: str,
        tag: str
    ) -> Dict[str, Any]:
        """Remove a tag from an asset"""
        table = get_table()

        # Get current asset
        response = table.get_item(
            Key={
                'PK': f'USER#{user_id}',
                'SK': f'ASSET#{asset_id}'
            }
        )

        if 'Item' not in response:
            return {'status': 'error', 'message': 'Asset not found'}

        item = response['Item']
        tags = item.get('tags', [])

        if tag in tags:
            tags.remove(tag)

        # Update asset
        table.update_item(
            Key={
                'PK': f'USER#{user_id}',
                'SK': f'ASSET#{asset_id}'
            },
            UpdateExpression='SET tags = :tags, updated_at = :updated_at',
            ExpressionAttributeValues={
                ':tags': tags,
                ':updated_at': datetime.utcnow().isoformat()
            }
        )

        return {
            'status': 'success',
            'asset_id': asset_id,
            'tags': tags
        }

    def get_assets_by_tag(self, user_id: str, tag: str) -> Dict[str, Any]:
        """Get all assets with a specific tag"""
        table = get_table()

        response = table.query(
            KeyConditionExpression=Key('PK').eq(f'USER#{user_id}') & Key('SK').begins_with('ASSET#')
        )

        assets = []
        for item in response.get('Items', []):
            tags = item.get('tags', [])
            if tag in tags:
                assets.append({
                    'asset_id': item.get('asset_id'),
                    'symbol': item.get('symbol'),
                    'name': item.get('name'),
                    'asset_type': item.get('asset_type'),
                    'quantity': float(item.get('quantity', 0)),
                    'tags': tags
                })

        return {
            'status': 'success',
            'tag': tag,
            'assets': assets
        }

    def get_all_tags(self, user_id: str) -> Dict[str, Any]:
        """Get all unique tags used by a user"""
        table = get_table()

        response = table.query(
            KeyConditionExpression=Key('PK').eq(f'USER#{user_id}') & Key('SK').begins_with('ASSET#')
        )

        tags_count = {}
        for item in response.get('Items', []):
            tags = item.get('tags', [])
            for tag in tags:
                tags_count[tag] = tags_count.get(tag, 0) + 1

        tags_list = [
            {'tag': tag, 'count': count}
            for tag, count in sorted(tags_count.items(), key=lambda x: -x[1])
        ]

        return {
            'status': 'success',
            'tags': tags_list
        }

    def quick_filter(
        self,
        user_id: str,
        filter_type: str
    ) -> Dict[str, Any]:
        """
        Apply quick filters

        filter_type options:
        - profitable: Assets with positive gain
        - losers: Assets with negative gain
        - recent: Recently purchased (last 30 days)
        - crypto: Only crypto assets
        - stocks: Only stock assets
        - high_value: Top 10 by value
        """
        table = get_table()

        response = table.query(
            KeyConditionExpression=Key('PK').eq(f'USER#{user_id}') & Key('SK').begins_with('ASSET#')
        )

        assets = []
        for item in response.get('Items', []):
            quantity = float(item.get('quantity', 0))
            purchase_price = float(item.get('purchase_price', 0))
            current_price = float(item.get('current_price', purchase_price))
            current_value = quantity * current_price
            invested = quantity * purchase_price
            gain_loss = current_value - invested
            gain_loss_pct = (gain_loss / invested * 100) if invested > 0 else 0

            asset = {
                'asset_id': item.get('asset_id'),
                'symbol': item.get('symbol'),
                'name': item.get('name'),
                'asset_type': item.get('asset_type'),
                'quantity': quantity,
                'current_value': current_value,
                'gain_loss': gain_loss,
                'gain_loss_percentage': gain_loss_pct,
                'purchase_date': item.get('purchase_date'),
                'tags': item.get('tags', [])
            }
            assets.append(asset)

        # Apply filter
        if filter_type == 'profitable':
            assets = [a for a in assets if a['gain_loss'] > 0]
            assets.sort(key=lambda x: -x['gain_loss_percentage'])
        elif filter_type == 'losers':
            assets = [a for a in assets if a['gain_loss'] < 0]
            assets.sort(key=lambda x: x['gain_loss_percentage'])
        elif filter_type == 'recent':
            thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            assets = [a for a in assets if a.get('purchase_date', '') >= thirty_days_ago]
            assets.sort(key=lambda x: x.get('purchase_date', ''), reverse=True)
        elif filter_type == 'crypto':
            assets = [a for a in assets if a['asset_type'] == 'crypto']
        elif filter_type == 'stocks':
            assets = [a for a in assets if a['asset_type'] == 'stock']
        elif filter_type == 'high_value':
            assets.sort(key=lambda x: -x['current_value'])
            assets = assets[:10]

        return {
            'status': 'success',
            'filter_type': filter_type,
            'assets': assets,
            'count': len(assets)
        }


# Import timedelta for quick_filter
from datetime import timedelta

search_service = SearchService()
