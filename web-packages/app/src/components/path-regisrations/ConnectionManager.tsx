import { useEffect, useMemo, useState } from "react";
import urlJoin from "url-join";
import { Box, Button, Card, CardActions, CardContent, Chip, Container, Dialog, DialogActions, DialogContent, DialogTitle, Fab, Grid, Stack, TextField, Typography } from "@mui/material";
import { Add, Delete as DeleteIcon } from "@mui/icons-material";
import { PathRegistrationFrontend } from "../../types/path-registration";

type UrlData = {
    id: string;
    url: string;
    running: boolean;
};

type ServerData = UrlData & {
    connection_count: number;
};

type ConnectionData = UrlData & {
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
    const [newServerUrl, setNewServerUrl] = useState("");
    const [creatingServer, setCreatingServer] = useState(false);

    const [newConnectionUrl, setNewConnectionUrl] = useState("");
    const [creatingConnection, setCreatingConnection] = useState(false);
    const [servers, setServers] = useState<ServerData[]>([]);
    const [connections, setConnections] = useState<ConnectionData[]>([]);

    const baseUrl = useMemo(() => String(new URL("." + props.pathRegistration.path, location.href)), [props.pathRegistration])

    const loadConnections = (controller?: AbortController) => fetch(urlJoin(baseUrl, "./api/connections"), { signal: controller?.signal }).then(res => res.json()).then(data => setConnections(data))
    const loadServers = (controller?: AbortController) => fetch(urlJoin(baseUrl, "./api/servers"), { signal: controller?.signal }).then(res => res.json()).then(data => setServers(data));

    const deleteConnection = (id: string) => fetch(urlJoin(baseUrl, `./api/connection/${id}`), { method: "delete" }).then(() => setConnections(pv => pv.filter(c => c.id !== id)))
    const deleteServer = (id: string) => fetch(urlJoin(baseUrl, `./api/server/${id}`), { method: "delete" }).then(() => setServers(pv => pv.filter(c => c.id !== id)))

    const createConnection = (url: string) => fetch(urlJoin(baseUrl, `./api/connection`), { method: "post", body: JSON.stringify({ url }), headers: { "content-type": "application/json" } })
        .then(res => res.json()).then(data => setConnections(pv => [...pv, data]));
    const createServer = (url: string) => fetch(urlJoin(baseUrl, `./api/server`), { method: "post", body: JSON.stringify({ url }), headers: { "content-type": "application/json" } })
        .then(res => res.json()).then(data => setServers(pv => [...pv, data]));

    useEffect(() => {
        setConnections([]);
        setServers([]);
        const controller = new AbortController()

        loadConnections(controller);
        loadServers(controller);

        const wsUrl = new URL(baseUrl);
        wsUrl.protocol = "ws";
        const updateConnection = new WebSocket(urlJoin(String(wsUrl), "on-change"));
        updateConnection.addEventListener("message", e => {
            if (e.data == "server") {
                loadServers();
            }
            if (e.data == "connection") {
                loadConnections();
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
                            {connections.map(connection => (
                                <Grid item xs={4}>
                                    <Card sx={{ minWidth: 275 }} key={connection.id}>
                                        <CardContent>
                                            <Typography sx={{ fontSize: 14 }} color="text.secondary" gutterBottom>
                                                {connection.id.substring(0, 8)}
                                            </Typography>
                                            <Typography variant="h5" gutterBottom>
                                                {connection.url}
                                            </Typography>
                                            <Stack direction="row" spacing={2}>
                                                {connection.connected ? (
                                                    <Chip label="connected" color="success" />
                                                ) : (
                                                    <Chip label="disconnected" color="default" />
                                                )}
                                                <RunningChip running={connection.running} />
                                            </Stack>
                                        </CardContent>
                                        <CardActions>
                                            <Button size="small" startIcon={<DeleteIcon />} onClick={() => deleteConnection(connection.id)}>remove</Button>
                                        </CardActions>
                                    </Card>
                                </Grid>
                            ))}
                        </Grid>
                        <Typography variant="h3" gutterBottom marginTop={5}>servers</Typography>
                        <Grid container spacing={2} columns={{ sm: 4, md: 8 }}>
                            {servers.map(server => (
                                <Grid item xs={4}>
                                    <Card sx={{ minWidth: 275 }} key={server.id}>
                                        <CardContent>
                                            <Typography sx={{ fontSize: 14 }} color="text.secondary" gutterBottom>
                                                {server.id.substring(0, 8)}
                                            </Typography>
                                            <Typography variant="h5" gutterBottom>
                                                {server.url}
                                            </Typography>
                                            <Stack direction="row" spacing={2}>
                                                <Chip label={server.connection_count + " connected"} color="default" />
                                                <RunningChip running={server.running} />
                                            </Stack>
                                        </CardContent>
                                        <CardActions>
                                            <Button size="small" startIcon={<DeleteIcon />} onClick={() => deleteServer(server.id)}>remove</Button>
                                        </CardActions>
                                    </Card>
                                </Grid>
                            ))}
                        </Grid>
                    </Box>
                </Container>
            </Box>
            <Stack position="fixed" bottom="2rem" right="2rem" direction="column" spacing={3}>
                <Fab variant="extended" color="primary" onClick={() => setCreatingConnection(true)}>
                    <Add sx={{ mr: 1 }} />
                    create connection
                </Fab>
                <Fab variant="extended" color="primary" onClick={() => setCreatingServer(true)}>
                    <Add sx={{ mr: 1 }} />
                    create server
                </Fab>
            </Stack>
            <UrlEditorDialog isOpen={creatingConnection} label="connection url" title="create connection" onClose={(create) => {
                if (create) {
                    createConnection(newConnectionUrl);
                }
                setCreatingConnection(false);
                setNewConnectionUrl("");
            }} onUpdate={setNewConnectionUrl} value={newConnectionUrl} />
            <UrlEditorDialog isOpen={creatingServer} label="server url" title="create server" onClose={(create) => {
                if (create) {
                    createServer(newServerUrl);
                }
                setCreatingServer(false);
                setNewServerUrl("");
            }} onUpdate={setNewServerUrl} value={newServerUrl} />
        </>
    );
}