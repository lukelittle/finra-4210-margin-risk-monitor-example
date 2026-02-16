"""
Real-Time Margin Risk Calculator - Apache Flink

Flink streaming job that:
1. Consumes fills, prices, and betas from Kafka
2. Maintains position state per account (stateful processing)
3. Computes maintenance margin requirements
4. Performs beta-weighted stress testing
5. Evaluates TIMS-style scenarios
6. Emits margin calculations and stress results

Flink advantages over Spark Streaming:
- True streaming (not micro-batches)
- Lower latency (milliseconds vs seconds)
- More efficient state management
- Better exactly-once guarantees
- Purpose-built for streaming
"""

import os
import json
from pyflink.datastream import StreamExecutionEnvironment, TimeCharacteristic
from pyflink.table import StreamTableEnvironment, EnvironmentSettings
from pyflink.table.expressions import col, lit, call
from pyflink.table.window import Tumble
from pyflink.table.udf import udf
from pyflink.table import DataTypes

# Configuration
KAFKA_BROKERS = os.getenv('KAFKA_BROKERS', 'localhost:9092')
CHECKPOINT_INTERVAL = int(os.getenv('CHECKPOINT_INTERVAL', '60000'))  # 60 seconds

# Risk parameters
MAINTENANCE_RATE = 0.25
SPY_SCENARIOS = [-0.08, -0.06, -0.04, -0.02, 0.0, 0.02, 0.04, 0.06]


def create_execution_environment():
    """Create Flink execution environment with checkpointing."""
    env = StreamExecutionEnvironment.get_execution_environment()
    
    # Enable checkpointing for fault tolerance
    env.enable_checkpointing(CHECKPOINT_INTERVAL)
    
    # Set parallelism
    env.set_parallelism(2)
    
    # Create table environment
    settings = EnvironmentSettings.new_instance() \
        .in_streaming_mode() \
        .build()
    
    table_env = StreamTableEnvironment.create(env, settings)
    
    return env, table_env


def create_kafka_source_table(table_env, table_name, topic, schema_ddl):
    """Create Kafka source table."""
    ddl = f"""
        CREATE TABLE {table_name} (
            {schema_ddl},
            event_time TIMESTAMP(3) METADATA FROM 'timestamp',
            WATERMARK FOR event_time AS event_time - INTERVAL '5' SECOND
        ) WITH (
            'connector' = 'kafka',
            'topic' = '{topic}',
            'properties.bootstrap.servers' = '{KAFKA_BROKERS}',
            'properties.group.id' = 'margin-risk-calculator',
            'scan.startup.mode' = 'latest-offset',
            'format' = 'json',
            'json.fail-on-missing-field' = 'false',
            'json.ignore-parse-errors' = 'true'
        )
    """
    table_env.execute_sql(ddl)


def create_kafka_sink_table(table_env, table_name, topic, schema_ddl):
    """Create Kafka sink table."""
    ddl = f"""
        CREATE TABLE {table_name} (
            {schema_ddl}
        ) WITH (
            'connector' = 'kafka',
            'topic' = '{topic}',
            'properties.bootstrap.servers' = '{KAFKA_BROKERS}',
            'format' = 'json',
            'json.fail-on-missing-field' = 'false'
        )
    """
    table_env.execute_sql(ddl)


def setup_source_tables(table_env):
    """Setup Kafka source tables for fills, prices, and betas."""
    
    # Fills table
    create_kafka_source_table(
        table_env,
        'fills',
        'fills.v1',
        """
        account_id STRING,
        symbol STRING,
        qty INT,
        price DOUBLE,
        fill_timestamp BIGINT,
        fill_id STRING
        """
    )
    
    # Prices table
    create_kafka_source_table(
        table_env,
        'prices',
        'prices.v1',
        """
        symbol STRING,
        price DOUBLE,
        price_timestamp BIGINT
        """
    )
    
    # Betas table
    create_kafka_source_table(
        table_env,
        'betas',
        'betas.v1',
        """
        symbol STRING,
        beta DOUBLE,
        beta_timestamp BIGINT
        """
    )


def setup_sink_tables(table_env):
    """Setup Kafka sink tables for results."""
    
    # Margin calculations sink
    create_kafka_sink_table(
        table_env,
        'margin_calc_sink',
        'margin.calc.v1',
        """
        account_id STRING,
        total_mv DOUBLE,
        beta_weighted_exposure DOUBLE,
        cash DOUBLE,
        equity DOUBLE,
        maintenance_req DOUBLE,
        excess DOUBLE,
        excess_pct DOUBLE,
        calc_timestamp BIGINT
        """
    )
    
    # Stress test results sink
    create_kafka_sink_table(
        table_env,
        'stress_sink',
        'stress.beta_spy.v1',
        """
        account_id STRING,
        scenario DOUBLE,
        scenario_type STRING,
        delta_pnl DOUBLE,
        equity_stressed DOUBLE,
        excess_stressed DOUBLE,
        underwater BOOLEAN,
        calc_timestamp BIGINT
        """
    )


def compute_positions(table_env):
    """
    Compute cumulative positions per account and symbol.
    
    Uses Flink's stateful processing to maintain running totals.
    """
    table_env.execute_sql("""
        CREATE VIEW positions AS
        SELECT 
            account_id,
            symbol,
            SUM(qty) as qty,
            MAX(event_time) as last_updated
        FROM fills
        GROUP BY account_id, symbol
        HAVING SUM(qty) <> 0
    """)


