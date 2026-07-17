import { Routes, Route } from 'react-router-dom';
import Layout from '@/components/Layout';
import Login from '@/pages/Login';
import Dashboard from '@/pages/Dashboard';
import Platforms from '@/pages/Platforms';
import Think from '@/pages/Think';
import Loops from '@/pages/Loops';
import Campaigns from '@/pages/Campaigns';

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<Layout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/platforms" element={<Platforms />} />
        <Route path="/think" element={<Think />} />
        <Route path="/loops" element={<Loops />} />
        <Route path="/campaigns" element={<Campaigns />} />
      </Route>
    </Routes>
  );
}
