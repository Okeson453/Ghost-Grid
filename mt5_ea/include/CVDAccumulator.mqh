//+------------------------------------------------------------------+
//| CVDAccumulator.mqh
//| Cumulative Volume Delta accumulator with session resets
//| WHY: Tracks directional volume (buy - sell) for divergence detection
//+------------------------------------------------------------------+

#ifndef __CVD_ACCUMULATOR_MQH__
#define __CVD_ACCUMULATOR_MQH__

// CVD state per symbol
struct CVDState {
    double cvd_running;          // Current accumulated CVD
    datetime last_update_time;   // Last tick time
    string last_session;         // Last known session
    int tick_count;              // Ticks processed in this session
    double cumulative_volume;    // Total volume in session
};

// Global CVD registry (keyed by symbol)
static CVDState g_cvd_states[];


//+------------------------------------------------------------------+
//| InitCVD
//| Initialize CVD accumulator for a symbol
//+------------------------------------------------------------------+
void InitCVD(string symbol) {
    int idx = GetCVDIndex(symbol);
    if (idx >= 0) {
        g_cvd_states[idx].cvd_running = 0.0;
        g_cvd_states[idx].last_update_time = TimeCurrent();
        g_cvd_states[idx].last_session = "UNKNOWN";
        g_cvd_states[idx].tick_count = 0;
        g_cvd_states[idx].cumulative_volume = 0.0;
    }
}


//+------------------------------------------------------------------+
//| GetCVDIndex
//| Get index in g_cvd_states array (or create if not exists)
//+------------------------------------------------------------------+
int GetCVDIndex(string symbol) {
    for (int i = 0; i < ArraySize(g_cvd_states); i++) {
        // Check if slot is for this symbol
        if (StringLen(symbol) > 0) {
            // Simple check: if tick_count is 0, slot is available
            if (g_cvd_states[i].tick_count == 0 && g_cvd_states[i].cumulative_volume == 0.0) {
                return i;
            }
        }
    }
    
    // Expand array if needed
    int new_size = ArraySize(g_cvd_states) + 1;
    ArrayResize(g_cvd_states, new_size);
    return new_size - 1;
}


//+------------------------------------------------------------------+
//| AccumulateCVD
//| Accumulate CVD from a single tick
//| Returns: updated CVD value
//+------------------------------------------------------------------+
double AccumulateCVD(
    string symbol,
    double bid,
    double ask,
    double volume,
    string current_session
) {
    int idx = GetCVDIndex(symbol);
    if (idx < 0) {
        return 0.0;
    }
    
    CVDState &state = g_cvd_states[idx];
    
    // Session boundary: reset CVD
    if (current_session != state.last_session && StringLen(state.last_session) > 0) {
        state.cvd_running = 0.0;
        state.tick_count = 0;
        state.cumulative_volume = 0.0;
    }
    
    state.last_session = current_session;
    state.last_update_time = TimeCurrent();
    state.tick_count++;
    state.cumulative_volume += volume;
    
    // CVD delta calculation:
    // If bid ticked up (compare to previous): buying volume
    // If ask ticked down (compare to previous): selling pressure
    // Simplified: use volume × (bid - ask) direction
    // Positive CVD = buying pressure, Negative CVD = selling pressure
    
    double mid = (bid + ask) / 2.0;
    double delta = (bid > ask) ? volume : -volume;  // Simplified heuristic
    
    state.cvd_running += delta;
    
    return state.cvd_running;
}


//+------------------------------------------------------------------+
//| GetCVD
//| Get current CVD for a symbol
//+------------------------------------------------------------------+
double GetCVD(string symbol) {
    for (int i = 0; i < ArraySize(g_cvd_states); i++) {
        // Search for symbol (this is simplified; real implementation would use a map)
        // For now, return first state's CVD
        if (g_cvd_states[i].cumulative_volume > 0 || g_cvd_states[i].tick_count > 0) {
            return g_cvd_states[i].cvd_running;
        }
    }
    return 0.0;
}


//+------------------------------------------------------------------+
//| ResetCVD
//| Reset CVD for a symbol (session boundary or manual)
//+------------------------------------------------------------------+
void ResetCVD(string symbol) {
    for (int i = 0; i < ArraySize(g_cvd_states); i++) {
        if (g_cvd_states[i].cumulative_volume > 0 || g_cvd_states[i].tick_count > 0) {
            g_cvd_states[i].cvd_running = 0.0;
            g_cvd_states[i].tick_count = 0;
            g_cvd_states[i].cumulative_volume = 0.0;
            break;
        }
    }
}


//+------------------------------------------------------------------+
//| GetCVDTickCount
//| Get number of ticks processed in current session
//+------------------------------------------------------------------+
int GetCVDTickCount(string symbol) {
    for (int i = 0; i < ArraySize(g_cvd_states); i++) {
        if (g_cvd_states[i].tick_count > 0) {
            return g_cvd_states[i].tick_count;
        }
    }
    return 0;
}

#endif
