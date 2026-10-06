import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import type { ReactElement } from "react";
import Layout from "./components/Layout";
import ErrorBoundary from "./components/ErrorBoundary";
import { Toaster } from "react-hot-toast";
import { useAuthStore } from "@/store/authStore";
import LoginPage from "./pages/auth/LoginPage";
import CharacterListPage from "./pages/characters/CharacterListPage";
import CharacterDetailPage from "./pages/characters/CharacterDetailPage";
import ScriptListPage from "./pages/scripts/ScriptListPage";
import ScriptDetailPage from "./pages/scripts/ScriptDetailPage";
import ReviewPage from "./pages/reviews/ReviewPage";
import ImageLibraryPage from "./pages/ImageLibraryPage";
import AdminPage from "./pages/AdminPage";

const Protected = ({ children }: { children: ReactElement }) => {
  const { hydrated, hydrate, user } = useAuthStore();
  if (!hydrated) {
    hydrate();
    return null;
  }
  if (!user) return <Navigate to="/login" replace />;
  return children;
};

const App = () => (
  <BrowserRouter>
    <ErrorBoundary>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/characters"
          element={<Protected><Layout><CharacterListPage /></Layout></Protected>}
        />
        <Route
          path="/characters/:id"
          element={<Protected><Layout><CharacterDetailPage /></Layout></Protected>}
        />
        <Route path="/scripts" element={<Protected><Layout><ScriptListPage /></Layout></Protected>} />
        <Route
          path="/scripts/:id"
          element={<Protected><Layout><ScriptDetailPage /></Layout></Protected>}
        />
        <Route path="/reviews" element={<Protected><Layout><ReviewPage /></Layout></Protected>} />
        <Route path="/images" element={<Protected><Layout><ImageLibraryPage /></Layout></Protected>} />
        <Route path="/admin" element={<Protected><Layout><AdminPage /></Layout></Protected>} />
        <Route path="*" element={<Navigate to="/characters" replace />} />
      </Routes>
      <Toaster position="top-right" toastOptions={{ duration: 3200 }} />
    </ErrorBoundary>
  </BrowserRouter>
);

export default App;
