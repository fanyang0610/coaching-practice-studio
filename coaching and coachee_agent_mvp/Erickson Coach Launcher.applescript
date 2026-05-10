set workspace_path_value to "/Users/fanyang/Documents/My Documents/Vibe Coding/coaching and coachee_agent_mvp"
set launch_command to "cd " & (quoted form of workspace_path_value) & " && ERICKSON_INBROWSER=0 python3 mac_launcher.py"

tell application "Terminal.app"
	activate
	«event coredosc» launch_command
end tell
