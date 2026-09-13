import { useState } from "react"

import { pct, safeUrl } from "@/app/api"
import type { ActionResult, GapReport, Requirements, RunResult } from "@/app/types"
import { APP_LABELS, OUTCOMES } from "@/app/types"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import { Spinner } from "@/components/ui/spinner"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"

export function Receipts({ result }: { result: RunResult }) {
  const [active, setActive] = useState<number | null>(null)
  const receipts = result.executor_verdict.receipts ?? []
  const unsupported = receipts.filter((r) => !r.supported).length

  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-muted-foreground">
        {unsupported
          ? `${unsupported} line(s) failed the receipts check and blocked the apps.`
          : `All ${receipts.length} tailored lines trace back to your resume${result.github?.verified.length ? " or your GitHub repos" : ""}. Hover a line to see its source.`}
      </p>
      <div className="grid gap-4 md:grid-cols-2">
        <div className="flex flex-col gap-2">
          <span className="text-xs font-medium text-muted-foreground">Tailored (source line)</span>
          <ScrollArea className="h-96 rounded-lg border">
            <div className="flex flex-col gap-1 p-2">
              {receipts.map((receipt, i) => (
                <button
                  key={i}
                  type="button"
                  onMouseEnter={() => setActive(receipt.source_line)}
                  onFocus={() => setActive(receipt.source_line)}
                  onClick={() => setActive(receipt.source_line)}
                  className="flex gap-2 rounded-md p-2 text-left text-sm hover:bg-muted focus-visible:bg-muted"
                >
                  <Badge variant={receipt.supported ? "outline" : "destructive"}>{receipt.source_line ?? "?"}</Badge>
                  <span className="flex flex-col gap-1">
                    {receipt.tailored}
                    {receipt.reason ? <span className="text-xs text-destructive">{receipt.reason}</span> : null}
                  </span>
                </button>
              ))}
            </div>
          </ScrollArea>
        </div>
        <div className="flex flex-col gap-2">
          <span className="text-xs font-medium text-muted-foreground">Your resume{result.github?.verified.length ? " + GitHub evidence" : ""}</span>
          <ScrollArea className="h-96 rounded-lg border">
            <div className="flex flex-col gap-1 p-2">
              {result.resume_lines.map((line, i) => (
                <div key={i} className={`flex gap-2 rounded-md p-2 text-sm ${active === i ? "bg-primary/10" : ""}`}>
                  <span className="w-6 shrink-0 text-right font-mono text-xs text-muted-foreground">{i}</span>
                  <span>{line}</span>
                </div>
              ))}
            </div>
          </ScrollArea>
        </div>
      </div>
    </div>
  )
}

const gapCount = (g: GapReport) =>
  g.missing_must_haves.length + g.missing_keywords.length + g.unsupported_claims.length + (g.seniority ? 1 : 0)

export function Gaps({ gaps }: { gaps: GapReport }) {
  if (!gapCount(gaps)) {
    return (
      <Empty>
        <EmptyHeader>
          <EmptyTitle>No gaps</EmptyTitle>
          <EmptyDescription>Your resume covers what this job asks for.</EmptyDescription>
        </EmptyHeader>
      </Empty>
    )
  }
  const section = (title: string, items: string[]) =>
    items.length ? (
      <div className="flex flex-col gap-2">
        <span className="text-xs font-medium text-muted-foreground">{title}</span>
        <div className="flex flex-wrap gap-2">
          {items.map((item) => (
            <Badge key={item} variant="outline">
              {item}
            </Badge>
          ))}
        </div>
      </div>
    ) : null
  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-muted-foreground">What this job wants that your resume doesn't show.</p>
      {gaps.seniority ? (
        <Alert>
          <AlertTitle>Seniority</AlertTitle>
          <AlertDescription>{gaps.seniority}</AlertDescription>
        </Alert>
      ) : null}
      {section("Must-haves not found", gaps.missing_must_haves)}
      {section("Keywords not found", gaps.missing_keywords)}
      {gaps.unsupported_claims.length ? (
        <Alert variant="destructive">
          <AlertTitle>Blocked claims</AlertTitle>
          <AlertDescription>
            <ul className="flex list-disc flex-col gap-1 pl-4">
              {gaps.unsupported_claims.map((claim) => (
                <li key={claim}>{claim}</li>
              ))}
            </ul>
          </AlertDescription>
        </Alert>
      ) : null}
    </div>
  )
}

function Actions({ actions }: { actions: Record<string, ActionResult> }) {
  const entries = Object.entries(actions)
  if (!entries.length) {
    return (
      <Empty>
        <EmptyHeader>
          <EmptyTitle>No app actions ran</EmptyTitle>
        </EmptyHeader>
      </Empty>
    )
  }
  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-muted-foreground">
        Chained in order: the email link goes into the reminder, both links onto the CRM deal, and Slack gets all three.
      </p>
      {entries.map(([key, action], i) => {
        const link = safeUrl(action.link)
        const label = APP_LABELS[key as keyof typeof APP_LABELS] ?? key
        const ok = action.status === "ok" || action.status === "mocked"
        return (
          <div key={key} className="flex flex-col gap-3">
            {i ? <Separator /> : null}
            <div className="flex flex-wrap items-start gap-3">
              <Badge variant={ok ? "default" : action.status === "skipped" ? "outline" : "destructive"}>{action.status}</Badge>
              <div className="flex min-w-0 flex-1 flex-col gap-1">
                <span className="text-sm font-medium">{label}</span>
                <span className="text-sm text-muted-foreground">{action.detail}</span>
              </div>
              {link ? (
                <Button variant="outline" size="sm" nativeButton={false} render={<a href={link} target="_blank" rel="noopener noreferrer" />}>
                  Open in {label}
                </Button>
              ) : null}
            </div>
          </div>
        )
      })}
    </div>
  )
}

