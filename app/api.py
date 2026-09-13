"""Stateless HTTP boundary for ResolveAI's persisted case investigations."""
from __future__ import annotations
import json
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from agent.graph import ResolutionAgent
from app.settings import settings
from services.enterprise import Enterprise
from storage.database import connect, ensure_database

app=FastAPI(title="ResolveAI",version="4.0")
app.add_middleware(CORSMiddleware,allow_origins=[origin.strip() for origin in settings.cors_origin.split(",")],allow_credentials=True,allow_methods=["GET","POST"],allow_headers=["X-ResolveAI-Key","Content-Type"])

class ResolveRequest(BaseModel):
    request: str
    customer_context: str | None = None
    investigation_id: str | None = None

def authorize(x_resolveai_key: str | None=Header(default=None)):
    if settings.api_key and x_resolveai_key != settings.api_key:
        raise HTTPException(status_code=401,detail="Invalid API key")

def resolve(case_id: str | None, body: ResolveRequest):
    ensure_database(settings.database_path)
    enterprise=Enterprise(settings.database_path)
    if case_id and body.customer_context:
        case=enterprise._one("SELECT customer_id FROM cases WHERE id=?",(case_id.upper(),))
        if case and case["customer_id"]!=body.customer_context:
            raise HTTPException(status_code=403,detail="Case does not belong to the supplied customer context")
    return ResolutionAgent(enterprise).run(case_id,body.request,customer_context=body.customer_context,investigation_id=body.investigation_id).model_dump()

@app.get("/healthz")
def healthz():
    try:
        ensure_database(settings.database_path); c=connect(settings.database_path);c.execute("SELECT 1").fetchone();c.close()
        return {"status":"ok","database":"reachable","llm":"configured-or-offline"}
    except Exception as exc:
        raise HTTPException(status_code=503,detail=f"Database unavailable: {type(exc).__name__}")

@app.post("/cases/{case_id}/resolve",dependencies=[Depends(authorize)])
def resolve_case(case_id: str,body: ResolveRequest): return resolve(case_id,body)

@app.post("/cases/{case_id}/resolve/stream",dependencies=[Depends(authorize)])
def resolve_case_stream(case_id: str,body: ResolveRequest):
    """SSE trace: each yielded state is an observable decision/action turn."""
    ensure_database(settings.database_path)
    enterprise=Enterprise(settings.database_path)
    if body.customer_context:
        case=enterprise._one("SELECT customer_id FROM cases WHERE id=?",(case_id.upper(),))
        if case and case["customer_id"]!=body.customer_context:raise HTTPException(status_code=403,detail="Case does not belong to the supplied customer context")
    def events():
        agent=ResolutionAgent(enterprise)
        for state in agent.run_streaming(case_id,body.request,customer_context=body.customer_context,investigation_id=body.investigation_id):
            latest=state.action_history[-1].model_dump() if state.action_history else None
            event_type="terminal" if state.final_status!="IN_PROGRESS" else "turn"
            payload={"type":event_type,"state":state.model_dump(),"event":latest}
            yield f"data: {json.dumps(payload,default=str)}\n\n"
    return StreamingResponse(events(),media_type="text/event-stream",headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})

@app.post("/cases/resolve",dependencies=[Depends(authorize)])
def resolve_new_case(body: ResolveRequest): return resolve(None,body)

@app.get("/cases/{case_id}",dependencies=[Depends(authorize)])
def get_case(case_id: str):
    ensure_database(settings.database_path);c=connect(settings.database_path);row=c.execute("SELECT * FROM cases WHERE id=?",(case_id.upper(),)).fetchone();c.close()
    if not row: raise HTTPException(status_code=404,detail="Case not found")
    return dict(row)
