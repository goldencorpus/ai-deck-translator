import Foundation
import Combine
import Security
import OSLog

// Simple logger for the translation service
class AppLogger {
    private static let subsystem = "com.translationassistant"
    static let service = OSLog(subsystem: subsystem, category: "TranslationService")
    
    static func log(_ level: OSLogType, message: String, file: String = #file, function: String = #function, line: Int = #line) {
        let fileName = (file as NSString).lastPathComponent
        let logMessage = "\(fileName):\(line) - \(function) - \(message)"
        os_log("%{public}@", log: service, type: level, logMessage)
        
        // Also write to a log file
        writeToLogFile(message: "[\(levelString(level))] \(logMessage)")
    }
    
    private static func levelString(_ level: OSLogType) -> String {
        switch level {
        case .debug: return "DEBUG"
        case .info: return "INFO"
        case .default: return "DEFAULT"
        case .error: return "ERROR"
        case .fault: return "FAULT"
        default: return "UNKNOWN"
        }
    }
    
    private static func writeToLogFile(message: String) {
        // Use the specified fixed path for the log file
        let logFileURL = URL(fileURLWithPath: "/Users/eprouveze/Documents/Dev/App/TranslationAssistantFinal/translation_assistant.log")
        
        let timestamp = ISO8601DateFormatter().string(from: Date())
        let logEntry = "[\(timestamp)] \(message)\n"
        
        do {
            let fileManager = FileManager.default
            if fileManager.fileExists(atPath: logFileURL.path) {
                let fileHandle = try FileHandle(forWritingTo: logFileURL)
                fileHandle.seekToEndOfFile()
                if let data = logEntry.data(using: .utf8) {
                    fileHandle.write(data)
                }
                fileHandle.closeFile()
            } else {
                try logEntry.write(to: logFileURL, atomically: true, encoding: .utf8)
            }
        } catch {
            // We can't log to the log file, so just print to console
            print("Error writing to log file: \(error)")
            print(logEntry)
        }
    }
    
}

enum LLMProvider: String, CaseIterable, Identifiable {
    case openAI = "OpenAI"
    case anthropic = "Anthropic (Claude)"
    case googleAI = "Google AI (Gemini)"
    case localModel = "Local Model"
    
    var id: String { self.rawValue }
    
    var baseURL: URL {
        switch self {
        case .openAI:
            return URL(string: "https://api.openai.com/v1/chat/completions")!
        case .anthropic:
            return URL(string: "https://api.anthropic.com/v1/messages")!
        case .googleAI:
            return URL(string: "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent")!
        case .localModel:
            // This would be a localhost URL if running a local model
            return URL(string: "http://localhost:8000/generate")!
        }
    }
    
    var requiresKey: Bool {
        // Local models might not require API keys if self-hosted
        return self != .localModel
    }
    
    // Define a keychain service name for each provider
    var keychainService: String {
        return "com.translationassistant.\(self.rawValue.lowercased().replacingOccurrences(of: " ", with: "_"))"
    }
}

enum TranslationServiceError: Error {
    case invalidAPIKey
    case networkError(Error)
    case invalidResponse
    case decodingError(Error)
    case apiError(String)
    case noCloudPermission
    case keychainError
}

// Keychain manager to securely store API keys
class KeychainManager {
    static func save(key: String, for provider: LLMProvider) -> Bool {
        let service = provider.keychainService
        let account = "apikey"
        
        // Delete any existing key first
        _ = deleteKey(for: provider)
        
        guard let data = key.data(using: .utf8) else { return false }
        
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecValueData as String: data
        ]
        
        let status = SecItemAdd(query as CFDictionary, nil)
        return status == errSecSuccess
    }
    
    static func loadKey(for provider: LLMProvider) -> String? {
        // Log loading attempt
        AppLogger.log(.info, message: "Attempting to load key for \(provider.rawValue) from keychain")
        
        let service = provider.keychainService
        let account = "apikey"
        
        // Development mode would use a stored key from environment or local config
        // No hardcoded keys in source code for security reasons
        
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne
        ]
        
        var dataTypeRef: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &dataTypeRef)
        
        if status == errSecSuccess, let data = dataTypeRef as? Data {
            let key = String(data: data, encoding: .utf8)
            AppLogger.log(.info, message: "Successfully loaded key for \(provider.rawValue) from keychain")
            return key
        } else {
            AppLogger.log(.error, message: "Failed to load key for \(provider.rawValue) from keychain, status: \(status)")
        }
        
        return nil
    }
    
    static func deleteKey(for provider: LLMProvider) -> Bool {
        let service = provider.keychainService
        let account = "apikey"
        
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account
        ]
        
        let status = SecItemDelete(query as CFDictionary)
        return status == errSecSuccess || status == errSecItemNotFound
    }
}

