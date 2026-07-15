import { BrowserRouter, Route, Routes } from 'react-router-dom'

import { AuthProvider } from './auth/AuthProvider'
import { EditProfilePage } from './auth/EditProfilePage'
import { LoginPage } from './auth/LoginPage'
import { ProfilePage } from './auth/ProfilePage'
import { SignupPage } from './auth/SignupPage'
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
            <Route path="/" element={<MainMenu />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/signup" element={<SignupPage />} />
            <Route path="/profile" element={<ProfilePage />} />
            <Route path="/profile/edit" element={<EditProfilePage />} />
            <Route path="/:gameType/:mode/leaderboard" element={<LeaderboardPage />} />
            <Route path="/:gameType/:mode" element={<GameRoute />} />
          </Routes>
        </AuthProvider>
      </BrowserRouter>
    </ThemeProvider>
  )
}

export default App
