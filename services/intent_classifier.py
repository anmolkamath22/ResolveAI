"""Offline TF-IDF intent hinting from the cached Bitext support utterances."""
from __future__ import annotations
from collections import Counter
from math import log,sqrt
import json,re
from pathlib import Path

_CACHE_PATH=Path(__file__).with_name("bitext_intent_cache.json")
def _terms(text: str)->list[str]:return re.findall(r"[a-z0-9]{2,}",text.lower())

class IntentClassifier:
    _shared: tuple[list[tuple[str,set[str]]],dict[str,float]]|None=None
    def __init__(self,cache_path: Path=_CACHE_PATH):
        if cache_path==_CACHE_PATH and self._shared:
            self.docs,self.idf=self._shared
        else:
            data=json.loads(cache_path.read_text());self.docs=[]
            for intent,utterances in data.items():self.docs.extend((intent,set(_terms(utterance))) for utterance in utterances)
            self.idf={term:log((1+len(self.docs))/(1+sum(term in terms for _,terms in self.docs)))+1 for _,terms in self.docs for term in terms}
            if cache_path==_CACHE_PATH:self.__class__._shared=(self.docs,self.idf)
        # ResolveAI-specific phrases supplement, rather than replace, Bitext's
        # broader support vocabulary (e.g. its PAYMENT category focuses on methods).
        self.anchors={"payment_issue":{"duplicate","twice","double","extra","charge","billed","transaction"},"shipment_issue":{"missing","lost","delayed","delivered","parcel","package"},"address_change":{"address","location","destination"},"refund":{"refund","reimbursement","money","return"},"cancellation":{"cancel","stop","cancellation"},"escalation":{"supervisor","complaint","claim"}}
    def classify(self,text: str,top_k: int=1)->list[dict[str,object]]:
        query=Counter(_terms(text))
        if not query:return []
        q_norm=sqrt(sum((count*self.idf.get(term,0))**2 for term,count in query.items())) or 1
        scores={}
        for intent,terms in self.docs:
            d_norm=sqrt(sum(self.idf.get(term,0)**2 for term in terms)) or 1
            score=sum(query[term]*(1 if term in terms else 0)*self.idf.get(term,0)**2 for term in query)/(q_norm*d_norm)
            scores[intent]=max(scores.get(intent,0.0),score)
        for intent,anchors in self.anchors.items():
            overlap=len(set(query)&anchors)
            if overlap:scores[intent]=scores.get(intent,0.0)+(0.24*overlap)
        ranked=sorted(scores.items(),key=lambda pair:pair[1],reverse=True)
        return [{"intent":intent,"score":round(score,4)} for intent,score in ranked[:top_k] if score>0]