class TranslationService {
    // Singleton instance
    static let shared = TranslationService()
    
    // A key for UserDefaults to store the selected provider
    private let selectedProviderKey = "selectedLLMProvider"
    private let cloudProcessingKey = "allowCloudProcessing"
    
    private init() {
        // First load API keys from keychain to memory cache
        // This needs to happen before attempting to select a provider
        for provider in LLMProvider.allCases {
            if let key = KeychainManager.loadKey(for: provider) {
                apiKeys[provider] = key
                AppLogger.log(.info, message: "Loaded key from keychain for \(provider.rawValue)")
            } else {
                AppLogger.log(.info, message: "No key found in keychain for \(provider.rawValue)")
            }
        }
        
        // Set default provider
        selectedProvider = .anthropic
        
        // Load saved provider preference
        if let savedProviderString = UserDefaults.standard.string(forKey: selectedProviderKey),
           let savedProvider = LLMProvider.allCases.first(where: { $0.rawValue == savedProviderString }) {
            selectedProvider = savedProvider
            AppLogger.log(.info, message: "Loaded saved provider preference: \(savedProvider.rawValue)")
        }
        
        // Load saved cloud processing preference
        if UserDefaults.standard.object(forKey: cloudProcessingKey) != nil {
            allowCloudProcessing = UserDefaults.standard.bool(forKey: cloudProcessingKey)
        }
        
        // Log loaded keys
        for provider in LLMProvider.allCases {
            if let key = apiKeys[provider] {
                AppLogger.log(.info, message: "API key loaded for \(provider.rawValue), length: \(key.count)")
            }
        }
        
        // Auto-select a provider with a valid key if current provider doesn't have one
        // Delay this to ensure all initialization is complete
        DispatchQueue.main.async {
            self.ensureValidProviderIsSelected()
        }
    }
    
    // Auto-select a provider with a valid key
    func ensureValidProviderIsSelected() {
        AppLogger.log(.info, message: "Checking if currently selected provider has a valid key...")
        
        // Log all available keys
        for provider in LLMProvider.allCases {
            let hasKey = apiKeys[provider] != nil
            AppLogger.log(.info, message: "Provider \(provider.rawValue) has key in memory: \(hasKey)")
        }
        
        // First, try to use Anthropic (Claude) if it has a valid key, as it's our preferred provider
        let preferredProviders: [LLMProvider] = [.anthropic, .openAI, .googleAI, .localModel]
        
        for provider in preferredProviders {
            if hasValidAPIKey(for: provider) {
                AppLogger.log(.info, message: "Auto-selecting provider \(provider.rawValue) which has a valid key")
                selectedProvider = provider
                return
            }
        }
        
        // If the current provider has a valid key, we're good
        if hasValidAPIKey(for: selectedProvider) {
            AppLogger.log(.info, message: "Current provider (\(selectedProvider.rawValue)) has a valid key")
            return
        }
        
        // If we get here, no provider has a valid key
        // Force select Anthropic as default even without key
        AppLogger.log(.error, message: "No provider has a valid API key, defaulting to Anthropic")
        selectedProvider = .anthropic
    }
    
    // Selected LLM provider with persistence
    var selectedProvider: LLMProvider = .anthropic {
        didSet {
            UserDefaults.standard.set(selectedProvider.rawValue, forKey: selectedProviderKey)
        }
    }
    
    // API Key storage in memory with keychain backup
    private var apiKeys: [LLMProvider: String] = [:]
    
    // Store the user's cloud permission with persistence
    var allowCloudProcessing: Bool = true {
        didSet {
            UserDefaults.standard.set(allowCloudProcessing, forKey: cloudProcessingKey)
        }
    }
    
