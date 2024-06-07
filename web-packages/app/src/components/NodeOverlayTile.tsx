import { Box, Stack } from "@mui/material";
import React from "react";

export function NodeOverlayTile(props: React.PropsWithChildren<{ header?: React.ReactNode }>) {
    return (
        <Stack
            boxSizing="border-box"
            bgcolor={theme => theme.palette.background.paper}
            width="100%"
            height="100%"
            borderRadius={1}>
            <Box paddingX={1} paddingY={0.75} color={theme => theme.palette.text.primary}>{props.header}</Box>
            <Stack flex={1} overflow="auto" direction={"column"}>{props.children}</Stack>
        </Stack>
    );
}