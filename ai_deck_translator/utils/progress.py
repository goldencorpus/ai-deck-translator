"""
Progress tracking utilities for translation processes.

This module provides classes and functions for tracking progress during translation
operations. It includes support for both command-line and web UI progress reporting,
with customizable callbacks for integration with different interfaces.

Public Classes:
    CustomTqdm: A custom progress bar wrapper for command-line interfaces
    WebUITqdm: A progress bar wrapper for web interfaces
    ProgressTracker: A simple progress tracker for translation processes

Public Functions:
    create_progress_bar: Factory function to create the appropriate progress bar
"""
from typing import Callable, Optional, Dict, Any
from tqdm import tqdm as tqdm_original
from ..utils.logging import get_logger

# Set up logging
logger = get_logger(__name__)

class ProgressTracker:
    """
    A simple progress tracker for translation processes.
    
    This class provides a simple interface for tracking progress during translation
    processes. It supports callback functions for integration with different UIs.
    
    Attributes:
        total (int): Total number of items to process
        current (int): Current number of processed items
        callback (callable, optional): Callback function for progress updates
    """
    
    def __init__(self, total: int, callback: Optional[Callable[[int, int], None]] = None):
        """
        Initialize the progress tracker.
        
        Args:
            total (int): Total number of items to process
            callback (callable, optional): Callback function for progress updates.
                The function should accept two integers: current progress and total items.
        
        Raises:
            ValueError: If total is negative
        """
        if total < 0:
            raise ValueError("Total must be a non-negative integer")
            
        self.total = total
        self.current = 0
        self.callback = callback
        
        logger.debug(f"Created progress tracker (total: {total})")
    
    def update(self, n: int = 1):
        """
        Update the progress tracker.
        
        Args:
            n (int, optional): Number of items to increment by (default: 1)
            
        Raises:
            ValueError: If n is negative
        """
        if n < 0:
            raise ValueError("Update increment must be non-negative")
            
        self.current += n
        
        # Call the callback if registered
        if self.callback:
            self.callback(self.current, self.total)
            
        logger.debug(f"Progress updated: {self.current}/{self.total} ({int(100 * self.current / self.total) if self.total > 0 else 0}%)")
    
    def reset(self):
        """
        Reset the progress tracker.
        """
        self.current = 0
        logger.debug("Progress tracker reset")
    
    def is_complete(self) -> bool:
        """
        Check if the progress is complete.
        
        Returns:
            bool: True if the progress is complete, False otherwise
        """
        return self.current >= self.total

class CustomTqdm:
    """
    A custom progress bar wrapper that can be used in different contexts.
    
    This class wraps the tqdm progress bar library to provide a consistent
    interface for progress tracking across different parts of the application.
    It supports callback functions for integration with custom UIs.
    
    Attributes:
        total (int): Total number of items to process
        n (int): Current number of processed items
        description (str): Description text for the progress bar
        tqdm_instance (tqdm): The underlying tqdm instance
        callback (callable, optional): Callback function for progress updates
    """
    
    def __init__(self, total: int, desc: str = "", **kwargs):
        """
        Initialize the progress tracker.
        
        Args:
            total (int): Total number of items to process
            desc (str, optional): Description of the progress bar
            **kwargs: Additional arguments to pass to tqdm
                These can include:
                - unit (str): Unit name (default: "it")
                - unit_scale (bool): Whether to scale units (default: False)
                - ncols (int): Width of the progress bar
                - colour (str): Color of the progress bar
        
        Raises:
            ValueError: If total is negative
        """
        if total < 0:
            raise ValueError("Total must be a non-negative integer")
            
        self.total = total
        self.n = 0
        self.description = desc
        self.tqdm_instance = tqdm_original(total=total, desc=desc, **kwargs)
        self.callback = None
        
        logger.debug(f"Created progress bar: {desc} (total: {total})")
    
    def update(self, n: int = 1):
        """
        Update the progress bar.
        
        Args:
            n (int, optional): Number of items to increment by (default: 1)
            
        Raises:
            ValueError: If n is negative
        """
        if n < 0:
            raise ValueError("Update increment must be non-negative")
            
        self.n += n
        self.tqdm_instance.update(n)
        
        # Call the callback if registered
        if self.callback:
            progress = int(100 * self.n / self.total) if self.total > 0 else 0
            self.callback(progress)
            
        logger.debug(f"Progress updated: {self.n}/{self.total} ({int(100 * self.n / self.total) if self.total > 0 else 0}%)")
    
    def set_description(self, desc: str):
        """
        Set the description of the progress bar.
        
        Args:
            desc (str): Description text
        """
        self.description = desc
        self.tqdm_instance.set_description(desc)
        logger.debug(f"Progress description updated: {desc}")
    
    def register_callback(self, callback: Callable[[int], None]):
        """
        Register a callback function for progress updates.
        
        The callback function will be called whenever the progress is updated,
        with the current progress percentage (0-100) as an argument.
        
        Args:
            callback (callable): Function that takes a progress percentage (int)
        """
        self.callback = callback
        logger.debug("Callback registered for progress updates")
    
    def close(self):
        """
        Close the progress bar and clean up resources.
        """
        self.tqdm_instance.close()
        logger.debug("Progress bar closed")


