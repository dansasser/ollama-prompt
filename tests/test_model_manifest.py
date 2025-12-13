#!/usr/bin/env python3
"""Tests for ModelManifest module."""

import json
import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from ollama_prompt.model_manifest import ModelManifest


class TestManifestInit:
    """Test manifest initialization."""

    def test_default_path_windows(self, tmp_path, monkeypatch):
        """Test default path on Windows."""
        # Patch os.name at the module level where it's used
        monkeypatch.setattr("ollama_prompt.model_manifest.os.name", "nt")
        monkeypatch.setenv("APPDATA", str(tmp_path))

        manifest = ModelManifest()
        assert "ollama-prompt" in str(manifest.path)
        assert "model-manifest.json" in str(manifest.path)

    def test_default_path_unix(self, tmp_path, monkeypatch):
        """Test default path on Unix/Linux/Mac."""
        # Patch os.name at the module level where it's used
        monkeypatch.setattr("ollama_prompt.model_manifest.os.name", "posix")
        # Patch Path.home() to use tmp_path
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        manifest = ModelManifest()
        assert "ollama-prompt" in str(manifest.path)
        assert "model-manifest.json" in str(manifest.path)
        assert ".config" in str(manifest.path)

    def test_custom_path(self, tmp_path):
        """Test custom manifest path."""
        custom_path = tmp_path / "custom" / "manifest.json"
        manifest = ModelManifest(path=custom_path)
        assert manifest.path == custom_path


