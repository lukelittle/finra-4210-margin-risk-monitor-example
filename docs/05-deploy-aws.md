# Deploy to AWS

This guide walks through deploying the system to AWS using Terraform.

## Prerequisites

- AWS account with appropriate permissions
- AWS CLI installed and configured
- Terraform 1.0+ installed
- Python 3.11+ for packaging Lambda functions

## Step 1: Configure AWS Credentials

```bash
# Configure AWS CLI
aws configure

# Verify credentials
aws sts get-caller-identity
```

## Step 2: Review Terraform Configuration

```bash
cd terraform

# Review variables
cat main.tf | grep variable

# Optionally create terraform.tfvars
cat > terraform.tfvars <<EOF
aws_region = "us-east-1"
environment = "dev"
project_name = "margin-risk-monitor"
EOF
```

## Step 3: Initialize Terraform

```bash
# Initialize Terraform
terraform init

# Validate configuration
terraform validate

# Preview changes
terraform plan
```

Expected output:
- VPC and subnets
- MSK Serverless cluster
- EMR Serverless application
- Lambda function
- DynamoDB table
- S3 bucket
- IAM roles and policies

## Step 4: Deploy Infrastructure

```bash
# Apply configuration
terraform apply

# Review plan and type 'yes' to confirm
```

This takes ~10-15 minutes. MSK cluster creation is the slowest part.

## Step 5: Package and Deploy Lambda Function

```bash
# Create deployment package
cd ../lambda/enforcement
pip install -r requirements.txt -t package/
cd package
zip -r ../lambda_deployment.zip .
cd ..
zip -g lambda_deployment.zip handler.py

# Upload to Lambda
aws lambda update-function-code \
  --function-name margin-risk-monitor-enforcement \
  --zip-file fileb://lambda_deployment.zip
```

## Step 6: Upload Spark Job to S3

```bash
# Get S3 bucket name from Terraform output
S3_BUCKET=$(terraform output -raw s3_bucket)

# Upload Spark job
aws s3 cp ../spark/margin_calculator.py s3://$S3_BUCKET/spark/margin_calculator.py

# Verify upload
aws s3 ls s3://$S3_BUCKET/spark/
```

## Step 7: Configure Lambda Event Source Mapping

```bash
# Get MSK cluster ARN
MSK_ARN=$(terraform output -raw msk_cluster_arn)

# Create event source mapping for margin.calc.v1
aws lambda create-event-source-mapping \
  --function-name margin-risk-monitor-enforcement \
  --event-source-arn $MSK_ARN \
  --topics margin.calc.v1 \
  --starting-position LATEST \
  --batch-size 100 \
  --maximum-batching-window-in-seconds 5

# Create event source mapping for stress.beta_spy.v1
aws lambda create-event-source-mapping \
  --function-name margin-risk-monitor-enforcement \
  --event-source-arn $MSK_ARN \
  --topics stress.beta_spy.v1 \
  --starting-position LATEST \
  --batch-size 100 \
  --maximum-batching-window-in-seconds 5
```

## Step 8: Start EMR Serverless Job

```bash
# Get EMR application ID
EMR_APP_ID=$(terraform output -raw emr_application_id)

# Get IAM role ARN
EMR_ROLE_ARN=$(aws iam get-role --role-name margin-risk-monitor-emr-serverless-role --query 'Role.Arn' --output text)

# Get Kafka bootstrap brokers
KAFKA_BROKERS=$(terraform output -raw msk_bootstrap_brokers)

# Start Spark job
aws emr-serverless start-job-run \
  --application-id $EMR_APP_ID \
  --execution-role-arn $EMR_ROLE_ARN \
  --job-driver '{
    "sparkSubmit": {
      "entryPoint": "s3://'$S3_BUCKET'/spark/margin_calculator.py",
      "sparkSubmitParameters": "--conf spark.executor.memory=4g --conf spark.executor.cores=2 --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0"
    }
  }' \
  --configuration-overrides '{
    "monitoringConfiguration": {
      "cloudWatchLoggingConfiguration": {
        "enabled": true,
        "logGroupName": "/aws/emr-serverless/margin-risk-monitor"
      }
    }
  }' \
  --name "margin-risk-calculator"

# Save job run ID
JOB_RUN_ID=<output-from-above>
```

## Step 9: Create Kafka Topics

```bash
# Install Kafka client tools
# macOS: brew install kafka
# Linux: apt-get install kafka

# Create topics (if not auto-created)
kafka-topics.sh --create \
  --bootstrap-server $KAFKA_BROKERS \
  --command-config client.properties \
  --topic fills.v1 \
  --partitions 3 \
  --replication-factor 2

# Repeat for other topics...
```

Create `client.properties`:
```properties
security.protocol=SASL_SSL
sasl.mechanism=AWS_MSK_IAM
sasl.jaas.config=software.amazon.msk.auth.iam.IAMLoginModule required;
sasl.client.callback.handler.class=software.amazon.msk.auth.iam.IAMClientCallbackHandler
```

## Step 10: Deploy API Gateway (Optional)

For ingesting data via HTTP:

