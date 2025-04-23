import SwiftUI
import Combine
import OSLog

struct SettingsView: View {
    @ObservedObject var viewModel: TranslationViewModel
    @State private var showingRevokeAlert = false
    @State private var providerToRevoke: LLMProvider?
    @State private var showingAddKeyView = false
    @State private var refreshKeys = false // Trigger view refresh
    @State private var diagnosticsResult: String? = nil
    @State private var showingDiagnosticsSheet = false
    
    var body: some View {
        VStack(spacing: 30) {
            Text("Settings")
                .font(.largeTitle)
                .fontWeight(.bold)
                .multilineTextAlignment(.center)
            
            // API Key Management Section
            VStack(alignment: .leading, spacing: 16) {
                Text("API Keys")
                    .font(.headline)
                
                // Use _ to force view refresh when refreshKeys changes
                ForEach(LLMProvider.allCases) { provider in
                    if viewModel.translationService.hasValidAPIKey(for: provider) {
                        apiKeyRow(for: provider)
                            .id("\(provider.rawValue)_\(refreshKeys)")
                    }
                }
                
                if !LLMProvider.allCases.contains(where: { viewModel.translationService.hasValidAPIKey(for: $0) }) {
                    Text("No API keys have been added yet")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                        .padding()
                        .frame(maxWidth: .infinity)
                        .id("no_keys_\(refreshKeys)") // Force update when refreshKeys changes
                }
                
                Button(action: {
                    showingAddKeyView = true
                }) {
                    HStack {
                        Image(systemName: "plus.circle.fill")
                            .foregroundColor(.blue)
                        Text("Add API Key")
                            .fontWeight(.semibold)
                    }
                    .padding()
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Color.blue.opacity(0.1))
                    .cornerRadius(10)
                }
                .buttonStyle(PlainButtonStyle())
            }
            .padding()
            .background(Color.gray.opacity(0.1))
            .cornerRadius(12)
            
            // Cloud Permission Section
            cloudPermissionSection
            
            // App Information Section
            appInfoSection
            
            // Return to App Button
            Button(action: {
                // Return to the previous step or the content input if we had already started
                if viewModel.currentStep == .settings {
                    if viewModel.sourceText.isEmpty && viewModel.sourceFile == nil && viewModel.sourceImage == nil {
                        viewModel.currentStep = .selectType
                    } else {
                        viewModel.currentStep = .contentInput
                    }
                }
            }) {
                HStack {
                    Image(systemName: "arrow.left")
                    Text("Return to App")
                }
                .padding()
                .frame(width: 200)
                .background(Color.blue)
                .foregroundColor(.white)
                .cornerRadius(10)
            }
            .buttonStyle(PlainButtonStyle())
        }
        .padding(.vertical, 40)
        .padding(.horizontal)
        .onAppear {
            // Refresh the view when it appears
            refreshKeys.toggle()
        }
        .alert(isPresented: $showingRevokeAlert) {
            Alert(
                title: Text("Revoke API Key"),
                message: Text("Are you sure you want to remove the API key for \(providerToRevoke?.rawValue ?? "this provider")?"),
                primaryButton: .destructive(Text("Revoke")) {
                    if let provider = providerToRevoke {
                        revokeAPIKey(for: provider)
                        // Force view refresh
                        refreshKeys.toggle()
                    }
                },
                secondaryButton: .cancel()
            )
        }
        .sheet(isPresented: $showingAddKeyView, onDismiss: {
            // Force refresh when sheet is dismissed to show any new keys
            refreshKeys.toggle()
        }) {
            AddAPIKeyView(viewModel: viewModel, isPresented: $showingAddKeyView)
        }
        .sheet(isPresented: $showingDiagnosticsSheet) {
            DiagnosticsResultView(result: diagnosticsResult ?? "No diagnostics data available", isPresented: $showingDiagnosticsSheet)
        }
    }
    
    private func apiKeyRow(for provider: LLMProvider) -> some View {
        HStack {
            VStack(alignment: .leading) {
                Text(provider.rawValue)
                    .font(.headline)
                
                if let key = viewModel.translationService.getAPIKey(for: provider) {
                    Text(maskAPIKey(key))
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }
            
            Spacer()
            
            Button(action: {
                providerToRevoke = provider
                showingRevokeAlert = true
            }) {
                Image(systemName: "trash")
                    .foregroundColor(.red)
                    .padding(8)
                    .background(Circle().fill(Color.red.opacity(0.1)))
            }
            .buttonStyle(PlainButtonStyle())
        }
        .padding()
        .background(Color.gray.opacity(0.05))
        .cornerRadius(10)
    }
    
    private var cloudPermissionSection: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Cloud Processing")
                .font(.headline)
            
            Toggle("Allow Cloud Processing", isOn: Binding(
                get: { viewModel.translationService.allowCloudProcessing },
                set: { newValue in
                    viewModel.translationService.allowCloudProcessing = newValue
                    viewModel.allowCloudUpload = newValue
                }
            ))
            .toggleStyle(SwitchToggleStyle(tint: .blue))
            
            Text("When enabled, content will be sent to external API services for translation.")
                .font(.caption)
                .foregroundColor(.secondary)
        }
        .padding()
        .background(Color.gray.opacity(0.1))
        .cornerRadius(12)
    }
    
    private var appInfoSection: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("About")
                .font(.headline)
            
            VStack(alignment: .leading, spacing: 8) {
                Text("Translation Assistant")
                    .font(.subheadline)
                    .fontWeight(.semibold)
                
                Text("Version 1.0.0")
                    .font(.caption)
                    .foregroundColor(.secondary)
                
                Text("© 2025 Translation Assistant")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            Divider().padding(.vertical, 8)
            
            diagnosticsSection
        }
        .padding()
        .background(Color.gray.opacity(0.1))
        .cornerRadius(12)
    }
    
    private var diagnosticsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Diagnostics")
                .font(.subheadline)
                .fontWeight(.semibold)
            
            Button(action: {
                viewModel.getLogFileURL()
                // Open log file if it exists
                if let logUrl = viewModel.showLogFileUrl {
                    NSWorkspace.shared.open(logUrl)
                }
            }) {
                HStack {
                    Image(systemName: "doc.text.magnifyingglass")
                    Text("View Log File")
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
            .buttonStyle(PlainButtonStyle())
            
            Button(action: {
                diagnoseLLMProviders()
            }) {
                HStack {
                    Image(systemName: "stethoscope")
                    Text("Run API Key Diagnostics")
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
            .buttonStyle(PlainButtonStyle())
        }
    }
    
    private func revokeAPIKey(for provider: LLMProvider) {
        _ = viewModel.translationService.removeAPIKey(for: provider)
    }
    
    private func maskAPIKey(_ key: String) -> String {
        if key.count <= 8 {
            return "••••••••"
        }
        
        // Show first 4 and last 4 characters
        let prefix = String(key.prefix(4))
        let suffix = String(key.suffix(4))
        return "\(prefix)••••••••\(suffix)"
    }
    
    // Diagnose all LLM providers
    private func diagnoseLLMProviders() {
        AppLogger.log(.info, message: "Running API key diagnostics")
        
        var result = "# API Key Diagnostics Report\n"
        result += "Time: \(ISO8601DateFormatter().string(from: Date()))\n\n"
        
        for provider in LLMProvider.allCases {
            result += "## \(provider.rawValue)\n"
            
            // Check if key exists
            if let key = viewModel.translationService.getAPIKey(for: provider) {
                result += "- Key exists: ✓ (length: \(key.count))\n"
                
                // Check key format
                let formatValid = validateKeyFormat(key, for: provider)
                result += "- Format valid: \(formatValid ? "✓" : "✗")\n"
                
                // Include masked key
                result += "- Masked key: \(maskAPIKey(key))\n"
                
                if provider == viewModel.translationService.selectedProvider {
                    result += "- Current selected provider: ✓\n"
                }
                
                result += "\n"
            } else {
                result += "- Key exists: ✗\n"
                result += "- No API key found for this provider\n\n"
            }
        }
        
        // Add cloud permissions info
        result += "## Cloud Processing\n"
        result += "- Cloud processing enabled: \(viewModel.translationService.allowCloudProcessing ? "✓" : "✗")\n"
        
        // Add other diagnostic information
        result += "\n## Environment\n"
        result += "- viewModel.hasApiKey: \(String(describing: viewModel.hasApiKey))\n"
        result += "- viewModel.allowCloudUpload: \(String(describing: viewModel.allowCloudUpload))\n"
        
        // Capture and display
        diagnosticsResult = result
        showingDiagnosticsSheet = true
        AppLogger.log(.info, message: "Diagnostics completed and displayed")
    }
    
    // Validate key format for diagnostics
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

struct AddAPIKeyView: View {
    @ObservedObject var viewModel: TranslationViewModel
    @Binding var isPresented: Bool
    
    @State private var newApiKey: String = ""
    @State private var selectedProvider: LLMProvider = .openAI
    @State private var showingProviderSheet = false
    @State private var isValidatingKey = false
    @State private var validationMessage: String? = nil
    @FocusState private var isKeyFieldFocused: Bool
    
    var body: some View {
        VStack(spacing: 20) {
            HStack {
                Text("Add API Key")
                    .font(.headline)
                
                Spacer()
                
                Button(action: {
                    isPresented = false
                }) {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundColor(.gray)
                }
                .buttonStyle(PlainButtonStyle())
            }
            .padding()
            
            VStack(alignment: .leading, spacing: 16) {
                Text("Select Provider")
                    .font(.subheadline)
                
                Button(action: {
                    showingProviderSheet = true
                }) {
                    HStack {
                        Text(selectedProvider.rawValue)
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
            }
            .padding(.horizontal)
            
            VStack(alignment: .leading, spacing: 16) {
                Text("Enter API Key")
                    .font(.subheadline)
                
                SecureField("API Key", text: $newApiKey)
                    .textFieldStyle(RoundedBorderTextFieldStyle())
                    .padding(.horizontal)
                    .focused($isKeyFieldFocused)
                    .onAppear {
                        // Set focus to the field when view appears
                        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
                            isKeyFieldFocused = true
                        }
                    }
                
                if let message = validationMessage {
                    Text(message)
                        .font(.caption)
                        .foregroundColor(message.contains("Valid") ? .green : .red)
                        .padding(.horizontal)
                }
            }
            .padding(.horizontal)
            
            providerInfoView
            
            HStack(spacing: 12) {
                Button(action: {
                    validateKey()
                }) {
                    HStack {
                        if isValidatingKey {
                            ProgressView()
                                .scaleEffect(0.7)
                        } else {
                            Image(systemName: "checkmark.seal")
                        }
                        Text("Test Key")
                    }
                    .padding()
                    .frame(maxWidth: .infinity)
                    .background(Color.gray.opacity(0.2))
                    .foregroundColor(.primary)
                    .cornerRadius(10)
                }
                .buttonStyle(PlainButtonStyle())
                .disabled(newApiKey.isEmpty || isValidatingKey)
                .opacity(newApiKey.isEmpty || isValidatingKey ? 0.5 : 1)
                
                Button(action: {
                    if !newApiKey.isEmpty {
                        // Save key to both view model for current session and service for persistence
                        viewModel.translationService.setAPIKey(newApiKey, for: selectedProvider)
                        
                        // Force the service to save it to keychain immediately
                        _ = viewModel.translationService.hasValidAPIKey(for: selectedProvider)
                        
                        // Debug: print confirmation
                        print("Saved key for \(selectedProvider.rawValue): \(newApiKey.prefix(4))...")
                        
                        // Close sheet
                        isPresented = false
                    }
                }) {
                    Text("Save API Key")
                        .padding()
                        .frame(maxWidth: .infinity)
                        .background(Color.blue)
                        .foregroundColor(.white)
                        .cornerRadius(10)
                }
                .buttonStyle(PlainButtonStyle())
                .disabled(newApiKey.isEmpty)
                .opacity(newApiKey.isEmpty ? 0.5 : 1)
            }
            .padding()
            
            Spacer()
        }
        .frame(width: 400, height: 500)
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
                
                Text("\(selectedProvider.rawValue) Information")
                    .font(.headline)
            }
            
            VStack(alignment: .leading, spacing: 12) {
                switch selectedProvider {
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
                    selectedProvider = provider
                    showingProviderSheet = false
                }) {
                    HStack {
                        Text(provider.rawValue)
                            .foregroundColor(.primary)
                        
                        Spacer()
                        
                        if selectedProvider == provider {
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

// Extension for AddAPIKeyView
extension AddAPIKeyView {
    func validateKey() {
        guard !newApiKey.isEmpty else { return }
        
        isValidatingKey = true
        validationMessage = nil
        
        // Log the validation attempt
        AppLogger.log(.info, message: "Validating API key for provider: \(selectedProvider.rawValue)")
        
        viewModel.translationService.validateAPIKey(for: selectedProvider, key: newApiKey)
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
                } else {
                    AppLogger.log(.error, message: "API key validation failed")
                    validationMessage = "✗ Invalid API key. Please check and try again."
                }
            })
            .store(in: &viewModel.cancellables)
    }
}

// View for displaying diagnostics results
struct DiagnosticsResultView: View {
    let result: String
    @Binding var isPresented: Bool
    
    var body: some View {
        VStack(spacing: 20) {
            HStack {
                Text("Diagnostics Results")
                    .font(.headline)
                
                Spacer()
                
                Button(action: {
                    isPresented = false
                }) {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundColor(.gray)
                }
                .buttonStyle(PlainButtonStyle())
            }
            .padding()
            
            ScrollView {
                Text(result)
                    .font(.system(.body, design: .monospaced))
                    .padding()
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
            
            HStack {
                Spacer()
                
                Button(action: {
                    let pasteboard = NSPasteboard.general
                    pasteboard.clearContents()
                    pasteboard.setString(result, forType: .string)
                }) {
                    HStack {
                        Image(systemName: "doc.on.doc")
                        Text("Copy Report")
                    }
                    .padding(.horizontal, 20)
                    .padding(.vertical, 8)
                    .background(Color.blue)
                    .foregroundColor(.white)
                    .cornerRadius(6)
                }
                .buttonStyle(PlainButtonStyle())
                
                Button(action: {
                    saveReport()
                }) {
                    HStack {
                        Image(systemName: "square.and.arrow.down")
                        Text("Save Report")
                    }
                    .padding(.horizontal, 20)
                    .padding(.vertical, 8)
                    .background(Color.green)
                    .foregroundColor(.white)
                    .cornerRadius(6)
                }
                .buttonStyle(PlainButtonStyle())
            }
            .padding()
        }
        .frame(width: 600, height: 500)
    }
    
    private func saveReport() {
        // Create a save panel
        let savePanel = NSSavePanel()
        savePanel.allowedContentTypes = [.text]
        savePanel.nameFieldStringValue = "translation_assistant_diagnostics.txt"
        savePanel.title = "Save Diagnostics Report"
        savePanel.message = "Choose a location to save the diagnostics report"
        savePanel.prompt = "Save"
        
        savePanel.begin { response in
            if response == .OK, let url = savePanel.url {
                do {
                    try result.write(to: url, atomically: true, encoding: .utf8)
                } catch {
                    AppLogger.log(.error, message: "Failed to save diagnostics report: \(error.localizedDescription)")
                }
            }
        }
    }
}