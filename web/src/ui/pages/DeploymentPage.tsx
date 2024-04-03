import { Box } from "@mui/material";
import { observer, useLocalObservable } from "mobx-react-lite";
import { TaskSelectionMenu } from "../TaskSelectionMenu";
import { NodeEditor } from "../NodeEditor";
import { useParams } from "react-router-dom";
import { useEffect, useMemo } from "react";
import { DeploymentContext, DeploymentState } from "../../state/deployment";
import { useTaskManager } from "../../state/task-manager";
import { useRootStore } from "../../state/root-store";

export const DeploymentPage = observer(() => {
    const params = useParams();
    const taskManager = useTaskManager();
    const rootStore = useRootStore();
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
        rootStore.getDeployment(params.id).then(res => {
            if (disposed) return;
            if (res) {
                state.deployment = new DeploymentState(res, taskManager);
                state.deployment.loadTasks();
            }
            else {
                state.notFound = true;
            }
        })
    }, [params.id])

    if (!state.deployment) {
        if (state.notFound) {
            return "not found";
        }
        else {
            return "loading"
        }
    }

    return (
        <DeploymentContext.Provider value={state.deployment}>

            <Box width="100%" height="100%" position="relative">
                <Box width={"100%"} height={"100%"} position="absolute"><NodeEditor /></Box>
                <Box height={"100%"} sx={theme => ({ [theme.breakpoints.up("xl")]: { width: "15%" }, [theme.breakpoints.down("xl")]: { width: "20%" }, [theme.breakpoints.down("md")]: { width: "25%" } })} position="absolute">
                    <TaskSelectionMenu />
                </Box>
            </Box>
        </DeploymentContext.Provider>
    )
});