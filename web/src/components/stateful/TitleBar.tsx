import { AppBar, Box, Drawer, IconButton, List, ListItem, ListItemButton, ListItemIcon, ListItemText, ListSubheader, Stack, Typography } from "@mui/material";
import { observer } from "mobx-react";
import { Menu as MenuIcon, Add as AddIcon, Home as HomeIcon } from "@mui/icons-material"
import React, { useState } from "react";
import { state } from "../../state";
import { useNavigate } from "react-router-dom";

const DeploymentList = observer(() => {
    const navigate = useNavigate();

    return (
        <List subheader={
            <Stack direction="row" alignItems="center">
                <ListSubheader>Deployments</ListSubheader>
                <Box flex={1} minWidth={"1.5rem"} />
                <Box paddingRight={1}>
                    <IconButton size="small" onClick={async () => {
                        const deployment = await state.createDeployment("New Deployment");
                        navigate(`/deployment/view/${deployment.id}`);
                    }}>
                        <AddIcon />
                    </IconButton>
                </Box>
            </Stack>
        }>
            {state.deployments.map(deployment => (
                <ListItem disablePadding>
                    <ListItemButton href={`/deployment/view/${deployment.id}`}>
                        <ListItemText primary={deployment.label} />
                    </ListItemButton>
                </ListItem>
            ))}
        </List>
    );
});


export const TitleBar = observer((props: { children?: React.ReactNode }) => {
    const [open, setOpen] = useState(false);

    return (
        <>
            <Drawer anchor="left" open={open} onClose={() => setOpen(false)}>
                <Box minWidth={"20vw"} paddingRight={1}>

                    <List>
                        <ListItem disablePadding>
                            <ListItemButton href="/">
                                <ListItemIcon>
                                    <HomeIcon />
                                </ListItemIcon>
                                <ListItemText primary={"Home"} />
                            </ListItemButton>
                        </ListItem>
                    </List>
                    <DeploymentList />
                    <List subheader={<ListSubheader>Dashboards</ListSubheader>}>
                        {state.dashboards.map(dashboard => (
                            <ListItem disablePadding>
                                <ListItemButton href={`/dashboard/${dashboard.id}`}>
                                    <ListItemText primary={dashboard.label} />
                                </ListItemButton>
                            </ListItem>
                        ))}
                    </List>
                </Box>
            </Drawer>
            <AppBar position="static" sx={{ boxShadow: "none" }}>
                <Stack direction="row" paddingY={0.35}>
                    <IconButton size="small" onClick={() => setOpen(v => !v)}>
                        <MenuIcon htmlColor="#fff" />
                    </IconButton>
                    <Box flex={1} paddingLeft={1}>
                        {props.children}
                    </Box>
                </Stack>
            </AppBar>
        </>
    );
});