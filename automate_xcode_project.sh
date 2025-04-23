#!/bin/bash

# Set colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Automating Xcode Project Creation ===${NC}"

# Set directories
BASE_DIR="$HOME/Documents/Dev/App/TranslationAssistantFinal"
XCODE_PROJECT_DIR="$BASE_DIR/XcodeProject"
SOURCES_DIR="$BASE_DIR/Sources"
RESOURCES_DIR="$BASE_DIR/Resources"

# Create a temporary file for Xcode project template
TEMPLATE_FILE="$(mktemp)"

# Create template for Xcode project creation
cat > "$TEMPLATE_FILE" << 'EOF'
// !$*UTF8*$!
{
    archiveVersion = 1;
    classes = {
    };
    objectVersion = 56;
    objects = {
        LastUpgradeCheck = 1420;
        LastSwiftUpdateCheck = 1420;
        BuildIndependentTargetsInParallel = 1;
    };
    rootObject = ROOT_OBJECT;
}
EOF

# Create XcodeProject directory
echo -e "${BLUE}Creating Xcode project directory...${NC}"
mkdir -p "$XCODE_PROJECT_DIR/TranslationAssistant"

# Create Xcode project structure
echo -e "${BLUE}Creating Xcode project structure...${NC}"
mkdir -p "$XCODE_PROJECT_DIR/TranslationAssistant.xcodeproj"
cp "$TEMPLATE_FILE" "$XCODE_PROJECT_DIR/TranslationAssistant.xcodeproj/project.pbxproj"

# Create Info.plist
echo -e "${BLUE}Creating Info.plist...${NC}"
cat > "$XCODE_PROJECT_DIR/TranslationAssistant/Info.plist" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>$(DEVELOPMENT_LANGUAGE)</string>
    <key>CFBundleExecutable</key>
    <string>$(EXECUTABLE_NAME)</string>
    <key>CFBundleIdentifier</key>
    <string>$(PRODUCT_BUNDLE_IDENTIFIER)</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>$(PRODUCT_NAME)</string>
    <key>CFBundlePackageType</key>
    <string>$(PRODUCT_BUNDLE_PACKAGE_TYPE)</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundleVersion</key>
    <string>1</string>
    <key>LSMinimumSystemVersion</key>
    <string>$(MACOSX_DEPLOYMENT_TARGET)</string>
    <key>NSHumanReadableCopyright</key>
    <string></string>
</dict>
</plist>
EOF

# Copy source files
echo -e "${BLUE}Copying source files...${NC}"

# Create directory structure
mkdir -p "$XCODE_PROJECT_DIR/TranslationAssistant/Views"
mkdir -p "$XCODE_PROJECT_DIR/TranslationAssistant/ViewModels"
mkdir -p "$XCODE_PROJECT_DIR/TranslationAssistant/Services"

# Copy main app file
cp "$SOURCES_DIR/TranslationAssistantApp.swift" "$XCODE_PROJECT_DIR/TranslationAssistant/" 2>/dev/null || echo -e "${RED}Failed to copy TranslationAssistantApp.swift${NC}"

# Copy view files
if [ -d "$SOURCES_DIR/Views" ]; then
    cp "$SOURCES_DIR/Views/"*.swift "$XCODE_PROJECT_DIR/TranslationAssistant/Views/" 2>/dev/null
    echo -e "${GREEN}Copied Views${NC}"
else
    echo -e "${RED}Views directory not found!${NC}"
fi

# Copy viewmodel files
if [ -d "$SOURCES_DIR/ViewModels" ]; then
    cp "$SOURCES_DIR/ViewModels/"*.swift "$XCODE_PROJECT_DIR/TranslationAssistant/ViewModels/" 2>/dev/null
    echo -e "${GREEN}Copied ViewModels${NC}"
else
    echo -e "${RED}ViewModels directory not found!${NC}"
fi

# Copy service files
if [ -d "$SOURCES_DIR/Services" ]; then
    cp "$SOURCES_DIR/Services/"*.swift "$XCODE_PROJECT_DIR/TranslationAssistant/Services/" 2>/dev/null
    echo -e "${GREEN}Copied Services${NC}"
else
    echo -e "${RED}Services directory not found!${NC}"
fi

# Create Assets.xcassets structure
echo -e "${BLUE}Creating Assets.xcassets...${NC}"
mkdir -p "$XCODE_PROJECT_DIR/TranslationAssistant/Assets.xcassets/Colors/Background.colorset"

# Create Contents.json for Assets
cat > "$XCODE_PROJECT_DIR/TranslationAssistant/Assets.xcassets/Contents.json" << 'EOF'
{
  "info" : {
    "author" : "xcode",
    "version" : 1
  }
}
EOF

# Create Contents.json for Colors folder
cat > "$XCODE_PROJECT_DIR/TranslationAssistant/Assets.xcassets/Colors/Contents.json" << 'EOF'
{
  "info" : {
    "author" : "xcode",
    "version" : 1
  }
}
EOF

# Create Background.colorset
cat > "$XCODE_PROJECT_DIR/TranslationAssistant/Assets.xcassets/Colors/Background.colorset/Contents.json" << 'EOF'
{
  "colors" : [
    {
      "color" : {
        "color-space" : "srgb",
        "components" : {
          "alpha" : "1.000",
          "blue" : "0.980",
          "green" : "0.980",
          "red" : "0.980"
        }
      },
      "idiom" : "universal"
    },
    {
      "appearances" : [
        {
          "appearance" : "luminosity",
          "value" : "dark"
        }
      ],
      "color" : {
        "color-space" : "srgb",
        "components" : {
          "alpha" : "1.000",
          "blue" : "0.180",
          "green" : "0.160",
          "red" : "0.160"
        }
      },
      "idiom" : "universal"
    }
  ],
  "info" : {
    "author" : "xcode",
    "version" : 1
  }
}
EOF

