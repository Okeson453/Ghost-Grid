//+------------------------------------------------------------------+
//| PositionTracker.mqh
//| Position lifecycle management and state tracking for GHOST GRID
//| WHY: Track entry state, confluence scores, regime shifts for exits
//+------------------------------------------------------------------+

#ifndef __POSITION_TRACKER_MQH__
#define __POSITION_TRACKER_MQH__

// Position state enum
enum PositionState {
    POS_NONE = 0,
    POS_ENTRY = 1,
    POS_ACTIVE = 2,
    POS_AT_TARGET = 3,
    POS_AT_STOP = 4,
    POS_CLOSING = 5
};

// Position tracking record
struct TrackedPosition {
    ulong ticket;               // MT5 position ticket
    string symbol;              // Trading pair
    int direction;              // 1=BUY, -1=SELL
    double entry_price;         // Entry price
    datetime entry_time;        // Entry timestamp
    double lot_size;            // Position size
    double profit_target;       // TP level
    double stop_loss;           // SL level
    double h_c_score;           // Confluence score at entry
    string regime_at_entry;     // Regime snapshot
    double max_profit;          // Max unrealised profit
    double max_loss;            // Max unrealised loss
    PositionState state;        // Current position state
    int bars_held;              // Bars in position
    datetime last_update;       // Last state update
};

// Global position registry
static TrackedPosition g_positions[];
static int g_position_count = 0;
static int g_max_positions = 50;


//+------------------------------------------------------------------+
//| InitPositionTracker
//| Initialize position tracking system
//+------------------------------------------------------------------+
void InitPositionTracker() {
    ArrayResize(g_positions, g_max_positions);
    g_position_count = 0;
}


//+------------------------------------------------------------------+
//| AddPosition
//| Register a new position for tracking
//+------------------------------------------------------------------+
bool AddPosition(
    ulong ticket,
    string symbol,
    int direction,
    double entry_price,
    double lot_size,
    double profit_target,
    double stop_loss,
    double h_c_score,
    string regime
) {
    if (g_position_count >= g_max_positions) {
        return false;  // Registry full
    }
    
    TrackedPosition &pos = g_positions[g_position_count];
    pos.ticket = ticket;
    pos.symbol = symbol;
    pos.direction = direction;
    pos.entry_price = entry_price;
    pos.entry_time = TimeCurrent();
    pos.lot_size = lot_size;
    pos.profit_target = profit_target;
    pos.stop_loss = stop_loss;
    pos.h_c_score = h_c_score;
    pos.regime_at_entry = regime;
    pos.max_profit = 0.0;
    pos.max_loss = 0.0;
    pos.state = POS_ENTRY;
    pos.bars_held = 0;
    pos.last_update = TimeCurrent();
    
    g_position_count++;
    return true;
}


//+------------------------------------------------------------------+
//| UpdatePositionState
//| Update position state based on current price
//+------------------------------------------------------------------+
void UpdatePositionState(ulong ticket, double current_price) {
    for (int i = 0; i < g_position_count; i++) {
        if (g_positions[i].ticket == ticket) {
            TrackedPosition &pos = g_positions[i];
            
            // Calculate unrealised P&L
            double pnl = pos.direction * (current_price - pos.entry_price) * 100;  // Simplified
            
            // Track max profit/loss
            pos.max_profit = MathMax(pos.max_profit, pnl);
            pos.max_loss = MathMin(pos.max_loss, pnl);
            
            // Update state based on price levels
            if (pos.direction == 1) {  // BUY position
                if (current_price >= pos.profit_target) {
                    pos.state = POS_AT_TARGET;
                } else if (current_price <= pos.stop_loss) {
                    pos.state = POS_AT_STOP;
                } else {
                    pos.state = POS_ACTIVE;
                }
            } else {  // SELL position
                if (current_price <= pos.profit_target) {
                    pos.state = POS_AT_TARGET;
                } else if (current_price >= pos.stop_loss) {
                    pos.state = POS_AT_STOP;
                } else {
                    pos.state = POS_ACTIVE;
                }
            }
            
            pos.bars_held++;
            pos.last_update = TimeCurrent();
            return;
        }
    }
}


//+------------------------------------------------------------------+
//| GetPositionState
//| Get current state of a position
//+------------------------------------------------------------------+
PositionState GetPositionState(ulong ticket) {
    for (int i = 0; i < g_position_count; i++) {
        if (g_positions[i].ticket == ticket) {
            return g_positions[i].state;
        }
    }
    return POS_NONE;
}


//+------------------------------------------------------------------+
//| GetPositionByTicket
//| Get position record by ticket
//+------------------------------------------------------------------+
TrackedPosition *GetPositionByTicket(ulong ticket) {
    for (int i = 0; i < g_position_count; i++) {
        if (g_positions[i].ticket == ticket) {
            return &g_positions[i];
        }
    }
    return NULL;
}


//+------------------------------------------------------------------+
//| RemovePosition
//| Remove closed position from registry
//+------------------------------------------------------------------+
bool RemovePosition(ulong ticket) {
    for (int i = 0; i < g_position_count; i++) {
        if (g_positions[i].ticket == ticket) {
            // Shift remaining positions
            for (int j = i; j < g_position_count - 1; j++) {
                g_positions[j] = g_positions[j + 1];
            }
            g_position_count--;
            return true;
        }
    }
    return false;
}


//+------------------------------------------------------------------+
//| GetOpenPositionCount
//| Get total tracked open positions
//+------------------------------------------------------------------+
int GetTrackedPositionCount() {
    return g_position_count;
}


//+------------------------------------------------------------------+
//| GetPositionsByState
//| Count positions in a specific state
//+------------------------------------------------------------------+
int GetPositionsByState(PositionState state) {
    int count = 0;
    for (int i = 0; i < g_position_count; i++) {
        if (g_positions[i].state == state) {
            count++;
        }
    }
    return count;
}


//+------------------------------------------------------------------+
//| GetAverageConfluence
//| Get average confluence score of open positions
//+------------------------------------------------------------------+
double GetAverageConfluence() {
    if (g_position_count == 0) {
        return 0.0;
    }
    
    double total = 0.0;
    for (int i = 0; i < g_position_count; i++) {
        total += g_positions[i].h_c_score;
    }
    return total / g_position_count;
}


//+------------------------------------------------------------------+
//| GetMaxPositionProfit
//| Get maximum profit from a position
//+------------------------------------------------------------------+
double GetMaxPositionProfit(ulong ticket) {
    TrackedPosition *pos = GetPositionByTicket(ticket);
    if (pos != NULL) {
        return pos.max_profit;
    }
    return 0.0;
}


//+------------------------------------------------------------------+
//| GetBarsHeld
//| Get number of bars position has been held
//+------------------------------------------------------------------+
int GetBarsHeld(ulong ticket) {
    TrackedPosition *pos = GetPositionByTicket(ticket);
    if (pos != NULL) {
        return pos.bars_held;
    }
    return 0;
}

#endif