import "./styles.css";

import { Application, extensions } from "pixi.js";
import {
  Live2DModel,
  Live2DPlugin,
} from "untitled-pixi-live2d-engine/cubism";

extensions.add(Live2DPlugin);

async function main() {
  const app = new Application();

  await app.init({
    resizeTo: window,
    preference: "webgl",
    autoDensity: true,
    resolution: window.devicePixelRatio,
  });

  const root = document.querySelector<HTMLDivElement>("#app");

  if (!root) {
    throw new Error("#app element was not found");
  }

  root.appendChild(app.canvas);

  const fpsCounter = document.createElement("div");
  fpsCounter.id = "fps-counter";
  fpsCounter.textContent = "FPS: --";
  document.body.appendChild(fpsCounter);

  const model = await Live2DModel.from(
    "/models/Nahida/Nahida.model3.json"
  );

  model.anchor.set(0.5);

  const fitModel = () => {
    model.scale.set(1);

    const scaleX =
      (app.screen.width * 0.85) / model.width;

    const scaleY =
      (app.screen.height * 0.85) / model.height;

    const scale = Math.min(scaleX, scaleY);

    model.scale.set(scale);

    model.position.set(
      app.screen.width / 2,
      app.screen.height / 2
    );
  };

  fitModel();

  app.stage.addChild(model);

  window.addEventListener("resize", fitModel);

  let frameCount = 0;
  let lastTime = performance.now();

  app.ticker.add(() => {
    frameCount++;

    const now = performance.now();
    const elapsed = now - lastTime;

    if (elapsed >= 1000) {
      const fps = Math.round(
        (frameCount * 1000) / elapsed
      );

      fpsCounter.textContent = `FPS: ${fps}`;

      frameCount = 0;
      lastTime = now;
    }
  });

  console.log("Live2D model loaded successfully");
  console.log(model);
}

main().catch((error) => {
  console.error("Failed to start Nahida Pet:");
  console.error(error);
});