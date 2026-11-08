import { Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import { RequireAuth } from "./auth";
import Listings from "./pages/Listings";
import Login from "./pages/Login";
import NewListing from "./pages/NewListing";
import ListingDetail from "./pages/ListingDetail";
import Deal from "./pages/Deal";
import Account from "./pages/Account";
import Activity from "./pages/Activity";
import Results from "./pages/Results";
import Bid from "./pages/Bid";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Listings />} />
        <Route path="login" element={<Login />} />
        <Route path="listings/:id" element={<ListingDetail />} />
        <Route path="results" element={<Results />} />

        <Route element={<RequireAuth />}>
          <Route path="account" element={<Account />} />
          <Route path="deals/:id" element={<Deal />} />
          <Route path="activity" element={<Activity />} />
        </Route>

        <Route element={<RequireAuth role="seller" />}>
          <Route path="sell" element={<NewListing />} />
        </Route>

        <Route element={<RequireAuth role="buyer" />}>
          <Route path="bid" element={<Bid />} />
        </Route>

        <Route path="*" element={<p>Page not found.</p>} />
      </Route>
    </Routes>
  );
}
