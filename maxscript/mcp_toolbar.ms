/*
	MCP Server Toolbar Buttons — Multi-Instance
	---------------------------------------------
	Run this script once in 3ds Max to register macroscripts.
	Then: Customize > Customize User Interface > Toolbars
	Look under category "MCP Server" to find:
	  - MCP1  (slot 1, port 8765)
	  - MCP2  (slot 2, port 8766)
	  - MCP3  (slot 3, port 8767)
	  - MCP Manager (status dialog)

	Each slot button toggles: click to start on that slot's port,
	click again (or click a different slot) to stop/switch.
	Only one slot can be active per 3ds Max instance.
*/

-- Helper: ensure mcp_server.ms is loaded
fn MCP_EnsureLoaded =
(
	if ::MCP_StartSlot == undefined then
	(
		local serverScript = (getDir #scripts) + "\\mcp\\mcp_server.ms"
		if doesFileExist serverScript then
		(
			fileIn serverScript
			format "MCP: Loaded mcp_server.ms\n"
			true
		)
		else
		(
			messageBox ("mcp_server.ms not found at:\n" + serverScript + "\n\nCopy it there first.") title:"MCP"
			false
		)
	)
	else true
)

-- Slot 1 (port 8765)
macroScript MCP_Slot1
	category:"MCP Server"
	buttonText:"MCP1"
	toolTip:"Toggle MCP Server slot 1 (port 8765)"
(
	on isChecked do
	(
		::MCP_ActiveSlot != undefined and ::MCP_ActiveSlot == 1
	)
	on execute do
	(
		if not (MCP_EnsureLoaded()) then return undefined
		if ::MCP_ActiveSlot == 1 then
			::MCP_StopServer()
		else
			::MCP_StartSlot 1
	)
)

-- Slot 2 (port 8766)
macroScript MCP_Slot2
	category:"MCP Server"
	buttonText:"MCP2"
	toolTip:"Toggle MCP Server slot 2 (port 8766)"
(
	on isChecked do
	(
		::MCP_ActiveSlot != undefined and ::MCP_ActiveSlot == 2
	)
	on execute do
	(
		if not (MCP_EnsureLoaded()) then return undefined
		if ::MCP_ActiveSlot == 2 then
			::MCP_StopServer()
		else
			::MCP_StartSlot 2
	)
)

-- Slot 3 (port 8767)
macroScript MCP_Slot3
	category:"MCP Server"
	buttonText:"MCP3"
	toolTip:"Toggle MCP Server slot 3 (port 8767)"
(
	on isChecked do
	(
		::MCP_ActiveSlot != undefined and ::MCP_ActiveSlot == 3
	)
	on execute do
	(
		if not (MCP_EnsureLoaded()) then return undefined
		if ::MCP_ActiveSlot == 3 then
			::MCP_StopServer()
		else
			::MCP_StartSlot 3
	)
)

-- Manager dialog button
macroScript MCP_Manager
	category:"MCP Server"
	buttonText:"MCP Mgr"
	toolTip:"Open MCP Server Manager"
(
	on execute do
	(
		local mgrScript = (getDir #scripts) + "\\mcp\\mcp_manager.ms"
		if doesFileExist mgrScript then
		(
			fileIn mgrScript
		)
		else
		(
			-- Try relative to this script's location
			local altPath = (getFilenamePath (getSourceFileName())) + "mcp_manager.ms"
			if doesFileExist altPath then
				fileIn altPath
			else
				messageBox "mcp_manager.ms not found." title:"MCP"
		)
	)
)
