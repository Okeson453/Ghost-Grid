//+------------------------------------------------------------------+
//| GhostGrid.mq5
//| GHOST GRID algorithmic trading EA — Consolidated Phase 3
//| PURPOSE: Tick emission + trade execution + position management
//+------------------------------------------------------------------+

#property copyright "GHOST GRID"
#property link "https://github.com/Okeson453/Ghost-Grid"
#property version "2.00"
#property strict
#property description "Consolidated EA with dual-pipe communication"

// Include headers
#include <PipeServer.mqh>
#include <Heartbeat.mqh>
#include <CVDAccumulator.mqh>
#include <OHLCVBuilder.mqh>
#include <OrderExecutor.mqh>
#include <SpreadMonitor.mqh>
#include <PositionTracker.mqh>
#include <ExitLogic.mqh>
#include <RiskManager.mqh>

// Configuration
#define PIPE_PATH "\\\\.\\pipe\\ghostgrid"
#define TICK_EMIT_INTERVAL_MS 200
#define COMMAND_POLL_INTERVAL_MS 100
#define SYMBOLS_TO_TRADE "EURUSD,GBPUSD,USDJPY,XAUUSD"
#define EXIT_CHECK_INTERVAL_MS 500

// Phase 2/3: Command processing
#define MAX_PENDING_COMMANDS 100
struct PendingCommand
{
    string command_type; // "ORDER" or "CLOSE"
    string symbol;
    string direction;
    double lot_size;
    double entry_price;
    double stop_loss;   // optional, can be 0
    double take_profit; // optional, can be 0
    ulong position_id;
    string exit_reason;
    datetime received_time;
};

static PendingCommand g_pending_commands[];
static int g_command_index = 0;

// Phase 3: Exit tracking
static datetime g_last_exit_check = 0;
static ulong g_positions_closed = 0;
static double g_total_pnl_usd = 0.0;

// Global state
static datetime g_last_tick_time = 0;
static datetime g_last_command_check = 0;
static ulong g_ticks_emitted = 0;
static ulong g_pipe_writes = 0;
static ulong g_orders_executed = 0;
static ulong g_fills_reported = 0;
static int g_errors = 0;
static bool g_ea_running = false;

// Forward declarations
string GetCurrentSession();
int Hour();

//+------------------------------------------------------------------+
//| EvaluateExits
//+------------------------------------------------------------------+
void EvaluateExits()
{
    for (int i = 0; i < GetTrackedPositionCount(); i++)
    {
        TrackedPosition *pos = GetTrackedPositionByIndex(i);
        if (pos == NULL)
            continue;

        double current_price = SymbolInfoDouble(pos.symbol, (pos.direction == 1) ? SYMBOL_BID : SYMBOL_ASK);
        UpdatePositionState(pos.ticket, current_price);

        ExitSignal tp_signal = EvaluateProfitTarget(pos.direction, current_price, pos.profit_target);
        ExitSignal sl_signal = EvaluateStopLoss(pos.direction, current_price, pos.stop_loss);
        ExitSignal cvd_signal = EvaluateCVDDivergence(pos.direction, current_price, pos.entry_price, GetCVD(pos.symbol), pos.entry_cvd);
        ExitSignal regime_signal = EvaluateRegimeShift(pos.regime_at_entry, GetCurrentSession());

        ExitSignal best_exit = SelectBestExit(tp_signal, sl_signal, cvd_signal, regime_signal);
        if (best_exit.should_exit)
        {
            ExecuteExit(pos.ticket, best_exit);
        }
    }
}

//+------------------------------------------------------------------+
//| ExecuteExit
//+------------------------------------------------------------------+
void ExecuteExit(ulong ticket, ExitSignal exit_signal)
{
    if (ClosePositionByTicket((int)ticket))
    {
        g_positions_closed++;

        string exit_msg = StringFormat("EXIT|%I64d|%s|%d\n", ticket, exit_signal.description, (int)exit_signal.reason);
        SendToPipe(exit_msg);
        g_pipe_writes++;

        RemovePosition(ticket);
    }
}

