-- Figma Serial Controller Agent Launcher
-- Save as Application in Script Editor

tell application "Terminal"
	activate
	set agentPath to POSIX path of ((path to me as text) & "::")
	set agentScript to agentPath & "agent/agent.py"
	
	do script "cd " & quoted form of agentPath & "/agent && python3 agent.py"
end tell