```bash
# Create API Gateway
aws apigatewayv2 create-api \
  --name margin-risk-monitor-api \
  --protocol-type HTTP \
  --target arn:aws:lambda:us-east-1:123456789012:function:margin-risk-monitor-ingest

# Get API endpoint
API_ENDPOINT=$(aws apigatewayv2 get-apis --query 'Items[?Name==`margin-risk-monitor-api`].ApiEndpoint' --output text)

echo "API Endpoint: $API_ENDPOINT"
```

## Step 11: Test Deployment

```bash
# Send test fill
curl -X POST $API_ENDPOINT/fills \
  -H "Content-Type: application/json" \
  -d '{
    "account_id": "ACC_TEST_001",
    "symbol": "AAPL",
    "qty": 100,
    "price": 150.00,
    "timestamp": '$(date +%s000)',
    "fill_id": "'$(uuidgen)'"
  }'

# Send test price
curl -X POST $API_ENDPOINT/prices \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "AAPL",
    "price": 150.00,
    "timestamp": '$(date +%s000)'
  }'

# Send test beta
curl -X POST $API_ENDPOINT/betas \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "AAPL",
    "beta": 1.2,
    "timestamp": '$(date +%s000)'
  }'
```

## Step 12: Monitor Deployment

### CloudWatch Logs

```bash
# View EMR Serverless logs
aws logs tail /aws/emr-serverless/margin-risk-monitor --follow

# View Lambda logs
aws logs tail /aws/lambda/margin-risk-monitor-enforcement --follow
```

### EMR Job Status

```bash
# Check job status
aws emr-serverless get-job-run \
  --application-id $EMR_APP_ID \
  --job-run-id $JOB_RUN_ID

# List all job runs
aws emr-serverless list-job-runs \
  --application-id $EMR_APP_ID
```

### Kafka Topics

```bash
# List topics
kafka-topics.sh --list \
  --bootstrap-server $KAFKA_BROKERS \
  --command-config client.properties

# Consume margin calculations
kafka-console-consumer.sh \
  --bootstrap-server $KAFKA_BROKERS \
  --consumer.config client.properties \
  --topic margin.calc.v1 \
  --from-beginning
```

### DynamoDB

```bash
# Query account state
aws dynamodb query \
  --table-name margin-risk-monitor-account-state \
  --key-condition-expression "account_id = :aid" \
  --expression-attribute-values '{":aid":{"S":"ACC_TEST_001"}}'
```

### S3 Audit Trail

```bash
# List audit files
aws s3 ls s3://$S3_BUCKET/audit/ --recursive

# Download audit file
aws s3 cp s3://$S3_BUCKET/audit/year=2026/month=02/day=16/hour=14/<file>.json .

# View contents
cat <file>.json | jq .
```

## Step 13: Run Demo Scenario (AWS)

Modify `scripts/demo_scenario.py` to use AWS endpoints:

```python
# Update configuration
KAFKA_BROKERS = '<MSK_BOOTSTRAP_BROKERS>'  # From Terraform output
API_ENDPOINT = '<API_GATEWAY_ENDPOINT>'    # From Step 10

# Use IAM authentication for Kafka
producer = KafkaProducer(
    bootstrap_servers=KAFKA_BROKERS.split(','),
    security_protocol='SASL_SSL',
    sasl_mechanism='AWS_MSK_IAM',
    sasl_oauth_token_provider=MSKTokenProvider(),
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)
```

Run:
```bash
python scripts/demo_scenario_aws.py
```

## Troubleshooting

### MSK Connection Issues

**Issue**: Can't connect to MSK from Lambda

**Solution**:
- Verify Lambda is in same VPC as MSK
- Check security group allows traffic on port 9092
- Verify IAM role has `kafka-cluster:*` permissions

### EMR Job Fails

**Issue**: Spark job fails to start

**Solution**:
```bash
# Check logs
aws logs tail /aws/emr-serverless/margin-risk-monitor --follow

# Common issues:
# - S3 path incorrect
# - IAM role missing permissions
# - Kafka packages not loaded
```

### Lambda Timeout

**Issue**: Lambda times out processing events

**Solution**:
- Increase timeout (currently 60s)
- Reduce batch size
- Check DynamoDB/S3 latency

### No Events in Topics

**Issue**: Topics exist but no events

**Solution**:
- Verify Spark job is running
- Check CloudWatch logs for errors
- Verify IAM permissions for Kafka write

## Cost Monitoring

```bash
# View current costs
aws ce get-cost-and-usage \
  --time-period Start=$(date -u +%Y-%m-01),End=$(date -u +%Y-%m-%d) \
  --granularity DAILY \
  --metrics BlendedCost \
  --group-by Type=SERVICE \
  --filter file://filter.json

# filter.json
{
  "Tags": {
    "Key": "Project",
    "Values": ["margin-risk-monitor"]
  }
}
```

## Outputs

After successful deployment, Terraform outputs:

```bash
# View all outputs
terraform output

# Specific outputs
terraform output msk_bootstrap_brokers
terraform output s3_bucket
terraform output dynamodb_table
terraform output emr_application_id
terraform output lambda_function_name
```

## Next Steps

- [06 - Run Demo](06-run-demo.md) - Run the demo scenario
- [07 - Observe](07-observe.md) - Monitor the system
- [09 - Cost and Cleanup](09-cost-and-cleanup.md) - Manage costs
