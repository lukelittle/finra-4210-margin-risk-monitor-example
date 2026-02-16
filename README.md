# Real-Time Margin Risk Monitor

A graduate-level streaming architecture implementing real-time margin risk monitoring inspired by FINRA Rule 4210, portfolio margin methodology, TIMS (Theoretical Intermarket Margining System), and broker house beta-weighted stress testing.

## 🎓 Educational Purpose

This repository is designed for graduate computer science students studying cloud and distributed systems at UNC Charlotte. It demonstrates:

- Event-driven architecture with Kafka
- Streaming joins and stateful processing with Spark
- Financial risk modeling and portfolio margin mathematics
- Beta-weighted stress testing
- Control enforcement workflows
- Auditability and regulatory thinking

## ⚠️ Disclaimer

**This is an educational example only.**

- Not a production trading system
- Simplified risk mathematics for pedagogical purposes
- Not legal or financial advice
- Not suitable for actual trading or risk management
- Consult qualified professionals for production systems

## 🏗️ Architecture

### AWS Serverless Stack
- **Amazon MSK Serverless** - Event streaming backbone
- **EMR Serverless** - PySpark streaming jobs
- **AWS Lambda** - Enforcement logic (Python 3.11+)
- **API Gateway** - HTTP API for data ingestion
- **DynamoDB** - State indexing
- **S3** - Artifacts and audit trail
- **CloudWatch** - Monitoring and logging

### Local Development
- Docker Compose with Kafka and Spark
- Uses pre-built images (Confluent Kafka, Bitnami Spark)
- Mirrors AWS architecture for local testing

## 📊 What This System Does

1. **Continuously computes per-account margin risk**
2. **Implements maintenance margin logic** (Reg T style)
3. **Implements beta-weighted SPY stress testing**
4. **Implements TIMS-style scenario evaluation** (simplified)
5. **Detects accounts that would become underwater under stress**
6. **Escalates through enforcement ladder:**
   - Warning
   - Margin Call
   - Restriction (close-only)
   - Liquidation trigger
7. **Produces immutable audit trail**

## 🚀 Quick Start

### Local Development
```bash
# Start local stack
docker-compose up -d

# Run demo scenario
python scripts/demo_scenario.py

# Observe results
python scripts/observe_streams.py
```

### AWS Deployment
```bash
cd terraform
terraform init
terraform plan
terraform apply

# Setup for workshop (warms up workers)
./scripts/workshop_setup.sh

# Deploy Spark job
./scripts/deploy_spark_job.sh

# Run demo
python scripts/demo_scenario_aws.py
```

## 📚 Documentation

- [00 - Overview](docs/00-overview.md)
- [01 - FINRA Rule 4210](docs/01-finra-4210.md)
- [02 - What is TIMS?](docs/02-what-is-tims.md)
- [03 - Beta Weighting](docs/03-beta-weighting.md)
- [04 - Architecture](docs/04-architecture.md)
- [05 - Deploy AWS](docs/05-deploy-aws.md)
- [06 - Run Demo](docs/06-run-demo.md)
- [07 - Observe](docs/07-observe.md)
- [08 - Exercises](docs/08-exercises.md)
- [09 - Cost and Cleanup](docs/09-cost-and-cleanup.md)

**For Instructors**:
- [Workshop Guide](WORKSHOP_GUIDE.md) - Complete workshop setup and teaching guide
- [Architecture Explained](ARCHITECTURE_EXPLAINED.md) - Local vs. AWS, why Spark, why pre-init workers

## 📖 Blog Post

See [Real-Time Margin Risk Monitoring with FINRA Rule 4210](blog/posts/real-time-margin-risk-finra-4210.md) for a deep dive into the regulatory context and technical implementation.

## 🧮 Key Concepts

### Maintenance Margin (Reg T Style)
```
Maintenance Requirement = 25% × Market Value
Excess = Equity - Maintenance Requirement
```

### Beta-Weighted Stress Testing
```
Beta-Weighted Exposure = Σ (Position Value × Beta to SPY)
Stressed PnL = Beta-Weighted Exposure × SPY Move %
```

### TIMS-Style Portfolio Margin
```
Worst-Case Loss = min(PnL across all scenarios)
Portfolio Margin Requirement = |Worst-Case Loss|
```

## 📁 Repository Structure

```
.
├── docs/                    # Workshop documentation
├── blog/                    # Blog post
├── terraform/               # AWS infrastructure
├── spark/                   # PySpark streaming jobs
├── lambda/                  # Enforcement functions
├── docker/                  # Local development
├── scripts/                 # Demo and utilities
├── tests/                   # Unit and integration tests
└── data/                    # Sample data
```

## 🎯 Learning Objectives

After completing this workshop, students will understand:

1. **Regulatory Context**: FINRA Rule 4210, maintenance margin, portfolio margin
2. **Risk Mathematics**: Beta weighting, scenario analysis, worst-case loss
3. **Streaming Architecture**: Event-driven design, stateful processing, exactly-once semantics
4. **Cloud Patterns**: Serverless compute, managed streaming, infrastructure as code
5. **Operational Excellence**: Monitoring, auditability, cost optimization

## 💰 Cost Considerations

AWS resources are serverless with pre-initialized workers (realistic production pattern):
- MSK Serverless: ~$2.50/GB ingested + storage
- EMR Serverless (pre-init): ~$0.39/hour for warm workers + job costs
- Lambda: First 1M requests free
- Estimated workshop cost (8 hours): **~$10**
- Can stop completely when not needed: **$0 idle**

**Trade-off**: Pre-initialized workers cost more (~$3/workshop) but provide:
- Fast startup (30-60 sec vs. 2-4 min)
- Realistic production pattern
- Better student experience

See [Cost and Cleanup](docs/09-cost-and-cleanup.md) for details and alternatives.

## 🤝 Contributing

This is an educational project. Contributions that improve clarity, add exercises, or fix bugs are welcome.

## 📄 License

MIT License - See LICENSE file

## 🙏 Acknowledgments

- FINRA for regulatory guidance
- OCC for TIMS methodology
- UNC Charlotte Computer Science Department
