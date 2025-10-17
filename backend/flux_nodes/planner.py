#!/usr/bin/env python3
# Copyright (c) 2025 SNF-AI
# SPDX-License-Identifier: MIT

"""
Planner Node

This module implements the Planner expert node using a local instruction-following model.
"""

import logging
import os
import time
from pathlib import Path
from typing import Dict, Any, Optional

# Try to import vLLM, but don't fail if it's not available
try:
    from vllm import LLM, SamplingParams
    VLLM_AVAILABLE = True
except ImportError:
    VLLM_AVAILABLE = False

# Import llama_cpp
from llama_cpp import Llama

from .base import FluxNode

logger = logging.getLogger(__name__)

class PlannerNode(FluxNode):
    """Planner expert node using a local instruction-following model."""

    def __init__(
        self,
        model_path: Optional[Path] = None,
        node_id: str = "planner-mistral-7b",
        name: str = "Planner (Mistral-7B)",
        description: str = "Task planning and decomposition using a local instruction-following model",
    ):
        """Initialize the planner node."""
        super().__init__(node_id, name, description)
        
        self.runtime = os.environ.get("FLUX_PLANNER_RUNTIME", "llama_cpp")
        
        if model_path is None:
            from . import MODELS_DIR
            self.model_path = MODELS_DIR / "mistral-7b-instruct-q4.gguf"
            logger.info(f"Loading Mistral model for planning from local file: {self.model_path}")
            if not self.model_path.exists():
                logger.error(f"Model file not found: {self.model_path}")
                raise FileNotFoundError(f"Model file not found: {self.model_path}")
        else:
            self.model_path = model_path
            logger.info(f"Using provided model path: {self.model_path}")
        
        self.keywords = {
            "plan", "organize", "schedule", "task", "project", "workflow", "itinerary", "timeline"
        }
        
        self.metadata = {
            "model": "Mistral-7B-Instruct-v0.2-Local",
            "backend": self.runtime,
            "context_length": "4096",
            "capabilities": "task_planning,travel_planning,project_planning,sprint_planning,meeting_planning,resource_planning",
            "model_file": str(self.model_path)
        }
        
        self.model = None
        self.model_loaded = False

    def start(self):
        """Public method to start the node."""
        return self._start_impl()

    def stop(self):
        """Public method to stop the node."""
        self._stop_impl()

    def _start_impl(self):
        """Implementation of node startup."""
        if self.model_loaded:
            return True
            
        logger.info(f"Initializing planner model using {self.runtime} runtime from: {self.model_path}")
        try:
            if self.runtime == "llama_cpp":
                self.model = Llama(model_path=str(self.model_path), n_ctx=4096, n_gpu_layers=-1, verbose=False)
            elif self.runtime == "vllm" and VLLM_AVAILABLE:
                self.model = LLM(model=str(self.model_path))
            else:
                logger.error(f"Unsupported runtime '{self.runtime}' or vLLM not available.")
                return False
            
            self.model_loaded = True
            logger.info("Planner model loaded successfully.")
            return True
        except Exception as e:
            logger.exception(f"Error loading planner model: {e}")
            self.model_loaded = False
            return False

    def _stop_impl(self):
        """Implementation of node shutdown."""
        logger.info("Stopping planner node.")
        self.model = None
        self.model_loaded = False

    def generate(self, prompt: str, **kwargs: Any) -> str:
        """Generate a response based on a prompt."""
        conversation_history = kwargs.get('conversation_history', [])
        logger.info(f"Received query for planner node: '{prompt}' with {len(conversation_history)} history items")
        if not self.model_loaded:
            logger.warning("Model not loaded, attempting to start it now.")
            if not self.start():
                return "Planner node is not available. Failed to load model."

        query_text = self.sanitize_input(prompt)
        plan_type = self._determine_plan_type(query_text)
        enhanced_prompt = self._enhance_prompt(query_text, plan_type, conversation_history)
        
        logger.info(f"Generating plan of type '{plan_type}' with prompt length: {len(enhanced_prompt)}")
        plan_text = self._generate_plan_from_model(enhanced_prompt)
        
        return plan_text

    def sanitize_input(self, text: str) -> str: 
        """Sanitize user input."""
        return text.strip()

    def _generate_plan_from_model(self, prompt: str) -> str:
        """Generates a plan using the loaded model."""
        try:
            if self.runtime == "llama_cpp":
                response = self.model.create_completion(
                    prompt,
                    max_tokens=2048,
                    temperature=0.7,
                    top_p=0.9,
                    stop=None,
                )
                result = response["choices"][0]["text"].strip()
            elif self.runtime == "vllm" and VLLM_AVAILABLE:
                sampling_params = SamplingParams(temperature=0.7, top_p=0.9, max_tokens=2048, stop=None)
                response = self.model.generate(prompt, sampling_params)
                result = response[0].outputs[0].text.strip()
            else:
                return "Planner misconfiguration. Unsupported runtime."
            
            logger.info(f"Successfully generated plan, length: {len(result)}")
            return result
        except Exception as e:
            logger.exception(f"Error generating plan with model: {e}")
            return "I'm having trouble generating a detailed plan right now. Please try again."

    def _determine_plan_type(self, query_text: str) -> str:
        """Determines the type of planning required based on keywords."""
        query_lower = query_text.lower()
        if any(k in query_lower for k in ["sprint", "agile", "scrum"]):
            return "sprint_planning"
        if any(k in query_lower for k in ["project", "timeline", "milestone"]):
            return "project_planning"
        if any(k in query_lower for k in ["trip", "travel", "itinerary"]):
            return "travel_planning"
        if any(k in query_lower for k in ["meeting", "agenda", "workshop"]):
            return "meeting_planning"
        if any(k in query_lower for k in ["resource", "budget", "cost"]):
            return "resource_planning"
        return "general_planning"
    
    def _enhance_prompt(self, query_text: str, plan_type: str, conversation_history: list = None) -> str:
        """Enhances the prompt with type-specific instructions and conversation history."""
        prompts = {
            "sprint_planning": "You are an expert Agile/Scrum Master. Create a detailed sprint plan with user stories, acceptance criteria, and time estimates.",
            "project_planning": "You are an expert Project Manager. Create a detailed project plan with phases, milestones, deliverables, and timelines.",
            "travel_planning": "You are an expert Travel Planner. Create a detailed travel itinerary with destinations, activities, and logistics.",
            "meeting_planning": "You are an expert Meeting Facilitator. Create a detailed meeting plan with agenda, objectives, and action items.",
            "resource_planning": "You are an expert Resource Manager. Create a detailed resource allocation plan with requirements, assignments, and schedules.",
            "general_planning": "You are an expert Planner. Create a detailed, structured plan with clear steps and objectives."
        }
        base_prompt = prompts.get(plan_type, prompts["general_planning"]) # Fallback to general
        
        # Add conversation history if available
        if conversation_history:
            context_parts = []
            # Add recent conversation history (limit to last 3 messages for planning context)
            recent_history = conversation_history[-3:] if len(conversation_history) > 3 else conversation_history
            
            for msg in recent_history:
                if msg.get('role') == 'user':
                    context_parts.append(f"User: {msg.get('content', '')}")
                elif msg.get('role') == 'assistant':
                    # Truncate long planning responses to keep context manageable
                    content = msg.get('content', '')
                    if len(content) > 200:
                        content = content[:200] + "...[truncated]"
                    context_parts.append(f"Assistant: {content}")
            
            if context_parts:
                context = "\n".join(context_parts)
                return f"{base_prompt}\n\nPrevious conversation context:\n{context}\n\nCurrent request: {query_text}\n\nProvide a detailed, structured response that builds on our previous discussion with clear steps and actionable recommendations."
        
        return f"{base_prompt}\n\nRequest: {query_text}\n\nProvide a detailed, structured response with clear steps and actionable recommendations."

    def reset_state(self):
        """
        Reset the node's state.
        
        This method should be called between tests to ensure that the node is in a clean state.
        It resets both the sanitizer state and any internal state that might affect subsequent queries.
        """
        logger.info(f"Resetting state for {self.node_id}")
        
        # Reset sanitizer state
        if hasattr(self, 'sanitizer') and self.sanitizer is not None:
            self.sanitizer.reset_state()
        
        # Reset internal state
        self.last_query_id = None
        self.query_count = 0
        
        # Reset any other internal state variables
        if hasattr(self, 'language_node'):
            self.language_node = None
        
        # Log the reset operation
        logger.info(f"Reset state for node {self.node_id} completed successfully at {time.time()}")
        
        return Response(
            query_id="reset-state",
            text="Node state has been reset successfully.",
            processing_time_ms=10
        )
