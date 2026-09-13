import { useCallback, useEffect, useMemo, useState } from "react"
import { toast } from "sonner"

import { api, pct, safeUrl } from "@/app/api"
import type { HistoryRow } from "@/app/types"
import { OUTCOMES } from "@/app/types"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty"
import { Input } from "@/components/ui/input"
import { Spinner } from "@/components/ui/spinner"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"

interface ReplySync {
  mode: string
  checked: number
  replies: { run_id: string; company?: string; error?: string }[]
}

function replySummary(res: ReplySync) {
  if (!res.replies.length) return `Checked ${res.checked} application(s) in ${res.mode} mode. No new replies.`
  return res.replies
    .map((r) => (r.error ? `Error: ${r.error}` : `Reply from ${r.company}: CRM deal moved to replied, reminder cancelled, Slack pinged.`))
    .join(" ")
}

export function Tracker({ googleLive, refreshKey, onUndo }: { googleLive: boolean; refreshKey: number; onUndo: (runId: string) => Promise<boolean> }) {
  const [rows, setRows] = useState<HistoryRow[]>([])
  const [query, setQuery] = useState("")
  const [busy, setBusy] = useState<string | null>(null)

  const load = useCallback(() => {
    api<HistoryRow[]>("/api/history")
      .then(setRows)
      .catch((err: Error) => toast.error(err.message))
  }, [])

  useEffect(load, [load, refreshKey])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return rows.filter((r) => !q || `${r.company} ${r.role}`.toLowerCase().includes(q))
  }, [rows, query])

  async function withBusy(key: string, fn: () => Promise<void>) {
    setBusy(key)
    try {
      await fn()
    } catch (err) {
      toast.error((err as Error).message)
    } finally {
      setBusy(null)
      load()
    }
  }

  const active = rows.filter((r) => !r.undone)
  const metrics = [
    ["Applications", active.length],
    ["Drafted or sent", active.filter((r) => r.outcome === "drafted" || r.outcome === "sent").length],
    ["Flagged", rows.filter((r) => r.outcome === "flagged").length],
    ["Replies", active.filter((r) => r.replied).length],
  ] as const

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {metrics.map(([label, value]) => (
          <Card key={label}>
            <CardHeader>
              <CardDescription>{label}</CardDescription>
              <CardTitle className="text-3xl tabular-nums">{value}</CardTitle>
            </CardHeader>
          </Card>
        ))}
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Application history</CardTitle>
          <CardDescription>Reply found → CRM deal moves to replied, reminder cancelled, Slack pinged.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="flex flex-wrap gap-2">
            <Input className="max-w-xs" type="search" placeholder="Search company or role" aria-label="Search applications" value={query} onChange={(e) => setQuery(e.target.value)} />
            <Button
              variant="outline"
              disabled={busy !== null}
              onClick={() =>
                withBusy("sync", async () => {
                  toast.info(replySummary(await api<ReplySync>("/api/replies/sync", { method: "POST" })))
                })
              }
            >
              {busy === "sync" ? <Spinner data-icon="inline-start" /> : null}
              Sync replies
            </Button>
          </div>
          {filtered.length ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>When</TableHead>
                  <TableHead>Company</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead>Overlap</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Executor</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.map((row) => {
                  const actionable = !row.undone && ["sent", "drafted", "partial"].includes(row.outcome)
                  const outcome = OUTCOMES[row.outcome]
                  const replyLink = safeUrl(row.reply_link)
                  return (
                    <TableRow key={row.run_id}>
                      <TableCell>{row.started_at.replace("T", " ").slice(0, 16)}</TableCell>
                      <TableCell>{row.company}</TableCell>
                      <TableCell className="max-w-56 truncate">{row.role}</TableCell>
                      <TableCell className="tabular-nums">{pct(row.overlap)}</TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <Badge variant={row.undone ? "outline" : row.replied ? "default" : (outcome?.variant ?? "outline")}>
                            {row.undone ? "Undone" : row.replied ? "Replied" : (outcome?.label ?? row.outcome)}
                          </Badge>
                          {replyLink ? (
                            <Button variant="link" size="sm" render={<a href={replyLink} target="_blank" rel="noopener noreferrer" />}>
                              reply
                            </Button>
                          ) : null}
                        </div>
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {row.executor_mode ?? "—"}
                        {row.faults?.length ? " · chaos" : ""}
                      </TableCell>
                      <TableCell>
                        <div className="flex justify-end gap-2">
                          {actionable ? (
                            <Button variant="outline" size="sm" disabled={busy !== null} onClick={() => withBusy(row.run_id, async () => void (await onUndo(row.run_id)))}>
                              {busy === row.run_id ? <Spinner data-icon="inline-start" /> : null}
                              Undo
                            </Button>
                          ) : null}
                          {actionable && !googleLive && !row.replied && row.outcome !== "partial" ? (
                            <Button
                              variant="ghost"
                              size="sm"
                              disabled={busy !== null}
                              onClick={() =>
                                withBusy(`reply-${row.run_id}`, async () => {
                                  toast.info(replySummary(await api<ReplySync>(`/api/replies/simulate/${encodeURIComponent(row.run_id)}`, { method: "POST" })))
                                })
                              }
                            >
                              Simulate reply
                            </Button>
                          ) : null}
                        </div>
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          ) : (
            <Empty>
              <EmptyHeader>
                <EmptyTitle>{rows.length ? "No matches" : "No applications yet"}</EmptyTitle>
                <EmptyDescription>{rows.length ? "Try another search." : "Run the agent to start tracking."}</EmptyDescription>
              </EmptyHeader>
            </Empty>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
