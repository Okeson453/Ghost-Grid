//+------------------------------------------------------------------+
//| ExitLogic.mqh
//| Multi-layer exit evaluation for GHOST GRID positions
//| WHY: Implement 4-layer exit strategy (profit target, stop loss, etc)
//+------------------------------------------------------------------+

#ifndef __EXIT_LOGIC_MQH__
#define __EXIT_LOGIC_MQH__

// Exit reason enum
enum ExitReason {
    EXIT_NONE = 0,
    EXIT_PROFIT_TARGET = 1,
    EXIT_STOP_LOSS = 2,
    EXIT_CVD_DIVERGENCE = 3,
    EXIT_REGIME_SHIFT = 4,
    EXIT_MANUAL_CLOSE = 5,
    EXIT_FORCED_CLOSE = 6
};

// Exit signal structure
struct ExitSignal {
    bool should_exit;           // Exit flag
    ExitReason reason;          // Why we're exiting
    double exit_price;          // Target exit price
    string description;         // Human-readable reason
    int priority;               // Exit priority (higher = more urgent)
};


//+------------------------------------------------------------------+
//| EvaluateProfitTarget
//| Check if position has hit profit target
//+------------------------------------------------------------------+
ExitSignal EvaluateProfitTarget(
    int direction,
    double current_price,
    double target_price
) {
    ExitSignal signal = {false, EXIT_NONE, 0.0, "", 0};
    
    if (direction == 1) {  // BUY
        if (current_price >= target_price) {
            signal.should_exit = true;
            signal.reason = EXIT_PROFIT_TARGET;
            signal.exit_price = MathMax(current_price, target_price);
            signal.description = "Hit profit target";
            signal.priority = 1;  // Lowest priority
        }
    } else {  // SELL
        if (current_price <= target_price) {
            signal.should_exit = true;
            signal.reason = EXIT_PROFIT_TARGET;
            signal.exit_price = MathMin(current_price, target_price);
            signal.description = "Hit profit target";
            signal.priority = 1;
        }
    }
    
    return signal;
}


//+------------------------------------------------------------------+
//| EvaluateStopLoss
//| Check if position has hit stop loss (highest priority)
//+------------------------------------------------------------------+
ExitSignal EvaluateStopLoss(
    int direction,
    double current_price,
    double stop_level
) {
    ExitSignal signal = {false, EXIT_NONE, 0.0, "", 0};
    
    if (direction == 1) {  // BUY
        if (current_price <= stop_level) {
            signal.should_exit = true;
            signal.reason = EXIT_STOP_LOSS;
            signal.exit_price = MathMin(current_price, stop_level);
            signal.description = "Hit stop loss";
            signal.priority = 4;  // Highest priority
        }
    } else {  // SELL
        if (current_price >= stop_level) {
            signal.should_exit = true;
            signal.reason = EXIT_STOP_LOSS;
            signal.exit_price = MathMax(current_price, stop_level);
            signal.description = "Hit stop loss";
            signal.priority = 4;
        }
    }
    
    return signal;
}


//+------------------------------------------------------------------+
//| EvaluateCVDDivergence
//| Check for CVD divergence (price up, CVD down = bearish)
//+------------------------------------------------------------------+
ExitSignal EvaluateCVDDivergence(
    int direction,
    double current_price,
    double entry_price,
    double current_cvd,
    double entry_cvd
) {
    ExitSignal signal = {false, EXIT_NONE, 0.0, "", 0};
    
    double price_move = (current_price - entry_price) / entry_price * 100.0;
    double cvd_move = current_cvd - entry_cvd;
    
    // Detect divergence: price moving up but CVD down (or vice versa)
    if (direction == 1) {  // BUY position
        // Bearish divergence: price up 1%+, but CVD down
        if (price_move > 1.0 && cvd_move < 0) {
            signal.should_exit = true;
            signal.reason = EXIT_CVD_DIVERGENCE;
            signal.exit_price = current_price;
            signal.description = "CVD divergence detected (bearish)";
            signal.priority = 3;  // High priority
        }
    } else {  // SELL position
        // Bullish divergence: price down 1%+, but CVD up
        if (price_move < -1.0 && cvd_move > 0) {
            signal.should_exit = true;
            signal.reason = EXIT_CVD_DIVERGENCE;
            signal.exit_price = current_price;
            signal.description = "CVD divergence detected (bullish)";
            signal.priority = 3;
        }
    }
    
    return signal;
}


