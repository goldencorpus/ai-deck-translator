#!/bin/bash

# Script to build a proper macOS app bundle for TranslationAssistant
# This will create a complete .app package that can be launched like a normal macOS application

set -e  # Exit on any error

APP_NAME="TranslationAssistant"
BUILD_DIR="./build"
APP_DIR="$BUILD_DIR/$APP_NAME.app"
CONTENTS_DIR="$APP_DIR/Contents"
MACOS_DIR="$CONTENTS_DIR/MacOS"
RESOURCES_DIR="$CONTENTS_DIR/Resources"

echo "Building $APP_NAME as a proper macOS application bundle..."

# First build the executable using the existing build script
./build.sh

# Create the app bundle directory structure
mkdir -p "$MACOS_DIR"
mkdir -p "$RESOURCES_DIR"

# Copy the executable to the MacOS directory
cp "$BUILD_DIR/$APP_NAME" "$MACOS_DIR/"

# Create a basic Info.plist
cat > "$CONTENTS_DIR/Info.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>$APP_NAME</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>CFBundleIdentifier</key>
    <string>com.example.$APP_NAME</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>$APP_NAME</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>LSMinimumSystemVersion</key>
    <string>12.0</string>
    <key>CFBundleVersion</key>
    <string>1</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSPrincipalClass</key>
    <string>NSApplication</string>
    <key>NSSupportsAutomaticGraphicsSwitching</key>
    <true/>
</dict>
</plist>
EOF

# Create a dummy icon file (can be replaced with a real icon later)
echo "Creating placeholder icon..."
touch "$RESOURCES_DIR/AppIcon.icns"

# Create PkgInfo
echo "APPL????" > "$CONTENTS_DIR/PkgInfo"

echo "App bundle created at $APP_DIR"
echo ""
echo "You can now launch the application by:"
echo "1. Open Finder and navigate to $(pwd)/$APP_DIR"
echo "2. Double-click on the app icon to run"
echo ""
echo "Or run this command:"
echo "open \"$APP_DIR\""