import { BrowserRouter, Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import Listings from "./pages/Listings";
import Login from "./pages/Login";
import Deal from "./pages/Deal";
import Sell from "./pages/Sell";
import Account from "./pages/Account";
import Activity from "./pages/Activity";
import Results from "./pages/Results";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Listings />} />
          <Route path="/login" element={<Login />} />
          <Route path="/deal/:id" element={<Deal />} />
          <Route path="/sell" element={<Sell />} />
          <Route path="/account" element={<Account />} />
          <Route path="/activity" element={<Activity />} />
          <Route path="/results" element={<Results />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
