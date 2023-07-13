import { useEffect, useMemo, useState } from "react";
import { DeploymentState } from "../state/deployment";
import { state } from "../state";
import { observer } from "mobx-react";
import { useParams, useNavigate } from "react-router-dom";
import React from "react";
import { Box, Divider, IconButton, Stack, SxProps, Theme, Tooltip, Typography } from "@mui/material";
import { Clear as ClearIcon, PlayArrow as PlayIcon, Pause as PauseIcon, Cached as ReloadIcon, ReceiptLong as LogsIcon } from "@mui/icons-material";
import { TaskTemplateList } from "../components/stateful/TaskTemplateList";
import { NodeEditor } from "../components/stateless/NodeEditor";
import { TitleBar } from "../components/stateful/TitleBar";
import { DeploymentLabelEditor } from "../components/stateless/DeploymentLabelEditor";
import { LoadingButton } from '@mui/lab';
import { SystemLogDisplay } from "../components/stateful/SystemLogDisplay";
import { Task } from "../lib/task";

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

const TaskEditor = observer((props: { task: Task, deployment: DeploymentState, onUnselect: () => void }) => {
    return (
        <div>hi</div>
    );
});

function TaskEditorOverlay(props: { children: React.ReactNode, onClose?: () => void }) {
    return (
        <Box sx={{
            position: "absolute",
            top: 5,
            right: 5,
            width: "30%",
            maxHeight: "calc(100% - 10px)",
            backgroundColor: "#fff",
            boxShadow: "0px 0px 10px 0px rgba(0,0,0,0.3)",
            borderRadius: 1,
        }}>
            <Stack direction="column" height={"100%"} width={"100%"} maxHeight={"100%"}>
                <Stack direction="row" alignItems={"center"}>
                    <Box flex={1} />
                    <Box sx={{
                        borderRadius: "50%",
                        cursor: "pointer",
                        userSelect: "none",
                        padding: "1px",
                        ":hover": {
                            backgroundColor: "#eee"
                        }
                    }} onClick={props.onClose}>
                        <ClearIcon sx={{ display: "block" }} width={"8px"} height={"8px"}/>
                    </Box>
                </Stack>
                <Divider />
                <Box flex={1} overflow="hidden">{props.children}</Box>
            </Stack>
        </Box>
    );
}

export const DeploymentPage = observer((props: {}) => {
    const [deployment, setDeployment] = useState<DeploymentState | undefined>()
    const [editLabel, setEditLabel] = useState<boolean>(false)
    const [logsOpen, setLogsOpen] = useState<boolean>(false)
    const [selectedTaskId, setSelectedTaskId] = useState<string | undefined>(undefined)
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

    useEffect(() => {
        if (!deployment) {
            return;
        }

        deployment.editor.on("selected", id => {
            console.log("selected", id);
            setSelectedTaskId(id)
        });
    }, [deployment])

    const selectedTask = useMemo(() => {
        if (!deployment || !selectedTaskId) {
            return undefined;
        }
        return deployment.getTaskById(selectedTaskId);
    }, [deployment, selectedTaskId])

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
                    <Tooltip title="logs">
                        <IconButton size="small" sx={{ marginRight: 1 }} onClick={() => setLogsOpen(v => !v)}>
                            <LogsIcon htmlColor="#fff" />
                        </IconButton>
                    </Tooltip>
                    <DeploymentStatusButton deployment={deployment} />
                    <Box width={"5px"} />
                </Stack>
            </TitleBar>
            <Box flex={1} sx={{ overflowY: "hidden" }} width="100%">
                <Stack direction="row" height="100%" maxHeight="100%" maxWidth="100%">
                    <TaskTemplateList onSelect={(t) => deployment.createTaskFromTemplate(t)} />
                    <Box flex={6} height={"100%"} sx={{
                        position: "relative",
                    }}>
                        <NodeEditor editor={deployment.editor} />
                        {!!selectedTask && (
                            <TaskEditorOverlay onClose={() => setSelectedTaskId(undefined)}>
                                <TaskEditor deployment={deployment} task={selectedTask} onUnselect={() => setSelectedTaskId(undefined)} />
                            </TaskEditorOverlay>
                        )}
                    </Box>
                </Stack>
            </Box>
        </Stack>
    );
});