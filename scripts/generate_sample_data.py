#!/usr/bin/env python3
"""
Sample Data Generator

Generates realistic market data for testing:
- Multiple accounts with varying risk profiles
- Realistic stock prices with volatility
- Beta coefficients
- Trade fills
"""

import json
import random
import time
import uuid
from datetime import datetime, timedelta
from kafka import KafkaProducer

# Configuration
KAFKA_BROKERS = 'localhost:9092'

# Stock universe
STOCKS = {
    'AAPL': {'price': 175.00, 'beta': 1.2, 'volatility': 0.25},
    'MSFT': {'price': 380.00, 'beta': 1.1, 'volatility': 0.22},
    'GOOGL': {'price': 140.00, 'beta': 1.15, 'volatility': 0.24},
    'AMZN': {'price': 155.00, 'beta': 1.3, 'volatility': 0.28},
    'NVDA': {'price': 400.00, 'beta': 1.8, 'volatility': 0.40},
    'TSLA': {'price': 200.00, 'beta': 2.0, 'volatility': 0.50},
    'META': {'price': 350.00, 'beta': 1.25, 'volatility': 0.30},
    'JPM': {'price': 150.00, 'beta': 1.0, 'volatility': 0.20},
    'JNJ': {'price': 160.00, 'beta': 0.7, 'volatility': 0.15},
    'PG': {'price': 145.00, 'beta': 0.6, 'volatility': 0.12},
    'KO': {'price': 60.00, 'beta': 0.6, 'volatility': 0.14},
    'SPY': {'price': 450.00, 'beta': 1.0, 'volatility': 0.18}
}

# Account profiles
ACCOUNTS = [
    {'id': 'ACC_CONSERVATIVE_001', 'cash': 100000, 'risk_profile': 'conservative'},
    {'id': 'ACC_MODERATE_001', 'cash': 200000, 'risk_profile': 'moderate'},
    {'id': 'ACC_AGGRESSIVE_001', 'cash': 150000, 'risk_profile': 'aggressive'},
    {'id': 'ACC_HEDGED_001', 'cash': 300000, 'risk_profile': 'hedged'},
    {'id': 'ACC_CONCENTRATED_001', 'cash': 50000, 'risk_profile': 'concentrated'},
]


