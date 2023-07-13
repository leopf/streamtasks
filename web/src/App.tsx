import { observer } from "mobx-react";
import { useEffect } from "react";
import { state } from "./state";
import React from "react";
import { Route, RouterProvider, createBrowserRouter, createRoutesFromElements } from "react-router-dom";
import { DeploymentPage } from "./pages/DeploymentPage";
import { NewDeploymentPage } from "./pages/NewDeploymentPage";
import { ThemeProvider, createTheme } from "@mui/material";

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

const theme = createTheme({
    
});

export const App = observer(() => {
    useEffect(() => {
        state.init();
    }, []);

    if (!state.initialized) {
        return <div>Loading...</div>;
    }

    return (
        <RouterProvider router={router}/>
    )
})