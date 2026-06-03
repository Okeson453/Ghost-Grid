//+------------------------------------------------------------------+
//| Heartbeat.mqh
//| Keepalive signal sender for GHOST GRID EA
//| WHY: Detects EA crashes/hangs on VPS by periodic signal to Python
//+------------------------------------------------------------------+

#ifndef __HEARTBEAT_MQH__
#define __HEARTBEAT_MQH__

// Heartbeat configuration
#define PIPE_HEARTBEAT_INTERVAL_S 5  // Send heartbeat every 5 seconds
#define HEARTBEAT_VERSION "V1"

// Global heartbeat state
static datetime g_last_heartbeat_time = 0;
static ulong g_heartbeat_count = 0;


//+------------------------------------------------------------------+
//| SendHeartbeat
//| Send keepalive signal: V1|HEARTBEAT|{timestamp_ms}\n
//| Returns: true if sent, false if interval not elapsed
//+------------------------------------------------------------------+
bool SendHeartbeat(int pipe_handle) {
    datetime current_time = TimeCurrent();
    
    // Check if enough time has elapsed
    if (current_time - g_last_heartbeat_time < PIPE_HEARTBEAT_INTERVAL_S) {
        return false;
    }
    
    // Build heartbeat message
    string message = StringFormat(
        "%s|HEARTBEAT|%lld\n",
        HEARTBEAT_VERSION,
        (long)current_time * 1000  // Convert to milliseconds
    );
    
    // Write to pipe
    bool result = FileWriteString(pipe_handle, message);
    
    if (result) {
        g_last_heartbeat_time = current_time;
        g_heartbeat_count++;
    }
    
    return result;
}


//+------------------------------------------------------------------+
//| InitHeartbeat
//| Initialize heartbeat state
//+------------------------------------------------------------------+
void InitHeartbeat() {
    g_last_heartbeat_time = TimeCurrent();
    g_heartbeat_count = 0;
}


//+------------------------------------------------------------------+
//| GetHeartbeatCount
//| Returns total heartbeats sent
//+------------------------------------------------------------------+
ulong GetHeartbeatCount() {
    return g_heartbeat_count;
}


//+------------------------------------------------------------------+
//| ResetHeartbeat
//| Reset heartbeat state (for testing)
//+------------------------------------------------------------------+
void ResetHeartbeat() {
    g_last_heartbeat_time = 0;
    g_heartbeat_count = 0;
}

#endif
