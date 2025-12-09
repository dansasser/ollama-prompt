#!/usr/bin/env python3
"""
Automatic Context Window Management System for ollama-prompt

This module implements a self-managing context window that automatically
decides when and how to compact context based on usage patterns.
"""

import numpy as np
import ollama
from typing import List, Dict, Tuple, Optional
from datetime import datetime
import json


class ContextManager:
    """
    Automatic context window manager with graduated compaction levels.
    
    The system automatically monitors context usage and applies the appropriate
    compaction strategy without user intervention.
    """
    
    def __init__(self, max_tokens: int = 16000, model_name: str = "deepseek-v3.1:671b-cloud"):
        """
        Initialize the context manager.
        
        Args:
            max_tokens: Maximum context window size in tokens
            model_name: Model name for generating summaries
        """
        self.max_tokens = max_tokens
        self.model_name = model_name
        self.current_tokens = 0
        self.messages = []
        self.file_references = {}
        self.compaction_history = []
        
        # Lazy-load vector scorer only if needed (Level 2)
        self._vector_scorer = None
        
        # Compaction thresholds (based on Manus context engineering best practices)
        # Lower thresholds prevent "context rot" and maintain reasoning quality
        self.SOFT_THRESHOLD = 0.50    # 50% - Start early
        self.HARD_THRESHOLD = 0.65    # 65% - More aggressive
        self.EMERGENCY_THRESHOLD = 0.80  # 80% - Leave headroom
        
        # Compaction cooldown (prevent repeated compaction)
        self.last_compaction_level = 0
        self.messages_since_last_compaction = 0
        self.MIN_MESSAGES_BETWEEN_COMPACTION = 2
    
    # ============================================================================
    # AUTOMATIC DECISION SYSTEM
    # ============================================================================
    
    def add_message(self, role: str, content: str, file_refs: Optional[List[str]] = None) -> None:
        """
        Add a message and AUTOMATICALLY apply compaction if needed.
        
        This is the main entry point - the system decides everything automatically.
        
        Args:
            role: 'user' or 'assistant'
            content: Message content
            file_refs: List of file paths referenced in this message
        """
        # Create message object
        message = {
            'role': role,
            'content': content,
            'timestamp': datetime.now().isoformat(),
            'tokens': self._estimate_tokens(content),
            'file_refs': file_refs or [],
            'index': len(self.messages)
        }
        
        # Add to message list
        self.messages.append(message)
        self.current_tokens += message['tokens']
        self.messages_since_last_compaction += 1
        
        # Track file references
        if file_refs:
            for file_path in file_refs:
                self.file_references[file_path] = {
                    'last_message_index': message['index'],
                    'reference_count': self.file_references.get(file_path, {}).get('reference_count', 0) + 1,
                    'mode': 'full'  # Assume full unless specified otherwise
                }
        
        # AUTOMATIC DECISION: Check if compaction is needed
        self._auto_compact()
    
    def _auto_compact(self) -> None:
        """
        AUTOMATIC DECISION ENGINE
        
        This method decides:
        1. IF compaction is needed (based on thresholds)
        2. WHICH level to use (based on usage percentage)
        3. WHEN to apply it (respects cooldown)
        """
        # Calculate current usage
        usage_percent = self.current_tokens / self.max_tokens
        
        # Determine required compaction level
        required_level = self._determine_compaction_level(usage_percent)
        
        # Check if we should compact
        if required_level == 0:
            # No compaction needed
            return
        
        # Check cooldown (prevent thrashing)
        if self.messages_since_last_compaction < self.MIN_MESSAGES_BETWEEN_COMPACTION:
            print(f"[Context Manager] Compaction needed (Level {required_level}) but in cooldown period")
            return
        
        # Check if we need to escalate from previous level
        if required_level <= self.last_compaction_level and usage_percent < 0.85:
            # Don't re-apply same level unless we're getting critical
            return
        
        # APPLY COMPACTION
        print(f"[Context Manager] Usage: {self.current_tokens}/{self.max_tokens} ({usage_percent*100:.1f}%)")
        print(f"[Context Manager] Applying Level {required_level} compaction...")
        
        tokens_before = self.current_tokens
        
        if required_level == 1:
            tokens_freed = self._soft_compact()
        elif required_level == 2:
            tokens_freed = self._hard_compact()
        elif required_level == 3:
            tokens_freed = self._emergency_compact()
        
        tokens_after = self.current_tokens
        
        # Record compaction
        self._record_compaction(required_level, tokens_before, tokens_after, tokens_freed)
        
        # Reset cooldown
        self.last_compaction_level = required_level
        self.messages_since_last_compaction = 0
        
        print(f"[Context Manager] Freed {tokens_freed} tokens")
        print(f"[Context Manager] New usage: {tokens_after}/{self.max_tokens} ({100*tokens_after/self.max_tokens:.1f}%)")
    
    def _determine_compaction_level(self, usage_percent: float) -> int:
        """
        DECISION LOGIC: Determine which compaction level to use.
        
        Args:
            usage_percent: Current usage as percentage (0.0 to 1.0)
        
        Returns:
            0: No compaction needed
            1: Soft compaction (file recompression)
            2: Hard compaction (message summarization)
            3: Emergency compaction (aggressive pruning)
        """
        if usage_percent < self.SOFT_THRESHOLD:
            return 0  # No compaction needed
        
        elif usage_percent < self.HARD_THRESHOLD:
            return 1  # Soft compaction
        
        elif usage_percent < self.EMERGENCY_THRESHOLD:
            return 2  # Hard compaction
        
        else:
            return 3  # Emergency compaction
    
    # ============================================================================
    # LEVEL 1: SOFT COMPACTION (Rule-Based)
    # ============================================================================
    
    def _soft_compact(self) -> int:
        """
        Level 1: Recompress file content that hasn't been used recently.
        
        DECISION: Use simple rules (no LLM, no vectors)
        - Compress files not referenced in last 3 messages
        - Keep conversation history intact
        
        Returns:
            Number of tokens freed
        """
        tokens_freed = 0
        current_index = len(self.messages) - 1
        RECENCY_THRESHOLD = 3  # Messages
        
        files_to_compress = []
        
        # DECISION: Which files to compress?
        for file_path, info in self.file_references.items():
            if info['mode'] == 'full':
                messages_since_reference = current_index - info['last_message_index']
                
                # RULE: Compress if not referenced in last N messages
                if messages_since_reference >= RECENCY_THRESHOLD:
                    files_to_compress.append(file_path)
        
        # Apply compression
        for file_path in files_to_compress:
            tokens_saved = self._compress_file_in_messages(file_path)
            tokens_freed += tokens_saved
            
            print(f"[Context Manager] Compressed {file_path} (saved {tokens_saved} tokens)")
        
        self.current_tokens -= tokens_freed
        return tokens_freed
    
    def _compress_file_in_messages(self, file_path: str) -> int:
        """
        Find and compress a file reference in message history.
        
        Args:
            file_path: Path to file to compress
        
        Returns:
            Tokens saved
        """
        # Find the message containing this file
        for msg in self.messages:
            if file_path in msg.get('file_refs', []):
                # Simulate compression (in real implementation, use FileChunker)
                old_content = msg['content']
                old_tokens = self._estimate_tokens(old_content)
                
                # For now, simulate 90% reduction
                # In real implementation: use FileChunker.summarize_python()
                compressed_marker = f"\n[File {file_path} compressed to summary - use :full to restore]\n"
                new_content = old_content[:len(old_content)//10] + compressed_marker
                new_tokens = self._estimate_tokens(new_content)
                
                msg['content'] = new_content
                msg['tokens'] = new_tokens
                
                # Update file reference tracking
                self.file_references[file_path]['mode'] = 'summary'
                
                return old_tokens - new_tokens
        
        return 0
    
    # ============================================================================
    # LEVEL 2: HARD COMPACTION (Vector-Based)
    # ============================================================================
    
    def _hard_compact(self) -> int:
        """
        Level 2: Summarize old messages using vector-based relevance scoring.
        
        DECISION: Use lightweight vector scoring
        - Embed current query and old messages
        - Keep top 50% most relevant messages
        - Always keep last 5 messages
        
        Returns:
            Number of tokens freed
        """
        tokens_freed = 0
        KEEP_RECENT = 5  # Always keep last 5 messages
        
        # Split messages into recent and old
        if len(self.messages) <= KEEP_RECENT:
            return 0  # Not enough history to compact
        
        recent_messages = self.messages[-KEEP_RECENT:]
        old_messages = self.messages[:-KEEP_RECENT]
        
        # Get current query (last user message)
        current_query = next(
            (msg['content'] for msg in reversed(self.messages) if msg['role'] == 'user'),
            ""
        )
        
        if not current_query:
            # Fallback to simple truncation if no query found
            return self._simple_truncate(old_messages)
        
        # DECISION: Score messages by relevance
        scored_messages = self._score_messages_by_relevance(old_messages, current_query)
        
        # DECISION: Keep top 50% by relevance
        keep_count = max(1, len(scored_messages) // 2)
        messages_to_keep = [msg for score, msg in scored_messages[:keep_count]]
        
        # Calculate tokens saved
        tokens_removed = sum(
            msg['tokens'] for score, msg in scored_messages[keep_count:]
        )
        
        # Rebuild message list
        self.messages = messages_to_keep + recent_messages
        
        tokens_freed = tokens_removed
        self.current_tokens -= tokens_freed
        
        print(f"[Context Manager] Kept {keep_count}/{len(old_messages)} old messages based on relevance")
        
        return tokens_freed
    
    def _score_messages_by_relevance(
        self, 
        messages: List[Dict], 
        query: str
    ) -> List[Tuple[float, Dict]]:
        """
        Score messages by relevance to current query using vectors.
        
        Args:
            messages: Messages to score
            query: Current query to compare against
        
        Returns:
            List of (score, message) tuples, sorted by score descending
        """
        # Lazy-load vector scorer
        if self._vector_scorer is None:
            self._vector_scorer = LightweightVectorScorer()
        
        # Embed query
        query_embedding = self._vector_scorer.embed(query)
        
        # Score each message
        scored = []
        for msg in messages:
            score = self._vector_scorer.score_relevance(msg['content'], query_embedding)
            scored.append((score, msg))
        
        # Sort by score (highest first)
        scored.sort(reverse=True, key=lambda x: x[0])
        
        return scored
    
    # ============================================================================
    # LEVEL 3: EMERGENCY COMPACTION (LLM-Based)
    # ============================================================================
    
    def _emergency_compact(self) -> int:
        """
        Level 3: Aggressive compaction using LLM summarization.
        
        DECISION: Use LLM to create intelligent summary
        - Compress ALL files to summaries
        - Keep only last 2 exchanges (4 messages)
        - Summarize everything else with LLM
        
        Returns:
            Number of tokens freed
        """
        tokens_freed = 0
        
        # Step 1: Compress ALL files
        for file_path, info in self.file_references.items():
            if info['mode'] == 'full':
                tokens_saved = self._compress_file_in_messages(file_path)
                tokens_freed += tokens_saved
        
        # Step 2: Ultra-compress conversation history
        KEEP_RECENT = 4  # Last 2 exchanges
        
        if len(self.messages) <= KEEP_RECENT:
            return tokens_freed
        
        old_messages = self.messages[:-KEEP_RECENT]
        recent_messages = self.messages[-KEEP_RECENT:]
        
        # Calculate tokens in old messages
        old_tokens = sum(msg['tokens'] for msg in old_messages)
        
        # DECISION: Use LLM to summarize
        summary = self._generate_llm_summary(old_messages)
        summary_tokens = self._estimate_tokens(summary)
        
        # Create summary message
        summary_message = {
            'role': 'system',
            'content': f"[COMPRESSED CONVERSATION HISTORY]\n{summary}\n[END COMPRESSED HISTORY]",
            'timestamp': old_messages[0]['timestamp'],
            'tokens': summary_tokens,
            'is_summary': True,
            'file_refs': []
        }
        
        # Rebuild message list
        self.messages = [summary_message] + recent_messages
        
        tokens_saved = old_tokens - summary_tokens
        tokens_freed += tokens_saved
        
        self.current_tokens -= tokens_saved
        
        print(f"[Context Manager] EMERGENCY: Summarized {len(old_messages)} messages into {summary_tokens} tokens")
        
        return tokens_freed
    
    def _generate_llm_summary(self, messages: List[Dict]) -> str:
        """
        Use LLM to generate intelligent summary of messages.
        
        Args:
            messages: Messages to summarize
        
        Returns:
            Summary text
        """
        # Format messages for summarization
        conversation = "\n\n".join([
            f"{msg['role'].upper()}: {msg['content'][:500]}..."
            for msg in messages
        ])
        
        prompt = f"""Create a concise summary (max 300 words) of this conversation.

Preserve:
1. User's main goal/question
2. Key technical points discussed
3. Important code/file references
4. Decisions or conclusions reached

Omit:
- Verbose explanations
- Redundant information
- Greeting/politeness

CONVERSATION:
{conversation}

SUMMARY:"""
        
        try:
            response = ollama.generate(
                model='llama3.2:3b',  # Use smaller model for speed
                prompt=prompt,
                options={'temperature': 0.3, 'max_tokens': 500}
            )
            return response['response']
        except Exception as e:
            print(f"[Context Manager] LLM summary failed: {e}")
            # Fallback to simple truncation
            return f"[Summary of {len(messages)} messages - LLM summarization failed]"
    
    # ============================================================================
    # HELPER METHODS
    # ============================================================================
    
    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count (rough: 1 token ≈ 4 characters)."""
        return len(text) // 4
    
    def _simple_truncate(self, messages: List[Dict]) -> int:
        """Fallback: simple truncation if vector scoring fails."""
        if len(messages) <= 5:
            return 0
        
        keep = messages[-5:]
        remove = messages[:-5]
        
        tokens_freed = sum(msg['tokens'] for msg in remove)
        
        self.messages = [msg for msg in self.messages if msg not in remove]
        self.current_tokens -= tokens_freed
        
        return tokens_freed
    
    def _record_compaction(
        self, 
        level: int, 
        tokens_before: int, 
        tokens_after: int, 
        tokens_freed: int
    ) -> None:
        """Record compaction event for analytics."""
        self.compaction_history.append({
            'timestamp': datetime.now().isoformat(),
            'level': level,
            'tokens_before': tokens_before,
            'tokens_after': tokens_after,
            'tokens_freed': tokens_freed,
            'usage_before': tokens_before / self.max_tokens,
            'usage_after': tokens_after / self.max_tokens
        })
    
    def get_status(self) -> Dict:
        """Get current context manager status."""
        return {
            'current_tokens': self.current_tokens,
            'max_tokens': self.max_tokens,
            'usage_percent': 100 * self.current_tokens / self.max_tokens,
            'message_count': len(self.messages),
            'file_references': len(self.file_references),
            'last_compaction_level': self.last_compaction_level,
            'total_compactions': len(self.compaction_history)
        }


# ============================================================================
# LIGHTWEIGHT VECTOR SCORER (for Level 2)
# ============================================================================

class LightweightVectorScorer:
    """
    Simple vector-based relevance scoring without a full vector database.
    
    Uses Ollama's embedding model for semantic similarity.
    """
    
    def __init__(self, embedding_model: str = "nomic-embed-text"):
        """
        Initialize vector scorer.
        
        Args:
            embedding_model: Ollama embedding model to use
        """
        self.embedding_model = embedding_model
        self.cache = {}  # Cache embeddings to avoid recomputation
    
    def embed(self, text: str) -> np.ndarray:
        """
        Generate embedding for text.
        
        Args:
            text: Text to embed
        
        Returns:
            Embedding vector as numpy array
        """
        # Check cache
        cache_key = hash(text[:200])  # Hash first 200 chars
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        # Generate embedding
        try:
            response = ollama.embeddings(
                model=self.embedding_model,
                prompt=text[:1000]  # Limit to 1000 chars for speed
            )
            embedding = np.array(response["embedding"], dtype=np.float32)
            
            # Cache it
            self.cache[cache_key] = embedding
            
            return embedding
        
        except Exception as e:
            print(f"[Vector Scorer] Embedding failed: {e}")
            # Return zero vector as fallback
            return np.zeros(768, dtype=np.float32)  # nomic-embed-text dimension
    
    def score_relevance(self, text: str, reference_embedding: np.ndarray) -> float:
        """
        Score how relevant text is to reference embedding.
        
        Args:
            text: Text to score
            reference_embedding: Reference embedding to compare against
        
        Returns:
            Cosine similarity score (0.0 to 1.0)
        """
        text_embedding = self.embed(text)
        
        # Cosine similarity
        dot_product = np.dot(text_embedding, reference_embedding)
        norm_product = np.linalg.norm(text_embedding) * np.linalg.norm(reference_embedding)
        
        if norm_product == 0:
            return 0.0
        
        similarity = dot_product / norm_product
        
        # Clamp to [0, 1]
        return float(max(0.0, min(1.0, similarity)))


# ============================================================================
# USAGE EXAMPLE
# ============================================================================

if __name__ == "__main__":
    # Initialize context manager
    cm = ContextManager(max_tokens=16000)
    
    # Simulate a conversation
    print("=== Simulating Conversation ===\n")
    
    # Message 1: User asks about a file
    cm.add_message(
        'user',
        'Explain how authentication works @./user_manager.py:full',
        file_refs=['./user_manager.py']
    )
    print(f"Status: {cm.get_status()}\n")
    
    # Message 2: Assistant responds (simulate large response)
    cm.add_message('assistant', 'A' * 20000)  # 5000 tokens
    print(f"Status: {cm.get_status()}\n")
    
    # Messages 3-10: Continue conversation
    for i in range(3, 11):
        cm.add_message('user', f'Question {i}' + 'X' * 4000)  # 1000 tokens each
        cm.add_message('assistant', 'A' * 4000)
        print(f"Message {i} - Status: {cm.get_status()}\n")
    
    # Final status
    print("\n=== Final Status ===")
    status = cm.get_status()
    for key, value in status.items():
        print(f"{key}: {value}")
    
    print("\n=== Compaction History ===")
    for event in cm.compaction_history:
        print(f"Level {event['level']}: {event['tokens_before']} → {event['tokens_after']} tokens "
              f"({event['usage_before']*100:.1f}% → {event['usage_after']*100:.1f}%)")
