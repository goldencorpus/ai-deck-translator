import SwiftUI
import UniformTypeIdentifiers
import NaturalLanguage
import Combine
import AppKit
import OSLog
import Foundation

enum TranslationStep {
    case selectType
    case apiKeyQuestion
    case apiKeyManagement
    case cloudPermission
    case contentInput
    case confirmLanguages
    case result
    case settings
}

enum TranslationType: String, CaseIterable, Identifiable {
    case text = "Text"
    case file = "File"
    case image = "Image"
    
    var id: String { self.rawValue }
    
    var icon: String {
        switch self {
        case .text: return "text.alignleft"
        case .file: return "doc.fill"
        case .image: return "photo.fill"
        }
    }
    
    var description: String {
        switch self {
        case .text: return "Translate text paragraphs or snippets"
        case .file: return "Translate documents (PDF, PPTX, DOCX, etc.)"
        case .image: return "Extract and translate text from images"
        }
    }
}

class TranslationViewModel: ObservableObject {
    // Step management
    @Published var currentStep: TranslationStep = .selectType
    
    // Translation type selection
    @Published var selectedType: TranslationType?
    
    // API key management
    @Published var hasApiKey: Bool?
    @Published var apiKey: String = ""
    @Published var selectedProvider: LLMProvider {
        didSet {
            // When provider changes, load its API key if available
            if let savedKey = translationService.getAPIKey(for: selectedProvider) {
                apiKey = savedKey
            } else {
                apiKey = ""
            }
        }
    }
    
    // Cloud permission
    @Published var allowCloudUpload: Bool?
    
    // Content input
    @Published var sourceText: String = ""
    @Published var sourceLanguage: String = ""
    @Published var targetLanguage: String = ""
    @Published var detectedLanguage: String = ""
    
    @Published var sourceFile: URL?
    @Published var sourceImage: NSImage?
    
    // Result
    @Published var promptText: String = ""
    @Published var resultText: String = ""
    
    // Processing state
    @Published var isProcessing: Bool = false
    @Published var errorMessage: String?
    @Published var showLogFileUrl: URL?
    
    // Cancellables set for Combine
    var cancellables = Set<AnyCancellable>()
    
    // Translation service
    let translationService = TranslationService.shared
    
    init() {
        // Set the initial value before using the property observers
        _selectedProvider = Published(initialValue: translationService.selectedProvider)
        
        // Check if we already have any API keys
        let hasAnyKeys = LLMProvider.allCases.contains { provider in
            translationService.hasValidAPIKey(for: provider)
        }
        
        // If we have a key for the selected provider, pre-populate it
        if let existingKey = translationService.getAPIKey(for: selectedProvider) {
            self.apiKey = existingKey
        }
        
        // If we already have an API key stored, we can skip the question
        if hasAnyKeys {
            self.hasApiKey = true
        }
    }
    
    // Step management
    func selectType(_ type: TranslationType) {
        self.selectedType = type
        
        // Ensure we have a provider with a valid key selected before proceeding
        translationService.ensureValidProviderIsSelected()
        selectedProvider = translationService.selectedProvider
        
        // Log the selected type and provider
        AppLogger.log(.info, message: "Selected translation type: \(type.rawValue)")
        AppLogger.log(.info, message: "Using provider: \(selectedProvider.rawValue) with valid key: \(translationService.hasValidAPIKey(for: selectedProvider))")
        
        moveToNextStep()
    }
    
    func setApiKeyAvailability(_ hasKey: Bool) {
        self.hasApiKey = hasKey
        
        if hasKey {
            // If they have a key, go to the API key management step
            
            // Check if we already have a key for the selected provider
            if let existingKey = translationService.getAPIKey(for: selectedProvider) {
                // Pre-populate the text field with the saved key
                apiKey = existingKey
            }
            
            currentStep = .apiKeyManagement
        } else {
            // If they don't have a key, skip the API key management
            currentStep = .cloudPermission
        }
    }
    
