#!/usr/bin/env python3
"""
Demo Scenario: Concentrated High-Beta Position Under Stress

This script demonstrates the margin risk monitoring system by:
1. Creating an account with a concentrated NVDA position
2. Simulating SPY market decline
3. Showing how beta-weighted stress testing detects risk
4. Triggering enforcement actions (margin call, restriction)
"""

import json
import time
import uuid
from datetime import datetime
from kafka import KafkaProducer
from kafka.errors import KafkaError

# Configuration
KAFKA_BROKERS = 'localhost:9092'

# Demo account
ACCOUNT_ID = 'ACC_DEMO_001'

# Initial positions and prices
INITIAL_CASH = 50000
POSITIONS = [
    {'symbol': 'NVDA', 'qty': 500, 'price': 400.00},  # $200k position
]

# Beta coefficients
BETAS = {
    'NVDA': 1.8,
    'SPY': 1.0
}

# Market scenario: SPY declines
SPY_SCENARIOS = [
    {'time': 0, 'spy_price': 450.00, 'nvda_price': 400.00, 'description': 'Market open'},
    {'time': 5, 'spy_price': 445.50, 'nvda_price': 392.00, 'description': 'SPY -1%, NVDA -2% (1.8x beta)'},
    {'time': 10, 'spy_price': 441.00, 'nvda_price': 384.00, 'description': 'SPY -2%, NVDA -4%'},
    {'time': 15, 'spy_price': 432.00, 'nvda_price': 368.00, 'description': 'SPY -4%, NVDA -8%'},
    {'time': 20, 'spy_price': 423.00, 'nvda_price': 352.00, 'description': 'SPY -6%, NVDA -12%'},
    {'time': 25, 'spy_price': 414.00, 'nvda_price': 336.00, 'description': 'SPY -8%, NVDA -16%'},
]


class DemoProducer:
    """Kafka producer for demo events."""
    
    def __init__(self, brokers):
        self.producer = KafkaProducer(
            bootstrap_servers=brokers.split(','),
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            key_serializer=lambda k: k.encode('utf-8') if k else None
        )
    
    def send_fill(self, account_id, symbol, qty, price):
        """Send fill event."""
        fill = {
            'account_id': account_id,
            'symbol': symbol,
            'qty': qty,
            'price': price,
            'timestamp': int(time.time() * 1000),
            'fill_id': str(uuid.uuid4())
        }
        
        self.producer.send('fills.v1', key=account_id, value=fill)
        print(f"  📝 Fill: {qty} {symbol} @ ${price:.2f}")
        return fill
    
    def send_price(self, symbol, price):
        """Send price update."""
        price_event = {
            'symbol': symbol,
            'price': price,
            'timestamp': int(time.time() * 1000)
        }
        
        self.producer.send('prices.v1', key=symbol, value=price_event)
        print(f"  💹 Price: {symbol} = ${price:.2f}")
        return price_event
    
    def send_beta(self, symbol, beta):
        """Send beta coefficient."""
        beta_event = {
            'symbol': symbol,
            'beta': beta,
            'timestamp': int(time.time() * 1000)
        }
        
        self.producer.send('betas.v1', key=symbol, value=beta_event)
        print(f"  📊 Beta: {symbol} = {beta:.2f}")
        return beta_event
    
    def flush(self):
        """Flush producer."""
        self.producer.flush()
    
    def close(self):
        """Close producer."""
        self.producer.close()


def print_banner(text):
    """Print section banner."""
    print("\n" + "=" * 80)
    print(f"  {text}")
    print("=" * 80 + "\n")


def print_account_summary(cash, positions, prices):
    """Print account summary."""
    print("\n📊 Account Summary:")
    print(f"  Cash: ${cash:,.2f}")
    print(f"  Positions:")
    
    total_mv = 0
    for pos in positions:
        symbol = pos['symbol']
        qty = pos['qty']
        price = prices.get(symbol, pos['price'])
        mv = qty * price
        total_mv += mv
        print(f"    {symbol}: {qty} shares @ ${price:.2f} = ${mv:,.2f}")
    
    equity = cash + total_mv
    maintenance_req = total_mv * 0.25
    excess = equity - maintenance_req
    
    print(f"\n  Market Value: ${total_mv:,.2f}")
    print(f"  Equity: ${equity:,.2f}")
    print(f"  Maintenance Req (25%): ${maintenance_req:,.2f}")
    print(f"  Excess: ${excess:,.2f}")
    
    if excess < 0:
        print(f"  ⚠️  MARGIN DEFICIENCY: ${abs(excess):,.2f}")
    elif excess < total_mv * 0.05:
        print(f"  ⚠️  WARNING: Low excess margin")
    else:
        print(f"  ✅ Account in good standing")
    
    return equity, total_mv, maintenance_req, excess


