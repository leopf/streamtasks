import React from "react";
import { createRoot } from 'react-dom/client';
import { App } from "./App";
import { configure } from "mobx";

configure({
    observableRequiresReaction: false,
    enforceActions: "never",
});

createRoot(document.getElementById("root")!).render(<App/>);

console.log("App started4");