import { Navigate } from 'react-router-dom'
import { useAuthStore } from '../../store/authStore'

function ProtectedRoute({ children }) {
  const accessToken = useAuthStore((state) => state.accessToken)

  if (!accessToken) {
    return <Navigate to="/login" replace />
  }

  return children
}

export default ProtectedRoute
