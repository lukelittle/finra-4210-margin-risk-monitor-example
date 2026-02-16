# What is TIMS?

## Introduction

TIMS (Theoretical Intermarket Margining System) is a portfolio margin methodology developed by the Options Clearing Corporation (OCC). It's used to calculate risk-based margin requirements for portfolios containing options, futures, and their underlying securities.

**Key Insight**: Instead of fixed percentage requirements, TIMS evaluates how much a portfolio could lose under various market scenarios.

## The Problem with Fixed Percentage Margin

Traditional Reg T margin treats each position independently:

```
Stock A: $10,000 × 25% = $2,500 requirement
Stock B: $10,000 × 25% = $2,500 requirement
Total: $5,000 requirement
```

But what if Stock A and Stock B are perfectly hedged (e.g., long stock + protective put)? The actual risk is much lower than $5,000, but Reg T doesn't recognize this.

## TIMS Approach: Scenario-Based Risk

TIMS asks: "What's the worst-case loss if markets move?"

### Step 1: Define Scenarios

Create a grid of underlying price movements:

```
Scenarios: -15%, -10%, -5%, 0%, +5%, +10%, +15%
```

For options, also vary implied volatility:

```
Volatility: -4%, -2%, 0%, +2%, +4%
```

This creates a matrix of scenarios (e.g., 7 price × 5 vol = 35 scenarios).

### Step 2: Revalue Portfolio

For each scenario, revalue all positions:

```python
for scenario in scenarios:
    underlying_price_new = underlying_price * (1 + scenario.price_move)
    
    for position in portfolio:
        if position.type == 'stock':
            value_new = position.qty * underlying_price_new
        elif position.type == 'option':
            value_new = black_scholes(
                underlying_price_new,
                position.strike,
                position.expiry,
                scenario.vol_move
            ) * position.qty
        
        pnl = value_new - position.current_value
        scenario_pnl += pnl
```

### Step 3: Find Worst-Case Loss

```python
worst_case_loss = min(scenario_pnls)
```

### Step 4: Set Margin Requirement

```python
margin_requirement = abs(worst_case_loss) * multiplier
```

The multiplier (typically 1.0-1.5) provides a buffer.

## Example: Hedged Position

### Position
- Long 100 shares of XYZ at $100
- Long 1 put option (100 shares) at strike $95

### Reg T Margin
```
Stock: $10,000 × 25% = $2,500
Put: $500 (premium paid, no margin)
Total: $2,500
```

### TIMS Margin

Scenarios:

| Scenario | Stock Price | Stock Value | Put Value | Total Value | PnL |
|----------|-------------|-------------|-----------|-------------|-----|
| -15% | $85 | $8,500 | $1,000 | $9,500 | -$500 |
| -10% | $90 | $9,000 | $500 | $9,500 | -$500 |
| -5% | $95 | $9,500 | $50 | $9,550 | -$450 |
| 0% | $100 | $10,000 | $5 | $10,005 | +$5 |
| +5% | $105 | $10,500 | $0 | $10,500 | +$500 |
| +10% | $110 | $11,000 | $0 | $11,000 | +$1,000 |
| +15% | $115 | $11,500 | $0 | $11,500 | +$1,500 |

Worst-case loss: -$500

TIMS margin: $500 × 1.0 = $500

**Result**: TIMS recognizes the hedge and requires only $500 vs. $2,500 under Reg T.

## TIMS for Intermarket Spreads

TIMS also recognizes risk offsets between related products:

- Stock vs. stock index futures
- Options on different expirations
- Options on correlated underlyings

This is the "Intermarket" part of TIMS.

## Our Simplified TIMS Implementation

For educational purposes, we implement a simplified version:

### Assumptions
- Equities only (no options)
- Single underlying price grid
- No volatility dimension
- No time decay

### Algorithm

```python
def compute_tims_margin(portfolio, scenarios):
    """
    Simplified TIMS for equity portfolios.
    
    Args:
        portfolio: List of positions {symbol, qty, price}
        scenarios: List of price move percentages
    
    Returns:
        worst_case_loss, portfolio_margin_requirement
    """
    scenario_pnls = []
    
    for scenario in scenarios:
        scenario_pnl = 0
        
        for position in portfolio:
            # Apply scenario to this symbol's price
            price_new = position.price * (1 + scenario)
            value_new = position.qty * price_new
            value_current = position.qty * position.price
            pnl = value_new - value_current
            scenario_pnl += pnl
        
        scenario_pnls.append(scenario_pnl)
    
    worst_case_loss = min(scenario_pnls)
    portfolio_margin_req = abs(worst_case_loss)
    
    return worst_case_loss, portfolio_margin_req
```

