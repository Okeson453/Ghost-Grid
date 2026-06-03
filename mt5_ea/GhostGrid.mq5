//+------------------------------------------------------------------+
//| GhostGrid.mq5
//| GHOST GRID algorithmic trading EA — Phase 1 Foundation
//| PURPOSE: Emit market ticks via named pipe to Python scoring engine
//| PHASE 1: Tick emission + heartbeat + CVD accumulation (no trading)
//+------------------------------------------------------------------+

#property copyright   "GHOST GRID"
#property link        "https://github.com/Okeson453/Ghost-Grid"
#property version     "1.00"
#property strict
#property description "Tick emitter for GHOST GRID scoring engine"

// Include headers
#include <PipeServer.mqh>
#include <Heartbeat.mqh>
#include <CVDAccumulator.mqh>
#include <OHLCVBuilder.mqh>
#include <OrderExecutor.mqh>
#include <SpreadMonitor.mqh>

// Configuration
#define PIPE_PATH "\\\\.\\pipe\\ghostgrid"
#define TICK_EMIT_INTERVAL_MS 200  // Emit tick every 200ms
#define SYMBOLS_TO_TRADE "EURUSD,GBPUSD,USDJPY,XAUUSD"

// Global state
static datetime g_last_tick_time = 0;
static ulong g_ticks_emitted = 0;
static ulong g_pipe_writes = 0;
static int g_errors = 0;
static bool g_ea_running = false;


//+------------------------------------------------------------------+
//| OnInit
//| Initialize EA on startup
//+------------------------------------------------------------------+
int OnInit() {
    // Initialize pipe connection
    if (!InitPipe(PIPE_PATH)) {
        Alert("Failed to initialize pipe: " + PIPE_PATH);
        return INIT_FAILED;
    }
    
    // Initialize heartbeat system
    InitHeartbeat();
    
    // Initialize CVD for each symbol
    string symbols_list[4];
    int symbol_count = StringSplit(SYMBOLS_TO_TRADE, ",", symbols_list);
    
    for (int i = 0; i < symbol_count; i++) {
        InitCVD(symbols_list[i]);
    }
    
    g_ea_running = true;
    g_last_tick_time = TimeCurrent();
    
    Alert("GHOST GRID EA initialized successfully");
    Print("Pipe: ", PIPE_PATH);
    Print("Symbols: ", SYMBOLS_TO_TRADE);
    Print("Tick interval: ", TICK_EMIT_INTERVAL_MS, " ms");
    
    return INIT_SUCCEEDED;
}


//+------------------------------------------------------------------+
//| OnTick
//| Main EA logic: emit ticks and send heartbeats
//+------------------------------------------------------------------+
void OnTick() {
    if (!g_ea_running) {
        return;
    }
    
    // Ensure pipe is connected
    if (!IsPipeConnected()) {
        if (!InitPipe(PIPE_PATH)) {
            g_errors++;
            return;
        }
    }
    
    // Send heartbeat every 5 seconds
    if (SendHeartbeat(g_pipe_handle)) {
        g_pipe_writes++;
    }
    
    // Send tick snapshots
    datetime current_time = TimeCurrent();
    if (current_time - g_last_tick_time >= TICK_EMIT_INTERVAL_MS / 1000) {
        EmitTickSnapshot();
        g_last_tick_time = current_time;
    }
}


//+------------------------------------------------------------------+
//| EmitTickSnapshot
//| Emit current market snapshot for all symbols
//+------------------------------------------------------------------+
void EmitTickSnapshot() {
    string symbols_list[4];
    int symbol_count = StringSplit(SYMBOLS_TO_TRADE, ",", symbols_list);
    
    for (int i = 0; i < symbol_count; i++) {
        string symbol = symbols_list[i];
        
        // Build tick message: TICK|symbol|bid|ask|mid|volume|spread|time_ms\n
        double bid = SymbolInfoDouble(symbol, SYMBOL_BID);
        double ask = SymbolInfoDouble(symbol, SYMBOL_ASK);
        double mid = (bid + ask) / 2.0;
        long volume = (long)SymbolInfoInteger(symbol, SYMBOL_VOLUME);
        double spread = ask - bid;
        long time_ms = (long)TimeCurrent() * 1000;
        
        // Accumulate CVD
        string session = GetCurrentSession();
        double cvd = AccumulateCVD(symbol, bid, ask, volume, session);
        
        // Format message
        string message = StringFormat(
            "TICK|%s|%.5f|%.5f|%.5f|%I64d|%.5f|%I64d|%.2f\n",
            symbol,
            bid,
            ask,
            mid,
            volume,
            spread,
            time_ms,
            cvd
        );
        
        // Send to pipe
        if (SendToPipe(message)) {
            g_pipe_writes++;
            g_ticks_emitted++;
        } else {
            g_errors++;
        }
    }
}


//+------------------------------------------------------------------+
//| GetCurrentSession
//| Determine current trading session (UTC)
//+------------------------------------------------------------------+
string GetCurrentSession() {
    int hour = Hour();
    
    if (hour >= 0 && hour < 8) {
        return "ASIA";
    } else if (hour >= 8 && hour < 12) {
        return "LONDON";
    } else if (hour >= 12 && hour < 17) {
        return "OVERLAP";
    } else if (hour >= 17 && hour < 22) {
        return "NY";
    } else {
        return "INACTIVE";
    }
}


//+------------------------------------------------------------------+
//| OnDeinit
//| Cleanup on EA stop
//+------------------------------------------------------------------+
void OnDeinit(const int reason) {
    g_ea_running = false;
    
    // Log final statistics
    Print("==== GHOST GRID EA SHUTDOWN ====");
    Print("Ticks emitted: ", g_ticks_emitted);
    Print("Pipe writes: ", g_pipe_writes);
    Print("Errors: ", g_errors);
    Print("Heartbeats sent: ", GetHeartbeatCount());
    Print("Reason: ", EnumToString((ENUM_UNINIT_REASON)reason));
    
    // Close pipe
    ClosePipe();
}


//+------------------------------------------------------------------+
//| Helper: Hour
//| Get current hour in UTC (simplified)
//+------------------------------------------------------------------+
int Hour() {
    return (int)(TimeCurrent() % 86400) / 3600;
}
