"""
Utility functions for image and PDF processing.
"""

import os
import base64
import fitz # PyMuPDF
import io
from PIL import Image
import logging

logger = logging.getLogger(__name__)

def encode_image_to_base64(image_bytes):
    """Encodes image bytes to a base64 string."""
    return base64.b64encode(image_bytes).decode('utf-8')

def extract_images_from_pdf(pdf_path, zoom=2):
    """
    Extracts each page of a PDF as a base64 PNG string.
    
    Args:
        pdf_path (str): Path to the PDF file.
        zoom (int): Zoom factor for rendering (higher zoom = higher resolution, e.g., 2 for 144 DPI).
        
    Returns:
        list: List of base64 strings (data only, no data URI prefix), one per page.
              Returns an empty list on error or for an empty PDF.
    """
    images_base64 = []
    pdf_filename = os.path.basename(pdf_path)
    try:
        doc = fitz.open(pdf_path)
        num_pages = len(doc)
        if num_pages == 0:
            logger.warning(f"PDF '{pdf_filename}' has no pages.")
            return []

        logger.info(f"Extracting {num_pages} pages as images from PDF: {pdf_filename} (Zoom: {zoom}x)...")
        for page_num in range(num_pages):
            page_image_data = None
            try:
                page = doc.load_page(page_num)
                # Render page to pixmap (image) with zoom
                mat = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat, alpha=False) # alpha=False prevents unnecessary alpha channel

                # Convert pixmap to PNG image bytes
                img_bytes = pix.tobytes("png")
                if img_bytes:
                    page_image_data = encode_image_to_base64(img_bytes) # Use the utility function
                else:
                     logger.warning(f"pix.tobytes('png') returned empty for page {page_num + 1}/{num_pages} of '{pdf_filename}'.")

            except Exception as page_err:
                logger.error(f"Error processing page {page_num + 1}/{num_pages} of '{pdf_filename}': {page_err}", exc_info=False)

            if page_image_data:
                images_base64.append(page_image_data)
            else:
                 logger.warning(f"Skipping page {page_num + 1} of '{pdf_filename}' due to previous error.")

        doc.close()
        logger.info(f"PDF image extraction finished for '{pdf_filename}'. Successful: {len(images_base64)}/{num_pages}")
        return images_base64

    except FileNotFoundError:
        logger.error(f"PDF file not found: {pdf_path}")
        return []
    except Exception as e:
        logger.error(f"Critical error processing PDF '{pdf_filename}' for image extraction: {e}", exc_info=True)
        return []

def extract_data_uri_from_image(image_path):
    """Reads an image and returns it as a data URI string (base64 with MIME prefix)."""
    img_filename = os.path.basename(image_path)
    try:
        with open(image_path, "rb") as image_file:
            img_bytes = image_file.read()

        # Infer MIME type for the data URI
        mime_type = "image/jpeg" # Default
        try:
            img = Image.open(io.BytesIO(img_bytes))
            img_format = img.format or "JPEG"
            detected_mime = Image.MIME.get(img_format.upper())
            if detected_mime:
                mime_type = detected_mime
            else:
                logger.warning(f"Could not determine MIME type for format {img_format} in '{img_filename}'. Using {mime_type}.")
        except Exception as img_err:
            logger.warning(f"Could not open image '{img_filename}' to determine MIME type: {img_err}. Using {mime_type}.")

        b64_string = encode_image_to_base64(img_bytes) # Use the utility function
        data_uri = f"data:{mime_type};base64,{b64_string}"
        logger.info(f"Direct image read and encoded: {img_filename} (Type: {mime_type})")
        return data_uri # Return the complete data URI

    except FileNotFoundError:
         logger.error(f"Image file not found: {image_path}")
         return None
    except Exception as e:
        logger.error(f"Error reading or encoding image file '{img_filename}': {e}", exc_info=True)
        return None 