import type { LucideIcon } from "lucide-react"
import { ArrowRight, BriefcaseBusiness, CircleCheck, ListChecks, MailCheck, Plug, Send, ShieldCheck, TriangleAlert } from "lucide-react"
import { useEffect, useState } from "react"

import { api, pct } from "@/app/api"
import type { Connections, EvalSummary, HistoryRow, Status } from "@/app/types"
import { APP_LABELS, OUTCOMES } from "@/app/types"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty"
import { Skeleton } from "@/components/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"

export type Section = "overview" | "run" | "jobs" | "tracker" | "reliability" | "apps"

function Kpi({ icon: Icon, label, value, hint }: { icon: LucideIcon; label: string; value?: number; hint: string }) {
  return (
    <Card>
      <CardHeader>
        <CardDescription className="flex items-center gap-2">
          <Icon aria-hidden="true" />
          {label}
        </CardDescription>
        {value === undefined ? <Skeleton className="h-9 w-16" /> : <CardTitle className="text-3xl font-bold tabular-nums">{value}</CardTitle>}
      </CardHeader>
      <CardContent className="text-xs text-muted-foreground">{hint}</CardContent>
    </Card>
  )
}

export function Overview({
  status,
  connections,
  refreshKey,
  onNavigate,
}: {
  status: Status | null
  connections: Connections | null
  refreshKey: number
  onNavigate: (section: Section) => void
}) {
  const [history, setHistory] = useState<HistoryRow[] | null>(null)
  const [summary, setSummary] = useState<{ normal?: EvalSummary; faults?: EvalSummary } | null>(null)

  useEffect(() => {
    api<HistoryRow[]>("/api/history").then(setHistory).catch(() => setHistory([]))
    api<{ normal?: EvalSummary; faults?: EvalSummary }>("/api/eval/summary").then(setSummary).catch(() => setSummary({}))
  }, [refreshKey])

  const active = history?.filter((r) => !r.undone)
  const connectedCount = connections ? Object.values(connections.apps).filter((a) => a.connected).length : 0

  const steps: { done: boolean; title: string; text: string; action: string; section: Section; icon: LucideIcon }[] = [
    { done: connectedCount === 4, title: "Connect your apps", text: `${connectedCount}/4 connected`, action: "Manage apps", section: "apps", icon: Plug },
    { done: (history?.length ?? 0) > 0, title: "Find matching jobs", text: "Ranked by skills you can prove", action: "Find jobs", section: "jobs", icon: BriefcaseBusiness },
    { done: (active?.some((r) => r.outcome === "drafted" || r.outcome === "sent")) ?? false, title: "Apply honestly", text: "Receipts checked before any app", action: "Run agent", section: "run", icon: ShieldCheck },
  ]

  return (
    <div className="flex flex-col gap-6">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Kpi icon={ListChecks} label="Applications" value={active?.length} hint="Runs that weren't undone" />
        <Kpi icon={Send} label="Drafted or sent" value={active?.filter((r) => r.outcome === "drafted" || r.outcome === "sent").length} hint="Passed every gate" />
        <Kpi icon={TriangleAlert} label="Stopped by a gate" value={history?.filter((r) => r.outcome === "flagged" || r.outcome === "duplicate").length} hint="Nothing sent, Slack told you why" />
        <Kpi icon={MailCheck} label="Replies" value={active?.filter((r) => r.replied).length} hint="CRM moved, reminder cancelled" />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Start here</CardTitle>
            <CardDescription>Three steps from resume to tracked, honest applications.</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            {steps.map((step, i) => (
              <div key={step.title} className="flex flex-wrap items-center gap-3 rounded-lg border p-3">
                <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-secondary text-secondary-foreground">
                  {step.done ? <CircleCheck aria-hidden="true" /> : <step.icon aria-hidden="true" />}
                </span>
                <div className="flex min-w-0 flex-1 flex-col">
                  <span className="text-sm font-medium">
                    {i + 1}. {step.title}
                  </span>
                  <span className="text-xs text-muted-foreground">{step.text}</span>
                </div>
                <Button variant={step.done ? "outline" : "default"} size="sm" onClick={() => onNavigate(step.section)}>
                  {step.action}
                  <ArrowRight data-icon="inline-end" />
                </Button>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Reliability</CardTitle>
            <CardDescription>10 job descriptions, 4 checks each</CardDescription>
            <CardAction>
              <Button variant="ghost" size="sm" onClick={() => onNavigate("reliability")}>
                Details
              </Button>
            </CardAction>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            {summary === null ? (
              <>
                <Skeleton className="h-12 w-full" />
                <Skeleton className="h-12 w-full" />
              </>
            ) : (
              [
                { label: "Normal run", s: summary.normal },
                { label: "Gmail down + LLM 429", s: summary.faults },
              ].map(({ label, s }) => (
                <div key={label} className="flex items-center justify-between gap-3 rounded-lg border p-3">
                  <div className="flex flex-col">
                    <span className="text-sm font-medium">{label}</span>
                    <span className="text-xs text-muted-foreground">{s ? `${pct(s.passed / Math.max(s.total, 1))} passed` : "Not run yet"}</span>
                  </div>
                  <Badge variant={s && s.passed === s.total ? "default" : "secondary"}>{s ? `${s.passed}/${s.total}` : "—"}</Badge>
                </div>
              ))
            )}
            <div className="flex flex-wrap gap-2 pt-1">
              <Badge variant={status?.llm ? "default" : "outline"}>LLM · {status?.llm ? "live" : "rule-based"}</Badge>
              {connections
                ? (Object.keys(APP_LABELS) as (keyof typeof APP_LABELS)[]).map((app) => (
                    <Badge key={app} variant={connections.apps[app].connected ? "default" : "outline"}>
                      {APP_LABELS[app]}
                    </Badge>
                  ))
                : null}
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Recent applications</CardTitle>
          <CardDescription>The last five runs across every app.</CardDescription>
          <CardAction>
            <Button variant="ghost" size="sm" onClick={() => onNavigate("tracker")}>
              Open tracker
            </Button>
          </CardAction>
        </CardHeader>
        <CardContent>
          {history === null ? (
            <div className="flex flex-col gap-2">
              {[0, 1, 2].map((i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : history.length ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Role</TableHead>
                  <TableHead>Company</TableHead>
                  <TableHead>Overlap</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {history.slice(0, 5).map((row) => (
                  <TableRow key={row.run_id}>
                    <TableCell className="max-w-64 truncate font-medium">{row.role}</TableCell>
                    <TableCell className="max-w-48 truncate">{row.company}</TableCell>
                    <TableCell className="tabular-nums">{pct(row.overlap)}</TableCell>
                    <TableCell>
                      <Badge variant={row.undone ? "outline" : row.replied ? "default" : (OUTCOMES[row.outcome]?.variant ?? "outline")}>
                        {row.undone ? "Undone" : row.replied ? "Replied" : (OUTCOMES[row.outcome]?.label ?? row.outcome)}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <Empty>
              <EmptyHeader>
                <EmptyTitle>No applications yet</EmptyTitle>
                <EmptyDescription>Find jobs that match skills you can prove, then let the agent apply.</EmptyDescription>
              </EmptyHeader>
              <EmptyContent>
                <Button onClick={() => onNavigate("jobs")}>
                  Find jobs
                  <ArrowRight data-icon="inline-end" />
                </Button>
              </EmptyContent>
            </Empty>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
