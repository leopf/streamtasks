import { CircularProgress, Divider, IconButton, Stack, Typography } from "@mui/material";
import { observer, useLocalObservable } from "mobx-react-lite";
import { useParams } from "react-router-dom";
import { useEffect } from "react";
import { useRootStore } from "../../state/root-store";
import { PageLayout } from "../Layout";
import { Edit as EditIcon } from "@mui/icons-material";
import { Dashboard } from "../../types/dashboard";

export const DashboardPage = observer(() => {
    const params = useParams();
    const rootStore = useRootStore();
    const state = useLocalObservable(() => ({
        get dashboard() {
            return rootStore.dashboard.dashboards.find(db => db.id === params.id);
        },
        notFound: false
    }));

    useEffect(() => {
        if (!params.id) {
            state.notFound = true;
            return;
        }
        let disposed = false;

        rootStore.dashboard.get(params.id).then(dashboard => {
            if (disposed) return;
            if (dashboard) {
                state.dashboard = dashboard;
            }
            else { state.notFound = true; }
        });

        return () => {
            state.notFound = false;
        };
    }, [params.id]);

    if (!state.dashboard) {
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
                <Typography marginRight={1}>{state.dashboard.label}</Typography>
                <IconButton color="inherit" size="small" onClick={() => rootStore.uiControl.editDashboard(state.dashboard!)}><EditIcon fontSize="inherit" /></IconButton>
            </>
        )}>

        </PageLayout>
    )
});