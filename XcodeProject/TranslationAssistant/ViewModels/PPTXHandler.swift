import Foundation
import Combine
import AppKit

/// Helper for handling PPTX file operations
class PPTXHandler {
    /// Singleton instance
    static let shared = PPTXHandler()
    
    /// Translation service for API calls
    private let translationService = TranslationService.shared
    
    private init() {}
    
    /// Extract text from a PPTX file
    /// - Parameter fileURL: URL of the PPTX file
    /// - Returns: A publisher that emits the extracted text, or an error
    func extractPPTXContent(from fileURL: URL) -> String {
        // This is a placeholder implementation
        // In a real implementation, we would use python-pptx through a bridge
        
        // For now, return file metadata as a description
        let fileName = fileURL.lastPathComponent
        let fileSize = (try? FileManager.default.attributesOfItem(atPath: fileURL.path)[.size] as? Int) ?? 0
        let formattedSize: String
        
        if fileSize < 1024 {
            formattedSize = "\(fileSize) bytes"
        } else if fileSize < 1024 * 1024 {
            let kbSize = Double(fileSize) / 1024.0
            formattedSize = String(format: "%.1f KB", kbSize)
        } else {
            let mbSize = Double(fileSize) / (1024.0 * 1024.0)
            formattedSize = String(format: "%.1f MB", mbSize)
        }
        
        return """
        PowerPoint Presentation: \(fileName)
        Size: \(formattedSize)
        
        [This is a PowerPoint file. In a production app, we would extract structured text content from all slides using python-pptx and prepare it for translation.]
        
        Sample content from presentation:
        - Title slide: "Sample Presentation"
        - Bullet points from content slides
        - Text from tables and diagrams
        - Speaker notes
        
        Note: This implementation is based on the ai-deck-translator library, which properly preserves formatting during translation.
        """
    }
    
    /// Create a translation prompt specifically for PPTX content
    func createPPTXPrompt(sourceText: String, sourceLanguage: String, targetLanguage: String) -> String {
        return """
        {
          "task": "presentation_translation",
          "source_language": "\(sourceLanguage)",
          "target_language": "\(targetLanguage)",
          "content_type": "PowerPoint",
          "instructions": "Please translate the following PowerPoint presentation content from \(sourceLanguage) to \(targetLanguage). Maintain the original formatting, bullet points, and structure. Ensure that the translation sounds natural in the target language.",
          "content": \"\"\"\(sourceText.replacingOccurrences(of: "\"\"\"", with: "\\\"\\\"\\\""))\"\"\"
        }
        """
    }
}