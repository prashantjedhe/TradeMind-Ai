import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import DashboardPage from './pages/DashboardPage'
import TradingPage from './pages/TradingPage'
import StrategyBuilderPage from './pages/StrategyBuilderPage'
import NewsPage from './pages/NewsPage'
import FOPage from './pages/FOPage'
import ProfilePage from './pages/ProfilePage'
import LeaguePage from './pages/LeaguePage'
import ProtectedRoute from './components/common/ProtectedRoute'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <DashboardPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/trading"
          element={
            <ProtectedRoute>
              <TradingPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/fno"
          element={
            <ProtectedRoute>
              <FOPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/strategies"
          element={
            <ProtectedRoute>
              <StrategyBuilderPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/news"
          element={
            <ProtectedRoute>
              <NewsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/league"
          element={
            <ProtectedRoute>
              <LeaguePage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/profile"
          element={
            <ProtectedRoute>
              <ProfilePage />
            </ProtectedRoute>
          }
        />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App