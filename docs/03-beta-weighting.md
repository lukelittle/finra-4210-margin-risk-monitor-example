# Beta Weighting and Stress Testing

## Introduction

Beta weighting is a technique used by broker-dealers to convert a multi-stock portfolio into an equivalent exposure to a single benchmark (typically SPY, the S&P 500 ETF). This enables:

1. **Unified stress testing**: Apply market scenarios to the entire portfolio
2. **Risk aggregation**: Understand total market exposure
3. **House margin overlays**: Add requirements for high-beta, concentrated portfolios

## What is Beta?

Beta (β) measures how much a stock moves relative to the market:

```
β = Cov(Stock, Market) / Var(Market)
```

### Interpretation

- **β = 1.0**: Stock moves in line with market (e.g., SPY itself)
- **β = 1.5**: Stock moves 1.5× the market (high beta, more volatile)
- **β = 0.5**: Stock moves 0.5× the market (low beta, defensive)
- **β = 0.0**: Stock uncorrelated with market
- **β = -0.5**: Stock moves opposite to market (rare for equities)

### Example

If NVDA has β = 1.8 to SPY:
- SPY up 1% → NVDA expected up 1.8%
- SPY down 2% → NVDA expected down 3.6%

## Beta-Weighted Market Value

To convert a position to SPY-equivalent exposure:

```
Beta-Weighted Value = Position Value × Beta
```

### Example: Single Position

Position: 100 shares of TSLA at $200
- Market Value: $20,000
- Beta to SPY: 2.0
- Beta-Weighted Value: $20,000 × 2.0 = $40,000

**Interpretation**: This TSLA position has the market risk equivalent of $40,000 of SPY.

### Example: Portfolio

| Symbol | Qty | Price | Value | Beta | Beta-Weighted Value |
|--------|-----|-------|-------|------|---------------------|
| AAPL | 100 | $150 | $15,000 | 1.2 | $18,000 |
| NVDA | 50 | $400 | $20,000 | 1.8 | $36,000 |
| KO | 200 | $60 | $12,000 | 0.6 | $7,200 |
| **Total** | | | **$47,000** | | **$61,200** |

**Interpretation**: This $47,000 portfolio has the market risk of $61,200 of SPY.

The portfolio is **1.3× levered to market risk** ($61,200 / $47,000).

## Stress Testing with Beta Weighting

Once we have beta-weighted exposure, we can apply SPY scenarios:

### Scenario Grid

Typical scenarios:

```python
spy_scenarios = [-0.08, -0.06, -0.04, -0.02, 0.0, 0.02, 0.04, 0.06]
```

This represents SPY moves from -8% to +6%.

### Computing Stressed PnL

For each scenario:

```
ΔPnL = Beta-Weighted Exposure × SPY Move %
Equity_stressed = Equity + ΔPnL
Excess_stressed = Equity_stressed - Maintenance Requirement
```

### Example: Portfolio Under Stress

Starting state:
- Cash: $10,000
- Market Value: $47,000
- Beta-Weighted Exposure: $61,200
- Equity: $57,000
- Maintenance Requirement (25%): $11,750
- Excess: $45,250 ✓

SPY -8% scenario:
- ΔPnL: $61,200 × -0.08 = -$4,896
- Equity_stressed: $57,000 - $4,896 = $52,104
- Excess_stressed: $52,104 - $11,750 = $40,354 ✓

SPY -6% scenario:
- ΔPnL: $61,200 × -0.06 = -$3,672
- Equity_stressed: $57,000 - $3,672 = $53,328
- Excess_stressed: $53,328 - $11,750 = $41,578 ✓

All scenarios pass. Account is not at risk.

### Example: High-Beta, Leveraged Account

Starting state:
- Cash: $5,000
- Market Value: $95,000 (highly leveraged)
- Beta-Weighted Exposure: $140,000 (high-beta stocks)
- Equity: $100,000
- Maintenance Requirement (25%): $23,750
- Excess: $76,250 ✓

SPY -8% scenario:
- ΔPnL: $140,000 × -0.08 = -$11,200
- Equity_stressed: $100,000 - $11,200 = $88,800
- Maintenance Requirement: $23,750 (unchanged)
- Excess_stressed: $88,800 - $23,750 = $65,050 ✓

SPY -10% scenario (more severe):
- ΔPnL: $140,000 × -0.10 = -$14,000
- Equity_stressed: $100,000 - $14,000 = $86,000
- Excess_stressed: $86,000 - $23,750 = $62,250 ✓

SPY -15% scenario (extreme):
- ΔPnL: $140,000 × -0.15 = -$21,000
- Equity_stressed: $100,000 - $21,000 = $79,000
- Excess_stressed: $79,000 - $23,750 = $55,250 ✓

Even at -15%, account survives. But the firm may still impose restrictions due to high leverage and beta.

## House Margin Overlays

Firms often add requirements based on beta-weighted stress:

### Rule: Underwater in Severe Stress

```python
if excess_stressed < 0 in any scenario where |SPY move| >= 6%:
    apply_restriction()  # Close-only mode
```

### Rule: High Beta-Weighted Leverage

