//+------------------------------------------------------------------+
//| CVDAccumulator.mqh
//| Cumulative Volume Delta accumulator with session resets
//| WHY: Tracks directional volume (buy - sell) for divergence detection
//+------------------------------------------------------------------+

#ifndef __CVD_ACCUMULATOR_MQH__
#define __CVD_ACCUMULATOR_MQH__

// CVD state per symbol
struct CVDState
{
    string symbol;
    double cvd_running;        // Current accumulated CVD
    datetime last_update_time; // Last tick time
    string last_session;       // Last known session
    int tick_count;            // Ticks processed in this session
    double cumulative_volume;  // Total volume in session
    double last_mid;           // Last mid price
    string last_dominant;      // "BUY" | "SELL" | "NEUTRAL"
};

// Global CVD registry (parallel arrays)
static CVDState g_cvd_states[];

//+------------------------------------------------------------------+
//| FindOrCreateCVDIndex
//| Returns index for a symbol, creating a new slot if necessary
//+------------------------------------------------------------------+
int FindOrCreateCVDIndex(const string symbol)
{
    for (int i = 0; i < ArraySize(g_cvd_states); i++)
    {
        if (StringLen(g_cvd_states[i].symbol) > 0 && StringCompare(g_cvd_states[i].symbol, symbol) == 0)
        {
            return i;
        }
    }
    int idx = ArraySize(g_cvd_states);
    ArrayResize(g_cvd_states, idx + 1);
    g_cvd_states[idx].symbol = symbol;
    g_cvd_states[idx].cvd_running = 0.0;
    g_cvd_states[idx].last_update_time = TimeCurrent();
    g_cvd_states[idx].last_session = "UNKNOWN";
    g_cvd_states[idx].tick_count = 0;
    g_cvd_states[idx].cumulative_volume = 0.0;
    g_cvd_states[idx].last_mid = 0.0;
    g_cvd_states[idx].last_dominant = "NEUTRAL";
    return idx;
}

//+------------------------------------------------------------------+
//| InitCVD
//| Initialize CVD accumulator for a symbol
//+------------------------------------------------------------------+
void InitCVD(const string symbol)
{
    FindOrCreateCVDIndex(symbol);
}

//+------------------------------------------------------------------+
//| AccumulateCVD
//| Accumulate CVD from a single tick. Uses MqlTick.flags when available
//| Returns: updated CVD value
//+------------------------------------------------------------------+
double AccumulateCVD(const string symbol, const MqlTick &tick, const string current_session)
{
    int idx = FindOrCreateCVDIndex(symbol);
    CVDState &state = g_cvd_states[idx];

    // Session boundary: reset CVD if session changed
    if (StringLen(state.last_session) > 0 && StringCompare(state.last_session, current_session) != 0)
    {
        state.cvd_running = 0.0;
        state.tick_count = 0;
        state.cumulative_volume = 0.0;
        state.last_mid = 0.0;
        state.last_dominant = "NEUTRAL";
    }

    state.last_session = current_session;
    state.last_update_time = TimeCurrent();
    state.tick_count++;
    state.cumulative_volume += (double)tick.volume;

    // Determine dominant side from tick.flags if available
    // TICK_FLAG_BUY / TICK_FLAG_SELL constants are available in MQL5
    string dominant = "NEUTRAL";
    if ((tick.flags & TICK_FLAG_BUY) != 0)
        dominant = "BUY";
    else if ((tick.flags & TICK_FLAG_SELL) != 0)
        dominant = "SELL";
    else
    {
        // Fallback heuristic: compare mid to last_mid
        double mid = (tick.bid + tick.ask) / 2.0;
        if (state.last_mid > 0)
        {
            if (mid > state.last_mid)
                dominant = "BUY";
            else if (mid < state.last_mid)
                dominant = "SELL";
            else
                dominant = "NEUTRAL";
        }
        state.last_mid = mid;
    }

    // Update CVD running based on dominant side
    double delta = 0.0;
    if (StringCompare(dominant, "BUY") == 0)
        delta = (double)tick.volume;
    else if (StringCompare(dominant, "SELL") == 0)
        delta = -(double)tick.volume;
    else
        delta = 0.0;

    state.cvd_running += delta;
    state.last_dominant = dominant;

    return state.cvd_running;
}

//+------------------------------------------------------------------+
//| GetCVD
//| Get current CVD for a symbol
//+------------------------------------------------------------------+
double GetCVD(const string symbol)
{
    for (int i = 0; i < ArraySize(g_cvd_states); i++)
    {
        if (StringLen(g_cvd_states[i].symbol) > 0 && StringCompare(g_cvd_states[i].symbol, symbol) == 0)
        {
            return g_cvd_states[i].cvd_running;
        }
    }
    return 0.0;
}

//+------------------------------------------------------------------+
//| GetDominantSide
//| Returns the last dominant side for the symbol: "BUY"|"SELL"|"NEUTRAL"
//+------------------------------------------------------------------+
string GetDominantSide(const string symbol)
{
    for (int i = 0; i < ArraySize(g_cvd_states); i++)
    {
        if (StringLen(g_cvd_states[i].symbol) > 0 && StringCompare(g_cvd_states[i].symbol, symbol) == 0)
        {
            return g_cvd_states[i].last_dominant;
        }
    }
    return "NEUTRAL";
}

//+------------------------------------------------------------------+
//| ResetCVD
//| Reset CVD for a symbol (session boundary or manual)
//+------------------------------------------------------------------+
void ResetCVD(const string symbol)
{
    for (int i = 0; i < ArraySize(g_cvd_states); i++)
    {
        if (StringLen(g_cvd_states[i].symbol) > 0 && StringCompare(g_cvd_states[i].symbol, symbol) == 0)
        {
            g_cvd_states[i].cvd_running = 0.0;
            g_cvd_states[i].tick_count = 0;
            g_cvd_states[i].cumulative_volume = 0.0;
            g_cvd_states[i].last_mid = 0.0;
            g_cvd_states[i].last_dominant = "NEUTRAL";
            break;
        }
    }
}

//+------------------------------------------------------------------+
//| GetCVDTickCount
//| Get number of ticks processed in current session
//+------------------------------------------------------------------+
int GetCVDTickCount(const string symbol)
{
    for (int i = 0; i < ArraySize(g_cvd_states); i++)
    {
        if (StringLen(g_cvd_states[i].symbol) > 0 && StringCompare(g_cvd_states[i].symbol, symbol) == 0)
        {
            return g_cvd_states[i].tick_count;
        }
    }
    return 0;
}

#endif
