"""Safe customer-facing resolution report; deliberately excludes prompts and hidden reasoning."""
from __future__ import annotations
from models.schemas import ResolutionState

def resolution_report(state: ResolutionState) -> str:
    lines=[f"# ResolveAI Resolution Report", "", f"**Investigation:** {state.investigation_id}", f"**Case:** {state.case_id}", f"**Status:** {state.final_status}", "", "## Customer request", state.user_request, "", "## Resolution", state.final_summary or "No final resolution was produced.", "", "## Operational actions"]
    lines += [f"- **{event.action}** ({event.status}): {event.summary}" for event in state.action_history]
    if state.verification_results:
        lines += ["", "## Verification", "```json", str(state.verification_results[-1]), "```"]
    return "\n".join(lines)
