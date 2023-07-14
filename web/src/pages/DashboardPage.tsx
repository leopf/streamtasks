import { Stack, Typography, Box, Container, Button, Divider } from "@mui/material";
import { observer } from "mobx-react";
import React, { useEffect, useMemo } from "react";
import { TitleBar } from "../components/stateful/TitleBar";
import { ShowSystemLogsButton } from "../components/stateful/ShowSystemLogsButton";
import { useNavigate, useParams } from "react-router-dom";
import { state } from "../state";

export const DashboardPage = observer((props: {}) => {
    const params = useParams<{id: string}>();
    const navigate = useNavigate();
    const dashboard = params.id ? state.getDashboard(params.id) : undefined;

    useEffect(() => {
        if (!dashboard) {
            navigate("/");
        }
    }, [dashboard]);

    if (!dashboard) {
        return <div>Error...</div>
    }

    return (
        <Stack direction="column" height={"100%"} maxHeight={"100%"}>
            <TitleBar>
                <Stack height="100%" direction="row" alignItems="center" boxSizing="border-box">
                    <Typography lineHeight={1} fontSize={18} >Dashboard: {dashboard.label}</Typography>
                    <Box flex={1} />
                    <ShowSystemLogsButton />
                </Stack>
            </TitleBar>
            <Box flex={1} sx={{ overflowY: "hidden" }} width="100%">
                <iframe src={dashboard.url} style={{
                    width: "100%",
                    height: "100%",
                    border: "none"
                }} />
            </Box>
        </Stack>
    );
});