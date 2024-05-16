import { Box, CircularProgress, Divider, IconButton, List, ListItemButton, ListItemIcon, ListItemText, Stack, Typography } from "@mui/material";
import { observer, useLocalObservable } from "mobx-react-lite";
import { Link, useParams } from "react-router-dom";
import { useEffect, useRef, useState } from "react";
import { useRootStore } from "../../state/root-store";
import { PageLayout } from "../Layout";
import { Edit as EditIcon, Terminal as TerminalIcon } from "@mui/icons-material";
import { Dashboard } from "../../types/dashboard";
import { reaction } from "mobx";
import { DeploymentManager } from "../../state/deployment-manager";
import { WindowEditorRenderer } from "../lib/window-editor/editor";
import cloneDeep from "clone-deep";

const DashboardEditor = observer((props: { dashboard: Dashboard, deployment: DeploymentManager }) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const windowEditorRef = useRef<WindowEditorRenderer>();
    const rootStore = useRootStore();
    const state = useLocalObservable(() => ({
        get availableTasks() {
            const usedIds = new Set(props.dashboard.windows.map(w => w.task_id));
            return Array.from(props.deployment.tasks.values()).filter(task => !usedIds.has(task.id));
        },
        dashboard: cloneDeep(props.dashboard)
    }));

    useEffect(() => reaction(() => props.dashboard.id, () => {
        state.dashboard = cloneDeep(props.dashboard);
    }), []);

    useEffect(() => {
        if (!containerRef.current) return;

        windowEditorRef.current = new WindowEditorRenderer(props.deployment);
        for (const window of props.dashboard.windows) {
            windowEditorRef.current.addWindow(window);
        }
        windowEditorRef.current.addListener("updated", window => {
            state.dashboard.windows = [...state.dashboard.windows.filter(w => w.task_id !== window.task_id), window];
            rootStore.dashboard.putThrottled(state.dashboard);
        });
        windowEditorRef.current.addListener("removed", window => {
            state.dashboard.windows = state.dashboard.windows.filter(w => w.task_id !== window.task_id);
            rootStore.dashboard.putThrottled(state.dashboard);
        });

        windowEditorRef.current.mount(containerRef.current);
        return () => windowEditorRef.current?.destroy();
    }, [props.dashboard.id, props.deployment]);

    return (
        <Stack width="100%" height="100%" direction="row">
            <Box flex={1} bgcolor="#fff" sx={{ overflowY: "auto", direction: "rtl" }}>
                <List component="div" disablePadding sx={{ direction: "ltr" }}>
                    {Array.from(Array(1)).map(() => state.availableTasks).reduce((pv, cv) => [...pv, ...cv]).map(task => (
                        <ListItemButton sx={{ cursor: "grab" }} disableRipple draggable={true} onDragStart={(e) => e.dataTransfer.setData("task_id", task.id)}>
                            <ListItemIcon>
                                <TerminalIcon />
                            </ListItemIcon>
                            <ListItemText primary={task.label} />
                        </ListItemButton>
                    ))}
                </List>
            </Box>
            <Box flex={4} ref={containerRef} onDragOver={e => e.preventDefault()} onDrop={async e => {
                try {
                    const taskId = e.dataTransfer.getData("task_id");
                    if (taskId) {
                        const containerOffset = containerRef.current!.getBoundingClientRect();
                        windowEditorRef.current?.addWindow({ 
                            task_id: taskId, 
                            ...windowEditorRef.current!.viewport.toLocal({
                                x: e.clientX - containerOffset.x,
                                y: e.clientY - containerOffset.y
                            }), 
                            width: 300, height: 300 
                        });
                    }
                } catch { }
            }}></Box>
        </Stack>
    );
});

export const DashboardPage = observer(() => {
    const params = useParams();
    const rootStore = useRootStore();
    const state = useLocalObservable(() => ({
        id: undefined as string | undefined,
        get dashboard() {
            return rootStore.dashboard.dashboards.find(db => db.id === this.id);
        },
        deployment: undefined as undefined | DeploymentManager,
        notFound: false
    }));

    useEffect(() => {
        state.id = params.id;
        if (!params.id) {
            state.notFound = true;
            return;
        }
        if (!state.dashboard) {
            rootStore.dashboard.loadOne(params.id).catch(() => {
                state.notFound = true;
            });
        }
        return () => {
            state.notFound = false;
        };
    }, [params.id]);

    useEffect(() => reaction(() => state.dashboard?.deployment_id, async () => {
        if (state.dashboard?.deployment_id) {
            state.deployment = await rootStore.deployment.createManager(state.dashboard.deployment_id);
            if (state.deployment === undefined) {
                state.notFound = true;
            }
            else {
                await state.deployment.loadTasks()
            }
        }
        else {
            state.deployment = undefined;
        }
    }), [])

    if (!state.dashboard || !state.deployment) {
        if (state.notFound) {
            throw new Error("Not found");
        }
        else {
            return (
                <PageLayout>
                    <Stack alignItems={"center"} justifyContent="center" height="100%" width="100%"><CircularProgress /></Stack>
                </PageLayout>
            );
        }
    }

    return (
        <PageLayout headerContent={(
            <>
                <Divider color="inherit" orientation="vertical" sx={{ marginX: 3, height: "1rem", borderColor: "#fff" }} />
                <Typography marginRight={1}>{state.dashboard.label}</Typography>
                <IconButton color="inherit" size="small" onClick={() => rootStore.uiControl.editDashboard(state.dashboard!)}><EditIcon fontSize="inherit" /></IconButton>
            </>
        )}>
            <Box position="relative" width="100%" height="100%">
                <Box position="absolute" width="100%" height="100%">
                    <DashboardEditor dashboard={state.dashboard} deployment={state.deployment} />
                </Box>
            </Box>
        </PageLayout>
    )
});