import SwiftUI

struct TranslationResultView: View {
    @ObservedObject var viewModel: TranslationViewModel
    @State private var showingPrompt = false
    
    var body: some View {
        VStack(spacing: 30) {
            Text("Translation Results")
                .font(.largeTitle)
                .fontWeight(.bold)
                .multilineTextAlignment(.center)
            
            // Translation status
            if viewModel.isProcessing {
                loadingView
            } else if let errorMessage = viewModel.errorMessage {
                errorView(message: errorMessage)
            } else {
                resultContent
            }
        }
        .padding(.vertical, 40)
        .sheet(isPresented: $showingPrompt) {
            promptSheetView
        }
    }
    
    // Loading view
    private var loadingView: some View {
        VStack(spacing: 20) {
            ProgressView()
                .scaleEffect(1.5)
                .padding()
            
            Text("Processing your translation...")
                .font(.headline)
            
            Text("This may take a moment depending on the content size")
                .foregroundColor(.secondary)
        }
        .frame(maxWidth: .infinity)
        .padding()
        .background(Color.blue.opacity(0.05))
        .cornerRadius(12)
    }
    
    // Error view
    private func errorView(message: String) -> some View {
        VStack(spacing: 16) {
            Image(systemName: "exclamationmark.triangle.fill")
                .font(.system(size: 40))
                .foregroundColor(.orange)
            
            Text("Translation Error")
                .font(.headline)
            
            Text(message)
                .multilineTextAlignment(.center)
                .foregroundColor(.secondary)
            
            if viewModel.showLogFileUrl != nil {
                HStack {
                    Image(systemName: "doc.text.magnifyingglass")
                        .foregroundColor(.blue)
                    
                    Button("View Log File") {
                        if let url = viewModel.showLogFileUrl {
                            NSWorkspace.shared.open(url)
                        }
                    }
                    .foregroundColor(.blue)
                    .buttonStyle(PlainButtonStyle())
                }
                .padding(.vertical, 8)
            }
            
            HStack(spacing: 16) {
                Button("Try Again") {
                    viewModel.translate()
                }
                .padding(.horizontal, 20)
                .padding(.vertical, 8)
                .background(Color.blue)
                .foregroundColor(.white)
                .cornerRadius(6)
                
                Button("Validate API Key") {
                    viewModel.currentStep = .apiKeyManagement
                }
                .padding(.horizontal, 20)
                .padding(.vertical, 8)
                .background(Color.green)
                .foregroundColor(.white)
                .cornerRadius(6)
                .opacity(message.contains("API key") ? 1.0 : 0.0)
                .disabled(!message.contains("API key"))
            }
        }
        .padding()
        .background(Color.orange.opacity(0.05))
        .cornerRadius(12)
    }
    
    // Result content
    private var resultContent: some View {
        VStack(spacing: 30) {
            // Translation info
            translationInfoView
            
            // Result text
            resultTextView
            
            // Action buttons
            HStack(spacing: 20) {
                actionButton(title: "View Prompt", icon: "text.alignleft") {
                    showingPrompt = true
                }
                
                actionButton(title: "Copy Translation", icon: "doc.on.doc") {
                    // Try to parse the JSON to extract just the translation text
                    if let jsonData = viewModel.resultText.data(using: .utf8),
                       let json = try? JSONSerialization.jsonObject(with: jsonData, options: []) as? [String: Any],
                       let translation = json["translation"] as? [String: Any],
                       let text = translation["text"] as? String {
                        // Copy just the translated text
                        let pasteboard = NSPasteboard.general
                        pasteboard.clearContents()
                        pasteboard.setString(text, forType: .string)
                    } else {
                        // If parsing fails, copy the entire result
                        let pasteboard = NSPasteboard.general
                        pasteboard.clearContents()
                        pasteboard.setString(viewModel.resultText, forType: .string)
                    }
                }
                
                actionButton(title: "Save As...", icon: "arrow.down.doc") {
                    // Create a save panel
                    let savePanel = NSSavePanel()
                    savePanel.allowedContentTypes = [.text]
                    savePanel.nameFieldStringValue = "translation.txt"
                    savePanel.title = "Save Translation"
                    savePanel.message = "Choose a location to save your translation"
                    savePanel.prompt = "Save"
                    
                    savePanel.begin { response in
                        if response == .OK, let url = savePanel.url {
                            do {
                                try viewModel.resultText.write(to: url, atomically: true, encoding: .utf8)
                            } catch {
                                print("Failed to save translation: \(error.localizedDescription)")
                            }
                        }
                    }
                }
                
                actionButton(title: "New Translation", icon: "arrow.clockwise") {
                    viewModel.currentStep = .selectType
                    viewModel.selectedType = nil
                    viewModel.hasApiKey = nil
                    viewModel.allowCloudUpload = nil
                    viewModel.sourceText = ""
                    viewModel.sourceFile = nil
                    viewModel.sourceImage = nil
                    viewModel.sourceLanguage = ""
                    viewModel.targetLanguage = ""
                    viewModel.detectedLanguage = ""
                    viewModel.promptText = ""
                    viewModel.resultText = ""
                }
            }
        }
    }
    
