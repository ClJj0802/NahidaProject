# Nahida Memory System & Database Design

> Status: Design Draft  
> Target: Nahida Brain  
> Goal: Build a long-term companion memory system that preserves context, relationships, events, goals, emotions, and important life experiences without overloading the LLM context.

---

# 1. Design Goals

Nahida's memory system should not be a simple vector database that stores every conversation and retrieves semantically similar text.

The system should behave more like a structured cognitive memory system.

Main goals:

- Remember important user facts permanently.
- Remember future events until they happen.
- Keep recent daily-life details for a limited time.
- Understand current conversation references such as "她", "那个人", "刚刚那个".
- Keep people and relationships separated.
- Track current goals and unfinished tasks.
- Preserve important life experiences after events are completed.
- Keep short-lived emotional states without turning them into permanent facts.
- Avoid permanently storing incorrect AI assumptions.
- Allow memory to evolve when facts or relationships change.
- Retrieve only relevant memories instead of loading the entire database into the prompt.

---

# 2. Overall Memory Architecture

Nahida's memory system is divided into four groups:

```text
MEMORY SYSTEM

Runtime Memory
├── Perception Buffer
├── Active Context
└── Session Memory

Persistent Memory
├── Short-term Episodic Memory
├── Event Memory
├── Goal Memory
├── Social / Relationship Memory
├── Preference / Habit Memory
├── Autobiographical Memory
└── Fixed / Semantic Memory

Dynamic State
├── Emotional State
└── Narrative State

Memory Infrastructure
└── Meta Memory / Memory Index
```

The system is not only ordered from short-term to long-term.

There are two main dimensions:

```text
Time dimension:
seconds → minutes → hours → days → months → permanent

Meaning dimension:
person / event / emotion / preference / goal / fact / experience / habit
```

---

# 3. Memory Layers

## 3.1 Perception Buffer

### Purpose

Stores raw, very recent sensory information.

Examples:

- Mouse pressed near Nahida's head.
- User moved the mouse while holding the button.
- User spoke.
- Screen content changed.
- User clicked a window.
- A new image appeared.

### Lifetime

```text
seconds → several minutes
```

### Storage

Usually memory-only.

Do not store raw perception data permanently unless it becomes meaningful.

Example:

```text
15:20:03 mouse_down near head
15:20:04 mouse_move near head
15:20:05 mouse_move near head
15:20:06 mouse_up
```

Can be compressed into:

```text
User petted Nahida's head for about 3 seconds.
```

Then it may be moved into Active Context.

---

# 4. Active Context

### Purpose

Tracks what the current conversation is about.

It is especially important for resolving references.

Examples:

```text
她
他
那个人
刚刚那个同事
之前说的项目
那个女生
```

### Lifetime

```text
minutes → hours
```

### Example

```json
{
  "current_topic": "workplace coworker conflict",
  "last_entity": "coworker_A",
  "entities": {
    "coworker_A": {
      "role": "coworker",
      "relationship": "difficult",
      "description": "coworker who often suspects the user's intentions"
    },
    "coworker_B": {
      "role": "coworker",
      "relationship": "good",
      "description": "coworker the user enjoys working with"
    }
  }
}
```

If the user says:

```text
现在领导又叫我跟她合作。
```

Active Context should resolve:

```text
她 = coworker_A
```

before memory retrieval or LLM generation.

---

# 5. Session Memory

### Purpose

Maintains the overall summary of the current conversation session.

It prevents the LLM from repeatedly reconstructing the conversation from many small memories.

### Lifetime

```text
hours → one session → about one day
```

### Example

```text
The user explained that coworker A frequently distrusts their intentions.
The user initially wondered whether the collaboration problem was their own fault.
After working with coworker B, the user realized collaboration could be smooth and enjoyable.
A new project now requires the user to work with coworker A again.
The user is worried that the previous problems will return.
```

### End of Session

At session end:

```text
Session Memory
      ↓
Memory Consolidation
      ↓
Short-term Episodic Memory
```

