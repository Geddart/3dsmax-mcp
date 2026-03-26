/*
	MCP Server Auto-Start (Multi-Instance)
	Place this file in: [3ds Max Install Dir]\scripts\startup\
	Also copy mcp_server.ms to: [3ds Max Install Dir]\scripts\mcp\mcp_server.ms

	Tries slots 1-3 in order, picks the first free port.
*/

(
	local scriptDir = (getDir #scripts) + "\\mcp\\"
	local serverScript = scriptDir + "mcp_server.ms"

	if doesFileExist serverScript then
	(
		fileIn serverScript

		-- Try each slot until one succeeds (port not in use)
		local started = false
		for s = 1 to 3 while not started do
		(
			started = ::MCP_StartSlot s
			if started then
				format "MCP: Auto-start on slot % (port %) complete\n" s (::MCP_BasePort + s - 1)
			else
				format "MCP: Slot % (port %) in use, trying next...\n" s (::MCP_BasePort + s - 1)
		)

		if not started then
			format "MCP: All slots (1-3) are in use. Start manually with MCP1/MCP2/MCP3 buttons.\n"
	)
	else
	(
		format "MCP: Server script not found at: %\n" serverScript
		format "MCP: Copy mcp_server.ms to the path above for auto-start\n"
	)
)
