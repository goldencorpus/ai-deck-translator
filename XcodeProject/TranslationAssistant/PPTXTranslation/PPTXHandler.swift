import Foundation
import Combine
import AppKit

/// PPTXHandler: A class for handling PPTX file operations
/// 
/// This class provides functionality for:
/// - Extracting text from PPTX files
/// - Translating PPTX content
/// - Updating PPTX files with translated content
///
/// It serves as a Swift interface to the Python-based PPTX handling functionality
/// from the ai-deck-translator project.
class PPTXHandler {
    /// Singleton instance
    static let shared = PPTXHandler()
    
    /// Translation service for API calls
    private let translationService = TranslationService.shared
    
    private init() {}
    
    /// Extract text from a PPTX file
    /// - Parameter fileURL: URL of the PPTX file
    /// - Returns: A publisher that emits the extracted text and metadata, or an error
    func extractText(from fileURL: URL) -> AnyPublisher<(textElements: [String: String], metadata: [String: Any]), Error> {
        return Future<(textElements: [String: String], metadata: [String: Any]), Error> { promise in
            // Extract relevant PPTX information for translation
            let presentationInfo = self.extractPresentationInfo(from: fileURL)
            let slideTexts = self.extractSlideTexts(from: fileURL)
            
            // Combine into a structured format similar to ai-deck-translator output
            var textElements: [String: String] = [:]
            var metadata: [[String: Any]] = []
            
            // Add presentation title if available
            if let title = presentationInfo["title"] as? String, !title.isEmpty {
                textElements["presentation_title"] = title
            }
            
            // Process each slide
            for (index, slideInfo) in slideTexts.enumerated() {
                let slideNumber = index + 1
                
                // Build slide metadata
                var slideMetadata: [String: Any] = [
                    "slide_number": slideNumber,
                    "title": slideInfo["title"] as? String ?? "",
                    "elements": []
                ]
                
                // Process slide content
                if let texts = slideInfo["texts"] as? [[String: Any]] {
                    var slideElements: [[String: Any]] = []
                    
                    for (elementIndex, textInfo) in texts.enumerated() {
                        let elementId = "slide\(slideNumber)_shape\(elementIndex)"
                        if let text = textInfo["text"] as? String, !text.isEmpty {
                            textElements[elementId] = text
                            
                            let elementMetadata: [String: Any] = [
                                "id": elementId,
                                "type": textInfo["type"] as? String ?? "shape",
                                "shape_type": textInfo["shape_type"] as? String ?? "Unknown Shape"
                            ]
                            slideElements.append(elementMetadata)
                        }
                    }
                    
                    slideMetadata["elements"] = slideElements
                }
                
                // Add slide notes if available
                if let notes = slideInfo["notes"] as? String, !notes.isEmpty {
                    let notesId = "slide\(slideNumber)_notes"
                    textElements[notesId] = notes
                    slideMetadata["notes"] = notes
                }
                
                metadata.append(slideMetadata)
            }
            
            promise(.success((textElements: textElements, metadata: ["slides": metadata])))
        }.eraseToAnyPublisher()
    }
    
    /// Update a PPTX file with translated text
    /// - Parameters:
    ///   - fileURL: URL of the original PPTX file
    ///   - translatedElements: Dictionary mapping element IDs to translated text
    ///   - targetLanguage: The target language code
    /// - Returns: A publisher that emits the URL of the updated file, or an error
    func updatePPTX(
        fileURL: URL, 
        translatedElements: [String: String],
        targetLanguage: String
    ) -> AnyPublisher<URL, Error> {
        return Future<URL, Error> { promise in
            // Create a copy of the original file with language suffix
            let originalFileName = fileURL.deletingPathExtension().lastPathComponent
            let newFileName = "\(originalFileName)_\(targetLanguage).pptx"
            let outputURL = fileURL.deletingLastPathComponent().appendingPathComponent(newFileName)
            
            do {
                // Copy the original file
                if FileManager.default.fileExists(atPath: outputURL.path) {
                    try FileManager.default.removeItem(at: outputURL)
                }
                try FileManager.default.copyItem(at: fileURL, to: outputURL)
                
                // Call Python script to update the copy with translations
                self.updatePresentationWithTranslations(outputURL, translatedElements: translatedElements)
                
                promise(.success(outputURL))
            } catch {
                AppLogger.log(.error, message: "Failed to update PPTX: \(error)")
                promise(.failure(error))
            }
        }.eraseToAnyPublisher()
    }
    
