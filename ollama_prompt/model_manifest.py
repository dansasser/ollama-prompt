#!/usr/bin/env python3
"""
Model manifest storage and retrieval for ollama-prompt.

Manages persistent storage of model configurations, task assignments,
and fallback chains.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ollama_prompt.model_scanner import ModelScanner


class ModelManifest:
    """
    Manages the model manifest file.

    The manifest stores:
    - Available models and their capabilities
    - Task-to-model assignments
    - Fallback chains for each task type
    """

    # Task types supported
    TASK_TYPES = [
        "vision",
        "architecture",
        "code",
        "reasoning",
        "security",
        "performance",
        "general",
        "embedding",
    ]

    def __init__(self, path: Optional[Path] = None):
        """
        Initialize model manifest.

        Args:
            path: Custom manifest path (default: ~/.config/ollama-prompt/model-manifest.json)
        """
        if path:
            self.path = Path(path)
        else:
            # Cross-platform config directory
            if os.name == "nt":
                # Windows: %APPDATA%/ollama-prompt/
                config_dir = Path(os.environ.get("APPDATA", Path.home())) / "ollama-prompt"
            else:
                # Unix: ~/.config/ollama-prompt/
                config_dir = Path.home() / ".config" / "ollama-prompt"

            self.path = config_dir / "model-manifest.json"

        self._data: Optional[Dict[str, Any]] = None
        self._scanner = ModelScanner()

    def _get_default_manifest(self) -> Dict[str, Any]:
        """Get default empty manifest structure."""
        return {
            "version": "1.0",
            "last_scan": None,
            "models": {},
            "task_assignments": {task: None for task in self.TASK_TYPES},
            "fallback_chains": {task: [] for task in self.TASK_TYPES},
        }

    def load(self) -> Dict[str, Any]:
        """
        Load manifest from disk.

        Returns:
            Manifest data dict
        """
        if self._data is not None:
            return self._data

        if self.path.exists():
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
                    return self._data
            except (json.JSONDecodeError, IOError):
                pass

        self._data = self._get_default_manifest()
        return self._data

    def save(self) -> None:
        """Save manifest to disk."""
        if self._data is None:
            return

        # Ensure parent directory exists
        self.path.parent.mkdir(parents=True, exist_ok=True)

        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)

    def exists(self) -> bool:
        """Check if manifest file exists."""
        return self.path.exists()

    def get_model_for_task(self, task: str) -> Optional[str]:
        """
        Get assigned model for task type.

        Args:
            task: Task type (vision, code, embedding, etc.)

        Returns:
            Model name or None if not assigned
        """
        data = self.load()
        return data.get("task_assignments", {}).get(task)

    def set_model_for_task(self, task: str, model: str) -> None:
        """
        Set model for task type.

        Args:
            task: Task type
            model: Model name to assign
        """
        if task not in self.TASK_TYPES:
            raise ValueError(f"Unknown task type: {task}. Valid: {self.TASK_TYPES}")

        data = self.load()
        if "task_assignments" not in data:
            data["task_assignments"] = {}
        data["task_assignments"][task] = model
        self.save()

    def get_embedding_model(self) -> Optional[str]:
        """
        Get the configured embedding model.

        Returns:
            Embedding model name or None
        """
        return self.get_model_for_task("embedding")

    def set_embedding_model(self, model: str) -> None:
        """
        Set the embedding model.

        Args:
            model: Embedding model name
        """
        self.set_model_for_task("embedding", model)

    def get_fallback_chain(self, task: str) -> List[str]:
        """
        Get fallback models for task.

        Args:
            task: Task type

        Returns:
            List of fallback model names
        """
        data = self.load()
        return data.get("fallback_chains", {}).get(task, [])

    def get_model_with_fallback(self, task: str) -> Optional[str]:
        """
        Get model for task, trying fallbacks if primary not available.

        Args:
            task: Task type

        Returns:
            Available model name or None
        """
        # Try primary assignment
        primary = self.get_model_for_task(task)
        if primary and self._is_model_available(primary):
            return primary

        # Try fallbacks
        for fallback in self.get_fallback_chain(task):
            if self._is_model_available(fallback):
                return fallback

        return None

    def _is_model_available(self, model_name: str) -> bool:
        """Check if model is in the manifest's available models."""
        data = self.load()
        return model_name in data.get("models", {})

    def get_all_models(self) -> Dict[str, Any]:
        """
        Get all known models and their info.

        Returns:
            Dict of model name -> model info
        """
        data = self.load()
        return data.get("models", {})

    def get_task_assignments(self) -> Dict[str, Optional[str]]:
        """
        Get all task assignments.

        Returns:
            Dict of task -> model name
        """
        data = self.load()
        return data.get("task_assignments", {})

    def update_from_scan(self, scan_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Update manifest with scan results.

        Args:
            scan_results: List of model info dicts from ModelScanner.scan()

        Returns:
            Summary of changes
        """
        data = self.load()
        existing_models = set(data.get("models", {}).keys())
        new_models = []
        updated_models = []

        # Update models
        if "models" not in data:
            data["models"] = {}

        for model_info in scan_results:
            name = model_info["name"]
            if name in existing_models:
                # Update existing
                data["models"][name].update(model_info)
                updated_models.append(name)
            else:
                # Add new
                data["models"][name] = model_info
                new_models.append(name)

        # Auto-assign models for tasks that don't have assignments
        assignments = self._scanner.auto_assign_models(scan_results)
        for task, model in assignments.items():
            if model and not data.get("task_assignments", {}).get(task):
                if "task_assignments" not in data:
                    data["task_assignments"] = {}
                data["task_assignments"][task] = model

        # Build fallback chains
        self._build_fallback_chains(data, scan_results)

        # Update timestamp
        data["last_scan"] = datetime.now().isoformat()

        self._data = data
        self.save()

        return {
            "new_models": new_models,
            "updated_models": updated_models,
            "total_models": len(data["models"]),
            "task_assignments": data.get("task_assignments", {}),
        }

    def _build_fallback_chains(
        self,
        data: Dict[str, Any],
        scan_results: List[Dict[str, Any]]
    ) -> None:
        """Build fallback chains from available models."""
        if "fallback_chains" not in data:
            data["fallback_chains"] = {}

        # Group models by capability
        capability_models: Dict[str, List[str]] = {}
        for model in scan_results:
            for cap in model.get("capabilities", []):
                if cap not in capability_models:
                    capability_models[cap] = []
                capability_models[cap].append(model["name"])

        # Task to capability mapping
        task_capability_map = {
            "vision": "vision",
            "architecture": "code",
            "code": "code",
            "reasoning": "reasoning",
            "security": "code",
            "performance": "code",
            "general": "general",
            "embedding": "embedding",
        }

        for task, capability in task_capability_map.items():
            candidates = capability_models.get(capability, [])
            # Exclude the primary assignment from fallbacks
            primary = data.get("task_assignments", {}).get(task)
            fallbacks = [m for m in candidates if m != primary]
            data["fallback_chains"][task] = fallbacks

    def scan_and_update(self) -> Dict[str, Any]:
        """
        Run a full scan and update the manifest.

        Returns:
            Summary of scan results
        """
        scan_results = self._scanner.scan()
        return self.update_from_scan(scan_results)

    def import_from_claude_plugin(self) -> bool:
        """
        Import model info from claude-ollama-agents plugin if available.

        Returns:
            True if import successful
        """
        claude_manifest = Path.home() / ".claude" / "model-capabilities.json"
        if not claude_manifest.exists():
            return False

        try:
            with open(claude_manifest, "r", encoding="utf-8") as f:
                claude_data = json.load(f)

            data = self.load()

            # Import models
            claude_models = claude_data.get("models", {})
            for name, info in claude_models.items():
                if name not in data.get("models", {}):
                    if "models" not in data:
                        data["models"] = {}
                    data["models"][name] = {
                        "capabilities": info.get("capabilities", []),
                        "supports_embedding": "embedding" in info.get("capabilities", []),
                        "auto_discovered": False,
                        "imported_from": "claude-ollama-agents",
                    }

            # Import user defaults as task assignments if not set
            user_defaults = claude_data.get("user_defaults", {})
            if "task_assignments" not in data:
                data["task_assignments"] = {}

            for task, model in user_defaults.items():
                if task in self.TASK_TYPES and not data["task_assignments"].get(task):
                    data["task_assignments"][task] = model

            self._data = data
            self.save()
            return True

        except (json.JSONDecodeError, IOError, KeyError):
            return False

    def get_summary(self) -> str:
        """
        Get a human-readable summary of the manifest.

        Returns:
            Formatted summary string
        """
        data = self.load()

        lines = ["Model Assignments:", ""]
        lines.append("| Task         | Model                           | Status    |")
        lines.append("|--------------|----------------------------------|-----------|")

        assignments = data.get("task_assignments", {})
        models = data.get("models", {})

        for task in self.TASK_TYPES:
            model = assignments.get(task, "")
            if model:
                status = "available" if model in models else "not found"
                # Truncate long model names
                model_display = model[:32] + "..." if len(model) > 35 else model
            else:
                model_display = "(not set)"
                status = "-"

            lines.append(f"| {task:<12} | {model_display:<32} | {status:<9} |")

        lines.append("")
        lines.append(f"Total models: {len(models)}")
        lines.append(f"Last scan: {data.get('last_scan', 'never')}")

        return "\n".join(lines)
