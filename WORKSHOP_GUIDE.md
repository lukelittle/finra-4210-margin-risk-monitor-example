# Workshop Guide: Real-Time Margin Risk Monitoring

## Overview

This guide explains how to run the workshop for graduate students, including the architectural decisions and cost trade-offs.

## Pre-Workshop Setup (Instructor)

### 1. Deploy Infrastructure (One Time)

```bash
# Clone repository
git clone https://github.com/lukelittle/real-time-margin-risk-monitor-example.git
cd real-time-margin-risk-monitor-example

# Deploy AWS infrastructure
cd terraform
terraform init
terraform apply  # Takes ~15 minutes

# Upload Spark job to S3
S3_BUCKET=$(terraform output -raw s3_bucket)
aws s3 cp ../spark/margin_calculator.py s3://$S3_BUCKET/spark/margin_calculator.py

cd ..
```

**Cost**: Infrastructure itself costs $0 when idle (serverless)

### 2. Warm Up Workers (Before Each Workshop)

Run this **10-15 minutes before workshop starts**:

```bash
./scripts/workshop_setup.sh
```

This script:
- ✅ Starts the EMR Serverless application
- ✅ Submits a warmup job to initialize workers
- ✅ Waits for workers to be ready (~3-4 minutes)
- ✅ Keeps workers warm for fast subsequent jobs

**Why?**
- Cold start: 2-4 minutes (unacceptable for demos)
- Warm start: 30-60 seconds (good student experience)
- Cost: $0.39/hour for warm workers (~$3.12 for 8-hour workshop)

**Teaching moment**: Explain that production systems keep workers warm for low latency, trading cost for performance.

## Workshop Timeline

### T-15 minutes: Instructor Setup
```bash
./scripts/workshop_setup.sh
```
- Application starts warming up
- Takes 3-4 minutes to be ready
- Workers stay warm for duration of workshop

### T-0 minutes: Workshop Begins

**Lecture (30 minutes)**:
1. FINRA Rule 4210 (maintenance margin)
2. Portfolio margin and TIMS
3. Beta weighting and stress testing
4. Streaming architecture overview

**Demo (15 minutes)**:
```bash
# Show local development first
docker-compose up -d
python scripts/demo_scenario.py
python scripts/observe_streams.py
```

Explain:
- Local uses Docker (Kafka + Spark)
- AWS uses MSK Serverless + EMR Serverless
- Same code runs in both environments

### T+45 minutes: Hands-On Lab

Students deploy to AWS and run demos:

```bash
# Each student (or groups of 2-3)
cd terraform
terraform apply  # Uses shared infrastructure

# Run demo
python scripts/demo_scenario_aws.py

# Observe results
python scripts/observe_streams.py
```

**Expected behavior**:
- First student: Job starts in 30-60 seconds (warm workers)
- Other students: Jobs start in 30-60 seconds (shared warm workers)
- No 2-4 minute waits!

### T+2 hours: Architecture Deep Dive

**Discuss trade-offs**:

| Pattern | Startup | Idle Cost | Use Case |
|---------|---------|-----------|----------|
| Cold start | 2-4 min | $0/hour | Batch, dev/test |
| Pre-init workers | 30-60 sec | $0.39/hour | Production, real-time |
| Always-on cluster | Instant | $11.67/hour | Legacy, sub-second latency |

**Key teaching points**:
1. Production systems prioritize availability over cost
2. Regulatory compliance often requires low latency
3. Architectural decisions involve trade-offs
4. Serverless doesn't mean "free" - it means "pay-per-use"

### T+3 hours: Exercises

Students complete exercises from [docs/08-exercises.md](docs/08-exercises.md):
1. Implement concentration add-on
2. Add volatility-based margin
3. Compare Reg T vs. portfolio margin
4. Build real-time dashboard
5. Implement liquidation logic

### T+7 hours: Wrap-Up

**Review**:
- What we built
- Why we made certain architectural choices
- How this applies to real production systems
- Cost vs. performance trade-offs

**Cleanup**:
```bash
# Application will auto-stop 15 minutes after last job
# Or manually stop:
aws emr-serverless stop-application --application-id $APP_ID

# Full cleanup (optional):
cd terraform
terraform destroy
```

## Cost Breakdown

### Per Workshop (8 hours, 20 students)

| Service | Cost | Notes |
|---------|------|-------|
| MSK Serverless | $5.80 | Kafka streaming |
| EMR Serverless (pre-init) | $3.12 | Warm workers |
| EMR Serverless (jobs) | $1.01 | Actual processing |
| Lambda | $0.00 | Free tier |
| DynamoDB | $0.00 | Free tier |
| S3 | $0.00 | Minimal storage |
| **Total** | **$9.93** | ~$0.50 per student |

### Cost Comparison

**Without pre-initialized workers**: $6.01 total
- Saves $3.92
- But: 2-4 minute cold starts
- Poor student experience

**With pre-initialized workers**: $9.93 total
- Costs $3.92 more
- But: 30-60 second warm starts
- Great student experience
- Teaches production patterns

