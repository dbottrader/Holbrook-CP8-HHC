import { ASINEngine } from "./core/engine";
import { defaultConfig } from "./core/config";

const canvas = document.getElementById("view") as HTMLCanvasElement | null;

if (!canvas) {
  throw new Error("Canvas element #view not found");
}

canvas.width = defaultConfig.width;
canvas.height = defaultConfig.height;

const ctx = canvas.getContext("2d");

if (!ctx) {
  throw new Error("2D canvas context unavailable");
}

const engine = new ASINEngine(defaultConfig);

function render(): void {
  engine.render(ctx as CanvasRenderingContext2D);
}

const exportButton = document.getElementById("export");
if (exportButton) {
  exportButton.addEventListener("click", () => {
    const image = canvas.toDataURL("image/png");
    console.log(image);
  });
}

render();
