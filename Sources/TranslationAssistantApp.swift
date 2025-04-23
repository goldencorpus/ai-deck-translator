import SwiftUI
import AppKit
import OSLog

@main
struct TranslationAssistantApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    @StateObject private var viewModel = TranslationViewModel()
    
    init() {
        // Initialize logging
        AppLogger.log(.info, message: "======= APPLICATION STARTING =======")
        AppLogger.log(.info, message: "Starting TranslationAssistant application")
        
        // Log application directory for debug purposes
        let bundlePath = Bundle.main.bundlePath
        AppLogger.log(.info, message: "Application bundle path: \(bundlePath)")
        
        // Log app's directory
        let appDirectory = Bundle.main.bundleURL
        AppLogger.log(.info, message: "App directory: \(appDirectory.path)")
        
        // Check if log file exists at the specified path
        let logFilePath = "/Users/eprouveze/Documents/Dev/App/TranslationAssistantFinal/translation_assistant.log"
        let fileManager = FileManager.default
        let logFileExists = fileManager.fileExists(atPath: logFilePath)
        AppLogger.log(.info, message: "Log file exists at \(logFilePath): \(logFileExists)")
        
        AppLogger.log(.info, message: "Initialization complete")
    }
    
    var body: some Scene {
        WindowGroup {
            ContentView()
                .frame(minWidth: 800, minHeight: 600)
                .environmentObject(viewModel)
        }
        .windowStyle(TitleBarWindowStyle()) // Use standard title bar for better visibility
        .commands {
            // Remove new document command to prevent multiple windows
            CommandGroup(replacing: .newItem) { }
        }
        
        // For macOS menu bar settings
        #if os(macOS)
        Settings {
            EmptyView() // We'll handle settings through our custom UI instead
        }
        #endif
    }
}

// Extension to help find a suitable first responder in the view hierarchy
extension NSView {
    func findFirstResponder() -> NSView? {
        // If this view can become first responder, return it
        if self.acceptsFirstResponder {
            return self
        }
        
        // Otherwise search through subviews
        for subview in self.subviews {
            if let responder = subview.findFirstResponder() {
                return responder
            }
        }
        
        return nil
    }
}

// Window delegate to handle key window events and focus management
class WindowDelegate: NSObject, NSWindowDelegate {
    func windowDidBecomeKey(_ notification: Notification) {
        // Force activation when window becomes key
        NSApp.activate(ignoringOtherApps: true)
        
        // Find a suitable first responder in the window
        if let window = notification.object as? NSWindow,
           let contentView = window.contentView {
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
                if let firstResponder = self.findFirstEditableTextView(in: contentView) {
                    window.makeFirstResponder(firstResponder)
                }
            }
        }
    }
    
    // Helper function to find editable text views
    private func findFirstEditableTextView(in view: NSView) -> NSView? {
        if let textView = view as? NSTextView, textView.isEditable {
            return textView
        }
        
        for subview in view.subviews {
            if let found = findFirstEditableTextView(in: subview) {
                return found
            }
        }
        
        return nil
    }
}

// Enhanced App delegate for robust window activation
class AppDelegate: NSObject, NSApplicationDelegate {
    private var windowDelegate: WindowDelegate?
    
    func applicationDidFinishLaunching(_ notification: Notification) {
        // More robust activation sequence
        DispatchQueue.main.async {
            // First, activate the application at the process level
            NSApp.activate(ignoringOtherApps: true)
            
            // Then handle the window
            if let window = NSApp.windows.first {
                // Center the window
                window.center()
                
                // Make window key and front - this establishes focus within the app
                window.makeKeyAndOrderFront(nil)
                
                // Important: Ensure the application is active before trying to establish first responder
                NSApp.windows.forEach { $0.deminiaturize(nil) }
                
                // Ensure application is activated and in correct state
                NSRunningApplication.current.activate(options: [.activateAllWindows])
                
                // Set up window delegate for better focus handling
                self.windowDelegate = WindowDelegate()
                window.delegate = self.windowDelegate
                
                // Give time for activation to complete and then try to set first responder
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
                    // This forces macOS to fully register this app as the active one
                    // that should receive keyboard input
                    if let contentView = window.contentView {
                        if let responderField = contentView.findFirstResponder() {
                            window.makeFirstResponder(responderField)
                        }
                    }
                }
            }
        }
    }
}