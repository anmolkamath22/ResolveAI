"""Credential loading for local `.env`, environment variables, and Streamlit Secrets."""
from __future__ import annotations
import os
from pathlib import Path

def load_local_env() -> None:
    """Minimal dotenv loader; existing environment values always win and keys are never logged."""
    path=Path(__file__).resolve().parents[1] / ".env"
    if not path.exists(): return
    for line in path.read_text().splitlines():
        if "=" not in line or line.lstrip().startswith("#"): continue
        key,value=line.split("=",1);key=key.strip()
        if key: os.environ.setdefault(key,value.strip().strip('"').strip("'"))

def secret(name: str) -> str | None:
    load_local_env()
    value=os.getenv(name)
    if value: return value
    try:
        import streamlit as st
        value=st.secrets.get(name)
        return str(value) if value else None
    except Exception:
        return None
