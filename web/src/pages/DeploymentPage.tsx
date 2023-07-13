import { useEffect, useState } from "react";
import { DeploymentState } from "../state/deployment";
import { state } from "../state";
import { observer } from "mobx-react";
import { useParams, useNavigate } from "react-router-dom";
import React from "react";
import { AppBar, Box, IconButton, Stack, Typography } from "@mui/material";
import { Edit as EditIcon } from "@mui/icons-material";
import { TaskTemplateList } from "../components/stateful/TaskTemplateList";
import { NodeEditor } from "../components/stateless/NodeEditor";
import { TitleBar } from "../components/stateful/TitleBar";
import { DeploymentLabelEditor } from "../components/stateless/DeploymentLabelEditor";

export const DeploymentPage = observer((props: {}) => {
    const [deployment, setDeployment] = useState<DeploymentState | undefined>()
    const [editLabel, setEditLabel] = useState<boolean>(false)
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
            <DeploymentLabelEditor open={editLabel} value={deployment.label} onChange={(v) => deployment.label = v} onClose={() => setEditLabel(false)} />
            <TitleBar>
                <Stack height="100%" direction="row" alignItems="center">
                    <Typography sx={{
                        lineHeight: 1,
                        cursor: "text",
                        ":hover": {
                            paddingX: 0.5,
                            marginX: -0.5,
                            paddingY: 0.3,
                            marginY: -0.3,
                            borderRadius: 1.25,
                            backgroundColor: "rgba(0, 0, 0, 0.2)"
                        }
                    }} fontSize={18} onClick={() => setEditLabel(true)} >{deployment.label}</Typography>
                </Stack>
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