    func saveAPIKey() {
        AppLogger.log(.info, message: "Saving API key for provider: \(selectedProvider.rawValue)")
        if !apiKey.isEmpty {
            AppLogger.log(.debug, message: "API key is not empty, saving key of length: \(apiKey.count)")
            translationService.setAPIKey(apiKey, for: selectedProvider)
        } else {
            AppLogger.log(.error, message: "Attempted to save empty API key for \(selectedProvider.rawValue)")
        }
    }
    
    func setCloudPermission(_ allowed: Bool) {
        self.allowCloudUpload = allowed
        translationService.allowCloudProcessing = allowed
        moveToNextStep()
    }
    
    func submitContent() {
        detectLanguage()
        moveToNextStep()
    }
    
    func confirmLanguages() {
        createPrompt()
        moveToNextStep()
    }
    
    func moveToNextStep() {
        switch currentStep {
        case .selectType:
            // For ALL translation types, check if we have any valid API keys
            // If we do, skip the API key question and management steps
            if LLMProvider.allCases.contains(where: { translationService.hasValidAPIKey(for: $0) }) {
                // Ensure a provider with a valid key is selected
                translationService.ensureValidProviderIsSelected()
                
                // Update selected provider to match service
                selectedProvider = translationService.selectedProvider
                
                // Skip API key steps completely
                currentStep = .cloudPermission
                hasApiKey = true
                
                AppLogger.log(.info, message: "Found valid API key, skipping API key steps")
            } else {
                currentStep = .apiKeyQuestion
                AppLogger.log(.info, message: "No valid API keys found, showing API key question")
            }
        case .apiKeyQuestion:
            // apiKeyQuestion now handles navigation logic in setApiKeyAvailability
            break
        case .apiKeyManagement:
            currentStep = .cloudPermission
        case .cloudPermission:
            currentStep = .contentInput
        case .contentInput:
            currentStep = .confirmLanguages
        case .confirmLanguages:
            currentStep = .result
            translate()
        case .result:
            // This is the final step
            break
        case .settings:
            // If returning from settings, go back to select type
            currentStep = .selectType
            break
        }
    }
    
    func goBack() {
        switch currentStep {
        case .selectType:
            // Already at first step
            break
        case .apiKeyQuestion:
            currentStep = .selectType
            selectedType = nil
        case .apiKeyManagement:
            currentStep = .apiKeyQuestion
            hasApiKey = nil
        case .cloudPermission:
            if hasApiKey == true {
                currentStep = .apiKeyManagement
            } else {
                currentStep = .apiKeyQuestion
            }
        case .contentInput:
            currentStep = .cloudPermission
            allowCloudUpload = nil
        case .confirmLanguages:
            currentStep = .contentInput
            detectedLanguage = ""
        case .result:
            currentStep = .confirmLanguages
            promptText = ""
            resultText = ""
        case .settings:
            // Return to the previous meaningful step or home
            if sourceText.isEmpty && sourceFile == nil && sourceImage == nil {
                currentStep = .selectType
            } else {
                currentStep = .contentInput
            }
        }
    }
    
    // Processing logic
    func detectLanguage() {
        guard let text = getContentText() else {
            detectedLanguage = "Unknown"
            return
        }
        
        let languageRecognizer = NLLanguageRecognizer()
        languageRecognizer.processString(text)
        
        if let language = languageRecognizer.dominantLanguage {
            let locale = Locale.current
            if let languageName = locale.localizedString(forIdentifier: language.rawValue) {
                detectedLanguage = languageName
                sourceLanguage = languageName
            } else {
                detectedLanguage = language.rawValue
                sourceLanguage = language.rawValue
            }
        } else {
            detectedLanguage = "Unknown"
        }
    }
    
