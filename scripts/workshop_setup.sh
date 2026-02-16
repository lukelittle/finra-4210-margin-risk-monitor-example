#!/bin/bash
set -e

echo "================================================================================"
echo "  Workshop Setup - Real-Time Margin Risk Monitor"
echo "================================================================================"
echo ""
echo "This script prepares the AWS environment for the workshop by:"
echo "  1. Starting the EMR Serverless application"
echo "  2. Warming up pre-initialized workers"
echo "  3. Verifying all services are ready"
echo ""
echo "Run this 10-15 minutes before the workshop starts."
echo ""
echo "================================================================================"
echo ""

# Get Terraform outputs
cd terraform
EMR_APP_ID=$(terraform output -raw emr_application_id)
EMR_ROLE_ARN=$(terraform output -raw emr_role_arn 2>/dev/null || echo "")
S3_BUCKET=$(terraform output -raw s3_bucket)
KAFKA_BROKERS=$(terraform output -raw msk_bootstrap_brokers)
cd ..

if [ -z "$EMR_APP_ID" ]; then
    echo "❌ Error: Could not get EMR application ID from Terraform"
    echo "   Make sure you've run 'terraform apply' first"
    exit 1
fi

echo "📋 Configuration:"
echo "   EMR Application ID: $EMR_APP_ID"
echo "   S3 Bucket: $S3_BUCKET"
echo ""

# Check if application exists
echo "🔍 Checking EMR Serverless application status..."
APP_STATUS=$(aws emr-serverless get-application --application-id $EMR_APP_ID --query 'application.state' --output text 2>/dev/null || echo "NOT_FOUND")

if [ "$APP_STATUS" = "NOT_FOUND" ]; then
    echo "❌ Error: EMR Serverless application not found"
    echo "   Run 'terraform apply' to create infrastructure"
    exit 1
fi

echo "   Application status: $APP_STATUS"

if [ "$APP_STATUS" != "CREATED" ] && [ "$APP_STATUS" != "STARTED" ]; then
    echo "⚠️  Warning: Application is in $APP_STATUS state"
    echo "   Waiting for application to be ready..."
    
    # Wait for application to be ready
    while [ "$APP_STATUS" != "CREATED" ] && [ "$APP_STATUS" != "STARTED" ]; do
        sleep 10
        APP_STATUS=$(aws emr-serverless get-application --application-id $EMR_APP_ID --query 'application.state' --output text)
        echo "   Current status: $APP_STATUS"
    done
fi

echo "✅ Application is ready"
echo ""

# Start a warmup job
echo "🔥 Starting warmup job to initialize workers..."
echo "   This will:"
echo "   - Provision driver and executor containers"
echo "   - Load Spark and dependencies"
echo "   - Connect to Kafka"
echo "   - Keep workers warm for fast subsequent jobs"
echo ""

# Get IAM role ARN if not already set
if [ -z "$EMR_ROLE_ARN" ]; then
    EMR_ROLE_ARN=$(aws iam get-role --role-name margin-risk-monitor-emr-serverless-role --query 'Role.Arn' --output text 2>/dev/null || echo "")
fi

if [ -z "$EMR_ROLE_ARN" ]; then
    echo "❌ Error: Could not find EMR execution role"
    echo "   Make sure Terraform has created the IAM role"
    exit 1
fi

# Submit warmup job
JOB_RUN_ID=$(aws emr-serverless start-job-run \
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
    --name "workshop-warmup-$(date +%Y%m%d-%H%M%S)" \
    --query 'jobRunId' \
    --output text)

echo "   Job Run ID: $JOB_RUN_ID"
echo ""

# Wait for job to start
echo "⏳ Waiting for job to start (this takes 2-4 minutes on cold start)..."
echo "   You can monitor progress at:"
echo "   https://console.aws.amazon.com/emr/home#/serverless/applications/$EMR_APP_ID/job-runs/$JOB_RUN_ID"
echo ""

ELAPSED=0
while true; do
    JOB_STATE=$(aws emr-serverless get-job-run \
        --application-id $EMR_APP_ID \
        --job-run-id $JOB_RUN_ID \
        --query 'jobRun.state' \
        --output text)
    
    echo "   [$ELAPSED sec] Job state: $JOB_STATE"
    
    if [ "$JOB_STATE" = "RUNNING" ]; then
        echo ""
        echo "✅ Job is running! Workers are now warm."
        echo ""
        break
    elif [ "$JOB_STATE" = "FAILED" ] || [ "$JOB_STATE" = "CANCELLED" ]; then
        echo ""
        echo "❌ Job failed to start. Check CloudWatch logs:"
        echo "   aws logs tail /aws/emr-serverless/margin-risk-monitor --follow"
        exit 1
    fi
    
    sleep 10
    ELAPSED=$((ELAPSED + 10))
    
    if [ $ELAPSED -gt 300 ]; then
        echo ""
        echo "⚠️  Job is taking longer than expected (>5 minutes)"
        echo "   Continuing anyway, but check the console for issues"
        break
    fi
done

echo "================================================================================"
echo "  Workshop Environment Ready!"
echo "================================================================================"
echo ""
echo "✅ EMR Serverless application is running with warm workers"
echo "✅ Subsequent jobs will start in 30-60 seconds (not 2-4 minutes)"
echo "✅ Students can now submit jobs immediately"
echo ""
echo "📊 Current Status:"
echo "   - Application ID: $EMR_APP_ID"
echo "   - Job Run ID: $JOB_RUN_ID"
echo "   - Pre-initialized workers: 1 driver + 2 executors"
echo "   - Auto-stop: 15 minutes after last job completes"
echo ""
echo "💰 Cost Impact:"
echo "   - Pre-initialized capacity: ~\$0.39/hour (3 workers × 2 vCPU × 4 GB)"
echo "   - 8-hour workshop: ~\$3.12 for warm workers"
echo "   - Trade-off: Fast startup vs. idle cost (realistic production pattern)"
echo ""
echo "🎓 Teaching Points:"
echo "   1. Production systems keep workers warm for low latency"
echo "   2. Cold start: 2-4 minutes (first job of the day)"
echo "   3. Warm start: 30-60 seconds (subsequent jobs)"
echo "   4. Cost vs. latency trade-off is a key architectural decision"
echo ""
echo "📝 Next Steps:"
echo "   1. Students can now run: python scripts/demo_scenario.py"
echo "   2. Monitor with: python scripts/observe_streams.py"
echo "   3. View Spark UI: https://console.aws.amazon.com/emr/home#/serverless"
echo ""
echo "🛑 After Workshop:"
echo "   - Application will auto-stop 15 minutes after last job"
echo "   - Or manually stop: aws emr-serverless stop-application --application-id $EMR_APP_ID"
echo "   - Cleanup everything: cd terraform && terraform destroy"
echo ""
echo "================================================================================"
