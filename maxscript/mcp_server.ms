/*
	3ds Max MCP Server - TCP Socket v2.0
	Non-blocking TCP command server for Model Context Protocol bridge
	Supports multi-instance via slot system (ports 8765-8767)

	Usage:
		-- Slot-based (recommended):
		MCP_StartSlot 1    -- start on port 8765
		MCP_StartSlot 2    -- start on port 8766
		MCP_StopServer()   -- stop current server

		-- Direct (backward compat):
		MCP_Server = MCPServerStruct()
		MCP_Server.start()
		MCP_Server.stop()

	Protocol: JSON over TCP
	- Client connects, sends JSON + newline
	- Server executes, returns JSON + newline, closes connection
*/

-- Stop any existing server before redefining globals
if MCP_Server != undefined and MCP_Server.isRunning then
(
	try (MCP_Server.stop()) catch ()
)

global MCP_Server = undefined
global MCP_ActiveSlot = 0
global MCP_BasePort = 8765

struct MCPServerStruct
(
	timer = undefined,
	listener = undefined,
	isRunning = false,
	port = 8765,
	slot = 0,
	pid = 0,
	safeMode = true,

	-- Escape a string for safe JSON embedding
	fn escapeJsonString str =
	(
		s = str as string
		s = substituteString s "\\" "\\\\"
		s = substituteString s "\"" "\\\""
		s = substituteString s "\n" "\\n"
		s = substituteString s "\r" "\\r"
		s = substituteString s "\t" "\\t"
		s
	),

	-- Build a JSON response string
	fn buildResponse success result errorMsg =
	(
		safeResult = escapeJsonString (if result != undefined then (result as string) else "")
		safeError = escapeJsonString errorMsg
		successStr = if success then "true" else "false"

		"{" + \
			"\"success\":" + successStr + "," + \
			"\"result\":\"" + safeResult + "\"," + \
			"\"error\":\"" + safeError + "\"" + \
		"}"
	),

	-- Extract a JSON string value by key (simple parser)
	fn extractJsonValue jsonStr key =
	(
		searchKey = "\"" + key + "\""
		keyPos = findString jsonStr searchKey
		if keyPos == undefined then return ""

		colonPos = findString (substring jsonStr (keyPos + searchKey.count) -1) ":"
		if colonPos == undefined then return ""
		startPos = keyPos + searchKey.count + colonPos

		while startPos <= jsonStr.count and (jsonStr[startPos] == " " or jsonStr[startPos] == "\t") do
			startPos += 1

		if startPos > jsonStr.count then return ""

		if jsonStr[startPos] == "\"" then
		(
			pos = startPos + 1
			result = ""
			while pos <= jsonStr.count do
			(
				if jsonStr[pos] == "\\" and pos + 1 <= jsonStr.count then
				(
					nextChar = jsonStr[pos + 1]
					if nextChar == "\"" then (result += "\""; pos += 2)
					else if nextChar == "\\" then (result += "\\"; pos += 2)
					else if nextChar == "n" then (result += "\n"; pos += 2)
					else if nextChar == "r" then (result += "\r"; pos += 2)
					else if nextChar == "t" then (result += "\t"; pos += 2)
					else (result += jsonStr[pos]; pos += 1)
				)
				else if jsonStr[pos] == "\"" then
				(
					exit
				)
				else
				(
					result += jsonStr[pos]
					pos += 1
				)
			)
			return result
		)
		else
		(
			pos = startPos
			while pos <= jsonStr.count and jsonStr[pos] != "," and jsonStr[pos] != "}" do
				pos += 1
			return (trimRight (trimLeft (substring jsonStr startPos (pos - startPos))))
		)
	),

	-- Process a request and return JSON response
	fn processRequest jsonString =
	(
		response = ""

		try
		(
			command = extractJsonValue jsonString "command"
			cmdType = extractJsonValue jsonString "type"

			if cmdType == "" do cmdType = "maxscript"

			if command == "" then
			(
				return (buildResponse false undefined "Empty command")
			)

			result = undefined
			success = true
			errorMsg = ""
			savedSafeMode = safeMode

			try
			(
				if cmdType == "maxscript" then
				(
					if safeMode then
						result = safeExecute command
					else
						result = execute command
				)
				else if cmdType == "python" then
				(
					if safeMode then
					(
						success = false
						errorMsg = "Python execution blocked by safe mode"
					)
					else
					(
						python.Execute command
						result = "Python executed"
					)
				)
				else
				(
					success = false
					errorMsg = "Unknown command type: " + cmdType
				)
			)
			catch
			(
				success = false
				errorMsg = getCurrentException()
			)

			-- Restore safeMode so commands cannot tamper with it
			safeMode = savedSafeMode

			response = buildResponse success result errorMsg
		)
		catch
		(
			response = buildResponse false undefined ("Parse error: " + (getCurrentException()))
		)

		response
	),

	-- Handle a single client connection
	fn handleClient client =
	(
		try
		(
			stream = client.GetStream()
			reader = dotNetObject "System.IO.StreamReader" stream
			writer = dotNetObject "System.IO.StreamWriter" stream

			-- Read the request line
			requestLine = reader.ReadLine()

			-- Convert .NET string to MAXScript string
			requestStr = requestLine as string

			format "MCP: Received request: %\n" requestStr

			if requestStr != undefined and requestStr.count > 0 then
			(
				-- Process and send response
				responseStr = processRequest requestStr
				format "MCP: Sending response: %\n" responseStr
				writer.WriteLine responseStr
				writer.Flush()
			)
			else
			(
				format "MCP: Empty request received\n"
			)

			reader.Close()
			writer.Close()
			client.Close()
		)
		catch
		(
			format "MCP: Client error: %\n" (getCurrentException())
			try (client.Close()) catch ()
		)
	),

	-- Timer tick: check for pending connections
	fn onTick sender args =
	(
		if MCP_Server == undefined or not MCP_Server.isRunning then return()
		if MCP_Server.listener == undefined then return()

		-- Guard: only process if this tick came from the current server's timer.
		-- Orphaned timers from failed reloads will self-stop here.
		if MCP_Server.timer != sender then
		(
			try (sender.Stop(); dotNet.removeAllEventHandlers sender) catch ()
			format "MCP: Killed orphaned timer\n"
			return()
		)

		try
		(
			-- Check if there's a pending connection (non-blocking)
			local hasPending = MCP_Server.listener.Pending()
			if hasPending then
			(
				local client = MCP_Server.listener.AcceptTcpClient()
				MCP_Server.handleClient client
			)
		)
		catch
		(
			-- Listener is invalid — stop server to prevent error flood
			format "MCP: Listener error, stopping server: %\n" (getCurrentException())
			try (MCP_Server.stop()) catch ()
		)
	),

	-- Start the TCP server
	fn start =
	(
		if not isRunning then
		(
			try
			(
				-- Capture PID (two-step to avoid parser issue with chained calls)
				local proc = (dotNetClass "System.Diagnostics.Process").GetCurrentProcess()
				pid = proc.Id

				-- Create TCP listener
				ipAddress = (dotNetClass "System.Net.IPAddress").Parse "127.0.0.1"
				listener = dotNetObject "System.Net.Sockets.TcpListener" ipAddress port
				listener.Start()

				-- Create timer to poll for connections
				timer = dotNetObject "System.Windows.Forms.Timer"
				timer.Interval = 50  -- 50ms polling

				dotNet.addEventHandler timer "Tick" onTick
				timer.Start()
				isRunning = true

				local slotStr = if slot > 0 then (" slot " + slot as string) else ""
				format "MCP Server started (TCP on port %%,  PID %)\n" port slotStr pid
			)
			catch
			(
				format "MCP: Failed to start on port %: %\n" port (getCurrentException())
			)
		)
		else
		(
			format "MCP Server already running on port %\n" port
		)
	),

	-- Stop the server
	fn stop =
	(
		if isRunning then
		(
			try (timer.Stop()) catch ()
			try (dotNet.removeAllEventHandlers timer) catch ()
			try (listener.Stop()) catch ()
			isRunning = false
			timer = undefined
			listener = undefined
			local slotStr = if slot > 0 then (" slot " + slot as string) else ""
			format "MCP Server stopped (port %%)\n" port slotStr
		)
		else
		(
			-- Defensive cleanup: stop timer/listener even if isRunning was false
			try (if timer != undefined do (timer.Stop(); dotNet.removeAllEventHandlers timer; timer = undefined)) catch ()
			try (if listener != undefined do (listener.Stop(); listener = undefined)) catch ()
			format "MCP Server is not running\n"
		)
	),

	-- Restart the server
	fn restart =
	(
		stop()
		start()
	)
)

-- ============================================================
-- Slot management functions
-- ============================================================

fn MCP_StartSlot slotNum =
(
	if slotNum < 1 or slotNum > 3 then
	(
		format "MCP: Invalid slot % (must be 1-3)\n" slotNum
		return false
	)

	-- Stop existing server if running
	if MCP_Server != undefined and MCP_Server.isRunning then
		MCP_Server.stop()

	-- Create new server on slot's port
	MCP_Server = MCPServerStruct()
	MCP_Server.slot = slotNum
	MCP_Server.port = MCP_BasePort + slotNum - 1
	MCP_Server.start()
	MCP_ActiveSlot = if MCP_Server.isRunning then slotNum else 0
	MCP_Server.isRunning
)

fn MCP_StopServer =
(
	if MCP_Server != undefined and MCP_Server.isRunning then
		MCP_Server.stop()
	MCP_ActiveSlot = 0
	true
)

fn MCP_GetStatus =
(
	local running = MCP_Server != undefined and MCP_Server.isRunning
	local p = if running then MCP_Server.port else 0
	local s = if running then MCP_Server.slot else 0
	local pid = if running then MCP_Server.pid else 0
	#(s, p, running, pid)
)
