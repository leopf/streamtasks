import { Box, CircularProgress, Stack, Typography } from "@mui/material";
import { Header } from "./components/Header";
import React, { createContext, useContext, useEffect, useState } from "react";
import { DashboardEditorDialog } from "./components/DashboardEditorDialog";
import { DeploymentEditorDialog } from "./components/DeploymentEditorDialog";
import { TopicViewerModal } from "./components/TopicViewerModal";
import { Outlet } from "react-router-dom";

const PageLayoutContext = createContext({
    setHeaderContent: (content: React.ReactNode) => { },
});

export function PageLayout() {
    const [headerContent, setHeaderContent] = useState<React.ReactNode>(null);

    return (
        <PageLayoutContext.Provider value={{ setHeaderContent }}>
            <Stack direction="column" alignItems="stretch" sx={{ width: "100vw", height: "100vh", overflowY: "auto" }}>
                <Header>{headerContent}</Header>
                <Box flex={1} bgcolor="#2a2a2a" color={theme => theme.palette.text.primary}>
                    <Outlet />
                </Box>
            </Stack>
            <TopicViewerModal />
            <DeploymentEditorDialog />
            <DashboardEditorDialog />
        </PageLayoutContext.Provider>
    );
}

export function PageLayoutHeader(props: React.PropsWithChildren<{}>) {
    const { setHeaderContent } = useContext(PageLayoutContext);

    useEffect(() => {
        setHeaderContent(props.children);
        return () => setHeaderContent(null);
    }, [props.children, setHeaderContent]);

    return null;
}

export function LoadingPage(props: { text: string }) {
    return (
        <Stack alignItems={"center"} justifyContent="center" height="100%" width="100%" spacing={2}>
            <CircularProgress />
            <Typography>{props.text}</Typography>
        </Stack>
    );
}