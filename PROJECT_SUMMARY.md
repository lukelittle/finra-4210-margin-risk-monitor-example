# Project Summary: Real-Time Margin Risk Monitor

## Overview

This repository implements a production-grade streaming architecture for real-time margin risk monitoring, designed to teach graduate computer science students about event-driven systems, financial risk modeling, and cloud computing.

## What Students Will Learn

### 1. Regulatory & Financial Concepts

- **FINRA Rule 4210**: Maintenance margin requirements (25% baseline)
- **Portfolio Margin**: Risk-based requirements using scenario analysis
- **TIMS**: Theoretical Intermarket Margining System methodology
- **Beta Weighting**: Converting portfolios to market-equivalent exposure
- **House Requirements**: How firms impose stricter rules than regulations
- **Enforcement Ladder**: Warning → Margin Call → Restriction → Liquidation

### 2. Streaming Architecture

- **Event-Driven Design**: Kafka topics as event streams
- **Stateful Processing**: Maintaining position state in Spark
- **Stream Joins**: Combining fills, prices, and betas
- **Exactly-Once Semantics**: Ensuring correctness
- **Watermarking**: Handling late-arriving events
- **Micro-Batching**: Balancing latency and throughput

### 3. Cloud & Distributed Systems

- **Serverless Architecture**: MSK, EMR, Lambda
- **Auto-Scaling**: Pay-per-use compute
- **Infrastructure as Code**: Terraform
- **Observability**: CloudWatch, metrics, logs, traces
- **Cost Optimization**: Serverless vs. always-on
- **Fault Tolerance**: Checkpointing, retries, DLQs

### 4. Software Engineering

- **Clean Code**: Readable, maintainable implementations
- **Documentation**: Comprehensive guides and examples
- **Testing**: Unit tests, integration tests, scenarios
- **Deployment**: Local (Docker) and cloud (AWS)
- **Monitoring**: Real-time observability
- **Auditability**: Immutable event logs

## System Architecture

```
Data Sources (Fills, Prices, Betas)
    ↓
Kafka Topics (Event Streams)
    ↓
Spark Streaming (Risk Calculation)
    ↓
Kafka Topics (Margin, Stress Results)
    ↓
Lambda (Enforcement Logic)
    ↓
Kafka Topics (Margin Calls, Restrictions, Liquidations)
    ↓
Storage (DynamoDB State, S3 Audit Trail)
```

## Key Components

### 1. Spark Streaming Job (`spark/margin_calculator.py`)

- Consumes fills, prices, betas from Kafka
- Maintains cumulative position state per account
- Joins streams to enrich positions
- Computes maintenance margin requirements
- Performs beta-weighted stress testing
- Evaluates TIMS-style scenarios
- Emits results to output topics

**Key Concepts**: Stateful aggregation, stream joins, windowing

### 2. Lambda Enforcement (`lambda/enforcement/handler.py`)

- Consumes margin and stress events
- Applies escalation ladder logic
- Emits control events (margin calls, restrictions)
- Writes to DynamoDB (state index)
- Writes to S3 (audit trail)

**Key Concepts**: Event-driven functions, idempotency, correlation IDs

### 3. Infrastructure (`terraform/main.tf`)

- MSK Serverless cluster
- EMR Serverless application
- Lambda function with VPC access
- DynamoDB table with TTL
- S3 bucket with lifecycle policies
- IAM roles with least privilege

**Key Concepts**: Infrastructure as code, security, cost optimization

## Risk Methodologies Implemented

### 1. Maintenance Margin (Reg T Style)

```
Maintenance Requirement = 25% × Market Value
Excess = Equity - Maintenance Requirement
```

If Excess < 0, issue margin call.

### 2. Concentration Add-On (House Rule)

```
If (Position / Portfolio) > 30%:
    Additional Margin = 10% × Position Value
```

Protects against idiosyncratic risk.

### 3. Beta-Weighted Stress Testing

```
Beta-Weighted Exposure = Σ (Position Value × Beta)
Stressed PnL = Beta-Weighted Exposure × SPY Move %
```

Apply scenarios: SPY -8%, -6%, -4%, -2%, 0%, +2%, +4%, +6%

If underwater in severe scenario (≥6%), restrict account.

### 4. TIMS-Style Portfolio Margin

```
For each scenario (-15% to +15%):
    Compute portfolio PnL
Worst-Case Loss = min(PnL)
Portfolio Margin = |Worst-Case Loss|
```

Compare to Reg T margin to show capital efficiency.

## Demo Scenario

The demo simulates a concentrated high-beta position under market stress:

1. **Initial State**: Account with 500 NVDA shares (β=1.8) at $400
2. **Market Decline**: SPY drops 8% over the day
3. **Position Impact**: NVDA drops 16% (1.8× beta effect)
4. **Risk Detection**: Stress tests show underwater in severe scenarios
5. **Enforcement**: System issues warnings, margin calls, restrictions

