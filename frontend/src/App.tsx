import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth, ROLE_HOME } from "./lib/auth";
import { Role } from "./lib/api";
import Navbar from "./components/Navbar";
import LandingPage from "./pages/LandingPage";
import Login from "./pages/Login";
import Register from "./pages/Register";
import PatientHome from "./pages/PatientHome";
import HospitalDashboard from "./pages/HospitalDashboard";
import DoctorDashboard from "./pages/DoctorDashboard";
import FamilyPortal from "./pages/FamilyPortal";

function Protected({ role, children }: { role: Role; children: JSX.Element }) {
  const { me, loading } = useAuth();
  if (loading) return null;
  if (!me) return <Navigate to="/login" replace />;
  if (me.role !== role) return <Navigate to={ROLE_HOME[me.role]} replace />;
  return children;
}

export default function App() {
  return (
    <>
      <Navbar />
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/patient" element={<Protected role="patient"><PatientHome /></Protected>} />
        <Route path="/hospital" element={<Protected role="hospital"><HospitalDashboard /></Protected>} />
        <Route path="/doctor" element={<Protected role="doctor"><DoctorDashboard /></Protected>} />
        <Route path="/family" element={<Protected role="family"><FamilyPortal /></Protected>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  );
}
