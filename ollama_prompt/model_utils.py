#!/usr/bin/env python3
"""
Model configuration utility command handlers for ollama-prompt CLI.

Handles --scan-models, --show-models, --set-*-model commands.
"""

import json
import sys
from typing import Any

from ollama_prompt.model_manifest import ModelManifest


def handle_model_command(args: Any) -> None:
    """
    Handle model configuration commands.

    Args:
        args: Parsed command line arguments
    """
    manifest = ModelManifest()

    # Handle --scan-models
    if args.scan_models:
        print("Scanning available Ollama models...", file=sys.stderr)

        try:
            result = manifest.scan_and_update()

            print(f"Found {result['total_models']} model(s)", file=sys.stderr)

            if result["new_models"]:
                print(f"New models: {', '.join(result['new_models'])}", file=sys.stderr)

            print("", file=sys.stderr)
            print("Task Assignments:", file=sys.stderr)
            for task, model in result["task_assignments"].items():
                status = "[OK]" if model else "[--]"
                model_display = model or "(none)"
                print(f"  {status} {task}: {model_display}", file=sys.stderr)

            print("", file=sys.stderr)
            print(f"Manifest saved to: {manifest.path}", file=sys.stderr)

            # Output JSON for scripting
            print(json.dumps({
                "success": True,
                "total_models": result["total_models"],
                "new_models": result["new_models"],
                "task_assignments": result["task_assignments"],
                "manifest_path": str(manifest.path),
            }))

        except Exception as e:
            print(f"[FAIL] Scan failed: {e}", file=sys.stderr)
            print(json.dumps({"success": False, "error": str(e)}))
            sys.exit(1)

        return

    # Handle --show-models
    if args.show_models:
        if not manifest.exists():
            print("No manifest found. Run --scan-models first.", file=sys.stderr)
            print(json.dumps({
                "success": False,
                "error": "No manifest found",
                "hint": "Run --scan-models to create one",
            }))
            sys.exit(1)

        print(manifest.get_summary(), file=sys.stderr)

        # Output JSON for scripting
        data = manifest.load()
        print(json.dumps({
            "success": True,
            "task_assignments": data.get("task_assignments", {}),
            "total_models": len(data.get("models", {})),
            "last_scan": data.get("last_scan"),
        }))
        return

    # Handle --set-*-model commands
    set_commands = {
        "set_embedding_model": ("embedding", args.set_embedding_model),
        "set_vision_model": ("vision", args.set_vision_model),
        "set_code_model": ("code", args.set_code_model),
        "set_reasoning_model": ("reasoning", args.set_reasoning_model),
        "set_general_model": ("general", args.set_general_model),
    }

    for attr, (task, model) in set_commands.items():
        if model:
            _set_model_for_task(manifest, task, model)
            return


def _set_model_for_task(manifest: ModelManifest, task: str, model: str) -> None:
    """
    Set a model for a task type.

    Args:
        manifest: ModelManifest instance
        task: Task type
        model: Model name to assign
    """
    # Auto-scan if manifest doesn't exist
    if not manifest.exists():
        print("No manifest found. Running initial scan...", file=sys.stderr)
        manifest.scan_and_update()

    try:
        manifest.set_model_for_task(task, model)

        print(f"[OK] Set {task} model to: {model}", file=sys.stderr)
        print(json.dumps({
            "success": True,
            "task": task,
            "model": model,
        }))

    except ValueError as e:
        print(f"[FAIL] {e}", file=sys.stderr)
        print(json.dumps({
            "success": False,
            "error": str(e),
        }))
        sys.exit(1)


def ensure_manifest_exists() -> ModelManifest:
    """
    Ensure manifest exists, creating via scan if needed.

    Returns:
        ModelManifest instance with loaded data
    """
    manifest = ModelManifest()

    if not manifest.exists():
        # First run - auto scan
        print("First run: scanning available models...", file=sys.stderr)
        result = manifest.scan_and_update()
        print(f"Found {result['total_models']} models", file=sys.stderr)

        # Try to import from claude plugin if available
        if manifest.import_from_claude_plugin():
            print("Imported additional models from claude-ollama-agents", file=sys.stderr)

    return manifest