    // Translation info view
    private var translationInfoView: some View {
        VStack(spacing: 12) {
            HStack(spacing: 20) {
                VStack(spacing: 4) {
                    Text("From")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                    
                    Text(viewModel.sourceLanguage)
                        .font(.headline)
                }
                .frame(width: 120)
                
                Image(systemName: "arrow.right")
                    .font(.title3)
                    .foregroundColor(.blue)
                
                VStack(spacing: 4) {
                    Text("To")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                    
                    Text(viewModel.targetLanguage)
                        .font(.headline)
                }
                .frame(width: 120)
                
                Divider()
                    .frame(height: 30)
                
                VStack(spacing: 4) {
                    Text("Content Type")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                    
                    Text(viewModel.selectedType?.rawValue ?? "Text")
                        .font(.headline)
                }
                .frame(width: 120)
            }
            
            VStack(spacing: 6) {
                HStack {
                    Image(systemName: "server.rack")
                        .foregroundColor(.blue)
                    
                    Text("Powered by \(viewModel.selectedProvider.rawValue)")
                        .font(.footnote)
                        .foregroundColor(.secondary)
                    
                    Spacer()
                }
                .padding(.leading, 8)
            }
        }
        .padding()
        .background(Color.blue.opacity(0.05))
        .cornerRadius(12)
    }
    
    // Result text view
    private var resultTextView: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text("Translation Result")
                    .font(.headline)
                
                Spacer()
                
                Button(action: {
                    showingPrompt = true
                }) {
                    Text("View Prompt")
                        .font(.caption)
                        .foregroundColor(.blue)
                }
                .buttonStyle(PlainButtonStyle())
            }
            
            ScrollView {
                VStack(spacing: 16) {
                    // Try to parse the result as JSON
                    if let jsonData = viewModel.resultText.data(using: .utf8),
                       let json = try? JSONSerialization.jsonObject(with: jsonData, options: []) as? [String: Any],
                       let translation = json["translation"] as? [String: Any] {
                        
                        // Extracted translation text
                        if let text = translation["text"] as? String {
                            VStack(alignment: .leading, spacing: 12) {
                                Text("Translated Text:")
                                    .font(.subheadline)
                                    .foregroundColor(.secondary)
                                
                                Text(text)
                                    .padding()
                                    .frame(maxWidth: .infinity, alignment: .leading)
                                    .background(Color.blue.opacity(0.05))
                                    .cornerRadius(8)
                                    .overlay(
                                        RoundedRectangle(cornerRadius: 8)
                                            .stroke(Color.blue.opacity(0.2), lineWidth: 1)
                                    )
                            }
                        }
                        
                        // Additional information
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Translation Metadata:")
                                .font(.subheadline)
                                .foregroundColor(.secondary)
                            
                            // Source language
                            HStack {
                                Text("Source Language:")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                                    .frame(width: 120, alignment: .leading)
                                
                                Text(translation["original_language"] as? String ?? "Unknown")
                                    .font(.caption)
                                    .fontWeight(.medium)
                            }
                            
                            // Target language
                            HStack {
                                Text("Target Language:")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                                    .frame(width: 120, alignment: .leading)
                                
                                Text(translation["target_language"] as? String ?? "Unknown")
                                    .font(.caption)
                                    .fontWeight(.medium)
                            }
                            
                            // Notes if available
                            if let notes = translation["notes"] as? String {
                                HStack(alignment: .top) {
                                    Text("Notes:")
                                        .font(.caption)
                                        .foregroundColor(.secondary)
                                        .frame(width: 120, alignment: .leading)
                                    
                                    Text(notes)
                                        .font(.caption)
                                        .foregroundColor(.secondary)
                                        .fixedSize(horizontal: false, vertical: true)
                                }
                            }
                        }
                        .padding()
                        .background(Color.gray.opacity(0.05))
                        .cornerRadius(8)
                    } else {
                        // Fallback for non-JSON or unexpected format
                        Text(viewModel.resultText)
                            .padding()
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .background(Color.gray.opacity(0.05))
                            .cornerRadius(8)
                            .overlay(
                                RoundedRectangle(cornerRadius: 8)
                                    .stroke(Color.gray.opacity(0.2), lineWidth: 1)
                            )
                    }
                }
                .padding(.vertical, 8)
            }
            .frame(height: 300)
        }
        .frame(maxWidth: 800)
    }
    
    // Action button
    private func actionButton(title: String, icon: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            VStack(spacing: 8) {
                Image(systemName: icon)
                    .font(.title3)
                
                Text(title)
                    .font(.caption)
            }
            .frame(width: 100, height: 70)
            .background(Color.blue.opacity(0.1))
            .foregroundColor(.blue)
            .cornerRadius(8)
        }
        .buttonStyle(PlainButtonStyle())
    }
    
    // Prompt sheet view
    private var promptSheetView: some View {
        VStack(spacing: 20) {
            HStack {
                Text("Translation Prompt")
                    .font(.headline)
                
                Spacer()
                
                Button(action: {
                    showingPrompt = false
                }) {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundColor(.gray)
                }
                .buttonStyle(PlainButtonStyle())
            }
            
            Text("This is the prompt sent to the AI model:")
                .font(.subheadline)
                .foregroundColor(.secondary)
            
            ScrollView {
                Text(viewModel.promptText)
                    .font(.system(.body, design: .monospaced))
                    .padding()
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Color.blue.opacity(0.05))
                    .cornerRadius(8)
            }
            
            HStack {
                Spacer()
                
                Button(action: {
                    let pasteboard = NSPasteboard.general
                    pasteboard.clearContents()
                    pasteboard.setString(viewModel.promptText, forType: .string)
                }) {
                    HStack {
                        Image(systemName: "doc.on.doc")
                        Text("Copy Prompt")
                    }
                    .padding(.horizontal, 20)
                    .padding(.vertical, 8)
                    .background(Color.blue)
                    .foregroundColor(.white)
                    .cornerRadius(6)
                }
                .buttonStyle(PlainButtonStyle())
            }
        }
        .padding()
        .frame(width: 600, height: 400)
    }
}