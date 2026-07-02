#!/usr/bin/env python3
# Copyright (c) 2025 SNF-AI
# SPDX-License-Identifier: MIT

"""Planner Node - task planning using a shared local Mistral instance."""

import logging
import os
from pathlib import Path
from typing import Any, Optional

from .base import FluxNode

logger = logging.getLogger(__name__)


class PlannerNode(FluxNode):
    """Planner expert node (Mistral-7B with planning-specific prompting)."""

    def __init__(self, model_path: Optional[Path] = None, node_id: str = "planner-mistral-7b",
                 name: str = "Planner (Mistral-7B)",
                 description: str = "Task planning and decomposition using a local instruction-following model"):
        super().__init__(node_id, name, description)
        if model_path is None:
            from . import MODELS_DIR
            self.model_path = MODELS_DIR / "mistral-7b-instruct-q4.gguf"
        else:
            self.model_path = model_path

        if not os.path.exists(self.model_path):
            logger.error(f"Model file not found: {self.model_path}")
            self.is_available = False
            return

        self.keywords = {"plan", "organize", "schedule", "task", "project",
                         "workflow", "itinerary", "timeline"}
        self.metadata = {
            "model": "Mistral-7B-Instruct-v0.2-Local",
            "backend": "llama_cpp",
            "context_length": "8192",
            "capabilities": "task_planning,travel_planning,project_planning,meeting_planning,resource_planning",
        }

    def generate(self, prompt: str, **kwargs: Any) -> str:
        conversation_history = kwargs.get('conversation_history', [])
        plan_type = self._determine_plan_type(prompt.strip())
        enhanced_prompt = self._enhance_prompt(prompt.strip(), plan_type, conversation_history)
        try:
            # Fetch at call time (do not cache): the shared cache keeps ONE
            # resident model and may have evicted ours for another node.
            from .shared_model import get_shared_model
            model = get_shared_model(self.model_path)
            response = model(
                enhanced_prompt, max_tokens=1024, temperature=0.7, top_p=0.9,
                stop=["</s>"], echo=False,
            )
            return response["choices"][0]["text"].strip()
        except Exception as e:
            logger.exception(f"Error generating plan: {e}")
            return "I'm having trouble generating a detailed plan right now. Please try again."

    def _determine_plan_type(self, query_text: str) -> str:
        q = query_text.lower()
        if any(k in q for k in ["sprint", "agile", "scrum"]):
            return "sprint_planning"
        if any(k in q for k in ["project", "timeline", "milestone"]):
            return "project_planning"
        if any(k in q for k in ["trip", "travel", "itinerary"]):
            return "travel_planning"
        if any(k in q for k in ["meeting", "agenda", "workshop"]):
            return "meeting_planning"
        if any(k in q for k in ["resource", "budget", "cost"]):
            return "resource_planning"
        return "general_planning"

    def _enhance_prompt(self, query_text: str, plan_type: str, conversation_history: list = None) -> str:
        prompts = {
            "sprint_planning": "You are an expert Agile/Scrum Master. Create a detailed sprint plan with user stories, acceptance criteria, and time estimates.",
            "project_planning": "You are an expert Project Manager. Create a detailed project plan with phases, milestones, deliverables, and timelines.",
            "travel_planning": "You are an expert Travel Planner. Create a detailed travel itinerary with destinations, activities, and logistics.",
            "meeting_planning": "You are an expert Meeting Facilitator. Create a detailed meeting plan with agenda, objectives, and action items.",
            "resource_planning": "You are an expert Resource Manager. Create a detailed resource allocation plan with requirements, assignments, and schedules.",
            "general_planning": "You are an expert Planner. Create a detailed, structured plan with clear steps and objectives.",
        }
        base = prompts.get(plan_type, prompts["general_planning"])
        return f"[INST] {base}\n\nRequest: {query_text}\n\nProvide a detailed, structured plan with clear steps. [/INST]"
