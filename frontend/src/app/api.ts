import type { PipelineEvent } from "@/app/types"

function detailText(detail: unknown, status: number): string {
  if (!detail) return `HTTP ${status}`
  if (typeof detail === "string") return detail
  if (Array.isArray(detail)) {
    return detail.map((d) => (d as { msg?: string }).msg ?? String(d)).join("; ")
  }
  return JSON.stringify(detail)
}

export async function api<T>(path: string, options: { method?: string; body?: unknown } = {}): Promise<T> {
  const res = await fetch(path, {
    method: options.method ?? (options.body === undefined ? "GET" : "POST"),
    headers: options.body === undefined ? undefined : { "Content-Type": "application/json" },
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  })
  const data: unknown = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(detailText((data as { detail?: unknown }).detail, res.status))
  return data as T
}

/** POST, then read the server-sent event stream, calling onEvent for each `data:` message. */
export async function streamEvents(path: string, body: unknown, onEvent: (event: PipelineEvent) => void) {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  if (!res.ok || !res.body) {
    const data: unknown = await res.json().catch(() => ({}))
    throw new Error(detailText((data as { detail?: unknown }).detail, res.status))
  }
  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ""
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += value
    let split: number
    while ((split = buffer.indexOf("\n\n")) >= 0) {
      const chunk = buffer.slice(0, split)
      buffer = buffer.slice(split + 2)
      if (chunk.startsWith("data: ")) onEvent(JSON.parse(chunk.slice(6)) as PipelineEvent)
    }
  }
}

/** Only https links from the server become clickable. */
export const safeUrl = (url?: string | null) => (url && /^https:\/\//.test(url) ? url : undefined)

export const pct = (value?: number) => `${Math.round((value ?? 0) * 100)}%`

/** localStorage for per-browser conveniences; silently a no-op when storage is blocked. */
export const store = {
  get(key: string) {
    try {
      return localStorage.getItem(key) ?? ""
    } catch {
      return ""
    }
  },
  set(key: string, value: string) {
    try {
      localStorage.setItem(key, value)
    } catch {
      // storage blocked: keep working for this visit
    }
  },
}
