import cv2
import numpy as np
import imutils
from typing import Tuple, Optional, Dict, List
import logging
from pathlib import Path
from dataclasses import dataclass
from enum import Enum

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DocumentType(Enum):
    """Document type classification for adaptive preprocessing"""
    RECEIPT = "receipt"  # Clean, high-contrast (SROIE, CORD)
    INVOICE = "invoice"  # General invoices with varying quality
    HANDWRITTEN = "handwritten"  # Handwritten text emphasis
    NOISY = "noisy"  # Low quality, damaged (FUNSD)


@dataclass
class PreprocessingConfig:
    """Configuration for preprocessing pipeline"""
    # Deskewing
    deskew_enabled: bool = True
    deskew_angle_threshold: float = 1.0  # degrees
    
    # Noise removal
    denoise_strength: int = 10  # h parameter for fastNlMeansDenoising
    denoise_template_size: int = 7
    denoise_search_size: int = 21
    
    # Binarization
    binarization_method: str = "adaptive"  # "adaptive", "otsu", "sauvola"
    binary_block_size: int = 31
    binary_constant: int = 2
    
    # Contrast enhancement
    contrast_clip_limit: float = 2.0  # CLAHE clip limit
    contrast_tile_size: Tuple[int, int] = (8, 8)
    
    # Morphological operations
    morph_kernel_size: int = 3
    morph_enabled: bool = True
    
    # Document type-specific adjustments
    document_type: DocumentType = DocumentType.INVOICE


class ImagePreprocessor:
    """Production-grade preprocessing pipeline for document images"""
    
    def __init__(self, config: Optional[PreprocessingConfig] = None):
        """
        Initialize preprocessor with configuration
        
        Args:
            config: PreprocessingConfig object. If None, uses defaults.
        """
        self.config = config or PreprocessingConfig()
        self._apply_document_type_adjustments()
        logger.info(f"Preprocessor initialized for {self.config.document_type.value}")
    
    def _apply_document_type_adjustments(self):
        """Apply document-type-specific parameter adjustments"""
        doc_type = self.config.document_type
        
        if doc_type == DocumentType.HANDWRITTEN:
            # Handwritten text needs stronger denoising
            self.config.denoise_strength = 15
            self.config.binary_block_size = 25
            self.config.contrast_clip_limit = 3.0
            
        elif doc_type == DocumentType.NOISY:
            # FUNSD: damaged, low-quality documents
            self.config.denoise_strength = 20
            self.config.denoise_template_size = 9
            self.config.contrast_clip_limit = 3.5
            self.config.morph_kernel_size = 5
            
        elif doc_type == DocumentType.RECEIPT:
            # Clean receipts: minimal processing needed
            self.config.denoise_strength = 7
            self.config.contrast_clip_limit = 1.8
    
    def preprocess(self, image_path: str) -> np.ndarray:
        # Load image
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Cannot read image: {image_path}")
        
        logger.info(f"Processing: {Path(image_path).name} | Shape: {img.shape}")
        
        # Convert to grayscale if needed
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img
        
        # Pipeline steps
        gray = self.deskew(gray)
        gray = self.denoise(gray)
        gray = self.enhance_contrast(gray)
        binary = self.binarize(gray)
        binary = self.morphological_operations(binary)
        
        logger.info(f"Preprocessing complete | Final shape: {binary.shape}")
        return binary
    
    def deskew(self, image: np.ndarray) -> np.ndarray:
        if not self.config.deskew_enabled:
            return image
        
        try:
            # Create binary version for skew detection
            _, binary = cv2.threshold(image, 127, 255, cv2.THRESH_BINARY)
            
            # Hough transform for line detection
            lines = cv2.HoughLines(binary, 1, np.pi / 180, 100)
            
            if lines is None or len(lines) == 0:
                logger.info("No skew detected")
                return image
            
            # Calculate average angle
            angles = []
            for line in lines:
                rho, theta = line[0]
                angle = np.degrees(theta)
                # Convert to -90 to 0 range for easier rotation
                if angle > 90:
                    angle = angle - 180
                angles.append(angle)
            
            median_angle = np.median(angles)
            
            # Check if rotation is needed
            if abs(median_angle) < self.config.deskew_angle_threshold:
                logger.info(f"Skew angle {median_angle:.2f}° - below threshold, no rotation")
                return image
            
            # Rotate image
            rotated = imutils.rotate_bound(image, median_angle)
            logger.info(f"Deskewed by {median_angle:.2f}°")
            return rotated
            
        except Exception as e:
            logger.warning(f"Deskew failed: {e}. Continuing without deskewing.")
            return image
    
    def denoise(self, image: np.ndarray) -> np.ndarray:
        try:
            denoised = cv2.fastNlMeansDenoising(
                image,
                h=self.config.denoise_strength,
                templateWindowSize=self.config.denoise_template_size,
                searchWindowSize=self.config.denoise_search_size
            )
            logger.info("Denoising complete")
            return denoised
        except Exception as e:
            logger.warning(f"Denoising failed: {e}")
            return image
    
    def enhance_contrast(self, image: np.ndarray) -> np.ndarray:
        try:
            clahe = cv2.createCLAHE(
                clipLimit=self.config.contrast_clip_limit,
                tileGridSize=self.config.contrast_tile_size
            )
            enhanced = clahe.apply(image)
            logger.info("Contrast enhancement complete")
            return enhanced
        except Exception as e:
            logger.warning(f"Contrast enhancement failed: {e}")
            return image
    
    def binarize(self, image: np.ndarray) -> np.ndarray:
        try:
            if self.config.binarization_method == "adaptive":
                binary = cv2.adaptiveThreshold(
                    image,
                    255,
                    cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                    cv2.THRESH_BINARY,
                    blockSize=self.config.binary_block_size,
                    C=self.config.binary_constant
                )
                logger.info(f"Adaptive binarization applied (block_size={self.config.binary_block_size})")
                
            elif self.config.binarization_method == "otsu":
                _, binary = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                logger.info("Otsu binarization applied")
                
            elif self.config.binarization_method == "sauvola":
                # Sauvola binarization for handwritten/low-contrast documents
                binary = self._sauvola_binarize(image)
                logger.info("Sauvola binarization applied")
            else:
                binary = cv2.adaptiveThreshold(
                    image, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY,
                    self.config.binary_block_size, self.config.binary_constant
                )
            
            return binary
        except Exception as e:
            logger.warning(f"Binarization failed: {e}")
            return image
    
    @staticmethod
    def _sauvola_binarize(image: np.ndarray, window_size: int = 31, k: float = 0.2) -> np.ndarray:
        mean = cv2.blur(image, (window_size, window_size))
        sqmean = cv2.blur(image ** 2, (window_size, window_size))
        variance = sqmean - mean ** 2
        stddev = np.sqrt(np.maximum(variance, 0))
        threshold = mean * (1 + k * (stddev / 128 - 1))
        binary = np.uint8((image >= threshold) * 255)
        return binary
    
    def morphological_operations(self, image: np.ndarray) -> np.ndarray:
        if not self.config.morph_enabled:
            return image
        
        try:
            kernel = cv2.getStructuringElement(
                cv2.MORPH_RECT,
                (self.config.morph_kernel_size, self.config.morph_kernel_size)
            )
            
            # Close small holes (fill gaps in text)
            morph = cv2.morphologyEx(image, cv2.MORPH_CLOSE, kernel, iterations=1)
            
            # Open (remove small noise)
            morph = cv2.morphologyEx(morph, cv2.MORPH_OPEN, kernel, iterations=1)
            
            logger.info("Morphological operations complete")
            return morph
        except Exception as e:
            logger.warning(f"Morphological operations failed: {e}")
            return image
    
    def preprocess_batch(self, image_paths: List[str], output_dir: Optional[str] = None) -> Dict[str, np.ndarray]:
        results = {}
        
        for i, path in enumerate(image_paths, 1):
            try:
                processed = self.preprocess(path)
                results[path] = processed
                
                if output_dir:
                    output_path = Path(output_dir) / f"processed_{Path(path).name}"
                    cv2.imwrite(str(output_path), processed)
                    logger.info(f"[{i}/{len(image_paths)}] Saved to {output_path}")
                else:
                    logger.info(f"[{i}/{len(image_paths)}] Processed {Path(path).name}")
                    
            except Exception as e:
                logger.error(f"Failed to process {path}: {e}")
        
        return results


