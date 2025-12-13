# Dynamic Context Window Management Strategy for ollama-prompt

## The Problem

As conversations grow longer, the context window fills up with:
- **Conversation history** - previous user messages and model responses
- **File content** - code, documentation, and data referenced in the conversation
- **System prompts** - instructions and metadata

Without active management, the context window eventually overflows, causing either:
1. **Truncation** - older messages are silently dropped, losing important context
2. **Failure** - the model refuses to process the request due to token limit exceeded

## The Solution: Four-Level Context Compaction Strategy

We implement a graduated response system that progressively compacts context as the window fills up.

### Compaction Levels

| Level | Trigger | Action | Token Savings | Information Loss |
|-------|---------|--------|---------------|------------------|
| **0: Normal** | < 50% full | No action | 0% | None |
| **1: Soft Compact** | 50-65% full | Compress file content | 30-50% | Minimal |
| **2: Hard Compact** | 65-80% full | Summarize old messages | 50-70% | Moderate |
| **3: Emergency** | > 80% full | Aggressive pruning | 70-85% | Significant but controlled |

## Level 1: Soft Compaction (50-65% Full)

**Trigger:** Context window reaches 50% capacity

**Strategy:** Recompress file content that was sent in full earlier in the conversation

### What Happens

When a file was initially sent with `:full` mode, but hasn't been referenced in the last 3 messages, automatically recompress it to summary mode.

**Example:**
```
Message 1: "@./user_manager.py:full explain authentication"
[Sends full 45KB file]

Message 2-5: [Discussion about authentication]

Message 6: [Context reaches 50%]
System: Recompresses user_manager.py from 45KB → 2KB summary
         Keeps the conversation history intact
         
Result: Conversation continues smoothly with 43KB freed
```

### Implementation

```python
class ContextManager:
    """Manage context window with dynamic compaction."""
    
    def __init__(self, max_tokens: int = 16000):
        self.max_tokens = max_tokens
        self.current_tokens = 0
        self.messages = []
        self.file_references = {}  # Track when files were last used
        
    def check_compaction_needed(self) -> int:
        """
        Check if compaction is needed and return level.

        Returns:
            0: No compaction needed
            1: Soft compaction (50-65%)
            2: Hard compaction (65-80%)
            3: Emergency compaction (>80%)
        """
        usage = self.current_tokens / self.max_tokens
        
        if usage < 0.50:
            return 0
        elif usage < 0.65:
            return 1
        elif usage < 0.80:
            return 2
        else:
            return 3
    
    def soft_compact(self) -> int:
        """
        Level 1: Recompress file content to summaries.
        
        Returns:
            Number of tokens freed
        """
        tokens_freed = 0
        current_msg_idx = len(self.messages) - 1
        
        # Find files that haven't been referenced recently
        for file_path, info in self.file_references.items():
            if info['mode'] == 'full':
                # Check if file was referenced in last 3 messages
                last_reference = info['last_message_index']
                messages_since = current_msg_idx - last_reference
                
                if messages_since >= 3:
                    # Recompress this file
                    old_content = info['content']
                    old_tokens = self._estimate_tokens(old_content)
                    
                    # Generate summary
                    chunker = FileChunker()
                    summary = chunker.summarize_python(old_content, file_path)
                    new_content = chunker.format_summary(summary)
                    new_tokens = self._estimate_tokens(new_content)
                    
                    # Update the message that contained this file
                    msg_idx = info['message_index']
                    self.messages[msg_idx]['content'] = self.messages[msg_idx]['content'].replace(
                        old_content, 
                        new_content + "\n[Note: Full content was compressed to summary to save context window space]"
                    )
                    
                    # Update tracking
                    info['mode'] = 'summary'
                    info['content'] = new_content
                    
                    tokens_saved = old_tokens - new_tokens
                    tokens_freed += tokens_saved
                    
                    print(f"[Context Manager] Compressed {file_path}: {old_tokens} → {new_tokens} tokens (saved {tokens_saved})")
        
        self.current_tokens -= tokens_freed
        return tokens_freed
    
    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count (rough approximation: 1 token ≈ 4 chars)."""
        return len(text) // 4
```

## Level 2: Hard Compaction (65-80% Full)

**Trigger:** Context window reaches 65% capacity

**Strategy:** Summarize older conversation messages while preserving recent context

### What Happens

Messages older than 5 exchanges ago are summarized into a condensed format that preserves key information but reduces verbosity.

