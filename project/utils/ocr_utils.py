import pytesseract
import pyautogui
import base64
from datetime import datetime
import os
import logging

logger = logging.getLogger("custom_logger")

class OCRManager:
    def __init__(self, tesseract_path=r'C:\IDXPROJT\AI\Browser-use\Timesheet_test\Tesseract\tesseract.exe'):
        self.logger = logger
        self.tesseract_path = tesseract_path
        pytesseract.pytesseract.tesseract_cmd = self.tesseract_path

    def capture_screen(self, screenshot_dir, timestamp):
        """Captures a screenshot of the current screen."""
        file_path = os.path.join(screenshot_dir, f"screenshot_{timestamp}.png")
        pyautogui.screenshot(file_path)
        return file_path

    def encode_image(self, image_path):
        """Convert a local image file to a Base64-encoded string."""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")

    def extract_text_from_image_tess(self, image_path):
        """Extract text from an image using Tesseract OCR."""
        try:
            text = pytesseract.image_to_string(image_path)
            self.logger.debug("\nExtracted Text:")
            self.logger.debug(text)
            return text
        except Exception as e:
            self.logger.error(f"Error during OCR: {e}")
            return None