    func getContentText() -> String? {
        switch selectedType {
        case .text:
            return sourceText
            
        case .file:
            guard let fileURL = sourceFile else { return nil }
            
            // Extract text based on file type
            let fileExtension = fileURL.pathExtension.lowercased()
            
            // Special handling for PPTX files using our dedicated handler
            if fileExtension == "pptx" {
                return PPTXHandler.shared.extractPPTXContent(from: fileURL)
            }
            
            // Provide information about the file
            let fileName = fileURL.lastPathComponent
            let fileInfo = """
            File information:
            - Name: \(fileName)
            - Type: \(fileExtension.uppercased())
            - Size: \(getFileSizeString(for: fileURL))
            """
            
            // Try to read the file content
            do {
                // For simple text-based files
                if ["txt", "rtf", "md"].contains(fileExtension) {
                    let fileContent = try String(contentsOf: fileURL, encoding: .utf8)
                    return "\(fileInfo)\n\nFile content:\n\(fileContent)"
                }
                
                // For other file types that we can't directly read,
                // just provide file info and let the user know
                return "\(fileInfo)\n\n[This is a \(fileExtension.uppercased()) file. In a production app, we would extract text using PDFKit, Office document parsers, etc.]"
            } catch {
                return "\(fileInfo)\n\nUnable to read file content: \(error.localizedDescription)"
            }
            
        case .image:
            guard let image = sourceImage else { return nil }
            
            // Provide information about the image
            let imageInfo = """
            Image information:
            - Size: \(Int(image.size.width))×\(Int(image.size.height)) pixels
            - Format: \(image.tiffRepresentation != nil ? "TIFF/JPG/PNG" : "Unknown")
            """
            
            // In a real app, we would use Vision framework for OCR
            // For now, we'll simulate OCR with a placeholder
            return "\(imageInfo)\n\n[This is an image. In a production app, we would use Vision framework to extract text using OCR.]"
            
        case nil:
            return nil
        }
    }
    
    // Helper to get formatted file size
    private func getFileSizeString(for url: URL) -> String {
        do {
            let resourceValues = try url.resourceValues(forKeys: [.fileSizeKey])
            if let fileSize = resourceValues.fileSize {
                if fileSize < 1024 {
                    return "\(fileSize) bytes"
                } else if fileSize < 1024 * 1024 {
                    let kbSize = Double(fileSize) / 1024.0
                    return String(format: "%.1f KB", kbSize)
                } else {
                    let mbSize = Double(fileSize) / (1024.0 * 1024.0)
                    return String(format: "%.1f MB", mbSize)
                }
            }
        } catch {
            // Ignore errors and just return Unknown
        }
        return "Unknown size"
    }
    
    // Get log file URL for debugging
    func getLogFileURL() {
        AppLogger.log(.info, message: "Getting log file URL for debugging")
        
        // Use the specified fixed path for the log file
        let logFileURL = URL(fileURLWithPath: "/Users/eprouveze/Documents/Dev/App/TranslationAssistantFinal/translation_assistant.log")
        let fileManager = FileManager.default
        
        if fileManager.fileExists(atPath: logFileURL.path) {
            showLogFileUrl = logFileURL
            AppLogger.log(.info, message: "Log file exists at \(logFileURL.path)")
        } else {
            AppLogger.log(.error, message: "Log file does not exist at \(logFileURL.path)")
        }
    }
    
    func createPrompt() {
        guard let contentText = getContentText() else { return }
        
        // Check if this is a PPTX file
        if selectedType == .file, 
            let fileURL = sourceFile,
            fileURL.pathExtension.lowercased() == "pptx" {
            
            // Use specialized PPTX prompt
            promptText = PPTXHandler.shared.createPPTXPrompt(
                sourceText: contentText,
                sourceLanguage: sourceLanguage,
                targetLanguage: targetLanguage
            )
            return
        }
        
        // Standard prompt for other content types
        let promptTemplate = """
        {
          "task": "translation",
          "source_language": "\(sourceLanguage)",
          "target_language": "\(targetLanguage)",
          "content_type": "\(selectedType?.rawValue ?? "Text")",
          "content": \"\"\"\(contentText.replacingOccurrences(of: "\"\"\"", with: "\\\"\\\"\\\""))\"\"\",
          "instructions": "Please translate the provided content from \(sourceLanguage) to \(targetLanguage), maintaining the original formatting and structure as much as possible. Ensure the translation is accurate and natural-sounding in the target language."
        }
        """
        
        promptText = promptTemplate
    }
    
