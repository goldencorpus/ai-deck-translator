"""
Progress tracking utilities for translation processes.
"""
from tqdm import tqdm as tqdm_original

class CustomTqdm:
    """A custom progress bar wrapper that can be used in different contexts."""
    
    def __init__(self, total, desc="", **kwargs):
        """
        Initialize the progress tracker.
        
        Args:
            total: Total number of items
            desc: Description of the progress bar
            **kwargs: Additional arguments to pass to tqdm
        """
        self.total = total
        self.n = 0
        self.description = desc
        self.tqdm_instance = tqdm_original(total=total, desc=desc, **kwargs)
        self.callback = None
    
    def update(self, n=1):
        """
        Update the progress bar.
        
        Args:
            n: Number of items to increment by
        """
        self.n += n
        self.tqdm_instance.update(n)
        
        # Call the callback if registered
        if self.callback:
            progress = int(100 * self.n / self.total) if self.total > 0 else 0
            self.callback(progress)
    
    def set_description(self, desc):
        """
        Set the description of the progress bar.
        
        Args:
            desc: Description text
        """
        self.description = desc
        self.tqdm_instance.set_description(desc)
    
    def register_callback(self, callback):
        """
        Register a callback function to be called when progress is updated.
        
        Args:
            callback: Function that takes a progress percentage (0-100)
        """
        self.callback = callback
    
    def close(self):
        """Close the progress bar."""
        self.tqdm_instance.close()

class WebUITqdm(CustomTqdm):
    """Specialized progress bar for the web UI."""
    
    def __init__(self, total, web_state=None, **kwargs):
        """
        Initialize the web UI progress bar.
        
        Args:
            total: Total number of items
            web_state: Dictionary containing web state to update
            **kwargs: Additional arguments to pass to tqdm
        """
        super().__init__(total, **kwargs)
        self.web_state = web_state
    
    def update(self, n=1):
        """
        Update the progress bar and web state.
        
        Args:
            n: Number of items to increment by
        """
        self.n += n
        if self.total > 0 and self.web_state:
            self.web_state['progress'] = int(100 * self.n / self.total)
        
        # Skip calling tqdm's update to avoid console output in web mode
        if self.callback:
            progress = int(100 * self.n / self.total) if self.total > 0 else 0
            self.callback(progress)
    
    def set_description(self, desc):
        """
        Set the description (no-op in web mode).
        
        Args:
            desc: Description text
        """
        self.description = desc
        # No visual update in web mode

def create_progress_bar(total, desc="", web_state=None, **kwargs):
    """
    Factory function to create an appropriate progress bar.
    
    Args:
        total: Total number of items
        desc: Description of the progress bar
        web_state: Optional web state dictionary for web UI mode
        **kwargs: Additional arguments to pass to tqdm
        
    Returns:
        CustomTqdm or WebUITqdm instance
    """
    if web_state is not None:
        return WebUITqdm(total, web_state=web_state, desc=desc, **kwargs)
    else:
        return CustomTqdm(total, desc=desc, **kwargs) 