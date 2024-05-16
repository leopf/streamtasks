import { useEffect, useMemo, useState } from "react";
import { PathRegistrationFrontend } from "../../../types/path";
import urlJoin from "url-join";
import { Box, Button, Card, CardActions, CardContent, Chip, Container, Dialog, DialogActions, DialogContent, DialogTitle, Fab, Grid, Stack, TextField, Typography } from "@mui/material";
import { Add, Delete as DeleteIcon } from "@mui/icons-material";

type UrlData = {
    id: string;
    url: string;
    running: boolean;
};

type ServeData = UrlData & {
    connection_count: number;
};

type ConnectData = UrlData & {
    connected: boolean;
};

function UrlEditorDialog(props: { title: string, isOpen: boolean, label: string, value: string, onUpdate: (v: string) => void, onClose: (create: boolean) => void }) {
    return (
        <Dialog fullWidth open={props.isOpen} onClose={() => props.onClose(false)}>
            <DialogTitle>{props.title}</DialogTitle>
            <DialogContent>
                <TextField
                    value={props.value}
                    onInput={(e) => props.onUpdate((e.target as HTMLInputElement).value)}
                    autoFocus
                    required
                    label={props.label}
                    fullWidth
                    variant="standard"
                />
            </DialogContent>
            <DialogActions>
                <Button onClick={() => props.onClose(true)}>Save</Button>
            </DialogActions>
        </Dialog>
    )
}

function RunningChip(props: { running: boolean }) {
    return props.running ? (
        <Chip label="running" color="success" />
    ) : (
        <Chip label="not running" color="default" />
    )
}

export function ConnectionManager(props: { pathRegistration: PathRegistrationFrontend }) {
    const [newServeUrl, setNewServeUrl] = useState("");
    const [creatingServe, setCreatingServe] = useState(false);

    const [newConnectUrl, setNewConnectUrl] = useState("");
    const [creatingConnect, setCreatingConnect] = useState(false);
    const [serves, setServes] = useState<ServeData[]>([]);
    const [connects, setConnects] = useState<ConnectData[]>([]);

    const baseUrl = useMemo(() => String(new URL("." + props.pathRegistration.path, location.href)), [props.pathRegistration])

    const loadConnects = (controller?: AbortController) => fetch(urlJoin(baseUrl, "./api/connects"), { signal: controller?.signal }).then(res => res.json()).then(data => setConnects(data))
    const loadServes = (controller?: AbortController) => fetch(urlJoin(baseUrl, "./api/serves"), { signal: controller?.signal }).then(res => res.json()).then(data => setServes(data));

    const deleteConnect = (id: string) => fetch(urlJoin(baseUrl, `./api/connect/${id}`), { method: "delete" }).then(() => setConnects(pv => pv.filter(c => c.id !== id)))
    const deleteServe = (id: string) => fetch(urlJoin(baseUrl, `./api/serve/${id}`), { method: "delete" }).then(() => setServes(pv => pv.filter(c => c.id !== id)))

    const createConnect = (url: string) => fetch(urlJoin(baseUrl, `./api/connect`), { method: "post", body: JSON.stringify({ url }), headers: { "content-type": "application/json" } })
        .then(res => res.json()).then(data => setConnects(pv => [...pv, data]));
    const createServe = (url: string) => fetch(urlJoin(baseUrl, `./api/serve`), { method: "post", body: JSON.stringify({ url }), headers: { "content-type": "application/json" } })
        .then(res => res.json()).then(data => setServes(pv => [...pv, data]));

    useEffect(() => {
        setConnects([]);
        setServes([]);
        const controller = new AbortController()

        loadConnects(controller);
        loadServes(controller);

        const wsUrl = new URL(baseUrl);
        wsUrl.protocol = "ws";
        const updateConnection = new WebSocket(urlJoin(String(wsUrl), "on-change"));
        updateConnection.addEventListener("message", e => {
            if (e.data == "server") {
                loadServes();
            }
            if (e.data == "connection") {
                loadConnects();
            }
        });

        return () => {
            controller.abort();
            updateConnection.close();
        }
    }, [props.pathRegistration])

    return (
        <>
            <Box width="100%" height="100%">
                <Container>
                    <Box paddingY={10}>
                        <Typography variant="h2" gutterBottom>{props.pathRegistration.frontend.label}</Typography>
                        <Typography variant="h3" gutterBottom marginTop={5}>connections</Typography>
                        <Grid container spacing={2} columns={{ sm: 4, md: 8 }}>
                            {connects.map(connect => (
                                <Grid item xs={4}>
                                    <Card sx={{ minWidth: 275 }} key={connect.id}>
                                        <CardContent>
                                            <Typography sx={{ fontSize: 14 }} color="text.secondary" gutterBottom>
                                                {connect.id.substring(0, 8)}
                                            </Typography>
                                            <Typography variant="h5" gutterBottom>
                                                {connect.url}
                                            </Typography>
                                            <Stack direction="row" spacing={2}>
                                                {connect.connected ? (
                                                    <Chip label="connected" color="success" />
                                                ) : (
                                                    <Chip label="disconnected" color="default" />
                                                )}
                                                <RunningChip running={connect.running} />
                                            </Stack>
                                        </CardContent>
                                        <CardActions>
                                            <Button size="small" startIcon={<DeleteIcon />} onClick={() => deleteConnect(connect.id)}>remove</Button>
                                        </CardActions>
                                    </Card>
                                </Grid>
                            ))}
                        </Grid>
                        <Typography variant="h3" gutterBottom marginTop={5}>servers</Typography>
                        <Grid container spacing={2} columns={{ sm: 4, md: 8 }}>
                            {serves.map(serve => (
                                <Grid item xs={4}>
                                    <Card sx={{ minWidth: 275 }} key={serve.id}>
                                        <CardContent>
                                            <Typography sx={{ fontSize: 14 }} color="text.secondary" gutterBottom>
                                                {serve.id.substring(0, 8)}
                                            </Typography>
                                            <Typography variant="h5" gutterBottom>
                                                {serve.url}
                                            </Typography>
                                            <Stack direction="row" spacing={2}>
                                                <Chip label={serve.connection_count + " connected"} color="default" />
                                                <RunningChip running={serve.running} />
                                            </Stack>
                                        </CardContent>
                                        <CardActions>
                                            <Button size="small" startIcon={<DeleteIcon />} onClick={() => deleteServe(serve.id)}>remove</Button>
                                        </CardActions>
                                    </Card>
                                </Grid>
                            ))}
                        </Grid>
                    </Box>
                </Container>
            </Box>
            <Stack position="fixed" bottom="2rem" right="2rem" direction="column" spacing={3}>
                <Fab variant="extended" color="primary" onClick={() => setCreatingConnect(true)}>
                    <Add sx={{ mr: 1 }} />
                    create connection
                </Fab>
                <Fab variant="extended" color="primary" onClick={() => setCreatingServe(true)}>
                    <Add sx={{ mr: 1 }} />
                    create server
                </Fab>
            </Stack>
            <UrlEditorDialog isOpen={creatingConnect} label="connection url" title="create connection" onClose={(create) => {
                if (create) {
                    createConnect(newConnectUrl);
                }
                setCreatingConnect(false);
                setNewConnectUrl("");
            }} onUpdate={setNewConnectUrl} value={newConnectUrl} />
            <UrlEditorDialog isOpen={creatingServe} label="server url" title="create server" onClose={(create) => {
                if (create) {
                    createServe(newServeUrl);
                }
                setCreatingServe(false);
                setNewServeUrl("");
            }} onUpdate={setNewServeUrl} value={newServeUrl} />
        </>
    );
}