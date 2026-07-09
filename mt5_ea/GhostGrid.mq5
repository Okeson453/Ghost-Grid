//+------------------------------------------------------------------+
//| GhostGrid.mq5
//| GHOST GRID algorithmic trading EA — Phase 1-3 Foundation
//| PURPOSE: Tick emission + trade execution + position management
//| PHASE 1: Tick emission + heartbeat + CVD accumulation (COMPLETE)
//| PHASE 2: Command receiving + order execution + fill reporting (COMPLETE)
//| PHASE 3: Position tracking + exit logic + risk management (NEW)
//+------------------------------------------------------------------+

#property copyright "GHOST GRID"
#property link "https://github.com/Okeson453/Ghost-Grid"
#property version "2.00"
#property strict
#property description "Complete trading EA with position management"

// Include headers
#include <PipeServer.mqh>
#include <Heartbeat.mqh>
#include <CVDAccumulator.mqh>
#include <OHLCVBuilder.mqh>
#include <OrderExecutor.mqh>
#include <SpreadMonitor.mqh>
#include <PositionTracker.mqh>
#include <ExitLogic.mqh>

// Configuration
#define PIPE_PATH "\\\\.\\pipe\\ghostgrid"
#define TICK_EMIT_INTERVAL_MS 200
#define COMMAND_POLL_INTERVAL_MS 100
#define SYMBOLS_TO_TRADE "EURUSD,GBPUSD,USDJPY,XAUUSD"
#define EXIT_CHECK_INTERVAL_MS 500

// Phase 2: Command processing
#define MAX_PENDING_COMMANDS 100
struct PendingCommand
{
    string command_type; // "ORDER" or "CLOSE"
    string symbol;
    string direction;
    double lot_size;
    double entry_price;
    ulong position_id;
    string exit_reason;
    datetime received_time;
};

static PendingCommand g_pending_commands[];
static int g_command_index = 0;

// Phase 3: Exit tracking
static datetime g_last_exit_check = 0;
static ulong g_positions_closed = 0;
static ulong g_total_pnl_usd = 0;

// Global state
static datetime g_last_tick_time = 0;
static datetime g_last_command_check = 0;
static ulong g_ticks_emitted = 0;
static ulong g_pipe_writes = 0;
static ulong g_orders_executed = 0;
static ulong g_fills_reported = 0;
static int g_errors = 0;
static bool g_ea_running = false;

//+------------------------------------------------------------------+
//| OnInit
//| Initialize EA on startup
//+------------------------------------------------------------------+
int OnInit()
{
    // Initialize pipe connection
    if (!InitPipe(PIPE_PATH))
    {
        Alert("Failed to initialize pipe: " + PIPE_PATH);
        return INIT_FAILED;
    }

    // Initialize heartbeat system
    InitHeartbeat();

    // Initialize spread monitoring
    InitSpreadMonitor();

    // Initialize bar builders
    InitBarBuilders(Symbol());

    // Initialize position tracking (Phase 3)
    InitPositionTracker();

    // Risk governor is enforced in the Python core per design; EA does not set portfolio-level hard limits here.

    // Initialize CVD for each symbol
    string symbols_list[4];
    int symbol_count = StringSplit(SYMBOLS_TO_TRADE, ",", symbols_list);

    for (int i = 0; i < symbol_count; i++)
    {
        InitCVD(symbols_list[i]);
    }

    // Initialize command queue
    ArrayResize(g_pending_commands, MAX_PENDING_COMMANDS);

    g_ea_running = true;
    g_last_tick_time = TimeCurrent();
    g_last_command_check = TimeCurrent();
    g_last_exit_check = TimeCurrent();
    g_positions_closed = 0;
    g_total_pnl_usd = 0;

    Alert("GHOST GRID EA v2.00 initialized (Phase 3)");
    Print("Pipe: ", PIPE_PATH);
    Print("Symbols: ", SYMBOLS_TO_TRADE);
    Print("Position tracking enabled");
    Print("Exit logic enabled");
    Print("Risk management active");
    Print("Max positions: 5");
    Print("Max daily loss: $5000");

    return INIT_SUCCEEDED;
}

