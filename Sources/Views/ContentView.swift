import SwiftUI

struct ContentView: View {
    @EnvironmentObject var viewModel: TranslationViewModel
    
    var body: some View {
        ZStack {
            // Background
            Color("Background")
                .ignoresSafeArea()
            
            VStack(spacing: 0) {
                // Header
                HStack {
                    Text("Translation Assistant")
                        .font(.title)
                        .fontWeight(.bold)
                        .foregroundColor(.primary)
                    
                    Spacer()
                    
                    // Settings button
                    Button(action: {
                        viewModel.currentStep = .settings
                    }) {
                        HStack(spacing: 4) {
                            Image(systemName: "gear")
                                .font(.title2)
                            
                            Text("Settings")
                                .font(.headline)
                        }
                        .padding(.horizontal, 12)
                        .padding(.vertical, 8)
                        .background(Color.blue.opacity(0.1))
                        .cornerRadius(8)
                    }
                    .buttonStyle(PlainButtonStyle())
                }
                .padding()
                
                // Main content
                ScrollView {
                    VStack(spacing: 20) {
                        switch viewModel.currentStep {
                        case .selectType:
                            TranslationTypeView(viewModel: viewModel)
                        case .apiKeyQuestion:
                            ApiKeyQuestionView(viewModel: viewModel)
                        case .apiKeyManagement:
                            APIKeyManagementView(viewModel: viewModel)
                        case .cloudPermission:
                            CloudPermissionView(viewModel: viewModel)
                        case .contentInput:
                            ContentInputView(viewModel: viewModel)
                        case .confirmLanguages:
                            LanguageConfirmationView(viewModel: viewModel)
                        case .result:
                            TranslationResultView(viewModel: viewModel)
                        case .settings:
                            SettingsView(viewModel: viewModel)
                        }
                    }
                    .padding()
                    .animation(.easeInOut, value: viewModel.currentStep)
                }
                
                // Footer
                if viewModel.currentStep != .selectType {
                    HStack {
                        Button(action: {
                            viewModel.goBack()
                        }) {
                            HStack {
                                Image(systemName: "arrow.left")
                                Text("Back")
                            }
                            .padding(.horizontal)
                            .padding(.vertical, 8)
                        }
                        .buttonStyle(.bordered)
                        
                        Spacer()
                    }
                    .padding()
                }
            }
        }
    }
}

struct ContentView_Previews: PreviewProvider {
    static var previews: some View {
        ContentView()
            .environmentObject(TranslationViewModel())
    }
}