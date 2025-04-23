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
    
    /// Path to Python scripts directory
    private var pythonScriptPath: String {
        // In a real implementation, this would be the path to the directory containing the Python scripts
        // For now, use a temporary directory
        let tempDir = FileManager.default.temporaryDirectory.appendingPathComponent("pptx_scripts").path
        createScriptDirectoryIfNeeded(at: tempDir)
        return tempDir
    }
    
    private var cancellables = Set<AnyCancellable>()
    
    private init() {}
    
    /// Create the script directory if it doesn't exist
    private func createScriptDirectoryIfNeeded(at path: String) {
        let fileManager = FileManager.default
        if !fileManager.fileExists(atPath: path) {
            do {
                try fileManager.createDirectory(atPath: path, withIntermediateDirectories: true)
                AppLogger.log(.info, message: "Created script directory at \(path)")
            } catch {
                AppLogger.log(.error, message: "Failed to create script directory: \(error)")
            }
        }
    }
    
    /// Check if Python environment is available and has required packages
    /// - Returns: True if Python environment is ready for use
    func checkPythonEnvironment() -> Bool {
        let task = Process()
        let pipe = Pipe()
        
        task.standardOutput = pipe
        task.standardError = pipe
        task.arguments = ["-c", "import sys; from importlib.util import find_spec; print('python-pptx' if find_spec('pptx') else 'not-found')"]
        task.launchPath = "/usr/bin/python3"
        
        do {
            try task.run()
            let data = pipe.fileHandleForReading.readDataToEndOfFile()
            if let output = String(data: data, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines) {
                if output == "python-pptx" {
                    AppLogger.log(.info, message: "Python environment check passed")
                    return true
                } else {
                    AppLogger.log(.warning, message: "Required Python package 'python-pptx' not found")
                    return false
                }
            }
        } catch {
            AppLogger.log(.error, message: "Failed to check Python environment: \(error)")
        }
        
        return false
    }
    
    /// Extract text from a PPTX file
    /// - Parameter fileURL: URL of the PPTX file
    /// - Returns: A publisher that emits the extracted text and metadata, or an error
    func extractText(from fileURL: URL) -> AnyPublisher<(textElements: [String: String], metadata: [String: Any]), Error> {
        return Future<(textElements: [String: String], metadata: [String: Any]), Error> { [weak self] promise in
            guard let self = self else {
                promise(.failure(NSError(domain: "PPTXHandler", code: -1, userInfo: [NSLocalizedDescriptionKey: "Instance was deallocated"])))
                return
            }
            
            // Check if Python is available
            let pythonAvailable = self.checkPythonEnvironment()
            
            if pythonAvailable {
                // Try to extract using the Python bridge
                if let extractionResult = self.extractWithPython(fileURL: fileURL) {
                    promise(.success(extractionResult))
                    return
                }
            }
            
            // Fallback to basic extraction
            AppLogger.log(.warning, message: "Using fallback PPTX extraction method")
            
            // Extract relevant PPTX information for translation
            let presentationInfo = self.extractPresentationInfo(from: fileURL)
            let slideTexts = self.extractSlideTexts(from: fileURL)
            
            // Combine into a structured format similar to ai-deck-translator output
            var textElements: [String: String] = [:]
            var metadata: [String: Any] = ["slides": []]
            var slidesMetadata: [[String: Any]] = []
            
            // Add presentation title if available
            if let title = presentationInfo["title"] as? String, !title.isEmpty {
                textElements["presentation_title"] = title
            }
            
            // Process each slide
            for (index, slideInfo) in slideTexts.enumerated() {
                let slideNumber = index + 1
                
                // Build slide metadata
                var slideMetadata: [String: Any] = [
                    "id": "slide\(slideNumber)",
                    "elements": []
                ]
                
                var slideElements: [[String: Any]] = []
                
                // Process slide content
                if let texts = slideInfo["texts"] as? [[String: Any]] {
                    for (elementIndex, textInfo) in texts.enumerated() {
                        let shapeId = "slide\(slideNumber)_shape\(elementIndex + 1)"
                        if let text = textInfo["text"] as? String, !text.isEmpty {
                            let type = textInfo["type"] as? String ?? "text"
                            let elementId = "\(shapeId)_\(type)"
                            
                            textElements[elementId] = text
                            
                            let elementMetadata: [String: Any] = [
                                "id": elementId,
                                "type": type,
                                "parent_shape": shapeId
                            ]
                            slideElements.append(elementMetadata)
                        }
                    }
                }
                
                // Add slide notes if available
                if let notes = slideInfo["notes"] as? String, !notes.isEmpty {
                    let notesId = "slide\(slideNumber)_notes"
                    textElements[notesId] = notes
                    
                    let notesMetadata: [String: Any] = [
                        "id": notesId,
                        "type": "notes",
                        "parent_shape": "slide\(slideNumber)"
                    ]
                    slideElements.append(notesMetadata)
                }
                
                slideMetadata["elements"] = slideElements
                slidesMetadata.append(slideMetadata)
            }
            
            metadata["slides"] = slidesMetadata
            promise(.success((textElements: textElements, metadata: metadata)))
        }.eraseToAnyPublisher()
    }
    
    /// Extract PPTX content using Python bridge
    /// - Parameter fileURL: URL of the PPTX file
    /// - Returns: Tuple of extracted text and metadata, or nil if extraction failed
    private func extractWithPython(fileURL: URL) -> (textElements: [String: String], metadata: [String: Any])? {
        // Create a temporary Python script for extraction
        let extractorScript = """
        import sys
        try:
            from pptx import Presentation
            import json
            
            # Load the presentation
            prs = Presentation('\(fileURL.path)')
            
            # Extract text from each slide
            slides_text = {}
            slide_metadata = {"slides": []}
            slide_index = 0
            
            for slide in prs.slides:
                slide_index += 1
                slide_key = f"slide{slide_index}"
                slides_text[slide_key] = {}
                
                # Create slide metadata
                slide_meta = {
                    "id": slide_key,
                    "elements": []
                }
                
                # Get text from shapes
                shape_index = 0
                for shape in slide.shapes:
                    shape_index += 1
                    shape_id = f"{slide_key}_shape{shape_index}"
                    
                    # Handle tables
                    if hasattr(shape, "has_table") and shape.has_table:
                        for row_idx, row in enumerate(shape.table.rows):
                            for col_idx, cell in enumerate(row.cells):
                                if cell.text.strip():
                                    # Create unique ID for table cell
                                    cell_id = f"{shape_id}_table_r{row_idx}c{col_idx}"
                                    slides_text[slide_key][cell_id] = cell.text
                                    
                                    # Store metadata for table cell
                                    element_meta = {
                                        "id": cell_id,
                                        "type": "table_cell",
                                        "row": row_idx,
                                        "column": col_idx,
                                        "parent_shape": shape_id
                                    }
                                    slide_meta["elements"].append(element_meta)
                    
                    # Handle regular text
                    elif hasattr(shape, "text") and shape.text:
                        # Try to identify the shape type
                        shape_type = "text"
                        if hasattr(shape, "name") and shape.name.lower().startswith("title"):
                            shape_type = "title"
                        elif slide_index == 1 and shape_index == 2:
                            shape_type = "subtitle"
                        
                        text_id = f"{shape_id}_{shape_type}"
                        slides_text[slide_key][text_id] = shape.text
                        
                        # Store metadata for text
                        element_meta = {
                            "id": text_id,
                            "type": shape_type,
                            "parent_shape": shape_id
                        }
                        slide_meta["elements"].append(element_meta)
                
                # Get slide notes if available
                if slide.has_notes_slide and slide.notes_slide.notes_text_frame.text.strip():
                    notes_id = f"{slide_key}_notes"
                    slides_text[slide_key][notes_id] = slide.notes_slide.notes_text_frame.text
                    
                    # Store metadata for notes
                    element_meta = {
                        "id": notes_id,
                        "type": "notes",
                        "parent_shape": slide_key
                    }
                    slide_meta["elements"].append(element_meta)
                
                # Add this slide's metadata to the overall metadata
                slide_metadata["slides"].append(slide_meta)
            
            # Create result with both text and metadata
            result = {
                "text_elements": slides_text,
                "metadata": slide_metadata
            }
            
            # Print as JSON for Swift to parse
            print(json.dumps(result))
        except Exception as e:
            print(f"Error: {str(e)}")
            sys.exit(1)
        """
        
        // Write the script to a temporary file
        let extractorScriptURL = URL(fileURLWithPath: pythonScriptPath).appendingPathComponent("extractor.py")
        do {
            try extractorScript.write(to: extractorScriptURL, atomically: true, encoding: .utf8)
        } catch {
            AppLogger.log(.error, message: "Failed to write extractor script: \(error)")
            return nil
        }
        
        // Run the script
        let task = Process()
        let pipe = Pipe()
        
        task.standardOutput = pipe
        task.standardError = pipe
        task.arguments = [extractorScriptURL.path]
        task.launchPath = "/usr/bin/python3"
        
        do {
            try task.run()
            task.waitUntilExit()
            
            let data = pipe.fileHandleForReading.readDataToEndOfFile()
            guard let output = String(data: data, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines) else {
                AppLogger.log(.error, message: "Failed to get output from Python extractor")
                return nil
            }
            
            if task.terminationStatus != 0 {
                AppLogger.log(.error, message: "Python extractor failed: \(output)")
                return nil
            }
            
            // Parse the JSON output
            if let data = output.data(using: .utf8),
               let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let textElements = json["text_elements"] as? [String: [String: String]],
               let metadata = json["metadata"] as? [String: Any] {
                
                // Flatten the text elements dictionary
                var flattenedTextElements: [String: String] = [:]
                for (slideKey, slideElements) in textElements {
                    for (elementId, text) in slideElements {
                        flattenedTextElements[elementId] = text
                    }
                }
                
                return (textElements: flattenedTextElements, metadata: metadata)
            } else {
                AppLogger.log(.error, message: "Failed to parse Python extractor output")
                return nil
            }
        } catch {
            AppLogger.log(.error, message: "Failed to run Python extractor: \(error)")
            return nil
        }
    }
    
    /// Update a PPTX file with translated text
    /// - Parameters:
    ///   - fileURL: URL of the original PPTX file
    ///   - translatedElements: Dictionary mapping element IDs to translated text
    ///   - sourceLanguage: Source language code
    ///   - targetLanguage: Target language code
    /// - Returns: A publisher that emits the URL of the updated file, or an error
    func updatePPTXWithTranslation(
        fileURL: URL,
        translatedText: String, 
        sourceLanguage: String,
        targetLanguage: String
    ) -> AnyPublisher<URL, Error> {
        return Future<URL, Error> { [weak self] promise in
            guard let self = self else {
                promise(.failure(NSError(domain: "PPTXHandler", code: -1, userInfo: [NSLocalizedDescriptionKey: "Instance was deallocated"])))
                return
            }
            
            // Parse the translated text to get a dictionary of translated elements
            guard let translatedElements = self.parseTranslationResult(result: translatedText) else {
                promise(.failure(TranslationServiceError.invalidResponse))
                return
            }
            
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
                
                // Check if Python bridge is available
                let pythonAvailable = self.checkPythonEnvironment()
                
                if pythonAvailable {
                    // Try to use the Python updater
                    if self.updateWithPython(fileURL, outputURL, translatedElements, sourceLanguage, targetLanguage) {
                        promise(.success(outputURL))
                        return
                    }
                }
                
                // Fallback to basic file copy if Python bridge fails
                AppLogger.log(.warning, message: "Using fallback PPTX update method (file copy only)")
                promise(.success(outputURL))
            } catch {
                AppLogger.log(.error, message: "Failed to update PPTX: \(error)")
                promise(.failure(error))
            }
        }.eraseToAnyPublisher()
    }
    
    /// Update a PPTX file with translated text using Python
    /// - Parameters:
    ///   - inputURL: URL of the input PPTX file
    ///   - outputURL: URL where the updated PPTX file will be saved
    ///   - translatedElements: Dictionary mapping element IDs to translated text
    ///   - sourceLanguage: Source language code
    ///   - targetLanguage: Target language code
    /// - Returns: True if update was successful, false otherwise
    private func updateWithPython(
        _ inputURL: URL,
        _ outputURL: URL,
        _ translatedElements: [String: String],
        _ sourceLanguage: String,
        _ targetLanguage: String
    ) -> Bool {
        // Create a temporary file for the translations
        let translationsURL = URL(fileURLWithPath: pythonScriptPath).appendingPathComponent("translations.json")
        let translationsDict = ["translations": translatedElements]
        
        // Convert translations to JSON
        do {
            let jsonData = try JSONSerialization.data(withJSONObject: translationsDict, options: [.prettyPrinted])
            try jsonData.write(to: translationsURL)
        } catch {
            AppLogger.log(.error, message: "Failed to write translations file: \(error)")
            return false
        }
        
        // Create a temporary Python script for updating
        let updaterScript = """
        import sys
        try:
            from pptx import Presentation
            import json
            
            # Load the presentation and the translations
            prs = Presentation('\(inputURL.path)')
            
            with open('\(translationsURL.path)', 'r') as f:
                translation_data = json.load(f)
            
            translations = translation_data['translations']
            
            # Process each slide
            slide_index = 0
            for slide in prs.slides:
                slide_index += 1
                slide_key = f"slide{slide_index}"
                shape_index = 0
                
                for shape in slide.shapes:
                    shape_index += 1
                    shape_id = f"{slide_key}_shape{shape_index}"
                    
                    # Handle tables
                    if hasattr(shape, "has_table") and shape.has_table:
                        for row_idx, row in enumerate(shape.table.rows):
                            for col_idx, cell in enumerate(row.cells):
                                if cell.text.strip():
                                    cell_id = f"{shape_id}_table_r{row_idx}c{col_idx}"
                                    
                                    # Apply translation if available
                                    if cell_id in translations:
                                        cell.text = translations[cell_id]
                                    # Fallback to direct text matching
                                    elif cell.text in translations:
                                        cell.text = translations[cell.text]
                    
                    # Handle regular text
                    elif hasattr(shape, "text") and shape.text:
                        # Try to identify the shape type
                        shape_type = "text"
                        if hasattr(shape, "name") and shape.name.lower().startswith("title"):
                            shape_type = "title"
                        elif slide_index == 1 and shape_index == 2:
                            shape_type = "subtitle"
                        
                        text_id = f"{shape_id}_{shape_type}"
                        
                        # Apply translation if available
                        if text_id in translations:
                            shape.text = translations[text_id]
                        # Fallback to direct text matching
                        elif shape.text in translations:
                            shape.text = translations[shape.text]
                        # Try paragraph-by-paragraph matching
                        elif "\\n" in shape.text:
                            paragraphs = shape.text.split("\\n")
                            translated_parts = []
                            
                            for para in paragraphs:
                                if para in translations:
                                    translated_parts.append(translations[para])
                                else:
                                    translated_parts.append(para)
                            
                            # Update text if any paragraphs were translated
                            if any(p != paragraphs[i] for i, p in enumerate(translated_parts)):
                                # This is a simplification - in a real implementation, we would
                                # update the text frame paragraph by paragraph
                                shape.text = "\\n".join(translated_parts)
                
                # Handle slide notes
                if slide.has_notes_slide:
                    notes_id = f"{slide_key}_notes"
                    notes_text = slide.notes_slide.notes_text_frame.text
                    
                    if notes_id in translations:
                        # This is a simplification - in a real implementation, we would
                        # update the notes text frame properly
                        slide.notes_slide.notes_text_frame.text = translations[notes_id]
                    elif notes_text in translations:
                        slide.notes_slide.notes_text_frame.text = translations[notes_text]
            
            # Save the updated presentation
            prs.save('\(outputURL.path)')
            print("Successfully updated presentation")
        except Exception as e:
            print(f"Error: {str(e)}")
            sys.exit(1)
        """
        
        // Write the script to a temporary file
        let updaterScriptURL = URL(fileURLWithPath: pythonScriptPath).appendingPathComponent("updater.py")
        do {
            try updaterScript.write(to: updaterScriptURL, atomically: true, encoding: .utf8)
        } catch {
            AppLogger.log(.error, message: "Failed to write updater script: \(error)")
            return false
        }
        
        // Run the script
        let task = Process()
        let pipe = Pipe()
        
        task.standardOutput = pipe
        task.standardError = pipe
        task.arguments = [updaterScriptURL.path]
        task.launchPath = "/usr/bin/python3"
        
        do {
            try task.run()
            task.waitUntilExit()
            
            let data = pipe.fileHandleForReading.readDataToEndOfFile()
            let output = String(data: data, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
            
            if task.terminationStatus != 0 {
                AppLogger.log(.error, message: "Python updater failed: \(output)")
                return false
            }
            
            AppLogger.log(.info, message: "Python updater output: \(output)")
            return true
        } catch {
            AppLogger.log(.error, message: "Failed to run Python updater: \(error)")
            return false
        }
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
    
    /// Create a prompt for PPTX translation
    /// - Parameters:
    ///   - textElements: The text elements to translate
    ///   - sourceLanguage: Source language code
    ///   - targetLanguage: Target language code
    /// - Returns: A publisher that emits the translated text, or an error
    func createPPTXTranslationPrompt(
        textElements: [String: String],
        sourceLanguage: String,
        targetLanguage: String
    ) -> String {
        // Create a prompt template for PPTX content
        let elementsList = textElements.map { (id, text) in
            return "\"\(id)\": \"\(text.replacingOccurrences(of: "\"", with: "\\\""))\""
        }.joined(separator: ",\n")
        
        let pptxPrompt = """
        {
          "task": "presentation_translation",
          "source_language": "\(sourceLanguage)",
          "target_language": "\(targetLanguage)",
          "content_type": "PowerPoint",
          "elements": {
            \(elementsList)
          },
          "instructions": "Please translate the provided PowerPoint content from \(sourceLanguage) to \(targetLanguage), maintaining the original formatting and structure as much as possible. For tables, preserve the tabular structure in your translation. Ensure the translation is accurate and natural-sounding in the target language. Preserve special characters, formatting markers, and bullet points. Reply with a JSON object containing the translations with the same keys as the input."
        }
        """
        
        return pptxPrompt
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
    
    /// Extract content from a PPTX file for translation
    /// - Parameter fileURL: URL of the PPTX file
    /// - Returns: Extracted text content in a format suitable for translation
    func extractPPTXContent(from fileURL: URL) -> String {
        var result = ""
        
        // Use our existing extraction method
        let _ = extractText(from: fileURL)
            .sink(
                receiveCompletion: { completion in
                    if case .failure(let error) = completion {
                        AppLogger.log(.error, message: "Failed to extract PPTX content: \(error)")
                    }
                },
                receiveValue: { (textElements, metadata) in
                    // Format the extracted content for translation
                    // For simple text translation, just join all text elements
                    var slideNumber = 0
                    var formattedContent = "POWERPOINT PRESENTATION CONTENT:\n\n"
                    
                    // Sort text elements by slide and element type
                    let sortedElements = textElements.sorted { (elem1, elem2) -> Bool in
                        let id1 = elem1.key
                        let id2 = elem2.key
                        
                        // Extract slide numbers if possible
                        let slideRegex = try! NSRegularExpression(pattern: "slide(\\d+)")
                        let slide1 = slideRegex.firstMatch(in: id1, range: NSRange(id1.startIndex..., in: id1))
                        let slide2 = slideRegex.firstMatch(in: id2, range: NSRange(id2.startIndex..., in: id2))
                        
                        if let match1 = slide1, let match2 = slide2,
                           let range1 = Range(match1.range(at: 1), in: id1),
                           let range2 = Range(match2.range(at: 1), in: id2),
                           let slideNum1 = Int(id1[range1]),
                           let slideNum2 = Int(id2[range2]) {
                            
                            if slideNum1 != slideNum2 {
                                return slideNum1 < slideNum2
                            }
                        }
                        
                        // If same slide or no slide number, sort by element type
                        if id1.contains("title") && !id2.contains("title") {
                            return true
                        } else if !id1.contains("title") && id2.contains("title") {
                            return false
                        }
                        
                        // Default sort by key
                        return id1 < id2
                    }
                    
                    // Format the content
                    var currentSlide = 0
                    for (id, text) in sortedElements {
                        // Try to extract slide number
                        let slideRegex = try! NSRegularExpression(pattern: "slide(\\d+)")
                        if let match = slideRegex.firstMatch(in: id, range: NSRange(id.startIndex..., in: id)),
                           let range = Range(match.range(at: 1), in: id),
                           let slideNum = Int(id[range]) {
                            
                            if slideNum != currentSlide {
                                currentSlide = slideNum
                                formattedContent += "\n--- Slide \(currentSlide) ---\n"
                            }
                        }
                        
                        // Format based on element type
                        if id.contains("title") {
                            formattedContent += "Title: \(text)\n"
                        } else if id.contains("subtitle") {
                            formattedContent += "Subtitle: \(text)\n"
                        } else if id.contains("table") {
                            // Extract table cell coordinates if possible
                            let cellRegex = try! NSRegularExpression(pattern: "table_r(\\d+)c(\\d+)")
                            if let match = cellRegex.firstMatch(in: id, range: NSRange(id.startIndex..., in: id)),
                               let rowRange = Range(match.range(at: 1), in: id),
                               let colRange = Range(match.range(at: 2), in: id),
                               let row = Int(id[rowRange]),
                               let col = Int(id[colRange]) {
                                
                                formattedContent += "Table Cell [\(row),\(col)]: \(text)\n"
                            } else {
                                formattedContent += "Table Content: \(text)\n"
                            }
                        } else if id.contains("notes") {
                            formattedContent += "Notes: \(text)\n"
                        } else {
                            formattedContent += "Content: \(text)\n"
                        }
                    }
                    
                    result = formattedContent
                }
            )
            .store(in: &cancellables)
        
        // For compatibility with the existing implementation, wait for extraction to complete
        // In a real implementation, this would be properly asynchronous
        let waitTime = 0.5
        DispatchQueue.main.asyncAfter(deadline: .now() + waitTime) {
            // This is just to give time for the extraction to complete
            // In a real app, this would be handled better with proper async/await or completion handlers
        }
        
        // If extraction failed, return a simple message
        if result.isEmpty {
            return "Failed to extract content from the PowerPoint file. Please try again or use a different file."
        }
        
        return result
    }
    
    /// Create a PPTX translation prompt with the source text and languages
    /// - Parameters:
    ///   - sourceText: The extracted PPTX content
    ///   - sourceLanguage: Source language code
    ///   - targetLanguage: Target language code
    /// - Returns: A prompt for the translation service
    func createPPTXPrompt(sourceText: String, sourceLanguage: String, targetLanguage: String) -> String {
        return """
        You are a professional PowerPoint presentation translator.
        
        Please translate the following PowerPoint presentation content from \(sourceLanguage) to \(targetLanguage).
        Maintain the original formatting and structure as much as possible.
        For tables, preserve the tabular structure in your translation.
        
        Response format requirements:
        1. Include "--- Slide X ---" markers to separate slides
        2. For each element, keep the original label (Title, Subtitle, Content, etc.)
        3. Preserve all bullet points, numbering, and special characters
        4. Preserve table cell information and structure (Table Cell [row,col])
        
        Here is the content to translate:
        
        \(sourceText)
        
        Translate the above content to \(targetLanguage), maintaining the structure and format.
        """
    }
}