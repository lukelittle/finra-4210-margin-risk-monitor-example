"""
Margin Enforcement Lambda

Consumes margin and stress events from Kafka.
Applies enforcement ladder logic.
Emits control events and audit trail.
"""

import json
import os
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import boto3
from kafka import KafkaProducer

# Configuration
KAFKA_BROKERS = os.getenv('KAFKA_BROKERS', 'localhost:9092')
DYNAMODB_TABLE = os.getenv('DYNAMODB_TABLE', 'margin-risk-state')
S3_BUCKET = os.getenv('S3_AUDIT_BUCKET', 'margin-risk-audit')

# Thresholds
WARNING_THRESHOLD_PCT = 0.05  # Warn if excess < 5% of MV
ESCALATION_MINUTES = 30  # Escalate to restriction after 30 minutes
SEVERE_STRESS_THRESHOLD = 0.06  # Consider SPY moves >= 6% as severe

# AWS clients
dynamodb = boto3.resource('dynamodb')
s3 = boto3.client('s3')
table = dynamodb.Table(DYNAMODB_TABLE)

# Kafka producer
producer = None


def get_producer():
    """Get or create Kafka producer."""
    global producer
    if producer is None:
        producer = KafkaProducer(
            bootstrap_servers=KAFKA_BROKERS.split(','),
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
    return producer


def emit_event(topic: str, event: Dict):
    """Emit event to Kafka topic."""
    prod = get_producer()
    prod.send(topic, value=event)
    prod.flush()


def emit_audit(event_type: str, account_id: str, details: Dict, correlation_id: str = None):
    """Emit audit event."""
    audit_event = {
        'event_id': str(uuid.uuid4()),
        'event_type': event_type,
        'account_id': account_id,
        'timestamp': datetime.utcnow().isoformat(),
        'details': details,
        'correlation_id': correlation_id or str(uuid.uuid4())
    }
    
    emit_event('audit.v1', audit_event)
    
    # Also write to S3 for durable storage
    write_audit_to_s3(audit_event)


def write_audit_to_s3(audit_event: Dict):
    """Write audit event to S3 with partitioning."""
    dt = datetime.utcnow()
    key = f"audit/year={dt.year}/month={dt.month:02d}/day={dt.day:02d}/hour={dt.hour:02d}/{audit_event['event_id']}.json"
    
    try:
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=key,
            Body=json.dumps(audit_event),
            ContentType='application/json'
        )
    except Exception as e:
        print(f"Error writing to S3: {e}")


def get_account_state(account_id: str) -> Optional[Dict]:
    """Get current account state from DynamoDB."""
    try:
        response = table.query(
            KeyConditionExpression='account_id = :aid',
            ExpressionAttributeValues={':aid': account_id},
            ScanIndexForward=False,  # Descending order
            Limit=1
        )
        
        if response['Items']:
            return response['Items'][0]
        return None
    except Exception as e:
        print(f"Error querying DynamoDB: {e}")
        return None


def update_account_state(account_id: str, state: Dict):
    """Update account state in DynamoDB."""
    try:
        item = {
            'account_id': account_id,
            'timestamp': int(time.time() * 1000),
            **state,
            'ttl': int((datetime.utcnow() + timedelta(days=30)).timestamp())
        }
        table.put_item(Item=item)
    except Exception as e:
        print(f"Error updating DynamoDB: {e}")


