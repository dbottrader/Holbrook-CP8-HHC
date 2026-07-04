import { generateGeometry } from "../math/phyllotaxis";
import { renderFrame } from "./renderer";
import type { EngineConfig } from "./types";

export class ASINEngine {
  private config: EngineConfig;

  constructor(config: EngineConfig) {
    this.config = config;
  }

  update(config: Partial<EngineConfig>): void {
    this.config = { ...this.config, ...config };
  }

  getConfig(): EngineConfig {
    return { ...this.config };
  }

  render(ctx: CanvasRenderingContext2D) {
    const geometry = generateGeometry(this.config);
    return renderFrame(ctx, geometry, this.config);
  }
}
