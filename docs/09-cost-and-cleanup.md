# Cost and Cleanup

## AWS Cost Breakdown

This system uses serverless AWS services that scale to zero when not in use.

### Estimated Costs

#### Demo Run (1 hour) - With Pre-Initialized Workers

| Service | Usage | Cost |
|---------|-------|------|
| MSK Serverless | ~100 MB ingested | $0.25 |
| MSK Serverless | Storage (1 GB-hour) | $0.10 |
| EMR Serverless (pre-init) | 3 workers × 2 vCPU × 1 hour | $0.39 |
| EMR Serverless (job) | 2 vCPU × 1 hour | $0.13 |
| Lambda | 100 invocations | $0.00 |
| DynamoDB | 100 writes, 100 reads | $0.00 |
| S3 | 1 MB storage, 100 requests | $0.00 |
| **Total** | | **~$0.87** |

#### Workshop (8 hours, 20 students) - With Pre-Initialized Workers

| Service | Usage | Cost |
|---------|-------|------|
| MSK Serverless | ~2 GB ingested | $5.00 |
| MSK Serverless | Storage (8 GB-hours) | $0.80 |
| EMR Serverless (pre-init) | 3 workers × 2 vCPU × 8 hours | $3.12 |
| EMR Serverless (jobs) | 2 vCPU × 8 hours | $1.01 |
| Lambda | 2000 invocations | $0.00 |
| DynamoDB | 2000 writes, 2000 reads | $0.00 |
| S3 | 10 MB storage, 2000 requests | $0.00 |
| **Total** | | **~$9.93** |

#### Monthly (24/7 with Pre-Initialized Workers)

If you leave resources running continuously:

| Service | Usage | Cost |
|---------|-------|------|
| MSK Serverless | ~10 GB/month | $25.00 |
| MSK Serverless | Storage | $10.00 |
| EMR Serverless (pre-init) | 3 workers × 2 vCPU × 720 hours | $280.80 |
| EMR Serverless (jobs) | 2 vCPU × 720 hours | $91.20 |
| Lambda | 10k invocations | $0.00 |
| DynamoDB | On-demand, moderate traffic | $5.00 |
| S3 | 1 GB storage | $0.02 |
| **Total** | | **~$412/month** |

#### Monthly (Idle - Stopped)

If you stop the EMR application when not in use:

| Service | Usage | Cost |
|---------|-------|------|
| MSK Serverless | No traffic | $0.00 |
| EMR Serverless | Stopped | $0.00 |
| Lambda | No invocations | $0.00 |
| DynamoDB | On-demand, no traffic | $0.00 |
| S3 | 100 MB storage | $0.00 |
| **Total** | | **~$0.00** |

**Key Insight**: With pre-initialized workers, you pay for fast startup (~$0.39/hour) but can still stop completely when not needed.

### Cost Optimization Tips

### Understanding Pre-Initialized Workers

This system uses **pre-initialized workers** in EMR Serverless - a realistic production pattern.

**What are pre-initialized workers?**
- Workers that stay "warm" (ready to process)
- Reduces startup time from 2-4 minutes to 30-60 seconds
- Costs ~$0.39/hour even when idle

**Why use them?**
1. **Regulatory compliance**: Margin monitoring should be near real-time
2. **Risk management**: Delays could expose firm to losses
3. **Production reality**: Trading systems prioritize availability over cost
4. **User experience**: Traders expect instant feedback

**Cost vs. Latency Trade-off**:

| Configuration | Startup Time | Idle Cost | 8-Hour Workshop | 24/7 Monthly |
|---------------|--------------|-----------|-----------------|--------------|
| No pre-init | 2-4 minutes | $0/hour | $6.01 | $166/month |
| Pre-initialized | 30-60 seconds | $0.39/hour | $9.93 | $412/month |
| Always-on cluster | Instant | $11.67/hour | $93.36 | $8,400/month |

**When to use each**:

**No Pre-Initialization** (Cheapest):
- Batch processing (end-of-day reports)
- Development/testing
- Acceptable 2-4 minute latency
- Cost-sensitive workloads

**Pre-Initialized Workers** (Balanced):
- Real-time monitoring (this system)
- Production trading systems
- Regulatory compliance
- Sub-minute latency required

**Always-On Cluster** (Fastest):
- Legacy systems
- Sub-second latency required
- Complex cluster configurations
- When serverless limitations are blockers

### Our Choice: Pre-Initialized Workers

For this educational system, we use pre-initialized workers to teach realistic production patterns:

```hcl
# terraform/main.tf
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

**Cost Impact**:
- Workshop (8 hours): +$3.12 for warm workers
- Monthly (24/7): +$280.80 for warm workers
- **But**: Can still stop completely when not needed ($0 idle)

**Teaching Value**:
Students learn that production systems make trade-offs between:
- Cost (pay for idle capacity)
- Latency (fast startup)
- Availability (always ready)

This is a **realistic architectural decision** that firms face daily.

### Alternative: Remove Pre-Initialization

If you want to minimize costs for the workshop, you can remove pre-initialized workers:

```hcl
# Remove initial_capacity blocks from terraform/main.tf
resource "aws_emrserverless_application" "spark" {
  name          = "${var.project_name}-spark-app"
  release_label = "emr-7.0.0"
  type          = "Spark"
  
  maximum_capacity {
    cpu    = "4 vCPU"
    memory = "16 GB"
  }
  
  # No initial_capacity = cold start every time
  
  auto_start_configuration {
    enabled = true
  }
  
  auto_stop_configuration {
    enabled              = true
    idle_timeout_minutes = 15
  }
}
```

**Result**:
- Workshop cost: $6.01 (saves $3.92)
- First job: 2-4 minute startup
- Subsequent jobs: 30-60 seconds (if within 15 min)

**Trade-off**: Students wait longer for first job, but learn about cold starts.

### Recommendation

**Keep pre-initialized workers** for the workshop because:
1. ✅ Teaches realistic production patterns
2. ✅ Better student experience (no waiting)
3. ✅ Shows cost vs. latency trade-offs
4. ✅ Only $3.92 extra for 8-hour workshop
5. ✅ Can still demonstrate cold starts by stopping/restarting

The extra $3.92 is worth the educational value of showing how production systems work.

### Cost Monitoring

1. **Use Auto-Stop**: EMR Serverless auto-stops after 15 minutes idle (configured in Terraform)

2. **Set Retention**: Kafka topics retain 7 days (configurable)

3. **Use DynamoDB TTL**: Old records auto-delete after 30 days

4. **Use S3 Lifecycle**: Audit logs expire after 90 days

5. **Monitor Usage**: Set CloudWatch alarms for unexpected costs

### Cost Monitoring

#### Set Up Billing Alerts

```bash
# Create SNS topic for alerts
aws sns create-topic --name billing-alerts

# Subscribe your email
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-1:123456789012:billing-alerts \
  --protocol email \
  --notification-endpoint your-email@example.com

# Create CloudWatch alarm
aws cloudwatch put-metric-alarm \
  --alarm-name daily-cost-alert \
  --alarm-description "Alert if daily cost exceeds $10" \
  --metric-name EstimatedCharges \
  --namespace AWS/Billing \
  --statistic Maximum \
  --period 86400 \
  --evaluation-periods 1 \
  --threshold 10 \
  --comparison-operator GreaterThanThreshold \
  --alarm-actions arn:aws:sns:us-east-1:123456789012:billing-alerts
```

#### View Current Costs

```bash
# Install AWS CLI
# macOS: brew install awscli

# View current month costs
aws ce get-cost-and-usage \
  --time-period Start=$(date -u +%Y-%m-01),End=$(date -u +%Y-%m-%d) \
  --granularity MONTHLY \
  --metrics BlendedCost \
  --group-by Type=SERVICE
```

## Cleanup

### Option 1: Destroy Everything (Recommended)

```bash
cd terraform

# Preview what will be destroyed
terraform plan -destroy

# Destroy all resources
terraform destroy

# Confirm when prompted
```

This removes:
- MSK cluster
- EMR application
- Lambda function
- DynamoDB table
- S3 bucket (if empty)
- VPC and networking

**Note**: S3 bucket must be empty before Terraform can delete it.

### Option 2: Manual Cleanup

If Terraform fails or you want manual control:

#### Delete MSK Cluster

```bash
# List clusters
aws kafka list-clusters-v2

# Delete cluster
aws kafka delete-cluster \
  --cluster-arn arn:aws:kafka:us-east-1:123456789012:cluster/margin-risk-monitor-cluster/...
```

#### Delete EMR Application

```bash
# List applications
aws emr-serverless list-applications

# Stop application
aws emr-serverless stop-application \
  --application-id <application-id>

# Delete application
aws emr-serverless delete-application \
  --application-id <application-id>
```

#### Delete Lambda Function

```bash
# Delete function
aws lambda delete-function \
  --function-name margin-risk-monitor-enforcement
```

#### Delete DynamoDB Table

```bash
# Delete table
aws dynamodb delete-table \
  --table-name margin-risk-monitor-account-state
```

#### Empty and Delete S3 Bucket

```bash
# List buckets
aws s3 ls

# Empty bucket
aws s3 rm s3://margin-risk-monitor-artifacts-123456789012 --recursive

# Delete bucket
aws s3 rb s3://margin-risk-monitor-artifacts-123456789012
```

#### Delete VPC and Networking

```bash
# Delete VPC (this will fail if resources still attached)
aws ec2 delete-vpc --vpc-id vpc-xxxxx

