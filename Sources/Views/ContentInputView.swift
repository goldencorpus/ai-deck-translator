import SwiftUI
import UniformTypeIdentifiers
import AppKit
import Combine

// Improved Focusable TextEditor that properly handles keyboard input
struct FocusableTextEditor: NSViewRepresentable {
    @Binding var text: String
    var placeholder: String?
    
    func makeNSView(context: Context) -> NSScrollView {
        let scrollView = NSTextView.scrollableTextView()
        
        guard let textView = scrollView.documentView as? NSTextView else {
            return scrollView
        }
        
        // Configure the text view
        textView.delegate = context.coordinator
        textView.string = text
        textView.isRichText = false
        textView.isEditable = true
        textView.isSelectable = true
        textView.font = NSFont.systemFont(ofSize: NSFont.systemFontSize)
        textView.textContainerInset = NSSize(width: 5, height: 5)
        textView.autoresizingMask = [.width]
        textView.backgroundColor = NSColor.clear
        
        // Important for proper focus
        textView.isAutomaticTextReplacementEnabled = true
        textView.allowsUndo = true
        
        // This will help the text view correctly gain focus
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.7) {
            NSApp.activate(ignoringOtherApps: true)
            if let window = textView.window {
                NSRunningApplication.current.activate(options: [.activateIgnoringOtherApps, .activateAllWindows])
                window.makeFirstResponder(textView)
            }
        }
        
        return scrollView
    }
    
    func updateNSView(_ nsView: NSScrollView, context: Context) {
        guard let textView = nsView.documentView as? NSTextView else {
            return
        }
        
        // Only update if the text doesn't match to avoid cursor jumping
        if textView.string != text {
            textView.string = text
        }
        
        // Ensure proper first responder status when updating
        if let window = nsView.window, window.isKeyWindow {
            DispatchQueue.main.async {
                window.makeFirstResponder(textView)
            }
        }
    }
    
    func makeCoordinator() -> Coordinator {
        Coordinator(self)
    }
    
    class Coordinator: NSObject, NSTextViewDelegate {
        var parent: FocusableTextEditor
        
        init(_ parent: FocusableTextEditor) {
            self.parent = parent
        }
        
        func textDidChange(_ notification: Notification) {
            guard let textView = notification.object as? NSTextView else { return }
            parent.text = textView.string
        }
        
        func textDidEndEditing(_ notification: Notification) {
            // When text field loses focus, ensure the window stays active
            DispatchQueue.main.async {
                NSApp.activate(ignoringOtherApps: true)
            }
        }
    }
}

// Custom NSTextView that renders a placeholder when empty
class PlaceholderTextView: NSTextView {
    var placeholderAttributedString: NSAttributedString?
    
    override func draw(_ dirtyRect: NSRect) {
        super.draw(dirtyRect)
        
        if string.isEmpty, let placeholderAttributedString = placeholderAttributedString {
            let placeholderRect = NSRect(x: 5, y: 5, width: bounds.width - 10, height: bounds.height)
            placeholderAttributedString.draw(in: placeholderRect)
        }
    }
}

struct ContentInputView: View {
    // MARK: - Properties
    @ObservedObject var viewModel: TranslationViewModel
    @State private var isDragging = false
    
    var body: some View {
        VStack(spacing: 30) {
            Text("What would you like to translate?")
                .font(.largeTitle)
                .fontWeight(.bold)
                .multilineTextAlignment(.center)
            
            Group {
                switch viewModel.selectedType {
                case .text:
                    textInputView
                case .file:
                    fileInputView
                case .image:
                    imageInputView
                case nil:
                    EmptyView()
                }
            }
            
            if !viewModel.sourceText.isEmpty || viewModel.sourceFile != nil || viewModel.sourceImage != nil {
                Button(action: {
                    viewModel.submitContent()
                }) {
                    HStack {
                        Text("Continue")
                        Image(systemName: "arrow.right")
                    }
                    .padding()
                    .frame(width: 200)
                    .background(Color.blue)
                    .foregroundColor(.white)
                    .cornerRadius(10)
                }
                .buttonStyle(PlainButtonStyle())
                .padding(.top, 20)
            }
        }
        .padding(.vertical, 40)
    }
    