    func translate() {
        isProcessing = true
        errorMessage = nil
        
        AppLogger.log(.info, message: "Starting translation in ViewModel")
        AppLogger.log(.debug, message: "allowCloudUpload: \(allowCloudUpload == true), hasApiKey: \(hasApiKey == true)")
        
        // Check and auto-select valid provider
        translationService.ensureValidProviderIsSelected()
        
        // Update UI to show which provider is being used
        selectedProvider = translationService.selectedProvider
        
        AppLogger.log(.debug, message: "Selected provider: \(translationService.selectedProvider.rawValue)")
        
        // Also log if the service thinks we have a valid key
        let hasValidKey = translationService.hasValidAPIKey(for: translationService.selectedProvider)
        AppLogger.log(.debug, message: "Service reports valid API key: \(hasValidKey)")
        
        if allowCloudUpload == true && (hasApiKey == true || hasValidKey) {
            // Use the translation service
            AppLogger.log(.info, message: "Using translation service to translate")
            translationService.translate(prompt: promptText)
                .receive(on: DispatchQueue.main)
                .sink(receiveCompletion: { [weak self] completion in
                    self?.isProcessing = false
                    
                    if case .failure(let error) = completion {
                        AppLogger.log(.error, message: "Translation failed with error: \(error)")
                        switch error {
                        case .invalidAPIKey:
                            AppLogger.log(.error, message: "Invalid API key error")
                            self?.errorMessage = "Invalid or missing API key for \(self?.translationService.selectedProvider.rawValue ?? "selected provider"). Please go to Settings to add a valid API key."
                            
                            // Switch to API key management when the error occurs to help the user fix it
                            DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
                                self?.currentStep = .apiKeyManagement
                            }
                            
                            self?.getLogFileURL()
                        case .networkError(let underlying):
                            AppLogger.log(.error, message: "Network error: \(underlying)")
                            self?.errorMessage = "Network error. Please check your internet connection and try again."
                        case .invalidResponse:
                            AppLogger.log(.error, message: "Invalid response error")
                            self?.errorMessage = "Invalid response from the API. Please try again."
                        case .decodingError(let underlying):
                            AppLogger.log(.error, message: "Decoding error: \(underlying)")
                            self?.errorMessage = "Error processing the response. Please try again."
                        case .apiError(let message):
                            AppLogger.log(.error, message: "API error: \(message)")
                            self?.errorMessage = "API error: \(message)"
                        case .noCloudPermission:
                            AppLogger.log(.error, message: "No cloud permission error")
                            self?.errorMessage = "Cloud processing is not allowed. Please enable cloud processing in settings."
                        case .keychainError:
                            AppLogger.log(.error, message: "Keychain error")
                            self?.errorMessage = "Error accessing the secure storage. Please try again."
                        }
                    } else {
                        AppLogger.log(.info, message: "Translation completed successfully")
                    }
                }, receiveValue: { [weak self] result in
                    AppLogger.log(.info, message: "Received translation result of length: \(result.count)")
                    self?.resultText = result
                })
                .store(in: &cancellables)
        } else {
            // Simulate a response for local processing or no API key
            DispatchQueue.main.asyncAfter(deadline: .now() + 2) { [weak self] in
                guard let self = self else { return }
                
                if self.allowCloudUpload == false {
                    self.resultText = """
                    {
                      "message": "Cloud processing is disabled. To translate your content, please use the following prompt with an LLM of your choice:",
                      "prompt": \(self.promptText)
                    }
                    """
                } else if self.hasApiKey == false {
                    self.resultText = """
                    {
                      "message": "No API key provided. To translate your content, please use the following prompt with an LLM of your choice:",
                      "prompt": \(self.promptText)
                    }
                    """
                }
                
                self.isProcessing = false
            }
        }
    }
}