**Example:**
```
Original (Message 1-3):
User: "How does the authentication system work?"
Assistant: [500 words explaining authentication with code examples]
User: "What about password hashing?"
Assistant: [400 words explaining hashing with implementation details]
User: "Can you show me the validation logic?"
Assistant: [600 words with code snippets]

After Hard Compaction:
[Summary of messages 1-3]
Topics covered: authentication flow, password hashing (bcrypt), validation logic
Key points: 
- Authentication uses JWT tokens with 1-hour expiration
- Passwords hashed with bcrypt (cost=12)
- Validation checks: email format, password strength (8+ chars, mixed case)
Code references: user_manager.py:authenticate(), security.py:hash_password()

[Recent messages 4-6 remain in full]
```

### Implementation

```python
def hard_compact(self) -> int:
    """
    Level 2: Summarize old conversation messages.
    
    Returns:
        Number of tokens freed
    """
    tokens_freed = 0
    messages_to_keep_full = 5  # Keep last 5 exchanges in full
    
    # Calculate cutoff point
    cutoff_index = max(0, len(self.messages) - (messages_to_keep_full * 2))
    
    if cutoff_index < 2:
        return 0  # Not enough history to compact
    
    # Group old messages into conversation pairs
    old_messages = self.messages[:cutoff_index]
    
    # Generate summary using the model itself
    summary_prompt = self._create_summary_prompt(old_messages)
    summary = self._generate_summary(summary_prompt)
    
    # Calculate tokens saved
    old_tokens = sum(self._estimate_tokens(msg['content']) for msg in old_messages)
    new_tokens = self._estimate_tokens(summary)
    tokens_saved = old_tokens - new_tokens
    
    # Replace old messages with summary
    summary_message = {
        'role': 'system',
        'content': f"[Conversation Summary - Messages 1-{cutoff_index}]\n{summary}\n[End Summary]",
        'timestamp': old_messages[0]['timestamp'],
        'is_summary': True
    }
    
    self.messages = [summary_message] + self.messages[cutoff_index:]
    self.current_tokens -= tokens_saved
    tokens_freed += tokens_saved
    
    print(f"[Context Manager] Summarized {cutoff_index} messages: {old_tokens} → {new_tokens} tokens (saved {tokens_saved})")
    
    return tokens_freed

def _create_summary_prompt(self, messages: List[Dict]) -> str:
    """Create a prompt for summarizing conversation history."""
    conversation = "\n\n".join([
        f"{msg['role'].upper()}: {msg['content']}"
        for msg in messages
    ])
    
    return f"""Summarize the following conversation, preserving:
1. Main topics discussed
2. Key technical details and decisions
3. Code references (file names, function names, line numbers)
4. Important conclusions or action items

Be concise but don't lose critical information.

CONVERSATION:
{conversation}

SUMMARY:"""

def _generate_summary(self, prompt: str) -> str:
    """Generate summary using Ollama."""
    import ollama
    
    response = ollama.generate(
        model=self.model_name,
        prompt=prompt,
        options={
            'temperature': 0.3,  # Low temperature for factual summary
            'max_tokens': 500    # Limit summary length
        }
    )
    
    return response['response']
```

## Level 3: Emergency Compaction (>80% Full)

**Trigger:** Context window reaches 80% capacity

**Strategy:** Aggressive pruning with intelligent preservation of critical context

### What Happens

