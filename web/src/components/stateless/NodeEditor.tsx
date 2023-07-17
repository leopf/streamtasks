import React, { useCallback, useEffect } from "react";
import { NodeEditorRenderer } from "../../lib/node-editor";
import { Alert, Box, Snackbar } from "@mui/material";

export function NodeEditor(props: { editor: NodeEditorRenderer }) {
    const containerRef = React.useRef<HTMLDivElement>(null);
    const [alertOpen, setAlertOpen] = React.useState(false);
    const [connectErrorMessage, setConnectErrorMessage] = React.useState<string | undefined>(undefined);

    useEffect(() => {
        props.editor.mount(containerRef.current!);
        const connectErrorHandler = (message: string) => {
            setConnectErrorMessage(message);
            setAlertOpen(true);
        };
        props.editor.on("connectError", connectErrorHandler);
        return () => {
            props.editor.off("connectError", connectErrorHandler);
            props.editor.unmount();
        };
    }, [props.editor]);

    const handleClose = useCallback(() => setAlertOpen(false), []);

    return (
        <>
            <Snackbar
                open={alertOpen}
                autoHideDuration={5000}
                onClose={handleClose}>
                <Alert elevation={6} onClose={handleClose} severity="error">
                    {connectErrorMessage}
                </Alert>
            </Snackbar>
            <Box sx={{ width: "100%", height: "100%", position: "relative" }}>
                <Box sx={{ position: "absolute", width: "100%", height: "100%" }} ref={containerRef} />
            </Box>
        </>
    )
}