import { useCallback, useState } from "react"

import type { AgentKey, AppKey, PipelineEvent } from "@/app/types"
import { APP_LABELS } from "@/app/types"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Spinner } from "@/components/ui/spinner"

type AgentState = "idle" | "running" | "done" | "warn"

interface PipelineState {
  agents: Record<AgentKey, { state: AgentState; label: string }>
  apps: Record<AppKey, string>
  trace: { id: number; text: string; fault?: boolean }[]
}

const AGENTS: { key: AgentKey; name: string; idle: string }[] = [
  { key: "researcher", name: "Researcher", idle: "Reads the job post" },
  { key: "tailor", name: "Tailor", idle: "Rewrites with receipts" },
  { key: "executor", name: "Executor", idle: "Checks, then acts" },
]

const APPS: AppKey[] = ["gmail", "calendar", "crm", "slack"]

const STEP_STATES: Record<string, [AgentState, string]> = {
  running: ["running", "Working…"],
  done: ["done", "Done"],
  reviewing: ["running", "Checking receipts and fit…"],
  acting: ["running", "Acting in apps…"],
  drafted: ["done", "Drafted, ready for you"],
  sent: ["done", "Sent"],
  partial: ["warn", "Partly failed"],
  flagged: ["warn", "Flagged, nothing sent"],
  duplicate: ["warn", "Duplicate, skipped"],
}

let traceId = 0

function initialState(): PipelineState {
  return {
    agents: Object.fromEntries(AGENTS.map((a) => [a.key, { state: "idle", label: a.idle }])) as PipelineState["agents"],
    apps: { gmail: "idle", calendar: "idle", crm: "idle", slack: "idle" },
    trace: [],
  }
}

function withTrace(state: PipelineState, text: string, fault = false): PipelineState {
  const time = new Date().toLocaleTimeString()
  return { ...state, trace: [...state.trace, { id: ++traceId, text: `${time}  ${text}`, fault }] }
}

export function usePipeline() {
  const [state, setState] = useState<PipelineState>(initialState)

  const reset = useCallback(() => setState(initialState()), [])

  const handle = useCallback((event: PipelineEvent) => {
    setState((s) => {
      switch (event.type) {
        case "step": {
          const [agentState, label] = STEP_STATES[event.status] ?? ["running", event.status]
          const next = { ...s, agents: { ...s.agents, [event.step]: { state: agentState, label } } }
          return withTrace(next, `${event.step}: ${event.status}`)
        }
        case "tool": {
          const next = { ...s, apps: { ...s.apps, [event.app]: event.status } }
          return event.status === "running"
            ? next
            : withTrace(next, `${event.app}: ${event.status} — ${event.detail ?? ""}`, event.status === "error")
        }
        case "github":
          return withTrace(
            s,
            event.error
              ? `github: ${event.error}`
              : `github: ${event.verified.length ? `verified from your repos: ${event.verified.join(", ")}` : "no extra skills this job needs"}`,
          )
        case "fault":
          return withTrace(s, `chaos panel: injecting ${event.names.join(", ")}`, true)
        case "result":
          return {
            ...s,
            apps: Object.fromEntries(
              Object.entries(s.apps).map(([app, status]) => [app, status === "idle" ? "skipped" : status]),
            ) as PipelineState["apps"],
          }
        case "batch":
          return withTrace(initialState(), `job ${event.index}/${event.total}: ${event.role} @ ${event.company}`)
        default:
          return s
      }
    })
  }, [])

  return { state, reset, handle }
}

function appVariant(status: string): "default" | "secondary" | "destructive" | "outline" {
  if (status === "ok" || status === "mocked") return "default"
  if (status === "error") return "destructive"
  if (status === "running") return "secondary"
  return "outline"
}

export function PipelineCard({ state }: { state: PipelineState }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Live pipeline</CardTitle>
        <CardDescription>Three agents, then four apps that hand off to each other.</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4" aria-live="polite">
        <div className="grid gap-3 sm:grid-cols-3">
          {AGENTS.map((agent, i) => {
            const { state: agentState, label } = state.agents[agent.key]
            return (
              <div key={agent.key} className="flex items-center gap-3 rounded-lg border p-3">
                <Badge variant={agentState === "done" ? "default" : agentState === "warn" ? "destructive" : "outline"}>
                  {agentState === "running" ? <Spinner data-icon="inline-start" /> : null}
                  {i + 1}
                </Badge>
                <div className="flex min-w-0 flex-col">
                  <span className="text-sm font-medium">{agent.name}</span>
                  <span className="truncate text-xs text-muted-foreground">{label}</span>
                </div>
              </div>
            )
          })}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {APPS.map((app, i) => (
            <div key={app} className="flex items-center gap-2">
              <Badge variant={appVariant(state.apps[app])}>
                {state.apps[app] === "running" ? <Spinner data-icon="inline-start" /> : null}
                {APP_LABELS[app]}
                {state.apps[app] === "skipped" ? " · skipped" : state.apps[app] === "mocked" ? " · mock" : ""}
              </Badge>
              {i < APPS.length - 1 ? <span className="text-xs text-muted-foreground">→</span> : null}
            </div>
          ))}
        </div>
        {state.trace.length ? (
          <ScrollArea className="h-40 rounded-lg border bg-muted/40">
            <div className="flex flex-col gap-1 p-3 font-mono text-xs">
              {state.trace.map((line) => (
                <span key={line.id} className={line.fault ? "text-destructive" : "text-muted-foreground"}>
                  {line.text}
                </span>
              ))}
            </div>
          </ScrollArea>
        ) : null}
      </CardContent>
    </Card>
  )
}
