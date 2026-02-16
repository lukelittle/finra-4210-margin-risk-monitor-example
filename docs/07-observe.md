# Observe

This guide covers monitoring and observability for the margin risk monitoring system.

## Overview

Observability is critical for:
- Understanding system behavior
- Debugging issues
- Regulatory compliance (audit trail)
- Performance optimization

## Observability Stack

### Local (Docker)

- Kafka topics (raw events)
- Spark UI (job metrics)
- Python scripts (custom observers)

### AWS

- CloudWatch Logs (application logs)
- CloudWatch Metrics (system metrics)
- DynamoDB (state snapshots)
- S3 (audit trail)
- X-Ray (distributed tracing, optional)

## Kafka Topics

### View All Topics

```bash
# Local
docker-compose exec kafka kafka-topics \
  --bootstrap-server localhost:9092 \
  --list

# AWS
kafka-topics.sh --list \
  --bootstrap-server $KAFKA_BROKERS \
  --command-config client.properties
```

### Consume Topic (Real-Time)

```bash
# Local - margin calculations
docker-compose exec kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic margin.calc.v1 \
  --from-beginning

# Local - stress tests
docker-compose exec kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic stress.beta_spy.v1 \
  --from-beginning

# Local - margin calls
docker-compose exec kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic margin.calls.v1 \
  --from-beginning
```

### Use Custom Observer

```bash
# Run observer script
python scripts/observe_streams.py
```

This displays all events in real-time with color coding and formatting.

## Spark Monitoring

### Spark UI (Local)

Open http://localhost:8080

Shows:
- Running applications
- Completed applications
- Worker status
- Resource usage

### Spark Application UI

When a Spark job is running, access its UI at http://localhost:4040

Shows:
- Jobs and stages
- SQL queries
- Storage
- Environment
- Executors

### Key Metrics

- **Input Rate**: Events/second from Kafka
- **Processing Rate**: Events/second processed
- **Batch Duration**: Time to process each micro-batch
- **Scheduling Delay**: Lag between batches

**Healthy System**:
- Processing Rate > Input Rate
- Scheduling Delay < 1 second
- No failed tasks

### Spark Logs

```bash
# Local
docker-compose logs spark-master
docker-compose logs spark-worker

# Follow logs
docker-compose logs -f spark-master
```

## Lambda Monitoring (AWS)

### CloudWatch Logs

```bash
# Tail logs
aws logs tail /aws/lambda/margin-risk-monitor-enforcement --follow

# Query logs
aws logs filter-log-events \
  --log-group-name /aws/lambda/margin-risk-monitor-enforcement \
  --filter-pattern "ERROR"

# Get recent errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/margin-risk-monitor-enforcement \
  --filter-pattern "ERROR" \
  --start-time $(date -u -d '1 hour ago' +%s)000
```

### CloudWatch Metrics

```bash
# Get invocation count
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value=margin-risk-monitor-enforcement \
  --start-time $(date -u -d '1 hour ago' --iso-8601) \
  --end-time $(date -u --iso-8601) \
  --period 300 \
  --statistics Sum

# Get error count
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Errors \
  --dimensions Name=FunctionName,Value=margin-risk-monitor-enforcement \
  --start-time $(date -u -d '1 hour ago' --iso-8601) \
  --end-time $(date -u --iso-8601) \
  --period 300 \
  --statistics Sum

# Get duration
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Duration \
  --dimensions Name=FunctionName,Value=margin-risk-monitor-enforcement \
  --start-time $(date -u -d '1 hour ago' --iso-8601) \
  --end-time $(date -u --iso-8601) \
  --period 300 \
  --statistics Average,Maximum
```

## EMR Serverless Monitoring (AWS)

### Job Status

```bash
# List job runs
aws emr-serverless list-job-runs \
  --application-id $EMR_APP_ID

# Get job details
aws emr-serverless get-job-run \
  --application-id $EMR_APP_ID \
  --job-run-id $JOB_RUN_ID
```

### CloudWatch Logs