echo -e "${GREEN}Created assets${NC}"

# Create entitlements file
echo -e "${BLUE}Creating entitlements file...${NC}"
cat > "$XCODE_PROJECT_DIR/TranslationAssistant/TranslationAssistant.entitlements" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>com.apple.security.app-sandbox</key>
    <true/>
    <key>com.apple.security.files.user-selected.read-only</key>
    <true/>
    <key>com.apple.security.network.client</key>
    <true/>
</dict>
</plist>
EOF

# Create a Makefile for easy building
echo -e "${BLUE}Creating Makefile...${NC}"
cat > "$XCODE_PROJECT_DIR/Makefile" << 'EOF'
APP_NAME = TranslationAssistant
BUILD_DIR = build

.PHONY: all clean build run

all: build

build:
	@mkdir -p $(BUILD_DIR)
	@swiftc -o $(BUILD_DIR)/$(APP_NAME) TranslationAssistant/*.swift TranslationAssistant/Views/*.swift TranslationAssistant/ViewModels/*.swift TranslationAssistant/Services/*.swift

run: build
	@$(BUILD_DIR)/$(APP_NAME)

clean:
	@rm -rf $(BUILD_DIR)
EOF

# Create a simple Swift file to check
echo -e "${BLUE}Creating a test Swift file...${NC}"
cat > "$XCODE_PROJECT_DIR/test_build.swift" << 'EOF'
import SwiftUI
import AppKit

@main
struct TestApp {
    static func main() {
        let app = NSApplication.shared
        let delegate = AppDelegate()
        app.delegate = delegate
        app.run()
    }
}

class AppDelegate: NSObject, NSApplicationDelegate {
    var window: NSWindow!
    
    func applicationDidFinishLaunching(_ notification: Notification) {
        let contentView = TestView()
        
        window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 480, height: 300),
            styleMask: [.titled, .closable, .miniaturizable, .resizable],
            backing: .buffered,
            defer: false
        )
        window.center()
        window.title = "Test App"
        window.contentView = NSHostingView(rootView: contentView)
        window.makeKeyAndOrderFront(nil)
        
        NSApp.activate(ignoringOtherApps: true)
    }
}

struct TestView: View {
    var body: some View {
        VStack(spacing: 20) {
            Text("Test App Running!")
                .font(.largeTitle)
                .fontWeight(.bold)
            
            Text("If you can see this, the build configuration works")
                .font(.title2)
            
            Button("Close") {
                NSApp.terminate(nil)
            }
            .padding()
            .background(Color.blue)
            .foregroundColor(.white)
            .cornerRadius(10)
        }
        .padding()
    }
}
EOF

# Create a README with instructions
echo -e "${BLUE}Creating README...${NC}"
cat > "$XCODE_PROJECT_DIR/README.md" << 'EOF'
# TranslationAssistant - Automated Project

This is an automated build of the TranslationAssistant project.

## Opening in Xcode

1. In Xcode, select "Open a project or file"
2. Navigate to this directory and open TranslationAssistant.xcodeproj

## If Xcode doesn't open the project properly

You can compile and run the app using one of these methods:

### Option 1: Command line compilation

```bash
cd /path/to/this/directory
make build
make run
```

### Option 2: Create a new project

1. Open Xcode
2. Create a new macOS App project
3. Delete any auto-generated files
4. Right-click on the project and select "Add Files to [ProjectName]"
5. Navigate to the TranslationAssistant folder in this directory
6. Select all files and add them to the project
7. Build and run

## Project Structure

- TranslationAssistant/
  - TranslationAssistantApp.swift
  - Views/
  - ViewModels/
  - Services/
  - Assets.xcassets/
EOF

# Create a shell script to build without Xcode
echo -e "${BLUE}Creating build script...${NC}"
cat > "$XCODE_PROJECT_DIR/build.sh" << 'EOF'
#!/bin/bash

echo "Building TranslationAssistant..."

# Set directories
APP_NAME="TranslationAssistant"
BUILD_DIR="build"
SRC_DIR="TranslationAssistant"

# Create build directory
mkdir -p "$BUILD_DIR"

# Compile Swift files
swiftc -o "$BUILD_DIR/$APP_NAME" \
    "$SRC_DIR/TranslationAssistantApp.swift" \
    "$SRC_DIR/Views/"*.swift \
    "$SRC_DIR/ViewModels/"*.swift \
    "$SRC_DIR/Services/"*.swift

if [ $? -eq 0 ]; then
    echo "Build succeeded!"
    echo "To run the app: $BUILD_DIR/$APP_NAME"
else
    echo "Build failed!"
fi
EOF
chmod +x "$XCODE_PROJECT_DIR/build.sh"

# Create a script to open the project in Xcode
echo -e "${BLUE}Creating Xcode launcher...${NC}"
cat > "$XCODE_PROJECT_DIR/open_in_xcode.sh" << EOF
#!/bin/bash

echo "Opening TranslationAssistant in Xcode..."
open -a Xcode "$XCODE_PROJECT_DIR/TranslationAssistant.xcodeproj"
EOF
chmod +x "$XCODE_PROJECT_DIR/open_in_xcode.sh"

echo -e "${GREEN}Project setup complete!${NC}"
echo -e "${BLUE}To open in Xcode:${NC}"
echo "cd \"$XCODE_PROJECT_DIR\" && ./open_in_xcode.sh"
echo -e "${BLUE}Or create a build without Xcode:${NC}"
echo "cd \"$XCODE_PROJECT_DIR\" && ./build.sh"