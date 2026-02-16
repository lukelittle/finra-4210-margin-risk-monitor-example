#!/bin/bash

# Quick Start Script for Real-Time Margin Risk Monitor
# This script sets up and runs the entire system locally

set -e

echo "================================================================================"
echo "  Real-Time Margin Risk Monitor - Quick Start"
echo "================================================================================"
echo ""

# Check prerequisites
echo "Checking prerequisites..."

if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose not found. Please install Docker Compose first."
    exit 1
fi

if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.11+ first."
    exit 1
fi

echo "✅ Prerequisites satisfied"
echo ""

# Step 1: Start Docker services
echo "Step 1: Starting Docker services..."
docker-compose up -d

echo "Waiting for services to initialize (30 seconds)..."
sleep 30

# Check if Kafka is ready
echo "Checking Kafka status..."
docker-compose logs kafka-init | grep "Topics created successfully" || {
    echo "⚠️  Kafka topics may not be ready. Waiting another 10 seconds..."
    sleep 10
}

echo "✅ Docker services started"
echo ""

# Step 2: Install Python dependencies
echo "Step 2: Installing Python dependencies..."
pip3 install -r requirements.txt -q

echo "✅ Python dependencies installed"
echo ""

# Step 3: Submit Spark job
echo "Step 3: Submitting Spark streaming job..."
docker-compose exec -d spark-master spark-submit \
  --master spark://spark-master:7077 \
  --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0 \
  /opt/spark-apps/margin_calculator.py

echo "Waiting for Spark job to initialize (10 seconds)..."
sleep 10

echo "✅ Spark job submitted"
echo ""

# Step 4: Generate sample data
echo "Step 4: Generating sample data..."
python3 scripts/generate_sample_data.py

echo "✅ Sample data generated"
echo ""

# Step 5: Show results
echo "================================================================================"
echo "  System is running!"
echo "================================================================================"
echo ""
echo "Access points:"
echo "  - Spark UI:        http://localhost:8080"
echo "  - Spark App UI:    http://localhost:4040"
echo "  - Kafka:           localhost:9092"
echo "  - DynamoDB Local:  http://localhost:8000"
echo ""
echo "Next steps:"
echo "  1. Observe events:  python3 scripts/observe_streams.py"
echo "  2. Run demo:        python3 scripts/demo_scenario.py"
echo "  3. View Spark UI:   open http://localhost:8080"
echo ""
echo "To stop:"
echo "  docker-compose down"
echo ""
echo "To cleanup:"
echo "  docker-compose down -v"
echo ""
