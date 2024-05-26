import { configure } from 'mobx';
configure({ enforceActions: "never" })

import { createRoot } from 'react-dom/client';
import { App } from './App';
import { RootStore, RootStoreContext } from './state/root-store';
import { ThemeProvider, createTheme } from '@mui/material';
import { theme } from "@streamtasks/core";


const root = createRoot(document.getElementById("root")!);
root.render((
    <ThemeProvider theme={theme}>
        <RootStoreContext.Provider value={new RootStore()}>
            <App />
        </RootStoreContext.Provider>
    </ThemeProvider>
))