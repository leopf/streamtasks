import { Box, Stack } from '@mui/material';
import { useEffect } from 'react';
import { useTaskManager } from '../state/task-manager';
import { RouterProvider, createHashRouter } from "react-router-dom";
import { useRootStore } from '../state/root-store';
import { DeploymentPage } from './pages/DeploymentPage';
import { HomePage } from './pages/HomePage';
import { ErrorPage } from './pages/ErrorPage';

const router = createHashRouter([
    {
        path: "/deployment/:id",
        element: <DeploymentPage />,
        errorElement: <ErrorPage/>
    },
    {
        path: "/",
        element: <HomePage/>
    },
    {
        path: "*",
        element: <ErrorPage/>
    }
]);

export function App() {
    const taskManager = useTaskManager();
    const rootStore = useRootStore();

    useEffect(() => {
        taskManager.loadTaskHosts()
        rootStore.loadDeployments();
    }, []);

    return (<RouterProvider router={router}/>);
}

