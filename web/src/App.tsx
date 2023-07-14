import { observer } from "mobx-react";
import { useEffect } from "react";
import { state } from "./state";
import React from "react";
import { Route, RouterProvider, createBrowserRouter, Link as RouterLink, LinkProps as RouterLinkProps } from "react-router-dom";
import { DeploymentPage } from "./pages/DeploymentPage";
import { LinkProps, ThemeProvider, createTheme } from "@mui/material";
import { SystemLogModal } from "./components/stateful/SystemLogModal";
import { HomePage } from "./pages/HomePage";
import { DashboardPage } from "./pages/DashboardPage";

const router = createBrowserRouter([
    {
        path: "/deployment/view/:id",
        element: <DeploymentPage />
    },
    {
        path: "/dashboard/:id",
        element: <DashboardPage />
    },
    {
        path: "/",
        element: <HomePage />
    }
]);

const LinkBehavior = React.forwardRef<
    HTMLAnchorElement,
    Omit<RouterLinkProps, 'to'> & { href: RouterLinkProps['to'] }
>((props, ref) => {
    const { href, ...other } = props;
    return <RouterLink ref={ref} to={href} {...other} />;
});

const theme = createTheme({
    components: {
        MuiLink: {
            defaultProps: {
                component: LinkBehavior,
            } as LinkProps,
        },
        MuiButtonBase: {
            defaultProps: {
                LinkComponent: LinkBehavior,
            },
        },
    },
});

export const App = observer(() => {
    useEffect(() => {
        state.init();
    }, []);

    if (!state.initialized) {
        return <div>Loading...</div>;
    }

    return (
        <ThemeProvider theme={theme}>
            <>
                <SystemLogModal/>
                <RouterProvider router={router} />
            </>
        </ThemeProvider>
    )
})