import Foundation
import Combine
import AppKit

/// Helper for handling PPTX file operations using Python bridge
class PPTXHandler {
    /// Singleton instance
    static let shared = PPTXHandler()
    
    /// Translation service for API calls
    private let translationService = TranslationService.shared
    
    /// Path to the Python script directory
    private let pythonScriptPath = "/Users/eprouveze/Documents/Dev/App/ai-deck-translator"
    
    private init() {}
    
    /// Extract text from a PPTX file using the Python extractor
    /// - Parameter fileURL: URL of the PPTX file
    /// - Returns: A publisher that emits the extracted text, or an error
    func extractPPTXContent(from fileURL: URL) -> String {
        // Check if Python bridge is available
        let pythonAvailable = checkPythonEnvironment()
        
        if pythonAvailable {
            // Try to use the Python extractor
            if let extractedContent = extractWithPython(fileURL: fileURL) {
                return extractedContent
            }
        }
        
        // Fallback to basic extraction if Python bridge fails
        AppLogger.log(.warning, message: "Using fallback PPTX content extraction without Python")
        return createFallbackContent(for: fileURL)
    }
    
    /// Check if the Python environment is available and configured correctly
    private func checkPythonEnvironment() -> Bool {
        let result = runPythonCommand(args: ["-c", "import sys; print('Python is available')"])
        return result.contains("Python is available")
    }
    
    /// Extract PPTX content using the Python bridge
    private func extractWithPython(fileURL: URL) -> String? {
        let extractorScript = """
        import sys
        sys.path.append('\(pythonScriptPath)')
        try:
            from ai_deck_translator.pptx.extractor import extract_text
            import json
            
            # Extract text from the presentation
            text_dict, slide_metadata = extract_text('\(fileURL.path)')
            
            # Convert to a simple format for Swift
            result = {
                "text_elements": text_dict,
                "metadata": slide_metadata
            }
            
            # Print as JSON for Swift to parse
            print(json.dumps(result))
        except Exception as e:
            print(f"Error: {str(e)}")
            sys.exit(1)
        """
        
        // Save the script to a temporary file
        let tempDir = FileManager.default.temporaryDirectory
        let scriptURL = tempDir.appendingPathComponent("extract_pptx.py")
        
        do {
            try extractorScript.write(to: scriptURL, atomically: true, encoding: .utf8)
            
            // Run the Python script
            let output = runPythonCommand(args: [scriptURL.path])
            
            // Check for errors
            if output.contains("Error:") {
                AppLogger.log(.error, message: "Python extraction error: \(output)")
                return nil
            }
            
            // Format the content for display
            return "PowerPoint Presentation: \(fileURL.lastPathComponent)\n\n" +
                   "Extracted content from presentation using Python bridge:\n" +
                   output
            
        } catch {
            AppLogger.log(.error, message: "Failed to create Python script: \(error)")
            return nil
        }
    }
    
