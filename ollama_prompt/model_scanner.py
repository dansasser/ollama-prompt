#!/usr/bin/env python3
"""
Model scanning and capability detection for ollama-prompt.

Scans available Ollama models and detects their capabilities based on
model name patterns and known model families.
"""

import json
import subprocess
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional, Set


class ModelScanner:
    """
    Scans Ollama for available models and detects their capabilities.

    Capabilities are detected via:
    1. Name pattern matching (e.g., 'vl' in name -> vision)
    2. Known model family mappings (e.g., deepseek -> code, reasoning)
    3. API probing for embedding support
    """

    # Capability detection patterns (check if pattern is in model name)
    CAPABILITY_PATTERNS: Dict[str, List[str]] = {
        "vision": ["vl", "vision", "visual", "multimodal", "llava"],
        "code": ["code", "coder", "codellama", "starcoder", "codestral"],
        "reasoning": ["thinking", "reason", "r1"],
        "embedding": ["embed", "nomic", "mxbai", "minilm", "bge", "e5"],
        "general": []  # Fallback - all models have general capability
    }

    # Known model families and their capabilities
    FAMILY_CAPABILITIES: Dict[str, List[str]] = {
        "deepseek": ["code", "reasoning", "security", "performance"],
        "kimi": ["code", "reasoning", "architecture", "security"],
        "qwen": ["code", "general"],
        "qwen3": ["code", "reasoning", "general"],
        "nomic": ["embedding"],
        "mxbai": ["embedding"],
        "bge": ["embedding"],
        "llava": ["vision"],
        "mistral": ["general", "code"],
        "mixtral": ["general", "code"],
        "llama": ["general"],
        "gemma": ["general"],
        "phi": ["general", "code"],
        "codellama": ["code"],
        "starcoder": ["code"],
        "wizard": ["code", "general"],
    }

    # Known embedding models (explicit list for accuracy)
    KNOWN_EMBEDDING_MODELS: Set[str] = {
        "nomic-embed-text",
        "mxbai-embed-large",
        "all-minilm",
        "bge-base",
        "bge-large",
        "bge-small",
        "e5-base",
        "e5-large",
        "e5-small",
        "snowflake-arctic-embed",
    }

    def __init__(self, ollama_host: str = "http://localhost:11434"):
        """
        Initialize model scanner.

        Args:
            ollama_host: Ollama API host URL
        """
        self.ollama_host = ollama_host

    def scan(self) -> List[Dict[str, Any]]:
        """
        Scan ollama for available models.

        Returns:
            List of model info dicts with name, size, capabilities
        """
        models = []

        try:
            result = subprocess.run(
                ["ollama", "list"],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                return []

            # Parse ollama list output (skip header line)
            lines = result.stdout.strip().split("\n")
            if len(lines) <= 1:
                return []

            for line in lines[1:]:
                parts = line.split()
                if not parts:
                    continue

                model_name = parts[0]
                model_size = parts[2] if len(parts) > 2 else "unknown"

                capabilities = self.detect_capabilities(model_name)
                supports_embedding = self._is_embedding_model(model_name)

                models.append({
                    "name": model_name,
                    "size": model_size,
                    "capabilities": capabilities,
                    "supports_embedding": supports_embedding,
                    "auto_discovered": True
                })

        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            pass

        return models

    def detect_capabilities(self, model_name: str) -> List[str]:
        """
        Detect capabilities from model name patterns and family.

        Args:
            model_name: Name of the model (e.g., 'deepseek-v3.2:cloud')

        Returns:
            List of capability strings
        """
        capabilities: Set[str] = set()
        name_lower = model_name.lower()

        # Check name patterns
        for capability, patterns in self.CAPABILITY_PATTERNS.items():
            for pattern in patterns:
                if pattern in name_lower:
                    capabilities.add(capability)
                    break

        # Check model family
        for family, family_caps in self.FAMILY_CAPABILITIES.items():
            if family in name_lower:
                capabilities.update(family_caps)

        # All models have general capability
        capabilities.add("general")

        # If it's an embedding model, that's its primary purpose
        if self._is_embedding_model(model_name):
            capabilities.add("embedding")
            # Embedding models typically don't have other capabilities
            capabilities = {"embedding", "general"}

        return sorted(list(capabilities))

    def _is_embedding_model(self, model_name: str) -> bool:
        """
        Check if model is a dedicated embedding model.

        Args:
            model_name: Model name to check

        Returns:
            True if model is an embedding model
        """
        name_lower = model_name.lower()

        # Check against known embedding models
        for known in self.KNOWN_EMBEDDING_MODELS:
            if known in name_lower:
                return True

        # Check patterns
        for pattern in self.CAPABILITY_PATTERNS["embedding"]:
            if pattern in name_lower:
                return True

        return False

    def check_embedding_support(self, model_name: str) -> bool:
        """
        Test if model supports the embedding API by making a test request.

        Args:
            model_name: Model to test

        Returns:
            True if model supports embeddings
        """
        try:
            url = f"{self.ollama_host}/api/embeddings"
            data = json.dumps({
                "model": model_name,
                "prompt": "test"
            }).encode("utf-8")

            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"}
            )

            with urllib.request.urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode("utf-8"))
                return "embedding" in result and len(result["embedding"]) > 0

        except (urllib.error.URLError, json.JSONDecodeError, KeyError, Exception):
            return False

    def find_best_embedding_model(self, available_models: List[str]) -> Optional[str]:
        """
        Find the best available embedding model.

        Priority:
        1. Known dedicated embedding models
        2. Models with 'embed' in name

        Args:
            available_models: List of available model names

        Returns:
            Best embedding model name, or None if none found
        """
        # Priority order for embedding models
        priority_models = [
            "nomic-embed-text",
            "mxbai-embed-large",
            "bge-large",
            "bge-base",
            "e5-large",
            "e5-base",
            "all-minilm",
            "snowflake-arctic-embed",
        ]

        available_lower = {m.lower(): m for m in available_models}

        # Check priority models first
        for priority in priority_models:
            for avail_lower, avail_original in available_lower.items():
                if priority in avail_lower:
                    return avail_original

        # Check for any model with 'embed' in name
        for avail_lower, avail_original in available_lower.items():
            if "embed" in avail_lower:
                return avail_original

        return None

    def auto_assign_models(
        self,
        models: List[Dict[str, Any]]
    ) -> Dict[str, Optional[str]]:
        """
        Auto-assign best model for each task type.

        Args:
            models: List of model info dicts from scan()

        Returns:
            Dict mapping task type to model name
        """
        assignments: Dict[str, Optional[str]] = {
            "vision": None,
            "architecture": None,
            "code": None,
            "reasoning": None,
            "security": None,
            "performance": None,
            "general": None,
            "embedding": None,
        }

        # Build capability -> models mapping
        capability_models: Dict[str, List[str]] = {}
        for model in models:
            for cap in model.get("capabilities", []):
                if cap not in capability_models:
                    capability_models[cap] = []
                capability_models[cap].append(model["name"])

        # Priority patterns for selection (prefer these in model names)
        priority_patterns = {
            "vision": ["qwen3", "qwen", "llava"],
            "code": ["deepseek", "kimi", "code"],
            "reasoning": ["deepseek", "kimi", "thinking"],
            "embedding": ["nomic", "mxbai", "bge", "embed"],
            "general": ["mistral", "llama", "qwen"],
        }

        def select_best(task: str, capability: str) -> Optional[str]:
            candidates = capability_models.get(capability, [])
            if not candidates:
                return None

            # Check priority patterns
            patterns = priority_patterns.get(task, [])
            for pattern in patterns:
                for candidate in candidates:
                    if pattern in candidate.lower():
                        return candidate

            # Return first available
            return candidates[0] if candidates else None

        # Assign models
        assignments["vision"] = select_best("vision", "vision")
        assignments["code"] = select_best("code", "code")
        assignments["reasoning"] = select_best("reasoning", "reasoning")
        assignments["embedding"] = select_best("embedding", "embedding")
        assignments["general"] = select_best("general", "general")

        # These share with code/reasoning
        assignments["architecture"] = assignments["vision"] or assignments["code"]
        assignments["security"] = assignments["code"]
        assignments["performance"] = assignments["code"]

        return assignments
