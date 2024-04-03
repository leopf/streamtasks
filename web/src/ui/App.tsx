import { AppBar, Box, IconButton, Stack, Toolbar, Typography } from '@mui/material';
import { NodeEditor } from './NodeEditor';
import { TaskSelectionMenu } from './TaskSelectionMenu';
import { Menu as MenuIcon } from '@mui/icons-material';
import { useEffect, useMemo, useState } from 'react';
import { useTaskManager } from '../state/task-manager';
import { DeploymentContext, DeploymentState } from '../state/deployment';
import { v4 as uuidv4 } from "uuid";

export function App() {
    const [menuActive, setMenuActive] = useState(true);
    const taskManager = useTaskManager();

    useEffect(() => {
        taskManager.loadTaskHosts()
    }, []);

    const deployment = useMemo(() => new DeploymentState(uuidv4(), taskManager), []);

    return (
        <DeploymentContext.Provider value={deployment}>
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
                <Box flex={1} position="relative" bgcolor={"#eee"}>
                    <Box width={"100%"} height={"100%"} position="absolute"><NodeEditor /></Box>
                    <Box height={"100%"} sx={theme => ({ [theme.breakpoints.up("xl")]: { width: "15%" }, [theme.breakpoints.down("xl")]: { width: "20%" }, [theme.breakpoints.down("md")]: { width: "25%" } })} position="absolute">
                        <TaskSelectionMenu />
                    </Box>
                </Box>
            </Stack>
        </DeploymentContext.Provider>
    );
}