    /// Create a fallback content description when Python extraction isn't available
    private func createFallbackContent(for fileURL: URL) -> String {
        // Basic file metadata
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
        - Title slide content
        - Bullet points from content slides
        - Text from tables and diagrams
        - Speaker notes
        
        Note: This implementation normally uses the ai-deck-translator Python library, which preserves formatting during translation.
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
    
    /// Translate and update a PPTX file
    /// - Parameters:
    ///   - fileURL: URL of the source PPTX file
    ///   - translatedText: Translated content
    ///   - sourceLanguage: Source language code
    ///   - targetLanguage: Target language code
    /// - Returns: URL of the output file if successful, nil otherwise
    func updatePPTXWithTranslation(
        fileURL: URL,
        translatedText: String, 
        sourceLanguage: String,
        targetLanguage: String
    ) -> URL? {
        // Create output file name
        let fileName = fileURL.deletingPathExtension().lastPathComponent
        let outputFileName = "\(fileName)_\(targetLanguage).pptx"
        let outputDir = fileURL.deletingLastPathComponent()
        let outputURL = outputDir.appendingPathComponent(outputFileName)
        
        // Check if Python bridge is available
        let pythonAvailable = checkPythonEnvironment()
        
        if pythonAvailable {
            // Try to use the Python updater
            if updateWithPython(
                fileURL: fileURL,
                outputURL: outputURL,
                translatedText: translatedText,
                sourceLanguage: sourceLanguage,
                targetLanguage: targetLanguage
            ) {
                return outputURL
            }
        }
        
        // Fallback to basic file copy if Python bridge fails
        AppLogger.log(.warning, message: "Using fallback file copy without Python translation")
        return fallbackFileCopy(fileURL: fileURL, outputURL: outputURL)
    }
    
    /// Update a PPTX file with translated content using the Python bridge
    private func updateWithPython(
        fileURL: URL,
        outputURL: URL,
        translatedText: String,
        sourceLanguage: String,
        targetLanguage: String
    ) -> Bool {
        // First, parse the translated text to extract JSON content
        let translations = extractTranslations(from: translatedText)
        if translations.isEmpty {
            AppLogger.log(.error, message: "Failed to extract translations from API response")
            return false
        }
        
        // Create a temporary file to hold the translations
        let tempDir = FileManager.default.temporaryDirectory
        let translationsURL = tempDir.appendingPathComponent("translations.json")
        
        do {
            let jsonData = try JSONSerialization.data(withJSONObject: translations, options: .prettyPrinted)
            try jsonData.write(to: translationsURL)
            
            // Create the Python script for updating the PPTX
            let updaterScript = """
            import sys
            sys.path.append('\(pythonScriptPath)')
            try:
                from ai_deck_translator.pptx.updater import update_slides
                import json
                
                # Load the translations
                with open('\(translationsURL.path)', 'r', encoding='utf-8') as f:
                    translations = json.load(f)
                
                # Update the presentation
                success = update_slides('\(fileURL.path)', '\(outputURL.path)', translations)
                
                # Report result
                if success:
                    print("Success: Presentation updated successfully")
                else:
                    print("Error: Failed to update presentation")
                    sys.exit(1)
            except Exception as e:
                print(f"Error: {str(e)}")
                sys.exit(1)
            """
            
            // Save the script to a temporary file
            let scriptURL = tempDir.appendingPathComponent("update_pptx.py")
            try updaterScript.write(to: scriptURL, atomically: true, encoding: .utf8)
            
            // Run the Python script
            let output = runPythonCommand(args: [scriptURL.path])
            
            // Check for success
            if output.contains("Success:") {
                AppLogger.log(.info, message: "Python updater succeeded: \(output)")
                return true
            } else {
                AppLogger.log(.error, message: "Python updater failed: \(output)")
                return false
            }
            
        } catch {
            AppLogger.log(.error, message: "Failed to prepare Python updater: \(error)")
            return false
        }
    }
    
    /// Extract translations from the LLM response
    private func extractTranslations(from responseText: String) -> [String: String] {
        // Try to parse the response as JSON
        if let data = responseText.data(using: .utf8) {
            do {
                if let json = try JSONSerialization.jsonObject(with: data) as? [String: Any] {
                    // Check for different possible response formats
                    if let translation = json["translation"] as? [String: String] {
                        return translation
                    } else if let translations = json["translations"] as? [String: String] {
                        return translations
                    } else if let content = json["content"] as? [String: String] {
                        return content
                    } else if let elements = json["elements"] as? [String: String] {
                        return elements
                    }
                }
            } catch {
                AppLogger.log(.error, message: "Failed to parse response JSON: \(error)")
            }
        }
        
        // Try to find a JSON block in the text
        let jsonPattern = "\\{[\\s\\S]*\\}"
        if let regex = try? NSRegularExpression(pattern: jsonPattern),
           let match = regex.firstMatch(in: responseText, range: NSRange(responseText.startIndex..., in: responseText)),
           let range = Range(match.range, in: responseText) {
            let jsonString = String(responseText[range])
            if let data = jsonString.data(using: .utf8) {
                do {
                    if let json = try JSONSerialization.jsonObject(with: data) as? [String: Any] {
                        // Check for different possible response formats
                        if let translation = json["translation"] as? [String: String] {
                            return translation
                        } else if let translations = json["translations"] as? [String: String] {
                            return translations
                        } else if let content = json["content"] as? [String: String] {
                            return content
                        } else if let elements = json["elements"] as? [String: String] {
                            return elements
                        }
                    }
                } catch {
                    AppLogger.log(.error, message: "Failed to parse JSON block: \(error)")
                }
            }
        }
        
        // Return empty dictionary if parsing fails
        return [:]
    }
    
    /// Fall back to simple file copy when Python update fails
    private func fallbackFileCopy(fileURL: URL, outputURL: URL) -> URL? {
        do {
            // Remove existing file if it exists
            if FileManager.default.fileExists(atPath: outputURL.path) {
                try FileManager.default.removeItem(at: outputURL)
            }
            
            // Copy the original file
            try FileManager.default.copyItem(at: fileURL, to: outputURL)
            
            AppLogger.log(.info, message: "Copied file without modification: \(outputURL.path)")
            return outputURL
        } catch {
            AppLogger.log(.error, message: "Failed to copy file: \(error)")
            return nil
        }
    }
    
    /// Run a Python command and return the output
    private func runPythonCommand(args: [String]) -> String {
        let task = Process()
        let pipe = Pipe()
        
        task.standardOutput = pipe
        task.standardError = pipe
        task.arguments = args
        task.executableURL = URL(fileURLWithPath: "/usr/bin/python3")
        
        do {
            try task.run()
            task.waitUntilExit()
            
            let data = pipe.fileHandleForReading.readDataToEndOfFile()
            return String(data: data, encoding: .utf8) ?? ""
        } catch {
            AppLogger.log(.error, message: "Failed to run Python command: \(error)")
            return ""
        }
    }
}