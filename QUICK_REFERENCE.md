# Quick Reference Guide

## Key Formulas

### Maintenance Margin (Reg T)
```
Market Value (MV) = Σ (quantity × price)
Equity = Cash + MV
Maintenance Requirement (MR) = 25% × MV
Excess = Equity - MR

If Excess < 0 → Margin Deficiency
```

### Beta Weighting
```
Beta (β) = Cov(Stock, Market) / Var(Market)
Beta-Weighted Value = Position Value × Beta
Total Beta-Weighted Exposure = Σ (Position Value_i × Beta_i)
```

### Stress Testing
```
Stressed PnL = Beta-Weighted Exposure × SPY Move %
Equity_stressed = Equity + Stressed PnL
Excess_stressed = Equity_stressed - MR
Underwater = (Excess_stressed < 0)
```

### TIMS Portfolio Margin
```
For each scenario s in [-15%, +15%]:
    PnL_s = Σ (qty_i × price_i × s)
Worst-Case Loss = min(PnL_s)
Portfolio Margin Requirement = |Worst-Case Loss|
```

## Common Commands

### Local Development

```bash
# Start everything
./scripts/quick_start.sh

# Or manually:
docker-compose up -d
pip install -r requirements.txt

# Submit Spark job
docker-compose exec spark-master spark-submit \
  --master spark://spark-master:7077 \
  --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0 \
  /opt/spark-apps/margin_calculator.py

# Run demo
python scripts/demo_scenario.py

# Observe events
python scripts/observe_streams.py

# Generate sample data
python scripts/generate_sample_data.py

# Stop everything
docker-compose down

# Cleanup (remove volumes)
docker-compose down -v
```

### Kafka Operations

```bash
# List topics
docker-compose exec kafka kafka-topics \
  --bootstrap-server localhost:9092 \
  --list

# Consume topic
docker-compose exec kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic margin.calc.v1 \
  --from-beginning

# Describe topic
docker-compose exec kafka kafka-topics \
  --bootstrap-server localhost:9092 \
  --describe \
  --topic margin.calc.v1
```

### AWS Deployment

```bash
# Initialize Terraform
cd terraform
terraform init
terraform plan
terraform apply

# Get outputs
terraform output msk_bootstrap_brokers
terraform output s3_bucket
terraform output emr_application_id

# Deploy Lambda
cd ../lambda/enforcement
pip install -r requirements.txt -t package/
cd package && zip -r ../lambda.zip . && cd ..
zip -g lambda.zip handler.py
aws lambda update-function-code \
  --function-name margin-risk-monitor-enforcement \
  --zip-file fileb://lambda.zip

# Start Spark job
aws emr-serverless start-job-run \
  --application-id $EMR_APP_ID \
  --execution-role-arn $EMR_ROLE_ARN \
  --job-driver '{...}'

# Cleanup
terraform destroy
```

### Monitoring

```bash
# View Spark UI
open http://localhost:8080

# View Spark Application UI
open http://localhost:4040

# Tail logs
docker-compose logs -f spark-master
docker-compose logs -f python-services

# AWS logs
aws logs tail /aws/lambda/margin-risk-monitor-enforcement --follow
aws logs tail /aws/emr-serverless/margin-risk-monitor --follow
```

## Kafka Topics Reference

| Topic | Purpose | Key Fields |
|-------|---------|------------|
| `fills.v1` | Trade executions | account_id, symbol, qty, price |
| `prices.v1` | Market prices | symbol, price |
| `betas.v1` | Beta coefficients | symbol, beta |
| `margin.calc.v1` | Margin calculations | account_id, equity, excess |
| `stress.beta_spy.v1` | Stress results | account_id, scenario, underwater |
| `margin.calls.v1` | Margin calls | account_id, deficiency |
| `restrictions.v1` | Restrictions | account_id, action, reason |
| `liquidations.v1` | Liquidations | account_id, trigger |
| `audit.v1` | Audit trail | event_type, account_id, details |

## Enforcement Ladder

| Condition | Action | Topic |
|-----------|--------|-------|
| Excess < 5% of MV | WARNING | margin.calls.v1 |
| Excess < 0 | MARGIN_CALL | margin.calls.v1 |
| Underwater in severe stress | RESTRICTION | restrictions.v1 |
| Deficiency persists > 30 min | LIQUIDATION | liquidations.v1 |