//+------------------------------------------------------------------+
//| EmitTickSnapshot
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

        double cvd = AccumulateCVD(symbol, last_tick, session);
        string dominant = GetDominantSide(symbol);

        long time_ms = (long)TimeGMT() * 1000;

        ProcessTick((bid + ask) / 2.0, volume, symbol);
        UpdateSpread(symbol);

        string message = StringFormat("TICK|%s|%I64d|%.5f|%.5f|%I64d|%s|%.2f\n", symbol, time_ms, bid, ask, volume, dominant, cvd);

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
//+------------------------------------------------------------------+
void ProcessPendingCommands()
{
    for (int i = 0; i < g_command_index; i++)
    {
        PendingCommand &cmd = g_pending_commands[i];

        if (cmd.command_type == "ORDER")
        {
            if (!PerformRiskCheck(cmd.lot_size, 0.0))
            {
                string rejection = StringFormat("RISK_REJECT|%s|POSITION_SIZE_LIMIT\n", cmd.symbol);
                SendToPipe(rejection);
                g_pipe_writes++;
                continue;
            }

            int ticket = SendOrderToMT5(cmd.symbol, cmd.direction, cmd.lot_size);

            if (ticket > 0)
            {
                g_orders_executed++;

                double tp = cmd.take_profit;
                double sl = cmd.stop_loss;
                if (tp <= 0.0)
                    tp = cmd.entry_price * 1.01; // default 1%
                if (sl <= 0.0)
                    sl = cmd.entry_price * 0.99; // default 1%

                AddPosition(ticket, cmd.symbol, (cmd.direction == "BUY") ? 1 : -1, cmd.entry_price, cmd.lot_size, tp, sl, 0.0, GetCurrentSession());

                double fill_price = (cmd.direction == "BUY") ? SymbolInfoDouble(cmd.symbol, SYMBOL_ASK) : SymbolInfoDouble(cmd.symbol, SYMBOL_BID);
                string response = StringFormat("FILL|%I64d|%s|%.5f|SUCCESS\n", ticket, cmd.symbol, fill_price);
                SendToPipe(response);
                g_pipe_writes++;
                g_fills_reported++;
            }
            else
            {
                string rejection = StringFormat("REJECT|%I64d|ORDER_FAILED\n", cmd.position_id);
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
                string response = StringFormat("CLOSE|%I64d|%s|%s|SUCCESS\n", cmd.position_id, cmd.symbol, cmd.exit_reason);
                SendToPipe(response);
                g_pipe_writes++;
                g_fills_reported++;
            }
            else
            {
                string rejection = StringFormat("CLOSE|%I64d|%s|FAILED\n", cmd.position_id, cmd.exit_reason);
                SendToPipe(rejection);
                g_pipe_writes++;
            }
        }
    }

    // clear
    g_command_index = 0;
}

//+------------------------------------------------------------------+
//| ReportOrderFills
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

            string status = StringFormat("STATUS|%I64d|%s|%.5f|%.5f|%.2f\n", ticket, symbol, open_price, current_price, profit);

            if (SendToPipe(status))
                g_pipe_writes++;
        }
    }
}

//+------------------------------------------------------------------+
//| GetCurrentSession / Hour
//+------------------------------------------------------------------+
string GetCurrentSession()
{
    int hour = Hour();
    if (hour >= 0 && hour < 8)
        return "ASIA";
    if (hour >= 8 && hour < 12)
        return "LONDON";
    if (hour >= 12 && hour < 17)
        return "OVERLAP";
    if (hour >= 17 && hour < 22)
        return "NY";
    return "INACTIVE";
}

int Hour()
{
    return (int)(TimeCurrent() % 86400) / 3600;
}

