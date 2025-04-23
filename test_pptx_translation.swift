#!/usr/bin/swift

import Foundation

// Simple test script for the PPTX translation functionality

// Path to a sample PPTX file
let samplePptxPath = "/Users/eprouveze/Documents/Dev/App/TranslationAssistantFinal/sample_presentation.pptx"
let outputDirectory = "/Users/eprouveze/Documents/Dev/App/TranslationAssistantFinal"

// Mock translation result - this would normally come from the LLM
let mockTranslation = """
{
    "translations": {
        "Sample Presentation": "サンプルプレゼンテーション",
        "An example PowerPoint presentation with text and tables": "テキストとテーブルを含むPowerPointプレゼンテーションの例",
        "Introduction": "はじめに",
        "This presentation demonstrates how to create a simple PPTX file using Python.": "このプレゼンテーションは、Pythonを使用して簡単なPPTXファイルを作成する方法を示しています。",
        "It contains a title slide, a text slide, and a slide with a table.": "タイトルスライド、テキストスライド、テーブル付きのスライドが含まれています。",
        "Sample Table": "サンプルテーブル",
        
        "Header 1": "ヘッダー 1",
        "Header 2": "ヘッダー 2",
        "Header 3": "ヘッダー 3",
        "Data 1": "データ 1",
        "Data 2": "データ 2",
        "Data 3": "データ 3",
        "Value 1": "値 1",
        "Value 2": "値 2",
        "Value 3": "値 3"
    }
}
"""

// Function to execute shell commands
func shell(_ command: String) -> (exitCode: Int32, output: String) {
    let task = Process()
    let pipe = Pipe()
    
    task.standardOutput = pipe
    task.standardError = pipe
    task.arguments = ["-c", command]
    task.launchPath = "/bin/bash"
    task.launch()
    
    let data = pipe.fileHandleForReading.readDataToEndOfFile()
    let output = String(data: data, encoding: .utf8) ?? ""
    
    task.waitUntilExit()
    return (task.terminationStatus, output)
}

// Check if the sample file exists
if !FileManager.default.fileExists(atPath: samplePptxPath) {
    print("⚠️ Test file not found at \(samplePptxPath)")
    print("Please create a sample PPTX file or update the path in this script.")
    exit(1)
}

print("🔍 Testing PPTX translation with file: \(samplePptxPath)")

// 1. Test Python environment
print("\n🐍 Checking Python environment...")
let pythonResult = shell("which python3")
if pythonResult.exitCode == 0 {
    print("✅ Python found: \(pythonResult.output.trimmingCharacters(in: .whitespacesAndNewlines))")
    
    // Check for required packages
    print("\n📦 Checking for required Python packages...")
    let pipResult = shell("pip3 list | grep python-pptx")
    print(pipResult.output)
    
    if pipResult.output.contains("python-pptx") {
        print("✅ python-pptx is installed")
    } else {
        print("⚠️ python-pptx is not installed. You may need to run: pip3 install python-pptx")
        exit(1)
    }
} else {
    print("❌ Python not found. Please install Python 3.")
    exit(1)
}

// 2. Create a temporary directory for output
let tempDir = "\(outputDirectory)/temp_pptx_test"
let _ = shell("mkdir -p \(tempDir)")

// 3. Write a temporary translation file
let translationFilePath = "\(tempDir)/translation.json"
do {
    try mockTranslation.write(to: URL(fileURLWithPath: translationFilePath), atomically: true, encoding: .utf8)
    print("\n💾 Saved mock translation to \(translationFilePath)")
} catch {
    print("❌ Failed to write translation file: \(error)")
    exit(1)
}

