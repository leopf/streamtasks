import { Box, Divider, IconButton, Modal, Stack, Typography } from "@mui/material";
import { Clear as ClearIcon } from "@mui/icons-material";
import React from "react";

export function AppModal(props: { children: React.ReactNode, open: boolean, onClose: () => void, title: string }) {
    return (
        <Modal open={props.open} onClose={props.onClose}>
            <Box sx={{
                position: "absolute",
                top: 20,
                bottom: 20,
                left: 20,
                right: 20,
                backgroundColor: "#fff",
                borderRadius: 2,
                overflow:"hidden"
            }}>
                <Stack direction="column" height={"100%"} width={"100%"} maxHeight={"100%"}>
                    <Stack direction="row" alignItems={"center"}>
                        <Typography variant="h6" paddingLeft={2}>{props.title}</Typography>
                        <Box flex={1} />
                        <IconButton onClick={props.onClose}>
                            <ClearIcon />
                        </IconButton>
                    </Stack>
                    <Divider />
                    <Box flex={1} overflow="hidden">{props.children}</Box>
                </Stack>
            </Box>
        </Modal>
    );
}