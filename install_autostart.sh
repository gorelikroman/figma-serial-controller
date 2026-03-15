#!/bin/bash
# Install Serial Controller as Launch Agent (autostart on login)

PLIST_NAME="com.figma.serial-controller.plist"
PLIST_PATH="$HOME/Library/LaunchAgents/$PLIST_NAME"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Creating Launch Agent plist..."

cat > "$PLIST_PATH" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.figma.serial-controller</string>
    
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>$SCRIPT_DIR/agent/agent.py</string>
    </array>
    
    <key>WorkingDirectory</key>
    <string>$SCRIPT_DIR/agent</string>
    
    <key>RunAtLoad</key>
    <true/>
    
    <key>KeepAlive</key>
    <true/>
    
    <key>StandardOutPath</key>
    <string>$HOME/Library/Logs/figma-serial-controller.log</string>
    
    <key>StandardErrorPath</key>
    <string>$HOME/Library/Logs/figma-serial-controller-error.log</string>
</dict>
</plist>
EOF

echo "✓ Created: $PLIST_PATH"
echo ""
echo "To enable autostart:"
echo "  launchctl load \"$PLIST_PATH\""
echo ""
echo "To disable autostart:"
echo "  launchctl unload \"$PLIST_PATH\""
echo ""
echo "To start now:"
echo "  launchctl start com.figma.serial-controller"
echo ""
echo "To stop:"
echo "  launchctl stop com.figma.serial-controller"
echo ""
echo "Logs:"
echo "  tail -f ~/Library/Logs/figma-serial-controller.log"
