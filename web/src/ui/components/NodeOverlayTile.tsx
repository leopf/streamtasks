import { Box, Stack, Typography } from "@mui/material";
import React from "react";

export function NodeOverlayTile(props: React.PropsWithChildren<{ header: React.ReactNode }>) {
    return (
        <Stack
            boxSizing="border-box"
            bgcolor="#fff"
            boxShadow="0 0 10px rgba(0,0,0,0.1)"
            border="1px solid #cfcfcf"
            width="100%"
            height="100%"
            borderRadius={1}>
            <Box borderBottom="1px solid #cfcfcf" paddingX={1} paddingY={0.5}>{props.header}</Box>
            <Box flex={1}>{props.children}</Box>
        </Stack>
    );
}