// 4. Create a simple Python script to test the extraction process
let extractScriptPath = "\(tempDir)/extract_test.py"
let extractScript = """
import sys
from pptx import Presentation
import json

try:
    # Load the presentation
    prs = Presentation(sys.argv[1])
    
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
                print(f"Found table in slide {slide_index}, shape {shape_index}")
                
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
                if shape.name.lower().startswith("title"):
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
        
        # Add this slide's metadata to the overall metadata
        slide_metadata["slides"].append(slide_meta)
    
    # Create result with both text and metadata
    result = {
        "text_elements": slides_text,
        "metadata": slide_metadata
    }
    
    # Print as JSON
    print(json.dumps(result, indent=2))
    print("Extraction successful!")
    
except Exception as e:
    print(f"Error during extraction: {str(e)}")
    sys.exit(1)
"""

do {
    try extractScript.write(to: URL(fileURLWithPath: extractScriptPath), atomically: true, encoding: .utf8)
    print("📝 Created extraction test script")
} catch {
    print("❌ Failed to write extraction script: \(error)")
    exit(1)
}

// 5. Run the extraction test
print("\n🔍 Testing text extraction...")
let extractResult = shell("python3 \(extractScriptPath) \(samplePptxPath)")
print(extractResult.output)

if extractResult.exitCode != 0 {
    print("❌ Extraction test failed")
    exit(1)
}