class TestManifestLoadSave:
    """Test manifest load/save operations."""

    def test_load_creates_default(self, tmp_path):
        """Test that load creates default manifest if not exists."""
        manifest = ModelManifest(path=tmp_path / "manifest.json")
        data = manifest.load()

        assert "version" in data
        assert "models" in data
        assert "task_assignments" in data

    def test_save_creates_file(self, tmp_path):
        """Test that save creates manifest file."""
        path = tmp_path / "manifest.json"
        manifest = ModelManifest(path=path)
        manifest.load()
        manifest.save()

        assert path.exists()
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert "version" in data

    def test_load_existing_file(self, tmp_path):
        """Test loading existing manifest file."""
        path = tmp_path / "manifest.json"
        existing_data = {
            "version": "1.0",
            "models": {"test-model": {"capabilities": ["general"]}},
            "task_assignments": {"general": "test-model"},
            "fallback_chains": {},
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(existing_data, f)

        manifest = ModelManifest(path=path)
        data = manifest.load()

        assert data["models"]["test-model"]["capabilities"] == ["general"]


class TestTaskAssignments:
    """Test task assignment operations."""

    def test_get_model_for_task(self, tmp_path):
        """Test getting model for a task."""
        path = tmp_path / "manifest.json"
        manifest = ModelManifest(path=path)
        manifest.load()
        manifest._data["task_assignments"]["code"] = "deepseek-v3:cloud"
        manifest.save()

        result = manifest.get_model_for_task("code")
        assert result == "deepseek-v3:cloud"

    def test_get_model_for_unset_task(self, tmp_path):
        """Test getting model for unset task returns None."""
        manifest = ModelManifest(path=tmp_path / "manifest.json")
        manifest.load()

        result = manifest.get_model_for_task("vision")
        assert result is None

    def test_set_model_for_task(self, tmp_path):
        """Test setting model for a task."""
        path = tmp_path / "manifest.json"
        manifest = ModelManifest(path=path)
        manifest.load()

        manifest.set_model_for_task("embedding", "nomic-embed-text")

        assert manifest.get_model_for_task("embedding") == "nomic-embed-text"

        # Verify persisted
        manifest2 = ModelManifest(path=path)
        assert manifest2.get_model_for_task("embedding") == "nomic-embed-text"

    def test_set_model_invalid_task(self, tmp_path):
        """Test setting model for invalid task raises error."""
        manifest = ModelManifest(path=tmp_path / "manifest.json")
        manifest.load()

        with pytest.raises(ValueError, match="Unknown task type"):
            manifest.set_model_for_task("invalid_task", "some-model")


class TestEmbeddingModel:
    """Test embedding model operations."""

    def test_get_embedding_model(self, tmp_path):
        """Test getting embedding model."""
        manifest = ModelManifest(path=tmp_path / "manifest.json")
        manifest.load()
        manifest._data["task_assignments"]["embedding"] = "nomic-embed-text"

        assert manifest.get_embedding_model() == "nomic-embed-text"

    def test_set_embedding_model(self, tmp_path):
        """Test setting embedding model."""
        manifest = ModelManifest(path=tmp_path / "manifest.json")
        manifest.load()

        manifest.set_embedding_model("mxbai-embed-large")
        assert manifest.get_embedding_model() == "mxbai-embed-large"


class TestFallbackChains:
    """Test fallback chain operations."""

    def test_get_fallback_chain(self, tmp_path):
        """Test getting fallback chain."""
        manifest = ModelManifest(path=tmp_path / "manifest.json")
        manifest.load()
        manifest._data["fallback_chains"]["code"] = ["model1", "model2"]
        manifest.save()

        chain = manifest.get_fallback_chain("code")
        assert chain == ["model1", "model2"]

    def test_get_fallback_chain_empty(self, tmp_path):
        """Test getting empty fallback chain."""
        manifest = ModelManifest(path=tmp_path / "manifest.json")
        manifest.load()

        chain = manifest.get_fallback_chain("vision")
        assert chain == []


class TestUpdateFromScan:
    """Test updating manifest from scan results."""

    def test_update_adds_new_models(self, tmp_path):
        """Test that scan results add new models."""
        manifest = ModelManifest(path=tmp_path / "manifest.json")
        manifest.load()

        scan_results = [
            {"name": "llama3:8b", "capabilities": ["general"], "supports_embedding": False},
            {"name": "nomic-embed-text", "capabilities": ["embedding"], "supports_embedding": True},
        ]

        result = manifest.update_from_scan(scan_results)

        assert len(result["new_models"]) == 2
        assert "llama3:8b" in manifest.get_all_models()
        assert "nomic-embed-text" in manifest.get_all_models()

    def test_update_auto_assigns_tasks(self, tmp_path):
        """Test that scan auto-assigns tasks."""
        manifest = ModelManifest(path=tmp_path / "manifest.json")
        manifest.load()

        scan_results = [
            {"name": "nomic-embed-text", "capabilities": ["embedding", "general"], "supports_embedding": True},
        ]

        manifest.update_from_scan(scan_results)

        # Should auto-assign embedding task
        assert manifest.get_model_for_task("embedding") == "nomic-embed-text"

    def test_update_preserves_user_assignments(self, tmp_path):
        """Test that update preserves user-set assignments."""
        manifest = ModelManifest(path=tmp_path / "manifest.json")
        manifest.load()

        # User sets a model
        manifest.set_model_for_task("code", "user-preferred-model")

        scan_results = [
            {"name": "deepseek-v3:cloud", "capabilities": ["code", "reasoning"], "supports_embedding": False},
        ]

        manifest.update_from_scan(scan_results)

        # User preference should be preserved
        assert manifest.get_model_for_task("code") == "user-preferred-model"


class TestScanAndUpdate:
    """Test full scan and update workflow."""

    def test_scan_and_update(self, tmp_path):
        """Test scan_and_update method."""
        manifest = ModelManifest(path=tmp_path / "manifest.json")

        # Mock the scanner instance
        manifest._scanner = MagicMock()
        manifest._scanner.scan.return_value = [
            {"name": "test-model", "capabilities": ["general"], "supports_embedding": False},
        ]
        manifest._scanner.auto_assign_models.return_value = {"general": "test-model"}

        result = manifest.scan_and_update()

        assert result["total_models"] == 1
        assert "test-model" in result["new_models"]


class TestExists:
    """Test manifest existence check."""

    def test_exists_false_when_no_file(self, tmp_path):
        """Test exists returns False when no file."""
        manifest = ModelManifest(path=tmp_path / "nonexistent.json")
        assert manifest.exists() is False

    def test_exists_true_when_file_exists(self, tmp_path):
        """Test exists returns True when file exists."""
        path = tmp_path / "manifest.json"
        path.write_text("{}", encoding="utf-8")

        manifest = ModelManifest(path=path)
        assert manifest.exists() is True


class TestGetSummary:
    """Test summary generation."""

    def test_get_summary_format(self, tmp_path):
        """Test summary output format."""
        manifest = ModelManifest(path=tmp_path / "manifest.json")
        manifest.load()
        manifest._data["task_assignments"]["code"] = "deepseek-v3:cloud"
        manifest._data["models"]["deepseek-v3:cloud"] = {"capabilities": ["code"]}

        summary = manifest.get_summary()

        assert "Model Assignments" in summary
        assert "code" in summary
        assert "deepseek-v3:cloud" in summary
        assert "available" in summary
