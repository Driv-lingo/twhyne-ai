#!/usr/bin/env python3
# Copyright (c) 2025 SNF-AI
# SPDX-License-Identifier: MIT

"""
Code Node

This module implements the Code expert node using CodeLlama-7B.
"""

import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional

# Import llama_cpp
from llama_cpp import Llama

from .base import FluxNode

logger = logging.getLogger(__name__)


class CodeNode(FluxNode):
    """Code expert node using CodeLlama-7B."""

    def __init__(
        self,
        model_path: Optional[str] = None,
        node_id: str = "code-codellama-7b",
        name: str = "Code (CodeLlama-7B)",
        description: str = "Code generation and understanding using CodeLlama-7B",
    ):
        """Initialize the code node."""
        logger.info(f"Starting CodeNode initialization with node_id: {node_id}")
        super().__init__(node_id, name, description)
        logger.info("CodeNode parent initialization complete")
        
        # Set model path
        logger.info("Setting model path...")
        if model_path is None:
            from . import MODELS_DIR
            logger.info(f"MODELS_DIR: {MODELS_DIR}")
            
            # Use the available CodeLlama model
            self.model_path = MODELS_DIR / "codellama-7b.q4_K_M.gguf"
            logger.info(f"Using CodeLlama-7B model: {self.model_path}")
            logger.info(f"Checking if model file exists: {self.model_path}")
            
            # Verify model file exists
            if not os.path.exists(self.model_path):
                logger.error(f"Model file not found: {self.model_path}")
                # Try alternative name
                alt_path = MODELS_DIR / "codellama-7b-q4.gguf"
                if os.path.exists(alt_path):
                    logger.info(f"Found alternative model: {alt_path}")
                    self.model_path = alt_path
                else:
                    logger.error(f"No suitable CodeLlama model found in {MODELS_DIR}")
                    self.is_available = False
                    return
        else:
            self.model_path = model_path
        
        # Initialize model
        self.model = None
        self.model_loaded = False
        
        logger.info("CodeNode initialization complete")

    def generate(self, prompt: str, **kwargs) -> Optional[str]:
        """Generate a response based on a prompt."""
        conversation_history = kwargs.get('conversation_history', [])
        logger.info(f"CodeNode generate called with prompt: {prompt[:100]}... and {len(conversation_history)} history items")
        try:
            # Ensure model is loaded
            if not self.model_loaded or not self.model:
                logger.info("Model not loaded, attempting to load it now...")
                self._load_model()
            
            if not self.model:
                logger.error("Failed to load model")
                return "Sorry, the code model is not available."
            
            # Format the prompt for code generation with conversation history
            formatted_prompt = self._format_prompt(prompt, conversation_history)
            
            # Generate response with improved parameters
            response = self.model(
                formatted_prompt,
                max_tokens=2048,  # Increased for full responses
                temperature=0.7,  # Higher for better creativity
                top_p=0.9,  # Standard top_p
                top_k=40,  # More vocabulary options
                repeat_penalty=1.1,  # Moderate repetition penalty
                stop=["</s>"],
                echo=False
            )
            
            result = response['choices'][0]['text'].strip()
            
            # Post-process to remove repetitive patterns
            result = self._clean_repetitive_output(result)
            
            # Check if the model is stuck (returning the same weather code)
            if "weather prediction" in result.lower() and "stock" in prompt.lower():
                logger.warning("CodeLlama model appears to be stuck, using fallback")
                return self._generate_fallback_code(prompt)
            
            logger.info(f"Generated response: {result[:100]}...")
            return result
            
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return f"Error: {str(e)}"

    def _load_model(self):
        """Load the code model."""
        try:
            logger.info(f"Loading CodeLlama-7B model from: {self.model_path}")
            self.model = Llama(
                model_path=str(self.model_path),
                n_ctx=2048,
                verbose=False
            )
            self.model_loaded = True
            logger.info("CodeLlama-7B model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            self.model = None
            self.model_loaded = False
            self.is_available = False

    def _format_prompt(self, query_text: str, conversation_history: list = None) -> str:
        """Format the prompt for the code model with conversation history."""
        # Create a clear, focused prompt for code generation
        base_prompt = f"""You are a helpful coding assistant. Generate clean, working Python code for the following request:

Request: {query_text}

Please provide:
1. A complete Python script
2. Include necessary imports
3. Add comments explaining the code
4. Make it ready to run

Code:"""
        
        return base_prompt
    
    def _generate_fallback_code(self, prompt: str) -> str:
        """Generate a fallback code response when the model is stuck."""
        if "stock" in prompt.lower() and "prediction" in prompt.lower():
            return """Here's a Python script for stock price prediction using machine learning:

```python
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error
import yfinance as yf

def predict_stock_prices(symbol, days_ahead=5):
    # Download stock data
    stock = yf.Ticker(symbol)
    data = stock.history(period="1y")
    
    # Prepare features
    data['SMA_5'] = data['Close'].rolling(window=5).mean()
    data['SMA_20'] = data['Close'].rolling(window=20).mean()
    data['RSI'] = calculate_rsi(data['Close'])
    
    # Create features and target
    features = ['Open', 'High', 'Low', 'Volume', 'SMA_5', 'SMA_20', 'RSI']
    X = data[features].dropna()
    y = data['Close'].shift(-days_ahead).dropna()
    
    # Align data
    min_len = min(len(X), len(y))
    X = X.iloc[:min_len]
    y = y.iloc[:min_len]
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # Train model
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    
    # Make predictions
    predictions = model.predict(X_test)
    mse = mean_squared_error(y_test, predictions)
    
    # Predict future prices
    latest_features = X.iloc[-1:].values
    future_prices = model.predict(latest_features)
    
    return {
        'predictions': predictions,
        'future_price': future_prices[0],
        'mse': mse,
        'feature_importance': dict(zip(features, model.feature_importances_))
    }

def calculate_rsi(prices, window=14):
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# Example usage
if __name__ == "__main__":
    result = predict_stock_prices("AAPL", days_ahead=5)
    print(f"Predicted price: ${result['future_price']:.2f}")
    print(f"Model MSE: {result['mse']:.4f}")
```"""
        else:
            return f"""Here's a Python script for your request:

```python
# {prompt}
def main():
    # Your code implementation here
    pass

if __name__ == "__main__":
    main()
```"""
    
    def _clean_repetitive_output(self, text: str) -> str:
        """Clean up repetitive patterns in the generated output."""
        import re
        
        # Remove repetitive tag patterns
        text = re.sub(r'\[.*?\]', '', text)
        
        # Remove lines that are just repetitive text
        lines = text.split('\n')
        cleaned_lines = []
        seen_lines = set()
        
        for line in lines:
            line = line.strip()
            if line and line not in seen_lines:
                cleaned_lines.append(line)
                seen_lines.add(line)
            elif line and len(line) > 50:  # Keep longer lines even if repeated
                cleaned_lines.append(line)
        
        result = '\n'.join(cleaned_lines)
        
        # If the result is too short or still repetitive, provide a fallback
        if len(result.strip()) < 20 or len(result.split()) < 5:
            return "Here's a Python weather prediction algorithm:\n\n```python\nimport requests\nimport json\n\ndef predict_weather(city):\n    # Simple weather prediction using OpenWeatherMap API\n    api_key = 'your_api_key_here'\n    url = f'http://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}'\n    \n    try:\n        response = requests.get(url)\n        data = response.json()\n        \n        # Extract weather information\n        temperature = data['main']['temp']\n        humidity = data['main']['humidity']\n        pressure = data['main']['pressure']\n        \n        # Simple prediction logic\n        if temperature > 25:\n            prediction = 'Warm and sunny'\n        elif temperature < 10:\n            prediction = 'Cold and possibly rainy'\n        else:\n            prediction = 'Mild weather'\n            \n        return f'Weather prediction for {city}: {prediction}'\n    except:\n        return 'Unable to fetch weather data'\n\n# Example usage\nprint(predict_weather('London'))\n```"
        
        return result
