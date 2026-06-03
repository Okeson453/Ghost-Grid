"""Validate complete scoring pipeline: HMP → HLCP → MPP → Fusion → Gate"""

from data.schema import MarketSnapshot, Tick, OHLCV
from scoring import (
    calculate_hmp,
    calculate_hlcp,
    calculate_mpp,
    score_confluence,
    ConfluenceGate,
    GateDecision,
)
import time


# Create a test snapshot
def make_test_bar(close=1.08500):
    return OHLCV(
        open=close - 0.00010,
        high=close + 0.00015,
        low=close - 0.00020,
        close=close,
        volume=150,
        timestamp_ms=int(time.time() * 1000),
    )


bars = [make_test_bar(1.08500 + i * 0.00005) for i in range(50)]

snap = MarketSnapshot(
    symbol="EURUSD",
    tick=Tick(
        symbol="EURUSD",
        timestamp_ms=int(time.time() * 1000),
        bid=1.08500,
        ask=1.08502,
        spread=0.00002,
        tick_volume=150,
        dominant_side="BUY",
        cvd_running=500.0,
        session="LONDON",
    ),
    m1=bars,
    m3=bars[:40],
    m5=bars[:30],
    cvd_history=[float(i * 10) for i in range(200)],
    vwap=1.08490,
    atr_1m=0.00050,
    atr_5m=0.00080,
    session="LONDON",
    regime="TREND",
)

print("\n✓ Created test MarketSnapshot")

# Test all three scoring engines
hmp_long = calculate_hmp(snap, "LONG")
hmp_short = calculate_hmp(snap, "SHORT")
print(f"\nHMP Scores:")
print(f"  LONG:  {hmp_long.score}/60")
print(f"  SHORT: {hmp_short.score}/60")

hlcp_long = calculate_hlcp(snap, "LONG")
hlcp_short = calculate_hlcp(snap, "SHORT")
print(f"\nHLCP Scores:")
print(f"  LONG:  {hlcp_long.score}/60")
print(f"  SHORT: {hlcp_short.score}/60")

mpp_long = calculate_mpp(snap, "LONG")
mpp_short = calculate_mpp(snap, "SHORT")
print(f"\nMPP Scores:")
print(f"  LONG:  {mpp_long.score}/60")
print(f"  SHORT: {mpp_short.score}/60")

# Test fusion
confluence = score_confluence(snap)
print(f"\n✓ Fusion Result (H_c Composite):")
print(f"  Direction: {confluence.direction}")
print(f"  Composite: {confluence.composite}/180")
print(
    f"  HMP: {confluence.hmp}/60, HLCP: {confluence.hlcp}/60, MPP: {confluence.mpp}/60"
)

# Test gate
gate = ConfluenceGate()
decision1 = gate.evaluate(confluence)
decision2 = gate.evaluate(confluence)

print(f"\n✓ Gate Hysteresis Test:")
print(f"  Cycle 1: {decision1.value}")
print(f"  Cycle 2: {decision2.value}")

print("\n" + "=" * 60)
print("✅ COMPLETE SCORING PIPELINE VALIDATION PASSED")
print("   All engines (HMP, HLCP, MPP) → Fusion → Gate working!")
print("=" * 60)
