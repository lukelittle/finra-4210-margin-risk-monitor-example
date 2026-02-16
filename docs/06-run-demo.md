# Run Demo

This guide walks through running the demo scenario locally using Docker Compose.

## Prerequisites

- Docker and Docker Compose installed
- At least 8GB RAM available for Docker
- Python 3.11+ (for running scripts outside containers)

## Quick Start

### 1. Start the Local Stack

```bash
# Start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f
```

This starts:
- Kafka (with Zookeeper)
- Spark (master and worker)
- Python services container
- DynamoDB Local

### 2. Wait for Services to Initialize

```bash
# Wait for Kafka to be ready (about 30 seconds)
docker-compose logs kafka-init

# You should see "Topics created successfully"
```

### 3. Run the Demo Scenario

```bash
# Option A: Run from host (if you have Python installed)
pip install -r requirements.txt
python scripts/demo_scenario.py

# Option B: Run inside container
docker-compose exec python-services python scripts/demo_scenario.py
```

## Demo Scenario Walkthrough

The demo simulates a concentrated high-beta position under market stress.

### Initial State

**Account**: ACC_DEMO_001
- Cash: $50,000
- Position: 500 shares NVDA at $400 = $200,000
- Beta (NVDA): 1.8

**Margin Calculation**:
- Market Value: $200,000
- Equity: $250,000 ($50k cash + $200k MV)
- Maintenance Requirement (25%): $50,000
- Excess: $200,000 ✅

**Beta-Weighted Exposure**:
- NVDA: $200,000 × 1.8 = $360,000
- This position has the market risk of $360,000 of SPY

### Market Decline Sequence

#### T+0 (Market Open)
- SPY: $450
- NVDA: $400
- Status: ✅ Healthy

#### T+5 (SPY -1%)
- SPY: $445.50 (-1%)
- NVDA: $392 (-2%, 1.8× beta effect)
- Market Value: $196,000
- Equity: $246,000
- Excess: $196,000 ✅
- Status: Still healthy

#### T+10 (SPY -2%)
- SPY: $441 (-2%)
- NVDA: $384 (-4%)
- Market Value: $192,000
- Equity: $242,000
- Excess: $194,000 ✅
- Status: Still healthy

#### T+15 (SPY -4%)
- SPY: $432 (-4%)
- NVDA: $368 (-8%)
- Market Value: $184,000
- Equity: $234,000
- Excess: $188,000 ✅
- Stress Test: SPY -8% from here would cause:
  - ΔPnL: $331,200 × -0.08 = -$26,496
  - Equity_stressed: $207,504
  - Excess_stressed: $161,504 ✅
- Status: Passing stress tests

#### T+20 (SPY -6%)
- SPY: $423 (-6%)
- NVDA: $352 (-12%)
- Market Value: $176,000
- Equity: $226,000
- Excess: $182,000 ✅
- Stress Test: SPY -8% from here:
  - ΔPnL: $316,800 × -0.08 = -$25,344
  - Equity_stressed: $200,656
  - Excess_stressed: $156,656 ✅
- Status: Still passing

#### T+25 (SPY -8%)
- SPY: $414 (-8%)
- NVDA: $336 (-16%)
- Market Value: $168,000
- Equity: $218,000
- Maintenance Requirement: $42,000
- Excess: $176,000 ✅
- Stress Test: SPY -8% from here:
  - Beta-weighted: $302,400
  - ΔPnL: -$24,192
  - Equity_stressed: $193,808
  - Excess_stressed: $151,808 ✅
- Status: Current margin OK, but...

**Enforcement Action**: If we stress test with SPY dropping another 8% (total -16%), the account would be at risk. The system may issue a warning or restriction based on house rules.

### Expected System Behavior

1. **Margin Calculations** (`margin.calc.v1`):
   - Updated every time price changes
   - Shows equity, MV, maintenance req, excess

2. **Stress Test Results** (`stress.beta_spy.v1`):
   - Evaluated for each SPY scenario
   - Shows which scenarios cause underwater conditions

3. **Enforcement Actions**:
   - **Warning**: If excess < 5% of MV
   - **Margin Call**: If excess < 0
   - **Restriction**: If underwater in severe stress (SPY ±6%)
   - **Liquidation**: If deficiency persists

4. **Audit Trail** (`audit.v1`):
   - Every action logged with correlation IDs
   - Queryable for regulatory examination

## Observing Results

### View Kafka Topics

```bash
# Install kafkacat (if not already installed)
# macOS: brew install kafkacat
# Linux: apt-get install kafkacat

# View margin calculations
docker-compose exec kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic margin.calc.v1 \
  --from-beginning

# View stress test results
docker-compose exec kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic stress.beta_spy.v1 \
  --from-beginning

# View margin calls
docker-compose exec kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic margin.calls.v1 \
  --from-beginning

# View restrictions
docker-compose exec kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic restrictions.v1 \
  --from-beginning

# View audit trail
docker-compose exec kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic audit.v1 \
  --from-beginning
```

### Use the Observation Script

```bash
# Run the observation script
python scripts/observe_streams.py

# This will tail all relevant topics and display events in real-time
```

### Check Spark UI

Open http://localhost:8080 to view:
- Running applications
- Worker status
- Job progress

### Check DynamoDB Local

```bash
# Install AWS CLI
# macOS: brew install awscli

# List tables
aws dynamodb list-tables \
  --endpoint-url http://localhost:8000

# Query account state
aws dynamodb query \
  --table-name margin-risk-state \
  --key-condition-expression "account_id = :aid" \
  --expression-attribute-values '{":aid":{"S":"ACC_DEMO_001"}}' \
  --endpoint-url http://localhost:8000
```

## Running the Spark Job

The Spark streaming job must be submitted manually:

```bash
# Submit Spark job
docker-compose exec spark-master spark-submit \
  --master spark://spark-master:7077 \
  --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0 \
  /opt/spark-apps/margin_calculator.py
```

The job will:
1. Connect to Kafka
2. Read fills, prices, and betas
3. Compute positions and margin
4. Run stress tests
5. Emit results to output topics

## Troubleshooting

### Kafka Not Ready

If you see connection errors:

```bash
# Check Kafka logs
docker-compose logs kafka

# Restart Kafka
docker-compose restart kafka

# Wait for initialization
sleep 30
```

### Spark Job Fails

If Spark job fails to start:

```bash
# Check Spark logs
docker-compose logs spark-master
docker-compose logs spark-worker

# Ensure Kafka packages are available
# The --packages flag downloads them automatically
```

### No Events in Topics

If topics are empty:

```bash
# Verify topics exist
docker-compose exec kafka kafka-topics \
  --bootstrap-server localhost:9092 \
  --list

# Re-run demo
python scripts/demo_scenario.py
```

### Python Dependencies

If you get import errors:

```bash
# Install dependencies
pip install -r requirements.txt

# Or use the container
docker-compose exec python-services pip install -r requirements.txt
```

## Cleanup

```bash
# Stop all services
docker-compose down

# Remove volumes (clears all data)
docker-compose down -v

# Remove images
docker-compose down --rmi all
```

## Next Steps

- [07 - Observe](07-observe.md) - Deep dive into observability
- [08 - Exercises](08-exercises.md) - Extend the system with new features
- [05 - Deploy AWS](05-deploy-aws.md) - Deploy to AWS
