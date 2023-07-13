import { observer } from "mobx-react";
import { useEffect } from "react";
import { state } from "./state";
import React from "react";
import { Route, RouterProvider, createBrowserRouter, createRoutesFromElements } from "react-router-dom";
import { DeploymentPage } from "./pages/DeploymentPage";
import { NewDeploymentPage } from "./pages/NewDeploymentPage";

const router = createBrowserRouter([
    {
        path: "/deployment/view/:id",
        element: <DeploymentPage/>
    },
    {
        path: "/deployment/new",
        element: <NewDeploymentPage/>
    }
]);

{/* <Route path="/deployment/view/:id" element={<DeploymentPage/>}/>,
<Route path="/deployment/new" element={<NewDeploymentPage/>}/> */}

export const App = observer(() => {
    useEffect(() => {
        state.init();
    }, []);

    if (!state.initialized) {
        return <div>Loading...</div>;
    }

    return <RouterProvider router={router}/>;
})