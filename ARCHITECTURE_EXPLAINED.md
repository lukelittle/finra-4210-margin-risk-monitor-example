# Architecture Explained

## Why Spark Streaming on EMR Serverless?

Students in your class are learning **EMR** (Elastic MapReduce), so this project uses **Spark Streaming on EMR Serverless** to align with their coursework.

## Local vs. AWS: Two Environments

### Local Development (Docker Compose)

**Purpose**: Testing and development on your laptop without AWS costs

**Components**:
- **Kafka + Zookeeper** (Confluent images) - Message broker
- **Spark** (Bitnami images) - Stream processing
- **Python services** - Demo scripts
- **DynamoDB Local** - State storage

**Key Point**: We're using **pre-built Docker images** from:
- [Confluent](https://hub.docker.com/r/confluentinc/cp-kafka) for Kafka
- [Bitnami](https://hub.docker.com/r/bitnami/spark) for Spark

We're **NOT creating custom images** - just pulling official ones and running them.

**Why Zookeeper?**: Kafka versions < 3.3 require Zookeeper for cluster coordination. Modern Kafka (3.3+) has KRaft mode (no Zookeeper needed), but the Confluent images still use Zookeeper for stability.

### AWS Production (Serverless)

**Purpose**: Production deployment that scales automatically

**Components**:
- **MSK Serverless** - Managed Kafka (no Zookeeper to manage!)
- **EMR Serverless** - Managed Spark (no clusters to manage!)
- **Lambda** - Enforcement logic
- **DynamoDB** - State storage
- **S3** - Audit trail

**Key Point**: Everything is **truly serverless**:
- MSK Serverless handles Kafka automatically
- EMR Serverless runs Spark jobs without managing clusters
- Auto-stops when idle (15 minutes)
- Pay only for what you use

## EMR Serverless vs. Traditional EMR

### Traditional EMR
- Always-on cluster
- Manual scaling
- Pay for idle time
- **Cost**: ~$280/month for 2 × m5.xlarge
- **Startup**: Instant (always running)

### EMR Serverless (No Pre-Init)
- No cluster management
- Auto-scaling
- Auto-stops after 15 minutes idle
- **Cost**: ~$0.05/vCPU-hour (only when running)
- **Startup**: 2-4 minutes (cold start)

### EMR Serverless (With Pre-Init) ⭐ Our Choice
- No cluster management
- Auto-scaling
- Keeps workers warm
- **Cost**: ~$0.39/hour for warm workers + job costs
- **Startup**: 30-60 seconds

**For this demo**: 
- Cold start: 2-4 minutes (first job)
- Warm start: 30-60 seconds (subsequent jobs)
- Pre-init cost: ~$3.12 for 8-hour workshop
- Can still stop completely: $0 when not in use

### Why Pre-Initialized Workers?

This system uses **pre-initialized workers** - a realistic production pattern:

**Benefits**:
1. **Fast startup**: 30-60 seconds vs. 2-4 minutes
2. **Regulatory compliance**: Margin monitoring should be near real-time
3. **Risk management**: Delays could expose firm to losses
4. **Production reality**: Trading systems prioritize availability over cost
5. **Better UX**: Traders expect instant feedback

**Cost Trade-off**:
- Pay $0.39/hour for idle workers
- Get sub-minute startup time
- Still cheaper than always-on cluster ($11.67/hour)
- Can stop completely when not needed

**Configuration** (in `terraform/main.tf`):
```hcl
resource "aws_emrserverless_application" "spark" {
  # Keep 1 driver + 2 executors warm
  initial_capacity {
    initial_capacity_type = "Driver"
    initial_capacity_config {
      worker_count = 1
      worker_configuration {
        cpu    = "2 vCPU"
        memory = "4 GB"
      }
    }
  }
  
  initial_capacity {
    initial_capacity_type = "Executor"
    initial_capacity_config {
      worker_count = 2
      worker_configuration {
        cpu    = "2 vCPU"
        memory = "4 GB"
      }
    }
  }
}
```

This teaches students that **production systems make trade-offs** between cost, latency, and availability.

## Why Spark Streaming?

**Spark Streaming** is the right choice for this educational project because:
- Students are learning EMR in class
- Spark is more widely known and taught
- Easier to understand for beginners
- Structured Streaming API is intuitive (SQL-like)
- Still demonstrates streaming concepts well
- 42% cheaper than alternatives ($0.13/hour vs. $0.22/hour)

**Trade-offs:**
- Micro-batch processing (5-10 second latency) vs. true streaming
- Higher latency than specialized streaming engines
- But: Perfectly acceptable for margin monitoring use case

## The Spark Job

The `spark/margin_calculator.py` file:

1. **Reads from Kafka** (fills, prices, betas)
2. **Maintains state** (cumulative positions per account)
3. **Joins streams** (positions + prices + betas)
4. **Computes risk** (margin requirements, stress tests)
5. **Writes to Kafka** (margin calculations, stress results)

This runs:
- **Locally**: In Docker using Bitnami Spark
- **AWS**: On EMR Serverless

Same code, different infrastructure!

## Cost Breakdown

### Local (Docker)
- **Cost**: $0
- **Resources**: Your laptop (8GB RAM, 4 CPU cores)

### AWS Demo (1 hour)
- **MSK Serverless**: $0.25 (100 MB ingested)
- **EMR Serverless**: $0.10 (2 vCPU × 1 hour)
- **Lambda**: $0.00 (free tier)
- **DynamoDB**: $0.00 (free tier)
- **S3**: $0.00 (free tier)
- **Total**: ~$0.35

### AWS Idle (monthly)
- **MSK Serverless**: $0 (no traffic)
- **EMR Serverless**: $0 (auto-stopped)
- **Lambda**: $0 (no invocations)
- **DynamoDB**: $0 (on-demand, no traffic)
- **S3**: $0.00 (minimal storage)
- **Total**: ~$0

## Key Takeaways

1. **Docker Compose is for local development only** - uses pre-built images
2. **AWS deployment is truly serverless** - EMR Serverless + MSK Serverless
3. **Same Spark code runs in both environments** - portability
4. **Zookeeper is only needed locally** - MSK Serverless handles it
5. **EMR Serverless auto-stops** - no idle costs
6. **Students learn EMR** - aligns with coursework

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    LOCAL (Docker Compose)                    │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ Zookeeper│  │  Kafka   │  │  Spark   │  │  Python  │   │
│  │(Confluent│  │(Confluent│  │ (Bitnami)│  │ Services │   │
│  │  image)  │  │  image)  │  │          │  │          │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
│                                                               │
│  Pre-built images - just docker-compose up!                  │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    AWS (Serverless)                          │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │   MSK    │  │   EMR    │  │  Lambda  │  │ DynamoDB │   │
│  │Serverless│  │Serverless│  │          │  │          │   │
│  │          │  │          │  │          │  │          │   │
│  │(Managed) │  │(Managed) │  │(Managed) │  │(Managed) │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
│                                                               │
│  Fully managed - no servers to manage!                       │
│  Auto-scales, auto-stops, pay-per-use                        │
└─────────────────────────────────────────────────────────────┘
```

## Questions?

**Q: Why not just use Lambda for everything?**
A: Spark/EMR is what students are learning in class. Plus, Spark is better for complex stateful stream processing.

**Q: Is EMR Serverless really serverless?**
A: Yes! No clusters to manage, auto-scales, auto-stops, pay-per-use. It's serverless compute for Spark jobs.

**Q: Why Zookeeper in Docker but not AWS?**
A: MSK Serverless manages Zookeeper internally. Locally, we use Confluent's images which include Zookeeper.

**Q: Why Spark instead of other streaming engines?**
A: Spark aligns with EMR coursework, is widely taught, and provides an intuitive API. It's perfect for learning streaming concepts.

**Q: What about Kafka Streams or ksqlDB?**
A: Those are great alternatives! But Spark is more widely taught and provides more flexibility for complex analytics.