    // Set API key for provider and save to keychain
    func setAPIKey(_ key: String, for provider: LLMProvider) {
        AppLogger.log(.info, message: "Setting API key for provider: \(provider.rawValue)")
        apiKeys[provider] = key
        let saved = KeychainManager.save(key: key, for: provider)
        AppLogger.log(.info, message: "API key saved to keychain: \(saved)")
    }
    
    // Get API key for provider from memory cache or keychain
    func getAPIKey(for provider: LLMProvider) -> String? {
        AppLogger.log(.debug, message: "Getting API key for provider: \(provider.rawValue)")
        
        // Check memory cache first
        if let key = apiKeys[provider] {
            AppLogger.log(.info, message: "Found API key in memory cache for \(provider.rawValue)")
            return key
        }
        
        // Try loading from keychain if not in memory
        if let key = KeychainManager.loadKey(for: provider) {
            AppLogger.log(.info, message: "Loaded API key from keychain for \(provider.rawValue)")
            apiKeys[provider] = key // Cache for future use
            return key
        }
        
        AppLogger.log(.info, message: "No API key found for \(provider.rawValue)")
        return nil
    }
    
    // Remove API key for provider
    func removeAPIKey(for provider: LLMProvider) -> Bool {
        apiKeys.removeValue(forKey: provider)
        return KeychainManager.deleteKey(for: provider)
    }
    
    // Check if we have a valid API key
    func hasValidAPIKey(for provider: LLMProvider) -> Bool {
        AppLogger.log(.debug, message: "Checking for valid API key for provider: \(provider.rawValue)")
        guard let key = getAPIKey(for: provider), !key.isEmpty else {
            AppLogger.log(.info, message: "No valid API key found for \(provider.rawValue)")
            return false
        }
        // Log key length and first/last few characters for debugging
        AppLogger.log(.info, message: "API key found for \(provider.rawValue), length: \(key.count)")
        // Basic validation could be expanded
        return true
    }
    
    // Validate API key with a simple network request
    func validateAPIKey(for provider: LLMProvider, key: String) -> AnyPublisher<Bool, TranslationServiceError> {
        AppLogger.log(.info, message: "Validating API key for provider: \(provider.rawValue)")
        // First save the key to use it in the request
        let originalKey = getAPIKey(for: provider)
        AppLogger.log(.debug, message: "Original key present: \(originalKey != nil)")
        setAPIKey(key, for: provider)
        
        // Create a simple request to test API key validity
        var request = URLRequest(url: provider.baseURL)
        request.httpMethod = "POST"
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")
        
        // Add authentication headers based on provider
        switch provider {
        case .openAI:
            request.addValue("Bearer \(key)", forHTTPHeaderField: "Authorization")
        case .anthropic:
            // Anthropic API requires the x-api-key header, not Authorization
            request.addValue("\(key)", forHTTPHeaderField: "x-api-key")
            request.addValue("2023-06-01", forHTTPHeaderField: "anthropic-version")
            
            // Log headers for debugging
            AppLogger.log(.debug, message: "Anthropic API headers: \(request.allHTTPHeaderFields ?? [:])")
        case .googleAI:
            request.url = URL(string: "\(provider.baseURL)?key=\(key)")
        case .localModel:
            request.addValue("Bearer \(key)", forHTTPHeaderField: "Authorization")
        }
        
        // Create minimal request body
        let requestBody: [String: Any]
        switch provider {
        case .openAI:
            requestBody = [
                "model": "gpt-3.5-turbo",
                "messages": [
                    ["role": "user", "content": "Hello"]
                ],
                "max_tokens": 1
            ]
        case .anthropic:
            requestBody = [
                "model": "claude-3-haiku-20240307",
                "messages": [
                    ["role": "user", "content": "Hello"]
                ],
                "max_tokens": 1
            ]
        case .googleAI:
            requestBody = [
                "contents": [
                    ["parts": [["text": "Hello"]]]
                ],
                "generationConfig": [
                    "maxOutputTokens": 1
                ]
            ]
        case .localModel:
            requestBody = [
                "prompt": "Hello",
                "max_tokens": 1
            ]
        }
        
        // Set request body
        do {
            request.httpBody = try JSONSerialization.data(withJSONObject: requestBody)
        } catch {
            // If original key existed, restore it
            if let originalKey = originalKey {
                setAPIKey(originalKey, for: provider)
            }
            return Just(false)
                .setFailureType(to: TranslationServiceError.self)
                .eraseToAnyPublisher()
        }
        
        // Make the request to validate
        return URLSession.shared.dataTaskPublisher(for: request)
            .tryMap { data, response -> Bool in
                // Restore original key if it existed
                if let originalKey = originalKey {
                    AppLogger.log(.debug, message: "Restoring original key after validation")
                    self.setAPIKey(originalKey, for: provider)
                }
                
                guard let httpResponse = response as? HTTPURLResponse else {
                    AppLogger.log(.error, message: "Invalid HTTP response during key validation")
                    return false
                }
                
                // Check for success status code
                let isValid = httpResponse.statusCode >= 200 && httpResponse.statusCode < 300
                AppLogger.log(.info, message: "API key validation result: \(isValid), status code: \(httpResponse.statusCode)")
                
                // Log response data for debugging
                if !isValid {
                    let responseString = String(data: data, encoding: .utf8) ?? "Unknown error"
                    AppLogger.log(.error, message: "API key validation failed: \(responseString)")
                }
                
                return isValid
            }
            .mapError { error -> TranslationServiceError in
                // Restore original key if it existed
                if let originalKey = originalKey {
                    self.setAPIKey(originalKey, for: provider)
                }
                
                if let error = error as? TranslationServiceError {
                    return error
                }
                return TranslationServiceError.networkError(error)
            }
            .eraseToAnyPublisher()
    }
    