def print_stress_analysis(positions, prices, betas):
    """Print beta-weighted stress analysis."""
    print("\n🔬 Beta-Weighted Stress Analysis:")
    
    # Compute beta-weighted exposure
    total_bw = 0
    for pos in positions:
        symbol = pos['symbol']
        qty = pos['qty']
        price = prices.get(symbol, pos['price'])
        beta = betas.get(symbol, 1.0)
        mv = qty * price
        bw = mv * beta
        total_bw += bw
        print(f"  {symbol}: ${mv:,.2f} × {beta:.2f} = ${bw:,.2f} beta-weighted")
    
    print(f"\n  Total Beta-Weighted Exposure: ${total_bw:,.2f}")
    
    # Show stress scenarios
    print(f"\n  SPY Stress Scenarios:")
    spy_scenarios = [-0.08, -0.06, -0.04, -0.02, 0.0, 0.02, 0.04, 0.06]
    
    cash = INITIAL_CASH
    total_mv = sum(pos['qty'] * prices.get(pos['symbol'], pos['price']) for pos in positions)
    equity = cash + total_mv
    maintenance_req = total_mv * 0.25
    
    for scenario in spy_scenarios:
        delta_pnl = total_bw * scenario
        equity_stressed = equity + delta_pnl
        excess_stressed = equity_stressed - maintenance_req
        status = "✅" if excess_stressed >= 0 else "❌ UNDERWATER"
        
        print(f"    SPY {scenario:+.1%}: ΔPnL = ${delta_pnl:+,.0f}, Excess = ${excess_stressed:,.0f} {status}")


def main():
    """Run demo scenario."""
    print_banner("Real-Time Margin Risk Monitor - Demo Scenario")
    
    print("This demo simulates a concentrated high-beta position under market stress.")
    print("Watch as the system detects risk and triggers enforcement actions.\n")
    
    # Initialize producer
    print("Connecting to Kafka...")
    try:
        producer = DemoProducer(KAFKA_BROKERS)
        print("✅ Connected to Kafka\n")
    except KafkaError as e:
        print(f"❌ Failed to connect to Kafka: {e}")
        print("Make sure Kafka is running: docker-compose up -d")
        return
    
    # Step 1: Initialize betas
    print_banner("Step 1: Initialize Beta Coefficients")
    for symbol, beta in BETAS.items():
        producer.send_beta(symbol, beta)
    producer.flush()
    time.sleep(2)
    
    # Step 2: Initialize positions
    print_banner("Step 2: Account Opens Concentrated Position")
    print(f"Account: {ACCOUNT_ID}")
    print(f"Initial Cash: ${INITIAL_CASH:,.2f}\n")
    
    current_prices = {}
    for pos in POSITIONS:
        producer.send_fill(ACCOUNT_ID, pos['symbol'], pos['qty'], pos['price'])
        producer.send_price(pos['symbol'], pos['price'])
        current_prices[pos['symbol']] = pos['price']
    
    producer.flush()
    time.sleep(2)
    
    print_account_summary(INITIAL_CASH, POSITIONS, current_prices)
    print_stress_analysis(POSITIONS, current_prices, BETAS)
    
    print("\n⏸️  Waiting for Spark to process initial positions...")
    time.sleep(10)
    
    # Step 3: Market decline scenarios
    for i, scenario in enumerate(SPY_SCENARIOS[1:], 1):
        print_banner(f"Step {i+2}: {scenario['description']}")
        
        # Update prices
        producer.send_price('SPY', scenario['spy_price'])
        producer.send_price('NVDA', scenario['nvda_price'])
        current_prices['NVDA'] = scenario['nvda_price']
        current_prices['SPY'] = scenario['spy_price']
        
        producer.flush()
        time.sleep(2)
        
        print_account_summary(INITIAL_CASH, POSITIONS, current_prices)
        print_stress_analysis(POSITIONS, current_prices, BETAS)
        
        print(f"\n⏸️  Waiting {scenario['time']} seconds for processing...")
        time.sleep(scenario['time'])
    
    # Final summary
    print_banner("Demo Complete")
    print("The system has processed the market decline scenario.")
    print("\nExpected enforcement actions:")
    print("  1. ⚠️  Warning issued when excess margin becomes low")
    print("  2. 📞 Margin call issued when excess becomes negative")
    print("  3. 🚫 Restriction applied if underwater in severe stress scenarios")
    print("  4. 💥 Liquidation triggered if deficiency persists")
    print("\nCheck the following topics for results:")
    print("  - margin.calc.v1 (margin calculations)")
    print("  - stress.beta_spy.v1 (stress test results)")
    print("  - margin.calls.v1 (margin calls)")
    print("  - restrictions.v1 (account restrictions)")
    print("  - audit.v1 (audit trail)")
    print("\nUse scripts/observe_streams.py to view the events.")
    
    producer.close()


if __name__ == "__main__":
    main()
