import { AppBar, Box, Button, Grid, IconButton, Stack, Toolbar, Typography } from '@mui/material';
import { NodeEditor } from './NodeEditor';
import { TaskSelectionMenu } from './TaskSelectionMenu';
import { Menu as MenuIcon } from '@mui/icons-material';
import { useEffect, useState } from 'react';
import { GlobalStateContext, useGlobalState } from '../state';

export function App() {
    const [menuActive, setMenuActive] = useState(true);
    const state = useGlobalState();

    useEffect(() => {
        state.taskManager.loadTaskHosts()
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
            <Stack direction="row" flex={1} alignItems="stretch">
                {menuActive && (
                    <Box flex={1} position="relative">
                        <Box height={"100%"} width={"100%"} position="absolute">
                            <TaskSelectionMenu />
                        </Box>
                    </Box>
                )}
                <Box flex={6}><NodeEditor /></Box>
            </Stack>
        </Stack>
    );
}