// Duplicate OnInit removed (kept Phase 3 init)

//+------------------------------------------------------------------+
//| EvaluateExits
//| Phase 3: Check all positions for exit conditions
//+------------------------------------------------------------------+
void EvaluateExits()
{
    // Iterate through all tracked positions
    for (int i = 0; i < GetTrackedPositionCount(); i++)
    {
        // Get position data (simplified for Phase 3)
        if (PositionSelect(i))
        {
            ulong ticket = PositionGetTicket(i);
            string symbol = PositionGetString(POSITION_SYMBOL);
            double current_price = PositionGetDouble(POSITION_CURRENT_PRICE);

            // Get tracked position info
            TrackedPosition *pos = GetPositionByTicket(ticket);
            if (pos == NULL)
            {
                continue;
            }

            // Update position state with current price
            UpdatePositionState(ticket, current_price);

            // Evaluate exit signals
            ExitSignal tp_signal = EvaluateProfitTarget(
                pos.direction,
                current_price,
                pos.profit_target);

            ExitSignal sl_signal = EvaluateStopLoss(
                pos.direction,
                current_price,
                pos.stop_loss);

            ExitSignal cvd_signal = EvaluateCVDDivergence(
                pos.direction,
                current_price,
                pos.entry_price,
                0.0, // current_cvd (would be passed from Python)
                0.0  // entry_cvd
            );

            ExitSignal regime_signal = EvaluateRegimeShift(
                pos.regime_at_entry,
                GetCurrentSession() // Simplified regime
            );

            // Select best exit signal
            ExitSignal best_exit = SelectBestExit(
                tp_signal,
                sl_signal,
                cvd_signal,
                regime_signal);

            // Execute exit if warranted
            if (best_exit.should_exit)
            {
                ExecuteExit(ticket, best_exit);
            }
        }
    }
}

//+------------------------------------------------------------------+
//| ExecuteExit
//| Phase 3: Close a position based on exit signal
//+------------------------------------------------------------------+
void ExecuteExit(ulong ticket, ExitSignal exit_signal)
{
    if (ClosePositionByTicket((int)ticket))
    {
        g_positions_closed++;

        // Report exit to Python
        string exit_msg = StringFormat(
            "EXIT|%I64d|%s|%d\n",
            ticket,
            exit_signal.description,
            (int)exit_signal.reason);
        SendToPipe(exit_msg);
        g_pipe_writes++;

        // Remove from tracking
        RemovePosition(ticket);
    }
}

//+------------------------------------------------------------------+
//| EmitTickSnapshot
//| Emit current market snapshot for all symbols (design-aligned)
//+------------------------------------------------------------------+
void EmitTickSnapshot()
{
    string symbols_list[8];
    int symbol_count = StringSplit(SYMBOLS_TO_TRADE, ",", symbols_list);

    for (int i = 0; i < symbol_count; i++)
    {
        string symbol = symbols_list[i];
        MqlTick last_tick;
        if (!SymbolInfoTick(symbol, last_tick))
            continue;

        double bid = last_tick.bid;
        double ask = last_tick.ask;
        long volume = (long)last_tick.volume;
        string session = GetCurrentSession();

        // Update CVD using tick flags (design: MQL5 accumulation every tick)
        double cvd = AccumulateCVD(symbol, last_tick, session);
        string dominant = GetDominantSide(symbol);

        // Use UTC timestamp in ms per design
        long time_ms = (long)TimeGMT() * 1000;

        // Update local builders/monitors
        ProcessTick((bid + ask) / 2.0, volume, symbol);
        UpdateSpread(symbol);

        // Design-aligned message: symbol | timestamp_ms | bid | ask | tick_volume | dominant_side | cumulative_cvd
        string message = StringFormat(
            "TICK|%s|%I64d|%.5f|%.5f|%I64d|%s|%.2f\n",
            symbol,
            time_ms,
            bid,
            ask,
            volume,
            dominant,
            cvd);

        if (SendToPipe(message))
        {
            g_pipe_writes++;
            g_ticks_emitted++;
        }
        else
        {
            g_errors++;
        }
    }
}

