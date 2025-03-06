"""
Recovery utilities for handling translation progress and resuming failed translations.
"""
import os
import json
from datetime import datetime
from .. import config

def setup_recovery_system(presentation_id, text_dict, slide_metadata, source_language, target_language, resume_file=None):
    """
    Set up or load a recovery system for translation.
    
    Args:
        presentation_id: ID of the presentation being translated
        text_dict: Dictionary of text to translate
        slide_metadata: Metadata about slides
        source_language: Source language code
        target_language: Target language code
        resume_file: Optional file path to resume from
        
    Returns:
        tuple: (recovery_state, recovery_file_path, save_recovery_state_function)
    """
    # Create a directory for recovery files if it doesn't exist
    recovery_dir = config.RECOVERY_DIR
    os.makedirs(recovery_dir, exist_ok=True)
    
    # If a resume file is provided, load the state from that file
    if resume_file and os.path.exists(resume_file):
        with open(resume_file, 'r', encoding='utf-8') as f:
            recovery_state = json.load(f)
        recovery_file_path = resume_file
        print(f"Resuming translation from recovery file: {resume_file}")
    else:
        # Create a new recovery file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        recovery_file_path = os.path.join(recovery_dir, f"recovery_{presentation_id}_{timestamp}.json")
        
        # Initialize recovery state
        recovery_state = {
            "presentation_id": presentation_id,
            "source_language": source_language,
            "target_language": target_language,
            "start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_items": len(text_dict),
            "completed_batches": [],
            "failed_batches": [],
            "translated_items": {},
            "slide_metadata": slide_metadata
        }
    
    # Define a function to save the recovery state
    def save_recovery_state():
        recovery_state["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(recovery_file_path, 'w', encoding='utf-8') as f:
            json.dump(recovery_state, f, ensure_ascii=False, indent=2)
    
    # Save initial state if this is a new recovery file
    if not resume_file or not os.path.exists(resume_file):
        save_recovery_state()
    
    return recovery_state, recovery_file_path, save_recovery_state

def list_recovery_files():
    """
    List all available recovery files and their status.
    
    Returns:
        list: List of dictionaries with recovery file information
    """
    recovery_dir = config.RECOVERY_DIR
    if not os.path.exists(recovery_dir):
        print("No recovery directory found.")
        return []
    
    recovery_files = [f for f in os.listdir(recovery_dir) if f.endswith(".json")]
    
    if not recovery_files:
        print("No recovery files found.")
        return []
    
    results = []
    print(f"Found {len(recovery_files)} recovery files:")
    for f in recovery_files:
        file_path = os.path.join(recovery_dir, f)
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                data = json.load(file)
                total = data.get("total_items", 0)
                translated = len(data.get("translated_items", {}))
                failed = len(data.get("failed_batches", []))
                progress = (translated / total * 100) if total > 0 else 0
                
                info = {
                    "filename": f,
                    "path": file_path,
                    "presentation_id": data.get("presentation_id", "unknown"),
                    "source_language": data.get("source_language", "unknown"),
                    "target_language": data.get("target_language", "unknown"),
                    "progress": progress,
                    "total_items": total,
                    "translated_items": translated,
                    "failed_batches": failed,
                    "start_time": data.get("start_time", "unknown"),
                    "last_updated": data.get("last_updated", "unknown")
                }
                
                results.append(info)
                
                print(f"  {f}")
                print(f"    Progress: {progress:.1f}% ({translated}/{total} items)")
                print(f"    Failed batches: {failed}")
                print(f"    Start time: {data.get('start_time', 'unknown')}")
                print(f"    Last updated: {data.get('last_updated', 'unknown')}")
                print()
        except Exception as e:
            print(f"  {f} - Error reading file: {e}")
    
    return results 