---

# 6. Short-term Episodic Memory

### Purpose

Stores recent detailed experiences.

This memory is intentionally detailed.

Examples:

- Ate nasi lemak this morning.
- Was unhappy at work today.
- Drank Mixue today.
- Bought a favorite plush toy.
- Plans to play Apex later tonight.
- Had an argument with a coworker today.

### Lifetime

Typical TTL:

```text
1 day
3 days
7 days
30 days
```

### Example Record

```json
{
  "memory_type": "short_term_episode",
  "content": "User is worried because a new project requires working with coworker A again.",
  "entities": ["coworker_A"],
  "emotion": "frustrated",
  "importance": 0.65,
  "created_at": "2026-09-05T15:02:00+08:00",
  "expires_at": "2026-09-12T15:02:00+08:00"
}
```

### Important Rule

Short-term memory should not be summarized too aggressively.

Bad:

```text
User had trouble at work.
```

Better:

```text
User previously had difficulty working with coworker A because she often suspected the user's intentions. After working with coworker B, the user realized collaboration could be pleasant. A new project now requires working with coworker A again.
```

---

# 7. Emotional State

### Purpose

Tracks temporary emotional condition.

Examples:

```text
happy
sad
frustrated
worried
excited
tired
lonely
angry
```

### Lifetime

```text
minutes → hours → several days
```

Emotional State should decay over time.

Example:

```text
frustration = 0.80
after 4 hours = 0.50
next day = 0.20
later = expired
```

### Important Rule

Do not turn temporary emotions into permanent facts.

Bad:

```text
User is a sad person.
```

Good:

```text
User was frustrated today because of a workplace issue.
```

The emotion state can expire while the experience remains in Episodic Memory.

---

# 8. Event Memory

### Purpose

Stores time-based events.

Examples:

- Next week attending Comic Fiesta.
- Company team building.
- Going home next week.
- Camping on September 12.
- Traveling to Japan next year.
- Friend's birthday.
- Deadline.

### Lifetime

```text
until event is completed, cancelled, or archived
```

### Event Status

```text
UPCOMING
ONGOING
COMPLETED
CANCELLED
```

### Event Types

```text
EVENT
APPOINTMENT
TRAVEL
DEADLINE
COMMITMENT
ANNIVERSARY
BIRTHDAY
HOLIDAY
```

### Example

```json
{
  "title": "Camping trip",
  "event_type": "TRAVEL",
  "start_time": "2026-09-12T08:00:00+08:00",
  "end_time": "2026-09-13T18:00:00+08:00",
  "status": "UPCOMING",
  "importance": 0.80
}
```

### Event Lifecycle

```text
UPCOMING
   ↓
ONGOING
   ↓
COMPLETED
   ↓
important?
├── no → archive
└── yes → Autobiographical Memory
```

---

# 9. Goal / Task Memory

### Purpose

Stores things the user is trying to accomplish.

Unlike Event Memory, Goal Memory does not require a fixed date.

Examples:

- Planning to resign.
- Looking for a new job.
- Improving Nahida TTS latency.
- Building image understanding.
- Completing a university application.
- Learning a new technology.

### Status

```text
PLANNING
ACTIVE
BLOCKED
PAUSED
COMPLETED
ABANDONED
```

### Example

```json
{
  "title": "Improve Nahida memory system",
  "status": "ACTIVE",
  "progress": 0.35,
  "subgoals": [
    "redesign memory layers",
    "add structured people memory",
    "implement memory consolidation"
  ]
}
```

### Event vs Goal

```text
Event Memory
focus = WHEN?

Goal Memory
focus = PROGRESS?
```

Example:

```text
September 12 camping trip
→ Event

Find a new job
→ Goal
```

---

# 10. Social / Relationship Memory

### Purpose

Stores information about people and relationships.

This memory should be structured and entity-based instead of plain text only.

Examples:

