import { BrowserRouter, Route, Routes } from 'react-router-dom'

import { AdminPage } from './admin/AdminPage'
import { AuthProvider } from './auth/AuthProvider'
import { ChangePasswordPage } from './auth/ChangePasswordPage'
import { EditProfilePage } from './auth/EditProfilePage'
import { LoginPage } from './auth/LoginPage'
import { ProfilePage } from './auth/ProfilePage'
import { RequireAuth } from './auth/RequireAuth'
import { ResetPasswordPage } from './auth/ResetPasswordPage'
import { SignupPage } from './auth/SignupPage'
import { RoundsPage } from './games/rounds/RoundsPage'
import { DailyGameRoute } from './menu/DailyGameRoute'
import { DailyLeaderboardPage } from './menu/DailyLeaderboardPage'
import { GameRoute } from './menu/GameRoute'
import { LeaderboardPage } from './menu/LeaderboardPage'
import { MainMenu } from './menu/MainMenu'
import { ThemeProvider } from './theme/ThemeProvider'

function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/signup" element={<SignupPage />} />
            <Route path="/reset-password" element={<ResetPasswordPage />} />
            {/* Roadmap #H, F3 - every other route needs a session; RequireAuth is a layout route
                (renders <Outlet /> once logged in, redirects to /login otherwise) rather than
                wrapping each element individually. */}
            <Route element={<RequireAuth />}>
              <Route path="/" element={<MainMenu />} />
              <Route path="/profile" element={<ProfilePage />} />
              <Route path="/profile/edit" element={<EditProfilePage />} />
              <Route path="/profile/password" element={<ChangePasswordPage />} />
              <Route path="/admin" element={<AdminPage />} />
              <Route path="/:gameType/:mode/leaderboard" element={<LeaderboardPage />} />
              <Route path="/:gameType/:mode/game/:gameId/rounds" element={<RoundsPage />} />
              <Route path="/daily/:gameType/:mode/leaderboard" element={<DailyLeaderboardPage />} />
              <Route path="/daily/:gameType/:mode" element={<DailyGameRoute />} />
              <Route path="/:gameType/:mode" element={<GameRoute />} />
            </Route>
          </Routes>
        </AuthProvider>
      </BrowserRouter>
    </ThemeProvider>
  )
}

export default App
