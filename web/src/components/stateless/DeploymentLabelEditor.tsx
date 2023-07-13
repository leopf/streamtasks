import { Box, Button, Dialog, DialogTitle, Stack, TextField, Typography } from "@mui/material";
import React, { useEffect } from "react";

export function DeploymentLabelEditor(props: { open: boolean, value: string, onChange: (value: string) => void, onClose: () => void }) {

    const [label, setLabel] = React.useState<string>(props.value);

    useEffect(() => {
        if (props.open) {
            setLabel(props.value);
        }
    }, [props.open])

    useEffect(() => {
        props.onChange(label);
    }, [label])

    return (
        <Dialog open={props.open} onClose={() => props.onClose()} fullWidth>
            <Box padding={2}>

                <Typography variant="h5" marginY={3}>Deployment</Typography>
                <TextField fullWidth label="Label" value={label} onInput={(e) => setLabel((e.target as HTMLInputElement).value)} />
                <Stack direction="row-reverse" marginTop={2}>
                    <Button onClick={() => props.onClose()}>Save</Button>
                </Stack>
            </Box>
        </Dialog>
    );
}