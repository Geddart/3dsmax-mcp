-- Native MCP helpers and instance UI. No TCP listener.
struct MCPNativeHelpers (
	fn escapeJsonString str =
	(
		if str == undefined then return ""
		local s = str as string
		-- Fast path: common escapes via native substituteString
		s = substituteString s "\\" "\\\\"
		s = substituteString s "\"" "\\\""
		s = substituteString s "\n" "\\n"
		s = substituteString s "\r" "\\r"
		s = substituteString s "\t" "\\t"
		-- Check for remaining control chars (backspace, form feed, etc.)
		local hasControl = false
		for i = 1 to s.count while not hasControl do
		(
			local code = bit.charAsInt s[i]
			if code < 32 do hasControl = true
		)
		if hasControl then
		(
			local result = ""
			local hexChars = "0123456789abcdef"
			for i = 1 to s.count do
			(
				local code = bit.charAsInt s[i]
				if code == 8 then result += "\\b"
				else if code == 12 then result += "\\f"
				else if code < 32 then
				(
					local hi = (mod (bit.shift code -4) 16) as integer + 1
					local lo = (mod code 16) as integer + 1
					result += "\\u00" + hexChars[hi] + hexChars[lo]
				)
				else result += s[i]
			)
			s = result
		)
		s
	)
)
global MCP_Server = MCPNativeHelpers()

global MCP_InstancePanel
fn MCP_ConfigDirectory = ((dotNetClass "System.Environment").GetFolderPath (dotNetClass "System.Environment+SpecialFolder").LocalApplicationData) + "/3dsmax-mcp"

fn MCP_ClaimProcess processId = (
    local io = dotNetClass "System.IO.File"
    local config = MCP_ConfigDirectory()
    local record = config + "/instances/pid-" + (processId as string) + ".json"
    local proc = (dotNetClass "System.Diagnostics.Process").GetProcessById processId
    if proc.ProcessName != "3dsmax" or not (io.Exists record) do throw "This process has no native MCP discovery record"
    io.Copy record (config + "/active_instance.json") true
    format "MCP target: PID %\n" processId
)

rollout MCP_InstancePanel "MCP Native Instances" width:540 height:175 (
    local processIds = #()
    label status "Native named pipes - no ports or slots" align:#left
    dropdownList targets "Running Max instances:" items:#() width:515
    button refresh "Refresh" width:120 across:2
    button claim "Use selected instance" width:260
    label detail "Claim sets the default; an MCP session may explicitly pin its own target." align:#left
    fn refreshInstances = (
        local rows = #()
        processIds = #()
        local io = dotNetClass "System.IO.File"
        local regex = dotNetClass "System.Text.RegularExpressions.Regex"
        local config = MCP_ConfigDirectory()
        for proc in (dotNetClass "System.Diagnostics.Process").GetProcessesByName "3dsmax" do (
            local record = config + "/instances/pid-" + (proc.Id as string) + ".json"
            if io.Exists record do (
                local raw = io.ReadAllText record
                local version = (regex.Match raw "\"max_version\"\\s*:\\s*(\\d+)").Groups.Item[1].Value as string
                append processIds proc.Id
                append rows ("Max " + version + " | PID " + (proc.Id as string) + " | " + (proc.MainWindowTitle as string))
            )
        )
        targets.items = rows
        if rows.count > 0 do targets.selection = 1
        status.text = "Native instances found: " + (rows.count as string)
    )
    on MCP_InstancePanel open do refreshInstances()
    on refresh pressed do refreshInstances()
    on claim pressed do (
        if targets.selection > 0 do (
            try (MCP_ClaimProcess processIds[targets.selection]; status.text = "Default target: PID " + (processIds[targets.selection] as string))
            catch (status.text = getCurrentException() as string)
        )
    )
)

macroScript MCP_Claim_This_Max category:"MCP" tooltip:"Use this native Max instance" buttonText:"MCP Claim This Max" (
    on execute do MCP_ClaimProcess ((dotNetClass "System.Diagnostics.Process").GetCurrentProcess()).Id
)
macroScript MCP_Instances category:"MCP" tooltip:"Choose a native Max instance" buttonText:"MCP Instances" (
    on execute do (try(destroyDialog MCP_InstancePanel)catch(); createDialog MCP_InstancePanel)
)
