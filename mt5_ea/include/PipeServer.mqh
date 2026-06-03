//+------------------------------------------------------------------+
//| PipeServer.mqh
//| Named pipe communication wrapper for GHOST GRID EA
//| WHY: Encapsulates pipe I/O for tick sending and command receiving
//+------------------------------------------------------------------+

#ifndef __PIPE_SERVER_MQH__
#define __PIPE_SERVER_MQH__

// Pipe handle and configuration
static int g_pipe_handle = INVALID_HANDLE;
static string g_pipe_path = "\\\\.\\pipe\\ghostgrid";
static bool g_pipe_connected = false;
static int g_pipe_errors = 0;


//+------------------------------------------------------------------+
//| InitPipe
//| Open and initialize named pipe connection
//+------------------------------------------------------------------+
bool InitPipe(string pipe_path = "") {
    // Use provided path or default
    if (StringLen(pipe_path) > 0) {
        g_pipe_path = pipe_path;
    }
    
    // Create/open pipe for writing
    g_pipe_handle = FileOpen(g_pipe_path, FILE_WRITE | FILE_BIN);
    
    if (g_pipe_handle == INVALID_HANDLE) {
        Alert("Failed to open pipe: " + g_pipe_path);
        g_pipe_errors++;
        return false;
    }
    
    g_pipe_connected = true;
    return true;
}


//+------------------------------------------------------------------+
//| ClosePipe
//| Close pipe connection
//+------------------------------------------------------------------+
void ClosePipe() {
    if (g_pipe_handle != INVALID_HANDLE) {
        FileClose(g_pipe_handle);
        g_pipe_handle = INVALID_HANDLE;
    }
    g_pipe_connected = false;
}


//+------------------------------------------------------------------+
//| SendToP pipe
//| Send a message to the pipe
//| Returns: true if successful
//+------------------------------------------------------------------+
bool SendToPipe(string message) {
    if (g_pipe_handle == INVALID_HANDLE || !g_pipe_connected) {
        if (!InitPipe()) {
            g_pipe_errors++;
            return false;
        }
    }
    
    // Ensure message ends with newline
    if (StringFind(message, "\n") != StringLen(message) - 1) {
        message += "\n";
    }
    
    // Write to pipe
    bool result = FileWriteString(g_pipe_handle, message);
    
    if (!result) {
        g_pipe_errors++;
        g_pipe_connected = false;
        return false;
    }
    
    return true;
}


//+------------------------------------------------------------------+
//| ReadFromPipe
//| Read a single message line from pipe (non-blocking)
//| Returns: message string or empty if no data available
//+------------------------------------------------------------------+
string ReadFromPipe() {
    // In MQL5, named pipes are write-only in typical EA usage
    // Reading would require a separate file handle in read mode
    // For Phase 1, commands are sent via a separate mechanism (e.g., file polling)
    // This function is a placeholder for Phase 2 bidirectional communication
    return "";
}


//+------------------------------------------------------------------+
//| IsPipeConnected
//| Check if pipe is connected
//+------------------------------------------------------------------+
bool IsPipeConnected() {
    return g_pipe_connected && g_pipe_handle != INVALID_HANDLE;
}


//+------------------------------------------------------------------+
//| GetPipeErrors
//| Get total pipe errors
//+------------------------------------------------------------------+
int GetPipeErrors() {
    return g_pipe_errors;
}


//+------------------------------------------------------------------+
//| ResetPipeErrors
//| Reset error counter
//+------------------------------------------------------------------+
void ResetPipeErrors() {
    g_pipe_errors = 0;
}

#endif
