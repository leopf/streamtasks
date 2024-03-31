import React, { } from 'react';
import { Box, Grid, Stack } from '@mui/material';
import { NodeEditor } from './NodeEditor';
import { TaskSelectionMenu } from './TaskSelectionMenu';

export function App() {
    return (
        <Stack direction="column" alignItems="stretch" sx={{ width: "100vw", height: "100vh" }}>
            <Box bgcolor="green" sx={{ minHeight: 12, height: 12 }}></Box>
            <Stack direction="row" flex={1} alignItems="stretch">
                <Box flex={1} position="relative">
                    <Box height={"100%"} width={"100%"} position="absolute">
                        <TaskSelectionMenu />
                    </Box>
                </Box>
                <Box flex={6}><NodeEditor/></Box>
            </Stack>
        </Stack>
    );
}