```python
beta_weighted_leverage = beta_weighted_exposure / equity

if beta_weighted_leverage > 2.0:
    additional_margin = 0.05 * market_value
```

**Rationale**: High-beta, leveraged accounts pose risk to the firm even if they meet regulatory minimums.

## Implementation in Our System

### Data Flow

```
fills.v1 + prices.v1 + betas.v1
    ↓
Spark Streaming: Join and aggregate
    ↓
Compute beta-weighted exposure per account
    ↓
Apply SPY scenarios
    ↓
Emit stress.beta_spy.v1
    ↓
Lambda: Evaluate stress results
    ↓
restrictions.v1 if underwater
```

### Spark Code

```python
# Join positions with betas
positions_with_beta = positions_df.join(
    betas_df,
    on='symbol',
    how='left'
).fillna({'beta': 1.0})  # Default beta = 1.0 if missing

# Compute beta-weighted value
positions_with_beta = positions_with_beta.withColumn(
    'beta_weighted_value',
    col('qty') * col('price') * col('beta')
)

# Aggregate per account
account_beta_exposure = positions_with_beta.groupBy('account_id').agg(
    sum('market_value').alias('total_mv'),
    sum('beta_weighted_value').alias('beta_weighted_exposure')
)

# Apply scenarios
spy_scenarios = [-0.08, -0.06, -0.04, -0.02, 0.0, 0.02, 0.04, 0.06]

for scenario in spy_scenarios:
    scenario_df = account_beta_exposure.withColumn(
        'scenario', lit(scenario)
    ).withColumn(
        'delta_pnl', col('beta_weighted_exposure') * lit(scenario)
    ).withColumn(
        'equity_stressed', col('equity') + col('delta_pnl')
    ).withColumn(
        'excess_stressed', col('equity_stressed') - col('maintenance_req')
    ).withColumn(
        'underwater', col('excess_stressed') < 0
    )
    
    # Emit to stress.beta_spy.v1
    scenario_df.writeStream \
        .format('kafka') \
        .option('topic', 'stress.beta_spy.v1') \
        .start()
```

### Lambda Enforcement

```python
def handle_stress_event(event):
    """
    Process stress test results.
    """
    account_id = event['account_id']
    scenario = event['scenario']
    underwater = event['underwater']
    
    # Check if underwater in severe scenario
    if underwater and abs(scenario) >= 0.06:
        emit_restriction(
            account_id=account_id,
            reason=f'Underwater in SPY {scenario:.1%} scenario',
            action='CLOSE_ONLY'
        )
        
        emit_audit(
            account_id=account_id,
            event_type='STRESS_RESTRICTION',
            scenario=scenario,
            excess_stressed=event['excess_stressed']
        )
```

## Beta Calculation (Reference)

In production, betas are computed from historical returns:

```python
import numpy as np

def compute_beta(stock_returns, market_returns):
    """
    Compute beta from return series.
    
    Args:
        stock_returns: Array of stock returns
        market_returns: Array of market returns
    
    Returns:
        beta coefficient
    """
    covariance = np.cov(stock_returns, market_returns)[0, 1]
    market_variance = np.var(market_returns)
    beta = covariance / market_variance
    return beta
```

Typical lookback: 1-3 years of daily returns.

For this system, we use pre-computed betas from a reference data source.

## Limitations and Considerations

### 1. Beta is Historical

Beta is computed from past data. It may not predict future behavior, especially during regime changes.

### 2. Beta is Not Constant

Beta changes over time as correlations shift. Systems should update betas regularly (e.g., monthly).

### 3. Non-Linear Risk

Beta assumes linear relationships. Options and other derivatives have non-linear payoffs not captured by beta.

### 4. Idiosyncratic Risk

Beta captures only systematic (market) risk. Stock-specific events (earnings, lawsuits) are not captured.

### 5. Correlation ≠ Causation

High beta doesn't mean the stock is "caused" by SPY. It's a statistical relationship.

## Key Takeaways

1. **Beta measures sensitivity to market moves**
2. **Beta-weighting converts portfolios to SPY-equivalent exposure**
3. **Stress testing applies scenarios to beta-weighted exposure**
4. **Firms use stress tests to impose house margin overlays**
5. **High-beta, leveraged accounts pose firm risk**
6. **Streaming systems enable real-time stress monitoring**

## Formulas Summary

```
Beta = Cov(Stock, Market) / Var(Market)

Beta-Weighted Value = Position Value × Beta

Beta-Weighted Exposure = Σ (Position Value_i × Beta_i)

Stressed PnL = Beta-Weighted Exposure × SPY Move %

Equity_stressed = Equity + Stressed PnL

Excess_stressed = Equity_stressed - Maintenance Requirement

Underwater = (Excess_stressed < 0)
```

## Further Reading

- [Investopedia: Beta](https://www.investopedia.com/terms/b/beta.asp)
- [CBOE: Portfolio Beta Weighting](https://www.cboe.com/education/tools/portfolio-beta-weighting/)
- Academic: Sharpe, W. (1964). "Capital Asset Prices: A Theory of Market Equilibrium"

## Next Steps

- [04 - Architecture](04-architecture.md) - See how components fit together
- [06 - Run Demo](06-run-demo.md) - Watch stress testing in action
