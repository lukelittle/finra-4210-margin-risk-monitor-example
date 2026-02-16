#!/usr/bin/env python3
"""
Stream Observer

Consumes and displays events from all Kafka topics in real-time.
"""

import json
import sys
from datetime import datetime
from kafka import KafkaConsumer
from kafka.errors import KafkaError

# Configuration
KAFKA_BROKERS = 'localhost:9092'

# Topics to observe
TOPICS = [
    'fills.v1',
    'prices.v1',
    'betas.v1',
    'margin.calc.v1',
    'stress.beta_spy.v1',
    'margin.calls.v1',
    'restrictions.v1',
    'liquidations.v1',
    'audit.v1'
]

# Color codes for terminal output
COLORS = {
    'fills.v1': '\033[94m',        # Blue
    'prices.v1': '\033[96m',       # Cyan
    'betas.v1': '\033[95m',        # Magenta
    'margin.calc.v1': '\033[92m',  # Green
    'stress.beta_spy.v1': '\033[93m',  # Yellow
    'margin.calls.v1': '\033[91m', # Red
    'restrictions.v1': '\033[91m', # Red
    'liquidations.v1': '\033[91m', # Red
    'audit.v1': '\033[90m',        # Gray
    'RESET': '\033[0m'
}


def format_event(topic, value):
    """Format event for display."""
    color = COLORS.get(topic, '')
    reset = COLORS['RESET']
    
    timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
    
    # Format based on topic
    if topic == 'fills.v1':
        return f"{color}[{timestamp}] FILL: {value['account_id']} {value['qty']:+d} {value['symbol']} @ ${value['price']:.2f}{reset}"
    
    elif topic == 'prices.v1':
        return f"{color}[{timestamp}] PRICE: {value['symbol']} = ${value['price']:.2f}{reset}"
    
    elif topic == 'betas.v1':
        return f"{color}[{timestamp}] BETA: {value['symbol']} = {value['beta']:.2f}{reset}"
    
    elif topic == 'margin.calc.v1':
        excess = value.get('excess', 0)
        status = "✅" if excess >= 0 else "❌"
        return f"{color}[{timestamp}] MARGIN: {value['account_id']} Equity=${value.get('equity', 0):,.0f} Excess=${excess:,.0f} {status}{reset}"
    
    elif topic == 'stress.beta_spy.v1':
        underwater = value.get('underwater', False)
        status = "❌ UNDERWATER" if underwater else "✅"
        scenario = value.get('scenario', 0)
        return f"{color}[{timestamp}] STRESS: {value['account_id']} SPY {scenario:+.1%} Excess=${value.get('excess_stressed', 0):,.0f} {status}{reset}"
    
    elif topic == 'margin.calls.v1':
        action = value.get('action', 'UNKNOWN')
        deficiency = value.get('deficiency', 0)
        return f"{color}[{timestamp}] 📞 MARGIN CALL: {value['account_id']} {action} Deficiency=${deficiency:,.0f}{reset}"
    
    elif topic == 'restrictions.v1':
        action = value.get('action', 'UNKNOWN')
        reason = value.get('reason', 'N/A')
        return f"{color}[{timestamp}] 🚫 RESTRICTION: {value['account_id']} {action} - {reason}{reset}"
    
    elif topic == 'liquidations.v1':
        trigger = value.get('trigger', 'UNKNOWN')
        return f"{color}[{timestamp}] 💥 LIQUIDATION: {value['account_id']} Trigger={trigger}{reset}"
    
    elif topic == 'audit.v1':
        event_type = value.get('event_type', 'UNKNOWN')
        return f"{color}[{timestamp}] AUDIT: {event_type} {value['account_id']}{reset}"
    
    else:
        return f"{color}[{timestamp}] {topic}: {json.dumps(value, indent=2)}{reset}"


def main():
    """Main execution."""
    print("=" * 80)
    print("  Real-Time Margin Risk Monitor - Stream Observer")
    print("=" * 80)
    print("\nConnecting to Kafka...")
    
    try:
        consumer = KafkaConsumer(
            *TOPICS,
            bootstrap_servers=KAFKA_BROKERS.split(','),
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            auto_offset_reset='latest',  # Start from latest (real-time)
            enable_auto_commit=True,
            group_id='observer'
        )
        
        print(f"✅ Connected to Kafka")
        print(f"📡 Listening to {len(TOPICS)} topics...")
        print("\nPress Ctrl+C to stop\n")
        print("-" * 80)
        
        for message in consumer:
            try:
                formatted = format_event(message.topic, message.value)
                print(formatted)
            except Exception as e:
                print(f"Error formatting message: {e}")
                print(f"Raw: {message.value}")
    
    except KafkaError as e:
        print(f"❌ Failed to connect to Kafka: {e}")
        print("Make sure Kafka is running: docker-compose up -d")
        sys.exit(1)
    
    except KeyboardInterrupt:
        print("\n\n" + "=" * 80)
        print("  Observer stopped")
        print("=" * 80)
        consumer.close()


if __name__ == "__main__":
    main()
