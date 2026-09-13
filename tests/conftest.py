"""CI must be deterministic and must never spend live-model tokens."""
import os
os.environ.setdefault("RESOLVEAI_OFFLINE_TEST", "1")