def enforce_margin(margin_event: Dict):
    """
    Enforce margin requirements.
    
    Escalation ladder:
    1. Excess < warning threshold → WARNING
    2. Excess < 0 → MARGIN_CALL
    3. Margin call outstanding > escalation_minutes → RESTRICTION
    4. Still deficient → LIQUIDATION (trigger only, not executed here)
    """
    account_id = margin_event['account_id']
    excess = margin_event['excess']
    total_mv = margin_event['total_mv']
    equity = margin_event['equity']
    maintenance_req = margin_event['maintenance_req']
    
    correlation_id = str(uuid.uuid4())
    
    # Get current state
    current_state = get_account_state(account_id)
    current_status = current_state['status'] if current_state else 'ACTIVE'
    margin_call_issued_at = current_state.get('margin_call_issued_at') if current_state else None
    
    # Determine action
    new_status = current_status
    action_taken = None
    
    # Check for warning
    if excess < (total_mv * WARNING_THRESHOLD_PCT) and excess >= 0:
        if current_status == 'ACTIVE':
            new_status = 'WARNING'
            action_taken = 'WARNING_ISSUED'
            
            emit_event('margin.calls.v1', {
                'account_id': account_id,
                'action': 'WARNING',
                'excess': excess,
                'equity': equity,
                'maintenance_req': maintenance_req,
                'timestamp': datetime.utcnow().isoformat(),
                'correlation_id': correlation_id
            })
            
            emit_audit('WARNING_ISSUED', account_id, {
                'excess': excess,
                'excess_pct': excess / total_mv if total_mv > 0 else 0,
                'equity': equity,
                'maintenance_req': maintenance_req
            }, correlation_id)
    
    # Check for margin call
    if excess < 0:
        deficiency = abs(excess)
        
        if current_status in ['ACTIVE', 'WARNING']:
            new_status = 'MARGIN_CALL'
            action_taken = 'MARGIN_CALL_ISSUED'
            margin_call_issued_at = datetime.utcnow().isoformat()
            
            emit_event('margin.calls.v1', {
                'account_id': account_id,
                'action': 'MARGIN_CALL',
                'deficiency': deficiency,
                'excess': excess,
                'equity': equity,
                'maintenance_req': maintenance_req,
                'timestamp': margin_call_issued_at,
                'correlation_id': correlation_id
            })
            
            emit_audit('MARGIN_CALL_ISSUED', account_id, {
                'deficiency': deficiency,
                'excess': excess,
                'equity': equity,
                'maintenance_req': maintenance_req
            }, correlation_id)
        
        # Check if margin call is stale
        elif current_status == 'MARGIN_CALL' and margin_call_issued_at:
            call_time = datetime.fromisoformat(margin_call_issued_at)
            elapsed_minutes = (datetime.utcnow() - call_time).total_seconds() / 60
            
            if elapsed_minutes > ESCALATION_MINUTES:
                new_status = 'RESTRICTED'
                action_taken = 'RESTRICTION_APPLIED'
                
                emit_event('restrictions.v1', {
                    'account_id': account_id,
                    'action': 'CLOSE_ONLY',
                    'reason': f'Margin call outstanding for {elapsed_minutes:.0f} minutes',
                    'deficiency': deficiency,
                    'timestamp': datetime.utcnow().isoformat(),
                    'correlation_id': correlation_id
                })
                
                emit_audit('RESTRICTION_APPLIED', account_id, {
                    'action': 'CLOSE_ONLY',
                    'reason': 'Margin call escalation',
                    'elapsed_minutes': elapsed_minutes,
                    'deficiency': deficiency
                }, correlation_id)
                
                # If still deficient after restriction, trigger liquidation
                # (In production, this would have additional checks and human oversight)
                if deficiency > maintenance_req * 0.5:  # Severe deficiency
                    emit_event('liquidations.v1', {
                        'account_id': account_id,
                        'trigger': 'SEVERE_DEFICIENCY',
                        'deficiency': deficiency,
                        'timestamp': datetime.utcnow().isoformat(),
                        'correlation_id': correlation_id
                    })
                    
                    emit_audit('LIQUIDATION_TRIGGERED', account_id, {
                        'trigger': 'SEVERE_DEFICIENCY',
                        'deficiency': deficiency
                    }, correlation_id)
    
    # Update state
    if action_taken:
        update_account_state(account_id, {
            'status': new_status,
            'equity': equity,
            'market_value': total_mv,
            'maintenance_req': maintenance_req,
            'excess': excess,
            'margin_call_issued_at': margin_call_issued_at,
            'last_action': action_taken
        })


def enforce_stress(stress_event: Dict):
    """
    Enforce stress test results.
    
    If account is underwater in severe stress scenario, apply restriction.
    """
    account_id = stress_event['account_id']
    scenario = stress_event['scenario']
    underwater = stress_event['underwater']
    excess_stressed = stress_event['excess_stressed']
    
    correlation_id = str(uuid.uuid4())
    
    # Check if underwater in severe scenario
    if underwater and abs(scenario) >= SEVERE_STRESS_THRESHOLD:
        # Get current state
        current_state = get_account_state(account_id)
        current_status = current_state['status'] if current_state else 'ACTIVE'
        
        # Only restrict if not already restricted
        if current_status not in ['RESTRICTED', 'LIQUIDATION']:
            emit_event('restrictions.v1', {
                'account_id': account_id,
                'action': 'CLOSE_ONLY',
                'reason': f'Underwater in SPY {scenario:.1%} stress scenario',
                'excess_stressed': excess_stressed,
                'scenario': scenario,
                'timestamp': datetime.utcnow().isoformat(),
                'correlation_id': correlation_id
            })
            
            emit_audit('STRESS_RESTRICTION', account_id, {
                'action': 'CLOSE_ONLY',
                'reason': 'Stress test failure',
                'scenario': scenario,
                'excess_stressed': excess_stressed
            }, correlation_id)
            
            # Update state
            update_account_state(account_id, {
                'status': 'RESTRICTED',
                'last_action': 'STRESS_RESTRICTION',
                'stress_scenario': scenario,
                'excess_stressed': excess_stressed
            })


def lambda_handler(event, context):
    """
    Lambda handler for MSK trigger.
    
    Processes batches of Kafka events.
    """
    print(f"Processing {len(event['records'])} Kafka partitions")
    
    for topic_partition, records in event['records'].items():
        print(f"Processing {len(records)} records from {topic_partition}")
        
        for record in records:
            # Decode Kafka message
            value = json.loads(record['value'])
            topic = record['topic']
            
            try:
                if topic == 'margin.calc.v1':
                    enforce_margin(value)
                elif topic == 'stress.beta_spy.v1':
                    enforce_stress(value)
                else:
                    print(f"Unknown topic: {topic}")
            except Exception as e:
                print(f"Error processing record: {e}")
                # In production, would send to DLQ
                continue
    
    return {
        'statusCode': 200,
        'body': json.dumps('Processing complete')
    }


if __name__ == "__main__":
    # For local testing
    test_margin_event = {
        'account_id': 'ACC123',
        'total_mv': 100000,
        'equity': 95000,
        'maintenance_req': 25000,
        'excess': 70000
    }
    
    enforce_margin(test_margin_event)
