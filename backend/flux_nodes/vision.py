#!/usr/bin/env python3

import base64
import io
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
from PIL import Image

from .base import FluxNode

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Try to import llama-cpp-python for vision
try:
    from llama_cpp import Llama
    from llama_cpp.llama_chat_format import Llava15ChatHandler
    VISION_AVAILABLE = True
    logger.info("llama-cpp-python available - vision processing enabled")
except ImportError:
    VISION_AVAILABLE = False
    logger.warning("llama-cpp-python not available - vision processing disabled")

class VisionNode(FluxNode):
    """A node for handling vision-related tasks using LLaVA vision-language model."""

    def __init__(
        self,
        model_path: Optional[Path] = None,
        mmproj_path: Optional[Path] = None,
        node_id: str = "vision-llava-1.6-7b",
        name: str = "Vision (LLaVA-1.6-7B)",
        description: str = "Image captioning and visual question answering using LLaVA-1.6-7B.",
        **kwargs: Any,
    ):
        """Initialize the vision node."""
        super().__init__(node_id, name, description, **kwargs)

        self.model = None
        self.chat_handler = None
        
        if VISION_AVAILABLE and model_path and mmproj_path:
            try:
                logger.info(f"Loading LLaVA model from {model_path}")
                logger.info(f"Loading mmproj from {mmproj_path}")
                
                # Initialize chat handler with mmproj
                self.chat_handler = Llava15ChatHandler(clip_model_path=str(mmproj_path))
                
                # Load the LLaVA model
                self.model = Llama(
                    model_path=str(model_path),
                    chat_handler=self.chat_handler,
                    n_ctx=2048,  # Context window
                    n_gpu_layers=0,  # Use CPU only for stability
                    verbose=False
                )
                
                self.is_available = True
                logger.info("LLaVA vision model loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load LLaVA model: {e}", exc_info=True)
                self.is_available = True  # Still available for fallback
                self.model = None
        else:
            self.is_available = True
            logger.info("VisionNode initialized in fallback mode - basic image analysis available.")

    def process_image(self, image_data: bytes) -> Optional[Image.Image]:
        """Decode and process the input image data."""
        try:
            if isinstance(image_data, str):
                image_data = base64.b64decode(image_data)
            image = Image.open(io.BytesIO(image_data)).convert("RGB")
            return image
        except Exception as e:
            logger.error(f"Error processing image data: {e}", exc_info=True)
            return None

    def generate(self, prompt: str, **kwargs) -> str:
        """Generate a response based on the prompt using the vision model."""
        logger.info(f"VisionNode generate called with prompt: {prompt[:100]}...")
        try:
            # Check if an image file path is provided via kwargs or prompt
            image_path = kwargs.get('image_path', None)
            if not image_path and 'image' in prompt.lower():
                # Extract potential file path from prompt (basic approach)
                import re
                match = re.search(r'(?:image|file|path):\s*([\w\/\._-]+)', prompt, re.IGNORECASE)
                if match:
                    image_path = match.group(1)
            
            if image_path:
                if not os.path.exists(image_path):
                    logger.error(f"Image path does not exist: {image_path}")
                    return f"Error: Image file not found at {image_path}"
                
                logger.info(f"Processing image at: {image_path}")
                
                # Use LLaVA model if available
                if self.model and self.chat_handler:
                    try:
                        # Convert image path to data URI for llama-cpp-python
                        with open(image_path, 'rb') as f:
                            image_data = base64.b64encode(f.read()).decode('utf-8')
                        
                        # Determine image format from file extension
                        ext = os.path.splitext(image_path)[1].lower()
                        mime_type = 'image/jpeg' if ext in ['.jpg', '.jpeg'] else 'image/png'
                        data_uri = f"data:{mime_type};base64,{image_data}"
                        
                        # Create messages for vision model
                        messages = [
                            {
                                "role": "system",
                                "content": "You are an AI assistant that analyzes images and provides detailed, accurate descriptions."
                            },
                            {
                                "role": "user",
                                "content": [
                                    {"type": "image_url", "image_url": {"url": data_uri}},
                                    {"type": "text", "text": prompt}
                                ]
                            }
                        ]
                        
                        logger.info("Generating vision response with LLaVA model...")
                        response = self.model.create_chat_completion(
                            messages=messages,
                            max_tokens=512,
                            temperature=0.7
                        )
                        
                        result = response['choices'][0]['message']['content']
                        logger.info(f"Vision response generated: {result[:100]}...")
                        return result
                        
                    except Exception as e:
                        logger.error(f"Error using LLaVA model: {e}", exc_info=True)
                        return f"Error analyzing image with vision model: {str(e)}"
                else:
                    # Fallback: Basic image analysis
                    try:
                        img = Image.open(image_path)
                        width, height = img.size
                        mode = img.mode
                        format_name = img.format or "Unknown"
                        
                        return f"I can see an image file at {image_path}. It's a {format_name} image with dimensions {width}x{height} pixels in {mode} color mode. However, the full vision model is not loaded, so I cannot provide detailed content analysis. Please ensure the LLaVA model is properly configured."
                    except Exception as e:
                        logger.error(f"Error in fallback image analysis: {e}")
                        return f"Error analyzing image: {str(e)}"
            else:
                return "Please upload an image or provide an image file path for me to analyze."
        except Exception as e:
            logger.error(f"Error in VisionNode generate: {e}", exc_info=True)
            return f"Error processing vision request: {str(e)}"