```bash
# Tail EMR logs
aws logs tail /aws/emr-serverless/margin-risk-monitor --follow

# Filter for errors
aws logs filter-log-events \
  --log-group-name /aws/emr-serverless/margin-risk-monitor \
  --filter-pattern "ERROR"
```

### Spark UI (AWS)

EMR Serverless provides Spark UI access:

```bash
# Get Spark UI URL
aws emr-serverless get-dashboard-for-job-run \
  --application-id $EMR_APP_ID \
  --job-run-id $JOB_RUN_ID
```

## DynamoDB Monitoring

### Query Account State

```bash
# Get latest state for account
aws dynamodb query \
  --table-name margin-risk-monitor-account-state \
  --key-condition-expression "account_id = :aid" \
  --expression-attribute-values '{":aid":{"S":"ACC_DEMO_001"}}' \
  --scan-index-forward false \
  --limit 1

# Get state history
aws dynamodb query \
  --table-name margin-risk-monitor-account-state \
  --key-condition-expression "account_id = :aid" \
  --expression-attribute-values '{":aid":{"S":"ACC_DEMO_001"}}' \
  --scan-index-forward false \
  --limit 10
```

### DynamoDB Metrics

```bash
# Get read capacity
aws cloudwatch get-metric-statistics \
  --namespace AWS/DynamoDB \
  --metric-name ConsumedReadCapacityUnits \
  --dimensions Name=TableName,Value=margin-risk-monitor-account-state \
  --start-time $(date -u -d '1 hour ago' --iso-8601) \
  --end-time $(date -u --iso-8601) \
  --period 300 \
  --statistics Sum

# Get write capacity
aws cloudwatch get-metric-statistics \
  --namespace AWS/DynamoDB \
  --metric-name ConsumedWriteCapacityUnits \
  --dimensions Name=TableName,Value=margin-risk-monitor-account-state \
  --start-time $(date -u -d '1 hour ago' --iso-8601) \
  --end-time $(date -u --iso-8601) \
  --period 300 \
  --statistics Sum
```

## S3 Audit Trail

### List Audit Files

```bash
# List all audit files
aws s3 ls s3://$S3_BUCKET/audit/ --recursive

# List today's audit files
aws s3 ls s3://$S3_BUCKET/audit/year=$(date +%Y)/month=$(date +%-m)/day=$(date +%-d)/ --recursive
```

### Query with Athena

Create Athena table:

```sql
CREATE EXTERNAL TABLE IF NOT EXISTS audit_events (
  event_id STRING,
  event_type STRING,
  account_id STRING,
  timestamp STRING,
  details STRUCT<
    deficiency: DOUBLE,
    excess: DOUBLE,
    equity: DOUBLE,
    maintenance_req: DOUBLE,
    scenario: DOUBLE,
    reason: STRING
  >,
  correlation_id STRING
)
PARTITIONED BY (
  year INT,
  month INT,
  day INT,
  hour INT
)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
LOCATION 's3://margin-risk-monitor-artifacts-123456789012/audit/';
```

Query:

```sql
-- Get all margin calls for an account
SELECT *
FROM audit_events
WHERE account_id = 'ACC_DEMO_001'
  AND event_type = 'MARGIN_CALL_ISSUED'
ORDER BY timestamp DESC;

-- Count events by type
SELECT event_type, COUNT(*) as count
FROM audit_events
WHERE year = 2026 AND month = 2 AND day = 16
GROUP BY event_type
ORDER BY count DESC;

-- Find accounts with liquidations
SELECT DISTINCT account_id
FROM audit_events
WHERE event_type = 'LIQUIDATION_TRIGGERED'
  AND year = 2026 AND month = 2;
```

## Custom Dashboards

### CloudWatch Dashboard

Create dashboard:

```bash
aws cloudwatch put-dashboard \
  --dashboard-name margin-risk-monitor \
  --dashboard-body file://dashboard.json
```

