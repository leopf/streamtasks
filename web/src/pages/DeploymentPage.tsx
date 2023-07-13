import { useEffect, useMemo, useState } from "react";
import { DeploymentState } from "../state/deployment";
import { state } from "../state";
import { observer } from "mobx-react";
import { useParams, useNavigate } from "react-router-dom";
import React from "react";
import { AppBar, Box, Button, Icon, IconButton, Stack, SxProps, Theme, Typography } from "@mui/material";
import { Edit as EditIcon, PlayArrow as PlayIcon, Pause as PauseIcon, Cached as ReloadIcon, ReceiptLong as LogsIcon } from "@mui/icons-material";
import { TaskTemplateList } from "../components/stateful/TaskTemplateList";
import { NodeEditor } from "../components/stateless/NodeEditor";
import { TitleBar } from "../components/stateful/TitleBar";
import { DeploymentLabelEditor } from "../components/stateless/DeploymentLabelEditor";
import { LoadingButton } from '@mui/lab';
import { AppModal } from "../components/stateless/AppModel";
import { SystemLogDisplay } from "../components/stateful/SystemLogDisplay";

const statusButtonStyles: SxProps<Theme> = {
    backgroundColor: "#eee",
    color: "#000",
    ":hover": {
        backgroundColor: "#ddd"
    },
    ":disabled": {
        backgroundColor: "#ccc",
        color: "#555"
    }
};

const DeploymentStatusButton = observer((props: { deployment: DeploymentState }) => {
    const [isLoading, setLoading] = useState<boolean>(false);

    const text = `${props.deployment.status === "running" ? "stop" : "start"} (${props.deployment.status})`;
    const icon = props.deployment.status === "running" ? <PauseIcon /> : <PlayIcon />;

    return (
        <LoadingButton sx={statusButtonStyles} size="small" variant="contained" startIcon={icon} loadingPosition="start" loading={isLoading} onClick={async () => {
            setLoading(true);
            if (props.deployment.status === "running") {
                await props.deployment.stop();
            }
            else {
                await props.deployment.start();
            }
            setLoading(false);
        }}>
            {text}
        </LoadingButton>
    )
})

export const DeploymentPage = observer((props: {}) => {
    const [deployment, setDeployment] = useState<DeploymentState | undefined>()
    const [editLabel, setEditLabel] = useState<boolean>(false)
    const [logsOpen, setLogsOpen] = useState<boolean>(false)
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
        <Stack direction="column" height={"100%"} maxHeight={"100%"}>
            <DeploymentLabelEditor open={editLabel} value={deployment.label} onChange={(v) => deployment.label = v} onClose={() => setEditLabel(false)} />
            <SystemLogDisplay open={logsOpen} onClose={() => setLogsOpen(false)} />
            <TitleBar>
                <Stack height="100%" direction="row" alignItems="center" paddingY={0.35} boxSizing="border-box">
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
                    <IconButton sx={{ marginLeft: 1 }} size="small" onClick={() => deployment.reload()}>
                        <ReloadIcon htmlColor="#fff" />
                    </IconButton>
                    <Box flex={1} />
                    <IconButton size="small" sx={{ marginRight: 1 }} onClick={() => setLogsOpen(v => !v)}>
                        <LogsIcon htmlColor="#fff"/>
                    </IconButton>
                    <DeploymentStatusButton deployment={deployment} />
                    <Box width={"5px"} />
                </Stack>
            </TitleBar>
            <Box flex={1} sx={{ overflowY: "hidden" }} width="100%">
                <Stack direction="row" height="100%" maxHeight="100%" maxWidth="100%">
                    <TaskTemplateList onSelect={(t) => deployment.createTaskFromTemplate(t)} />
                    <Box flex={6} height={"100%"}>
                        <NodeEditor editor={deployment.editor} />
                    </Box>
                </Stack>
            </Box>
        </Stack>
    );
});