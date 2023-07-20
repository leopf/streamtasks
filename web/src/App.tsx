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
        element: <DeploymentPage showOriginal={true} />,
        errorElement: <ErrorScreen />,
        loader: async ({ params }) => {
            if (params.id) {
                const deployment = await state.loadDeployment(params.id);
                if (!deployment) {
                    throw new Error("Deployment not found");
                }
                return deployment;
            }
            return null;
        }
    },
    {
        path: "/deployment/view/:id/started",
        element: <DeploymentPage showOriginal={false} />,
        errorElement: <ErrorScreen />,
        loader: async ({ params }) => {
            if (params.id) {
                const deployment = await state.loadStartedDeployment(params.id);
                if (!deployment) {
                    throw new Error("Deployment not found");
                }
                return deployment;
            }
            return null;
        }
    },
    {
        path: "/dashboard/:id",
        errorElement: <ErrorScreen />,
        element: <DashboardPage />
    },
    {
        path: "/",
        errorElement: <ErrorScreen />,
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
        return <LoadingScreen />;
    }

    return (
        <ThemeProvider theme={theme}>
            <>
                <SystemLogModal />
                <RouterProvider fallbackElement={<LoadingScreen />} router={router} />
            </>
        </ThemeProvider>
    )
})