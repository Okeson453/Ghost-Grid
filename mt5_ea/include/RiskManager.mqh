//+------------------------------------------------------------------+
//| RiskManager.mqh
//| Risk management and position sizing for GHOST GRID
//| WHY: Enforce risk limits, position sizing, portfolio constraints
//+------------------------------------------------------------------+

#ifndef __RISK_MANAGER_MQH__
#define __RISK_MANAGER_MQH__

// Risk management configuration
struct RiskConfig {
    double max_position_size;       // Max lot size per trade
    double max_total_exposure;      // Max total notional exposure
    double max_daily_loss;          // Stop trading if daily loss > this
    double max_positions;           // Max concurrent open positions
    double risk_per_trade_pct;      // Risk % per position
    double max_correlation;         // Max portfolio correlation
};

// Risk state
struct RiskState {
    double daily_pnl;               // Daily P&L
    double total_exposure;          // Total notional exposure
    int position_count;             // Open position count
    double largest_position;        // Size of largest position
    bool daily_limit_hit;           // Daily loss limit triggered
    bool risk_check_passed;         // Last risk check result
};

static RiskConfig g_risk_config = {
    10.0,      // max_position_size (10 lots)
    100.0,     // max_total_exposure (100 lots total)
    2000.0,    // max_daily_loss ($2000)
    3,         // max_positions (3 open positions)
    2.0,       // risk_per_trade_pct (2% of account)
    0.85       // max_correlation (85%)
};

static RiskState g_risk_state = {0.0, 0.0, 0, 0.0, false, true};


//+------------------------------------------------------------------+
//| InitRiskManager
//| Initialize risk manager with config
//+------------------------------------------------------------------+
void InitRiskManager(RiskConfig config) {
    g_risk_config = config;
    g_risk_state.daily_pnl = 0.0;
    g_risk_state.total_exposure = 0.0;
    g_risk_state.position_count = 0;
    g_risk_state.largest_position = 0.0;
    g_risk_state.daily_limit_hit = false;
    g_risk_state.risk_check_passed = true;
}


//+------------------------------------------------------------------+
//| CheckPositionSizeValid
//| Verify position size doesn't exceed limits
//+------------------------------------------------------------------+
bool CheckPositionSizeValid(double proposed_lot_size) {
    // Check against max per-trade limit
    if (proposed_lot_size > g_risk_config.max_position_size) {
        return false;
    }
    
    // Check against total exposure limit
    if (g_risk_state.total_exposure + proposed_lot_size > g_risk_config.max_total_exposure) {
        return false;
    }
    
    return true;
}


//+------------------------------------------------------------------+
//| CheckMaxPositionsExceeded
//| Verify we haven't exceeded max concurrent positions
//+------------------------------------------------------------------+
bool CheckMaxPositionsExceeded() {
    return PositionsTotal() >= (int)g_risk_config.max_positions;
}


//+------------------------------------------------------------------+
//| CheckDailyLossLimit
//| Verify we haven't exceeded daily loss limit
//+------------------------------------------------------------------+
bool CheckDailyLossLimit(double current_daily_pnl) {
    if (current_daily_pnl < -g_risk_config.max_daily_loss) {
        g_risk_state.daily_limit_hit = true;
        return false;  // Limit exceeded
    }
    return true;
}


//+------------------------------------------------------------------+
//| CalculatePositionSize
//| Calculate appropriate position size based on account and risk
//+------------------------------------------------------------------+
double CalculatePositionSize(
    double account_balance,
    double stop_loss_pips,
    double risk_amount_usd
) {
    // Position size = Risk Amount / (Stop Loss Distance × Pip Value)
    // Simplified: lots = risk_usd / (stop_pips × 10 × leverage_factor)
    
    if (stop_loss_pips <= 0 || risk_amount_usd <= 0) {
        return 0.01;  // Minimum lot
    }
    
    double pip_value = 10.0;  // $10 per 1 pip for 1 lot (EURUSD)
    double position_size = risk_amount_usd / (stop_loss_pips * pip_value);
    
    // Cap to max allowed
    position_size = MathMin(position_size, g_risk_config.max_position_size);
    position_size = MathMax(position_size, 0.01);  // Minimum 0.01 lot
    
    return position_size;
}


//+------------------------------------------------------------------+
//| UpdateRiskState
//| Update current risk state based on open positions
//+------------------------------------------------------------------+
void UpdateRiskState() {
    g_risk_state.position_count = PositionsTotal();
    g_risk_state.total_exposure = 0.0;
    g_risk_state.largest_position = 0.0;
    
    for (int i = 0; i < PositionsTotal(); i++) {
        if (PositionSelect(i)) {
            double volume = PositionGetDouble(POSITION_VOLUME);
            g_risk_state.total_exposure += volume;
            g_risk_state.largest_position = MathMax(g_risk_state.largest_position, volume);
        }
    }
}


//+------------------------------------------------------------------+
//| PerformRiskCheck
//| Comprehensive risk check before allowing new trade
//+------------------------------------------------------------------+
bool PerformRiskCheck(double proposed_lot_size, double current_daily_pnl) {
    UpdateRiskState();
    
    // Check 1: Position size
    if (!CheckPositionSizeValid(proposed_lot_size)) {
        g_risk_state.risk_check_passed = false;
        return false;
    }
    
    // Check 2: Max positions
    if (CheckMaxPositionsExceeded()) {
        g_risk_state.risk_check_passed = false;
        return false;
    }
    
    // Check 3: Daily loss limit
    if (!CheckDailyLossLimit(current_daily_pnl)) {
        g_risk_state.risk_check_passed = false;
        return false;
    }
    
    g_risk_state.risk_check_passed = true;
    return true;
}


//+------------------------------------------------------------------+
//| GetRiskMetrics
//| Get current risk metrics
//+------------------------------------------------------------------+
string GetRiskMetrics() {
    UpdateRiskState();
    
    return StringFormat(
        "Positions:%d|Exposure:%.2f|MaxPos:%.2f|DailyPnL:%.2f|LimitHit:%d",
        g_risk_state.position_count,
        g_risk_state.total_exposure,
        g_risk_state.largest_position,
        g_risk_state.daily_pnl,
        g_risk_state.daily_limit_hit ? 1 : 0
    );
}


//+------------------------------------------------------------------+
//| GetAvailableRiskCapacity
//| Get how much more risk we can take
//+------------------------------------------------------------------+
double GetAvailableRiskCapacity() {
    UpdateRiskState();
    return g_risk_config.max_total_exposure - g_risk_state.total_exposure;
}


//+------------------------------------------------------------------+
//| IsRiskManagementActive
//| Check if risk management is enforcing limits
//+------------------------------------------------------------------+
bool IsRiskManagementActive() {
    return !g_risk_state.daily_limit_hit && g_risk_state.risk_check_passed;
}


//+------------------------------------------------------------------+
//| ResetDailyRisk
//| Reset daily counters (call at start of trading day)
//+------------------------------------------------------------------+
void ResetDailyRisk() {
    g_risk_state.daily_pnl = 0.0;
    g_risk_state.daily_limit_hit = false;
}

#endif