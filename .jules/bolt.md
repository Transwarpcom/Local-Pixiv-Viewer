## 2025-05-23 - N+1 Query in XP Dashboard
**Learning:** `joinedload` (or eager loading in general) is critical for iterating over relationships in loops. Without it, accessing `item.work` inside a loop of history items triggers a separate SQL query for each item, leading to N+1 performance degradation.
**Action:** Always check for relationship access inside loops and use `options(joinedload(Relationship))` to pre-fetch related data in a single query (or few queries). Confirmed improvement from ~52 queries to 2 queries for 50 items.
