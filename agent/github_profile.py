"""
GitHub as a second source of proof.

A resume goes stale; public repos don't. For skills a job asks for that the
resume doesn't mention, the agent looks through the candidate's public
repositories (language, topics, description, README). A skill found there is
added to the resume as a clearly labeled GitHub section that names the repos,
so the Tailor may use it and the Executor's receipts check sees it as backed:
new skills are shown, never invented.

Uses the public GitHub API without a token (60 requests/hour, one per
profile) plus raw.githubusercontent.com for READMEs (not rate-limited the same
way). Profiles are cached for 10 minutes.
"""
import re
import time

import requests

_API = "https://api.github.com"
_RAW = "https://raw.githubusercontent.com"
_TIMEOUT_SECONDS = 10
_MAX_READMES = 8
_CACHE_SECONDS = 600
_USERNAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{0,38}$")
_cache: dict[str, tuple[float, dict]] = {}


def valid_username(username: str) -> bool:
    return bool(username) and _USERNAME.fullmatch(username) is not None


def fetch_profile(username: str) -> dict:
    """Returns {"username", "repos": [{name, url, language, topics, description, readme}], "error"}."""
    empty = {"username": username, "repos": [], "error": None}
    if not valid_username(username):
        return {**empty, "error": "Not a valid GitHub username."}
    cached = _cache.get(username.lower())
    if cached and time.time() - cached[0] < _CACHE_SECONDS:
        return cached[1]

    try:
        resp = requests.get(f"{_API}/users/{username}/repos", params={"per_page": 100, "sort": "pushed"},
                            headers={"Accept": "application/vnd.github+json"}, timeout=_TIMEOUT_SECONDS)
        if resp.status_code == 404:
            return {**empty, "error": "GitHub user not found."}
        if resp.status_code == 403 and resp.headers.get("X-RateLimit-Remaining") == "0":
            return {**empty, "error": "GitHub API rate limit reached (60/hour without a token). Try again later."}
        resp.raise_for_status()
    except requests.RequestException as exc:
        return {**empty, "error": f"GitHub unavailable: {exc}"}

    repos = [
        {"name": r["name"], "full_name": r["full_name"], "url": r["html_url"], "language": r.get("language") or "",
         "topics": r.get("topics") or [], "description": r.get("description") or "", "readme": ""}
        for r in resp.json() if not r.get("fork")
    ]
    # ponytail: READMEs for the most recently pushed repos only; fetch more if older work matters
    for repo in repos[:_MAX_READMES]:
        try:
            readme = requests.get(f"{_RAW}/{repo['full_name']}/HEAD/README.md", timeout=_TIMEOUT_SECONDS)
            if readme.ok:
                repo["readme"] = readme.text[:20_000]
        except requests.RequestException:
            pass

    profile = {"username": username, "repos": repos, "error": None}
    _cache[username.lower()] = (time.time(), profile)
    return profile


def _word_in(term: str, text_lower: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", text_lower) is not None


def _repo_shows(term: str, repo: dict) -> bool:
    t = term.lower().strip()
    topics = {x.lower() for x in repo["topics"]} | {x.lower().replace("-", " ") for x in repo["topics"]}
    if t == repo["language"].lower() or t in topics:
        return True
    # In prose (description, README) only named technologies count: at least 4 characters and written
    # with a capital ("Kubernetes", "FastAPI"). Plain words like "data" or "working" appear in every
    # README, and "Go"/"R" are only trusted as a repo language or topic.
    if len(term.strip()) < 4 or not any(c.isupper() for c in term):
        return False
    return _word_in(t, f"{repo['description']}\n{repo['readme']}".lower())


def verified_skills(terms: list[str], resume_text: str, profile: dict) -> list[dict]:
    """Job terms the resume doesn't mention but public repos show: [{"skill", "repos": [{name, url}]}]."""
    resume_lower = resume_text.lower()
    found = []
    for term in dict.fromkeys(t.strip() for t in terms if t and t.strip()):
        if _word_in(term.lower(), resume_lower):
            continue
        repos = [{"name": r["name"], "url": r["url"]} for r in profile.get("repos", []) if _repo_shows(term, r)]
        if repos:
            found.append({"skill": term, "repos": repos[:3]})
    return found


def evidence_section(verified: list[dict]) -> str:
    """Resume section the Tailor may draw on; every line names the repos that back it."""
    if not verified:
        return ""
    lines = ["GITHUB (verified from public repositories)"]
    lines += [f"- {v['skill']}: " + ", ".join(f"{r['name']} ({r['url']})" for r in v["repos"]) for v in verified]
    return "\n".join(lines)


def profile_skills(profile: dict) -> list[str]:
    """Languages and topics across the profile's repos, most common first."""
    counts: dict[str, int] = {}
    for repo in profile.get("repos", []):
        for skill in [repo["language"], *repo["topics"]]:
            if skill:
                counts[skill] = counts.get(skill, 0) + 1
    return sorted(counts, key=lambda s: -counts[s])


if __name__ == "__main__":
    profile = {"repos": [
        {"name": "infra", "url": "https://github.com/u/infra", "language": "Go", "topics": ["kubernetes"],
         "description": "Cluster tooling", "readme": "Deploys with Terraform. Written in go."},
        {"name": "notes", "url": "https://github.com/u/notes", "language": "Python", "topics": [],
         "description": "", "readme": "Some go-to scripts for R users"},
    ]}
    resume = "Python, FastAPI, PostgreSQL"
    found = {v["skill"]: [r["name"] for r in v["repos"]] for v in verified_skills(
        ["Python", "Kubernetes", "Terraform", "Go", "R", "Rust"], resume, profile)}
    assert found == {"Kubernetes": ["infra"], "Terraform": ["infra"], "Go": ["infra"]}, found  # Python on resume; "R"/"go" in prose don't count
    # plain words from a rule-based extractor ("data", "working", "e.g.") are not proof, even if a README has them
    wordy = {"repos": [{"name": "notes", "url": "u", "language": "Python", "topics": ["data"], "description": "",
                        "readme": "I like working with cloud data, e.g. pipelines."}]}
    assert [v["skill"] for v in verified_skills(["data", "working", "cloud", "e.g.", "like"], resume, wordy)] == ["data"]  # topic only
    assert evidence_section([]) == ""
    assert "infra (https://github.com/u/infra)" in evidence_section(verified_skills(["Terraform"], resume, profile))
    assert profile_skills(profile)[0] in ("Go", "Python") and "kubernetes" in profile_skills(profile)
    assert not valid_username("bad name") and valid_username("charansaiponnada")
    print("github profile self-check passed")