- Friends.
- Coworkers.
- Family.
- Partner.
- Manager.
- Club members.
- Former coworkers.

### Example Entity

```json
{
  "person_id": "coworker_A",
  "display_name": null,
  "role": "coworker",
  "relationship_type": "coworker",
  "relationship_quality": -0.65,
  "facts": [
    "often suspects the user's intentions",
    "previous collaboration was frustrating"
  ]
}
```

Another person:

```json
{
  "person_id": "coworker_B",
  "display_name": null,
  "role": "coworker",
  "relationship_type": "coworker",
  "relationship_quality": 0.72,
  "facts": [
    "user enjoys working with her",
    "collaboration is smooth"
  ]
}
```

This prevents:

```text
coworker_A == coworker_B
```

from being accidentally mixed by semantic retrieval.

---

# 11. Preference / Habit Memory

## Preference

Stores likes, dislikes, and personal tendencies.

Examples:

- Likes matcha.
- Likes Japanese food.
- Prefers cmd.
- Dislikes a certain food.
- Likes traveling to Thailand.

Example:

```json
{
  "subject": "matcha",
  "preference_type": "LIKE",
  "strength": 0.92,
  "confidence": 0.95
}
```

## Habit

Stores repeated behavior.

Examples:

- Often plays Apex at night.
- Usually drinks coffee in the morning.
- Frequently works on Nahida Project after work.

Habit memory should require repeated evidence.

One-time behavior:

```text
User drank milk tea today.
```

should not immediately become:

```text
User often drinks milk tea.
```

---

# 12. Autobiographical Memory

### Purpose

Stores important life experiences.

Examples:

- First trip to Japan.
- First Comic Fiesta.
- Graduation.
- Changing company.
- Adopting a pet.
- Starting or ending an important relationship.
- Important personal achievements.

### Difference from Fixed Memory

Fixed Memory:

```text
User has a cat named Momo.
```

Autobiographical Memory:

```text
User adopted Momo in September 2026.
```

One stores a fact.

The other stores an experience.

### Promotion Source

Important completed events should be promoted:

```text
Event Memory
    ↓
COMPLETED
    ↓
high importance
    ↓
Autobiographical Memory
```

---

# 13. Fixed / Semantic Memory

### Purpose

Stores stable facts about the user's world.

Examples:

- Birthday.
- Occupation.
- Current company.
- Pet name.
- Important people.
- Membership in a club.
- Important anniversaries.
- Permanent preferences.
- Major current life state.

### Lifetime

```text
permanent until updated or explicitly removed
```

### Two Classes

```text
Fixed Memory
├── Core Memory
└── Retrieved Fixed Memory
```

## Core Memory

Loaded into the prompt when the model starts.

Only high-value and frequently useful information should be included.

Example:

```text
- User is a programmer.
- User is currently planning to resign.
- User likes matcha.
- User is building the Nahida Project.
```

## Retrieved Fixed Memory

Stored permanently but loaded only when relevant.

Example:

```text
Alice's birthday is March 14.
```

This does not need to be present in every LLM request.

---

# 14. Narrative State

### Purpose

Tracks how an ongoing story or situation has developed.

This is useful because real-life situations are usually not independent facts.

Examples:

- Workplace conflict.
- Job resignation.
- University application.
- Relationship development.
- Nahida Project development.

### Example

```text
Narrative: Difficult coworker

1. User collaborated with coworker A.
2. Coworker A repeatedly distrusted the user's intentions.
3. User wondered whether the issue was their own fault.
4. User later worked with coworker B.
5. Collaboration with coworker B was smooth and enjoyable.
6. User realized the previous difficulty was probably specific to coworker A.
7. A new project now requires collaboration with coworker A again.
8. User is currently worried the previous problem will return.
```

### Benefit

Narrative State preserves causality.

It helps the LLM understand:

```text
what happened before
why the user feels this way
what changed
what the current situation is
```

---

# 15. Meta Memory

### Purpose

Stores metadata about memories.

