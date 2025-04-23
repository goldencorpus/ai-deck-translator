import SwiftUI

struct LanguageConfirmationView: View {
    @ObservedObject var viewModel: TranslationViewModel
    
    let commonLanguages = [
        "English", "Spanish", "French", "German", "Chinese", "Japanese",
        "Korean", "Russian", "Arabic", "Portuguese", "Italian", "Dutch"
    ]
    
    var body: some View {
        VStack(spacing: 30) {
            Text("Confirm Languages")
                .font(.largeTitle)
                .fontWeight(.bold)
                .multilineTextAlignment(.center)
            
            VStack(spacing: 40) {
                sourceLanguageSection
                targetLanguageSection
            }
            
            Button(action: {
                viewModel.confirmLanguages()
            }) {
                HStack {
                    Text("Continue to Translation")
                    Image(systemName: "arrow.right")
                }
                .padding()
                .frame(width: 250)
                .background(Color.blue)
                .foregroundColor(.white)
                .cornerRadius(10)
            }
            .buttonStyle(PlainButtonStyle())
            .padding(.top, 20)
            .disabled(viewModel.sourceLanguage.isEmpty || viewModel.targetLanguage.isEmpty)
            .opacity(viewModel.sourceLanguage.isEmpty || viewModel.targetLanguage.isEmpty ? 0.5 : 1)
        }
        .padding(.vertical, 40)
    }
    
    // Source language section
    private var sourceLanguageSection: some View {
        VStack(spacing: 16) {
            HStack {
                Image(systemName: "text.bubble")
                    .foregroundColor(.blue)
                
                Text("Source Language")
                    .font(.title3)
                    .fontWeight(.semibold)
            }
            
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Text("We detected:")
                        .foregroundColor(.secondary)
                    
                    Text(viewModel.detectedLanguage)
                        .fontWeight(.medium)
                }
                
                Text("Is this correct? If not, please select the correct language:")
                    .foregroundColor(.secondary)
            }
            
            languageSelectionGrid(selectedLanguage: $viewModel.sourceLanguage)
        }
    }
    
    // Target language section
    private var targetLanguageSection: some View {
        VStack(spacing: 16) {
            HStack {
                Image(systemName: "arrow.right.doc")
                    .foregroundColor(.green)
                
                Text("Target Language")
                    .font(.title3)
                    .fontWeight(.semibold)
            }
            
            Text("Select the language you want to translate to:")
                .foregroundColor(.secondary)
            
            languageSelectionGrid(selectedLanguage: $viewModel.targetLanguage)
        }
    }
    
    // Language selection grid
    private func languageSelectionGrid(selectedLanguage: Binding<String>) -> some View {
        LazyVGrid(columns: [
            GridItem(.flexible()),
            GridItem(.flexible()),
            GridItem(.flexible()),
            GridItem(.flexible())
        ], spacing: 12) {
            ForEach(commonLanguages, id: \.self) { language in
                languageButton(language, isSelected: selectedLanguage.wrappedValue == language) {
                    selectedLanguage.wrappedValue = language
                }
            }
            
            // Add "Other" option
            languageButton("Other...", isSelected: !commonLanguages.contains(selectedLanguage.wrappedValue) && !selectedLanguage.wrappedValue.isEmpty) {
                // In a real app, this would show a text field or more comprehensive language selector
                selectedLanguage.wrappedValue = "Other"
            }
        }
    }
    
    // Individual language button
    private func languageButton(_ language: String, isSelected: Bool, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Text(language)
                .padding(.vertical, 8)
                .padding(.horizontal, 12)
                .frame(maxWidth: .infinity)
                .background(isSelected ? Color.blue : Color.gray.opacity(0.1))
                .foregroundColor(isSelected ? .white : .primary)
                .cornerRadius(8)
                .overlay(
                    RoundedRectangle(cornerRadius: 8)
                        .stroke(isSelected ? Color.blue : Color.clear, lineWidth: 1)
                )
        }
        .buttonStyle(PlainButtonStyle())
    }
}