// 6. Create a simple Python script to test the update process
let updateScriptPath = "\(tempDir)/update_test.py"
let outputPptxPath = "\(tempDir)/translated_output.pptx"
let updateScript = """
import sys
from pptx import Presentation
import json

try:
    # Load the presentation and the translations
    prs = Presentation(sys.argv[1])
    
    with open(sys.argv[2], 'r') as f:
        translation_data = json.load(f)
    
    translations = translation_data['translations']
    
    print("Slide texts found in the presentation:")
    
    # First, display what we found in the presentation
    slide_index = 0
    for slide in prs.slides:
        slide_index += 1
        print(f"Slide {slide_index}:")
        
        # Track shape index for this slide
        shape_index = 0
        
        for shape in slide.shapes:
            shape_index += 1
            shape_id = f"slide{slide_index}_shape{shape_index}"
            
            # Handle tables
            if hasattr(shape, "has_table") and shape.has_table:
                print(f"  - Table: {shape.name}")
                
                for row_idx, row in enumerate(shape.table.rows):
                    for col_idx, cell in enumerate(row.cells):
                        if cell.text.strip():
                            cell_id = f"{shape_id}_table_r{row_idx}c{col_idx}"
                            print(f"    - Cell [{row_idx},{col_idx}]: '{cell.text}'")
            
            # Handle regular text
            elif hasattr(shape, "text") and shape.text:
                # Replace newlines for display only
                display_text = shape.text.replace("\\n", " ")
                print(f"  - {shape.name}: '{display_text}'")
    
    # Reset and apply translations
    print("\\nApplying translations:")
    slide_index = 0
    
    for slide in prs.slides:
        slide_index += 1
        print(f"Processing Slide {slide_index}:")
        
        # Track shape index for this slide
        shape_index = 0
        
        for shape in slide.shapes:
            shape_index += 1
            shape_id = f"slide{slide_index}_shape{shape_index}"
            
            # Handle tables
            if hasattr(shape, "has_table") and shape.has_table:
                print(f"  - Processing table in shape {shape_index}")
                
                for row_idx, row in enumerate(shape.table.rows):
                    for col_idx, cell in enumerate(row.cells):
                        if cell.text.strip():
                            original_text = cell.text
                            
                            # Try exact text matching for table cells
                            if original_text in translations:
                                translation = translations[original_text]
                                print(f"    - Cell [{row_idx},{col_idx}] match: '{original_text}' -> '{translation}'")
                                cell.text = translation
                            else:
                                # Try fuzzy matching as fallback
                                for key, trans in translations.items():
                                    if (key.lower() in original_text.lower() or 
                                        original_text.lower() in key.lower() or
                                        original_text.strip() == key.strip()):
                                        translation = trans
                                        print(f"    - Cell [{row_idx},{col_idx}] fuzzy match: '{original_text}' -> '{translation}'")
                                        cell.text = translation
                                        break
            
            # Handle regular text
            elif hasattr(shape, "text") and shape.text:
                original_text = shape.text
                translation = None
                
                # Try exact text matching first (most reliable)
                if original_text in translations:
                    translation = translations[original_text]
                    print(f"  - Exact match: '{original_text}' -> '{translation}'")
                
                # Try matching paragraphs individually
                elif "\\n" in original_text:
                    paragraphs = original_text.split("\\n")
                    translated_parts = []
                    
                    for para in paragraphs:
                        if para.strip() in translations:
                            translated_parts.append(translations[para.strip()])
                            print(f"  - Paragraph match: '{para.strip()}' -> '{translations[para.strip()]}'")
                        else:
                            # Keep original if no translation
                            translated_parts.append(para)
                            print(f"  - No match for paragraph: '{para.strip()}'")
                    
                    if any(part != paragraphs[i] for i, part in enumerate(translated_parts)):
                        translation = "\\n".join(translated_parts)
                
                # Last resort - try basic heuristic matching
                if not translation:
                    for key, trans in translations.items():
                        if key.lower() in original_text.lower() or original_text.lower() in key.lower():
                            translation = trans
                            print(f"  - Heuristic match: '{original_text}' to '{key}' -> '{translation}'")
                            break
                
                # Apply the translation if we found one
                if translation:
                    print(f"  - Applying translation for: '{original_text}'")
                    
                    # Replace text in the shape
                    if hasattr(shape, "text_frame"):
                        # Clear existing paragraphs
                        for i in range(len(shape.text_frame.paragraphs)-1, 0, -1):
                            p = shape.text_frame.paragraphs[i]
                            p.text = ""
                        
                        # Set the new text in the first paragraph
                        if len(shape.text_frame.paragraphs) > 0:
                            shape.text_frame.paragraphs[0].text = translation
                        
                        # Add additional paragraphs if needed
                        if "\\n" in translation and len(translation.split("\\n")) > 1:
                            paras = translation.split("\\n")[1:]  # Skip first para as it's already set
                            for para_text in paras:
                                if para_text.strip():  # Only add non-empty paragraphs
                                    p = shape.text_frame.add_paragraph()
                                    p.text = para_text
                else:
                    print(f"  - No translation found for: '{original_text}'")
    
    # Save the result
    prs.save(sys.argv[3])
    print(f"\\nTranslation successful! Output saved to {sys.argv[3]}")
    print(f"Translated to Japanese: 日本語に翻訳されました")
    
except Exception as e:
    print(f"Error during update: {str(e)}")
    sys.exit(1)
"""

do {
    try updateScript.write(to: URL(fileURLWithPath: updateScriptPath), atomically: true, encoding: .utf8)
    print("📝 Created update test script")
} catch {
    print("❌ Failed to write update script: \(error)")
    exit(1)
}

// 7. Run the update test
print("\n🔄 Testing PPTX update with translations...")
let updateResult = shell("python3 \(updateScriptPath) \(samplePptxPath) \(translationFilePath) \(outputPptxPath)")
print(updateResult.output)

if updateResult.exitCode != 0 {
    print("❌ Update test failed")
} else if FileManager.default.fileExists(atPath: outputPptxPath) {
    print("✅ Translation test completed successfully!")
    print("📊 Original PPTX: \(samplePptxPath)")
    print("📊 Translated PPTX: \(outputPptxPath)")
    
    // Open the files for comparison
    print("\n🔍 Opening original and translated files for comparison...")
    let _ = shell("open \(samplePptxPath)")
    let _ = shell("open \(outputPptxPath)")
} else {
    print("❌ Update process did not produce an output file")
}

print("\n🧹 Cleaning up test directory? (You may want to keep it for debugging)")
print("To clean up, run: rm -rf \(tempDir)")