"""Fetch Bitext once and replace the compact offline cache used at runtime."""
from __future__ import annotations
from collections import defaultdict
import json
from pathlib import Path
from datasets import load_dataset
import pyarrow as pa
from pyarrow import ipc

CATEGORY_MAP={"ORDER":"cancellation","CANCEL":"cancellation","REFUND":"refund","SHIPPING":"address_change","DELIVERY":"shipment_issue","PAYMENT":"payment_issue","FEEDBACK":"escalation","CONTACT":"escalation","INVOICE":"info_request","ACCOUNT":"info_request","SUBSCRIPTION":"info_request"}
try:
    dataset=load_dataset("bitext/Bitext-customer-support-llm-chatbot-training-dataset",split="train")
except OSError:
    # Allows regenerating an already-downloaded cache in locked-down/offline CI.
    arrow=next((Path.home()/".cache/huggingface/datasets").glob("bitext___bitext-customer-support-llm-chatbot-training-dataset/**/*.arrow"))
    with pa.memory_map(str(arrow),"r") as source:dataset=ipc.open_stream(source).read_all().to_pylist()
cache=defaultdict(list)
for row in dataset:
    intent=CATEGORY_MAP.get(row["category"],"info_request")
    if len(cache[intent])<300:cache[intent].append(row["instruction"])
Path("services/bitext_intent_cache.json").write_text(json.dumps(cache,indent=2))
print({intent:len(items) for intent,items in cache.items()})