`dashboard.json`:
```json
{
  "widgets": [
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["AWS/Lambda", "Invocations", {"stat": "Sum"}],
          [".", "Errors", {"stat": "Sum"}]
        ],
        "period": 300,
        "stat": "Sum",
        "region": "us-east-1",
        "title": "Lambda Invocations & Errors"
      }
    },
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["AWS/DynamoDB", "ConsumedReadCapacityUnits", {"stat": "Sum"}],
          [".", "ConsumedWriteCapacityUnits", {"stat": "Sum"}]
        ],
        "period": 300,
        "stat": "Sum",
        "region": "us-east-1",
        "title": "DynamoDB Capacity"
      }
    }
  ]
}
```

### Grafana (Optional)

For advanced visualization:

1. Install Grafana
2. Add CloudWatch data source
3. Create dashboards for:
   - Kafka lag
   - Spark processing rate
   - Lambda invocations
   - Margin distribution
   - Enforcement actions

## Alerting

### CloudWatch Alarms

```bash
# Alert on Lambda errors
aws cloudwatch put-metric-alarm \
  --alarm-name margin-risk-lambda-errors \
  --alarm-description "Alert on Lambda errors" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --evaluation-periods 1 \
  --threshold 5 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=FunctionName,Value=margin-risk-monitor-enforcement \
  --alarm-actions arn:aws:sns:us-east-1:123456789012:alerts

# Alert on Spark job failure
aws cloudwatch put-metric-alarm \
  --alarm-name margin-risk-spark-failure \
  --alarm-description "Alert on Spark job failure" \
  --metric-name JobsFailed \
  --namespace AWS/EMRServerless \
  --statistic Sum \
  --period 300 \
  --evaluation-periods 1 \
  --threshold 1 \
  --comparison-operator GreaterThanThreshold \
  --alarm-actions arn:aws:sns:us-east-1:123456789012:alerts
```

## Debugging Workflows

### Trace a Margin Call

1. **Find margin call event**:
   ```bash
   aws logs filter-log-events \
     --log-group-name /aws/lambda/margin-risk-monitor-enforcement \
     --filter-pattern "MARGIN_CALL_ISSUED"
   ```

2. **Get correlation ID** from log

3. **Query audit trail**:
   ```sql
   SELECT *
   FROM audit_events
   WHERE correlation_id = '<correlation_id>'
   ORDER BY timestamp;
   ```

4. **Trace back to source**:
   - Find margin calculation that triggered call
   - Find price update that caused deficiency
   - Find original fill that created position

### Debug Spark Job

1. **Check job status**:
   ```bash
   aws emr-serverless get-job-run \
     --application-id $EMR_APP_ID \
     --job-run-id $JOB_RUN_ID
   ```

2. **View logs**:
   ```bash
   aws logs tail /aws/emr-serverless/margin-risk-monitor --follow
   ```

3. **Check Spark UI** for failed tasks

4. **Common issues**:
   - Kafka connection timeout → Check security groups
   - Out of memory → Increase executor memory
   - Checkpoint corruption → Delete checkpoint directory

## Performance Metrics

### Key Performance Indicators

| Metric | Target | Critical |
|--------|--------|----------|
| End-to-end latency | < 10s | > 30s |
| Spark processing rate | > input rate | < input rate |
| Lambda duration | < 5s | > 30s |
| Kafka lag | < 100 messages | > 1000 messages |
| Error rate | < 0.1% | > 1% |

### Measure End-to-End Latency

1. Send fill with timestamp
2. Observe margin call with timestamp
3. Compute difference

```python
fill_time = datetime.fromisoformat(fill['timestamp'])
call_time = datetime.fromisoformat(margin_call['timestamp'])
latency = (call_time - fill_time).total_seconds()
print(f"End-to-end latency: {latency:.2f}s")
```

## Best Practices

1. **Use Correlation IDs**: Track events across components
2. **Structured Logging**: Use JSON for easy parsing
3. **Set Alarms**: Don't wait for users to report issues
4. **Monitor Costs**: Track spending daily
5. **Regular Reviews**: Check dashboards weekly
6. **Audit Trail**: Query regularly to verify correctness
7. **Load Testing**: Test with realistic volumes

## Next Steps

- [08 - Exercises](08-exercises.md) - Extend the system
- [09 - Cost and Cleanup](09-cost-and-cleanup.md) - Manage costs
