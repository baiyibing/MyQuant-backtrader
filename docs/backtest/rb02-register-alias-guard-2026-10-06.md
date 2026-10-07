# RB-02: register order and alias integrity

The tip inventory is healthy: 68 shared books and one minute-only book, with
zero token collisions or same-domain alias overwrites. Every book includes its
own canonical name in its aliases.

Previously, minute registration checked both domains, but shared registration
only rejected duplicate shared canonical names. Shared registration now rejects
names or aliases already claimed by either domain, identifying the token and
domain in the error. `_alias_map()` also rejects aliases mapping to different
shared books if the registry is mutated directly.

Display order remains insertion order, not alphabetical order. Existing names,
aliases and registration order are unchanged. `normalize_minute_strategy()`
preserves its minute-first preference for valid inputs; cross-domain collisions
are rejected at registration time. No simulation rules or outputs are changed.
