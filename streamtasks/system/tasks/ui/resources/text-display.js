import { html } from "lit-html";

export function renderUI(value, config) {
    return html`<div style="font-size:1.5rem;">${value.value}</div>`;
}