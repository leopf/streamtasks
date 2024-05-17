import { Box, CircularProgress, Divider, Fab, IconButton, List, ListItemButton, ListItemIcon, ListItemText, Stack, Typography } from "@mui/material";
import { observer, useLocalObservable } from "mobx-react-lite";
import { useParams } from "react-router-dom";
import { useEffect, useRef } from "react";
import { useRootStore } from "../state/root-store";
import { PageLayout } from "../Layout";
import { ChevronLeft, ChevronRight, Edit as EditIcon, Terminal as TerminalIcon } from "@mui/icons-material";
import { reaction } from "mobx";
import { DeploymentManager } from "../state/deployment-manager";
import { WindowEditorRenderer } from "../lib/window-editor/editor";
import cloneDeep from "clone-deep";
import _ from "underscore";
import { Dashboard } from "../types/dashboard";

const DashboardEditor = observer((props: { dashboard: Dashboard, deployment: DeploymentManager }) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const windowEditorRef = useRef<WindowEditorRenderer>();
    const rootStore = useRootStore();
    const state = useLocalObservable(() => ({
        get availableTasks() {
            const usedIds = new Set(this.dashboard.windows.map(w => w.task_id));
            return Array.from(props.deployment.tasks.values()).filter(task => !usedIds.has(task.id));
        },
        dashboard: cloneDeep(props.dashboard),
        menuOpen: true
    }));

    useEffect(() => reaction(() => props.dashboard.id, () => {
        state.dashboard = cloneDeep(props.dashboard);
    }), []);

    useEffect(() => {
        if (!containerRef.current) return;
        const throttlePut = _.throttle((db: Dashboard) => rootStore.dashboard.put(db), 1000);
        const debouncePut = _.debounce((db: Dashboard) => throttlePut(db), 500);

        windowEditorRef.current = new WindowEditorRenderer(props.deployment);
        for (const window of props.dashboard.windows) {
            windowEditorRef.current.addWindow(window);
        }
        windowEditorRef.current.addListener("updated", window => {
            state.dashboard.windows = [...state.dashboard.windows.filter(w => w.task_id !== window.task_id), window];
            debouncePut(state.dashboard);
        });
        windowEditorRef.current.addListener("removed", window => {
            state.dashboard.windows = state.dashboard.windows.filter(w => w.task_id !== window.task_id);
            debouncePut(state.dashboard);
        });

        windowEditorRef.current.mount(containerRef.current);
        return () => windowEditorRef.current?.destroy();
    }, [props.dashboard.id, props.deployment]);

    return (
        <Stack width="100%" height="100%" direction="row">
            {state.menuOpen && (
                <Box flex={1} bgcolor="#fff" sx={{ overflowY: "auto", direction: "rtl", borderRight: "1px solid #cfcfcf" }}>
                    <Box sx={{ direction: "ltr" }}>
                        <Typography sx={{ ml: 2, mt: 2, mb: 2 }} variant="h6">
                            Tasks
                        </Typography>
                        <List component="div" disablePadding>
                            {state.availableTasks.map(task => (
                                <ListItemButton sx={{ cursor: "grab" }} disableRipple draggable={true} onDragStart={(e) => e.dataTransfer.setData("task_id", task.id)}>
                                    <ListItemIcon>
                                        <TerminalIcon />
                                    </ListItemIcon>
                                    <ListItemText primary={task.label} />
                                </ListItemButton>
                            ))}
                        </List>
                    </Box>
                </Box>
            )}
            <Box flex={4} position="relative">
                <Fab sx={{ position: "absolute", top: "1rem", left: "1rem" }} size="small" color="primary" onClick={() => state.menuOpen = !state.menuOpen}>
                    {state.menuOpen ? (<ChevronLeft />) : (<ChevronRight />)}
                </Fab>
                <Box ref={containerRef} position="absolute" top={0} left={0} width="100%" height="100%" onDragOver={e => e.preventDefault()} onDrop={async e => {
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
            </Box>
        </Stack>
    );
});

export const DashboardPage = observer(() => {
    const params = useParams();
    const rootStore = useRootStore();
    const state = useLocalObservable(() => ({
        id: undefined as string | undefined,
        get dashboard() {
            if (!this.id) {
                return undefined;
            }
            return rootStore.dashboard.dashboards.get(this.id);
        },
        deployment: undefined as undefined | DeploymentManager,
        notFound: false,
    }));

    useEffect(() => {
        state.id = params.id;
        return () => {
            state.notFound = false;
        };
    }, [params.id]);

    useEffect(() => {
        if (state.dashboard) {
            return;
        }
        const id = state.id;
        if (id) {
            rootStore.dashboard.loadOne(id).catch(() => {
                if (state.id === id) {
                    state.notFound = true;
                }
            });
        }
        else {
            state.notFound = true;
        }
    }, [state.dashboard?.id]);

    useEffect(() => {
        (async () => {
            if (state.dashboard) {
                const deploymentId = state.dashboard.deployment_id;
                const deployment = await rootStore.deployment.createManager(deploymentId);
                if (deployment === undefined) {
                    state.notFound = true;
                }
                else {
                    await deployment.loadTasks()
                    if (state.dashboard?.deployment_id === deployment.id) {
                        state.deployment = deployment;
                    }
                }
            }
        })();
    }, [state.dashboard?.id])

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