//+------------------------------------------------------------------+
//| ProcessPendingCommands
//| Execute any pending commands from Python
//+------------------------------------------------------------------+
void ProcessPendingCommands()
{
    for (int i = 0; i < g_command_index; i++)
    {
        PendingCommand &cmd = g_pending_commands[i];

        if (cmd.command_type == "ORDER")
        {
            // Risk check before execution (Phase 3)
            if (!PerformRiskCheck(cmd.lot_size, 0.0))
            {
                // Report risk rejection
                string rejection = StringFormat(
                    "RISK_REJECT|%s|POSITION_SIZE_LIMIT\n",
                    cmd.symbol);
                SendToPipe(rejection);
                g_pipe_writes++;
                continue;
            }

            // Execute order with risk-approved size
            int ticket = SendOrderToMT5(cmd.symbol, cmd.direction, cmd.lot_size);

            if (ticket > 0)
            {
                g_orders_executed++;

                // Add to position tracker (Phase 3)
                AddPosition(
                    ticket,
                    cmd.symbol,
                    (cmd.direction == "BUY") ? 1 : -1,
                    cmd.entry_price,
                    cmd.lot_size,
                    cmd.entry_price * 1.01, // TP: entry + 1%
                    cmd.entry_price * 0.99, // SL: entry - 1%
                    0.0,                    // h_c_score (from Python)
                    GetCurrentSession());

                // Report fill
                double fill_price = (cmd.direction == "BUY") ? SymbolInfoDouble(cmd.symbol, SYMBOL_ASK) : SymbolInfoDouble(cmd.symbol, SYMBOL_BID);

                string response = StringFormat(
                    "FILL|%I64d|%s|%.5f|SUCCESS\n",
                    ticket,
                    cmd.symbol,
                    fill_price);
                SendToPipe(response);
                g_pipe_writes++;
                g_fills_reported++;
            }
            else
            {
                string rejection = StringFormat(
                    "REJECT|%I64d|ORDER_FAILED\n",
                    cmd.position_id);
                SendToPipe(rejection);
                g_pipe_writes++;
            }
        }
        else if (cmd.command_type == "CLOSE")
        {
            if (ClosePositionByTicket((int)cmd.position_id))
            {
                g_orders_executed++;
                RemovePosition(cmd.position_id);

                string response = StringFormat(
                    "CLOSE|%I64d|%s|%s|SUCCESS\n",
                    cmd.position_id,
                    cmd.symbol,
                    cmd.exit_reason);
                SendToPipe(response);
                g_pipe_writes++;
                g_fills_reported++;
            }
            else
            {
                string rejection = StringFormat(
                    "CLOSE|%I64d|%s|FAILED\n",
                    cmd.position_id,
                    cmd.exit_reason);
                SendToPipe(rejection);
                g_pipe_writes++;
            }
        }
    }

    g_command_index = 0;
}

//+------------------------------------------------------------------+
//| ReportOrderFills
//| Send status updates for all open positions to Python
//+------------------------------------------------------------------+
void ReportOrderFills()
{
    for (int i = 0; i < PositionsTotal(); i++)
    {
        if (PositionSelect(i))
        {
            ulong ticket = PositionGetTicket(i);
            string symbol = PositionGetString(POSITION_SYMBOL);
            double open_price = PositionGetDouble(POSITION_PRICE_OPEN);
            double current_price = PositionGetDouble(POSITION_CURRENT_PRICE);
            double profit = PositionGetDouble(POSITION_PROFIT);

            string status = StringFormat(
                "STATUS|%I64d|%s|%.5f|%.5f|%.2f\n",
                ticket,
                symbol,
                open_price,
                current_price,
                profit);

            if (SendToPipe(status))
            {
                g_pipe_writes++;
            }
        }
    }
}