    // Translate using the selected provider
    func translate(prompt: String) -> AnyPublisher<String, TranslationServiceError> {
        // Auto-select a provider with a valid key first
        ensureValidProviderIsSelected()
        
        AppLogger.log(.info, message: "Starting translation with provider: \(selectedProvider.rawValue)")
        AppLogger.log(.debug, message: "Translation prompt: \(prompt)")
        
        // Check cloud permission
        guard allowCloudProcessing else {
            AppLogger.log(.error, message: "Translation failed: No cloud permission")
            return Fail(error: TranslationServiceError.noCloudPermission)
                .eraseToAnyPublisher()
        }
        
        // Check if we have an API key for selected provider
        let apiKeyExists = getAPIKey(for: selectedProvider) != nil
        AppLogger.log(.info, message: "API key exists for \(selectedProvider.rawValue): \(apiKeyExists)")
        
        guard let apiKey = getAPIKey(for: selectedProvider), !apiKey.isEmpty else {
            // If the API key is missing, provide a more detailed error message
            AppLogger.log(.error, message: "Translation failed: Missing API key for \(selectedProvider.rawValue)")
            
            // Log all providers and their key status for diagnostics
            for provider in LLMProvider.allCases {
                let hasKey = getAPIKey(for: provider) != nil
                AppLogger.log(.info, message: "Provider \(provider.rawValue) has API key: \(hasKey)")
            }
            
            return Fail(error: TranslationServiceError.invalidAPIKey)
                .eraseToAnyPublisher()
        }
        
        AppLogger.log(.info, message: "API key found for \(selectedProvider.rawValue), length: \(apiKey.count)")
        
        // Create request based on provider
        var request = URLRequest(url: selectedProvider.baseURL)
        request.httpMethod = "POST"
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")
        
        // Add authentication headers based on provider
        switch selectedProvider {
        case .openAI:
            request.addValue("Bearer \(apiKey)", forHTTPHeaderField: "Authorization")
        case .anthropic:
            // Anthropic API requires the x-api-key header, not Authorization
            request.addValue("\(apiKey)", forHTTPHeaderField: "x-api-key")
            request.addValue("2023-06-01", forHTTPHeaderField: "anthropic-version")
            
            // Also try newer header format as backup
            if !apiKey.hasPrefix("sk-ant-") {
                AppLogger.log(.info, message: "Using alternate Anthropic API key format for compatibility")
                request.addValue("Bearer \(apiKey)", forHTTPHeaderField: "Authorization")
            }
        case .googleAI:
            request.url = URL(string: "\(selectedProvider.baseURL)?key=\(apiKey)")
        case .localModel:
            // Local model might use different auth
            request.addValue("Bearer \(apiKey)", forHTTPHeaderField: "Authorization")
        }
        
        // Create request body based on provider
        let requestBody: [String: Any]
        switch selectedProvider {
        case .openAI:
            requestBody = [
                "model": "gpt-4",
                "messages": [
                    ["role": "system", "content": "You are a translation assistant. Your task is to translate text from the source language to the target language accurately and naturally. Maintain the original format, style, and tone as much as possible. Respond ONLY with the translation in a JSON format."],
                    ["role": "user", "content": prompt]
                ],
                "temperature": 0.3,
                "response_format": ["type": "json_object"]
            ]
        case .anthropic:
            requestBody = [
                "model": "claude-3-opus-20240229",
                "messages": [
                    ["role": "user", "content": "You are a translation assistant. Your task is to translate text from the source language to the target language accurately and naturally. Maintain the original format, style, and tone as much as possible. Respond ONLY with the translation in a JSON format.\n\n\(prompt)"]
                ],
                "temperature": 0.3,
                "max_tokens": 2000  // Add required parameter to fix HTTP 400 error
            ]
        case .googleAI:
            requestBody = [
                "contents": [
                    ["parts": [["text": "You are a translation assistant. Your task is to translate text from the source language to the target language accurately and naturally. Maintain the original format, style, and tone as much as possible. Respond ONLY with the translation in a JSON format.\n\n\(prompt)"]]]
                ],
                "generationConfig": [
                    "temperature": 0.3
                ]
            ]
        case .localModel:
            requestBody = [
                "prompt": "You are a translation assistant. Your task is to translate text from the source language to the target language accurately and naturally. Maintain the original format, style, and tone as much as possible. Respond ONLY with the translation in a JSON format.\n\n\(prompt)",
                "temperature": 0.3
            ]
        }
        
        // Serialize request body to JSON
        do {
            request.httpBody = try JSONSerialization.data(withJSONObject: requestBody)
        } catch {
            return Fail(error: .networkError(error))
                .eraseToAnyPublisher()
        }
        
        // Make the API request
        AppLogger.log(.info, message: "Sending translation request to \(selectedProvider.rawValue)")
        
        // Log request details
        AppLogger.log(.debug, message: "Request URL: \(request.url?.absoluteString ?? "unknown")")
        AppLogger.log(.debug, message: "Request method: \(request.httpMethod ?? "unknown")")
        AppLogger.log(.debug, message: "Request headers: \(request.allHTTPHeaderFields ?? [:])")
        
        return URLSession.shared.dataTaskPublisher(for: request)
            .tryMap { data, response -> Data in
                guard let httpResponse = response as? HTTPURLResponse else {
                    AppLogger.log(.error, message: "Invalid HTTP response in translation request")
                    throw TranslationServiceError.invalidResponse
                }
                
                AppLogger.log(.info, message: "Translation API response status: \(httpResponse.statusCode)")
                
                if httpResponse.statusCode < 200 || httpResponse.statusCode >= 300 {
                    let responseString = String(data: data, encoding: .utf8) ?? "Unknown error"
                    AppLogger.log(.error, message: "Translation API error: \(httpResponse.statusCode) - \(responseString)")
                    throw TranslationServiceError.apiError("HTTP \(httpResponse.statusCode): \(responseString)")
                }
                
                AppLogger.log(.info, message: "Translation API request successful")
                return data
            }
            .mapError { error -> TranslationServiceError in
                if let error = error as? TranslationServiceError {
                    return error
                }
                return TranslationServiceError.networkError(error)
            }
            .flatMap { data -> AnyPublisher<String, TranslationServiceError> in
                do {
                    // Process the API response based on the provider
                    switch self.selectedProvider {
                    case .openAI:
                        // OpenAI returns a different structure, so we need to extract the content
                        let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]
                        if let choices = json?["choices"] as? [[String: Any]],
                           let firstChoice = choices.first,
                           let message = firstChoice["message"] as? [String: Any],
                           let content = message["content"] as? String {
                            return Just(content)
                                .setFailureType(to: TranslationServiceError.self)
                                .eraseToAnyPublisher()
                        }
                        
                    case .anthropic:
                        // Anthropic returns a different structure
                        let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]
                        if let content = json?["content"] as? [[String: Any]],
                           let firstContent = content.first,
                           let text = firstContent["text"] as? String {
                            return Just(text)
                                .setFailureType(to: TranslationServiceError.self)
                                .eraseToAnyPublisher()
                        }
                        
                    case .googleAI, .localModel:
                        // Default handling for other providers
                        let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]
                        if let text = json?["text"] as? String {
                            return Just(text)
                                .setFailureType(to: TranslationServiceError.self)
                                .eraseToAnyPublisher()
                        }
                    }
                    