Students observe:
- Real-time margin calculations
- Stress test results
- Enforcement actions
- Audit trail

## Repository Structure

```
.
├── README.md                    # Project overview
├── LICENSE                      # MIT License
├── CONTRIBUTING.md              # Contribution guidelines
├── PROJECT_SUMMARY.md           # This file
├── requirements.txt             # Python dependencies
├── docker-compose.yml           # Local development stack
│
├── docs/                        # Workshop documentation
│   ├── 00-overview.md           # System overview
│   ├── 01-finra-4210.md         # Regulatory context
│   ├── 02-what-is-tims.md       # Portfolio margin
│   ├── 03-beta-weighting.md     # Stress testing
│   ├── 04-architecture.md       # System design
│   ├── 05-deploy-aws.md         # AWS deployment
│   ├── 06-run-demo.md           # Local demo
│   ├── 07-observe.md            # Observability
│   ├── 08-exercises.md          # Student exercises
│   └── 09-cost-and-cleanup.md   # Cost management
│
├── blog/                        # Blog post
│   └── posts/
│       └── real-time-margin-risk-finra-4210.md
│
├── spark/                       # PySpark streaming jobs
│   └── margin_calculator.py     # Main risk calculator
│
├── lambda/                      # AWS Lambda functions
│   └── enforcement/
│       └── handler.py           # Enforcement logic
│
├── terraform/                   # Infrastructure as code
│   └── main.tf                  # AWS resources
│
├── scripts/                     # Utilities and demos
│   ├── quick_start.sh           # One-command setup
│   ├── demo_scenario.py         # Demo scenario
│   ├── observe_streams.py       # Event observer
│   └── generate_sample_data.py  # Data generator
│
├── docker/                      # Docker configurations
│   └── Dockerfile.python        # Python services
│
└── data/                        # Sample data (gitignored)
```

## Quick Start

```bash
# Clone repository
git clone https://github.com/lukelittle/real-time-margin-risk-monitor-example.git
cd real-time-margin-risk-monitor-example

# Run quick start script
./scripts/quick_start.sh

# Or manually:
docker-compose up -d
pip install -r requirements.txt
python scripts/demo_scenario.py
python scripts/observe_streams.py
```

## Cost Analysis

### Local Development
- **Cost**: $0 (runs on your laptop)
- **Resources**: 8GB RAM, 4 CPU cores

### AWS Demo (1 hour)
- **MSK Serverless**: $0.25
- **EMR Serverless**: $0.14
- **Lambda**: $0.00 (free tier)
- **DynamoDB**: $0.00 (free tier)
- **S3**: $0.00 (free tier)
- **Total**: ~$0.50

### AWS Workshop (8 hours, 20 students)
- **Total**: ~$7.00

### AWS Idle (monthly)
- **Total**: ~$0.00 (serverless scales to zero)

**Comparison**: Traditional always-on architecture would cost ~$640/month.

## Learning Outcomes

After completing this workshop, students will be able to:

1. **Explain** FINRA margin requirements and portfolio margin methodology
2. **Implement** stateful stream processing with Spark Structured Streaming
3. **Design** event-driven architectures with Kafka
4. **Deploy** serverless applications to AWS
5. **Monitor** distributed systems with CloudWatch and custom tools
6. **Optimize** cloud costs using serverless patterns
7. **Build** audit trails for regulatory compliance
8. **Apply** financial risk concepts to software systems

## Extensions & Exercises

The repository includes 8 exercises for students:

1. Implement concentration add-on
2. Add volatility-based margin
3. Compare Reg T vs. portfolio margin
4. Build real-time dashboard
5. Implement liquidation logic
6. Add historical backtesting
7. Aggregate firm-wide risk
8. Send margin call notifications

Each exercise reinforces concepts and adds production-ready features.

## Production Considerations

This is an educational system. For production use, consider:

- **Options & Derivatives**: Full TIMS implementation with Greeks
- **Real-Time Pricing**: Sub-second market data feeds
- **Scalability**: Thousands of accounts, millions of positions
- **Compliance**: Full FINRA/SEC regulatory requirements
- **Risk Models**: VaR, Expected Shortfall, stress scenarios
- **Execution**: Actual liquidation logic with smart order routing
- **Monitoring**: 24/7 operations, alerting, incident response
- **Security**: Encryption, access controls, audit logs
- **Testing**: Extensive unit, integration, and load testing
- **Documentation**: Runbooks, disaster recovery plans

## Acknowledgments

- **FINRA** for regulatory guidance
- **OCC** for TIMS methodology
- **UNC Charlotte** Computer Science Department
- **Open Source Community** for tools and frameworks

## License

MIT License - See LICENSE file

## Contact

For questions or feedback:
- Open an issue on GitHub
- Email: [contact information]

---

**Disclaimer**: This is an educational example with simplified risk mathematics. It is not intended for production trading systems or actual financial risk management. Consult qualified professionals for production implementations.
