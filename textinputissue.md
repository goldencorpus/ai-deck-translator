# SwiftUI Text Input Issue Report

## Problem Description

When running the TranslationAssistant application, text input fields are not receiving keyboard input properly. Users can see the cursor blinking in the text field indicating that it visually has focus, but keyboard input is directed to the previously active window (e.g., the terminal window from which the app was launched) rather than the app's text field. Copy-paste operations work correctly, but direct typing does not.

## Technical Environment

- macOS desktop application (macOS Ventura/Sonoma)
- Swift 5.9
- SwiftUI framework (macOS version)
- Executed from command line via `swift run` or `./build/TranslationAssistant`
- Project created with Swift Package Manager
- Build system: Swift Package Manager and custom build scripts
- Application structure:
  - TranslationAssistantApp.swift (Entry point with AppDelegate)
  - ContentView.swift (Main view container)
  - ContentInputView.swift (Problematic text input view)
  - TranslationViewModel.swift (State management)
- Dependencies: 
  - AppKit (for custom text field implementations)
  - UniformTypeIdentifiers (for file handling)
  - Combine (for async operations)
  - NaturalLanguage (for language detection)

## Attempted Solutions

### 1. SwiftUI @FocusState Approach

We initially tried using SwiftUI's native focus management:

```swift
@FocusState private var isTextEditorFocused: Bool

TextEditor(text: $viewModel.sourceText)
    .focused($isTextEditorFocused)
    .onAppear {
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
            isTextEditorFocused = true
        }
    }
```

**Result**: The text field received visual focus (cursor blinking), but keyboard input was still directed elsewhere.

### 2. Custom NSViewRepresentable with NSTextView

We created a custom TextEditor implementation using AppKit's NSTextView wrapped in NSViewRepresentable:

```swift
struct CustomTextEditor: NSViewRepresentable {
    @Binding var text: String
    
    func makeNSView(context: Context) -> NSScrollView {
        let textView = CustomNSTextView()
        // Configuration...
        
        DispatchQueue.main.async {
            textView.window?.makeFirstResponder(textView)
        }
        
        return scrollView
    }
    
    // Other required methods...
}
```

**Result**: The NSTextView appeared correctly, but still couldn't capture keyboard input. We saw some crashes related to the responder chain.

### 3. Global Event Monitoring and Focus Management

We tried implementing a global focus manager that monitors key events and redirects them:

```swift
class TextEditorFocusManager {
    static let shared = TextEditorFocusManager()
    
    func enableFocusTracking() {
        NSEvent.addLocalMonitorForEvents(matching: [.keyDown]) { event in
            // Attempt to redirect key events to our text view
            // ...
            return event
        }
    }
}
```

**Result**: Didn't solve the issue and potentially interfered with normal event handling.

### 4. Simplified Standard SwiftUI TextEditor

We reverted to using the standard SwiftUI TextEditor with minimal customization:

```swift
TextEditor(text: $viewModel.sourceText)
    .font(.body)
    .background(Color.clear)
```

**Result**: Still experiencing the same issue - visual focus but no keyboard input.

### 5. NSTextField Approach

We tried using NSTextField instead of NSTextView:

```swift
struct SimpleTextField: NSViewRepresentable {
    @Binding var text: String
    
    func makeNSView(context: Context) -> NSTextField {
        let textField = NSTextField()
        // Configuration...
        return textField
    }
    
    // Other required methods...
}
```

**Result**: Same issue persisted.

## Technical Analysis

The problem appears to be related to the **application activation state** and **first responder chain** rather than the text field implementation itself. Several observations:

1. **Window Activation**: The application window visually activates (becomes frontmost), but doesn't seem to receive the proper activation state at the OS level.

2. **Input Focus vs. Visual Focus**: There's a disconnect between visual focus (cursor blinking) and input focus (where keyboard events are directed).

3. **Application Launch Context**: The issue may be related to how the app is launched from the command line, which might affect how macOS assigns keyboard focus.

4. **Responder Chain**: Errors observed during testing suggest the responder chain might be improperly configured or interrupted.

5. **Event Processing**: Even with manual attempts to redirect events, the keyboard input continues to be captured by the wrong window.

## Possible Root Causes

1. **Terminal/CLI Launch Context**: Applications launched from Terminal might have different activation behavior than those launched from Finder.

2. **NSApp Activation**: The `NSApp.activate(ignoringOtherApps: true)` call might not be fully activating the application from a keyboard focus perspective.

3. **Window Server Interaction**: There might be an issue with how the app interacts with the macOS window server when determining which application receives keyboard events.

4. **SwiftUI Lifecycle**: The issue might be related to how SwiftUI handles window and scene activation compared to AppKit.

5. **First Responder Management**: There might be conflicts in how first responder status is managed between SwiftUI and AppKit components.

## Potential Solutions to Explore

1. **Launch Method**: Try launching the application via Finder or through Xcode instead of the command line.

2. **External Process Activation**: Use AppleScript or other system-level tools to properly activate the application after launch.

3. **Alternative Window Creation**: Create the main window using AppKit directly instead of SwiftUI's WindowGroup.

4. **Process Management**: Investigate process-level settings that might affect how focus is assigned.

5. **SwiftUI Version Specifics**: Check if this is a known issue with specific versions of SwiftUI that might have workarounds.

6. **Input Methods**: Investigate if there's interaction with the input method system that might be affecting keyboard event routing.

7. **Event Tap**: Create a global event tap at the CGEvent level to redirect keyboard events.

This issue represents a complex interaction between SwiftUI, AppKit, and macOS window management systems, potentially exacerbated by the command-line launch context.