# If it fails, delete dependencies first:
# - Security groups
# - Subnets
# - Internet gateways
# - Route tables
```

### Option 3: Pause (Keep Infrastructure, Stop Costs)

If you want to keep infrastructure but stop costs:

```bash
# Stop EMR application
aws emr-serverless stop-application \
  --application-id <application-id>

# MSK Serverless automatically stops billing when idle
# Lambda only charges on invocation
# DynamoDB on-demand only charges for requests
```

**Result**: Infrastructure remains, but costs drop to ~$0/month.

## Local Cleanup

### Stop Docker Containers

```bash
# Stop all containers
docker-compose down

# Remove volumes (clears all data)
docker-compose down -v

# Remove images
docker-compose down --rmi all

# Remove everything (nuclear option)
docker system prune -a --volumes
```

### Free Disk Space

```bash
# Check Docker disk usage
docker system df

# Remove unused images
docker image prune -a

# Remove unused volumes
docker volume prune

# Remove unused networks
docker network prune
```

## Verification

### Verify AWS Cleanup

```bash
# Check for remaining resources
aws kafka list-clusters-v2
aws emr-serverless list-applications
aws lambda list-functions | grep margin-risk
aws dynamodb list-tables | grep margin-risk
aws s3 ls | grep margin-risk

# Check for unexpected costs
aws ce get-cost-and-usage \
  --time-period Start=$(date -u +%Y-%m-01),End=$(date -u +%Y-%m-%d) \
  --granularity DAILY \
  --metrics BlendedCost
```

### Verify Local Cleanup

```bash
# Check Docker
docker ps -a
docker images
docker volume ls
docker network ls

# Check disk space
df -h
```

## Troubleshooting Cleanup

### Terraform Destroy Fails

**Issue**: Dependencies prevent deletion

**Solution**:
```bash
# Identify stuck resources
terraform state list

# Remove from state (if resource already deleted manually)
terraform state rm <resource>

# Force destroy
terraform destroy -auto-approve
```

### S3 Bucket Not Empty

**Issue**: Terraform can't delete non-empty bucket

**Solution**:
```bash
# Empty bucket first
aws s3 rm s3://bucket-name --recursive

# Then destroy
terraform destroy
```

### VPC Deletion Fails

**Issue**: Resources still attached to VPC

**Solution**:
```bash
# Find attached resources
aws ec2 describe-network-interfaces \
  --filters Name=vpc-id,Values=vpc-xxxxx

# Delete each resource
# Then delete VPC
```

### Lambda in VPC Won't Delete

**Issue**: ENIs (Elastic Network Interfaces) still attached

**Solution**:
```bash
# Wait 5-10 minutes for ENIs to detach
# AWS automatically cleans them up

# Or force detach
aws ec2 describe-network-interfaces \
  --filters Name=description,Values="AWS Lambda VPC ENI*"

aws ec2 delete-network-interface \
  --network-interface-id eni-xxxxx
```

## Cost Comparison: Serverless vs. Traditional

### Traditional Architecture (Always-On)

| Service | Monthly Cost |
|---------|--------------|
| EC2 Kafka (3 × m5.large) | $300 |
| EC2 Spark (2 × m5.xlarge) | $280 |
| RDS PostgreSQL (db.t3.medium) | $60 |
| **Total** | **$640/month** |

### Serverless Architecture (This System)

| Service | Monthly Cost (Idle) |
|---------|---------------------|
| MSK Serverless | $0 |
| EMR Serverless | $0 |
| Lambda | $0 |
| DynamoDB | $0 |
| S3 | $0 |
| **Total** | **$0/month** |

**Savings**: $640/month = $7,680/year

**For Workshop**: $7 total vs. $640/month = 99% cost reduction

## Best Practices

1. **Always Set Budgets**: Use AWS Budgets to cap spending

2. **Tag Resources**: Tag all resources with `Project=margin-risk-monitor` for cost tracking

3. **Use Auto-Stop**: Configure auto-stop for all compute resources

4. **Monitor Daily**: Check costs daily during development

5. **Clean Up Immediately**: Don't leave resources running overnight

6. **Use Terraform**: Infrastructure as code makes cleanup easy

7. **Test Locally First**: Use Docker Compose before deploying to AWS

## Summary

- **Demo cost**: ~$0.50
- **Workshop cost**: ~$7
- **Idle cost**: ~$0
- **Cleanup**: `terraform destroy`
- **Verification**: Check AWS console and billing

Serverless architecture provides massive cost savings for educational and intermittent workloads.

## Next Steps

- [00 - Overview](00-overview.md) - Review system design
- [08 - Exercises](08-exercises.md) - Extend the system