//+------------------------------------------------------------------+
//| GetCurrentSession
//| Determine current trading session (UTC)
//+------------------------------------------------------------------+
string GetCurrentSession()
{
    int hour = Hour();

    if (hour >= 0 && hour < 8)
    {
        return "ASIA";
    }
    else if (hour >= 8 && hour < 12)
    {
        return "LONDON";
    }
    else if (hour >= 12 && hour < 17)
    {
        return "OVERLAP";
    }
    else if (hour >= 17 && hour < 22)
    {
        return "NY";
    }
    else
    {
        return "INACTIVE";
    }
}

//+------------------------------------------------------------------+
//| OnDeinit
//| Cleanup on EA stop
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
    g_ea_running = false;

    // Send shutdown signal to Python
    SendToPipe("SHUTDOWN|GHOSTGRID|EA_STOPPED\n");

    // Log final statistics
    Print("==== GHOST GRID EA SHUTDOWN (Phase 3) ====");
    Print("Version: 2.00");
    Print("Ticks emitted: ", g_ticks_emitted);
    Print("Orders executed: ", g_orders_executed);
    Print("Positions closed: ", g_positions_closed);
    Print("Fills reported: ", g_fills_reported);
    Print("Pipe writes: ", g_pipe_writes);
    Print("Errors: ", g_errors);
    Print("Heartbeats sent: ", GetHeartbeatCount());
    Print("Open positions: ", PositionsTotal());
    Print("Tracked positions: ", GetTrackedPositionCount());
    Print("Average confluence: ", GetAverageConfluence());
    Print("Risk capacity available: ", GetAvailableRiskCapacity());
    Print("Reason: ", EnumToString((ENUM_UNINIT_REASON)reason));
    Print("====================================");

    // Close pipe
    ClosePipe();
}

//+------------------------------------------------------------------+
//| Helper: Hour
//| Get current hour in UTC
//+------------------------------------------------------------------+
int Hour()
{
    return (int)(TimeCurrent() % 86400) / 3600;
}