The model should know whether a memory is:

- Explicitly stated by the user.
- Inferred by the AI.
- Old.
- Replaced by newer information.
- Contradictory.
- Low confidence.
- Recently confirmed.

### Example

```json
{
  "memory_id": 813,
  "confidence": 0.95,
  "source": "USER_EXPLICIT",
  "created_at": "2026-09-05T15:00:00+08:00",
  "last_confirmed_at": "2026-09-05T15:00:00+08:00",
  "superseded_by": null
}
```

### Suggested Confidence

```text
USER_EXPLICIT      1.00
STRONG_INFERENCE   0.70
WEAK_INFERENCE     0.40
MODEL_GUESS        0.20
```

Model guesses should generally not be promoted into permanent memory.

---

# 16. Memory Processing Pipeline

Recommended message flow:

```text
User Input
    │
    ▼
Perception / STT
    │
    ▼
Temporal Analyzer
    │
    ▼
Entity Resolver
    │
    ▼
Active Context Update
    │
    ▼
Memory Retrieval
    │
    ├── Session Memory
    ├── Short-term Episodic
    ├── Event Memory
    ├── Goal Memory
    ├── Social Memory
    ├── Preference Memory
    ├── Autobiographical Memory
    └── Fixed Memory
    │
    ▼
Narrative + Emotion State
    │
    ▼
Prompt Builder
    │
    ▼
LLM
    │
    ▼
Response
    │
    ▼
Memory Analyzer
    │
    ├── ADD
    ├── UPDATE
    ├── DELETE
    ├── PROMOTE
    ├── MERGE
    └── IGNORE
```

---

# 17. Memory Classifier Output

The Memory Analyzer should support multiple memories from one message.

Example input:

```text
我刚交了女朋友，她叫 Alice。
```

Suggested analyzer output:

```json
{
  "memories": [
    {
      "action": "ADD",
      "memory_type": "social",
      "entity": "Alice",
      "relationship": "girlfriend",
      "confidence": 1.0
    },
    {
      "action": "ADD",
      "memory_type": "fixed",
      "content": "Alice is the user's girlfriend.",
      "importance": 0.95,
      "confidence": 1.0
    },
    {
      "action": "ADD",
      "memory_type": "short_term_episode",
      "content": "User recently started dating Alice.",
      "importance": 0.80,
      "ttl_days": 7
    }
  ]
}
```

One message may create several different memory records.

---

# 18. Memory Promotion

Memory should be able to move between layers.

Example:

```text
Short-term Memory
       ↓ repeated / important
Preference / Habit Memory
```

Example:

```text
Event Memory
       ↓ completed + important
Autobiographical Memory
```

Example:

```text
Short-term Episode
       ↓ repeated relevance
Narrative State
```

Example:

```text
Repeated user statement
       ↓ stable fact
Fixed Memory
```

---

# 19. Purge Rules

Short-term memory should expire automatically.

Recommended strength mapping:

```text
TRIVIAL         1 day
NORMAL          3 days
IMPORTANT       7 days
VERY_IMPORTANT  30 days
```

Example:

```text
Drank Mixue today
→ NORMAL
→ 3 days

Upset about a major workplace conflict
→ IMPORTANT
→ 7 days

Bought a highly meaningful limited collectible
→ VERY_IMPORTANT
→ 30 days
```

Before deleting an important memory:

```text
Should this memory be promoted?
```

Possible destinations:

```text
Preference Memory
Social Memory
Autobiographical Memory
Fixed Memory
Narrative State
```

---

# 20. Memory Consolidation

Recommended to run at session end or daily summary.

Example raw memories:

```text
812 coworker A is suspicious
813 coworker B is pleasant to work with
814 new project requires coworker A
815 user feels worried
```

Consolidated memory:

```text
User has a difficult working relationship with coworker A, who often suspects the user's intentions. The user enjoys working with coworker B. A newly assigned project requires the user to work with coworker A again, causing concern.
```

