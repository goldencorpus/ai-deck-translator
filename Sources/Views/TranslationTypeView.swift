import SwiftUI

struct TranslationTypeView: View {
    @ObservedObject var viewModel: TranslationViewModel
    
    var body: some View {
        VStack(spacing: 30) {
            Text("What would you like to translate?")
                .font(.largeTitle)
                .fontWeight(.bold)
                .multilineTextAlignment(.center)
            
            VStack(spacing: 16) {
                ForEach(TranslationType.allCases) { type in
                    TypeSelectionCard(type: type) {
                        viewModel.selectType(type)
                    }
                }
            }
        }
        .padding(.vertical, 60)
    }
}

struct TypeSelectionCard: View {
    let type: TranslationType
    let action: () -> Void
    
    @State private var isHovering = false
    
    var body: some View {
        Button(action: action) {
            HStack(spacing: 16) {
                ZStack {
                    Circle()
                        .fill(Color.blue.opacity(0.2))
                        .frame(width: 50, height: 50)
                    
                    Image(systemName: type.icon)
                        .font(.title2)
                        .foregroundColor(.blue)
                }
                
                VStack(alignment: .leading, spacing: 4) {
                    Text(type.rawValue)
                        .font(.headline)
                        .foregroundColor(.primary)
                    
                    Text(type.description)
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }
                
                Spacer()
                
                Image(systemName: "chevron.right")
                    .foregroundColor(.blue)
                    .opacity(isHovering ? 1.0 : 0.5)
            }
            .padding()
            .background(Color.blue.opacity(isHovering ? 0.1 : 0.05))
            .cornerRadius(12)
        }
        .buttonStyle(PlainButtonStyle())
        .onHover { hovering in
            withAnimation {
                self.isHovering = hovering
            }
        }
    }
}