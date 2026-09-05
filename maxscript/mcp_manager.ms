/*
	MCP Server Manager Dialog
	--------------------------
	Shows status of the MCP server in this 3ds Max instance.
	Allows starting/stopping on any of the 3 slots (ports 8765-8767).

	Run this script or use the MCP Manager toolbar button.
*/

-- Close existing dialog if open
try (destroyDialog MCP_ManagerRollout) catch ()

rollout MCP_ManagerRollout "MCP Server Manager" width:260 height:200
(
	label lblPID "" align:#left offset:[0,4]
	label lblStatus "" align:#left offset:[0,4]
	label lblSlot "" align:#left offset:[0,2]

	dropdownList ddSlot "Select Slot:" items:#("Slot 1 (port 8765)", "Slot 2 (port 8766)", "Slot 3 (port 8767)") width:230 align:#center offset:[0,6]
	button btnToggle "Start" width:230 height:32 align:#center offset:[0,6]

	timer tmRefresh interval:500 active:true

	fn getProcessId =
	(
		local proc = (dotNetClass "System.Diagnostics.Process").GetCurrentProcess()
		proc.Id
	)

	fn refreshUI =
	(
		local myPid = getProcessId()
		lblPID.text = "PID: " + myPid as string

		if ::MCP_Server != undefined and ::MCP_Server.isRunning then
		(
			local s = ::MCP_ActiveSlot
			local p = ::MCP_Server.port
			lblStatus.text = "Status: RUNNING"
			lblSlot.text = "Active: Slot " + s as string + " (port " + p as string + ")"
			btnToggle.text = "Stop Slot " + s as string
			ddSlot.selection = s
		)
		else
		(
			lblStatus.text = "Status: STOPPED"
			lblSlot.text = "Active: None"
			btnToggle.text = "Start Slot " + ddSlot.selection as string
		)
	)

	on MCP_ManagerRollout open do
	(
		-- Ensure server script is loaded
		if ::MCP_StartSlot == undefined then
		(
			local serverScript = (getDir #scripts) + "\\mcp\\mcp_server.ms"
			if doesFileExist serverScript then fileIn serverScript
		)

		-- Set dropdown to current slot if running
		if ::MCP_ActiveSlot != undefined and ::MCP_ActiveSlot > 0 then
			ddSlot.selection = ::MCP_ActiveSlot

		refreshUI()
	)

	on tmRefresh tick do refreshUI()

	on ddSlot selected idx do
	(
		if ::MCP_Server == undefined or not ::MCP_Server.isRunning then
			btnToggle.text = "Start Slot " + idx as string
	)

	on btnToggle pressed do
	(
		if ::MCP_Server != undefined and ::MCP_Server.isRunning then
		(
			::MCP_StopServer()
		)
		else
		(
			local slot = ddSlot.selection
			::MCP_StartSlot slot
		)
		refreshUI()
	)
)

createDialog MCP_ManagerRollout style:#(#style_titlebar, #style_sysmenu, #style_toolwindow)
