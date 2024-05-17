import { Box, CircularProgress, Stack, Typography } from "@mui/material";
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

export function LoadingPage(props: { text: string }) {
    return (
        <PageLayout>
            <Stack alignItems={"center"} justifyContent="center" height="100%" width="100%" spacing={2}>
                <CircularProgress />
                <Typography>{props.text}</Typography>
            </Stack>
        </PageLayout>
    );
}