Raw memories may remain temporarily.

Example:

```text
Raw Short-term Memory
TTL = 7 days

Consolidated Episode
TTL = 30 days
```

---

# 21. Retrieval Strategy

Do not use vector similarity alone.

Recommended ranking:

```text
retrieval_score =
    semantic_similarity
  + entity_match
  + temporal_relevance
  + recency
  + importance
  + confidence
  + current_topic_match
  + narrative_relevance
  + relationship_relevance
```

Entity matching should have strong weight when the conversation contains:

```text
她
他
那个人
之前那个同事
我朋友
我领导
```

---

# 22. Suggested Database Architecture

Recommended database:

```text
SQLite initially

Future:
PostgreSQL if multi-user / network service is needed
```

SQLite is suitable for the current Nahida Brain architecture because:

- Local application.
- Single user.
- Easy backup.
- Easy migration.
- Supports transactions.
- No extra service required.
- Enough performance for thousands or tens of thousands of memories.

Vector embeddings can be stored separately or added later using a vector index.

---

# 23. Database Tables

Recommended structure:

```text
nahida_memory.db

├── memories
├── people
├── relationships
├── events
├── goals
├── preferences
├── narratives
├── emotion_states
├── sessions
├── session_memories
├── memory_entities
├── memory_links
└── memory_access_log
```

---

# 24. `memories` Table

Main general-purpose memory table.

```sql
CREATE TABLE memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    memory_type TEXT NOT NULL,
    content TEXT NOT NULL,

    importance REAL DEFAULT 0.5,
    confidence REAL DEFAULT 1.0,

    source TEXT DEFAULT 'USER_EXPLICIT',

    created_at TEXT NOT NULL,
    updated_at TEXT,
    last_confirmed_at TEXT,
    last_accessed_at TEXT,

    valid_from TEXT,
    valid_until TEXT,
    expires_at TEXT,

    status TEXT DEFAULT 'ACTIVE',

    is_core INTEGER DEFAULT 0,
    is_archived INTEGER DEFAULT 0,

    superseded_by INTEGER,

    FOREIGN KEY (superseded_by) REFERENCES memories(id)
);
```

Suggested `memory_type` values:

```text
SHORT_TERM_EPISODE
AUTOBIOGRAPHICAL
FIXED
SEMANTIC
```

---

# 25. `people` Table

```sql
CREATE TABLE people (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    entity_key TEXT UNIQUE NOT NULL,
    display_name TEXT,
    nickname TEXT,

    role TEXT,

    description TEXT,

    created_at TEXT NOT NULL,
    updated_at TEXT
);
```

Example:

```text
entity_key = coworker_A
display_name = NULL
role = coworker
```

If the real name is learned later:

```text
display_name = Alice
```

The same entity can continue to be used.

---

# 26. `relationships` Table

```sql
CREATE TABLE relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    person_id INTEGER NOT NULL,

    relationship_type TEXT,
    relationship_quality REAL DEFAULT 0.0,

    valid_from TEXT,
    valid_until TEXT,

    status TEXT DEFAULT 'ACTIVE',

    notes TEXT,

    created_at TEXT NOT NULL,
    updated_at TEXT,

    FOREIGN KEY (person_id) REFERENCES people(id)
);
```

Relationship examples:

```text
friend
close_friend
coworker
manager
girlfriend
boyfriend
partner
ex_partner
family
club_member
```

Relationships should support history instead of overwriting old relationships.

---

# 27. `events` Table

```sql
CREATE TABLE events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    title TEXT NOT NULL,
    description TEXT,

    event_type TEXT,

    start_time TEXT,
    end_time TEXT,

    status TEXT DEFAULT 'UPCOMING',

    importance REAL DEFAULT 0.5,
    confidence REAL DEFAULT 1.0,

    created_at TEXT NOT NULL,
    updated_at TEXT
);
```

Suggested event status:

```text
UPCOMING
ONGOING
COMPLETED
CANCELLED
```

