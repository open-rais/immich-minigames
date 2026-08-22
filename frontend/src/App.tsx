import { lazy, Suspense } from "react"
import { BrowserRouter, Route, Routes } from "react-router-dom"

import { AuthProvider } from "./auth/AuthProvider"
import { LoginPage } from "./auth/LoginPage"
import { RequireAuth } from "./auth/RequireAuth"
import { ResetPasswordPage } from "./auth/ResetPasswordPage"
import { SignupPage } from "./auth/SignupPage"
import { DailyGameRoute } from "./menu/DailyGameRoute"
import { GameRoute } from "./menu/GameRoute"
import { MainMenu } from "./menu/MainMenu"
import { ThemeProvider } from "./theme/ThemeProvider"

// Lazy-loaded: none of these are the entry path a session
// hits right after login (that's "/" and the gameplay routes below), so they don't need to be in
// the initial bundle. The Suspense boundary around <Routes> below covers all of them.
const AdminPage = lazy(() => import("./admin/AdminPage").then((m) => ({ default: m.AdminPage })))
const AdminReportsPage = lazy(() =>
  import("./admin/AdminReportsPage").then((m) => ({ default: m.AdminReportsPage })),
)
const ChangePasswordPage = lazy(() =>
  import("./auth/ChangePasswordPage").then((m) => ({ default: m.ChangePasswordPage })),
)
const EditProfilePage = lazy(() =>
  import("./auth/EditProfilePage").then((m) => ({ default: m.EditProfilePage })),
)
const ProfilePage = lazy(() =>
  import("./auth/ProfilePage").then((m) => ({ default: m.ProfilePage })),
)
const RoundsPage = lazy(() =>
  import("./games/rounds/RoundsPage").then((m) => ({ default: m.RoundsPage })),
)
const SettingsPage = lazy(() =>
  import("./settings/SettingsPage").then((m) => ({ default: m.SettingsPage })),
)
const DailyLeaderboardPage = lazy(() =>
  import("./menu/DailyLeaderboardPage").then((m) => ({ default: m.DailyLeaderboardPage })),
)
const LeaderboardPage = lazy(() =>
  import("./menu/LeaderboardPage").then((m) => ({ default: m.LeaderboardPage })),
)

function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <AuthProvider>
          <Suspense fallback={<div className="min-h-dvh bg-app-bg" />}>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route path="/signup" element={<SignupPage />} />
              <Route path="/reset-password" element={<ResetPasswordPage />} />
              {/* Every other route needs a session; RequireAuth is a layout route
                  (renders <Outlet /> once logged in, redirects to /login otherwise) rather than
                  wrapping each element individually. */}
              <Route element={<RequireAuth />}>
                <Route path="/" element={<MainMenu />} />
                <Route path="/profile" element={<ProfilePage />} />
                <Route path="/profile/edit" element={<EditProfilePage />} />
                <Route path="/profile/password" element={<ChangePasswordPage />} />
                <Route path="/settings" element={<SettingsPage />} />
                <Route path="/admin" element={<AdminPage />} />
                <Route path="/admin/reports" element={<AdminReportsPage />} />
                <Route path="/:gameType/:mode/leaderboard" element={<LeaderboardPage />} />
                <Route path="/:gameType/:mode/game/:gameId/rounds" element={<RoundsPage />} />
                <Route
                  path="/daily/:gameType/:mode/leaderboard"
                  element={<DailyLeaderboardPage />}
                />
                <Route path="/daily/:gameType/:mode" element={<DailyGameRoute />} />
                <Route path="/:gameType/:mode" element={<GameRoute />} />
              </Route>
            </Routes>
          </Suspense>
        </AuthProvider>
      </BrowserRouter>
    </ThemeProvider>
  )
}

export default App