function RequirementsView({ requirements }: { requirements: Requirements }) {
  const badges = (items?: string[]) => (
    <div className="flex flex-wrap gap-2">
      {(items ?? []).map((item) => (
        <Badge key={item} variant="secondary">
          {item}
        </Badge>
      ))}
    </div>
  )
  return (
    <div className="grid gap-6 md:grid-cols-2">
      <div className="flex flex-col gap-3">
        <span className="text-xs font-medium text-muted-foreground">Seniority</span>
        <span className="text-sm">{requirements.seniority ?? "?"}</span>
        <span className="text-xs font-medium text-muted-foreground">Skills</span>
        {badges(requirements.skills)}
      </div>
      <div className="flex flex-col gap-3">
        <span className="text-xs font-medium text-muted-foreground">Must-haves</span>
        <ul className="flex list-disc flex-col gap-1 pl-4 text-sm">
          {(requirements.must_haves ?? []).map((m) => (
            <li key={m}>{m}</li>
          ))}
        </ul>
        <span className="text-xs font-medium text-muted-foreground">Keywords</span>
        {badges(requirements.keywords)}
      </div>
    </div>
  )
}

export function ResultView({ result, onUndo }: { result: RunResult; onUndo: (runId: string) => Promise<boolean> }) {
  const [undoing, setUndoing] = useState(false)
  const [undone, setUndone] = useState(false)
  const verdict = result.executor_verdict
  const outcome = OUTCOMES[result.outcome] ?? { label: result.outcome, variant: "outline" as const }
  const canUndo = !undone && ["sent", "drafted", "partial"].includes(result.outcome)

  let callout: { title: string; text: string; destructive?: boolean } | null = null
  if (result.outcome === "flagged") {
    callout = result.gap_report.seniority
      ? { title: "Nothing sent", text: `${result.gap_report.seniority}. Slack was told why.` }
      : verdict.faithful
        ? { title: "Nothing sent", text: `Overlap ${pct(result.guardrail.score)} is below the ${pct(result.guardrail.threshold)} bar, so Gmail, Calendar and HubSpot were skipped. Slack was told why.` }
        : { title: "Blocked by receipts", text: `${verdict.unsupported_claims.length} claim(s) aren't backed by your resume, so nothing was sent anywhere.`, destructive: true }
  } else if (result.outcome === "duplicate") {
    callout = { title: "Already applied", text: `You already applied to ${result.role} at ${result.company}. Undo that run from the Tracker to apply again.` }
  } else if (result.outcome === "partial") {
    callout = { title: "Some apps failed", text: "They failed after retries (see Actions). The rest completed; re-run to retry.", destructive: true }
  }

  const gaps = gapCount(result.gap_report)

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-2">
          <Badge variant={outcome.variant}>{outcome.label}</Badge>
          {result.role} @ {result.company}
        </CardTitle>
        <CardDescription>
          Overlap {pct(result.guardrail.score)} · Executor {result.executor_mode} ·{" "}
          {result.used_live_llm ? "live LLM" : "rule-based fallback"} · review: {verdict.recommendation} ({pct(verdict.confidence)}) — {verdict.reason}
        </CardDescription>
        {canUndo ? (
          <CardAction>
            <Button
              variant="outline"
              size="sm"
              disabled={undoing}
              onClick={async () => {
                setUndoing(true)
                setUndone(await onUndo(result.run_id))
                setUndoing(false)
              }}
            >
              {undoing ? <Spinner data-icon="inline-start" /> : null}
              Undo everything
            </Button>
          </CardAction>
        ) : null}
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {callout ? (
          <Alert variant={callout.destructive ? "destructive" : "default"}>
            <AlertTitle>{callout.title}</AlertTitle>
            <AlertDescription>{callout.text}</AlertDescription>
          </Alert>
        ) : null}
        <Tabs defaultValue="receipts">
          <TabsList>
            <TabsTrigger value="receipts">Receipts</TabsTrigger>
            <TabsTrigger value="cover">Cover note</TabsTrigger>
            <TabsTrigger value="gaps">{gaps ? `Gaps (${gaps})` : "Gaps"}</TabsTrigger>
            <TabsTrigger value="actions">Actions</TabsTrigger>
            <TabsTrigger value="requirements">Requirements</TabsTrigger>
          </TabsList>
          <TabsContent value="receipts">
            <Receipts result={result} />
          </TabsContent>
          <TabsContent value="cover">
            <p className="text-sm leading-relaxed whitespace-pre-wrap">{result.cover_note || "—"}</p>
          </TabsContent>
          <TabsContent value="gaps">
            <Gaps gaps={result.gap_report} />
          </TabsContent>
          <TabsContent value="actions">
            <Actions actions={result.actions} />
          </TabsContent>
          <TabsContent value="requirements">
            <RequirementsView requirements={result.requirements} />
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  )
}