class WebUITqdm(CustomTqdm):
    """
    A progress bar wrapper for web interfaces.
    
    This class extends CustomTqdm to provide integration with web UIs by
    updating a shared state dictionary that can be accessed by the web server.
    
    Attributes:
        web_state (dict): Dictionary for tracking state in the web UI
    """
    
    def __init__(self, total: int, web_state: Optional[Dict[str, Any]] = None, **kwargs):
        """
        Initialize the web UI progress tracker.
        
        Args:
            total (int): Total number of items to process
            web_state (dict, optional): Dictionary for tracking state in the web UI
            **kwargs: Additional arguments to pass to tqdm
        """
        super().__init__(total, **kwargs)
        self.web_state = web_state
        
        # Initialize web state if provided
        if self.web_state is not None:
            self.web_state['progress'] = 0
            logger.debug("Initialized web UI progress tracker")
    
    def update(self, n: int = 1):
        """
        Update the progress bar and web UI state.
        
        Args:
            n (int, optional): Number of items to increment by (default: 1)
        """
        super().update(n)
        
        # Update web state if provided
        if self.web_state is not None:
            progress = int(100 * self.n / self.total) if self.total > 0 else 0
            self.web_state['progress'] = progress
            logger.debug(f"Web UI progress updated: {progress}%")
    
    def set_description(self, desc: str):
        """
        Set the description of the progress bar and update web UI state.
        
        Args:
            desc (str): Description text
        """
        super().set_description(desc)
        
        # Update web state if provided
        if self.web_state is not None:
            self.web_state['console_output'] += f"{desc}\n"
            logger.debug(f"Web UI description updated: {desc}")


def create_progress_bar(total: int, desc: str = "", web_state: Optional[Dict[str, Any]] = None, **kwargs) -> CustomTqdm:
    """
    Create an appropriate progress bar based on the context.
    
    This factory function creates either a CustomTqdm or WebUITqdm instance
    depending on whether a web_state dictionary is provided.
    
    Args:
        total (int): Total number of items to process
        desc (str, optional): Description of the progress bar
        web_state (dict, optional): Dictionary for tracking state in the web UI
        **kwargs: Additional arguments to pass to tqdm
    
    Returns:
        CustomTqdm: A progress bar instance (either CustomTqdm or WebUITqdm)
        
    Example:
        >>> progress_bar = create_progress_bar(100, desc="Processing items")
        >>> for i in range(100):
        ...     # Do some work
        ...     progress_bar.update()
        >>> progress_bar.close()
    """
    if web_state is not None:
        logger.info(f"Creating web UI progress bar: {desc} (total: {total})")
        return WebUITqdm(total, web_state=web_state, desc=desc, **kwargs)
    else:
        logger.info(f"Creating command-line progress bar: {desc} (total: {total})")
        return CustomTqdm(total, desc=desc, **kwargs) 