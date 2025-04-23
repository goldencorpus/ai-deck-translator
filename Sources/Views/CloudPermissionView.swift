import SwiftUI

struct CloudPermissionView: View {
    @ObservedObject var viewModel: TranslationViewModel
    
    var body: some View {
        VStack(spacing: 30) {
            Text("Cloud Service Permission")
                .font(.largeTitle)
                .fontWeight(.bold)
                .multilineTextAlignment(.center)
            
            VStack(spacing: 16) {
                HStack {
                    Image(systemName: "shield.fill")
                        .font(.title)
                        .foregroundColor(.blue)
                    
                    Text("Privacy & Security")
                        .font(.title3)
                        .fontWeight(.semibold)
                }
                
                Text("To perform translation, your content needs to be processed by an AI service. Would you allow uploading your content to a cloud service?")
                    .multilineTextAlignment(.center)
                    .foregroundColor(.secondary)
                    .padding(.horizontal)
            }
            
            VStack(spacing: 12) {
                PermissionInfoCard(
                    title: "What this means",
                    icon: "info.circle.fill",
                    color: .blue,
                    items: [
                        "Your content will be sent to a secure API endpoint",
                        "Content is processed by AI models running in the cloud",
                        "Data is not permanently stored unless required by the service"
                    ]
                )
                
                PermissionInfoCard(
                    title: "If you decline",
                    icon: "xmark.shield.fill",
                    color: .orange,
                    items: [
                        "You'll need to manually process your content",
                        "The app will provide instructions on how to do this",
                        "Some features may be limited or unavailable"
                    ]
                )
            }
            
            HStack(spacing: 20) {
                PermissionButton(
                    title: "Yes, allow cloud processing",
                    icon: "checkmark.circle.fill",
                    color: .green,
                    isSelected: viewModel.allowCloudUpload == true
                ) {
                    viewModel.setCloudPermission(true)
                }
                
                PermissionButton(
                    title: "No, keep content local",
                    icon: "xmark.circle.fill",
                    color: .red,
                    isSelected: viewModel.allowCloudUpload == false
                ) {
                    viewModel.setCloudPermission(false)
                }
            }
        }
        .padding(.vertical, 40)
    }
}

struct PermissionInfoCard: View {
    let title: String
    let icon: String
    let color: Color
    let items: [String]
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: icon)
                    .foregroundColor(color)
                
                Text(title)
                    .font(.headline)
                    .foregroundColor(.primary)
            }
            
            ForEach(items, id: \.self) { item in
                BulletPoint(text: item)
            }
        }
        .padding()
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(color.opacity(0.05))
        .cornerRadius(12)
    }
}

struct PermissionButton: View {
    let title: String
    let icon: String
    let color: Color
    let isSelected: Bool
    let action: () -> Void
    
    @State private var isHovering = false
    
    var body: some View {
        Button(action: action) {
            HStack(spacing: 12) {
                Image(systemName: icon)
                    .foregroundColor(isSelected ? .white : color)
                
                Text(title)
                    .fontWeight(.medium)
                    .foregroundColor(isSelected ? .white : .primary)
            }
            .padding()
            .frame(maxWidth: .infinity)
            .background(isSelected ? color : Color.gray.opacity(0.05))
            .cornerRadius(12)
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(isSelected ? color : Color.gray.opacity(0.2), lineWidth: 1)
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