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

const MODEL_PATH =
  "/models/WSQ/WSQ.model3.json";

const RAP_AUDIO_PATH =
  "/sound/rap.mp3";

const MODEL_WIDTH_RATIO = 0.9;
const MODEL_HEIGHT_RATIO = 0.9;

async function moveWindowToBottomRight() {
  const appWindow =
    getCurrentWindow();

  const monitor =
    await primaryMonitor();

  if (!monitor) {
    console.warn(
      "Primary monitor was not found"
    );
    return;
  }

  const scaleFactor =
    monitor.scaleFactor;

  const workPosition =
    monitor.workArea.position.toLogical(
      scaleFactor
    );

  const workSize =
    monitor.workArea.size.toLogical(
      scaleFactor
    );

  const physicalWindowSize =
    await appWindow.outerSize();

  const windowSize =
    physicalWindowSize.toLogical(
      scaleFactor
    );

  const marginRight = 10;
  const marginBottom = 10;

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

  console.log(
    "Monitor work area:",
    {
      x: workPosition.x,
      y: workPosition.y,
      width: workSize.width,
      height: workSize.height,
    }
  );

  console.log(
    "Window size:",
    {
      width: windowSize.width,
      height: windowSize.height,
    }
  );

  console.log(
    "Moving window to:",
    {
      x,
      y,
    }
  );

  await appWindow.setPosition(
    new LogicalPosition(
      x,
      y
    )
  );
}

async function main() {
  const app =
    new Application();

  await app.init({
    resizeTo: window,
    preference: "webgl",
    autoDensity: true,
    resolution:
      window.devicePixelRatio,
    backgroundAlpha: 0,
  });

  const root =
    document.querySelector<HTMLDivElement>(
      "#app"
    );

  if (!root) {
    throw new Error(
      "#app element was not found"
    );
  }

  root.appendChild(
    app.canvas
  );

  const fpsCounter =
    document.createElement(
      "div"
    );

  fpsCounter.id =
    "fps-counter";

  fpsCounter.textContent =
    "FPS: --";

  document.body.appendChild(
    fpsCounter
  );

  console.log(
    "Loading Live2D model:",
    MODEL_PATH
  );

  const model =
    await Live2DModel.from(
      MODEL_PATH
    );

  console.log(
    "Live2D model loaded successfully"
  );

  model.anchor.set(0.5);

  app.stage.addChild(
    model
  );

  try {
    await model.expression(
      "watermark_off"
    );

    console.log(
      "Watermark-off expression applied"
    );
  } catch (error) {
    console.warn(
      "Could not apply watermark-off expression:",
      error
    );
  }

  const fitModel = () => {
    model.scale.set(1);

    const originalWidth =
      model.width;

    const originalHeight =
      model.height;

    const availableWidth =
      app.screen.width *
      MODEL_WIDTH_RATIO;

    const availableHeight =
      app.screen.height *
      MODEL_HEIGHT_RATIO;

    const scaleX =
      availableWidth /
      originalWidth;

    const scaleY =
      availableHeight /
      originalHeight;

    const scale =
      Math.min(
        scaleX,
        scaleY
      );

    model.scale.set(
      scale
    );

    model.position.set(
      app.screen.width / 2,
      app.screen.height / 2
    );

    console.log(
      "Model fit information:",
      {
        screenWidth:
          app.screen.width,

        screenHeight:
          app.screen.height,

        modelWidth:
          originalWidth,

        modelHeight:
          originalHeight,

        scale,
      }
    );
  };

  fitModel();

  window.addEventListener(
    "resize",
    fitModel
  );

  model.eventMode =
    "static";

  model.cursor =
    "pointer";

  const modelBounds =
    model.getLocalBounds();

  model.hitArea =
    new Rectangle(
      modelBounds.x,
      modelBounds.y,
      modelBounds.width,
      modelBounds.height
    );

  console.log(
    "Model hit area:",
    {
      x:
        modelBounds.x,

      y:
        modelBounds.y,

      width:
        modelBounds.width,

      height:
        modelBounds.height,
    }
  );

  const rapAudio =
    new Audio(
      RAP_AUDIO_PATH
    );

  rapAudio.preload =
    "auto";

  rapAudio.volume =
    1.0;

  model.on(
    "pointertap",
    async () => {
      console.log(
        "Usagi clicked"
      );

      try {
        rapAudio.pause();

        rapAudio.currentTime =
          0;

        await rapAudio.play();

        console.log(
          "Playing rap.mp3"
        );
      } catch (error) {
        console.error(
          "Failed to play rap.mp3:",
          error
        );
      }
    }
  );

  model.automator.autoFocus =
    false;

  const focusCenter = {
    x: 0.5,
    y: 0.5,
  };

  model.on(
    "pointermove",
    (event) => {
      const desiredCenterX =
        app.screen.width *
        focusCenter.x;

      const desiredCenterY =
        app.screen.height *
        focusCenter.y;

      const defaultCenterX =
        app.screen.width /
        2;

      const defaultCenterY =
        app.screen.height /
        2;

      const offsetX =
        defaultCenterX -
        desiredCenterX;

      const offsetY =
        defaultCenterY -
        desiredCenterY;

      model.focus(
        event.global.x +
          offsetX,

        event.global.y +
          offsetY
      );
    }
  );

  await moveWindowToBottomRight();

  let frameCount =
    0;

  let lastTime =
    performance.now();

  app.ticker.add(
    () => {
      frameCount++;

      const now =
        performance.now();

      const elapsed =
        now -
        lastTime;

      if (
        elapsed >=
        1000
      ) {
        const fps =
          Math.round(
            (
              frameCount *
              1000
            ) /
              elapsed
          );

        fpsCounter.textContent =
          `FPS: ${fps}`;

        frameCount =
          0;

        lastTime =
          now;
      }
    }
  );

  console.log(
    "Model object:",
    model
  );

  console.log(
    "Available expressions:",
    model.internalModel
      ?.motionManager
      ?.expressionManager
      ?.definitions
  );
}

main().catch(
  (error) => {
    console.error(
      "Failed to start WSQ Pet:"
    );

    console.error(
      error
    );
  }
);