import { AppBar, Box, IconButton, Stack, Toolbar, Typography } from '@mui/material';
import { Menu as MenuIcon } from '@mui/icons-material';
import { useEffect, useState } from 'react';
import { useTaskManager } from '../state/task-manager';
import { RouterProvider, createHashRouter } from "react-router-dom";
import { useRootStore } from '../state/root-store';
import { DeploymentPage } from './pages/DeploymentPage';
import { HomePage } from './pages/HomePage';

const router = createHashRouter([
    {
        path: "/deployment/:id",
        element: <DeploymentPage />,
    },
    {
        path: "/",
        element: <HomePage/>
    }
]);

export function App() {
    const [menuActive, setMenuActive] = useState(true);
    const taskManager = useTaskManager();
    const rootStore = useRootStore();

    useEffect(() => {
        taskManager.loadTaskHosts()
        rootStore.loadDeployments();
    }, []);

    return (
        <Stack direction="column" alignItems="stretch" sx={{ width: "100vw", height: "100vh" }}>
            <AppBar position="static">
                <Toolbar variant="dense">
                    <IconButton
                        onClick={() => setMenuActive(pv => !pv)}
                        size="large"
                        edge="start"
                        color="inherit"
                        aria-label="menu"
                        sx={{ mr: 2 }}
                    >
                        <MenuIcon />
                    </IconButton>
                    <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
                        streamtasks
                    </Typography>
                </Toolbar>
            </AppBar>
            <Box flex={1} bgcolor="#eee">
                <RouterProvider router={router}/>
            </Box>
        </Stack>
    );
}

