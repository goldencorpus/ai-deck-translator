import SwiftUI
import Combine
import OSLog

struct APIKeyManagementView: View {
    @ObservedObject var viewModel: TranslationViewModel
    @State private var showingProviderSheet = false
    @State private var isValidatingKey = false
    @State private var validationMessage: String? = nil
    @FocusState private var isApiKeyFieldFocused: Bool
    
    // Ensure we start with Anthropic selected
    private let defaultProvider: LLMProvider = .anthropic
    
    var body: some View {
        VStack(spacing: 30) {
            Text("API Key Management")
                .font(.largeTitle)
                .fontWeight(.bold)
                .multilineTextAlignment(.center)
            
            VStack(alignment: .leading, spacing: 16) {
                Text("Select an LLM Provider")
                    .font(.headline)
                
                Button(action: {
                    showingProviderSheet = true
                }) {
                    HStack {
                        Text(viewModel.selectedProvider.rawValue)
                            .foregroundColor(.primary)
                        
                        Spacer()
                        
                        Image(systemName: "chevron.down")
                            .foregroundColor(.blue)
                    }
                    .padding()
                    .background(Color.gray.opacity(0.1))
                    .cornerRadius(8)
                }
                .buttonStyle(PlainButtonStyle())
                .onAppear {
                    // Always ensure we're using Anthropic by default for API key management
                    if viewModel.selectedProvider != defaultProvider {
                        DispatchQueue.main.async {
                            viewModel.selectedProvider = defaultProvider
                        }
                    }
                }
            }
            .padding(.horizontal)
            
            VStack(alignment: .leading, spacing: 16) {
                Text("Enter your API Key")
                    .font(.headline)
                
                VStack(alignment: .leading, spacing: 6) {
                    SecureField("API Key", text: $viewModel.apiKey)
                        .textFieldStyle(RoundedBorderTextFieldStyle())
                        .padding(.horizontal)
                        .focused($isApiKeyFieldFocused)
                        .onAppear {
                            // Set focus to the field when view appears
                            DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
                                isApiKeyFieldFocused = true
                            }
                        }
                    
                    HStack {
                        Text("Your API key is stored locally and never shared")
                            .font(.caption)
                            .foregroundColor(.secondary)
                        
                        Spacer()
                        
                        Button("Test Key") {
                            validateKey()
                        }
                        .disabled(viewModel.apiKey.isEmpty || isValidatingKey)
                        .opacity(viewModel.apiKey.isEmpty || isValidatingKey ? 0.5 : 1)
                    }
                    
                    if isValidatingKey {
                        HStack {
                            ProgressView()
                                .scaleEffect(0.8)
                            
                            Text("Testing API key...")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                        .padding(.top, 4)
                    }
                    
                    if let message = validationMessage {
                        Text(message)
                            .font(.caption)
                            .foregroundColor(message.contains("Valid") ? .green : .red)
                            .padding(.top, 4)
                    }
                }
            }
            .padding(.horizontal)
            
            // Provider information
            providerInfoView
            
            VStack(spacing: 12) {
                Button(action: {
                    validateKey()
                }) {
                    HStack {
                        Text("Verify API Key")
                        Image(systemName: "checkmark.shield")
                    }
                    .padding()
                    .frame(width: 200)
                    .background(Color.green)
                    .foregroundColor(.white)
                    .cornerRadius(10)
                }
                .buttonStyle(PlainButtonStyle())
                .disabled(viewModel.apiKey.isEmpty || isValidatingKey)
                .opacity((viewModel.apiKey.isEmpty || isValidatingKey) ? 0.5 : 1)
                
                Button(action: {
                    viewModel.saveAPIKey()
                    viewModel.moveToNextStep()
                }) {
                    HStack {
                        Text("Save and Continue")
                        Image(systemName: "arrow.right")
                    }
                    .padding()
                    .frame(width: 200)
                    .background(Color.blue)
                    .foregroundColor(.white)
                    .cornerRadius(10)
                }
                .buttonStyle(PlainButtonStyle())
                .disabled((viewModel.apiKey.isEmpty && viewModel.selectedProvider.requiresKey) || isValidatingKey)
                .opacity(((viewModel.apiKey.isEmpty && viewModel.selectedProvider.requiresKey) || isValidatingKey) ? 0.5 : 1)
            }
        }
        .padding(.vertical, 40)
        .sheet(isPresented: $showingProviderSheet) {
            providerSelectionSheet
        }
    }
    
    // Provider information view
    private var providerInfoView: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Image(systemName: "info.circle.fill")
                    .foregroundColor(.blue)
                
