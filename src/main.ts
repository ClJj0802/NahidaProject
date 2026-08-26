import "./styles.css";

import {
  Application,
  Rectangle,
  extensions,
} from "pixi.js";

import {
  Live2DModel,
  Live2DPlugin,
} from "untitled-pixi-live2d-engine/cubism";

import {
  getCurrentWindow,
  primaryMonitor,
  LogicalPosition,
} from "@tauri-apps/api/window";

extensions.add(Live2DPlugin);

async function moveWindowToBottomRight() {
  const appWindow = getCurrentWindow();

  const monitor = await primaryMonitor();

  if (!monitor) {
    console.warn("Primary monitor was not found");
    return;
  }

  const scaleFactor = monitor.scaleFactor;

  const workPosition =
    monitor.workArea.position.toLogical(scaleFactor);

  const workSize =
    monitor.workArea.size.toLogical(scaleFactor);

  const physicalWindowSize =
    await appWindow.outerSize();

  const windowSize =
    physicalWindowSize.toLogical(scaleFactor);

  const marginRight = 0;
  const marginBottom = 0;

  const x =
    workPosition.x +
    workSize.width -
    windowSize.width -
    marginRight;

  const y =
    workPosition.y +
    workSize.height -
    windowSize.height -
    marginBottom;

  console.log("Monitor work area:", {
    x: workPosition.x,
    y: workPosition.y,
    width: workSize.width,
    height: workSize.height,
  });

  console.log("Window size:", {
    width: windowSize.width,
    height: windowSize.height,
  });

  console.log("Moving window to:", {
    x,
    y,
  });

  await appWindow.setPosition(
    new LogicalPosition(x, y)
  );
}

async function main() {
  const app = new Application();

  await app.init({
    resizeTo: window,
    preference: "webgl",
    autoDensity: true,
    resolution: window.devicePixelRatio,
    backgroundAlpha: 0,
  });

  const root =
    document.querySelector<HTMLDivElement>("#app");

  if (!root) {
    throw new Error("#app element was not found");
  }

  root.appendChild(app.canvas);

  const fpsCounter =
    document.createElement("div");

  fpsCounter.id = "fps-counter";
  fpsCounter.textContent = "FPS: --";

  document.body.appendChild(fpsCounter);

  const model = await Live2DModel.from(
    "/models/Nahida/Nahida.model3.json"
  );

  model.anchor.set(0.5);

  app.stage.addChild(model);

  const fitModel = () => {
    model.scale.set(1);

    const scaleX =
      (app.screen.width * 4) /
      model.width;

    const scaleY =
      (app.screen.height * 7) /
      model.height;

    const scale =
      Math.min(scaleX, scaleY);

    model.scale.set(scale);

    model.position.set(
      app.screen.width / 2,
      app.screen.height / 2
    );
  };

  const hitArea = new Rectangle(
    -model.width * 0.35,
    -model.height * 0.4,
    model.width * 0.7,
    model.height
  );

  model.hitArea = hitArea;

  model.automator.autoFocus = false;

  model.on("pointermove", (event) => {
    model.focus(
      event.global.x,
      event.global.y
    );
  });

  fitModel();

  window.addEventListener(
    "resize",
    fitModel
  );

  await moveWindowToBottomRight();

  let frameCount = 0;
  let lastTime = performance.now();

  app.ticker.add(() => {
    frameCount++;

    const now = performance.now();

    const elapsed =
      now - lastTime;

    if (elapsed >= 1000) {
      const fps = Math.round(
        (frameCount * 1000) /
        elapsed
      );

      fpsCounter.textContent =
        `FPS: ${fps}`;

      frameCount = 0;
      lastTime = now;
    }
  });

  console.log(
    "Live2D model loaded successfully"
  );

  console.log(model);
}

main().catch((error) => {
  console.error(
    "Failed to start Nahida Pet:"
  );

  console.error(error);
});