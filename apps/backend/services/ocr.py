"""
OCR (Optical Character Recognition) Service
"""
import base64
import io
from typing import Optional, List, Dict, Any, Union
from PIL import Image
import pytesseract
import cv2
import numpy as np
from ..core.logging import logger
from ..services.ai_vision import ai_vision_service


class OCRService:
    """Service for optical character recognition and document processing"""
    
    def __init__(self):
        self.supported_formats = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.pdf']
        
    async def extract_text(
        self,
        image_data: Union[bytes, str],
        language: str = 'eng',
        preprocess: bool = True
    ) -> Dict[str, Any]:
        """
        Extract text from image using OCR
        
        Args:
            image_data: Image bytes or base64 string
            language: OCR language (default: English)
            preprocess: Whether to preprocess image for better OCR
        
        Returns:
            Extracted text and metadata
        """
        try:
            # Convert to bytes if base64
            if isinstance(image_data, str):
                image_data = base64.b64decode(image_data)
            
            # Open image
            image = Image.open(io.BytesIO(image_data))
            
            # Convert to numpy array for preprocessing
            img_array = np.array(image)
            
            if preprocess:
                img_array = self._preprocess_image(img_array)
            
            # Extract text using Tesseract
            try:
                text = pytesseract.image_to_string(img_array, lang=language)
                data = pytesseract.image_to_data(img_array, lang=language, output_type=pytesseract.Output.DICT)
            except Exception as e:
                logger.warning(f"Tesseract OCR failed, falling back to AI vision: {str(e)}")
                # Fallback to AI vision service
                result = await ai_vision_service.extract_text_from_image(image_data)
                return result
            
            # Process results
            words = []
            for i, word in enumerate(data['text']):
                if word.strip():
                    words.append({
                        'text': word,
                        'confidence': data['conf'][i],
                        'box': {
                            'x': data['left'][i],
                            'y': data['top'][i],
                            'width': data['width'][i],
                            'height': data['height'][i]
                        }
                    })
            
            return {
                'success': True,
                'text': text.strip(),
                'words': words,
                'language': language,
                'preprocessed': preprocess
            }
            
        except Exception as e:
            logger.error(f"OCR extraction failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """Preprocess image for better OCR accuracy"""
        try:
            # Convert to grayscale if needed
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image
            
            # Apply thresholding
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # Denoise
            denoised = cv2.medianBlur(thresh, 3)
            
            # Deskew
            angle = self._get_skew_angle(denoised)
            if abs(angle) > 0.5:
                denoised = self._rotate_image(denoised, angle)
            
            return denoised
            
        except Exception as e:
            logger.warning(f"Image preprocessing failed: {str(e)}")
            return image
    
    def _get_skew_angle(self, image: np.ndarray) -> float:
        """Detect skew angle of text in image"""
        try:
            # Find all contours
            contours, _ = cv2.findContours(image, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
            
            # Get minimum area rectangle for all contours
            all_points = []
            for contour in contours:
                all_points.extend(contour.reshape(-1, 2).tolist())
            
            if not all_points:
                return 0.0
            
            all_points = np.array(all_points)
            rect = cv2.minAreaRect(all_points)
            angle = rect[2]
            
            # Adjust angle
            if angle < -45:
                angle = 90 + angle
            elif angle > 45:
                angle = angle - 90
                
            return angle
            
        except:
            return 0.0
    
    def _rotate_image(self, image: np.ndarray, angle: float) -> np.ndarray:
        """Rotate image by given angle"""
        height, width = image.shape[:2]
        center = (width // 2, height // 2)
        
        # Get rotation matrix
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        
        # Calculate new dimensions
        cos = np.abs(M[0, 0])
        sin = np.abs(M[0, 1])
        new_width = int((height * sin) + (width * cos))
        new_height = int((height * cos) + (width * sin))
        
        # Adjust rotation matrix
        M[0, 2] += (new_width / 2) - center[0]
        M[1, 2] += (new_height / 2) - center[1]
        
        # Rotate image
        rotated = cv2.warpAffine(image, M, (new_width, new_height), 
                                 flags=cv2.INTER_CUBIC, 
                                 borderMode=cv2.BORDER_REPLICATE)
        
        return rotated
    
    async def extract_structured_data(
        self,
        image_data: Union[bytes, str],
        data_type: str = "invoice"
    ) -> Dict[str, Any]:
        """
        Extract structured data from documents
        
        Args:
            image_data: Document image
            data_type: Type of document (invoice, receipt, form, etc.)
        
        Returns:
            Structured data extracted from document
        """
        # First extract text
        ocr_result = await self.extract_text(image_data)
        
        if not ocr_result['success']:
            return ocr_result
        
        # Use AI to structure the data based on document type
        prompts = {
            "invoice": """Extract the following from this invoice text:
- Invoice number
- Date
- Vendor name and address
- Customer name and address
- Line items (description, quantity, price, amount)
- Subtotal
- Tax
- Total
Format as JSON.""",
            
            "receipt": """Extract the following from this receipt:
- Store name
- Date and time
- Items purchased (name, quantity, price)
- Subtotal
- Tax
- Total
- Payment method
Format as JSON.""",
            
            "estimate": """Extract the following from this roofing estimate:
- Estimate number
- Date
- Customer information
- Property address
- Scope of work items
- Materials list
- Labor costs
- Total estimate
Format as JSON."""
        }
        
        prompt = prompts.get(data_type, "Extract all relevant information from this document and format as JSON.")
        
        # Use AI vision to structure the data
        ai_result = await ai_vision_service.analyze_image(
            image_data,
            prompt + f"\n\nOCR Text:\n{ocr_result['text']}"
        )
        
        return {
            'success': True,
            'raw_text': ocr_result['text'],
            'structured_data': ai_result.get('analysis', {}),
            'document_type': data_type
        }
    
    async def batch_process(
        self,
        images: List[Union[bytes, str]],
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Process multiple images in batch"""
        results = []
        
        for image_data in images:
            result = await self.extract_text(image_data, **kwargs)
            results.append(result)
        
        return results


# Create singleton instance
ocr_service = OCRService()


# Convenience functions
async def extract_text(*args, **kwargs):
    return await ocr_service.extract_text(*args, **kwargs)

async def extract_structured_data(*args, **kwargs):
    return await ocr_service.extract_structured_data(*args, **kwargs)