                Text("\(viewModel.selectedProvider.rawValue) Information")
                    .font(.headline)
            }
            
            VStack(alignment: .leading, spacing: 12) {
                switch viewModel.selectedProvider {
                case .openAI:
                    ProviderInfoRow(title: "Required Model", value: "GPT-4")
                    ProviderInfoRow(title: "API Key Format", value: "sk-...")
                    ProviderInfoRow(title: "Get API Key", value: "OpenAI Dashboard", link: "https://platform.openai.com/api-keys")
                case .anthropic:
                    ProviderInfoRow(title: "Required Model", value: "Claude 3")
                    ProviderInfoRow(title: "API Key Format", value: "sk-ant-...")
                    ProviderInfoRow(title: "Get API Key", value: "Anthropic Console", link: "https://console.anthropic.com/keys")
                case .googleAI:
                    ProviderInfoRow(title: "Required Model", value: "Gemini Pro")
                    ProviderInfoRow(title: "API Key Format", value: "AIza...")
                    ProviderInfoRow(title: "Get API Key", value: "Google AI Studio", link: "https://ai.google.dev/")
                case .localModel:
                    ProviderInfoRow(title: "Required Model", value: "Any compatible with your setup")
                    ProviderInfoRow(title: "API Key", value: "Optional depending on setup")
                    ProviderInfoRow(title: "Local Setup", value: "Configure in settings")
                }
            }
        }
        .padding()
        .background(Color.blue.opacity(0.05))
        .cornerRadius(12)
        .padding(.horizontal)
    }
    
    // Provider selection sheet
    private var providerSelectionSheet: some View {
        VStack(spacing: 20) {
            Text("Select LLM Provider")
                .font(.headline)
                .padding()
            
            List(LLMProvider.allCases) { provider in
                Button(action: {
                    viewModel.selectedProvider = provider
                    showingProviderSheet = false
                }) {
                    HStack {
                        Text(provider.rawValue)
                            .foregroundColor(.primary)
                        
                        Spacer()
                        
                        if viewModel.selectedProvider == provider {
                            Image(systemName: "checkmark")
                                .foregroundColor(.blue)
                        }
                    }
                }
                .buttonStyle(PlainButtonStyle())
            }
            
            Button("Cancel") {
                showingProviderSheet = false
            }
            .padding()
        }
        .frame(width: 300, height: 400)
    }
}


// Extension for validating API keys
extension APIKeyManagementView {
    func validateKey() {
        guard !viewModel.apiKey.isEmpty else { return }
        
        // Basic format validation before sending to API
        let isFormatValid = validateKeyFormat(viewModel.apiKey, for: viewModel.selectedProvider)
        guard isFormatValid else {
            validationMessage = "✗ Invalid key format for \(viewModel.selectedProvider.rawValue)"
            return
        }
        
        isValidatingKey = true
        validationMessage = nil
        
        AppLogger.log(.info, message: "Validating API key for provider: \(viewModel.selectedProvider.rawValue)")
        
        viewModel.translationService.validateAPIKey(for: viewModel.selectedProvider, key: viewModel.apiKey)
            .receive(on: DispatchQueue.main)
            .sink(receiveCompletion: { completion in
                isValidatingKey = false
                if case .failure(let error) = completion {
                    AppLogger.log(.error, message: "Error validating key: \(error.localizedDescription)")
                    validationMessage = "Error validating key: \(error.localizedDescription)"
                }
            }, receiveValue: { isValid in
                if isValid {
                    AppLogger.log(.info, message: "API key validation successful")
                    validationMessage = "✓ Valid API key!"
                    // Save the key immediately when it's validated successfully
                    viewModel.saveAPIKey()
                } else {
                    AppLogger.log(.error, message: "API key validation failed")
                    validationMessage = "✗ Invalid API key. Please check and try again."
                }
            })
            .store(in: &viewModel.cancellables)
    }
    
    /// Validates the format of the API key based on the provider
    private func validateKeyFormat(_ key: String, for provider: LLMProvider) -> Bool {
        // Minimum key length requirements
        let minLength: Int = {
            switch provider {
            case .openAI: return 32        // OpenAI keys are typically 51 chars
            case .anthropic: return 32     // Anthropic keys are typically 48+ chars starting with sk-ant
            case .googleAI: return 20      // Google API keys are typically 39 chars starting with AIza
            case .localModel: return 0     // Local model might use any format
            }
        }()
        
        // Key must meet minimum length
        if key.count < minLength {
            AppLogger.log(.error, message: "API key too short for \(provider.rawValue): \(key.count) chars (min: \(minLength))")
            return false
        }
        
        // Provider-specific format checks
        switch provider {
        case .openAI:
            return key.hasPrefix("sk-")
        case .anthropic:
            return key.hasPrefix("sk-ant-")
        case .googleAI:
            return key.hasPrefix("AIza")
        case .localModel:
            return true  // Accept any format for local model
        }
    }
}