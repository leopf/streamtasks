import { html } from "lit-html";

export function renderUI(value, config) {
    const range = Math.max(0, config.max_value - config.min_value);
    const p = Math.min((value.value - config.min_value) / range, 1);

    const containerStyle = "border-radius: 3px;background-color: #d6d6d6;overflow: hidden;";
    const baseSize = "2rem";

    return html`
    <div class="flex-column flex-column--center flex-column--spaced" style="width:100vw;height:100vh;">
        ${config.direction == "vertical" ? html`
        <div style="${containerStyle}width: ${baseSize}; height: 100%;">
            <div style="height:${(1 - p) * 100}%;"></div>
            <div style="background-color:${config.color};width:100%;height:${p*100}%;"></div>
        </div>
        ` : html`
        <div style="${containerStyle}height: ${baseSize}; width: 100%;">
            <div style="background-color:${config.color};height:100%;width:${p*100}%;"></div>
        </div>
        `}
        <label>${value.value.toFixed(2)}</label>
    </div>
    `;
}