    /// Extract presentation information
    /// - Parameter fileURL: URL of the PPTX file
    /// - Returns: Dictionary with presentation metadata
    private func extractPresentationInfo(from fileURL: URL) -> [String: Any] {
        // In a real implementation, this would use the python-pptx library via Python bridge
        // For now, return basic file information
        let fileSize = (try? FileManager.default.attributesOfItem(atPath: fileURL.path)[.size] as? Int) ?? 0
        let fileName = fileURL.lastPathComponent
        
        return [
            "title": fileName.replacingOccurrences(of: ".pptx", with: ""),
            "path": fileURL.path,
            "size": fileSize,
            "slides_count": countSlides(in: fileURL)
        ]
    }
    
    /// Count the number of slides in a PPTX file
    /// - Parameter fileURL: URL of the PPTX file
    /// - Returns: Number of slides
    private func countSlides(in fileURL: URL) -> Int {
        // Placeholder implementation
        // In real implementation, this would use python-pptx to count slides
        return 5 // Return a default value for now
    }
    
    /// Extract text content from all slides
    /// - Parameter fileURL: URL of the PPTX file
    /// - Returns: Array of dictionaries with slide content
    private func extractSlideTexts(from fileURL: URL) -> [[String: Any]] {
        // This is a placeholder implementation
        // In a real implementation, this would call a Python bridge to python-pptx
        
        var slides: [[String: Any]] = []
        
        // Simulate extraction of a few slides for testing purposes
        for i in 1...5 {
            var slideInfo: [String: Any] = [
                "slide_number": i,
                "title": "Slide \(i)",
                "texts": [
                    [
                        "type": "title",
                        "shape_type": "Title",
                        "text": "Sample Title for Slide \(i)"
                    ],
                    [
                        "type": "body",
                        "shape_type": "Content Placeholder",
                        "text": "This is sample content for slide \(i).\nIt contains multiple lines.\nThis would be actual content from a PowerPoint file."
                    ]
                ],
                "notes": "Speaker notes for slide \(i)"
            ]
            
            slides.append(slideInfo)
        }
        
        return slides
    }
    
    /// Update a presentation with translated text
    /// - Parameters:
    ///   - fileURL: URL of the PPTX file to update
    ///   - translatedElements: Dictionary mapping element IDs to translated text
    private func updatePresentationWithTranslations(_ fileURL: URL, translatedElements: [String: String]) {
        // In a real implementation, this would use python-pptx through a bridge
        // For now, just log the update operation
        AppLogger.log(.info, message: "Would update PPTX at \(fileURL) with \(translatedElements.count) translated elements")
        
        // Log some sample translations
        for (key, value) in translatedElements.prefix(3) {
            AppLogger.log(.debug, message: "Translation for \(key): \(value)")
        }
    }
    
