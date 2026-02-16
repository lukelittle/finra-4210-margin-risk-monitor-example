# Exercises

These exercises extend the system with new features, helping you master streaming architectures and financial risk modeling.

## Exercise 1: Implement Concentration Add-On

**Difficulty**: Medium

**Goal**: Add house margin requirements for concentrated positions.

### Requirements

If a single position exceeds 30% of portfolio value, add 10% extra margin for that position.

### Implementation Steps

1. **Modify Spark Job**:
   ```python
   # In compute_margin_requirements()
   
   # Compute position weights
   positions_with_weight = positions_enriched_df.withColumn(
       "weight",
       col("market_value") / sum("market_value").over(Window.partitionBy("account_id"))
   )
   
   # Add concentration add-on
   positions_with_addon = positions_with_weight.withColumn(
       "concentration_addon",
       when(col("weight") > 0.30, col("market_value") * 0.10).otherwise(0)
   )
   
   # Aggregate
   account_summary = positions_with_addon.groupBy("account_id").agg(
       sum("market_value").alias("total_mv"),
       sum("concentration_addon").alias("total_concentration_addon")
   )
   
   # Total maintenance requirement
   account_summary = account_summary.withColumn(
       "maintenance_req",
       col("total_mv") * 0.25 + col("total_concentration_addon")
   )
   ```

2. **Test**: Create account with 80% in one stock, verify extra margin applied

3. **Observe**: Check `margin.calc.v1` for `concentration_addon` field

### Expected Outcome

Account with concentrated position has higher margin requirement, reducing excess and potentially triggering earlier warnings.

## Exercise 2: Add Volatility-Based Margin

**Difficulty**: Hard

**Goal**: Adjust margin requirements based on stock volatility.

### Requirements

- Compute 30-day historical volatility for each symbol
- If volatility > 40%, add 5% extra margin
- If volatility > 60%, add 10% extra margin

### Implementation Steps

1. **Create Volatility Calculator**:
   ```python
   # New Spark job: volatility_calculator.py
   
   def compute_volatility(prices_df):
       """Compute 30-day rolling volatility."""
       
       # Compute returns
       returns_df = prices_df.withColumn(
           "return",
           (col("price") - lag("price", 1).over(Window.partitionBy("symbol").orderBy("timestamp"))) / lag("price", 1).over(Window.partitionBy("symbol").orderBy("timestamp"))
       )
       
       # Compute 30-day std dev
       volatility_df = returns_df.withColumn(
           "volatility",
           stddev("return").over(Window.partitionBy("symbol").orderBy("timestamp").rowsBetween(-30, 0))
       )
       
       # Annualize (252 trading days)
       volatility_df = volatility_df.withColumn(
           "volatility_annual",
           col("volatility") * sqrt(lit(252))
       )
       
       return volatility_df
   ```

2. **Emit to New Topic**: `volatility.v1`

3. **Modify Margin Calculator**:
   ```python
   # Join with volatility
   positions_with_vol = positions_enriched_df.join(
       latest_volatility,
       on="symbol",
       how="left"
   ).fillna({"volatility_annual": 0.20})  # Default 20%
   
   # Add volatility add-on
   positions_with_vol = positions_with_vol.withColumn(
       "volatility_addon",
       when(col("volatility_annual") > 0.60, col("market_value") * 0.10)
       .when(col("volatility_annual") > 0.40, col("market_value") * 0.05)
       .otherwise(0)
   )
   ```

4. **Test**: Simulate high-volatility stock, verify extra margin

### Expected Outcome

High-volatility stocks require more margin, protecting firm from sudden moves.

## Exercise 3: Implement Portfolio Margin Comparison

**Difficulty**: Medium

**Goal**: Compare Reg T margin vs. TIMS portfolio margin side-by-side.

### Requirements

- Compute both methodologies for each account
- Emit both to `margin.calc.v1`
- Show which is more capital efficient

### Implementation Steps

