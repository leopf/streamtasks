import "@material/web/slider/slider.js";
import { html } from "lit-html";

export function renderUI(value, config, setValue) {
    const range = config.max_value - config.min_value

    return html`
    <div class="flex-column">
        <label style="display:block; margin-left: 1rem;">${config.label} - ${value.value}</label>
        <md-slider .step=${range / 200} .value=${value.value} .min=${config.min_value} .max=${config.max_value} @change=${e => setValue({ value: Number(e.target.value) })}></md-slider>
    </div>
    `;
}