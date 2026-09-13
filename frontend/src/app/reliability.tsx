import { useCallback, useEffect, useState } from "react"
import { toast } from "sonner"

import { api, pct } from "@/app/api"
import type { EvalSummary } from "@/app/types"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty"
import { Spinner } from "@/components/ui/spinner"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"

const CRITERIA = ["extraction", "faithfulness", "decision", "actions"] as const

function SummaryCard({ title, summary }: { title: string; summary?: EvalSummary }) {
  if (!summary) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{title}</CardTitle>
        </CardHeader>
        <CardContent>
          <Empty>
            <EmptyHeader>
              <EmptyTitle>Not run yet</EmptyTitle>
              <EmptyDescription>Run the suite above.</EmptyDescription>
            </EmptyHeader>
          </Empty>
        </CardContent>
      </Card>
    )
  }
  const mark = (ok: boolean) => <Badge variant={ok ? "secondary" : "destructive"}>{ok ? "pass" : "FAIL"}</Badge>
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>
          {summary.ran_at.replace("T", " ")}
          {summary.faults.length ? ` · faults: ${summary.faults.join(", ")}` : ""}
        </CardDescription>
        <CardAction>
          <Badge variant={summary.passed === summary.total ? "default" : "outline"}>
            {summary.passed}/{summary.total} passed
          </Badge>
        </CardAction>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {CRITERIA.map((c) => (
            <div key={c} className="flex flex-col gap-1 rounded-lg border p-3">
              <span className="text-2xl font-semibold tabular-nums">
                {summary.criteria[c]}/{summary.total}
              </span>
              <span className="text-xs text-muted-foreground capitalize">{c}</span>
            </div>
          ))}
        </div>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Job description</TableHead>
              <TableHead>Outcome</TableHead>
              <TableHead>Overlap</TableHead>
              {CRITERIA.map((c) => (
                <TableHead key={c} className="capitalize">
                  {c}
                </TableHead>
              ))}
              <TableHead>Result</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {summary.rows.map((row) => (
              <TableRow key={row.jd_file}>
                <TableCell>{row.jd_file}</TableCell>
                <TableCell>{row.error ? `crash: ${row.error}` : row.outcome}</TableCell>
                <TableCell className="tabular-nums">{row.error ? "—" : pct(row.overlap)}</TableCell>
                {CRITERIA.map((c) => (
                  <TableCell key={c}>{mark(row[c])}</TableCell>
                ))}
                <TableCell>{mark(row.passed)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  )
}

export function Reliability() {
  const [summaries, setSummaries] = useState<{ normal?: EvalSummary; faults?: EvalSummary }>({})
  const [running, setRunning] = useState<"normal" | "faults" | null>(null)

  const load = useCallback(() => {
    api<{ normal?: EvalSummary; faults?: EvalSummary }>("/api/eval/summary")
      .then(setSummaries)
      .catch((err: Error) => toast.error(err.message))
  }, [])

  useEffect(load, [load])

  async function run(kind: "normal" | "faults") {
    setRunning(kind)
    try {
      await api("/api/eval", { body: { faults: kind === "faults" ? ["gmail", "llm_429"] : [] } })
      load()
    } catch (err) {
      toast.error((err as Error).message)
    } finally {
      setRunning(null)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardHeader>
          <CardTitle>How we know it works</CardTitle>
          <CardDescription>
            Ten job descriptions, including a poor fit and one that baits the agent into claiming skills you don't have. Each is
            scored on extraction, faithfulness, decision and actions. Run it normally, then with Gmail down and the model rate-limited.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          <Button disabled={running !== null} onClick={() => run("normal")}>
            {running === "normal" ? <Spinner data-icon="inline-start" /> : null}
            Run test suite
          </Button>
          <Button variant="outline" disabled={running !== null} onClick={() => run("faults")}>
            {running === "faults" ? <Spinner data-icon="inline-start" /> : null}
            Run with Gmail down + LLM 429
          </Button>
        </CardContent>
      </Card>
      <SummaryCard title="Normal run" summary={summaries.normal} />
      <SummaryCard title="Under injected failures" summary={summaries.faults} />
    </div>
  )
}
