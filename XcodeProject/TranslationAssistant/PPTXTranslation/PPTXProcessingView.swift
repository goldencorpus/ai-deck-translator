import SwiftUI

/// A view for processing and displaying PPTX translation
struct PPTXProcessingView: View {
    @ObservedObject var viewModel: TranslationViewModel
    @State private var extractingText = false
    @State private var translatingText = false
    @State private var updatingFile = false
    @State private var progress = 0.0
    @State private var errorMessage: String?
    @State private var extractedSlideCount = 0
    @State private var translatedSlideCount = 0
    @State private var outputFileURL: URL?
    
    var body: some View {
        VStack(spacing: 20) {
            Text("PPTX Translation")
                .font(.largeTitle)
                .fontWeight(.bold)
            
            // File information
            if let url = viewModel.sourceFile {
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
                }
                .padding()
                .background(Color.blue.opacity(0.1))
                .cornerRadius(10)
            }
            
            // Progress view
            VStack {
                ProgressView(value: progress)
                    .padding(.vertical)
                
                Text(progressText())
                    .font(.headline)
            }
            .padding()
            
            // Status indicators
            VStack(alignment: .leading, spacing: 10) {
                HStack {
                    Image(systemName: extractingText ? "circle.dashed" : (extractedSlideCount > 0 ? "checkmark.circle.fill" : "circle"))
                        .foregroundColor(extractingText ? .orange : (extractedSlideCount > 0 ? .green : .gray))
                    Text("Extracting text from presentation")
                        .foregroundColor(extractingText ? .primary : (extractedSlideCount > 0 ? .primary : .secondary))
                }
                
                HStack {
                    Image(systemName: translatingText ? "circle.dashed" : (translatedSlideCount > 0 ? "checkmark.circle.fill" : "circle"))
                        .foregroundColor(translatingText ? .orange : (translatedSlideCount > 0 ? .green : .gray))
                    Text("Translating content")
                        .foregroundColor(translatingText ? .primary : (translatedSlideCount > 0 ? .primary : .secondary))
                }
                
                HStack {
                    Image(systemName: updatingFile ? "circle.dashed" : (outputFileURL != nil ? "checkmark.circle.fill" : "circle"))
                        .foregroundColor(updatingFile ? .orange : (outputFileURL != nil ? .green : .gray))
                    Text("Creating translated presentation")
                        .foregroundColor(updatingFile ? .primary : (outputFileURL != nil ? .primary : .secondary))
                }
            }
            .padding()
            
            // Actions
            if outputFileURL != nil {
                VStack(spacing: 10) {
                    Button(action: {
                        // Open the output file in Finder
                        NSWorkspace.shared.activateFileViewerSelecting([outputFileURL!])
                    }) {
                        Label("Open in Finder", systemImage: "folder")
                            .frame(minWidth: 200)
                    }
                    .buttonStyle(.borderedProminent)
                    
                    Button(action: {
                        // Open the output file with PowerPoint
                        NSWorkspace.shared.open(outputFileURL!)
                    }) {
                        Label("Open Presentation", systemImage: "doc.fill")
                            .frame(minWidth: 200)
                    }
                    .buttonStyle(.bordered)
                }
            } else {
                Button(action: startProcessing) {
                    Label(
                        extractingText || translatingText || updatingFile ? "Processing..." : "Start Translation",
                        systemImage: extractingText || translatingText || updatingFile ? "hourglass" : "play.fill"
                    )
                    .frame(minWidth: 200)
                }
                .buttonStyle(.borderedProminent)
                .disabled(extractingText || translatingText || updatingFile)
            }
            
            // Error message
            if let error = errorMessage {
                Text(error)
                    .foregroundColor(.red)
                    .padding()
                    .multilineTextAlignment(.center)
            }
            
            Spacer()
        }
        .padding()
        .frame(maxWidth: 700)
    }
    
    private func progressText() -> String {
        if extractingText {
            return "Extracting text... (\(extractedSlideCount) slides found)"
        } else if translatingText {
            return "Translating content... (\(translatedSlideCount)/\(extractedSlideCount) slides)"
        } else if updatingFile {
            return "Creating translated presentation..."
        } else if outputFileURL != nil {
            return "Translation complete!"
        } else {
            return "Ready to start"
        }
    }
    
    private func startProcessing() {
        guard let fileURL = viewModel.sourceFile else {
            errorMessage = "No file selected"
            return
        }
        
        extractingText = true
        progress = 0.1
        errorMessage = nil
        
        // Extract text from PPTX file
        PPTXHandler.shared.extractText(from: fileURL)
            .receive(on: DispatchQueue.main)
            .sink(
                receiveCompletion: { completion in
                    extractingText = false
                    if case .failure(let error) = completion {
                        errorMessage = "Failed to extract text: \(error.localizedDescription)"
                        progress = 0
                    }
                },
                receiveValue: { result in
                    let textElements = result.textElements
                    let metadata = result.metadata
                    
                    // Update the progress
                    extractedSlideCount = (metadata["slides"] as? [[String: Any]])?.count ?? 0
                    progress = 0.3
                    
                    // Start translation
                    translateContent(textElements: textElements, metadata: metadata)
                }
            )
            .store(in: &viewModel.translationService.cancellables)
    }
    
    private func translateContent(textElements: [String: String], metadata: [String: Any]) {
        translatingText = true
        
        // Get source and target languages
        let sourceLanguage = viewModel.sourceLanguage.isEmpty ? "English" : viewModel.sourceLanguage
        let targetLanguage = viewModel.targetLanguage.isEmpty ? "French" : viewModel.targetLanguage
        
        // Translate the content
        PPTXHandler.shared.translateContent(
            textElements: textElements,
            sourceLanguage: sourceLanguage,
            targetLanguage: targetLanguage
        )
        .receive(on: DispatchQueue.main)
        .sink(
            receiveCompletion: { completion in
                translatingText = false
                if case .failure(let error) = completion {
                    errorMessage = "Translation failed: \(error.localizedDescription)"
                    progress = 0.3  // Reset to extraction completion
                }
            },
            receiveValue: { translatedElements in
                // Update progress
                translatedSlideCount = extractedSlideCount
                progress = 0.7
                
                // Update the PPTX with translations
                updatePresentationWithTranslations(translatedElements: translatedElements, targetLanguage: targetLanguage)
            }
        )
        .store(in: &viewModel.translationService.cancellables)
    }
    
    private func updatePresentationWithTranslations(translatedElements: [String: String], targetLanguage: String) {
        guard let fileURL = viewModel.sourceFile else {
            errorMessage = "File not found"
            return
        }
        
        updatingFile = true
        
        PPTXHandler.shared.updatePPTX(
            fileURL: fileURL,
            translatedElements: translatedElements,
            targetLanguage: targetLanguage
        )
        .receive(on: DispatchQueue.main)
        .sink(
            receiveCompletion: { completion in
                updatingFile = false
                if case .failure(let error) = completion {
                    errorMessage = "Failed to create translated file: \(error.localizedDescription)"
                    progress = 0.7  // Reset to translation completion
                }
            },
            receiveValue: { url in
                outputFileURL = url
                progress = 1.0
                
                // Log success
                AppLogger.log(.info, message: "Successfully created translated PPTX at \(url.path)")
            }
        )
        .store(in: &viewModel.translationService.cancellables)
    }
}