class DataGenerator:
    """Generate realistic market data."""
    
    def __init__(self, brokers):
        self.producer = KafkaProducer(
            bootstrap_servers=brokers.split(','),
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            key_serializer=lambda k: k.encode('utf-8') if k else None
        )
        self.current_prices = {symbol: data['price'] for symbol, data in STOCKS.items()}
    
    def send_betas(self):
        """Send beta coefficients for all stocks."""
        print("Sending beta coefficients...")
        for symbol, data in STOCKS.items():
            beta_event = {
                'symbol': symbol,
                'beta': data['beta'],
                'timestamp': int(time.time() * 1000)
            }
            self.producer.send('betas.v1', key=symbol, value=beta_event)
            print(f"  {symbol}: β = {data['beta']:.2f}")
        self.producer.flush()
    
    def generate_initial_positions(self):
        """Generate initial positions for all accounts."""
        print("\nGenerating initial positions...")
        
        for account in ACCOUNTS:
            account_id = account['id']
            cash = account['cash']
            risk_profile = account['risk_profile']
            
            print(f"\n  {account_id} ({risk_profile}):")
            
            if risk_profile == 'conservative':
                # Low-beta, diversified
                positions = [
                    ('JNJ', 200),
                    ('PG', 200),
                    ('KO', 300),
                    ('JPM', 100)
                ]
            
            elif risk_profile == 'moderate':
                # Mix of stocks
                positions = [
                    ('AAPL', 200),
                    ('MSFT', 100),
                    ('JPM', 150),
                    ('JNJ', 100)
                ]
            
            elif risk_profile == 'aggressive':
                # High-beta stocks
                positions = [
                    ('NVDA', 200),
                    ('TSLA', 300),
                    ('AMZN', 200)
                ]
            
            elif risk_profile == 'hedged':
                # Long and short positions (simulated with negative qty)
                positions = [
                    ('AAPL', 500),
                    ('MSFT', -200),  # Short
                    ('GOOGL', 300),
                    ('AMZN', -100)   # Short
                ]
            
            elif risk_profile == 'concentrated':
                # Single large position
                positions = [
                    ('NVDA', 500)
                ]
            
            # Send fills
            for symbol, qty in positions:
                price = self.current_prices[symbol]
                fill = {
                    'account_id': account_id,
                    'symbol': symbol,
                    'qty': qty,
                    'price': price,
                    'timestamp': int(time.time() * 1000),
                    'fill_id': str(uuid.uuid4())
                }
                self.producer.send('fills.v1', key=account_id, value=fill)
                print(f"    {qty:+5d} {symbol} @ ${price:.2f}")
            
            self.producer.flush()
            time.sleep(1)
    
    def update_prices(self, market_move=0.0):
        """
        Update all stock prices.
        
        Args:
            market_move: SPY move percentage (e.g., -0.02 for -2%)
        """
        print(f"\nUpdating prices (SPY {market_move:+.1%})...")
        
        # Update SPY first
        spy_price = self.current_prices['SPY']
        new_spy_price = spy_price * (1 + market_move)
        self.current_prices['SPY'] = new_spy_price
        
        price_event = {
            'symbol': 'SPY',
            'price': new_spy_price,
            'timestamp': int(time.time() * 1000)
        }
        self.producer.send('prices.v1', key='SPY', value=price_event)
        print(f"  SPY: ${spy_price:.2f} → ${new_spy_price:.2f}")
        
        # Update other stocks based on beta and idiosyncratic noise
        for symbol, data in STOCKS.items():
            if symbol == 'SPY':
                continue
            
            beta = data['beta']
            volatility = data['volatility']
            
            # Stock move = beta × market move + idiosyncratic noise
            idiosyncratic = random.gauss(0, volatility * 0.1)
            stock_move = beta * market_move + idiosyncratic
            
            old_price = self.current_prices[symbol]
            new_price = old_price * (1 + stock_move)
            self.current_prices[symbol] = new_price
            
            price_event = {
                'symbol': symbol,
                'price': new_price,
                'timestamp': int(time.time() * 1000)
            }
            self.producer.send('prices.v1', key=symbol, value=price_event)
            print(f"  {symbol}: ${old_price:.2f} → ${new_price:.2f} ({stock_move:+.1%})")
        
        self.producer.flush()
    
    def simulate_trading_day(self):
        """Simulate a full trading day with market moves."""
        print("\n" + "=" * 80)
        print("  Simulating Trading Day")
        print("=" * 80)
        
        # Market open
        print("\n09:30 - Market Open")
        self.update_prices(0.0)
        time.sleep(5)
        
        # Morning rally
        print("\n10:00 - Morning Rally")
        self.update_prices(0.01)
        time.sleep(5)
        
        # Mid-day consolidation
        print("\n12:00 - Mid-Day")
        self.update_prices(-0.005)
        time.sleep(5)
        
        # Afternoon decline
        print("\n14:00 - Afternoon Decline")
        self.update_prices(-0.02)
        time.sleep(5)
        
        # Late day selloff
        print("\n15:30 - Late Day Selloff")
        self.update_prices(-0.03)
        time.sleep(5)
        
        # Market close
        print("\n16:00 - Market Close")
        self.update_prices(-0.01)
    
    def close(self):
        """Close producer."""
        self.producer.close()


def main():
    """Main execution."""
    print("=" * 80)
    print("  Sample Data Generator")
    print("=" * 80)
    
    generator = DataGenerator(KAFKA_BROKERS)
    
    # Step 1: Send betas
    generator.send_betas()
    time.sleep(2)
    
    # Step 2: Generate initial positions
    generator.generate_initial_positions()
    time.sleep(5)
    
    # Step 3: Simulate trading day
    generator.simulate_trading_day()
    
    print("\n" + "=" * 80)
    print("  Data Generation Complete")
    print("=" * 80)
    print("\nGenerated data for:")
    print(f"  - {len(STOCKS)} stocks")
    print(f"  - {len(ACCOUNTS)} accounts")
    print(f"  - Multiple price updates simulating market moves")
    print("\nUse scripts/observe_streams.py to view results.")
    
    generator.close()


if __name__ == "__main__":
    main()
