import { useEffect } from 'react';
import { RouterProvider, createHashRouter } from "react-router-dom";
import { useRootStore } from '../state/root-store';
import { DeploymentPage } from './pages/DeploymentPage';
import { HomePage } from './pages/HomePage';
import { ErrorPage } from './pages/ErrorPage';
import { DeploymentEditorDialog } from './components/DeploymentEditorDialog';
import { TopicViewerModal } from './components/TopicViewerModal';

const router = createHashRouter([
    {
        path: "/deployment/:id",
        element: <DeploymentPage />,
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
]);

export function App() {
    const rootStore = useRootStore();

    useEffect(() => {
        rootStore.taskManager.loadTaskHosts()
        rootStore.deployment.loadAll();
    }, []);

    return (
        <>
            <RouterProvider router={router} />
            <TopicViewerModal/>
            <DeploymentEditorDialog/>
        </>
    );
}