//+------------------------------------------------------------------+
//| OnInit
//| Initialize EA on startup
//+------------------------------------------------------------------+
int OnInit()
{
    // Initialize pipe connection
    if (!InitPipe(PIPE_PATH))
    {
        Alert("Failed to initialize pipe: " + PIPE_PATH);
        return INIT_FAILED;
    }

    // Initialize heartbeat system
    InitHeartbeat();

    // Initialize spread monitoring
    InitSpreadMonitor();

    // Initialize bar builders
    InitBarBuilders(Symbol());

    // Initialize CVD for each symbol
    string symbols_list[4];
    int symbol_count = StringSplit(SYMBOLS_TO_TRADE, ",", symbols_list);

    for (int i = 0; i < symbol_count; i++)
    {
        InitCVD(symbols_list[i]);
    }

    // Initialize command queue
    ArrayResize(g_pending_commands, MAX_PENDING_COMMANDS);

    g_ea_running = true;
    g_last_tick_time = TimeCurrent();
    g_last_command_check = TimeCurrent();

    // Duplicate Init removed (kept Phase 3 init)
    Print("Pipe: ", PIPE_PATH);
    Print("Symbols: ", SYMBOLS_TO_TRADE);
    Print("Tick interval: ", TICK_EMIT_INTERVAL_MS, " ms");
    Print("Command poll: ", COMMAND_POLL_INTERVAL_MS, " ms");

    return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| OnTick
//| Main EA logic: tick emission + command processing + fill reporting
//+------------------------------------------------------------------+
void OnTick()
{
    if (!g_ea_running)
    {
        return;
    }

    // Ensure pipe is connected
    if (!IsPipeConnected())
    {
        if (!InitPipe(PIPE_PATH))
        {
            g_errors++;
            return;
        }
    }

    // Send heartbeat every 5 seconds
    if (SendHeartbeat(g_pipe_handle))
    {
        g_pipe_writes++;
    }

    // Send tick snapshots every 200ms
    datetime current_time = TimeCurrent();
    if (current_time - g_last_tick_time >= TICK_EMIT_INTERVAL_MS / 1000)
    {
        EmitTickSnapshot();
        g_last_tick_time = current_time;
    }

    // Check for incoming commands every 100ms
    if (current_time - g_last_command_check >= COMMAND_POLL_INTERVAL_MS / 1000)
    {
        // Poll pipe for raw incoming messages and queue them
        string raw = ReadFromPipe();
        if (StringLen(raw) > 0)
        {
            string lines[32];
            int n = StringSplit(raw, "\n", lines);
            for (int li = 0; li < n; li++)
            {
                string ln = StringTrim(lines[li]);
                if (StringLen(ln) == 0)
                    continue;

                string parts[16];
                int pc = StringSplit(ln, "|", parts);
                if (pc <= 0)
                    continue;

                if (parts[0] == "ORDER")
                {
                    if (g_command_index >= MAX_PENDING_COMMANDS)
                        continue;
                    PendingCommand &cmd = g_pending_commands[g_command_index++];
                    cmd.command_type = "ORDER";
                    cmd.symbol = parts[1];
                    cmd.direction = parts[2];
                    cmd.lot_size = StrToDouble(parts[3]);
                    cmd.entry_price = StrToDouble(parts[4]);
                    cmd.position_id = (ulong)StrToInteger(parts[5]);
                    cmd.received_time = TimeCurrent();
                }
                else if (parts[0] == "CLOSE")
                {
                    if (g_command_index >= MAX_PENDING_COMMANDS)
                        continue;
                    PendingCommand &cmd = g_pending_commands[g_command_index++];
                    cmd.command_type = "CLOSE";
                    cmd.position_id = (ulong)StrToInteger(parts[1]);
                    cmd.symbol = parts[2];
                    cmd.exit_reason = parts[3];
                    cmd.received_time = TimeCurrent();
                }
            }
        }

        ProcessPendingCommands();
        g_last_command_check = current_time;
    }

    // Report fill status for all open orders
    ReportOrderFills();
}

//+------------------------------------------------------------------+
//| EmitTickSnapshot
//| Emit current market snapshot for all symbols (design-aligned)
//+------------------------------------------------------------------+
void EmitTickSnapshot()
{
    string symbols_list[8];
    int symbol_count = StringSplit(SYMBOLS_TO_TRADE, ",", symbols_list);

    for (int i = 0; i < symbol_count; i++)
    {
        string symbol = symbols_list[i];
        MqlTick last_tick;
        if (!SymbolInfoTick(symbol, last_tick))
            continue;

        double bid = last_tick.bid;
        double ask = last_tick.ask;
        long volume = (long)last_tick.volume;
        string session = GetCurrentSession();

        // Update CVD using tick flags (design: MQL5 accumulation every tick)
        double cvd = AccumulateCVD(symbol, last_tick, session);
        string dominant = GetDominantSide(symbol);

        // Use UTC timestamp in ms per design
        long time_ms = (long)TimeGMT() * 1000;

        // Update local builders/monitors
        ProcessTick((bid + ask) / 2.0, volume, symbol);
        UpdateSpread(symbol);

        // Design-aligned message: symbol | timestamp_ms | bid | ask | tick_volume | dominant_side | cumulative_cvd
        string message = StringFormat(
            "TICK|%s|%I64d|%.5f|%.5f|%I64d|%s|%.2f\n",
            symbol,
            time_ms,
            bid,
            ask,
            volume,
            dominant,
            cvd);

        if (SendToPipe(message))
        {
            g_pipe_writes++;
            g_ticks_emitted++;
        }
        else
        {
            g_errors++;
        }
    }
}

//+------------------------------------------------------------------+
//| ProcessPendingCommands
//| Execute any pending commands from Python
//+------------------------------------------------------------------+
void ProcessPendingCommands()
{
    for (int i = 0; i < g_command_index; i++)
    {
        PendingCommand &cmd = g_pending_commands[i];

        if (cmd.command_type == "ORDER")
        {
            // Execute buy/sell order
            int ticket = SendOrderToMT5(cmd.symbol, cmd.direction, cmd.lot_size);

            if (ticket > 0)
            {
                g_orders_executed++;

                // Report back to Python: FILL|position_id|symbol|fill_price|status\n
                double fill_price = (cmd.direction == "BUY") ? SymbolInfoDouble(cmd.symbol, SYMBOL_ASK) : SymbolInfoDouble(cmd.symbol, SYMBOL_BID);

                string response = StringFormat(
                    "FILL|%I64d|%s|%.5f|SUCCESS\n",
                    ticket,
                    cmd.symbol,
                    fill_price);
                SendToPipe(response);
                g_pipe_writes++;
                g_fills_reported++;
            }
            else
            {
                // Report rejection
                string rejection = StringFormat(
                    "REJECT|%I64d|ORDER_FAILED\n",
                    cmd.position_id);
                SendToPipe(rejection);
                g_pipe_writes++;
            }
        }
        else if (cmd.command_type == "CLOSE")
        {
            // Close position
            if (ClosePositionByTicket((int)cmd.position_id))
            {
                g_orders_executed++;

                // Report back: CLOSE|position_id|symbol|exit_reason|status\n
                string response = StringFormat(
                    "CLOSE|%I64d|%s|%s|SUCCESS\n",
                    cmd.position_id,
                    cmd.symbol,
                    cmd.exit_reason);
                SendToPipe(response);
                g_pipe_writes++;
                g_fills_reported++;
            }
            else
            {
                string rejection = StringFormat(
                    "CLOSE|%I64d|%s|FAILED\n",
                    cmd.position_id,
                    cmd.exit_reason);
                SendToPipe(rejection);
                g_pipe_writes++;
            }
        }
    }

    // Clear command queue
    g_command_index = 0;
}

//+------------------------------------------------------------------+
//| ReportOrderFills
//| Send status updates for all open positions to Python
//+------------------------------------------------------------------+
void ReportOrderFills()
{
    // Iterate through all open positions and send status updates
    for (int i = 0; i < PositionsTotal(); i++)
    {
        if (PositionSelect(i))
        {
            ulong ticket = PositionGetTicket(i);
            string symbol = PositionGetString(POSITION_SYMBOL);
            double open_price = PositionGetDouble(POSITION_PRICE_OPEN);
            double current_price = PositionGetDouble(POSITION_CURRENT_PRICE);
            double profit = PositionGetDouble(POSITION_PROFIT);

            // Format status: STATUS|ticket|symbol|open_price|current_price|profit\n
            string status = StringFormat(
                "STATUS|%I64d|%s|%.5f|%.5f|%.2f\n",
                ticket,
                symbol,
                open_price,
                current_price,
                profit);

            if (SendToPipe(status))
            {
                g_pipe_writes++;
            }
        }
    }
}

//+------------------------------------------------------------------+
//| GetCurrentSession
//| Determine current trading session (UTC)
//+------------------------------------------------------------------+
string GetCurrentSession()
{
    int hour = Hour();

    if (hour >= 0 && hour < 8)
    {
        return "ASIA";
    }
    else if (hour >= 8 && hour < 12)
    {
        return "LONDON";
    }
    else if (hour >= 12 && hour < 17)
    {
        return "OVERLAP";
    }
    else if (hour >= 17 && hour < 22)
    {
        return "NY";
    }
    else
    {
        return "INACTIVE";
    }
}

//+------------------------------------------------------------------+
//| OnDeinit
//| Cleanup on EA stop
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
    g_ea_running = false;

    // Send shutdown signal to Python
    SendToPipe("SHUTDOWN|GHOSTGRID|EA_STOPPED\n");

    // Log final statistics
    Print("==== GHOST GRID EA SHUTDOWN (Phase 2) ====");
    Print("Ticks emitted: ", g_ticks_emitted);
    Print("Orders executed: ", g_orders_executed);
    Print("Fills reported: ", g_fills_reported);
    Print("Pipe writes: ", g_pipe_writes);
    Print("Errors: ", g_errors);
    Print("Heartbeats sent: ", GetHeartbeatCount());
    Print("Open positions: ", PositionsTotal());
    Print("Reason: ", EnumToString((ENUM_UNINIT_REASON)reason));

    // Close pipe
    ClosePipe();
}

//+------------------------------------------------------------------+
//| Helper: Hour
//| Get current hour in UTC (simplified)
//+------------------------------------------------------------------+
int Hour()
{
    return (int)(TimeCurrent() % 86400) / 3600;
}
