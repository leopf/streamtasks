import { observer } from "mobx-react";
import { useEffect } from "react";
import { state } from "./state";
import React from "react";
import { RouterProvider, createBrowserRouter, Link as RouterLink, LinkProps as RouterLinkProps } from "react-router-dom";
import { DeploymentPage } from "./pages/DeploymentPage";
import { LinkProps, ThemeProvider, createTheme } from "@mui/material";
import { SystemLogModal } from "./components/stateful/SystemLogModal";
import { HomePage } from "./pages/HomePage";
import { DashboardPage } from "./pages/DashboardPage";
import { LoadingScreen } from "./components/stateless/LoadingScreen";
import { ErrorScreen } from "./components/stateless/ErrorScreen";

const router = createBrowserRouter([
    {
        path: "/deployment/view/:id",
        element: <DeploymentPage />,
        errorElement: <ErrorScreen/>,
        loader: async ({ params }) => {
            try {
                if (params.id) {
                    return await state.loadDeployment(params.id) ?? null;
                }
            }
            catch {}
            return null;
        }
    },
    {
        path: "/dashboard/:id",
        errorElement: <ErrorScreen/>,
        element: <DashboardPage />
    },
    {
        path: "/",
        errorElement: <ErrorScreen/>,
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
        return <LoadingScreen/>;
    }

    return (
        <ThemeProvider theme={theme}>
            <>
                <SystemLogModal/>
                <RouterProvider fallbackElement={<LoadingScreen/>} router={router} />
            </>
        </ThemeProvider>
    )
})