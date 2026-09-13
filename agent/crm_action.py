"""
CRM skill (HubSpot): every application becomes a Deal in a real CRM.

  Company = the employer (found by name, or created)
  Contact = the candidate, from the resume's name + email (found by email, or created)
  Deal    = this application, associated with both. Its stage tracks progress:
            drafted -> sent -> replied, and closed-lost when the run is undone.

This is what makes the agent team-ready: a career coach or staffing agency sees
every candidate's applications in the CRM they already run their pipeline in.

Setup: a free HubSpot account + private app token (HUBSPOT_TOKEN) with scopes
crm.objects.companies.read/write, crm.objects.contacts.read/write,
crm.objects.deals.read/write. Stage IDs default to HubSpot's built-in sales
pipeline; rename the labels in HubSpot or override the IDs with
HUBSPOT_STAGE_DRAFTED / _SENT / _REPLIED / _UNDONE. Without a token, deals go to
eval/logs/crm_mock.json.
"""
import json
import os
import re
import uuid
from datetime import date

import requests

from agent import composio_client as composio
from agent.utils import InjectedFault, maybe_fail, retry_with_backoff

_API = "https://api.hubapi.com"
_MOCK_JSON = os.path.join("eval", "logs", "crm_mock.json")
_TIMEOUT_SECONDS = 15
_STAGE_DEFAULTS = {
    "drafted": "appointmentscheduled",
    "sent": "qualifiedtobuy",
    "replied": "presentationscheduled",
    "undone": "closedlost",
}
_DEAL_TO_CONTACT, _DEAL_TO_COMPANY = 3, 5  # HubSpot-defined association type ids
_portal_id: str | None = None


def _token() -> str:
    return os.getenv("HUBSPOT_TOKEN", "").strip()


def is_live() -> bool:
    return bool(_token())


def _stage(name: str) -> str:
    return os.getenv(f"HUBSPOT_STAGE_{name.upper()}", "").strip() or _STAGE_DEFAULTS[name]


def _retryable(exc: Exception) -> bool:
    if isinstance(exc, InjectedFault):
        return True
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        return exc.response.status_code in (429, 500, 502, 503)
    return isinstance(exc, (requests.Timeout, requests.ConnectionError))


def _classify(exc: Exception) -> str:
    if isinstance(exc, InjectedFault):
        return f"service unavailable (HTTP {exc.status}, injected by chaos panel) — retried, then gave up"
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        code = exc.response.status_code
        if code == 401:
            return "HubSpot token invalid or expired"
        if code == 403:
            return "HubSpot token is missing a CRM scope (see README)"
        if code == 429:
            return "HubSpot rate limit, retries exhausted"
        return f"HubSpot API error (HTTP {code}): {exc.response.text[:160]}"
    return str(exc)


def _call(method: str, path: str, body: dict | None = None) -> dict:
    def go():
        resp = requests.request(method, _API + path, json=body, timeout=_TIMEOUT_SECONDS,
                                headers={"Authorization": f"Bearer {_token()}"})
        resp.raise_for_status()
        return resp.json() if resp.content else {}

    return retry_with_backoff(go, retryable_check=_retryable)


def _read_mock() -> list[dict]:
    if not os.path.exists(_MOCK_JSON):
        return []
    try:
        return json.loads(open(_MOCK_JSON, encoding="utf-8").read())
    except json.JSONDecodeError:
        return []


def _write_mock(deals: list[dict]) -> None:
    os.makedirs(os.path.dirname(_MOCK_JSON), exist_ok=True)
    with open(_MOCK_JSON, "w", encoding="utf-8") as f:
        json.dump(deals, f, indent=2, ensure_ascii=False)


def candidate_from_resume(resume_text: str) -> dict:
    """Name from the resume's first line, email from anywhere in it."""
    lines = [line.strip() for line in resume_text.splitlines() if line.strip()]
    email = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", resume_text)
    name = lines[0] if lines and len(lines[0]) <= 60 and "@" not in lines[0] else "Candidate"
    first, _, last = name.partition(" ")
    return {"name": name, "firstname": first, "lastname": last, "email": email.group() if email else ""}


def _find_or_create(obj: str, prop: str, value: str, properties: dict) -> str:
    found = _call("POST", f"/crm/v3/objects/{obj}/search", {
        "filterGroups": [{"filters": [{"propertyName": prop, "operator": "EQ", "value": value}]}],
        "limit": 1,
    })
    if found.get("results"):
        return found["results"][0]["id"]
    return _call("POST", f"/crm/v3/objects/{obj}", {"properties": properties})["id"]


def _deal_link(deal_id: str) -> str | None:
    global _portal_id
    if _portal_id is None:
        try:
            _portal_id = str(_call("GET", "/account-info/v3/details").get("portalId") or "")
        except Exception:  # noqa: BLE001 - the link is a nicety, the deal already exists
            _portal_id = ""
    return f"https://app.hubspot.com/contacts/{_portal_id}/record/0-3/{deal_id}" if _portal_id else None


def _association(to_id: str, type_id: int) -> dict:
    return {"to": {"id": to_id}, "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": type_id}]}


