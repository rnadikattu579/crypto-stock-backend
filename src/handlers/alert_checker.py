"""
Alert Checker Lambda Function
Runs periodically to check all active alerts and trigger notifications
"""
import json
import logging
from typing import Dict, Any

from services.alerts_service import alerts_service
from services.dynamodb_service import DynamoDBService

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Scheduled handler that checks all alerts
    Runs every 15 minutes via EventBridge
    """
    logger.info("Alert checker started")

    try:
        # Get all unique user IDs with active alerts
        db_service = DynamoDBService()
        user_ids = set()

        # Scan for all alert items
        scan_params = {
            'FilterExpression': 'entity_type = :entity_type AND #status = :status',
            'ExpressionAttributeNames': {
                '#status': 'status'
            },
            'ExpressionAttributeValues': {
                ':entity_type': 'alert',
                ':status': 'active'
            }
        }

        while True:
            response = db_service.table.scan(**scan_params)

            for item in response.get('Items', []):
                user_ids.add(item.get('user_id'))

            # Check if there are more items
            if 'LastEvaluatedKey' not in response:
                break
            scan_params['ExclusiveStartKey'] = response['LastEvaluatedKey']

        logger.info(f"Found {len(user_ids)} users with active alerts")

        # Check alerts for each user
        total_checked = 0
        total_triggered = 0

        for user_id in user_ids:
            try:
                triggered = alerts_service.check_all_alerts_for_user(user_id)
                total_triggered += len(triggered)

                # Get count of alerts checked
                alerts = alerts_service.list_alerts(user_id).alerts
                total_checked += len(alerts)

                if triggered:
                    logger.info(f"Triggered {len(triggered)} alerts for user {user_id}")

            except Exception as user_error:
                logger.error(f"Error checking alerts for user {user_id}: {str(user_error)}")
                continue

        result = {
            'success': True,
            'users_checked': len(user_ids),
            'alerts_checked': total_checked,
            'alerts_triggered': total_triggered,
            'message': f'Checked {total_checked} alerts for {len(user_ids)} users, triggered {total_triggered} alerts'
        }

        logger.info(f"Alert checker completed: {json.dumps(result)}")
        return result

    except Exception as e:
        logger.error(f"Error in alert checker: {str(e)}", exc_info=True)
        return {
            'success': False,
            'error': str(e)
        }