def enrich_positions(table_env):
    """
    Join positions with latest prices and betas.
    
    Uses temporal joins to get the latest price and beta for each symbol.
    """
    table_env.execute_sql("""
        CREATE VIEW positions_enriched AS
        SELECT 
            p.account_id,
            p.symbol,
            p.qty,
            pr.price,
            b.beta,
            p.qty * pr.price as market_value,
            p.qty * pr.price * b.beta as beta_weighted_value,
            p.last_updated
        FROM positions p
        LEFT JOIN (
            SELECT symbol, price
            FROM (
                SELECT symbol, price,
                       ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY event_time DESC) as rn
                FROM prices
            )
            WHERE rn = 1
        ) pr ON p.symbol = pr.symbol
        LEFT JOIN (
            SELECT symbol, beta
            FROM (
                SELECT symbol, beta,
                       ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY event_time DESC) as rn
                FROM betas
            )
            WHERE rn = 1
        ) b ON p.symbol = b.symbol
    """)


def compute_margin(table_env):
    """
    Compute margin requirements per account.
    
    Implements:
    - Base maintenance margin (25% of market value)
    - Equity calculation (simplified: cash = 10% of MV)
    - Excess margin
    """
    table_env.execute_sql(f"""
        CREATE VIEW margin_calculations AS
        SELECT 
            account_id,
            SUM(market_value) as total_mv,
            SUM(beta_weighted_value) as beta_weighted_exposure,
            SUM(market_value) * 0.1 as cash,
            SUM(market_value) * 1.1 as equity,
            SUM(market_value) * {MAINTENANCE_RATE} as maintenance_req,
            SUM(market_value) * 1.1 - SUM(market_value) * {MAINTENANCE_RATE} as excess,
            (SUM(market_value) * 1.1 - SUM(market_value) * {MAINTENANCE_RATE}) / SUM(market_value) as excess_pct,
            UNIX_TIMESTAMP() * 1000 as calc_timestamp
        FROM positions_enriched
        GROUP BY account_id
    """)


def compute_stress_tests(table_env):
    """
    Compute beta-weighted stress test scenarios.
    
    For each account, applies SPY move scenarios to beta-weighted exposure.
    """
    # Create a scenarios table
    scenarios_data = [(scenario,) for scenario in SPY_SCENARIOS]
    scenarios_table = table_env.from_elements(
        scenarios_data,
        schema=['scenario']
    )
    table_env.create_temporary_view('scenarios', scenarios_table)
    
    # Cross join margin calculations with scenarios
    table_env.execute_sql("""
        CREATE VIEW stress_results AS
        SELECT 
            m.account_id,
            s.scenario,
            'SPY_BETA_WEIGHTED' as scenario_type,
            m.beta_weighted_exposure * s.scenario as delta_pnl,
            m.equity + (m.beta_weighted_exposure * s.scenario) as equity_stressed,
            m.equity + (m.beta_weighted_exposure * s.scenario) - m.maintenance_req as excess_stressed,
            CASE 
                WHEN m.equity + (m.beta_weighted_exposure * s.scenario) - m.maintenance_req < 0 
                THEN TRUE 
                ELSE FALSE 
            END as underwater,
            UNIX_TIMESTAMP() * 1000 as calc_timestamp
        FROM margin_calculations m
        CROSS JOIN scenarios s
    """)


def write_results(table_env):
    """Write results to Kafka sinks."""
    
    # Write margin calculations
    table_env.execute_sql("""
        INSERT INTO margin_calc_sink
        SELECT 
            account_id,
            total_mv,
            beta_weighted_exposure,
            cash,
            equity,
            maintenance_req,
            excess,
            excess_pct,
            calc_timestamp
        FROM margin_calculations
    """)
    
    # Write stress test results
    table_env.execute_sql("""
        INSERT INTO stress_sink
        SELECT 
            account_id,
            scenario,
            scenario_type,
            delta_pnl,
            equity_stressed,
            excess_stressed,
            underwater,
            calc_timestamp
        FROM stress_results
    """)


def main():
    """Main execution."""
    print("=" * 80)
    print("  Real-Time Margin Risk Calculator - Apache Flink")
    print("=" * 80)
    print(f"Kafka Brokers: {KAFKA_BROKERS}")
    print(f"Checkpoint Interval: {CHECKPOINT_INTERVAL}ms")
    print("=" * 80)
    
    # Create execution environment
    env, table_env = create_execution_environment()
    
    # Setup tables
    print("\n[1/7] Setting up source tables...")
    setup_source_tables(table_env)
    
    print("[2/7] Setting up sink tables...")
    setup_sink_tables(table_env)
    
    print("[3/7] Computing positions...")
    compute_positions(table_env)
    
    print("[4/7] Enriching with prices and betas...")
    enrich_positions(table_env)
    
    print("[5/7] Computing margin requirements...")
    compute_margin(table_env)
    
    print("[6/7] Computing stress tests...")
    compute_stress_tests(table_env)
    
    print("[7/7] Writing results to Kafka...")
    write_results(table_env)
    
    print("\n" + "=" * 80)
    print("  Flink job submitted. Processing streams...")
    print("=" * 80)
    
    # Execute (this blocks until job is cancelled)
    env.execute("MarginRiskCalculator")


if __name__ == "__main__":
    main()
