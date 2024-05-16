import { Add as AddIcon, Dashboard as DashboardIcon, ExpandLess as ExpandLessIcon, ExpandMore as ExpandMoreIcon, Home as HomeIcon, Menu as MenuIcon } from "@mui/icons-material";
import { AppBar, Toolbar, IconButton, Typography, Box, Drawer, List, ListSubheader, ListItemButton, ListItemIcon, ListItemText, ListItem, Collapse } from "@mui/material";
import { observer, useLocalObservable } from "mobx-react-lite";
import React, { useEffect } from "react";
import { useRootStore } from "../../state/root-store";
import { Link, useParams } from "react-router-dom";
import { Deployment } from "../../types/deployment";
import { reaction } from "mobx";

const DeploymentListItem = observer((props: { deployment: Deployment }) => {
    const params = useParams();
    const rootStore = useRootStore();
    const state = useLocalObservable(() => ({
        isExpanded: false,
        get deployment() {
            return rootStore.deployment.createManager(props.deployment)
        }
    }));

    useEffect(() => reaction(() => state.isExpanded, () => {
        if (state.isExpanded) {
            state.deployment.loadDashboards();
        }
    }))

    return (
        <>
            <ListItem disablePadding secondaryAction={(
                <IconButton edge="end" onClick={() => state.isExpanded = !state.isExpanded}>
                    {state.isExpanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                </IconButton>
            )}>
                <ListItemButton component={Link} to={`/deployment/${props.deployment.id}`}>
                    <ListItemText primary={props.deployment.label} primaryTypographyProps={{ sx: { fontWeight: params.id == props.deployment.id ? "bold" : "400" } }} />
                </ListItemButton>
            </ListItem>
            <Collapse in={state.isExpanded} timeout="auto" unmountOnExit>
                <List component="div" disablePadding sx={{ "& div": { pl: 2 } }}>
                    {state.deployment.dashboards.map(db => (
                        <ListItemButton component={Link} to={`/dashboard/${db.id}`}>
                            <ListItemIcon>
                                <DashboardIcon />
                            </ListItemIcon>
                            <ListItemText primary={db.label} />
                        </ListItemButton>
                    ))}
                    <ListItemButton onClick={() => rootStore.uiControl.createNewDashboard(props.deployment.id)}>
                        <ListItemIcon>
                            <AddIcon />
                        </ListItemIcon>
                        <ListItemText primary="Create Dashboard" />
                    </ListItemButton>
                </List>
            </Collapse>
        </>
    );
});

export const Header = observer((props: React.PropsWithChildren<{}>) => {
    const state = useLocalObservable(() => ({
        menuOpen: false
    }));
    const params = useParams();
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
                        {rootStore.deployment.deployments.map(d => <DeploymentListItem deployment={d} key={d.id} />)}
                        <ListItemButton onClick={() => rootStore.uiControl.createNewDeployment()}>
                            <ListItemIcon>
                                <AddIcon />
                            </ListItemIcon>
                            <ListItemText primary={"New Deployment"} />
                        </ListItemButton>
                    </List>
                    <List subheader={<ListSubheader>Paths</ListSubheader>}>
                        {rootStore.pathRegistration.frontendPathRegistrations.map(d => (
                            <ListItemButton key={d.id} component={Link} to={`/path-reg/${d.id}`}>
                                <ListItemText primary={d.frontend.label} />
                            </ListItemButton>
                        ))}
                    </List>
                </Box>
            </Drawer>
        </>
    );
});