//+------------------------------------------------------------------+
//| OnInit
//+------------------------------------------------------------------+
int OnInit()
{
    if (!InitPipe(PIPE_PATH))
    {
        Alert("Failed to initialize pipe: " + PIPE_PATH);
        return INIT_FAILED;
    }

    InitHeartbeat();
    InitSpreadMonitor();
    InitBarBuilders(Symbol());
    InitPositionTracker();

    string symbols_list[8];
    int symbol_count = StringSplit(SYMBOLS_TO_TRADE, ",", symbols_list);
    for (int i = 0; i < symbol_count; i++)
        InitCVD(symbols_list[i]);

    ArrayResize(g_pending_commands, MAX_PENDING_COMMANDS);

    g_ea_running = true;
    g_last_tick_time = TimeCurrent();
    g_last_command_check = TimeCurrent();
    g_last_exit_check = TimeCurrent();

    Print("GHOST GRID EA v2.00 initialized");
    Print("Pipe: ", PIPE_PATH);
    Print("Symbols: ", SYMBOLS_TO_TRADE);

    return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| OnTick
//+------------------------------------------------------------------+
void OnTick()
{
    if (!g_ea_running)
        return;

    if (!IsPipeConnected())
    {
        if (!InitPipe(PIPE_PATH))
        {
            g_errors++;
            return;
        }
    }

    if (SendHeartbeat(g_pipe_handle))
        g_pipe_writes++;

    datetime current_time = TimeCurrent();
    if (current_time - g_last_tick_time >= TICK_EMIT_INTERVAL_MS / 1000)
    {
        EmitTickSnapshot();
        g_last_tick_time = current_time;
    }

    if (current_time - g_last_command_check >= COMMAND_POLL_INTERVAL_MS / 1000)
    {
        string raw = ReadFromPipe();
        if (StringLen(raw) > 0)
        {
            string lines[64];
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
                    // Allow optional SL/TP: parts[5]=stop_loss, parts[6]=take_profit, parts[7]=position_id
                    if (pc >= 6)
                        cmd.stop_loss = StrToDouble(parts[5]);
                    else
                        cmd.stop_loss = 0.0;
                    if (pc >= 7)
                        cmd.take_profit = StrToDouble(parts[6]);
                    else
                        cmd.take_profit = 0.0;
                    if (pc >= 8)
                        cmd.position_id = (ulong)StrToInteger(parts[7]);
                    else
                        cmd.position_id = 0;
                    cmd.received_time = TimeCurrent();
                }
                else if (parts[0] == "RISK_CONFIG")
                {
                    if (pc >= 6)
                    {
                        g_risk_config.risk_per_trade_pct = StrToDouble(parts[1]);
                        g_risk_config.max_daily_loss_pct = StrToDouble(parts[2]);
                        g_risk_config.max_concurrent = (int)StrToInteger(parts[3]);
                        g_risk_config.max_spread_pct = StrToDouble(parts[4]);
                        g_risk_config.margin_buffer = StrToDouble(parts[5]);
                        InitRiskManager(g_risk_config);
                        Print("Applied RISK_CONFIG from Python");
                    }
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

    // Periodically evaluate exits
    if (TimeCurrent() - g_last_exit_check >= EXIT_CHECK_INTERVAL_MS / 1000)
    {
        EvaluateExits();
        g_last_exit_check = TimeCurrent();
    }

    ReportOrderFills();
}

//+------------------------------------------------------------------+
//| OnDeinit
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
    g_ea_running = false;
    SendToPipe("SHUTDOWN|GHOSTGRID|EA_STOPPED\n");

    Print("==== GHOST GRID EA SHUTDOWN ====");
    Print("Ticks emitted: ", g_ticks_emitted);
    Print("Orders executed: ", g_orders_executed);
    Print("Positions closed: ", g_positions_closed);
    Print("Fills reported: ", g_fills_reported);
    Print("Pipe writes: ", g_pipe_writes);
    Print("Errors: ", g_errors);
    Print("Heartbeats sent: ", GetHeartbeatCount());
    Print("Open positions: ", PositionsTotal());

    ClosePipe();
}
