#!/bin/bash

# This script launches the TranslationAssistant application properly
# to ensure it gets correct keyboard focus

# Path to the application
APP_PATH="./build/TranslationAssistant.app"

# Use AppleScript to launch and activate the application properly
# This ensures better activation than directly calling the binary
osascript -e "
tell application \"Finder\"
    set appPath to POSIX file \"$(pwd)/$APP_PATH\" as string
    open appPath
end tell

delay 0.5

tell application \"System Events\"
    set frontmost of process \"TranslationAssistant\" to true
end tell
"

# Exit the terminal process to further avoid focus conflicts
echo "Application launched. Terminal process exiting to avoid focus conflicts."
exit 0