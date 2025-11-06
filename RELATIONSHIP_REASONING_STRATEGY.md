# Strategy: Improving Relationship Reasoning in Knowledge Graph

## Problem
When user asked "Who are my grandsons?", the system said there were none, even though the knowledge graph contained:
- James Weaver → parent → Kelli Jones
- Kelli Jones → parent → Levi Jones, Oliver Jones
- James Weaver → parent → Lori Hutchins
- Lori Hutchins → parent → Kaleb Hutchins

The system should have inferred that Levi, Oliver, and Kaleb are grandsons.

## Root Causes
1. **Missing Instructions**: System prompt didn't tell the LLM to reason about transitive relationships
2. **Truncated Context**: Only showing 10 relationships, missing critical parent-child links
3. **Poor Formatting**: Relationships weren't clearly marked as requiring inference

## Solution: Multi-Layered Approach

### 1. Enhanced System Prompt (constants.py)
Added explicit instructions at the TOP of SYSTEM_PROMPT:

```
KNOWLEDGE GRAPH REASONING: When answering questions about people, relationships,
or personal information, you have access to a Knowledge Graph Context below.

IMPORTANT - RELATIONSHIP INFERENCE: The knowledge graph shows direct relationships,
but you MUST reason about indirect relationships:
- Grandchildren = children of your children
- Siblings = people who share the same parents
- Cousins = children of your siblings
- In-laws = spouses of family members
- Always traverse the relationship graph to find indirect connections

EXAMPLE: If the knowledge graph shows:
- "James parent Kelli" AND "Kelli parent Levi"
- Then Levi is James's grandson (child of child = grandchild)
```

### 2. Improved Knowledge Graph Context (knowledge_graph_manager.py)

**Changes:**
- **Remove 10-relationship limit** → Show ALL relationships for complete reasoning
- **Add reasoning hint** → "NOTE: Use these relationships to infer indirect connections"
- **Use ALL entities for mapping** → Not just filtered ones

**Before:**
```
## Relationships
- Kelli Jones parent Levi Jones (family)
- Christian Jones parent Levi Jones (family)
... (only 10 shown)
```

**After:**
```
## Relationships
NOTE: Use these relationships to infer indirect connections (e.g., parent→child→grandchild)
- Kelli Jones spouse Christian Jones (family)
- Kelli Jones parent Levi Jones (family)
- Christian Jones parent Levi Jones (family)
- Kelli Jones parent Oliver Jones (family)
- Christian Jones parent Oliver Jones (family)
- Lori Hutchins spouse Marty Hutchins (family)
- Lori Hutchins parent Kaleb Hutchins (family)
- Marty Hutchins parent Kaleb Hutchins (family)
- Lori Hutchins parent Jillian Hutchins (family)
- Marty Hutchins parent Jillian Hutchins (family)
- Kelli Jones sibling Lori Hutchins (family)
- Levi Jones first cousin Jillian Hutchins (family)
- James Weaver parent Lori Hutchins (family)  ← CRITICAL
- James Weaver parent Kelli Jones (family)     ← CRITICAL
```

### 3. Reasoning Walkthrough Example

**Question:** "Who are my grandsons?"

**LLM Reasoning Process (with new strategy):**
1. See "RELATIONSHIP INFERENCE" instructions
2. Understand: grandsons = male children of my children
3. Look at relationships:
   - Find: "James Weaver parent Kelli Jones" → Kelli is my daughter
   - Find: "James Weaver parent Lori Hutchins" → Lori is my daughter
4. Find children of my daughters:
   - "Kelli Jones parent Levi Jones" → Levi is son of Kelli
   - "Kelli Jones parent Oliver Jones" → Oliver is son of Kelli
   - "Lori Hutchins parent Kaleb Hutchins" → Kaleb is son of Lori
5. Check entities to determine gender (all marked as "son")
6. Answer: "Levi Jones, Oliver Jones, and Kaleb Hutchins are your grandsons"

## Expected Improvements

### Before:
- ❌ "Who are my grandsons?" → "You don't have any grandsons"
- ✅ "Who are my children?" → "Kelli and Lori"
- ✅ "Who are their children?" → "Kelli has Levi and Oliver, Lori has Kaleb and Jillian"
- ✅ "Who are my grandsons?" (second time) → "Levi, Oliver, Kaleb"

### After:
- ✅ "Who are my grandsons?" (first time) → "Levi Jones, Oliver Jones, Kaleb Hutchins"
- ✅ Should work on first try without needing incremental questions
- ✅ Works for any transitive relationship (cousins, in-laws, etc.)

## Testing

To test the improvements:

1. **Clear conversation history** (start fresh session)
2. **Ask directly:** "Who are my grandsons?"
3. **Expected:** System should list all three grandsons immediately
4. **Try variations:**
   - "Who are my granddaughters?" → Should say Jillian Hutchins
   - "Are Levi and Kaleb related?" → Should say they're cousins
   - "Who is Christian Jones?" → Should say husband of Kelli (in-law)

## Files Modified

1. **constants.py** - Added relationship reasoning instructions to SYSTEM_PROMPT
2. **knowledge_graph_manager.py** - Removed relationship limit, added inference hint

## Notes

- This is a prompt engineering solution, not a code/algorithm solution
- Relies on the LLM's reasoning capabilities (Claude is very good at this)
- No changes to knowledge graph structure needed
- Works with existing relationships as-is
