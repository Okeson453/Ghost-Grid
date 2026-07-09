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
    // Try to open the same named pipe for reading in non-blocking fashion
    int fh = FileOpen(g_pipe_path, FILE_READ | FILE_BIN);
    if (fh == INVALID_HANDLE) {
        return "";
    }

    string buffer = "";

    while (!FileIsEnding(fh)) {
        string chunk = FileReadString(fh);
        if (StringLen(chunk) == 0) break;
        buffer += chunk;
    }

    FileClose(fh);

    // Trim any trailing newlines
    while (StringLen(buffer) > 0 && (StringGetCharacter(buffer, StringLen(buffer)-1) == 10 || StringGetCharacter(buffer, StringLen(buffer)-1) == 13)) {
        buffer = StringSubstr(buffer, 0, StringLen(buffer)-1);
    }

    return buffer;
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
