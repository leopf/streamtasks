import { useEffect, useState } from "react";
import { DeploymentState } from "../state/deployment";
import { state } from "../state";
import { observer } from "mobx-react";
import { useParams, useNavigate } from "react-router-dom";
import React from "react";
import { AppBar, Box, Stack } from "@mui/material";
import { TaskTemplateList } from "../components/stateful/TaskTemplateList";
import { NodeEditor } from "../components/stateless/NodeEditor";
import { TitleBar } from "../components/stateful/TitleBar";

export const DeploymentPage = observer((props: { }) => {
    const [deployment, setDeployment] = useState<DeploymentState | undefined>()
    const params = useParams<"id">();
    const navigate = useNavigate();

    useEffect(() => {
        const id = params.id;
        if (id) {
            const deployment = state.getDeployment(id);
            if (deployment) {
                setDeployment(deployment);
                return () => {
                    deployment.destroy();
                }
            }
        }

        if (!deployment) {
            navigate("/deployment/new")
            return;
        }
    }, [params.id])

    if (!deployment) {
        return <div>Loading...</div>
    }

    return (
        <Stack direction="column">
            <TitleBar>
                Hello
            </TitleBar>
            <Stack direction="row">
                <TaskTemplateList />
                <Box flex={6} height={"100%"}>
                    <NodeEditor editor={deployment.editor} />
                </Box>
            </Stack>
        </Stack>
    );
});