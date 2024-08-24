import { Box, CircularProgress, Stack, Typography } from "@mui/material";
import { Header } from "./components/Header";
import React from "react";
import { DashboardEditorDialog } from "./components/DashboardEditorDialog";
import { DeploymentEditorDialog } from "./components/DeploymentEditorDialog";
import { TopicViewerModal } from "./components/TopicViewerModal";
import { Outlet } from "react-router-dom";

export function PageLayout(props: React.PropsWithChildren<{ headerContent?: React.ReactNode }>) {
    return (
        <>
            <Stack direction="column" alignItems="stretch" sx={{ width: "100vw", height: "100vh", overflowY: "auto" }}>
                <Header>{props.headerContent}</Header>
                <Box flex={1} bgcolor="#2a2a2a" color={theme => theme.palette.text.primary}>
                    <Outlet/>
                </Box>
            </Stack>
            <TopicViewerModal />
            <DeploymentEditorDialog />
            <DashboardEditorDialog />
        </>
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