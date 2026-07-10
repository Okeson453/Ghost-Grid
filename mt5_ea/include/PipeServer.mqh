//+------------------------------------------------------------------+
//| PipeServer.mqh
//| Named pipe communication wrapper for GHOST GRID EA
//| WHY: Encapsulates pipe I/O for tick sending and command receiving
//+------------------------------------------------------------------+

#ifndef __PIPE_SERVER_MQH__
#define __PIPE_SERVER_MQH__

// Pipe handle and configuration
// Write handle (ticks / messages to Python) - preserve name for compatibility
static int g_pipe_handle = INVALID_HANDLE;
// Read handle (commands from Python)
static int g_pipe_commands_handle = INVALID_HANDLE;

// Base pipe path (without _ticks/_commands suffix)
static string g_pipe_path = "\\\\.\\pipe\\ghostgrid";
// Resolved per-direction paths
static string g_pipe_ticks_path = "\\\\.\\pipe\\ghostgrid_ticks";
static string g_pipe_commands_path = "\\\\.\\pipe\\ghostgrid_commands";

static bool g_pipe_connected = false;          // true when write handle is open
static bool g_pipe_commands_connected = false; // true when commands handle is open
static int g_pipe_errors = 0;

//+------------------------------------------------------------------+
//| InitPipe
//| Open and initialize named pipe connection
//+------------------------------------------------------------------+
// Initialize both ticks (write) and commands (read) pipes.
// Backwards-compatible InitPipe(path) will derive ticks/commands paths
bool InitPipe(string pipe_path = "")
{
    if (StringLen(pipe_path) > 0)
    {
        g_pipe_path = pipe_path;
    }

    // derive specific paths if a base was provided like "\\\\.\\pipe\\ghostgrid"
    g_pipe_ticks_path = StringConcatenate(g_pipe_path, "_ticks");
    g_pipe_commands_path = StringConcatenate(g_pipe_path, "_commands");

    // Open write pipe (ticks/messages -> Python)
    g_pipe_handle = FileOpen(g_pipe_ticks_path, FILE_WRITE | FILE_BIN | FILE_COMMON);
    if (g_pipe_handle == INVALID_HANDLE)
    {
        Alert("Failed to open ticks pipe: " + g_pipe_ticks_path);
        g_pipe_errors++;
        g_pipe_connected = false;
        return false;
    }

    // Open read pipe (commands <- Python)
    g_pipe_commands_handle = FileOpen(g_pipe_commands_path, FILE_READ | FILE_BIN | FILE_COMMON);
    if (g_pipe_commands_handle == INVALID_HANDLE)
    {
        // If commands pipe is not available, log but keep ticks pipe functional
        Alert("Warning: failed to open commands pipe: " + g_pipe_commands_path);
        g_pipe_errors++;
        g_pipe_commands_connected = false;
        // Keep running since ticks emission is critical
    }
    else
    {
        g_pipe_commands_connected = true;
    }

    g_pipe_connected = true;
    return true;
}

//+------------------------------------------------------------------+
//| ClosePipe
//| Close pipe connection
//+------------------------------------------------------------------+
void ClosePipe()
{
    if (g_pipe_handle != INVALID_HANDLE)
    {
        FileClose(g_pipe_handle);
        g_pipe_handle = INVALID_HANDLE;
    }
    if (g_pipe_commands_handle != INVALID_HANDLE)
    {
        FileClose(g_pipe_commands_handle);
        g_pipe_commands_handle = INVALID_HANDLE;
    }
    g_pipe_connected = false;
    g_pipe_commands_connected = false;
}

//+------------------------------------------------------------------+
//| SendToP pipe
//| Send a message to the pipe
//| Returns: true if successful
//+------------------------------------------------------------------+
bool SendToPipe(string message)
{
    // Ensure write pipe open
    if (g_pipe_handle == INVALID_HANDLE || !g_pipe_connected)
    {
        if (!InitPipe())
        {
            g_pipe_errors++;
            return false;
        }
    }

    // Ensure message ends with newline
    if (StringFind(message, "\n") != StringLen(message) - 1)
    {
        message += "\n";
    }

    // Write to ticks pipe (backwards-compatible name: g_pipe_handle)
    bool result = FileWriteString(g_pipe_handle, message);

    if (!result)
    {
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
string ReadFromPipe()
{
    // If commands handle isn't open, try to open it non-persistently
    if (g_pipe_commands_handle == INVALID_HANDLE || !g_pipe_commands_connected)
    {
        int fh = FileOpen(g_pipe_commands_path, FILE_READ | FILE_BIN);
        if (fh == INVALID_HANDLE)
        {
            return "";
        }

        string buffer = "";
        while (!FileIsEnding(fh))
        {
            string chunk = FileReadString(fh);
            if (StringLen(chunk) == 0)
                break;
            buffer += chunk;
        }
        FileClose(fh);

        // Trim trailing CR/LF
        while (StringLen(buffer) > 0 && (StringGetCharacter(buffer, StringLen(buffer) - 1) == 10 || StringGetCharacter(buffer, StringLen(buffer) - 1) == 13))
        {
            buffer = StringSubstr(buffer, 0, StringLen(buffer) - 1);
        }

        return buffer;
    }

    // Use persistent commands handle
    string out = "";
    while (!FileIsEnding(g_pipe_commands_handle))
    {
        string chunk = FileReadString(g_pipe_commands_handle);
        if (StringLen(chunk) == 0)
            break;
        out += chunk;
    }

    // Trim trailing CR/LF
    while (StringLen(out) > 0 && (StringGetCharacter(out, StringLen(out) - 1) == 10 || StringGetCharacter(out, StringLen(out) - 1) == 13))
    {
        out = StringSubstr(out, 0, StringLen(out) - 1);
    }

    return out;
}

//+------------------------------------------------------------------+
//| IsPipeConnected
//| Check if pipe is connected
//+------------------------------------------------------------------+
bool IsPipeConnected()
{
    return g_pipe_connected && g_pipe_handle != INVALID_HANDLE;
}

//+------------------------------------------------------------------+
//| GetPipeErrors
//| Get total pipe errors
//+------------------------------------------------------------------+
int GetPipeErrors()
{
    return g_pipe_errors;
}

//+------------------------------------------------------------------+
//| ResetPipeErrors
//| Reset error counter
//+------------------------------------------------------------------+
void ResetPipeErrors()
{
    g_pipe_errors = 0;
}

#endif
