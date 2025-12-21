## 2025-05-23 - N+1 Query in XP Dashboard
**Learning:** `joinedload` (or eager loading in general) is critical for iterating over relationships in loops. Without it, accessing `item.work` inside a loop of history items triggers a separate SQL query for each item, leading to N+1 performance degradation.
**Action:** Always check for relationship access inside loops and use `options(joinedload(Relationship))` to pre-fetch related data in a single query (or few queries). Confirmed improvement from ~52 queries to 2 queries for 50 items.

## 2025-05-24 - N+1 Query with Dynamic Relationships (Slideshow)
**Learning:** `joinedload` does not work with relationships configured as `lazy='dynamic'` because they return a query object, not a list. To optimize iteration over dynamic relationships (like getting the first image for many works), you must use manual batch fetching (e.g., `IN` clause queries) instead of SQLAlchemy's eager loaders.
**Action:** When optimizing N+1 queries for `lazy='dynamic'` relationships, fetch the related data in a separate batch query using `filter(Model.fk.in_(ids))` and map it back in Python. Reduced queries from 101 to 2 in slideshow data.
