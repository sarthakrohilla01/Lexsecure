import React from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { DashboardLayout } from './layouts/DashboardLayout';
import { LoginPage } from './pages/LoginPage';
import { DashboardPage } from './pages/DashboardPage';
import { DocumentsPage } from './pages/DocumentsPage';
import { DocumentDetailPage } from './pages/DocumentDetailPage';
import { IntegrityLedgerPage } from './pages/IntegrityLedgerPage';
import { AISearchPage } from './pages/AISearchPage';
import { AIAssistantPage } from './pages/AIAssistantPage';
import { CasesPage } from './pages/CasesPage';
import { CaseDetailPage } from './pages/CaseDetailPage';
import { AuditTrailPage } from './pages/AuditTrailPage';
import { AdminPage } from './pages/AdminPage';
import { LeakInvestigatorPage } from './pages/LeakInvestigatorPage';
import { GuidePage } from './pages/GuidePage';
import { NotFoundPage } from './pages/NotFoundPage';

const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const { user, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center text-cyan-400">
        Loading LEXSECURE Environment...
      </div>
    );
  }

  if (!user) {
    // The guide stays readable without a session so a first-time visitor
    // can learn the system before being asked to sign in.
    if (location.pathname === '/guide') return <>{children}</>;
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
};

const App = () => {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />

          <Route path="/" element={<ProtectedRoute><DashboardLayout /></ProtectedRoute>}>
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="dashboard" element={<DashboardPage />} />
            <Route path="cases" element={<CasesPage />} />
            <Route path="cases/:id" element={<CaseDetailPage />} />
            <Route path="documents" element={<DocumentsPage />} />
            <Route path="documents/:id" element={<DocumentDetailPage />} />
            <Route path="integrity" element={<IntegrityLedgerPage />} />
            <Route path="search" element={<AISearchPage />} />
            <Route path="assistant" element={<AIAssistantPage />} />
            <Route path="audit" element={<AuditTrailPage />} />
            <Route path="admin" element={<AdminPage />} />
            <Route path="leak" element={<LeakInvestigatorPage />} />
            <Route path="guide" element={<GuidePage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
};

export default App;
