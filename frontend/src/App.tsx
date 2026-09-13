import { MotionConfig } from "framer-motion"
import { lazy, Suspense } from "react"

import { Toaster } from "@/components/ui/sonner"
import { Spinner } from "@/components/ui/spinner"
import { TooltipProvider } from "@/components/ui/tooltip"

// One build serves both pages: FastAPI returns this app at / (landing) and /app (dashboard).
// Each page is its own chunk, so the landing page never downloads the dashboard's charts and sidebar.
const AgentApp = lazy(() => import("@/app/agent-app").then((m) => ({ default: m.AgentApp })))
const LandingPage = lazy(() => import("@/landing/landing-page").then((m) => ({ default: m.LandingPage })))

export function App() {
  const isDashboard = window.location.pathname.startsWith("/app")
  return (
    <MotionConfig reducedMotion="user">
      <TooltipProvider>
        <Suspense
          fallback={
            <div className="flex min-h-svh items-center justify-center" role="status" aria-label="Loading">
              <Spinner />
            </div>
          }
        >
          {isDashboard ? <AgentApp /> : <LandingPage />}
        </Suspense>
        <Toaster />
      </TooltipProvider>
    </MotionConfig>
  )
}

export default App
