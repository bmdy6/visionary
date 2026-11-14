import { useEffect, useState } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import ForgotPasswordPage from "./pages/ForgotPasswordPage";
import AdminPage from "./pages/AdminPage";
import CreationPage from "./pages/CreationPage";
import ProfilePage from "./pages/ProfilePage";
import HistoryPage from "./pages/HistoryPage";
import PrivateRoute from "./components/PrivateRoute";
import Layout from "./components/Layout";
import DemoNotice from "./components/DemoNotice";
import "./App.css";

export default function App() {
  const [isMobile, setIsMobile] = useState(window.innerWidth <= 1024);
  useEffect(() => {
    const resize = () => setIsMobile(window.innerWidth <= 1024);
    window.addEventListener("resize", resize);
    return () => window.removeEventListener("resize", resize);
  }, []);
  const protectedPage = (page) => (
    <PrivateRoute>
      <Layout>
        <DemoNotice />
        {page}
      </Layout>
    </PrivateRoute>
  );
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route
          path="/"
          element={protectedPage(<CreationPage isMobile={isMobile} />)}
        />
        <Route path="/history" element={protectedPage(<HistoryPage />)} />
        <Route path="/profile" element={protectedPage(<ProfilePage />)} />
        <Route path="/admin" element={protectedPage(<AdminPage />)} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
