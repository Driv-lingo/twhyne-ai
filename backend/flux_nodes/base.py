#!/usr/bin/env python3

import abc
import importlib
import inspect
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Type
from dataclasses import dataclass

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Data classes for query and response
@dataclass
class Query:
    id: str
    text: str
    parameters: Dict[str, Any]
    history: List[Dict[str, str]] = None

@dataclass
class Response:
    text: str
    metadata: Dict[str, Any] = None

@dataclass
class NodeInfo:
    node_id: str
    name: str
    description: str
    capabilities: List[str] = None
    keywords: List[str] = None

class NodeCapability:
    TEXT_GENERATION = "text_generation"
    CODE_GENERATION = "code_generation"
    MATH_SOLVING = "math_solving"
    PLANNING = "planning"
    VISION = "vision"

class FluxNode(abc.ABC):
    """Abstract base class for all expert nodes in the Flux system."""

    def __init__(self, node_id: str, name: str, description: str, **kwargs: Any):
        self.node_id = node_id
        self.name = name
        self.description = description
        self.is_available = True  # Default to True, subclasses should set to False if dependencies are missing

    @abc.abstractmethod
    def generate(self, prompt: str, **kwargs: Any) -> Optional[str]:
        """Generate a response based on a prompt and other optional arguments."""
        pass

    def process(self, query: Query) -> Response:
        """Process a query and return a response. This is the main interface method."""
        try:
            # Extract conversation history from query
            conversation_history = query.history or []
            
            # Call the generate method with the query text, history, and parameters
            result = self.generate(query.text, conversation_history=conversation_history, **query.parameters)
            
            if result is None:
                result = "I'm sorry, I couldn't generate a response at this time."
            
            return Response(text=result, metadata={"node_id": self.node_id})
        except Exception as e:
            logger.error(f"Error processing query in {self.node_id}: {e}")
            return Response(text=f"Error processing query: {str(e)}", metadata={"node_id": self.node_id, "error": True})

    def get_status(self) -> Dict[str, Any]:
        """Return the current status of the node."""
        return {
            'node_id': self.node_id,
            'name': self.name,
            'description': self.description,
            'status': 'online' if self.is_available else 'offline',
        }

class NodeRegistry:
    """Discovers, loads, and manages all available FluxNodes."""

    def __init__(self):
        self._nodes: Dict[str, FluxNode] = {}

    def load_nodes(self, nodes_path: Path):
        """Dynamically load all FluxNode subclasses from a given directory."""
        logger.info(f"Loading nodes from: {nodes_path}")
        for file_path in nodes_path.glob('*.py'):
            if file_path.name.startswith('_') or file_path.name == 'base.py':
                continue

            module_name = f'flux_nodes.{file_path.stem}'
            try:
                module = importlib.import_module(module_name)
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if issubclass(obj, FluxNode) and obj is not FluxNode:
                        try:
                            node_instance = obj()
                            if node_instance.node_id in self._nodes:
                                logger.warning(f"Duplicate node ID '{node_instance.node_id}' found. Overwriting.")
                            self._nodes[node_instance.node_id] = node_instance
                            logger.info(f"Successfully loaded node: {node_instance.name} ({node_instance.node_id})")
                        except Exception as e:
                            logger.error(f"Failed to instantiate node {name} from {module_name}: {e}", exc_info=True)

            except Exception as e:
                logger.error(f"Failed to import module {module_name}: {e}", exc_info=True)

    def register_node(self, node: FluxNode):
        """Register a node instance manually."""
        if node.node_id in self._nodes:
            logger.warning(f"Duplicate node ID '{node.node_id}' found. Overwriting.")
        self._nodes[node.node_id] = node
        logger.info(f"Registered node: {node.name} ({node.node_id})")

    def get_node(self, node_id: str) -> Optional[FluxNode]:
        """Retrieve a node by its ID."""
        return self._nodes.get(node_id)

    def get_all_nodes(self) -> List[FluxNode]:
        """Return a list of all registered node instances."""
        return list(self._nodes.values())
    
    def get_all_node_ids(self) -> List[str]:
        """Return a list of all registered node IDs."""
        return list(self._nodes.keys())

    def get_all_node_statuses(self) -> Dict[str, Any]:
        """Return a dictionary of statuses for all registered nodes."""
        return {node_id: node.get_status() for node_id, node in self._nodes.items()}
