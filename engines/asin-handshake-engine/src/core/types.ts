export interface EngineConfig {
  hz: number;
  points: number;
  phi: number;
  spokes: number;
  step: number;
  love: number;
  width: number;
  height: number;
}

export interface Point {
  x: number;
  y: number;
  angle: number;
  radius: number;
}

export interface GeometryOutput {
  points: Point[];
  cx: number;
  cy: number;
  R: number;
}

export interface RenderOutput {
  canvas: HTMLCanvasElement;
  imageData?: ImageData;
  meta: string;
}