                    // If we couldn't parse the response in a provider-specific way,
                    // just return the raw JSON string
                    let responseString = String(data: data, encoding: .utf8) ?? "{}"
                    return Just(responseString)
                        .setFailureType(to: TranslationServiceError.self)
                        .eraseToAnyPublisher()
                } catch {
                    return Fail(error: TranslationServiceError.decodingError(error))
                        .eraseToAnyPublisher()
                }
            }
            .eraseToAnyPublisher()
    }
    
    // Simulate API response for development/testing
    private func simulateResponse(for provider: LLMProvider, prompt: String) -> AnyPublisher<String, TranslationServiceError> {
        return Future<String, TranslationServiceError> { promise in
            // Add artificial delay to simulate network request
            DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) {
                // Extract source and target languages from prompt
                var sourceLanguage = "Unknown"
                var targetLanguage = "Unknown"
                var content = "Sample content"
                
                // Use simpler regex approach with regex matching groups
                let sourcePattern = try? NSRegularExpression(pattern: "\"source_language\"\\s*:\\s*\"([^\"]+)\"", options: [])
                if let sourcePattern = sourcePattern,
                   let sourceMatch = sourcePattern.firstMatch(in: prompt, options: [], range: NSRange(prompt.startIndex..., in: prompt)) {
                    if let range = Range(sourceMatch.range(at: 1), in: prompt) {
                        sourceLanguage = String(prompt[range])
                    }
                }
                
                let targetPattern = try? NSRegularExpression(pattern: "\"target_language\"\\s*:\\s*\"([^\"]+)\"", options: [])
                if let targetPattern = targetPattern,
                   let targetMatch = targetPattern.firstMatch(in: prompt, options: [], range: NSRange(prompt.startIndex..., in: prompt)) {
                    if let range = Range(targetMatch.range(at: 1), in: prompt) {
                        targetLanguage = String(prompt[range])
                    }
                }
                
                // Extract content using a similar approach
                let contentPattern = try? NSRegularExpression(pattern: "\"content\"\\s*:\\s*\"\"\"(.*?)\"\"\"", options: [.dotMatchesLineSeparators])
                if let contentPattern = contentPattern,
                   let contentMatch = contentPattern.firstMatch(in: prompt, options: [], range: NSRange(prompt.startIndex..., in: prompt)) {
                    if let range = Range(contentMatch.range(at: 1), in: prompt) {
                        content = String(prompt[range])
                    }
                }
                
                // Generate a simulated translation
                let simulatedTranslation: String
                
                if targetLanguage == "French" {
                    simulatedTranslation = """
                    {
                      "translation": {
                        "original_language": "\(sourceLanguage)",
                        "target_language": "French",
                        "text": "\(content.prefix(20))... [Translated to French]",
                        "notes": "This is a simulated translation. In a real application, this would be the actual French translation from the LLM."
                      }
                    }
                    """
                } else if targetLanguage == "Spanish" {
                    simulatedTranslation = """
                    {
                      "translation": {
                        "original_language": "\(sourceLanguage)",
                        "target_language": "Spanish",
                        "text": "\(content.prefix(20))... [Translated to Spanish]",
                        "notes": "This is a simulated translation. In a real application, this would be the actual Spanish translation from the LLM."
                      }
                    }
                    """
                } else if targetLanguage == "German" {
                    simulatedTranslation = """
                    {
                      "translation": {
                        "original_language": "\(sourceLanguage)",
                        "target_language": "German",
                        "text": "\(content.prefix(20))... [Translated to German]",
                        "notes": "This is a simulated translation. In a real application, this would be the actual German translation from the LLM."
                      }
                    }
                    """
                } else {
                    simulatedTranslation = """
                    {
                      "translation": {
                        "original_language": "\(sourceLanguage)",
                        "target_language": "\(targetLanguage)",
                        "text": "\(content.prefix(20))... [Translated to \(targetLanguage)]",
                        "notes": "This is a simulated translation. In a real application, this would be the actual translation from the LLM."
                      }
                    }
                    """
                }
                
                promise(.success(simulatedTranslation))
            }
        }
        .eraseToAnyPublisher()
    }
}