//+------------------------------------------------------------------+
//| EvaluateRegimeShift
//| Check if market regime has shifted away from entry regime
//+------------------------------------------------------------------+
ExitSignal EvaluateRegimeShift(
    string regime_at_entry,
    string current_regime
) {
    ExitSignal signal = {false, EXIT_NONE, 0.0, "", 0};
    
    // Exit if regime changed
    if (regime_at_entry != current_regime) {
        signal.should_exit = true;
        signal.reason = EXIT_REGIME_SHIFT;
        signal.description = StringFormat("Regime shift: %s → %s", regime_at_entry, current_regime);
        signal.priority = 2;  // Medium-high priority
    }
    
    return signal;
}


//+------------------------------------------------------------------+
//| EvaluatePartialTakeProfit
//| Implement trailing profit/partial close logic
//+------------------------------------------------------------------+
ExitSignal EvaluatePartialTakeProfit(
    int direction,
    double current_price,
    double entry_price,
    double max_profit_pips,
    double trailing_stop_pips
) {
    ExitSignal signal = {false, EXIT_NONE, 0.0, "", 0};
    
    double current_pnl_pips = (current_price - entry_price) / 0.00001;  // Convert to pips
    
    if (direction == 1) {  // BUY
        // Trailing stop: if price retraces 50 pips from max, exit
        if (max_profit_pips > 100 && (max_profit_pips - current_pnl_pips) > trailing_stop_pips) {
            signal.should_exit = true;
            signal.reason = EXIT_PROFIT_TARGET;
            signal.exit_price = current_price;
            signal.description = StringFormat("Trailing stop triggered: %f pips retrace", 
                                            max_profit_pips - current_pnl_pips);
            signal.priority = 2;  // Medium priority
        }
    } else {  // SELL
        // Similar logic for short positions
        if (max_profit_pips > 100 && (max_profit_pips - current_pnl_pips) > trailing_stop_pips) {
            signal.should_exit = true;
            signal.reason = EXIT_PROFIT_TARGET;
            signal.exit_price = current_price;
            signal.description = "Trailing stop triggered";
            signal.priority = 2;
        }
    }
    
    return signal;
}


//+------------------------------------------------------------------+
//| EvaluateTimeDecay
//| Exit if position held too long without profit (max_bars exceeded)
//+------------------------------------------------------------------+
ExitSignal EvaluateTimeDecay(
    int bars_held,
    int max_bars,
    double current_price,
    double entry_price
) {
    ExitSignal signal = {false, EXIT_NONE, 0.0, "", 0};
    
    if (bars_held > max_bars) {
        signal.should_exit = true;
        signal.reason = EXIT_FORCED_CLOSE;
        signal.exit_price = current_price;
        signal.description = StringFormat("Max bars exceeded: %d > %d", bars_held, max_bars);
        signal.priority = 2;
    }
    
    return signal;
}


//+------------------------------------------------------------------+
//| SelectBestExit
//| Choose best exit signal from multiple candidates (highest priority)
//+------------------------------------------------------------------+
ExitSignal SelectBestExit(
    ExitSignal signal1,
    ExitSignal signal2,
    ExitSignal signal3,
    ExitSignal signal4
) {
    ExitSignal signals[4] = {signal1, signal2, signal3, signal4};
    ExitSignal best = {false, EXIT_NONE, 0.0, "", 0};
    
    for (int i = 0; i < 4; i++) {
        if (signals[i].should_exit && signals[i].priority > best.priority) {
            best = signals[i];
        }
    }
    
    return best;
}

#endif