1. **Enhance TIMS Calculation**:
   ```python
   # Already implemented in margin_calculator.py
   # Ensure both are emitted
   
   account_summary = account_summary.withColumn(
       "reg_t_margin",
       col("total_mv") * 0.25
   )
   
   # Join with TIMS results
   account_with_tims = account_summary.join(
       tims_df,
       on="account_id",
       how="left"
   )
   
   # Compare
   account_with_tims = account_with_tims.withColumn(
       "margin_method",
       when(col("portfolio_margin_req") < col("reg_t_margin"), "PORTFOLIO")
       .otherwise("REG_T")
   )
   
   account_with_tims = account_with_tims.withColumn(
       "margin_savings",
       col("reg_t_margin") - col("portfolio_margin_req")
   )
   ```

2. **Create Dashboard**: Visualize savings for hedged portfolios

3. **Test**: Create hedged position (long stock + short correlated stock), verify portfolio margin is lower

### Expected Outcome

Hedged portfolios show significant margin savings under portfolio margin.

## Exercise 4: Add Real-Time Dashboard

**Difficulty**: Hard

**Goal**: Build web dashboard showing real-time margin status.

### Requirements

- Display all accounts with current margin status
- Show color-coded risk levels (green/yellow/red)
- Update in real-time as events arrive
- Show stress test results

### Implementation Steps

1. **Create WebSocket Server**:
   ```python
   # dashboard/server.py
   
   from flask import Flask, render_template
   from flask_socketio import SocketIO
   from kafka import KafkaConsumer
   import json
   
   app = Flask(__name__)
   socketio = SocketIO(app)
   
   def consume_margin_events():
       consumer = KafkaConsumer(
           'margin.calc.v1',
           bootstrap_servers='localhost:9092',
           value_deserializer=lambda m: json.loads(m.decode('utf-8'))
       )
       
       for message in consumer:
           socketio.emit('margin_update', message.value)
   
   @app.route('/')
   def index():
       return render_template('dashboard.html')
   
   if __name__ == '__main__':
       socketio.start_background_task(consume_margin_events)
       socketio.run(app, port=5000)
   ```

2. **Create Frontend**:
   ```html
   <!-- dashboard/templates/dashboard.html -->
   
   <script src="https://cdn.socket.io/4.0.0/socket.io.min.js"></script>
   <script>
       const socket = io();
       
       socket.on('margin_update', function(data) {
           updateAccountRow(data);
       });
       
       function updateAccountRow(account) {
           // Update table row with account data
           // Color-code based on excess
       }
   </script>
   ```

3. **Deploy**: Run alongside other services

### Expected Outcome

Real-time dashboard showing all accounts, updating as margin changes.

## Exercise 5: Implement Liquidation Logic

**Difficulty**: Hard

**Goal**: Automatically select positions to liquidate when margin call escalates.

### Requirements

- Prioritize liquidating highest-beta positions first
- Liquidate minimum quantity to restore compliance
- Emit liquidation orders to new topic
- Update position state

### Implementation Steps

1. **Create Liquidation Selector**:
   ```python
   # lambda/liquidation/selector.py
   
   def select_positions_to_liquidate(account_id, deficiency):
       """
       Select positions to liquidate.
       
       Strategy:
       1. Sort positions by beta (highest first)
       2. Liquidate positions until deficiency covered
       3. Add 10% buffer
       """
       
       # Get current positions
       positions = get_account_positions(account_id)
       
       # Sort by beta descending
       positions.sort(key=lambda p: p['beta'], reverse=True)
       
       target_proceeds = deficiency * 1.10  # 10% buffer
       liquidations = []
       total_proceeds = 0
       
       for position in positions:
           if total_proceeds >= target_proceeds:
               break
           
           # Liquidate entire position (simplified)
           proceeds = position['qty'] * position['price']
           liquidations.append({
               'symbol': position['symbol'],
               'qty': position['qty'],
               'estimated_proceeds': proceeds
           })
           total_proceeds += proceeds
       
       return liquidations
   ```

2. **Emit Liquidation Orders**:
   ```python
   emit_event('liquidation.orders.v1', {
       'account_id': account_id,
       'positions': liquidations,
       'reason': 'MARGIN_DEFICIENCY',
       'deficiency': deficiency,
       'timestamp': datetime.utcnow().isoformat()
   })
   ```

3. **Update Position State**: Consume liquidation orders, update positions

4. **Test**: Create deficient account, verify correct positions selected

### Expected Outcome

System automatically selects optimal positions to liquidate, minimizing market impact.

## Exercise 6: Add Historical Backtesting

