import { useEffect, useState } from "react"
import { toast } from "sonner"

import { api, pct, safeUrl, store } from "@/app/api"
import type { AppKey, Connections, Status } from "@/app/types"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Spinner } from "@/components/ui/spinner"
import { Switch } from "@/components/ui/switch"

const USER_ID = /^[\w.@+-]{1,200}$/
const CONNECT_APPS: { key: AppKey; label: string }[] = [
  { key: "gmail", label: "Gmail" },
  { key: "calendar", label: "Google Calendar" },
  { key: "crm", label: "HubSpot" },
  { key: "slack", label: "Slack" },
]

export interface Profile {
  userId: string
  github: string
  slackChannel: string
}

export function YourAppsCard({
  profile,
  onProfileChange,
  onConnections,
}: {
  profile: Profile
  onProfileChange: (profile: Profile) => void
  onConnections: (connections: Connections) => void
}) {
  const [connections, setConnections] = useState<Connections | null>(null)
  const [githubHint, setGithubHint] = useState("")
  const [linking, setLinking] = useState<AppKey | null>(null)
  const validUser = USER_ID.test(profile.userId)

  useEffect(() => {
    store.set("userId", profile.userId)
    store.set("slackChannel", profile.slackChannel)
    const timer = setTimeout(() => {
      api<Connections>(`/api/connections?user_id=${encodeURIComponent(profile.userId)}`)
        .then((res) => {
          setConnections(res)
          onConnections(res)
        })
        .catch((err: Error) => toast.error(err.message))
    }, 400)
    return () => clearTimeout(timer)
  }, [profile.userId, profile.slackChannel, onConnections])

  useEffect(() => {
    store.set("github", profile.github)
    const username = profile.github.trim()
    if (!username) {
      setGithubHint("")
      return
    }
    if (!/^[A-Za-z0-9-]{1,39}$/.test(username)) {
      setGithubHint("Not a valid GitHub username.")
      return
    }
    setGithubHint("Checking public repos…")
    const timer = setTimeout(() => {
      api<{ repo_count: number; skills: string[]; error: string | null }>(`/api/github/${encodeURIComponent(username)}`)
        .then((p) => setGithubHint(p.error ?? `${p.repo_count} public repos · ${p.skills.slice(0, 6).join(", ") || "no languages found"}`))
        .catch((err: Error) => setGithubHint(err.message))
    }, 600)
    return () => clearTimeout(timer)
  }, [profile.github])

  async function connect(app: AppKey) {
    setLinking(app)
    try {
      const { redirect_url: url } = await api<{ redirect_url: string }>(`/api/connections/${app}/link`, {
        body: { user_id: profile.userId.trim() },
      })
      const safe = safeUrl(url)
      if (safe) window.location.href = safe
      else toast.error("Composio did not return a connect link.")
    } catch (err) {
      toast.error((err as Error).message)
    } finally {
      setLinking(null)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Your apps</CardTitle>
        <CardDescription>
          {connections && !connections.composio
            ? "One-click Connect needs COMPOSIO_API_KEY on the server. Using server keys where set, mock otherwise."
            : "Actions run on the accounts you connect. Composio stores the sign-in."}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <FieldGroup>
          <Field>
            <FieldLabel htmlFor="user-id">Your email</FieldLabel>
            <Input
              id="user-id"
              type="email"
              autoComplete="email"
              placeholder="you@example.com"
              value={profile.userId}
              onChange={(e) => onProfileChange({ ...profile, userId: e.target.value.trim() })}
            />
          </Field>
          <Field>
            <FieldLabel htmlFor="github">GitHub username (optional)</FieldLabel>
            <Input
              id="github"
              autoComplete="off"
              placeholder="octocat"
              value={profile.github}
              onChange={(e) => onProfileChange({ ...profile, github: e.target.value.trim() })}
            />
            <FieldDescription>{githubHint || "Skills your public repos prove get added, with the repo as the receipt."}</FieldDescription>
          </Field>
          <div className="flex flex-col gap-2">
            {CONNECT_APPS.map(({ key, label }) => {
              const app = connections?.apps[key]
              const state = app?.via === "composio" ? "Connected" : app?.via === "env" ? "Server keys" : "Not connected"
              return (
                <div key={key} className="flex items-center gap-2 text-sm">
                  <Badge variant={app?.connected ? "default" : "outline"}>{state}</Badge>
                  <span className="font-medium">{label}</span>
                  {connections?.composio && app?.via !== "composio" ? (
                    <Button className="ml-auto" variant="outline" size="sm" disabled={!validUser || linking !== null} onClick={() => connect(key)}>
                      {linking === key ? <Spinner data-icon="inline-start" /> : null}
                      Connect
                    </Button>
                  ) : null}
                </div>
              )
            })}
          </div>
          <Field>
            <FieldLabel htmlFor="slack-channel">Slack channel</FieldLabel>
            <Input
              id="slack-channel"
              placeholder="#job-applications"
              value={profile.slackChannel}
              onChange={(e) => onProfileChange({ ...profile, slackChannel: e.target.value.trim() })}
            />
          </Field>
        </FieldGroup>
      </CardContent>
    </Card>
  )
}

export interface RunDetails {
  company: string
  role: string
  recipient: string
  allowSend: boolean
}

export function RunDetailsCard({
  details,
  onChange,
  status,
  gmailConnected,
  running,
  onRun,
}: {
  details: RunDetails
  onChange: (details: RunDetails) => void
  status: Status | null
  gmailConnected: boolean
  running: boolean
  onRun: () => void
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Application</CardTitle>
        <CardDescription>
          {status
            ? `Flag below ${pct(status.review_threshold)} overlap · send only at ${pct(status.send_threshold)}+ with every check clean.`
            : "Loading thresholds…"}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form
          onSubmit={(e) => {
            e.preventDefault()
            onRun()
          }}
        >
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="company">Company</FieldLabel>
              <Input id="company" maxLength={200} value={details.company} onChange={(e) => onChange({ ...details, company: e.target.value })} />
            </Field>
            <Field>
              <FieldLabel htmlFor="role">Role</FieldLabel>
              <Input id="role" maxLength={200} value={details.role} onChange={(e) => onChange({ ...details, role: e.target.value })} />
            </Field>
            <Field>
              <FieldLabel htmlFor="recipient">Send to (optional)</FieldLabel>
              <Input
                id="recipient"
                type="email"
                placeholder="hiring@company.com"
                value={details.recipient}
                onChange={(e) => onChange({ ...details, recipient: e.target.value })}
              />
            </Field>
            <Field orientation="horizontal" data-disabled={!gmailConnected || undefined}>
              <Switch
                id="allow-send"
                disabled={!gmailConnected}
                checked={details.allowSend && gmailConnected}
                onCheckedChange={(checked: boolean) => onChange({ ...details, allowSend: checked })}
              />
              <FieldLabel htmlFor="allow-send">Allow sending</FieldLabel>
            </Field>
            <FieldDescription>
              {gmailConnected
                ? "Sends only with a recipient, overlap above the send bar, and every receipt checked."
                : "Connect Gmail to enable. Until then everything stays a draft."}
            </FieldDescription>
            <Button type="submit" disabled={running}>
              {running ? <Spinner data-icon="inline-start" /> : null}
              {running ? "Running…" : "Run agent"}
            </Button>
          </FieldGroup>
        </form>
      </CardContent>
    </Card>
  )
}

const FAULT_LABELS: Record<string, string> = {
  gmail: "Gmail down",
  calendar: "Calendar down",
  crm: "HubSpot down",
  slack: "Slack down",
  llm_429: "LLM rate-limited",
  google_auth: "Google token expired",
}

export function ChaosCard({ status, onFaults }: { status: Status | null; onFaults: (faults: string[]) => void }) {
  async function toggle(name: string, on: boolean) {
    if (!status) return
    const next = new Set(status.faults)
    if (on) next.add(name)
    else next.delete(name)
    try {
      const res = await api<{ faults: string[] }>("/api/faults", { body: { faults: [...next] } })
      onFaults(res.faults)
    } catch (err) {
      toast.error((err as Error).message)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Chaos panel</CardTitle>
        <CardDescription>Break things on purpose. The agent should retry, fall back or flag, never crash.</CardDescription>
      </CardHeader>
      <CardContent>
        <FieldGroup className="grid grid-cols-2 gap-3">
          {(status?.available_faults ?? []).map((name) => (
            <Field key={name} orientation="horizontal">
              <Checkbox
                id={`fault-${name}`}
                checked={status?.faults.includes(name) ?? false}
                onCheckedChange={(checked: boolean) => toggle(name, checked)}
              />
              <FieldLabel htmlFor={`fault-${name}`}>{FAULT_LABELS[name] ?? name}</FieldLabel>
            </Field>
          ))}
        </FieldGroup>
      </CardContent>
    </Card>
  )
}
