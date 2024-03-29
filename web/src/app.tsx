import React from 'react';
import { createRoot } from 'react-dom/client';

window.React = React;

const root = createRoot(document.getElementById("root")!);
root.render((<div>Hello4</div>))