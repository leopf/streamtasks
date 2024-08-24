import { useEffect, useState } from "react";
import { Box, Button, Card, CardActions, CardContent, Container, Dialog, DialogActions, DialogContent, DialogTitle, Fab, Grid, Stack, TextField, Typography } from "@mui/material";
import { Add as AddIcon, Delete as DeleteIcon, Edit as EditIcon } from "@mui/icons-material";
import { PathRegistrationFrontend } from "../../types/path-registration";
import { Metadata } from "@streamtasks/core";

type NamedTopic = {
    name: string;
    metadata: Metadata;
};

async function getNamedTopics(): Promise<NamedTopic[]> {
    return await fetch(new URL(`./named-topics/api/named-topics`, location.href)).then(res => res.json())
}

async function putNamedTopic(namedTopic: NamedTopic): Promise<NamedTopic> {
    return await fetch(new URL("./named-topics/api/named-topic", location.href), {
        method: "put",
        body: JSON.stringify(namedTopic),
        headers: {
            "content-type": "application/json",
        }
    }).then(res => res.json())
}

async function deleteNamedTopic(name: string): Promise<void> {
    await fetch(new URL(`./named-topics/api/named-topic/${encodeURIComponent(name)}`, location.href), {
        method: "delete",
    })
}

function NamedTopicEditorDialog(props: { namedTopic?: NamedTopic, onClose: (t?: NamedTopic) => void }) {
    const [name, setName] = useState("");

    useEffect(() => {
        if (props.namedTopic) {
            setName(props.namedTopic.name);
        }
    }, [props.namedTopic]);

    return (
        <Dialog fullWidth open={!!props.namedTopic} onClose={() => props.onClose()}>
            {!!props.namedTopic && (
                <form onSubmit={async e => {
                    e.preventDefault();
                    props.onClose({ ...(props.namedTopic ?? { metadata: {} }), name: name });
                }}>
                    <DialogTitle>Named Topic: {name}</DialogTitle>
                    <DialogContent>
                        <TextField
                            value={name}
                            onInput={(e) => setName((e.target as HTMLInputElement).value)}
                            autoFocus
                            required
                            label="name"
                            fullWidth
                            variant="filled"
                        />
                    </DialogContent>
                    <DialogActions>
                        <Button type="submit">Save</Button>
                    </DialogActions>
                </form>
            )}
        </Dialog>
    )
}

export function NamedTopicManager(props: { pathRegistration: PathRegistrationFrontend }) {
    const [namedTopics, setNamedTopics] = useState<NamedTopic[]>([]);
    const [selectedNamedTopic, setSelectedNamedTopic] = useState<undefined | NamedTopic>(undefined);

    useEffect(() => {
        setNamedTopics([]);
        getNamedTopics().then(res => setNamedTopics(res));
    }, [props.pathRegistration])

    return (
        <>
            <Box width="100%" height="100%">
                <Container>
                    <Box paddingY={10}>
                        <Typography variant="h2" gutterBottom>{props.pathRegistration.frontend.label}</Typography>
                        <Typography variant="h3" gutterBottom marginTop={5}>named topics</Typography>
                        <Grid container spacing={2} columns={{ xs: 4, sm: 8, md: 12 }}>
                            {namedTopics.map(namedTopic => (
                                <Grid item xs={4}>
                                    <Card sx={{ minWidth: 275 }} key={namedTopic.name}>
                                        <CardContent>
                                            <Typography variant="h5" gutterBottom>
                                                {namedTopic.name}
                                            </Typography>
                                        </CardContent>
                                        <CardActions>
                                            <Stack direction="row" spacing={2}>
                                                <Button size="small" startIcon={<DeleteIcon />} onClick={async () => {
                                                    await deleteNamedTopic(namedTopic.name);
                                                    setNamedTopics(pv => pv.filter(t => t.name !== namedTopic.name));
                                                }}>remove</Button>
                                                <Button size="small" startIcon={<EditIcon />} onClick={() => setSelectedNamedTopic(namedTopic)}>edit</Button>
                                            </Stack>
                                        </CardActions>
                                    </Card>
                                </Grid>
                            ))}
                        </Grid>
                    </Box>
                </Container>
            </Box>
            <Stack position="fixed" bottom="2rem" right="2rem" direction="column" spacing={3}>
                <Fab variant="extended" color="primary" onClick={() => setSelectedNamedTopic({ metadata: {}, name: "" })}>
                    <AddIcon sx={{ mr: 1 }} />
                    create named topic
                </Fab>
            </Stack>
            <NamedTopicEditorDialog namedTopic={selectedNamedTopic} onClose={async (namedTopic) => {
                if (namedTopic) {
                    const newNamedTopic = await putNamedTopic(namedTopic);
                    setNamedTopics(pv => [...pv.filter(t => t.name !== newNamedTopic.name), namedTopic]);
                }
                setSelectedNamedTopic(undefined);
            }} />
        </>
    );
}