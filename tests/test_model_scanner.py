#!/usr/bin/env python3
"""Tests for ModelScanner module."""

import pytest
from unittest.mock import patch, MagicMock

from ollama_prompt.model_scanner import ModelScanner


class TestCapabilityDetection:
    """Test capability detection from model names."""

    def test_detect_vision_capability(self):
        """Test detection of vision capabilities."""
        scanner = ModelScanner()

        # Models with vision capability
        assert "vision" in scanner.detect_capabilities("qwen3-vl:latest")
        assert "vision" in scanner.detect_capabilities("llava:7b")
        assert "vision" in scanner.detect_capabilities("vision-model")

    def test_detect_code_capability(self):
        """Test detection of code capabilities."""
        scanner = ModelScanner()

        assert "code" in scanner.detect_capabilities("deepseek-coder:6.7b")
        assert "code" in scanner.detect_capabilities("codellama:13b")
        assert "code" in scanner.detect_capabilities("starcoder2:7b")

    def test_detect_reasoning_capability(self):
        """Test detection of reasoning capabilities."""
        scanner = ModelScanner()

        assert "reasoning" in scanner.detect_capabilities("kimi-k2-thinking:cloud")
        assert "reasoning" in scanner.detect_capabilities("deepseek-r1:7b")

    def test_detect_embedding_capability(self):
        """Test detection of embedding capabilities."""
        scanner = ModelScanner()

        assert "embedding" in scanner.detect_capabilities("nomic-embed-text")
        assert "embedding" in scanner.detect_capabilities("mxbai-embed-large")
        assert "embedding" in scanner.detect_capabilities("bge-base-en")

    def test_all_models_have_general(self):
        """Test that all models have general capability."""
        scanner = ModelScanner()

        assert "general" in scanner.detect_capabilities("any-random-model")
        assert "general" in scanner.detect_capabilities("llama3:8b")
        assert "general" in scanner.detect_capabilities("mistral:7b")

    def test_family_capabilities(self):
        """Test family-based capability detection."""
        scanner = ModelScanner()

        # Deepseek family
        caps = scanner.detect_capabilities("deepseek-v3:cloud")
        assert "code" in caps
        assert "reasoning" in caps

        # Kimi family
        caps = scanner.detect_capabilities("kimi-k2:cloud")
        assert "code" in caps
        assert "reasoning" in caps

    def test_embedding_model_limited_capabilities(self):
        """Test that embedding models have limited capabilities."""
        scanner = ModelScanner()

        caps = scanner.detect_capabilities("nomic-embed-text")
        assert "embedding" in caps
        assert "general" in caps
        # Should NOT have code/vision etc
        assert "code" not in caps
        assert "vision" not in caps


class TestEmbeddingModelDetection:
    """Test embedding model detection."""

    def test_known_embedding_models(self):
        """Test detection of known embedding models."""
        scanner = ModelScanner()

        assert scanner._is_embedding_model("nomic-embed-text")
        assert scanner._is_embedding_model("mxbai-embed-large")
        assert scanner._is_embedding_model("all-minilm")
        assert scanner._is_embedding_model("bge-large-en")

    def test_non_embedding_models(self):
        """Test that chat models are not marked as embedding."""
        scanner = ModelScanner()

        assert not scanner._is_embedding_model("llama3:8b")
        assert not scanner._is_embedding_model("mistral:7b")
        assert not scanner._is_embedding_model("deepseek-v3:cloud")


class TestFindBestEmbeddingModel:
    """Test finding best embedding model from available models."""

    def test_find_nomic_first(self):
        """Test that nomic-embed-text is preferred."""
        scanner = ModelScanner()

        available = ["llama3:8b", "nomic-embed-text", "mxbai-embed-large"]
        best = scanner.find_best_embedding_model(available)
        assert best == "nomic-embed-text"

    def test_find_mxbai_when_no_nomic(self):
        """Test fallback to mxbai when nomic not available."""
        scanner = ModelScanner()

        available = ["llama3:8b", "mxbai-embed-large", "bge-base"]
        best = scanner.find_best_embedding_model(available)
        assert best == "mxbai-embed-large"

    def test_find_any_embed_model(self):
        """Test finding any model with 'embed' in name."""
        scanner = ModelScanner()

        available = ["llama3:8b", "custom-embed-model"]
        best = scanner.find_best_embedding_model(available)
        assert best == "custom-embed-model"

    def test_no_embedding_model_available(self):
        """Test when no embedding model is available."""
        scanner = ModelScanner()

        available = ["llama3:8b", "mistral:7b", "deepseek:6.7b"]
        best = scanner.find_best_embedding_model(available)
        assert best is None


class TestAutoAssignModels:
    """Test automatic model assignment."""

    def test_auto_assign_with_varied_models(self):
        """Test auto-assignment with different model types."""
        scanner = ModelScanner()

        models = [
            {"name": "qwen3-vl:latest", "capabilities": ["vision", "code", "general"]},
            {"name": "deepseek-v3:cloud", "capabilities": ["code", "reasoning", "general"]},
            {"name": "nomic-embed-text", "capabilities": ["embedding", "general"]},
            {"name": "llama3:8b", "capabilities": ["general"]},
        ]

        assignments = scanner.auto_assign_models(models)

        assert assignments["vision"] == "qwen3-vl:latest"
        assert assignments["code"] == "deepseek-v3:cloud"
        assert assignments["embedding"] == "nomic-embed-text"
        assert assignments["general"] is not None

    def test_auto_assign_empty_models(self):
        """Test auto-assignment with no models."""
        scanner = ModelScanner()

        assignments = scanner.auto_assign_models([])

        for task in assignments:
            assert assignments[task] is None


class TestScan:
    """Test model scanning."""

    @patch("subprocess.run")
    def test_scan_parses_ollama_list(self, mock_run):
        """Test parsing of ollama list output."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="NAME                    ID           SIZE    MODIFIED\n"
                   "llama3:8b               abc123       4.7 GB  2 days ago\n"
                   "nomic-embed-text        def456       274 MB  5 days ago\n"
        )

        scanner = ModelScanner()
        models = scanner.scan()

        assert len(models) == 2
        assert models[0]["name"] == "llama3:8b"
        assert models[1]["name"] == "nomic-embed-text"

    @patch("subprocess.run")
    def test_scan_handles_empty_output(self, mock_run):
        """Test handling of empty ollama list."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="NAME                    ID           SIZE    MODIFIED\n"
        )

        scanner = ModelScanner()
        models = scanner.scan()

        assert len(models) == 0

    @patch("subprocess.run")
    def test_scan_handles_error(self, mock_run):
        """Test handling of ollama list error."""
        mock_run.return_value = MagicMock(returncode=1, stdout="")

        scanner = ModelScanner()
        models = scanner.scan()

        assert len(models) == 0

    @patch("subprocess.run")
    def test_scan_handles_timeout(self, mock_run):
        """Test handling of timeout."""
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired("ollama", 30)

        scanner = ModelScanner()
        models = scanner.scan()

        assert len(models) == 0
