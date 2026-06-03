//+------------------------------------------------------------------+
//| SpreadMonitor.mqh
//| Bid-ask spread and liquidity monitoring for GHOST GRID EA
//| WHY: Detect poor liquidity / wide spreads as execution risk signal
//+------------------------------------------------------------------+

#ifndef __SPREAD_MONITOR_MQH__
#define __SPREAD_MONITOR_MQH__

// Spread history per symbol
struct SpreadStats {
    double current_spread;
    double avg_spread;
    double max_spread;
    double min_spread;
    int tick_count;
    int wide_spread_events;  // Count of spreads > 2x baseline
};

// Global spread registry
static SpreadStats g_spread_stats[];
static double g_baseline_spreads[10];  // Per symbol baseline


//+------------------------------------------------------------------+
//| InitSpreadMonitor
//| Initialize spread monitoring for all symbols
//+------------------------------------------------------------------+
void InitSpreadMonitor() {
    ArrayResize(g_spread_stats, 10);
    
    for (int i = 0; i < 10; i++) {
        g_spread_stats[i].current_spread = 0.0;
        g_spread_stats[i].avg_spread = 0.0;
        g_spread_stats[i].max_spread = 0.0;
        g_spread_stats[i].min_spread = 999999.0;
        g_spread_stats[i].tick_count = 0;
        g_spread_stats[i].wide_spread_events = 0;
        g_baseline_spreads[i] = 0.0002;  // Default baseline 2 pips
    }
}


//+------------------------------------------------------------------+
//| UpdateSpread
//| Update spread measurement for a symbol
//| Returns: spread in pips
//+------------------------------------------------------------------+
double UpdateSpread(string symbol) {
    double bid = SymbolInfoDouble(symbol, SYMBOL_BID);
    double ask = SymbolInfoDouble(symbol, SYMBOL_ASK);
    double spread = ask - bid;
    
    // Convert to pips (5 decimal places = divide by 0.00001)
    int digits = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
    if (digits == 5) {
        spread = spread / 0.00001;
    } else if (digits == 3) {
        spread = spread / 0.001;
    }
    
    // Find symbol index
    int idx = 0;
    
    // Update statistics
    if (g_spread_stats[idx].tick_count == 0) {
        g_spread_stats[idx].current_spread = spread;
        g_spread_stats[idx].avg_spread = spread;
        g_spread_stats[idx].max_spread = spread;
        g_spread_stats[idx].min_spread = spread;
    } else {
        g_spread_stats[idx].current_spread = spread;
        g_spread_stats[idx].avg_spread = (g_spread_stats[idx].avg_spread * g_spread_stats[idx].tick_count + spread) / 
                                         (g_spread_stats[idx].tick_count + 1);
        g_spread_stats[idx].max_spread = MathMax(g_spread_stats[idx].max_spread, spread);
        g_spread_stats[idx].min_spread = MathMin(g_spread_stats[idx].min_spread, spread);
    }
    
    // Detect wide spread events (> 2x baseline)
    if (spread > g_baseline_spreads[idx] * 2.0) {
        g_spread_stats[idx].wide_spread_events++;
    }
    
    g_spread_stats[idx].tick_count++;
    
    return spread;
}


//+------------------------------------------------------------------+
//| GetCurrentSpread
//| Get current spread in pips
//+------------------------------------------------------------------+
double GetCurrentSpread() {
    return g_spread_stats[0].current_spread;
}


//+------------------------------------------------------------------+
//| GetAverageSpread
//| Get average spread in pips
//+------------------------------------------------------------------+
double GetAverageSpread() {
    return g_spread_stats[0].avg_spread;
}


//+------------------------------------------------------------------+
//| GetMaxSpread
//| Get maximum spread observed in pips
//+------------------------------------------------------------------+
double GetMaxSpread() {
    return g_spread_stats[0].max_spread;
}


//+------------------------------------------------------------------+
//| IsSpreadWide
//| Check if current spread is abnormally wide (> 2x baseline)
//| Returns: true if spread is suspicious
//+------------------------------------------------------------------+
bool IsSpreadWide() {
    return g_spread_stats[0].current_spread > g_baseline_spreads[0] * 2.0;
}


//+------------------------------------------------------------------+
//| GetWideSpreadEventCount
//| Get count of wide spread events detected
//+------------------------------------------------------------------+
int GetWideSpreadEventCount() {
    return g_spread_stats[0].wide_spread_events;
}


//+------------------------------------------------------------------+
//| SetBaselineSpread
//| Set baseline spread for liquidity analysis
//+------------------------------------------------------------------+
void SetBaselineSpread(double baseline_pips) {
    g_baseline_spreads[0] = baseline_pips;
}


//+------------------------------------------------------------------+
//| ResetSpreadStats
//| Reset all spread statistics
//+------------------------------------------------------------------+
void ResetSpreadStats() {
    for (int i = 0; i < 10; i++) {
        g_spread_stats[i].current_spread = 0.0;
        g_spread_stats[i].avg_spread = 0.0;
        g_spread_stats[i].max_spread = 0.0;
        g_spread_stats[i].min_spread = 999999.0;
        g_spread_stats[i].tick_count = 0;
        g_spread_stats[i].wide_spread_events = 0;
    }
}

#endif
