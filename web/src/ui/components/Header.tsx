import { Add as AddIcon, Home as HomeIcon, Menu as MenuIcon } from "@mui/icons-material";
import { AppBar, Toolbar, IconButton, Typography, Box, Drawer, List, ListSubheader, ListItemButton, ListItemIcon, ListItemText, ListItem } from "@mui/material";
import { observer, useLocalObservable } from "mobx-react-lite";
import React from "react";
import { useRootStore } from "../../state/root-store";
import { Link } from "react-router-dom";

export const Header = observer((props: React.PropsWithChildren<{}>) => {
    const state = useLocalObservable(() => ({
        menuOpen: false
    }));
    const rootStore = useRootStore();

    return (
        <>
            <AppBar position="static">
                <Toolbar variant="dense">
                    <IconButton
                        onClick={() => state.menuOpen = true}
                        size="large"
                        edge="start"
                        color="inherit"
                        aria-label="menu"
                        sx={{ mr: 2 }}
                    >
                        <MenuIcon />
                    </IconButton>
                    <Typography variant="h6" component="div">
                        streamtasks
                    </Typography>
                    {props.children}
                </Toolbar>
            </AppBar>
            <Drawer open={state.menuOpen} onClose={() => state.menuOpen = false}>
                <Box role="presentation" sx={{ width: "30vw" }}>
                    <List>
                        <ListItemButton component={Link} to={`/`}>
                            <ListItemIcon>
                                <HomeIcon />
                            </ListItemIcon>
                            <ListItemText primary="Home" />
                        </ListItemButton>
                    </List>
                    <List subheader={<ListSubheader>Deployments</ListSubheader>}>
                        {rootStore.deployment.deployments.map(d => (
                            <ListItemButton key={d.id} component={Link} to={`/deployment/${d.id}`}>
                                <ListItemText primary={d.label} />
                            </ListItemButton>
                        ))}
                        <ListItemButton onClick={() => rootStore.uiControl.createNewDeployment()}>
                            <ListItemIcon>
                                <AddIcon />
                            </ListItemIcon>
                            <ListItemText primary={"New Deployment"} />
                        </ListItemButton>
                    </List>
                    <List subheader={<ListSubheader>Dashboards</ListSubheader>}>
                        {rootStore.pathRegistration.frontendPathRegistrations.map(d => (
                            <ListItemButton key={d.id} component={Link} to={`/dashboard/${d.id}`}>
                                <ListItemText primary={d.frontend.label} />
                            </ListItemButton>
                        ))}
                    </List>
                </Box>
            </Drawer>
        </>
    );
});