1. **Compress all file content** to summaries (even recently used files)
2. **Summarize all but the last 2 exchanges**
3. **Remove redundant information** (duplicate file references, repeated explanations)
4. **Preserve critical context** (user's original goal, key decisions)

**Example:**
```
Before Emergency Compaction (14,500 tokens):
- System prompt: 200 tokens
- Conversation summary (messages 1-10): 3,000 tokens
- Messages 11-15 (full): 6,000 tokens
- File content (3 files, full): 5,000 tokens
- Current message: 300 tokens

After Emergency Compaction (4,800 tokens):
- System prompt: 200 tokens
- Ultra-compressed summary (messages 1-13): 1,000 tokens
- Last 2 exchanges (messages 14-15): 2,000 tokens
- File content (3 files, summaries): 600 tokens
- Current message: 300 tokens
- Emergency notice: 100 tokens

Tokens freed: 9,700 (67% reduction)
```

### Implementation

```python
def emergency_compact(self) -> int:
    """
    Level 3: Aggressive compaction to prevent overflow.
    
    Returns:
        Number of tokens freed
    """
    tokens_freed = 0
    
    # Step 1: Compress ALL file content to summaries
    for file_path, info in self.file_references.items():
        if info['mode'] == 'full':
            old_tokens = self._estimate_tokens(info['content'])
            
            chunker = FileChunker()
            summary = chunker.summarize_python(info['content'], file_path)
            new_content = chunker.format_summary(summary)
            new_tokens = self._estimate_tokens(new_content)
            
            # Update message
            msg_idx = info['message_index']
            self.messages[msg_idx]['content'] = self.messages[msg_idx]['content'].replace(
                info['content'],
                new_content
            )
            
            info['mode'] = 'summary'
            info['content'] = new_content
            tokens_freed += (old_tokens - new_tokens)
    
    # Step 2: Ultra-compress conversation history
    # Keep only last 2 exchanges (4 messages) in full
    messages_to_keep = 4
    cutoff = max(0, len(self.messages) - messages_to_keep)
    
    if cutoff > 0:
        old_messages = self.messages[:cutoff]
        old_tokens = sum(self._estimate_tokens(msg['content']) for msg in old_messages)
        
        # Generate ultra-compressed summary
        summary = self._generate_ultra_compressed_summary(old_messages)
        new_tokens = self._estimate_tokens(summary)
        
        summary_message = {
            'role': 'system',
            'content': f"[COMPRESSED HISTORY]\n{summary}\n[END COMPRESSED HISTORY]",
            'timestamp': old_messages[0]['timestamp'],
            'is_summary': True
        }
        
        self.messages = [summary_message] + self.messages[cutoff:]
        tokens_freed += (old_tokens - new_tokens)
    
    # Step 3: Add emergency notice
    emergency_notice = {
        'role': 'system',
        'content': "[NOTICE: Context window reached 90% capacity. Older messages and file content have been compressed. Use :full to re-fetch complete file content if needed.]",
        'timestamp': self._current_timestamp(),
        'is_notice': True
    }
    self.messages.insert(-1, emergency_notice)  # Insert before current message
    
    self.current_tokens -= tokens_freed
    
    print(f"[Context Manager] EMERGENCY COMPACTION: Freed {tokens_freed} tokens")
    print(f"[Context Manager] New usage: {self.current_tokens}/{self.max_tokens} ({100*self.current_tokens/self.max_tokens:.1f}%)")
    
    return tokens_freed

def _generate_ultra_compressed_summary(self, messages: List[Dict]) -> str:
    """Generate ultra-compressed summary for emergency compaction."""
    conversation = "\n".join([
        f"{msg['role']}: {msg['content'][:200]}..."  # Truncate each message
        for msg in messages
    ])
    
    prompt = f"""Create an EXTREMELY concise summary (max 200 words) of this conversation:
- What is the user trying to accomplish?
- What files/code are being discussed?
- What are the key technical points?

{conversation}

ULTRA-COMPRESSED SUMMARY:"""
    
    return self._generate_summary(prompt)
```

## Automatic Trigger System

The context manager automatically checks and applies compaction after every message:

```python
def add_message(self, role: str, content: str) -> None:
    """Add a message and automatically compact if needed."""
    # Add the new message
    message = {
        'role': role,
        'content': content,
        'timestamp': self._current_timestamp(),
        'tokens': self._estimate_tokens(content)
    }
    self.messages.append(message)
    self.current_tokens += message['tokens']
    
    # Check if compaction is needed
    level = self.check_compaction_needed()
    
    if level == 1:
        print("[Context Manager] Soft compaction triggered (50% full)")
        freed = self.soft_compact()
        print(f"[Context Manager] Freed {freed} tokens")

    elif level == 2:
        print("[Context Manager] Hard compaction triggered (65% full)")
        freed = self.hard_compact()
        print(f"[Context Manager] Freed {freed} tokens")

    elif level == 3:
        print("[Context Manager] EMERGENCY compaction triggered (80% full)")
        freed = self.emergency_compact()
        print(f"[Context Manager] Freed {freed} tokens")
        
        # If still over 95% after emergency compaction, warn user
        if self.current_tokens / self.max_tokens > 0.95:
            print("[Context Manager] WARNING: Context window still critically full after emergency compaction")
            print("[Context Manager] Consider starting a new session or reducing file references")
```

## User-Facing Features

### Transparency

Users should be informed when compaction happens:

```
[Context Manager] Your context window is 65% full. Compressing older file content to summaries...
[Context Manager] Compressed user_manager.py (45KB → 2KB). Use @./user_manager.py:full to restore.
```

### Manual Control

Add CLI flags for users to control compaction:

```bash
# Disable automatic compaction
ollama-prompt --prompt "..." --no-auto-compact

# Force compaction now
ollama-prompt --prompt "..." --compact-now

# Set custom thresholds
ollama-prompt --prompt "..." --compact-threshold 70

# View current context usage
ollama-prompt --session-info abc123
# Output:
# Session: abc123
# Context usage: 8,500 / 16,000 tokens (53%)
# Messages: 12 (2 summarized)
# Files referenced: 5 (3 compressed)
```

## Storage Strategy

Store compaction metadata in the session database:

```sql
-- Add to sessions table
ALTER TABLE sessions ADD COLUMN compaction_level INTEGER DEFAULT 0;
ALTER TABLE sessions ADD COLUMN tokens_used INTEGER DEFAULT 0;
ALTER TABLE sessions ADD COLUMN tokens_freed INTEGER DEFAULT 0;
ALTER TABLE sessions ADD COLUMN last_compaction TEXT;

-- New table for compaction history
CREATE TABLE compaction_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    level INTEGER NOT NULL,
    tokens_before INTEGER NOT NULL,
    tokens_after INTEGER NOT NULL,
    tokens_freed INTEGER NOT NULL,
    actions TEXT NOT NULL,  -- JSON array of actions taken
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);
```

## Integration with Existing Code

Modify `session_manager.py` to use the new ContextManager:

```python
class SessionManager:
    def __init__(self, db_path: Optional[str] = None):
        self.db = SessionDatabase(db_path)
        self.context_manager = ContextManager(max_tokens=16000)
    
    def prepare_prompt(self, session: Dict, new_prompt: str) -> str:
        """Prepare prompt with context, applying compaction if needed."""
        # Load session history into context manager
        self.context_manager.load_session(session)
        
        # Add new prompt
        self.context_manager.add_message('user', new_prompt)
        
        # Build final prompt from managed context
        final_prompt = self.context_manager.build_prompt()
        
        return final_prompt
    
    def save_response(self, session_id: str, response: str) -> None:
        """Save model response and update context."""
        self.context_manager.add_message('assistant', response)
        
        # Save updated context to database
        self.db.update_session(
            session_id,
            context=self.context_manager.serialize(),
            tokens_used=self.context_manager.current_tokens
        )
```

## Expected Results

| Metric | Without Compaction | With Compaction |
|--------|-------------------|-----------------|
| **Max conversation length** | 10-15 messages | 50-100+ messages |
| **Files per session** | 2-3 | 10-20 |
| **Context overflow errors** | Frequent | Rare |
| **Information retention** | 100% until overflow | 85-90% continuously |
| **User intervention needed** | High | Minimal |

## Monitoring and Tuning

Add telemetry to track compaction effectiveness:

```python
class CompactionMetrics:
    """Track compaction performance."""
    
    def __init__(self):
        self.total_compactions = 0
        self.tokens_freed = 0
        self.compaction_by_level = {1: 0, 2: 0, 3: 0}
        self.avg_time_between_compactions = []
    
    def record_compaction(self, level: int, tokens_freed: int, duration: float):
        """Record a compaction event."""
        self.total_compactions += 1
        self.tokens_freed += tokens_freed
        self.compaction_by_level[level] += 1
        
        # Log for analysis
        print(f"[Metrics] Level {level} compaction: {tokens_freed} tokens in {duration:.2f}s")
    
    def report(self) -> str:
        """Generate metrics report."""
        return f"""
Compaction Metrics:
- Total compactions: {self.total_compactions}
- Total tokens freed: {self.tokens_freed:,}
- Level 1 (soft): {self.compaction_by_level[1]}
- Level 2 (hard): {self.compaction_by_level[2]}
- Level 3 (emergency): {self.compaction_by_level[3]}
- Avg tokens per compaction: {self.tokens_freed / max(1, self.total_compactions):.0f}
"""
```

## Next Steps

1. **Implement Level 1 (Soft Compaction)** first - highest ROI, lowest risk
2. **Test with real conversations** - measure token savings and information loss
3. **Add user feedback mechanism** - let users report when compaction loses important context
4. **Tune thresholds** - adjust 50/65/80% triggers based on actual usage
5. **Implement Levels 2 and 3** once Level 1 proves stable

Would you like me to implement the ContextManager class with Level 1 compaction for you?
