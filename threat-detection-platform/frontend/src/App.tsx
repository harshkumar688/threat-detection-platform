import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/common/Layout';
import ProtectedRoute from './components/common/ProtectedRoute';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import LiveMonitoringPage from './pages/LiveMonitoringPage';
import IncidentsPage from './pages/IncidentsPage';
import IncidentDetailPage from './pages/IncidentDetailPage';
import CamerasPage from './pages/CamerasPage';
import AnalyticsPage from './pages/AnalyticsPage';
import EvidencePage from './pages/EvidencePage';
import UsersPage from './pages/UsersPage';
import SettingsPage from './pages/SettingsPage';
import NotFoundPage from './pages/NotFoundPage';
import { useAuthStore } from './store/authStore';

function App() {
  const { isAuthenticated } = useAuthStore();

  return (
    <BrowserRouter>
      <Routes>
        {/* Public route */}
        <Route path="/login" element={
          isAuthenticated ? <Navigate to="/dashboard" replace /> : <LoginPage />
        } />

        {/* Protected routes */}
        <Route path="/" element={
          <ProtectedRoute>
            <Layout><Navigate to="/dashboard" replace /></Layout>
          </ProtectedRoute>
        } />

        <Route path="/dashboard" element={
          <ProtectedRoute>
            <Layout><DashboardPage /></Layout>
          </ProtectedRoute>
        } />

        <Route path="/monitoring" element={
          <ProtectedRoute>
            <Layout><LiveMonitoringPage /></Layout>
          </ProtectedRoute>
        } />

        <Route path="/incidents" element={
          <ProtectedRoute>
            <Layout><IncidentsPage /></Layout>
          </ProtectedRoute>
        } />

        <Route path="/incidents/:id" element={
          <ProtectedRoute>
            <Layout><IncidentDetailPage /></Layout>
          </ProtectedRoute>
        } />

        <Route path="/evidence" element={
          <ProtectedRoute>
            <Layout><EvidencePage /></Layout>
          </ProtectedRoute>
        } />

        <Route path="/cameras" element={
          <ProtectedRoute>
            <Layout><CamerasPage /></Layout>
          </ProtectedRoute>
        } />

        <Route path="/analytics" element={
          <ProtectedRoute>
            <Layout><AnalyticsPage /></Layout>
          </ProtectedRoute>
        } />

        <Route path="/users" element={
          <ProtectedRoute requiredRole="admin">
            <Layout><UsersPage /></Layout>
          </ProtectedRoute>
        } />

        <Route path="/settings" element={
          <ProtectedRoute requiredRole="admin">
            <Layout><SettingsPage /></Layout>
          </ProtectedRoute>
        } />

        {/* 404 */}
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
