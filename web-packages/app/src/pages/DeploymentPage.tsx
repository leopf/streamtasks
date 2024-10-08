import { Box, Button, CircularProgress, IconButton, Stack, Typography } from "@mui/material";
import { observer, useLocalObservable } from "mobx-react-lite";
import { TaskSelectionMenu } from "../components/TaskSelectionMenu";
import { NodeEditor } from "../components/NodeEditor";
import { useParams } from "react-router-dom";
import { useEffect } from "react";
import { DeploymentContext, DeploymentManager } from "../state/deployment-manager";
import { useRootStore } from "../state/root-store";
import { PageLayoutHeader } from "../Layout";
import { Edit as EditIcon, PlayArrow as PlayArrowIcon, Stop as StopIcon } from "@mui/icons-material";
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
                <Stack alignItems={"center"} justifyContent="center" height="100%" width="100%"><CircularProgress /></Stack>
            );
        }
    }

    return (
        <>
            <PageLayoutHeader>
                <>
                    <Typography marginRight={1}>{state.deployment.label}</Typography>
                    <IconButton color="inherit" size="small" onClick={() => rootStore.uiControl.editingDeployment = state.deployment?.deployment}><EditIcon fontSize="inherit" /></IconButton>
                    <Box flex={1} />
                    {state.deployment.running ? (
                        <>
                            <Stack spacing={0.5} direction="row" marginRight={2}>
                                {Object.entries({}).filter(([_, v]) => v).map(([k, v]) => <StatusBadge key={k} status={k as any} text={String(v)} />)}
                            </Stack>
                            <Button color="inherit" startIcon={<StopIcon />} variant="text" onClick={() => state.deployment?.stop()}>Stop</Button>
                        </>
                    ) : (
                        <Button color="inherit" startIcon={<PlayArrowIcon />} variant="text" onClick={() => state.deployment?.start()}>Start</Button>
                    )}
                </>
            </PageLayoutHeader>
            <DeploymentContext.Provider value={state.deployment}>
                <Box width="100%" height="100%" position="relative">
                    <Box width={"100%"} height={"100%"} position="absolute"><NodeEditor /></Box>
                    <Box height={"100%"} width="min-content" position="absolute">
                        <TaskSelectionMenu />
                    </Box>
                </Box>
            </DeploymentContext.Provider>
        </>
    )
});