import { Button, Dialog, DialogTitle, Stack, TextField, Typography } from "@mui/material";
import React from "react";

export function DeploymentLabelEditor(props: { open: boolean, value: string, onChange: (value: string) => void, onClose: () => void }) {
    return (
        <Dialog open={props.open} onClose={() => props.onClose()}>
            <DialogTitle>Deployment</DialogTitle>
            <TextField label="Label" value={props.value} onInput={(e) => props.onChange((e.target as HTMLInputElement).value)}/>
            <Stack direction="row">
                <Button onClick={() => props.onClose()}>Close</Button>
            </Stack>
        </Dialog>
    );
}