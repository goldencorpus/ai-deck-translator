import SwiftUI

struct ApiKeyQuestionView: View {
    @ObservedObject var viewModel: TranslationViewModel
    
    var body: some View {
        VStack(spacing: 30) {
            Text("Do you have an LLM API key?")
                .font(.largeTitle)
                .fontWeight(.bold)
                .multilineTextAlignment(.center)
            
            Text("An API key is required to access AI translation services")
                .font(.title3)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
            
            HStack(spacing: 20) {
                YesNoButton(title: "Yes, I have an API key", icon: "key.fill", isSelected: viewModel.hasApiKey == true) {
                    viewModel.setApiKeyAvailability(true)
                }
                
                YesNoButton(title: "No, I don't have a key", icon: "xmark.circle.fill", isSelected: viewModel.hasApiKey == false) {
                    viewModel.setApiKeyAvailability(false)
                }
            }
            
            if viewModel.hasApiKey == true {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Enter your API key:")
                        .font(.headline)
                    
                    SecureField("API Key", text: $viewModel.apiKey)
                        .textFieldStyle(RoundedBorderTextFieldStyle())
                        .padding(.horizontal)
                }
                .padding()
                .background(Color.blue.opacity(0.05))
                .cornerRadius(12)
                .transition(.move(edge: .top).combined(with: .opacity))
            }
            
            if viewModel.hasApiKey == false {
                VStack(spacing: 12) {
                    Text("Without an API key, you can still use the app but:")
                        .font(.headline)
                    
                    VStack(alignment: .leading, spacing: 8) {
                        BulletPoint(text: "You'll need to manually paste your content into an external service")
                        BulletPoint(text: "Translation quality may vary depending on the service used")
                        BulletPoint(text: "Some features may be limited or unavailable")
                    }
                }
                .padding()
                .background(Color.orange.opacity(0.1))
                .cornerRadius(12)
                .transition(.move(edge: .top).combined(with: .opacity))
            }
        }
        .padding(.vertical, 40)
        .animation(.easeInOut, value: viewModel.hasApiKey)
    }
}

struct YesNoButton: View {
    let title: String
    let icon: String
    let isSelected: Bool
    let action: () -> Void
    
    @State private var isHovering = false
    
    var body: some View {
        Button(action: action) {
            VStack(spacing: 16) {
                ZStack {
                    Circle()
                        .fill(isSelected ? Color.blue : Color.gray.opacity(0.2))
                        .frame(width: 60, height: 60)
                    
                    Image(systemName: icon)
                        .font(.title)
                        .foregroundColor(isSelected ? .white : .gray)
                }
                
                Text(title)
                    .font(.headline)
                    .multilineTextAlignment(.center)
                    .foregroundColor(isSelected ? .primary : .secondary)
            }
            .padding()
            .frame(height: 150)
            .frame(maxWidth: .infinity)
            .background(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(isSelected ? Color.blue : Color.gray.opacity(0.2), lineWidth: 2)
                    .background(
                        RoundedRectangle(cornerRadius: 12)
                            .fill(isSelected ? Color.blue.opacity(0.1) : Color.gray.opacity(0.05))
                    )
            )
            .scaleEffect(isHovering ? 1.02 : 1.0)
        }
        .buttonStyle(PlainButtonStyle())
        .onHover { hovering in
            withAnimation {
                self.isHovering = hovering
            }
        }
    }
}

struct BulletPoint: View {
    let text: String
    
    var body: some View {
        HStack(alignment: .top, spacing: 8) {
            Image(systemName: "circle.fill")
                .font(.system(size: 6))
                .foregroundColor(.orange)
                .padding(.top, 6)
            
            Text(text)
                .foregroundColor(.secondary)
        }
    }
}