**Difficulty**: Medium

**Goal**: Replay historical market data to test system behavior.

### Requirements

- Load historical price data
- Replay at accelerated speed
- Measure how often margin calls would have occurred
- Identify worst-case scenarios

### Implementation Steps

1. **Create Replay Script**:
   ```python
   # scripts/backtest.py
   
   import pandas as pd
   
   def replay_historical_data(csv_file, speed_multiplier=10):
       """
       Replay historical data to Kafka.
       
       Args:
           csv_file: CSV with columns [timestamp, symbol, price]
           speed_multiplier: How much faster than real-time
       """
       
       df = pd.read_csv(csv_file)
       df['timestamp'] = pd.to_datetime(df['timestamp'])
       df = df.sort_values('timestamp')
       
       producer = DemoProducer(KAFKA_BROKERS)
       
       for i, row in df.iterrows():
           producer.send_price(row['symbol'], row['price'])
           
           if i > 0:
               time_delta = (row['timestamp'] - df.iloc[i-1]['timestamp']).total_seconds()
               time.sleep(time_delta / speed_multiplier)
       
       producer.close()
   ```

2. **Collect Metrics**: Count margin calls, restrictions, liquidations

3. **Analyze**: Which scenarios caused most issues?

### Expected Outcome

Understanding of system behavior under historical market conditions.

## Exercise 7: Add Multi-Account Aggregation

**Difficulty**: Medium

**Goal**: Aggregate risk across all accounts to compute firm-wide exposure.

### Requirements

- Sum beta-weighted exposure across all accounts
- Compute firm-wide stress scenarios
- Alert if firm exposure exceeds threshold

### Implementation Steps

1. **Create Firm Aggregator**:
   ```python
   # In Spark job
   
   firm_summary = account_summary.agg(
       sum("beta_weighted_exposure").alias("firm_beta_weighted_exposure"),
       sum("total_mv").alias("firm_total_mv"),
       count("account_id").alias("num_accounts")
   )
   
   # Compute firm-wide stress
   for scenario in SPY_SCENARIOS:
       firm_stress = firm_summary.withColumn(
           "scenario", lit(scenario)
       ).withColumn(
           "firm_delta_pnl", col("firm_beta_weighted_exposure") * lit(scenario)
       )
       
       # Emit to firm.risk.v1
   ```

2. **Set Firm Limits**: Alert if firm exposure > $10M beta-weighted

3. **Test**: Create multiple accounts, verify aggregation

### Expected Outcome

Firm-wide risk monitoring, catching systemic exposure.

## Exercise 8: Implement Margin Call Notifications

**Difficulty**: Easy

**Goal**: Send email/SMS notifications when margin calls issued.

### Requirements

- Integrate with AWS SNS or SendGrid
- Send notification when margin call issued
- Include account details and required action

### Implementation Steps

1. **Add SNS Integration**:
   ```python
   # In Lambda enforcement
   
   import boto3
   
   sns = boto3.client('sns')
   
   def send_margin_call_notification(account_id, deficiency):
       message = f"""
       MARGIN CALL ISSUED
       
       Account: {account_id}
       Deficiency: ${deficiency:,.2f}
       
       Action Required:
       - Deposit funds, or
       - Liquidate positions
       
       Failure to respond within 30 minutes will result in account restriction.
       """
       
       sns.publish(
           TopicArn='arn:aws:sns:us-east-1:123456789012:margin-calls',
           Subject='Margin Call Issued',
           Message=message
       )
   ```

2. **Test**: Trigger margin call, verify notification sent

### Expected Outcome

Automated notifications ensure timely customer response.

## Submission Guidelines

For each exercise:

1. **Code**: Commit changes to a branch
2. **Documentation**: Update relevant docs
3. **Tests**: Add unit tests
4. **Demo**: Show it working with demo scenario
5. **Analysis**: Write brief analysis of results

## Grading Rubric

- **Correctness** (40%): Does it work as specified?
- **Code Quality** (20%): Clean, documented, tested?
- **Performance** (20%): Efficient, scalable?
- **Analysis** (20%): Thoughtful interpretation of results?

## Next Steps

- [09 - Cost and Cleanup](09-cost-and-cleanup.md) - Manage AWS costs
- [00 - Overview](00-overview.md) - Review system design