**Recommendation**: Use pre-initialized workers. The extra $3.92 is worth it for:
1. Better student experience
2. Realistic production patterns
3. Teaching cost vs. latency trade-offs

## Architectural Decisions Explained

### Decision 1: Spark vs. Flink

**Chose**: Spark Streaming on EMR Serverless

**Why**:
- ✅ Students are learning EMR in class
- ✅ Spark is more widely known
- ✅ 42% cheaper than Flink ($0.13/hour vs. $0.22/hour)
- ✅ Auto-stops when idle (Flink requires manual stop)

**Trade-off**:
- ❌ Higher latency (5-10 sec vs. milliseconds)
- ❌ Micro-batches vs. true streaming

**When to use Flink**:
- Production systems needing sub-second latency
- Complex event-time processing
- Advanced stateful operations

### Decision 2: Pre-Initialized Workers

**Chose**: Keep workers warm

**Why**:
- ✅ Realistic production pattern
- ✅ Fast startup (30-60 sec vs. 2-4 min)
- ✅ Better student experience
- ✅ Teaches cost vs. latency trade-offs

**Trade-off**:
- ❌ $0.39/hour idle cost
- ❌ $3.12 extra for 8-hour workshop

**When to skip**:
- Cost-sensitive demos
- Teaching about cold starts
- Batch processing use cases

### Decision 3: Serverless vs. Always-On

**Chose**: Serverless (EMR Serverless + MSK Serverless)

**Why**:
- ✅ No cluster management
- ✅ Auto-scaling
- ✅ Pay-per-use
- ✅ Can stop completely ($0 idle)
- ✅ Modern cloud pattern

**Trade-off**:
- ❌ Cold start latency (mitigated with pre-init)
- ❌ Less control over cluster configuration

**When to use always-on**:
- Legacy systems
- Sub-second latency requirements
- Complex cluster configurations

## Teaching Points

### 1. Serverless Doesn't Mean Free

Students often think "serverless = no cost when idle". Clarify:

- **True**: No cost for stopped resources
- **False**: Pre-initialized workers cost money even when idle
- **Reality**: Production systems pay for availability

### 2. Cost vs. Latency Trade-Off

Every architectural decision involves trade-offs:

```
Cost ←→ Latency ←→ Complexity

Pick two:
- Low cost + Low latency = High complexity
- Low cost + Low complexity = High latency
- Low latency + Low complexity = High cost
```

### 3. Production vs. Development

Development priorities:
- Minimize cost
- Maximize flexibility
- Accept higher latency

Production priorities:
- Minimize latency
- Maximize availability
- Accept higher cost

### 4. Regulatory Compliance

Financial systems have unique requirements:
- Near real-time monitoring (not batch)
- Audit trails (immutable logs)
- Availability (can't be down during market hours)
- Compliance (FINRA, SEC regulations)

These requirements drive architectural decisions.

## Troubleshooting

### Workers Not Warming Up

**Symptom**: `workshop_setup.sh` times out

**Solution**:
```bash
# Check application status
aws emr-serverless get-application --application-id $APP_ID

# Check job status
aws emr-serverless get-job-run \
  --application-id $APP_ID \
  --job-run-id $JOB_RUN_ID

# View logs
aws logs tail /aws/emr-serverless/margin-risk-monitor --follow
```

### High Costs

**Symptom**: AWS bill higher than expected

**Solution**:
```bash
# Check if application is still running
aws emr-serverless list-applications

# Stop application
aws emr-serverless stop-application --application-id $APP_ID

# Check for running jobs
aws emr-serverless list-job-runs --application-id $APP_ID
```

### Students Can't Connect

**Symptom**: Students get Kafka connection errors

**Solution**:
- Verify MSK cluster is running
- Check security groups allow traffic
- Ensure IAM roles have correct permissions
- Verify VPC configuration

## Post-Workshop

### Cleanup

**Option 1**: Stop application (keeps infrastructure)
```bash
aws emr-serverless stop-application --application-id $APP_ID
# Cost: $0/hour
```

**Option 2**: Destroy everything
```bash
cd terraform
terraform destroy
# Cost: $0/hour
```

### Student Feedback

Ask students:
1. Did the pre-initialized workers improve the experience?
2. Was the cost vs. latency trade-off clear?
3. Do you understand why production systems make these choices?
4. What would you do differently?

### Next Steps

Students can:
1. Complete remaining exercises
2. Deploy their own version
3. Experiment with different configurations
4. Compare Spark vs. Flink implementations

## Summary

This workshop teaches:
- ✅ Financial risk modeling (FINRA 4210, TIMS, beta weighting)
- ✅ Streaming architectures (Kafka, Spark Streaming)
- ✅ Cloud patterns (serverless, auto-scaling, pay-per-use)
- ✅ Architectural trade-offs (cost vs. latency vs. complexity)
- ✅ Production thinking (availability, compliance, monitoring)

**Key takeaway**: Architectural decisions involve trade-offs. There's no "best" solution - only trade-offs that align with your requirements and constraints.

The extra $3.92 for pre-initialized workers teaches this lesson better than any lecture could.