### Scenario Grid

We use 10 evenly spaced scenarios from -15% to +15%:

```python
scenarios = [-0.15, -0.10, -0.05, -0.03, -0.01, 0.01, 0.03, 0.05, 0.10, 0.15]
```

### Example Output

For a portfolio:
- 100 AAPL at $150
- -50 MSFT at $300 (short)

Scenarios:

| Scenario | AAPL PnL | MSFT PnL | Total PnL |
|----------|----------|----------|-----------|
| -15% | -$2,250 | +$2,250 | $0 |
| -10% | -$1,500 | +$1,500 | $0 |
| -5% | -$750 | +$750 | $0 |
| 0% | $0 | $0 | $0 |
| +5% | +$750 | -$750 | $0 |
| +10% | +$1,500 | -$1,500 | $0 |
| +15% | +$2,250 | -$2,250 | $0 |

Worst-case loss: $0 (perfectly hedged)

TIMS margin: $0 (in practice, a minimum would apply)

## TIMS vs. Reg T: Summary

| Aspect | Reg T | TIMS |
|--------|-------|------|
| Methodology | Fixed % of position value | Scenario-based risk |
| Hedges | Not recognized | Recognized |
| Complexity | Simple | Complex |
| Capital Efficiency | Lower | Higher (for hedged portfolios) |
| Eligibility | All accounts | Qualified accounts only |
| Minimum Equity | $2,000 | $100,000+ |

## Why TIMS Matters for This System

Our system computes both:

1. **Maintenance Margin** (Reg T style) - Regulatory baseline
2. **TIMS-Style Portfolio Margin** - Risk-based assessment

This shows students:
- How different methodologies produce different requirements
- Why sophisticated firms use scenario-based risk
- How to implement scenario evaluation in streaming systems

## Implementation in Spark

```python
# In PySpark Structured Streaming
def compute_portfolio_scenarios(portfolio_df, scenarios):
    """
    Compute PnL across scenarios for each account.
    """
    scenario_results = []
    
    for scenario in scenarios:
        scenario_df = portfolio_df.withColumn(
            'scenario_pnl',
            col('qty') * col('price') * lit(scenario)
        )
        
        account_scenario_pnl = scenario_df.groupBy('account_id').agg(
            sum('scenario_pnl').alias('total_pnl')
        ).withColumn('scenario', lit(scenario))
        
        scenario_results.append(account_scenario_pnl)
    
    # Union all scenarios
    all_scenarios = scenario_results[0]
    for df in scenario_results[1:]:
        all_scenarios = all_scenarios.union(df)
    
    # Find worst case per account
    worst_case = all_scenarios.groupBy('account_id').agg(
        min('total_pnl').alias('worst_case_loss')
    )
    
    # Portfolio margin requirement
    portfolio_margin = worst_case.withColumn(
        'portfolio_margin_req',
        abs(col('worst_case_loss'))
    )
    
    return portfolio_margin
```

## Key Takeaways

1. **TIMS is scenario-based**: Evaluates risk under market moves
2. **Recognizes hedges**: Lower margin for offsetting positions
3. **More capital efficient**: For sophisticated, hedged portfolios
4. **More complex**: Requires pricing models and scenario grids
5. **Industry standard**: Used by OCC and major broker-dealers
6. **Our implementation is simplified**: Educational model, not production

## Further Reading

- [OCC TIMS Overview](https://www.theocc.com/risk-management/margin-methodology)
- [CBOE Portfolio Margin](https://www.cboe.com/tradable_products/margin/)
- [SEC Portfolio Margin Rules](https://www.sec.gov/rules/sro/nyse/2006/34-54918.pdf)

## Next Steps

- [03 - Beta Weighting](03-beta-weighting.md) - Learn stress testing methodology
- [04 - Architecture](04-architecture.md) - See how we implement this in streaming