    /// Translate PPTX content using the translation service
    /// - Parameters:
    ///   - textElements: Dictionary mapping element IDs to text
    ///   - sourceLanguage: Source language code
    ///   - targetLanguage: Target language code
    /// - Returns: A publisher that emits the translated text elements, or an error
    func translateContent(
        textElements: [String: String],
        sourceLanguage: String,
        targetLanguage: String
    ) -> AnyPublisher<[String: String], Error> {
        return Future<[String: String], Error> { promise in
            // This is where we would call the TranslationService for each text element
            // For now, use a simplified approach similar to ai-deck-translator
            
            // Create a prompt template for PPTX content
            let pptxPrompt = """
            {
              "task": "presentation_translation",
              "source_language": "\(sourceLanguage)",
              "target_language": "\(targetLanguage)",
              "content_type": "PowerPoint",
              "elements": \(self.jsonString(from: textElements) ?? "{}"),
              "instructions": "Please translate the provided PowerPoint content from \(sourceLanguage) to \(targetLanguage), maintaining the original formatting and structure as much as possible. Ensure the translation is accurate and natural-sounding in the target language. Preserve special characters, formatting, and bullet points."
            }
            """
            
            // Call the translation service
            self.translationService.translate(prompt: pptxPrompt)
                .sink(
                    receiveCompletion: { completion in
                        if case .failure(let error) = completion {
                            promise(.failure(error))
                        }
                    },
                    receiveValue: { translationResult in
                        // Parse the result to extract translations
                        if let translatedElements = self.parseTranslationResult(result: translationResult) {
                            promise(.success(translatedElements))
                        } else {
                            promise(.failure(TranslationServiceError.invalidResponse))
                        }
                    }
                )
                .store(in: &self.translationService.cancellables)
        }.eraseToAnyPublisher()
    }
    
    /// Parse translation result to extract translated elements
    /// - Parameter result: The JSON string from the translation service
    /// - Returns: Dictionary mapping element IDs to translated text, or nil if parsing failed
    private func parseTranslationResult(result: String) -> [String: String]? {
        // Try to extract JSON content from the result
        do {
            if let data = result.data(using: .utf8) {
                if let json = try JSONSerialization.jsonObject(with: data) as? [String: Any] {
                    // Check for different possible response formats
                    if let translation = json["translation"] as? [String: Any],
                       let elements = translation["elements"] as? [String: String] {
                        return elements
                    } else if let translations = json["translations"] as? [String: String] {
                        return translations
                    } else if let content = json["content"] as? [String: String] {
                        return content
                    }
                }
            }
            
            // Fallback: Try to find a JSON block in the text
            let jsonPattern = "\\{[\\s\\S]*\\}"
            if let regex = try? NSRegularExpression(pattern: jsonPattern),
               let match = regex.firstMatch(in: result, range: NSRange(result.startIndex..., in: result)),
               let range = Range(match.range, in: result) {
                let jsonString = String(result[range])
                if let data = jsonString.data(using: .utf8),
                   let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
                    // Check for different possible response formats again
                    if let translation = json["translation"] as? [String: Any],
                       let elements = translation["elements"] as? [String: String] {
                        return elements
                    } else if let translations = json["translations"] as? [String: String] {
                        return translations
                    } else if let content = json["content"] as? [String: String] {
                        return content
                    }
                }
            }
            
            // If we still haven't found the translations, log the issue
            AppLogger.log(.error, message: "Failed to parse translation result: \(result)")
            return nil
        } catch {
            AppLogger.log(.error, message: "JSON parsing error: \(error)")
            return nil
        }
    }
    
    /// Convert a dictionary to a JSON string
    /// - Parameter dictionary: The dictionary to convert
    /// - Returns: JSON string representation, or nil if conversion failed
    private func jsonString(from dictionary: [String: Any]) -> String? {
        do {
            let data = try JSONSerialization.data(withJSONObject: dictionary, options: [.prettyPrinted])
            return String(data: data, encoding: .utf8)
        } catch {
            AppLogger.log(.error, message: "Failed to convert dictionary to JSON: \(error)")
            return nil
        }
    }
    
    /// Convert a dictionary with string keys and values to a dictionary with string keys and any values
    /// - Parameter stringDict: Dictionary with string keys and values
    /// - Returns: Dictionary with string keys and any values
    private func convertToAnyDict(_ stringDict: [String: String]) -> [String: Any] {
        var result: [String: Any] = [:]
        for (key, value) in stringDict {
            result[key] = value
        }
        return result
    }
}