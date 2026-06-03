//+------------------------------------------------------------------+
//| OHLCVBuilder.mqh
//| Multi-timeframe OHLCV bar assembly for GHOST GRID EA
//| WHY: Build M1/M3/M5 bars from ticks for Python scoring layer
//+------------------------------------------------------------------+

#ifndef __OHLCV_BUILDER_MQH__
#define __OHLCV_BUILDER_MQH__

// OHLCV bar structure
struct OHLCVBar {
    double open;
    double high;
    double low;
    double close;
    long volume;
    datetime bar_time;
    int timeframe;  // 1=M1, 3=M3, 5=M5
};

// Per-timeframe builder state
struct BarBuilderState {
    OHLCVBar current_bar;
    OHLCVBar last_completed_bar;
    int bars_built;
    bool is_new_bar;
};

// Global builders
static BarBuilderState g_m1_builder;
static BarBuilderState g_m3_builder;
static BarBuilderState g_m5_builder;


//+------------------------------------------------------------------+
//| InitBarBuilders
//| Initialize all bar builders for a symbol
//+------------------------------------------------------------------+
void InitBarBuilders(string symbol) {
    // Initialize M1 builder
    g_m1_builder.current_bar.timeframe = 1;
    g_m1_builder.current_bar.open = 0.0;
    g_m1_builder.current_bar.high = 0.0;
    g_m1_builder.current_bar.low = 0.0;
    g_m1_builder.current_bar.close = 0.0;
    g_m1_builder.current_bar.volume = 0;
    g_m1_builder.current_bar.bar_time = TimeCurrent();
    g_m1_builder.bars_built = 0;
    g_m1_builder.is_new_bar = false;
    
    // Initialize M3 builder
    g_m3_builder.current_bar.timeframe = 3;
    g_m3_builder.current_bar.open = 0.0;
    g_m3_builder.current_bar.high = 0.0;
    g_m3_builder.current_bar.low = 0.0;
    g_m3_builder.current_bar.close = 0.0;
    g_m3_builder.current_bar.volume = 0;
    g_m3_builder.current_bar.bar_time = TimeCurrent();
    g_m3_builder.bars_built = 0;
    g_m3_builder.is_new_bar = false;
    
    // Initialize M5 builder
    g_m5_builder.current_bar.timeframe = 5;
    g_m5_builder.current_bar.open = 0.0;
    g_m5_builder.current_bar.high = 0.0;
    g_m5_builder.current_bar.low = 0.0;
    g_m5_builder.current_bar.close = 0.0;
    g_m5_builder.current_bar.volume = 0;
    g_m5_builder.current_bar.bar_time = TimeCurrent();
    g_m5_builder.bars_built = 0;
    g_m5_builder.is_new_bar = false;
}


//+------------------------------------------------------------------+
//| UpdateBar
//| Update bar with new tick price/volume
//| Returns: true if bar was completed
//+------------------------------------------------------------------+
bool UpdateBar(BarBuilderState &builder, double price, long volume) {
    // Initialize first bar
    if (builder.current_bar.open == 0.0) {
        builder.current_bar.open = price;
        builder.current_bar.high = price;
        builder.current_bar.low = price;
        builder.current_bar.close = price;
        builder.current_bar.volume = volume;
        return false;
    }
    
    // Update current bar
    builder.current_bar.high = MathMax(builder.current_bar.high, price);
    builder.current_bar.low = MathMin(builder.current_bar.low, price);
    builder.current_bar.close = price;
    builder.current_bar.volume += volume;
    
    return false;  // Bar not yet complete (completion checked externally)
}


//+------------------------------------------------------------------+
//| ProcessTick
//| Process tick for M1/M3/M5 bar building
//| Checks timeframe boundaries and advances bars if needed
//+------------------------------------------------------------------+
void ProcessTick(double price, long volume, string symbol) {
    datetime current_time = TimeCurrent();
    
    // Check M1 bar boundary (every minute)
    if (g_m1_builder.current_bar.bar_time > 0 && 
        (current_time - g_m1_builder.current_bar.bar_time) >= 60) {
        g_m1_builder.last_completed_bar = g_m1_builder.current_bar;
        g_m1_builder.bars_built++;
        g_m1_builder.is_new_bar = true;
        
        // Reset for new M1 bar
        g_m1_builder.current_bar.open = price;
        g_m1_builder.current_bar.high = price;
        g_m1_builder.current_bar.low = price;
        g_m1_builder.current_bar.close = price;
        g_m1_builder.current_bar.volume = 0;
        g_m1_builder.current_bar.bar_time = current_time;
    }
    
    // Check M3 bar boundary (every 3 minutes)
    if (g_m3_builder.current_bar.bar_time > 0 && 
        (current_time - g_m3_builder.current_bar.bar_time) >= 180) {
        g_m3_builder.last_completed_bar = g_m3_builder.current_bar;
        g_m3_builder.bars_built++;
        g_m3_builder.is_new_bar = true;
        
        // Reset for new M3 bar
        g_m3_builder.current_bar.open = price;
        g_m3_builder.current_bar.high = price;
        g_m3_builder.current_bar.low = price;
        g_m3_builder.current_bar.close = price;
        g_m3_builder.current_bar.volume = 0;
        g_m3_builder.current_bar.bar_time = current_time;
    }
    
    // Check M5 bar boundary (every 5 minutes)
    if (g_m5_builder.current_bar.bar_time > 0 && 
        (current_time - g_m5_builder.current_bar.bar_time) >= 300) {
        g_m5_builder.last_completed_bar = g_m5_builder.current_bar;
        g_m5_builder.bars_built++;
        g_m5_builder.is_new_bar = true;
        
        // Reset for new M5 bar
        g_m5_builder.current_bar.open = price;
        g_m5_builder.current_bar.high = price;
        g_m5_builder.current_bar.low = price;
        g_m5_builder.current_bar.close = price;
        g_m5_builder.current_bar.volume = 0;
        g_m5_builder.current_bar.bar_time = current_time;
    }
    
    // Update all builders with current tick
    UpdateBar(g_m1_builder, price, volume);
    UpdateBar(g_m3_builder, price, volume);
    UpdateBar(g_m5_builder, price, volume);
}


//+------------------------------------------------------------------+
//| GetM1Bar
//| Get current M1 bar
//+------------------------------------------------------------------+
OHLCVBar GetM1Bar() {
    return g_m1_builder.current_bar;
}


//+------------------------------------------------------------------+
//| GetM3Bar
//| Get current M3 bar
//+------------------------------------------------------------------+
OHLCVBar GetM3Bar() {
    return g_m3_builder.current_bar;
}


//+------------------------------------------------------------------+
//| GetM5Bar
//| Get current M5 bar
//+------------------------------------------------------------------+
OHLCVBar GetM5Bar() {
    return g_m5_builder.current_bar;
}


//+------------------------------------------------------------------+
//| GetM1BarCount
//| Get total M1 bars built
//+------------------------------------------------------------------+
int GetM1BarCount() {
    return g_m1_builder.bars_built;
}


//+------------------------------------------------------------------+
//| GetM3BarCount
//| Get total M3 bars built
//+------------------------------------------------------------------+
int GetM3BarCount() {
    return g_m3_builder.bars_built;
}


//+------------------------------------------------------------------+
//| GetM5BarCount
//| Get total M5 bars built
//+------------------------------------------------------------------+
int GetM5BarCount() {
    return g_m5_builder.bars_built;
}

#endif
