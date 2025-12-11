#!/usr/bin/env python3
"""
Context Manager for intelligent conversation compaction.

Provides automatic 3-level graduated compaction to manage context window usage:
- Level 1 (Soft): Compress stale files from full to summary
- Level 2 (Hard): Prune low-relevance messages
- Level 3 (Emergency): LLM-based summarization of history
"""

import json
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

from ollama_prompt.session_db import SessionDatabase
from ollama_prompt.file_chunker import FileChunker
from ollama_prompt.vector_embedder import VectorEmbedder


class ContextManager:
    """
    Manages context window usage with automatic compaction.

    Implements 3-level graduated compaction:
    - Level 1 (50%): File recompression (full -> summary)
    - Level 2 (65%): Message pruning by relevance
    - Level 3 (80%): Emergency LLM summarization

    Usage:
        manager = ContextManager(db, session_id, max_tokens=64000)
        manager.add_message("user", "Hello", tokens=10)
        manager.add_message("assistant", "Hi there!", tokens=15)
        # Compaction happens automatically when thresholds are crossed
    """

    # Compaction threshold constants (as percentages of max_tokens)
    SOFT_THRESHOLD = 0.50    # 50% - Start compressing stale files
    HARD_THRESHOLD = 0.65    # 65% - Start pruning low-relevance messages
    EMERGENCY_THRESHOLD = 0.80  # 80% - Emergency LLM summarization

    # Cooldown settings to prevent compaction thrashing
    MIN_MESSAGES_BETWEEN_COMPACTION = 2
    MIN_TIME_BETWEEN_COMPACTION_SECONDS = 30

    # Stale file detection
    STALE_FILE_THRESHOLD = 3  # Messages since last reference

    # Message pruning settings
    MIN_MESSAGES_TO_KEEP = 4  # Always keep last N messages (2 exchanges)
    RELEVANCE_KEEP_PERCENTAGE = 0.50  # Keep top 50% most relevant

    def __init__(
        self,
        db: SessionDatabase,
        session_id: str,
        max_tokens: int = 64000,
        file_chunker: Optional[FileChunker] = None,
        llm_summarizer: Optional[callable] = None,
        vector_embedder: Optional[VectorEmbedder] = None,
        use_vector_scoring: bool = True
    ):
        """
        Initialize context manager.

        Args:
            db: SessionDatabase instance
            session_id: Session identifier
            max_tokens: Maximum context window tokens
            file_chunker: FileChunker instance for file operations
            llm_summarizer: Optional callback for LLM summarization
                           Signature: (messages: List[Dict]) -> str
            vector_embedder: Optional VectorEmbedder for semantic scoring
            use_vector_scoring: Whether to use vector scoring (falls back to keywords)
        """
        self.db = db
        self.session_id = session_id
        self.max_tokens = max_tokens
        self.chunker = file_chunker or FileChunker()
        self.llm_summarizer = llm_summarizer
        self.use_vector_scoring = use_vector_scoring

        # Lazy-load vector embedder only when needed
        self._vector_embedder = vector_embedder
        self._vector_available: Optional[bool] = None

        # Cooldown tracking
        self._last_compaction_time: Optional[datetime] = None
        self._messages_since_compaction = 0

        # Load last compaction info from database
        last = db.get_last_compaction(session_id)
        if last:
            try:
                self._last_compaction_time = datetime.fromisoformat(last["timestamp"])
            except (ValueError, KeyError):
                pass

    def _get_vector_embedder(self) -> Optional[VectorEmbedder]:
        """
        Get vector embedder, creating it lazily if needed.

        Returns:
            VectorEmbedder instance, or None if not available/disabled
        """
        if not self.use_vector_scoring:
            return None

        if self._vector_embedder is None:
            self._vector_embedder = VectorEmbedder()

        # Check if model is available (cached after first check)
        if self._vector_available is None:
            self._vector_available = self._vector_embedder.is_available()

        if not self._vector_available:
            return None

        return self._vector_embedder

    def get_usage(self) -> float:
        """
        Get current context window usage as a ratio (0.0 to 1.0+).

        Returns:
            float: Ratio of current tokens to max tokens
        """
        current_tokens = self.db.get_message_tokens(self.session_id)
        if self.max_tokens <= 0:
            return 0.0
        return current_tokens / self.max_tokens

    def get_usage_percentage(self) -> float:
        """
        Get current context window usage as a percentage.

        Returns:
            float: Percentage of context window used (0-100+)
        """
        return self.get_usage() * 100

    def _determine_level(self) -> int:
        """
        Determine which compaction level to trigger based on usage.

        Returns:
            int: Compaction level (0=none, 1=soft, 2=hard, 3=emergency)
        """
        usage = self.get_usage()

        if usage >= self.EMERGENCY_THRESHOLD:
            return 3
        elif usage >= self.HARD_THRESHOLD:
            return 2
        elif usage >= self.SOFT_THRESHOLD:
            return 1
        else:
            return 0

    def _can_compact(self) -> bool:
        """
        Check if compaction is allowed (cooldown not active).

        Returns:
            bool: True if compaction can proceed
        """
        # Check message count cooldown
        if self._messages_since_compaction < self.MIN_MESSAGES_BETWEEN_COMPACTION:
            return False

        # Check time cooldown
        if self._last_compaction_time is not None:
            elapsed = (datetime.now() - self._last_compaction_time).total_seconds()
            if elapsed < self.MIN_TIME_BETWEEN_COMPACTION_SECONDS:
                return False

        return True

    def _record_compaction(self, level: int, tokens_before: int, tokens_after: int, strategy: str, details: Optional[Dict] = None):
        """Record compaction event and update cooldown tracking."""
        self.db.record_compaction(
            session_id=self.session_id,
            level=level,
            tokens_before=tokens_before,
            tokens_after=tokens_after,
            strategy=strategy,
            details=json.dumps(details) if details else None
        )
        self._last_compaction_time = datetime.now()
        self._messages_since_compaction = 0

    def add_message(
        self,
        role: str,
        content: str,
        tokens: int,
        file_refs: Optional[List[Tuple[str, str, int]]] = None
    ) -> int:
        """
        Add a message and automatically trigger compaction if needed.

        Args:
            role: Message role ('user', 'assistant', 'system')
            content: Message content
            tokens: Token count for the message
            file_refs: Optional list of (file_path, mode, tokens) tuples

        Returns:
            int: Message ID
        """
        # Save the message
        msg_id = self.db.save_message(
            session_id=self.session_id,
            role=role,
            content=content,
            tokens=tokens
        )

        # Track file references
        if file_refs:
            for file_path, mode, file_tokens in file_refs:
                self.db.track_file_reference(msg_id, file_path, mode, file_tokens)

        # Update cooldown counter
        self._messages_since_compaction += 1

        # Check if compaction is needed
        self._auto_compact()

        return msg_id

    def _auto_compact(self) -> Optional[int]:
        """
        Automatically perform compaction if thresholds are crossed.

        Returns:
            int: Compaction level performed (0 if none), or None if cooldown active
        """
        if not self._can_compact():
            return None

        level = self._determine_level()

        if level == 0:
            return 0

        # Execute appropriate compaction level
        if level >= 3:
            self._emergency_compact()
        elif level >= 2:
            self._hard_compact()
        elif level >= 1:
            self._soft_compact()

        return level

    def force_compact(self, level: int = 1) -> int:
        """
        Force compaction regardless of cooldown.

        Args:
            level: Compaction level (1=soft, 2=hard, 3=emergency)

        Returns:
            int: Tokens freed
        """
        tokens_before = self.db.get_message_tokens(self.session_id)

        if level >= 3:
            self._emergency_compact()
        elif level >= 2:
            self._hard_compact()
        else:
            self._soft_compact()

        tokens_after = self.db.get_message_tokens(self.session_id)
        return tokens_before - tokens_after

    # =========================================================================
    # Level 1: Soft Compaction (File Recompression)
    # =========================================================================

    def _soft_compact(self) -> int:
        """
        Level 1: Compress stale files from full to summary.

        Finds files in 'full' mode not referenced in recent messages
        and replaces their content with summaries.

        Returns:
            int: Tokens freed
        """
        tokens_before = self.db.get_message_tokens(self.session_id)

        # Find stale files that are still in 'full' mode
        stale_files = self.db.get_stale_files(
            session_id=self.session_id,
            stale_threshold=self.STALE_FILE_THRESHOLD,
            mode_filter="full"
        )

        compressed_count = 0
        tokens_saved = 0

        for file_info in stale_files:
            # Get the file reference record
            refs = self.db.get_file_references(
                self.session_id,
                file_path=file_info["file_path"]
            )

            if not refs:
                continue

            # Get the most recent reference
            latest_ref = refs[0]

            # Calculate summary tokens (estimate: ~10% of original)
            original_tokens = latest_ref["tokens"]
            summary_tokens = max(50, original_tokens // 10)

            # Update the reference mode
            self.db.update_file_reference_mode(
                file_ref_id=latest_ref["id"],
                new_mode="summary",
                new_tokens=summary_tokens
            )

            tokens_saved += (original_tokens - summary_tokens)
            compressed_count += 1

        tokens_after = self.db.get_message_tokens(self.session_id)

        if compressed_count > 0:
            self._record_compaction(
                level=1,
                tokens_before=tokens_before,
                tokens_after=tokens_after,
                strategy="file_compress",
                details={"files_compressed": compressed_count, "tokens_saved": tokens_saved}
            )

        return tokens_saved

    # =========================================================================
    # Level 2: Hard Compaction (Message Pruning)
    # =========================================================================

    def _hard_compact(self) -> int:
        """
        Level 2: Prune low-relevance messages.

        Scores messages by relevance to recent context and removes
        the lowest-scoring ones while keeping recent messages.

        Returns:
            int: Tokens freed
        """
        tokens_before = self.db.get_message_tokens(self.session_id)

        # First, try soft compaction
        self._soft_compact()

        # Load all messages
        messages = self.db.load_messages(self.session_id)

        if len(messages) <= self.MIN_MESSAGES_TO_KEEP:
            return 0

        # Get recent messages (last N) - these are always kept
        recent_messages = messages[-self.MIN_MESSAGES_TO_KEEP:]
        recent_ids = {m["id"] for m in recent_messages}

        # Get older messages to evaluate
        older_messages = [m for m in messages if m["id"] not in recent_ids]

        if not older_messages:
            return 0

        # Build context from recent messages for relevance scoring
        recent_context = " ".join(m["content"] for m in recent_messages)

        # Score older messages by relevance
        scored_messages = []
        for msg in older_messages:
            score = self._calculate_relevance(msg, recent_context)
            scored_messages.append((msg, score))

        # Sort by score (highest first) and keep top percentage
        scored_messages.sort(key=lambda x: x[1], reverse=True)
        keep_count = max(1, int(len(scored_messages) * self.RELEVANCE_KEEP_PERCENTAGE))
        messages_to_keep = scored_messages[:keep_count]
        messages_to_delete = scored_messages[keep_count:]

        # Delete low-relevance messages
        if messages_to_delete:
            delete_ids = [m[0]["id"] for m in messages_to_delete]
            self.db.delete_messages(delete_ids)

        tokens_after = self.db.get_message_tokens(self.session_id)

        if messages_to_delete:
            self._record_compaction(
                level=2,
                tokens_before=tokens_before,
                tokens_after=tokens_after,
                strategy="message_prune",
                details={
                    "messages_deleted": len(messages_to_delete),
                    "messages_kept": keep_count + len(recent_messages)
                }
            )

        return tokens_before - tokens_after

    def _calculate_relevance(self, message: Dict[str, Any], context: str) -> float:
        """
        Calculate relevance score for a message.

        Uses vector embeddings for semantic similarity if available,
        falls back to keyword-based scoring otherwise.

        Args:
            message: Message dictionary
            context: Recent context to compare against

        Returns:
            float: Relevance score (0.0 to 1.0)
        """
        message_content = message.get("content", "")

        # Try vector-based scoring first
        embedder = self._get_vector_embedder()
        if embedder:
            vector_score = embedder.score_relevance(message_content, context)
            if vector_score > 0:
                # Apply boosts to vector score
                return self._apply_relevance_boosts(message, vector_score)

        # Fall back to keyword-based scoring
        return self._calculate_keyword_relevance(message, context)

    def _calculate_keyword_relevance(self, message: Dict[str, Any], context: str) -> float:
        """
        Calculate relevance score using keyword overlap (Jaccard similarity).

        Args:
            message: Message dictionary
            context: Recent context to compare against

        Returns:
            float: Relevance score (0.0 to 1.0)
        """
        message_content = message.get("content", "")

        # Extract keywords (alphanumeric tokens)
        message_words = set(re.findall(r'\b\w{3,}\b', message_content.lower()))
        context_words = set(re.findall(r'\b\w{3,}\b', context.lower()))

        if not message_words or not context_words:
            return 0.0

        # Calculate Jaccard similarity
        intersection = len(message_words & context_words)
        union = len(message_words | context_words)

        if union == 0:
            return 0.0

        base_score = intersection / union
        return self._apply_relevance_boosts(message, base_score)

    def _apply_relevance_boosts(self, message: Dict[str, Any], base_score: float) -> float:
        """
        Apply boosts to relevance score based on message characteristics.

        Args:
            message: Message dictionary
            base_score: Initial relevance score

        Returns:
            float: Boosted score (capped at 1.0)
        """
        message_content = message.get("content", "")

        # Boost for certain message types
        role = message.get("role", "")
        if role == "assistant":
            base_score *= 1.1  # Slightly prefer assistant responses

        # Boost for messages with code blocks
        if "```" in message_content:
            base_score *= 1.2

        # Boost for messages with file references
        if "@./" in message_content or "@/" in message_content:
            base_score *= 1.15

        return min(1.0, base_score)

    # =========================================================================
    # Level 3: Emergency Compaction (LLM Summarization)
    # =========================================================================

    def _emergency_compact(self) -> int:
        """
        Level 3: Emergency LLM-based summarization.

        1. Compress ALL files to summaries
        2. Keep only last 2 exchanges (4 messages)
        3. Summarize older history using LLM
        4. Replace old messages with summary message

        Returns:
            int: Tokens freed
        """
        tokens_before = self.db.get_message_tokens(self.session_id)

        # First, force soft compaction on all files
        stale_files = self.db.get_stale_files(
            session_id=self.session_id,
            stale_threshold=0,  # All files are "stale" for emergency
            mode_filter="full"
        )

        for file_info in stale_files:
            refs = self.db.get_file_references(
                self.session_id,
                file_path=file_info["file_path"]
            )
            if refs:
                latest_ref = refs[0]
                original_tokens = latest_ref["tokens"]
                summary_tokens = max(50, original_tokens // 10)
                self.db.update_file_reference_mode(
                    file_ref_id=latest_ref["id"],
                    new_mode="summary",
                    new_tokens=summary_tokens
                )

        # Load all messages
        messages = self.db.load_messages(self.session_id)

        # Keep last 4 messages (2 exchanges)
        keep_count = min(4, len(messages))
        messages_to_keep = messages[-keep_count:] if keep_count > 0 else []
        messages_to_summarize = messages[:-keep_count] if keep_count < len(messages) else []

        if not messages_to_summarize:
            tokens_after = self.db.get_message_tokens(self.session_id)
            return tokens_before - tokens_after

        # Generate summary
        if self.llm_summarizer:
            # Use provided LLM summarizer
            summary_text = self.llm_summarizer(messages_to_summarize)
        else:
            # Fallback: Create a simple structural summary
            summary_text = self._create_fallback_summary(messages_to_summarize)

        # Delete old messages
        delete_ids = [m["id"] for m in messages_to_summarize]
        self.db.delete_messages(delete_ids)

        # Add summary as a system message
        summary_tokens = len(summary_text) // 4  # Rough estimate
        self.db.save_message(
            session_id=self.session_id,
            role="system",
            content=f"[Previous conversation summary]\n{summary_text}",
            tokens=summary_tokens,
            is_summary=True
        )

        tokens_after = self.db.get_message_tokens(self.session_id)

        self._record_compaction(
            level=3,
            tokens_before=tokens_before,
            tokens_after=tokens_after,
            strategy="llm_summary",
            details={
                "messages_summarized": len(messages_to_summarize),
                "summary_tokens": summary_tokens
            }
        )

        return tokens_before - tokens_after

    def _create_fallback_summary(self, messages: List[Dict[str, Any]]) -> str:
        """
        Create a simple structural summary without LLM.

        Args:
            messages: List of messages to summarize

        Returns:
            str: Summary text
        """
        summary_parts = []

        # Count message types
        user_count = sum(1 for m in messages if m["role"] == "user")
        assistant_count = sum(1 for m in messages if m["role"] == "assistant")

        summary_parts.append(f"Conversation contained {user_count} user messages and {assistant_count} assistant responses.")

        # Extract key topics (first message and any with code)
        if messages:
            first_content = messages[0].get("content", "")[:200]
            summary_parts.append(f"Started with: {first_content}...")

        # Note any code discussions
        code_messages = [m for m in messages if "```" in m.get("content", "")]
        if code_messages:
            summary_parts.append(f"Included {len(code_messages)} code-related exchanges.")

        # Note file references
        file_refs = [m for m in messages if "@./" in m.get("content", "") or "@/" in m.get("content", "")]
        if file_refs:
            summary_parts.append(f"Referenced files in {len(file_refs)} messages.")

        return "\n".join(summary_parts)

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def get_status(self) -> Dict[str, Any]:
        """
        Get current context manager status.

        Returns:
            Dict with usage info, thresholds, and cooldown status
        """
        current_tokens = self.db.get_message_tokens(self.session_id)
        messages = self.db.load_messages(self.session_id)

        return {
            "session_id": self.session_id,
            "max_tokens": self.max_tokens,
            "current_tokens": current_tokens,
            "usage_percentage": self.get_usage_percentage(),
            "message_count": len(messages),
            "thresholds": {
                "soft": self.SOFT_THRESHOLD * 100,
                "hard": self.HARD_THRESHOLD * 100,
                "emergency": self.EMERGENCY_THRESHOLD * 100
            },
            "current_level": self._determine_level(),
            "can_compact": self._can_compact(),
            "messages_since_compaction": self._messages_since_compaction,
            "last_compaction": self.db.get_last_compaction(self.session_id)
        }

    def get_compaction_stats(self) -> Dict[str, Any]:
        """
        Get compaction statistics for the session.

        Returns:
            Dict with compaction history summary
        """
        history = self.db.get_compaction_history(self.session_id)
        total_freed = self.db.get_total_tokens_freed(self.session_id)

        level_counts = {1: 0, 2: 0, 3: 0}
        for event in history:
            level = event.get("level", 0)
            if level in level_counts:
                level_counts[level] += 1

        return {
            "total_compactions": len(history),
            "total_tokens_freed": total_freed,
            "level_counts": {
                "soft": level_counts[1],
                "hard": level_counts[2],
                "emergency": level_counts[3]
            },
            "recent_compactions": history[:5]  # Last 5
        }
