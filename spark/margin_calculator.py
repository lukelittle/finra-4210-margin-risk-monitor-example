"""
Real-Time Margin Risk Calculator - PySpark Structured Streaming

This job runs on EMR Serverless and processes margin risk in real-time.

Architecture:
- Local: Runs in Docker with Bitnami Spark images (for development/testing)
- AWS: Runs on EMR Serverless (production, truly serverless)

The Docker images (Kafka, Zookeeper, Spark) are PRE-BUILT from:
- Confluent (Kafka + Zookeeper)
- Bitnami (Spark)
We're NOT creating custom images - just using official ones for local dev.
"""

import os
from pyspark.sql import SparkSession
from pyspark.sql.functions import *
from pyspark.sql.types import *

# Configuration
KAFKA_BROKERS = os.getenv('KAFKA_BROKERS', 'localhost:9092')
CHECKPOINT_LOCATION = os.getenv('CHECKPOINT_LOCATION', '/tmp/checkpoints')
MAINTENANCE_RATE = 0.25
SPY_SCENARIOS = [-0.08, -0.06, -0.04, -0.02, 0.0, 0.02, 0.04, 0.06]

# Schemas
fills_schema = StructType([
    StructField("account_id", StringType()),
    StructField("symbol", StringType()),
    StructField("qty", IntegerType()),
    StructField("price", DoubleType()),
    StructField("timestamp", LongType()),
    StructField("fill_id", StringType())
])

prices_schema = StructType([
    StructField("symbol", StringType()),
    StructField("price", DoubleType()),
    StructField("timestamp", LongType())
])

betas_schema = StructType([
    StructField("symbol", StringType()),
    StructField("beta", DoubleType()),
    StructField("timestamp", LongType())
])

def main():
    spark = SparkSession.builder.appName("MarginRiskCalculator").getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    
    print("=" * 80)
    print("  Margin Risk Calculator - PySpark Streaming on EMR Serverless")
    print("=" * 80)
    print(f"Kafka: {KAFKA_BROKERS}")
    print(f"Checkpoint: {CHECKPOINT_LOCATION}")
    print("=" * 80)
    
    # Read streams
    fills = spark.readStream.format("kafka") \
        .option("kafka.bootstrap.servers", KAFKA_BROKERS) \
        .option("subscribe", "fills.v1") \
        .option("startingOffsets", "latest") \
        .load() \
        .select(from_json(col("value").cast("string"), fills_schema).alias("data")) \
        .select("data.*")
    
    prices = spark.readStream.format("kafka") \
        .option("kafka.bootstrap.servers", KAFKA_BROKERS) \
        .option("subscribe", "prices.v1") \
        .load() \
        .select(from_json(col("value").cast("string"), prices_schema).alias("data")) \
        .select("data.*")
    
    betas = spark.readStream.format("kafka") \
        .option("kafka.bootstrap.servers", KAFKA_BROKERS) \
        .option("subscribe", "betas.v1") \
        .load() \
        .select(from_json(col("value").cast("string"), betas_schema).alias("data")) \
        .select("data.*")
    
    # Compute positions (stateful)
    positions = fills.groupBy("account_id", "symbol").agg(sum("qty").alias("qty"))
    
    # Join with prices and betas
    latest_prices = prices.groupBy("symbol").agg(last("price").alias("price"))
    latest_betas = betas.groupBy("symbol").agg(last("beta").alias("beta"))
    
    enriched = positions \
        .join(latest_prices, "symbol", "left") \
        .join(latest_betas, "symbol", "left") \
        .fillna({"price": 0.0, "beta": 1.0}) \
        .withColumn("market_value", col("qty") * col("price")) \
        .withColumn("beta_weighted_value", col("market_value") * col("beta"))
    
    # Aggregate per account
    margin = enriched.groupBy("account_id").agg(
        sum("market_value").alias("total_mv"),
        sum("beta_weighted_value").alias("beta_weighted_exposure")
    ).withColumn("cash", col("total_mv") * 0.1) \
     .withColumn("equity", col("cash") + col("total_mv")) \
     .withColumn("maintenance_req", col("total_mv") * MAINTENANCE_RATE) \
     .withColumn("excess", col("equity") - col("maintenance_req"))
    
    # Write margin calculations
    margin.selectExpr("to_json(struct(*)) AS value") \
        .writeStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", KAFKA_BROKERS) \
        .option("topic", "margin.calc.v1") \
        .option("checkpointLocation", f"{CHECKPOINT_LOCATION}/margin") \
        .outputMode("update") \
        .start()
    
    # Stress testing
    for scenario in SPY_SCENARIOS:
        stress = margin \
            .withColumn("scenario", lit(scenario)) \
            .withColumn("delta_pnl", col("beta_weighted_exposure") * lit(scenario)) \
            .withColumn("equity_stressed", col("equity") + col("delta_pnl")) \
            .withColumn("excess_stressed", col("equity_stressed") - col("maintenance_req")) \
            .withColumn("underwater", col("excess_stressed") < 0)
        
        stress.selectExpr("to_json(struct(*)) AS value") \
            .writeStream \
            .format("kafka") \
            .option("kafka.bootstrap.servers", KAFKA_BROKERS) \
            .option("topic", "stress.beta_spy.v1") \
            .option("checkpointLocation", f"{CHECKPOINT_LOCATION}/stress-{scenario}") \
            .outputMode("update") \
            .start()
    
    print("Streams started. Processing...")
    spark.streams.awaitAnyTermination()

if __name__ == "__main__":
    main()
