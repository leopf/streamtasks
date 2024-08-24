import { useEffect, useState } from 'react';
import { RouterProvider, createHashRouter } from "react-router-dom";
import { useRootStore } from './state/root-store';
import { DeploymentPage } from './pages/DeploymentPage';
import { HomePage } from './pages/HomePage';
import { ErrorPage } from './pages/ErrorPage';
import { LoadingPage, PageLayout } from './Layout';
import { PathRegistrationPage } from './pages/PathRegistrationPage';
import { DashboardPage } from './pages/DashboardPage';

const router = createHashRouter([
    {
        element: <PageLayout/>,
        errorElement: <ErrorPage />,
        children: [
            {
                path: "/deployment/:id",
                element: <DeploymentPage />,
                errorElement: <ErrorPage />
            },
            {
                path: "/dashboard/:id",
                element: <DashboardPage />,
                errorElement: <ErrorPage />
            },
            {
                path: "/path-reg/:id",
                element: <PathRegistrationPage />,
                errorElement: <ErrorPage />
            },
            {
                path: "/",
                element: <HomePage />
            },
            {
                path: "*",
                element: <ErrorPage />
            }
        ]
    }
]);

export function App() {
    const [isInitialized, setInitialized] = useState(false);
    const rootStore = useRootStore();

    useEffect(() => { rootStore.init().then(() => setInitialized(true)) }, []);

    if (!isInitialized) {
        return <LoadingPage text='initializing' />
    }

    return (
        <>
            <RouterProvider router={router} />
        </>
    );
}