    // Text input view
    private var textInputView: some View {
        VStack(spacing: 16) {
            Text("Enter the text you want to translate:")
                .font(.headline)
            
            VStack(spacing: 8) {
                // Use FocusState for better focus management
                ZStack(alignment: .topLeading) {
                    if viewModel.sourceText.isEmpty {
                        Text("Type or paste your text here...")
                            .font(.body)
                            .foregroundColor(.gray.opacity(0.7))
                            .padding(.horizontal, 5)
                            .padding(.vertical, 8)
                            .allowsHitTesting(false)
                    }
                    
                    // Replace with the custom TextEditor implementation
                    FocusableTextEditor(text: $viewModel.sourceText, placeholder: "Type or paste your text here...")
                        .frame(minHeight: 300)
                }
                .padding(2)
                .frame(minHeight: 300)
                .overlay(
                    RoundedRectangle(cornerRadius: 10)
                        .stroke(Color.blue.opacity(0.3), lineWidth: 1)
                )
                .background(Color(NSColor.textBackgroundColor).opacity(0.4))
                .cornerRadius(10)
                
                // Helper buttons for text input
                HStack {
                    Button(action: {
                        viewModel.sourceText = ""
                    }) {
                        Label("Clear", systemImage: "trash")
                            .font(.caption)
                    }
                    .buttonStyle(.borderless)
                    .disabled(viewModel.sourceText.isEmpty)
                    
                    Spacer()
                    
                    Button(action: {
                        // Get text from pasteboard
                        let pasteboard = NSPasteboard.general
                        if let string = pasteboard.string(forType: .string) {
                            viewModel.sourceText = string
                        }
                    }) {
                        Label("Paste", systemImage: "doc.on.clipboard")
                            .font(.caption)
                    }
                    .buttonStyle(.borderless)
                    
                    Text("\(viewModel.sourceText.count) characters")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }
        }
        .frame(maxWidth: 700)
        .onAppear {
            // Use AppKit to ensure the application is properly activated
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
                NSApplication.shared.activate(ignoringOtherApps: true)
                NSRunningApplication.current.activate(options: [.activateIgnoringOtherApps, .activateAllWindows])
            }
        }
    }
    
    // File input view
    private var fileInputView: some View {
        VStack(spacing: 20) {
            Text("Upload a document to translate:")
                .font(.headline)
            
            if let url = viewModel.sourceFile {
                // Display file information
                VStack {
                    HStack {
                        Image(systemName: "doc.fill")
                            .font(.largeTitle)
                            .foregroundColor(.blue)
                        
                        VStack(alignment: .leading) {
                            Text(url.lastPathComponent)
                                .font(.headline)
                            
                            Text(url.pathExtension.uppercased())
                                .font(.subheadline)
                                .foregroundColor(.secondary)
                        }
                        
                        Spacer()
                        
                        Button(action: {
                            viewModel.sourceFile = nil
                        }) {
                            Image(systemName: "xmark.circle.fill")
                                .foregroundColor(.gray)
                        }
                        .buttonStyle(PlainButtonStyle())
                    }
                    .padding()
                    .background(Color.blue.opacity(0.1))
                    .cornerRadius(10)
                }
            } else {
                fileDropZone
            }
            
            Text("Supported formats: PDF, DOCX, PPTX, TXT, RTF")
                .font(.caption)
                .foregroundColor(.secondary)
        }
        .frame(maxWidth: 700)
    }
    