def log_application(company: str, role: str, candidate: dict, jd_source: str, stage: str,
                    links: dict | None = None, user_id: str = "") -> dict:
    """Returns {"status": "ok"|"error"|"mocked", "detail", "live", "ref", "link"?}.
    links {"email", "follow_up"} from the Gmail and Calendar steps go on the deal,
    so the CRM record opens straight into the application and its reminder."""
    try:
        retry_with_backoff(lambda: maybe_fail("crm"), retryable_check=_retryable)
    except Exception as exc:  # noqa: BLE001 - chaos panel outage
        return {"status": "error", "detail": f"CRM deal failed: {_classify(exc)}", "live": False, "ref": None}

    deal_name = f"{candidate['name']} → {role} @ {company}"
    description = "\n".join(
        [f"Source: {jd_source}"] + [f"{k.replace('_', ' ').title()}: {v}" for k, v in (links or {}).items() if v]
    )

    if user_id:
        # ponytail: Composio path puts company + candidate in the deal name; add association calls once
        # HUBSPOT_CREATE_ASSOCIATION's params are confirmed via `check_connections --ping`
        try:
            data = composio.execute(user_id, "HUBSPOT_CREATE_DEAL", {
                "dealname": deal_name, "dealstage": _stage(stage), "pipeline": "default", "description": description,
            })
        except Exception as exc:  # noqa: BLE001 - isolate action failures
            return {"status": "error", "detail": f"CRM deal failed (Composio): {exc}", "live": True, "ref": None}
        deal_id = composio.find(data, "id", "hs_object_id")
        return {"status": "ok", "detail": f"HubSpot deal created in your connected CRM at stage '{stage}' (id: {deal_id}).",
                "live": True, "ref": {"composio_user": user_id, "deal_id": deal_id}}

    if not is_live():
        deals = _read_mock()
        deal_id = uuid.uuid4().hex[:10]
        deals.append({"id": deal_id, "dealname": deal_name, "company": company, "contact": candidate,
                      "stage": stage, "description": description, "created": date.today().isoformat()})
        _write_mock(deals)
        return {"status": "mocked", "detail": f"[mock] CRM deal '{deal_name}' at stage {stage} (no HUBSPOT_TOKEN configured).",
                "live": False, "ref": {"mock_deal": deal_id}}

    try:
        associations = [_association(_find_or_create("companies", "name", company, {"name": company}), _DEAL_TO_COMPANY)]
        if candidate["email"]:
            contact_id = _find_or_create("contacts", "email", candidate["email"], {
                "email": candidate["email"], "firstname": candidate["firstname"], "lastname": candidate["lastname"],
            })
            associations.append(_association(contact_id, _DEAL_TO_CONTACT))
        deal = _call("POST", "/crm/v3/objects/deals", {
            "properties": {"dealname": deal_name, "pipeline": "default", "dealstage": _stage(stage), "description": description},
            "associations": associations,
        })
        linked = f"{company} and {candidate['name']}" if candidate["email"] else company
        return {"status": "ok", "detail": f"HubSpot deal created at stage '{stage}', linked to {linked}.",
                "live": True, "ref": {"deal_id": deal["id"]}, "link": _deal_link(deal["id"])}
    except Exception as exc:  # noqa: BLE001 - isolate action failures
        return {"status": "error", "detail": f"CRM deal failed: {_classify(exc)}", "live": True, "ref": None}


def set_deal_stage(ref: dict, stage: str) -> dict:
    """Move a deal this app created (reply tracker, undo)."""
    if "mock_deal" in ref:
        deals = _read_mock()
        for deal in deals:
            if deal["id"] == ref["mock_deal"]:
                deal["stage"] = stage
                _write_mock(deals)
                return {"status": "mocked", "detail": f"[mock] CRM deal moved to '{stage}'."}
        return {"status": "error", "detail": "Mock CRM deal not found."}
    if ref.get("composio_user"):
        try:
            composio.execute(ref["composio_user"], "HUBSPOT_UPDATE_DEAL",
                             {"dealId": ref["deal_id"], "properties": {"dealstage": _stage(stage)}})
        except Exception as exc:  # noqa: BLE001 - isolate action failures
            return {"status": "error", "detail": f"CRM update failed (Composio): {exc}"}
        return {"status": "ok", "detail": f"HubSpot deal moved to '{stage}' in your connected CRM."}
    if not is_live():
        return {"status": "error", "detail": "HUBSPOT_TOKEN not configured, can't update the live deal."}
    try:
        _call("PATCH", f"/crm/v3/objects/deals/{ref['deal_id']}", {"properties": {"dealstage": _stage(stage)}})
    except Exception as exc:  # noqa: BLE001 - isolate action failures
        return {"status": "error", "detail": f"CRM update failed: {_classify(exc)}"}
    return {"status": "ok", "detail": f"HubSpot deal moved to '{stage}'."}


def undo_deal(ref: dict) -> dict:
    """Deals are closed, not deleted, so the CRM keeps an honest history."""
    return set_deal_stage(ref, "undone")


if __name__ == "__main__":
    c = candidate_from_resume("Jordan Rivera\njordan.rivera@email.com | (555) 012-3456\nSUMMARY")
    assert c == {"name": "Jordan Rivera", "firstname": "Jordan", "lastname": "Rivera", "email": "jordan.rivera@email.com"}, c
    assert candidate_from_resume("")["name"] == "Candidate"
    print("crm self-check passed")
