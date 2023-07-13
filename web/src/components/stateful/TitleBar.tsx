import { AppBar, Box, IconButton, Stack } from "@mui/material";
import { observer } from "mobx-react";
import { Menu as MenuIcon } from "@mui/icons-material"
import React from "react";

export const TitleBar = observer((props: { children?: React.ReactNode }) => {
    return (
        <AppBar position="static" sx={{ boxShadow: "none" }}>
            <Stack direction="row">
                <IconButton size="small">
                    <MenuIcon htmlColor="#fff" />
                </IconButton>
                <Box flex={1}>
                    {props.children}
                </Box>
            </Stack>
        </AppBar>
    );
});