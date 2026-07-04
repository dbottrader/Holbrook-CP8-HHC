# API Reference

## `EngineConfig`

```ts
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
```

## `ASINEngine`

### Constructor

```ts
new ASINEngine(config: EngineConfig)
```

Creates a new deterministic renderer instance.

### `update(config: Partial<EngineConfig>): void`

Applies partial configuration updates.

### `getConfig(): EngineConfig`

Returns a defensive copy of the current configuration.

### `render(ctx: CanvasRenderingContext2D): RenderOutput`

Generates geometry and renders the current frame to the supplied canvas context.

## `generateGeometry(config)`

Generates phyllotaxis geometry from normalized engine configuration.

## `renderFrame(ctx, geometry, config)`

Renders geometry to a 2D canvas context and returns metadata about the frame.
