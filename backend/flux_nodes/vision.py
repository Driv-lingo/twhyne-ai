#!/usr/bin/env python3

import base64
import io
import logging
import os
from pathlib import Path
from typing import Any, Optional

from PIL import Image

from .base import FluxNode

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    from llama_cpp import Llama
    from llama_cpp.llama_chat_format import Llava15ChatHandler
    VISION_AVAILABLE = True
    logger.info("llama-cpp-python available - vision processing enabled")
except ImportError:
    VISION_AVAILABLE = False
    logger.warning("llama-cpp-python not available - vision processing disabled")


class VisionNode(FluxNode):
    """Vision node using LLaVA. The model loads lazily on first image query."""

    def __init__(self, model_path: Optional[Path] = None, mmproj_path: Optional[Path] = None,
                 node_id: str = "vision-llava-1.6-7b", name: str = "Vision (LLaVA-1.6-7B)",
                 description: str = "Image captioning and visual question answering using LLaVA-1.6-7B.",
                 **kwargs: Any):
        super().__init__(node_id, name, description, **kwargs)
        self.model = None
        self.chat_handler = None
        self.model_path = model_path
        self.mmproj_path = mmproj_path
        # Registered/available if the files exist; heavy model loads on first use.
        self.is_available = bool(
            VISION_AVAILABLE and model_path and mmproj_path and os.path.exists(str(model_path))
        )
        logger.info("VisionNode ready (LLaVA loads on first image query)")

    def _ensure_model(self):
        if self.model is not None or not VISION_AVAILABLE:
            return
        if not (self.model_path and self.mmproj_path):
            return
        try:
            logger.info(f"Loading LLaVA model from {self.model_path}")
            self.chat_handler = Llava15ChatHandler(clip_model_path=str(self.mmproj_path))
            self.model = Llama(
                model_path=str(self.model_path),
                chat_handler=self.chat_handler,
                n_ctx=2048,
                n_gpu_layers=0,
                verbose=False,
            )
            logger.info("LLaVA vision model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load LLaVA model: {e}", exc_info=True)
            self.model = None

    def generate(self, prompt: str, **kwargs) -> str:
        logger.info(f"VisionNode generate called with prompt: {prompt[:100]}...")
        try:
            image_path = kwargs.get('image_path', None)
            if not image_path:
                return "Please upload an image for me to analyze."
            if not os.path.exists(image_path):
                return f"Error: Image file not found at {image_path}"

            self._ensure_model()

            if self.model and self.chat_handler:
                with open(image_path, 'rb') as f:
                    image_data = base64.b64encode(f.read()).decode('utf-8')
                ext = os.path.splitext(image_path)[1].lower()
                mime_type = 'image/jpeg' if ext in ['.jpg', '.jpeg'] else 'image/png'
                data_uri = f"data:{mime_type};base64,{image_data}"
                messages = [
                    {"role": "system", "content": "You are an AI assistant that analyzes images and provides detailed, accurate descriptions."},
                    {"role": "user", "content": [
                        {"type": "image_url", "image_url": {"url": data_uri}},
                        {"type": "text", "text": prompt},
                    ]},
                ]
                response = self.model.create_chat_completion(messages=messages, max_tokens=512, temperature=0.7)
                return response['choices'][0]['message']['content']

            # Fallback: basic image metadata
            img = Image.open(image_path)
            w, h = img.size
            return (f"I can see a {img.format or 'image'} of {w}x{h} pixels, but the LLaVA "
                    f"vision model could not be loaded for detailed analysis.")
        except Exception as e:
            logger.error(f"Error in VisionNode generate: {e}", exc_info=True)
            return f"Error processing vision request: {str(e)}"
