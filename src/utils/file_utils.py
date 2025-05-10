"""
Utility functions for file operations, like determining file type.
"""

import os
import logging

logger = logging.getLogger(__name__)

def get_file_type(filename):
    """Determines the file type based on its extension to guide extraction.
    
    Returns:
        str: A string code representing the file type (e.g., 'pdf_vision', 'image_direct', 'text', 'excel', 'json', 'csv') or None.
    """
    if not isinstance(filename, str) or '.' not in filename:
        return None # Not a valid filename with extension
    extension = filename.rsplit('.', 1)[-1].lower()

    if extension == 'pdf':
        return 'pdf_vision' # Process PDF with vision (page by page as PNG)
    elif extension in ['png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp']:
        return 'image_direct' # Process as a single image
    elif extension == 'txt':
        return 'text'
    elif extension in ['xlsx', 'xls']:
        # Decide if Excel should be text or structured based on context?
        # For now, let's make a choice for the dispatcher:
        # If OpenAI needs text, return 'excel_text'. 
        # If structured parsing is primary, maybe return 'excel_structured'?
        # Let's return 'excel' for now, the caller can decide.
        return 'excel' 
    elif extension == 'csv':
         # Similar decision for CSV: structured or text?
         # Return 'csv' for now.
         return 'csv'
    elif extension == 'tsv': # Added TSV
         return 'tsv'
    elif extension == 'json':
        # JSON can also be text or structured.
        # Return 'json' for now.
        return 'json' 
    else:
        logger.warning(f"Unknown or unsupported extension: '{extension}' for file '{filename}'")
        return None 