    // File drop zone
    private var fileDropZone: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 10)
                .stroke(style: StrokeStyle(lineWidth: 2, dash: [7]))
                .foregroundColor(isDragging ? Color.blue : Color.gray.opacity(0.5))
                .frame(height: 200)
                .background(Color.gray.opacity(0.05).cornerRadius(10))
            
            VStack(spacing: 12) {
                Image(systemName: "arrow.down.doc.fill")
                    .font(.system(size: 40))
                    .foregroundColor(isDragging ? .blue : .gray)
                
                Text("Drag & Drop your file here")
                    .font(.headline)
                
                Text("or")
                    .foregroundColor(.secondary)
                
                Button("Choose File") {
                    openFileDialog()
                }
                .padding(.horizontal, 20)
                .padding(.vertical, 8)
                .background(Color.blue)
                .foregroundColor(.white)
                .cornerRadius(6)
            }
        }
        .onDrop(of: [UTType.fileURL.identifier], isTargeted: $isDragging) { providers -> Bool in
            guard let provider = providers.first else { return false }
            
            _ = provider.loadObject(ofClass: URL.self) { url, error in
                guard error == nil, let url = url else { return }
                
                // Process on the main thread to update UI
                DispatchQueue.main.async {
                    if self.isAcceptableFileType(url) {
                        self.viewModel.sourceFile = url
                    }
                }
            }
            return true
        }
    }
    
    // Image input view
    private var imageInputView: some View {
        VStack(spacing: 20) {
            Text("Upload an image with text to translate:")
                .font(.headline)
            
            if let image = viewModel.sourceImage {
                VStack {
                    Image(nsImage: image)
                        .resizable()
                        .scaledToFit()
                        .frame(maxHeight: 300)
                        .cornerRadius(10)
                    
                    Button("Remove Image") {
                        viewModel.sourceImage = nil
                    }
                    .padding(.top, 10)
                }
            } else {
                imageDropZone
            }
            
            Text("Supported formats: PNG, JPG, JPEG, HEIF")
                .font(.caption)
                .foregroundColor(.secondary)
        }
        .frame(maxWidth: 700)
    }
    
    // Image drop zone
    private var imageDropZone: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 10)
                .stroke(style: StrokeStyle(lineWidth: 2, dash: [7]))
                .foregroundColor(isDragging ? Color.blue : Color.gray.opacity(0.5))
                .frame(height: 200)
                .background(Color.gray.opacity(0.05).cornerRadius(10))
            
            VStack(spacing: 12) {
                Image(systemName: "arrow.down.image")
                    .font(.system(size: 40))
                    .foregroundColor(isDragging ? .blue : .gray)
                
                Text("Drag & Drop your image here")
                    .font(.headline)
                
                Text("or")
                    .foregroundColor(.secondary)
                
                Button("Choose Image") {
                    openImageDialog()
                }
                .padding(.horizontal, 20)
                .padding(.vertical, 8)
                .background(Color.blue)
                .foregroundColor(.white)
                .cornerRadius(6)
            }
        }
        .onDrop(of: [UTType.image.identifier, UTType.fileURL.identifier], isTargeted: $isDragging) { providers -> Bool in
            guard let provider = providers.first else { return false }
            
            // Try to load as URL first (most common case)
            _ = provider.loadObject(ofClass: URL.self) { url, error in
                guard error == nil, let url = url else { 
                    // If URL fails, try loading as image data
                    _ = provider.loadDataRepresentation(forTypeIdentifier: UTType.image.identifier) { data, error in
                        guard error == nil, let data = data, let image = NSImage(data: data) else { return }
                        
                        DispatchQueue.main.async {
                            self.viewModel.sourceImage = image
                        }
                    }
                    return 
                }
                
                // If we have a URL, load it as an image if it's a supported image type
                DispatchQueue.main.async {
                    if self.isAcceptableImageType(url) {
                        if let image = NSImage(contentsOf: url) {
                            self.viewModel.sourceImage = image
                        }
                    }
                }
            }
            return true
        }
    }
    
    // MARK: - File and Image Selection Methods
    
    private func openFileDialog() {
        let panel = NSOpenPanel()
        panel.title = "Choose Document"
        panel.showsResizeIndicator = true
        panel.showsHiddenFiles = false
        panel.canChooseDirectories = false
        panel.canCreateDirectories = false
        panel.allowsMultipleSelection = false
        panel.allowedContentTypes = [
            UTType.pdf,
            UTType.rtf,
            UTType.plainText,
            UTType(importedAs: "com.microsoft.word.doc"),
            UTType(importedAs: "com.microsoft.word.docx"),
            UTType(importedAs: "com.microsoft.powerpoint.ppt"),
            UTType(importedAs: "com.microsoft.powerpoint.pptx")
        ]
        
        if panel.runModal() == .OK {
            if let url = panel.url {
                if isAcceptableFileType(url) {
                    viewModel.sourceFile = url
                }
            }
        }
    }
    
    private func openImageDialog() {
        let panel = NSOpenPanel()
        panel.title = "Choose Image"
        panel.showsResizeIndicator = true
        panel.showsHiddenFiles = false
        panel.canChooseDirectories = false
        panel.canCreateDirectories = false
        panel.allowsMultipleSelection = false
        panel.allowedContentTypes = [
            UTType.png,
            UTType.jpeg,
            UTType.gif,
            UTType.tiff,
            UTType.heic
        ]
        
        if panel.runModal() == .OK {
            if let url = panel.url {
                if isAcceptableImageType(url) {
                    if let image = NSImage(contentsOf: url) {
                        viewModel.sourceImage = image
                    }
                }
            }
        }
    }
    
    private func isAcceptableFileType(_ url: URL) -> Bool {
        let acceptableExtensions = ["pdf", "docx", "pptx", "doc", "ppt", "txt", "rtf"]
        let fileExtension = url.pathExtension.lowercased()
        return acceptableExtensions.contains(fileExtension)
    }
    
    private func isAcceptableImageType(_ url: URL) -> Bool {
        let acceptableExtensions = ["png", "jpg", "jpeg", "heic", "tiff", "gif"]
        let fileExtension = url.pathExtension.lowercased()
        return acceptableExtensions.contains(fileExtension)
    }
}