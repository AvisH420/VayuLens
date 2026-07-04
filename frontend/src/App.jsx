// VayuLens app shell: landing page at /, dashboard at /app.
// Routes are lazy so three.js ships only with the landing and
// maplibre only with the dashboard.
import { lazy, Suspense } from "react";
import { Routes, Route } from "react-router-dom";

const Landing = lazy(() => import("./components/landing/Landing.jsx"));
const Dashboard = lazy(() => import("./components/dashboard/Dashboard.jsx"));

export default function App() {
  return (
    <Suspense fallback={null}>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/app" element={<Dashboard />} />
      </Routes>
    </Suspense>
  );
}
