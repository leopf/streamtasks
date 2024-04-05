import { Box, Button, Divider, IconButton, Typography } from "@mui/material";
import { observer, useLocalObservable } from "mobx-react-lite";
import { TaskSelectionMenu } from "../TaskSelectionMenu";
import { NodeEditor } from "../NodeEditor";
import { useParams } from "react-router-dom";
import { useEffect, useMemo } from "react";
import { DeploymentContext, DeploymentState } from "../../state/deployment";
import { useTaskManager } from "../../state/task-manager";
import { useRootStore } from "../../state/root-store";
import { PageLayout } from "../Layout";
import { Edit as EditIcon, PlayArrow as PlayArrowIcon, Stop } from "@mui/icons-material";
import { useUIControl } from "../../state/ui-control-store";

export const DeploymentPage = observer(() => {
    const params = useParams();
    const taskManager = useTaskManager();
    const rootStore = useRootStore();
    const uiControl = useUIControl();
    const state = useLocalObservable(() => ({
        deployment: undefined as undefined | DeploymentState,
        notFound: false
    }));

    useEffect(() => {
        if (!params.id) {
            state.notFound = true;
            return;
        }
        state.notFound = false;
        state.deployment = undefined;
        let disposed = false;
        rootStore.loadDeployment(params.id).then(res => {
            if (disposed) return;
            if (res) {
                state.deployment = new DeploymentState(res.id, rootStore, taskManager);
                state.deployment.loadTasks();
            }
            else {
                state.notFound = true;
            }
        })
    }, [params.id])

    if (!state.deployment) {
        if (state.notFound) {
           throw new Error("Not found");
        }
        else {
            return "loading"
        }
    }

    return (
        <PageLayout headerContent={(
            <>  
                <Divider color="inherit" orientation="vertical" sx={{ marginX: 3, height: "1rem", borderColor: "#fff" }}/>
                <Typography marginRight={1}>{state.deployment.label}</Typography>
                <IconButton color="inherit" size="small" onClick={() => uiControl.editingDeployment = state.deployment?.deployment}><EditIcon fontSize="inherit"/></IconButton>
                <Box flex={1} />
                {state.deployment.running ? (
                    <Button color="inherit" startIcon={<Stop />} variant="text" onClick={() => state.deployment?.stop()}>Stop</Button>
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