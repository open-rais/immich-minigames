import { BrowserRouter, Route, Routes } from 'react-router-dom'

import { GameRoute } from './menu/GameRoute'
import { MainMenu } from './menu/MainMenu'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<MainMenu />} />
        <Route path="/:gameType/:mode" element={<GameRoute />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