def get_sroie_config() -> PreprocessingConfig:
    """Configuration optimized for SROIE (real receipts - high quality)"""
    return PreprocessingConfig(
        document_type=DocumentType.RECEIPT,
        deskew_enabled=True,
        denoise_strength=7,
        contrast_clip_limit=1.8,
        binarization_method="otsu"
    )


def get_handwritten_config() -> PreprocessingConfig:
    """Configuration optimized for handwritten text"""
    return PreprocessingConfig(
        document_type=DocumentType.HANDWRITTEN,
        deskew_enabled=True,
        denoise_strength=15,
        contrast_clip_limit=3.0,
        binarization_method="sauvola",
        morph_kernel_size=3
    )

def get_funsd_config() -> PreprocessingConfig:
    """Configuration optimized for FUNSD (noisy, damaged documents)"""
    return PreprocessingConfig(
        document_type=DocumentType.NOISY,
        deskew_enabled=True,
        denoise_strength=20,
        denoise_template_size=9,
        contrast_clip_limit=3.5,
        binarization_method="adaptive",
        morph_kernel_size=5,
        morph_enabled=True
    )


def get_general_invoice_config() -> PreprocessingConfig:
    """Configuration for general invoices (mixed quality)"""
    return PreprocessingConfig(
        document_type=DocumentType.INVOICE,
        deskew_enabled=True,
        denoise_strength=10,
        contrast_clip_limit=2.0,
        binarization_method="adaptive"
    )

def save_preprocessing_comparison(image_path: str, output_dir: str = "./comparison"):
    Path(output_dir).mkdir(exist_ok=True)
    
    img = cv2.imread(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    preprocessor = ImagePreprocessor(get_general_invoice_config())
    
    # Save each stage
    cv2.imwrite(f"{output_dir}/00_original.jpg", gray)
    
    deskewed = preprocessor.deskew(gray)
    cv2.imwrite(f"{output_dir}/01_deskewed.jpg", deskewed)
    
    denoised = preprocessor.denoise(deskewed)
    cv2.imwrite(f"{output_dir}/02_denoised.jpg", denoised)
    
    enhanced = preprocessor.enhance_contrast(denoised)
    cv2.imwrite(f"{output_dir}/03_enhanced.jpg", enhanced)
    
    binary = preprocessor.binarize(enhanced)
    cv2.imwrite(f"{output_dir}/04_binarized.jpg", binary)
    
    final = preprocessor.morphological_operations(binary)
    cv2.imwrite(f"{output_dir}/05_final.jpg", final)
    
    logger.info(f"Comparison images saved to {output_dir}")
import os
from preprocess import ImagePreprocessor, get_sroie_config

config = get_sroie_config()
preprocessor = ImagePreprocessor(config)

folder = "F:/SROIE dataset/SROIE2019/train/img"

image_paths = [
    os.path.join(folder, file)
    for file in os.listdir(folder)
    if file.endswith(".jpg")
]

results = preprocessor.preprocess_batch(image_paths, output_dir="./processed")

print("All images processed!")