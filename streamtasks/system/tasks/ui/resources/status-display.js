import { html } from "lit-html";

export function renderUI(value, config) {
    let text;
    let color;
    if (value.value > config.threshold) {
        text = config.text_above;
        color = config.color_above;
    }
    else {
        text = config.text_below;
        color = config.color_below;
    }

    return html`
    <div class="flex-column flex-column--center flex-column--jcenter" style="width:100vw;height:100vh;">
        <div class="flex-column flex-column--center flex-column--jcenter" style="width: calc(min(100vw, 100vh));height: calc(min(100vw, 100vh));background-color:${color};border-radius: 50%;">
            <div style="font-weight: 600; font-size: 2rem;">${text}</div>    
        </div>
    </div>
    `;
}