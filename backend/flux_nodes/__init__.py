#!/usr/bin/env python3
# Copyright (c) 2025 SNF-AI
# SPDX-License-Identifier: MIT

"""
Flux Nodes Package

This package contains the expert nodes for the SNF-AI Windsurf modular mesh.
"""

import logging
import os
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# Package version
__version__ = "0.1.0"

# Get package directory
PACKAGE_DIR = Path(os.path.dirname(os.path.abspath(__file__)))

# Default models directory
MODELS_DIR = Path(os.environ.get(
    "FLUX_MODELS_DIR", 
    Path.home() / ".snf-ai" / "windsurf" / "models"
))

# Ensure models directory exists
MODELS_DIR.mkdir(parents=True, exist_ok=True)