---

# 28. `goals` Table

```sql
CREATE TABLE goals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    title TEXT NOT NULL,
    description TEXT,

    status TEXT DEFAULT 'PLANNING',
    progress REAL DEFAULT 0.0,

    priority REAL DEFAULT 0.5,

    created_at TEXT NOT NULL,
    updated_at TEXT,
    completed_at TEXT
);
```

Suggested status:

```text
PLANNING
ACTIVE
BLOCKED
PAUSED
COMPLETED
ABANDONED
```

---

# 29. `preferences` Table

```sql
CREATE TABLE preferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    subject TEXT NOT NULL,
    preference_type TEXT NOT NULL,

    strength REAL DEFAULT 0.5,
    confidence REAL DEFAULT 1.0,

    evidence_count INTEGER DEFAULT 1,

    created_at TEXT NOT NULL,
    updated_at TEXT
);
```

Suggested types:

```text
LIKE
DISLIKE
PREFER
AVOID
HABIT
INTEREST
```

---

# 30. `narratives` Table

```sql
CREATE TABLE narratives (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    title TEXT NOT NULL,
    summary TEXT NOT NULL,

    status TEXT DEFAULT 'ACTIVE',

    importance REAL DEFAULT 0.5,

    created_at TEXT NOT NULL,
    updated_at TEXT,
    closed_at TEXT
);
```

Examples:

```text
Difficult coworker
Nahida Project
Job resignation
University application
Japan trip planning
```

---

# 31. `emotion_states` Table

Only current and recent emotional states need to be stored.

```sql
CREATE TABLE emotion_states (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    emotion TEXT NOT NULL,
    intensity REAL NOT NULL,

    cause TEXT,

    started_at TEXT NOT NULL,
    updated_at TEXT,
    expires_at TEXT,

    status TEXT DEFAULT 'ACTIVE'
);
```

---

# 32. `sessions` Table

```sql
CREATE TABLE sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    started_at TEXT NOT NULL,
    ended_at TEXT,

    summary TEXT,

    status TEXT DEFAULT 'ACTIVE'
);
```

---

# 33. `session_memories` Table

```sql
CREATE TABLE session_memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    session_id INTEGER NOT NULL,

    content TEXT NOT NULL,
    importance REAL DEFAULT 0.5,

    created_at TEXT NOT NULL,

    FOREIGN KEY (session_id) REFERENCES sessions(id)
);
```

---

# 34. `memory_entities` Table

Links memories with people or entities.

```sql
CREATE TABLE memory_entities (
    memory_id INTEGER NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id INTEGER NOT NULL,

    PRIMARY KEY (memory_id, entity_type, entity_id)
);
```

Example:

```text
memory 812
→ person coworker_A
```

---

# 35. `memory_links` Table

Allows memories to reference each other.

```sql
CREATE TABLE memory_links (
    source_memory_id INTEGER NOT NULL,
    target_memory_id INTEGER NOT NULL,

    relation_type TEXT NOT NULL,

    PRIMARY KEY (
        source_memory_id,
        target_memory_id,
        relation_type
    )
);
```

Suggested relations:

```text
RELATED_TO
CAUSE_OF
RESULT_OF
SUPERSEDES
PART_OF
PROMOTED_FROM
CONTRADICTS
CONFIRMS
```

This is important for building memory graphs later.

---

# 36. `memory_access_log` Table

Optional but useful for debugging retrieval.

```sql
CREATE TABLE memory_access_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    memory_id INTEGER NOT NULL,

    query TEXT,
    retrieval_score REAL,

    accessed_at TEXT NOT NULL
);
```

This can answer:

```text
Why did Nahida retrieve this memory?
Why did the wrong coworker appear?
Which memory was used for this response?
```

---

# 37. Active Context Storage

Active Context should not necessarily be stored in the main database.

Recommended:

```text
Runtime Python object
+
optional JSON checkpoint
```

Example:

