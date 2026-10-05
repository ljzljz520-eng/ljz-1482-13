import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import Layout from "./components/Layout";
import ErrorBoundary from "./components/ErrorBoundary";
import { Toaster } from "react-hot-toast";
import Login from "./pages/Login";
import Characters from "./pages/Characters";
import CharacterDetail from "./pages/CharacterDetail";
import Scripts from "./pages/Scripts";
import Review from "./pages/Review";
import Assets from "./pages/Assets";
import Exports from "./pages/Exports";
import { useAuth } from "./store/auth";
import { ReactNode } from "react";

function RequireAuth({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const location = useLocation();
  if (!user) return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  return <>{children}</>;
}

const App = () => {
  return (
    <BrowserRouter>
      <ErrorBoundary>
        <Layout>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/" element={<RequireAuth><Characters /></RequireAuth>} />
            <Route path="/characters/:id" element={<RequireAuth><CharacterDetail /></RequireAuth>} />
            <Route path="/scripts" element={<RequireAuth><Scripts /></RequireAuth>} />
            <Route path="/review" element={<RequireAuth><Review /></RequireAuth>} />
            <Route path="/assets" element={<RequireAuth><Assets /></RequireAuth>} />
            <Route path="/exports" element={<RequireAuth><Exports /></RequireAuth>} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
          <Toaster position="top-right" toastOptions={{ duration: 3000 }} />
        </Layout>
      </ErrorBoundary>
    </BrowserRouter>
  );
};

export default App;
