import { BrowserRouter, Route, Routes } from 'react-router-dom'

import { AuthProvider } from './auth/AuthProvider'
import { LoginPage } from './auth/LoginPage'
import { ProfilePage } from './auth/ProfilePage'
import { SignupPage } from './auth/SignupPage'
import { GameRoute } from './menu/GameRoute'
import { MainMenu } from './menu/MainMenu'

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/" element={<MainMenu />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/signup" element={<SignupPage />} />
          <Route path="/profile" element={<ProfilePage />} />
          <Route path="/:gameType/:mode" element={<GameRoute />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}

export default App
