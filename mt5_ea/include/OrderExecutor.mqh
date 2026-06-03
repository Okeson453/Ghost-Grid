//+------------------------------------------------------------------+
//| OrderExecutor.mqh
//| Trade execution and fill tracking for GHOST GRID EA
//| WHY: Orchestrates order lifecycle (REQUEST → PENDING → FILL → REPORT)
//+------------------------------------------------------------------+

#ifndef __ORDER_EXECUTOR_MQH__
#define __ORDER_EXECUTOR_MQH__

// Order state tracking
struct OrderState {
    ulong request_id;            // Unique request ID
    string symbol;               // Trading pair
    string direction;            // "BUY" or "SELL"
    double lot_size;             // Position size in lots
    double entry_price;          // Order entry level
    datetime create_time;        // Order creation time
    int status;                  // 0=PENDING, 1=FILL, 2=REJECT, 3=FAILED
    double fill_price;           // Actual fill price (if filled)
    double profit_loss;          // P&L in USD (if closed)
};

// Global order registry (keyed by request_id)
static OrderState g_orders[];
static ulong g_next_request_id = 1000;


//+------------------------------------------------------------------+
//| CreateOrder
//| Create new order and add to registry
//| Returns: request_id (or 0 if failed)
//+------------------------------------------------------------------+
ulong CreateOrder(
    string symbol,
    string direction,
    double lot_size,
    double entry_price
) {
    // Validate inputs
    if (lot_size <= 0 || entry_price <= 0) {
        return 0;
    }
    
    // Expand array if needed
    int idx = ArraySize(g_orders);
    ArrayResize(g_orders, idx + 1);
    
    ulong request_id = g_next_request_id++;
    
    g_orders[idx].request_id = request_id;
    g_orders[idx].symbol = symbol;
    g_orders[idx].direction = direction;
    g_orders[idx].lot_size = lot_size;
    g_orders[idx].entry_price = entry_price;
    g_orders[idx].create_time = TimeCurrent();
    g_orders[idx].status = 0;  // PENDING
    g_orders[idx].fill_price = 0.0;
    g_orders[idx].profit_loss = 0.0;
    
    return request_id;
}


//+------------------------------------------------------------------+
//| UpdateOrderFill
//| Mark order as filled with actual fill price
//| Returns: true if successful
//+------------------------------------------------------------------+
bool UpdateOrderFill(ulong request_id, double fill_price) {
    for (int i = 0; i < ArraySize(g_orders); i++) {
        if (g_orders[i].request_id == request_id) {
            g_orders[i].status = 1;  // FILL
            g_orders[i].fill_price = fill_price;
            return true;
        }
    }
    return false;
}


//+------------------------------------------------------------------+
//| UpdateOrderReject
//| Mark order as rejected
//+------------------------------------------------------------------+
bool UpdateOrderReject(ulong request_id) {
    for (int i = 0; i < ArraySize(g_orders); i++) {
        if (g_orders[i].request_id == request_id) {
            g_orders[i].status = 2;  // REJECT
            return true;
        }
    }
    return false;
}


//+------------------------------------------------------------------+
//| UpdateOrderFailed
//| Mark order as failed
//+------------------------------------------------------------------+
bool UpdateOrderFailed(ulong request_id) {
    for (int i = 0; i < ArraySize(g_orders); i++) {
        if (g_orders[i].request_id == request_id) {
            g_orders[i].status = 3;  // FAILED
            return true;
        }
    }
    return false;
}


//+------------------------------------------------------------------+
//| GetOrderStatus
//| Get order status: 0=PENDING, 1=FILL, 2=REJECT, 3=FAILED
//+------------------------------------------------------------------+
int GetOrderStatus(ulong request_id) {
    for (int i = 0; i < ArraySize(g_orders); i++) {
        if (g_orders[i].request_id == request_id) {
            return g_orders[i].status;
        }
    }
    return -1;  // Not found
}


//+------------------------------------------------------------------+
//| GetOrderFillPrice
//| Get fill price for an order
//+------------------------------------------------------------------+
double GetOrderFillPrice(ulong request_id) {
    for (int i = 0; i < ArraySize(g_orders); i++) {
        if (g_orders[i].request_id == request_id) {
            return g_orders[i].fill_price;
        }
    }
    return 0.0;
}


//+------------------------------------------------------------------+
//| SendOrderToMT5
//| Place market order via MT5 OrderSend
//| Returns: ticket (position ID) or -1 if failed
//+------------------------------------------------------------------+
int SendOrderToMT5(
    string symbol,
    string direction,
    double lot_size,
    double slippage = 10.0
) {
    MqlTradeRequest request = {0};
    MqlTradeResult result = {0};
    
    // Build trade request
    request.action = TRADE_ACTION_DEAL;
    request.symbol = symbol;
    request.volume = lot_size;
    request.type = (direction == "BUY") ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
    request.price = SymbolInfoDouble(symbol, (direction == "BUY") ? SYMBOL_ASK : SYMBOL_BID);
    request.deviation = (int)slippage;
    request.comment = "GHOST_GRID";
    
    // Execute order
    if (OrderSend(&request, &result)) {
        return (int)result.order;  // Return ticket/position ID
    }
    
    return -1;
}


//+------------------------------------------------------------------+
//| ClosePositionByTicket
//| Close an open position by ticket ID
//| Returns: true if successful
//+------------------------------------------------------------------+
bool ClosePositionByTicket(int ticket) {
    MqlTradeRequest request = {0};
    MqlTradeResult result = {0};
    
    request.action = TRADE_ACTION_DEAL;
    request.position = ticket;
    request.type = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? 
                   ORDER_TYPE_SELL : ORDER_TYPE_BUY;
    request.symbol = PositionGetString(POSITION_SYMBOL);
    request.volume = PositionGetDouble(POSITION_VOLUME);
    
    return OrderSend(&request, &result);
}


//+------------------------------------------------------------------+
//| ExecuteNuclearClose
//| Close all open positions immediately
//| Returns: count of positions closed
//+------------------------------------------------------------------+
int ExecuteNuclearClose() {
    int closed_count = 0;
    
    for (int i = 0; i < PositionsTotal(); i++) {
        if (PositionSelect(i)) {
            if (ClosePositionByTicket((int)PositionGetTicket(i))) {
                closed_count++;
            }
        }
    }
    
    return closed_count;
}


//+------------------------------------------------------------------+
//| GetOpenPositionCount
//| Get total number of open positions
//+------------------------------------------------------------------+
int GetOpenPositionCount() {
    return PositionsTotal();
}

#endif
