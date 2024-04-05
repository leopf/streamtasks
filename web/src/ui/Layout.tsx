import { Box, Stack } from "@mui/material";
import { Header } from "./components/Header";
import React from "react";

export function PageLayout(props: React.PropsWithChildren<{ headerContent?: React.ReactNode }>) {
    return (
        <Stack direction="column" alignItems="stretch" sx={{ width: "100vw", height: "100vh" }}>
            <Header>{props.headerContent}</Header>
            <Box flex={1} bgcolor="#eee">
                {props.children}
            </Box>
        </Stack>
    );
}