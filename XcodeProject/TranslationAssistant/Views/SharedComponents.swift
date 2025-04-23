import SwiftUI

// Shared components used across multiple views

struct ProviderInfoRow: View {
    let title: String
    let value: String
    var link: String? = nil
    
    var body: some View {
        HStack(alignment: .top) {
            Text(title)
                .font(.subheadline)
                .foregroundColor(.secondary)
                .frame(width: 120, alignment: .leading)
            
            if let link = link {
                Link(destination: URL(string: link)!) {
                    Text(value)
                        .font(.subheadline)
                        .foregroundColor(.blue)
                        .underline()
                }
            } else {
                Text(value)
                    .font(.subheadline)
            }
            
            Spacer()
        }
    }
}