## SPY Stress Scenarios

```
[-8%, -6%, -4%, -2%, 0%, +2%, +4%, +6%]
```

Severe scenarios: |SPY move| ≥ 6%

## TIMS Scenarios

```
[-15%, -10%, -5%, -3%, -1%, +1%, +3%, +5%, +10%, +15%]
```

## Configuration

### Environment Variables

```bash
# Kafka
KAFKA_BROKERS=localhost:9092

# AWS
AWS_REGION=us-east-1
DYNAMODB_TABLE=margin-risk-monitor-account-state
S3_AUDIT_BUCKET=margin-risk-monitor-artifacts-123456789012

# Spark
CHECKPOINT_LOCATION=/tmp/checkpoints
```

### Risk Parameters

```python
MAINTENANCE_RATE = 0.25              # 25% maintenance margin
CONCENTRATION_THRESHOLD = 0.30       # 30% position concentration
CONCENTRATION_ADDON = 0.10           # Additional 10% margin
WARNING_THRESHOLD = 0.05             # Warn if excess < 5% of MV
ESCALATION_MINUTES = 30              # Escalate after 30 minutes
SEVERE_STRESS_THRESHOLD = 0.06       # SPY moves ≥ 6%
```

## File Locations

```
docs/                    # Documentation
  00-overview.md         # Start here
  01-finra-4210.md       # Regulatory context
  02-what-is-tims.md     # Portfolio margin
  03-beta-weighting.md   # Stress testing
  04-architecture.md     # System design
  05-deploy-aws.md       # AWS deployment
  06-run-demo.md         # Local demo
  07-observe.md          # Monitoring
  08-exercises.md        # Student exercises
  09-cost-and-cleanup.md # Cost management

spark/
  margin_calculator.py   # Main Spark job

lambda/enforcement/
  handler.py             # Enforcement logic

terraform/
  main.tf                # Infrastructure

scripts/
  quick_start.sh         # One-command setup
  demo_scenario.py       # Demo
  observe_streams.py     # Event observer
  generate_sample_data.py # Data generator
```

## Troubleshooting

### Kafka Not Ready
```bash
docker-compose logs kafka-init
# Wait for "Topics created successfully"
```

### Spark Job Fails
```bash
docker-compose logs spark-master
# Check for errors in logs
```

### No Events in Topics
```bash
# Verify Spark job is running
docker-compose ps

# Re-run demo
python scripts/demo_scenario.py
```

### Python Import Errors
```bash
pip install -r requirements.txt
```

## Cost Estimates

| Usage | Cost |
|-------|------|
| Local (Docker) | $0 |
| AWS Demo (1 hour) | ~$0.50 |
| AWS Workshop (8 hours) | ~$7 |
| AWS Idle (monthly) | ~$0 |

## Learning Path

1. Read [00-overview.md](docs/00-overview.md)
2. Read [01-finra-4210.md](docs/01-finra-4210.md)
3. Read [02-what-is-tims.md](docs/02-what-is-tims.md)
4. Read [03-beta-weighting.md](docs/03-beta-weighting.md)
5. Read [04-architecture.md](docs/04-architecture.md)
6. Run [06-run-demo.md](docs/06-run-demo.md)
7. Complete [08-exercises.md](docs/08-exercises.md)

## Key Concepts

- **Event-Driven Architecture**: Kafka topics as event streams
- **Stateful Processing**: Maintaining position state in Spark
- **Stream Joins**: Combining multiple streams
- **Exactly-Once Semantics**: Ensuring correctness
- **Serverless**: Pay-per-use, auto-scaling
- **Auditability**: Immutable event logs
- **Regulatory Compliance**: FINRA Rule 4210

## Support

- GitHub Issues: Report bugs or ask questions
- Documentation: Comprehensive guides in `docs/`
- Blog Post: [https://lukelittle.com/posts/2026/02/real-time-margin-and-stress-monitoring-finra-rule-4210/](https://lukelittle.com/posts/2026/02/real-time-margin-and-stress-monitoring-finra-rule-4210/)

## License

MIT License - See LICENSE file

Educational use only. Not for production trading systems.