```json
{
  "topic": "workplace coworker conflict",
  "last_entity": "coworker_A",
  "entities": {
    "coworker_A": {
      "person_id": 12
    },
    "coworker_B": {
      "person_id": 13
    }
  }
}
```

---

# 38. Core Memory Loading

At Nahida Brain startup:

```text
Load model
    ↓
Load Core Fixed Memories
    ↓
Load active goals
    ↓
Load upcoming important events
    ↓
Load recent narrative states
    ↓
Build system context
```

Do not load the entire database.

Recommended startup context:

```text
Core user facts
Active goals
Important upcoming events
Current major narratives
Important relationship identities
```

Everything else should be retrieved when needed.

---

# 39. Example: Workplace Coworker Conversation

User says:

```text
之前那个同事每次都怀疑我要害她。
```

System creates:

```text
Social Memory
coworker_A
relationship_quality = negative
fact = often suspects user's intentions
```

Also:

```text
Short-term Episode
previous collaboration with coworker_A was frustrating
```

Later user says:

```text
换了另外一个同事之后合作就很开心。
```

System creates:

```text
Social Memory
coworker_B
relationship_quality = positive
```

Later:

```text
领导现在又叫我跟她合作。
```

Processing:

```text
Active Context
她 → coworker_A

Social Memory
coworker_A → difficult relationship

Narrative
new project requires coworker_A again

Emotion
worried / frustrated
```

The LLM should therefore understand:

```text
The user is being asked to work with the difficult coworker again.
```

and should not confuse coworker_A with coworker_B.

---

# 40. Example: Future Trip

User:

```text
明年四月我要去日本。
```

Create:

```text
Event Memory
type = TRAVEL
date = 2027-04
status = UPCOMING
```

Before the trip:

```text
Event remains active.
```

During the trip:

```text
status = ONGOING
```

After the trip:

```text
status = COMPLETED
```

If user says:

```text
这是我第一次去日本，我真的非常开心。
```

Promote:

```text
Autobiographical Memory
User's first trip to Japan was in April 2027 and was an important happy experience.
```

---

# 41. Example: New Pet

User:

```text
我今天养了一只猫，叫 Momo。
```

Possible records:

```text
Fixed Memory
User has a cat named Momo.

Social / Entity Memory
Momo = user's pet.

Short-term Episode
User adopted Momo today.

Autobiographical Memory
User adopted Momo in September 2026.
```

One sentence can create multiple memory types.

---

# 42. Recommended Priority for Implementation

Do not build everything at once.

Recommended order:

## Phase 1

```text
Active Context
Session Memory
Short-term Episodic
Fixed Memory
Event Memory
```

## Phase 2

```text
Social / Relationship Memory
Goal Memory
Emotional State
```

## Phase 3

```text
Autobiographical Memory
Narrative State
Preference / Habit Memory
```

## Phase 4

```text
Meta Memory
Memory graph
Advanced retrieval ranking
Automatic consolidation
```

---

# 43. Recommended Runtime Pipeline

Target log format:

```text
[Temporal] Analyzing...
[Active Context] Updating...
[Session] Updating...
[Memory] Retrieving...
  Fixed: [...]
  Short-term: [...]
  Events: [...]
  Goals: [...]
  Social: [...]
  Narrative: [...]
[Emotion] Current: ...
[Nahida] Thinking...
[Memory] Writing...
```

This will also make debugging much easier.

---

# 44. Final Principle

The system should distinguish between:

```text
what the user is experiencing now
what recently happened
what is scheduled to happen
what the user is trying to achieve
who people are
how relationships work
what the user likes
what important life experiences happened
what stable facts are true
what the AI is only guessing
```

The final goal is not simply:

```text
retrieve similar conversation text
```

The final goal is:

```text
build and maintain a structured internal model
of the user's life, relationships, goals, events,
preferences, recent experiences, and important history.
```

That allows Nahida to behave less like a chatbot with a history log and more like a long-term companion that understands continuity over time.
