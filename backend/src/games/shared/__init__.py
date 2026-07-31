"""Cross-game utilities.

Operative rule: this package holds **only pure, stateless functions that make no design decision
for any specific game** (`scoring.py`'s `exp_decay_score`, `picking.py`'s `pick_spread_asset`,
`serialization.py`'s `DictCodec`). No base class beyond `games/base.py`, no template-method
pattern, nothing that owns a game's flow. If a future game needs a different curve or picking
strategy, it copies a few lines here rather than adding a knob - duplication between games is
preferred over coupling them through a shared abstraction.
"""
