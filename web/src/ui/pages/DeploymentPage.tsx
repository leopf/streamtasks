import { Box, Button, CircularProgress, Divider, IconButton, Stack, Typography } from "@mui/material";
import { observer, useLocalObservable } from "mobx-react-lite";
import { TaskSelectionMenu } from "../TaskSelectionMenu";
import { NodeEditor } from "../NodeEditor";
import { useParams } from "react-router-dom";
import { useEffect } from "react";
import { DeploymentContext, DeploymentManager } from "../../state/deployment-manager";
import { useRootStore } from "../../state/root-store";
import { PageLayout } from "../Layout";
import { Edit as EditIcon, PlayArrow as PlayArrowIcon, Stop } from "@mui/icons-material";
import { StatusBadge } from "../components/StatusBadge";

export const DeploymentPage = observer(() => {
    const params = useParams();
    const rootStore = useRootStore();
    const state = useLocalObservable(() => ({
        deployment: undefined as undefined | DeploymentManager,
        notFound: false
    }));

    useEffect(() => {
        if (!params.id) {
            state.notFound = true;
            return;
        }
        let disposed = false;
        rootStore.deployment.createManager(params.id).then(deplyoment => {
            if (disposed) return;
            if (deplyoment) {
                state.deployment = deplyoment;
                state.deployment.loadTasks();
            }
            else { state.notFound = true; }
        });

        return () => {
            disposed = true;
            state.deployment?.destroy();
            state.deployment = undefined;
            state.notFound = false;
        };
    }, [params.id]);

    if (!state.deployment) {
        if (state.notFound) {
            throw new Error("Not found");
        }
        else {
            return (
                <PageLayout>
                    <Stack alignItems={"center"} justifyContent="center" height="100%" width="100%"><CircularProgress /></Stack>
                </PageLayout>);
        }
    }

    return (
        <PageLayout headerContent={(
            <>
                <Divider color="inherit" orientation="vertical" sx={{ marginX: 3, height: "1rem", borderColor: "#fff" }} />
                <Typography marginRight={1}>{state.deployment.label}</Typography>
                <IconButton color="inherit" size="small" onClick={() => rootStore.uiControl.editingDeployment = state.deployment?.deployment}><EditIcon fontSize="inherit" /></IconButton>
                <Box flex={1} />
                {state.deployment.running ? (
                    <>
                        <Stack spacing={0.5} direction="row" marginRight={2}>
                            {Object.entries({}).filter(([_, v]) => v).map(([k, v]) => <StatusBadge key={k} status={k as any} text={String(v)} round />)}
                        </Stack>
                        <Button color="inherit" startIcon={<Stop />} variant="text" onClick={() => state.deployment?.stop()}>Stop</Button>
                    </>
                ) : (
                    <Button color="inherit" startIcon={<PlayArrowIcon />} variant="text" onClick={() => state.deployment?.start()}>Start</Button>
                )}
            </>
        )}>
            <DeploymentContext.Provider value={state.deployment}>
                <Box width="100%" height="100%" position="relative">
                    <Box width={"100%"} height={"100%"} position="absolute"><NodeEditor /></Box>
                    <Box height={"100%"} sx={theme => ({ [theme.breakpoints.up("xl")]: { width: "15%" }, [theme.breakpoints.down("xl")]: { width: "20%" }, [theme.breakpoints.down("md")]: { width: "25%" } })} position="absolute">
                        <TaskSelectionMenu />
                    </Box>
                </Box>
            </DeploymentContext.Provider>
        </PageLayout>
    )
});