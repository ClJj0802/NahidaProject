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

const RANDOM_AUDIO_LIST_PATH =
  "/sound/list.json";

const RANDOM_AUDIO_BASE_PATH =
  "/sound/";

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

  await appWindow.setPosition(
    new LogicalPosition(
      x,
      y
    )
  );
}

async function loadRandomAudioList(): Promise<string[]> {
  try {
    const response =
      await fetch(
        RANDOM_AUDIO_LIST_PATH
      );

    if (!response.ok) {
      throw new Error(
        `HTTP ${response.status}`
      );
    }

    const files =
      await response.json();

    if (!Array.isArray(files)) {
      throw new Error(
        "Random audio list is not an array"
      );
    }

    console.log(
      "Random audio files:",
      files
    );

    return files as string[];
  } catch (error) {
    console.error(
      "Failed to load random audio list:",
      error
    );

    return [];
  }
}

function createContextMenu() {
  const menu =
    document.createElement(
      "div"
    );

  menu.id =
    "usagi-context-menu";

  Object.assign(
    menu.style,
    {
      position: "fixed",
      display: "none",
      background:
        "rgba(30, 30, 30, 0.96)",
      color: "white",
      border:
        "1px solid rgba(255,255,255,0.2)",
      borderRadius: "8px",
      padding: "6px",
      zIndex: "99999",
      minWidth: "210px",
      fontFamily:
        "Segoe UI, sans-serif",
      fontSize: "14px",
      boxShadow:
        "0 6px 20px rgba(0,0,0,0.35)",
    }
  );

  document.body.appendChild(
    menu
  );

  return menu;
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

  const randomAudioFiles =
    await loadRandomAudioList();

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
      x: modelBounds.x,
      y: modelBounds.y,
      width: modelBounds.width,
      height: modelBounds.height,
    }
  );

  /*
   * Normal click audio
   */

  const rapAudio =
    new Audio(
      RAP_AUDIO_PATH
    );

  rapAudio.preload =
    "auto";

  rapAudio.volume =
    1;

  /*
   * Random hover audio
   */

  let currentRandomAudio:
    HTMLAudioElement | null =
    null;

  let lastRandomAudioIndex =
    -1;

  let hoverRandomSoundEnabled =
    true;

  let isMouseOverUsagi =
    false;

  const playRandomAudio =
    async () => {
      if (
        !hoverRandomSoundEnabled
      ) {
        return;
      }

      if (
        randomAudioFiles.length ===
        0
      ) {
        console.warn(
          "No random audio files found"
        );

        return;
      }

      let randomIndex =
        Math.floor(
          Math.random() *
            randomAudioFiles.length
        );

      if (
        randomAudioFiles.length >
        1
      ) {
        while (
          randomIndex ===
          lastRandomAudioIndex
        ) {
          randomIndex =
            Math.floor(
              Math.random() *
                randomAudioFiles.length
            );
        }
      }

      lastRandomAudioIndex =
        randomIndex;

      const filename =
        randomAudioFiles[
          randomIndex
        ];

      const path =
        RANDOM_AUDIO_BASE_PATH +
        filename;

      console.log(
        "Playing random audio:",
        path
      );

      if (
        currentRandomAudio
      ) {
        currentRandomAudio.pause();

        currentRandomAudio.currentTime =
          0;
      }

      currentRandomAudio =
        new Audio(
          path
        );

      currentRandomAudio.preload =
        "auto";

      currentRandomAudio.volume =
        1;

      try {
        await currentRandomAudio.play();

        console.log(
          "Random audio started:",
          filename
        );
      } catch (error) {
        console.error(
          "Failed to play random audio:",
          error
        );
      }
    };

  /*
   * Left click only
   */

  model.on(
    "pointertap",
    async (event) => {
      if (
        event.button !==
        0
      ) {
        return;
      }

      console.log(
        "Left click on Usagi"
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

  /*
   * Hover enter
   */

  model.on(
    "pointerover",
    async () => {
      if (
        isMouseOverUsagi
      ) {
        return;
      }

      isMouseOverUsagi =
        true;

      console.log(
        "Mouse entered Usagi"
      );

      await playRandomAudio();
    }
  );

  /*
   * Hover leave
   */

  model.on(
    "pointerout",
    () => {
      if (
        !isMouseOverUsagi
      ) {
        return;
      }

      isMouseOverUsagi =
        false;

      console.log(
        "Mouse left Usagi"
      );
    }
  );

  /*
   * Context menu
   */

  const contextMenu =
    createContextMenu();

  const updateContextMenu =
    () => {
      contextMenu.innerHTML =
        "";

      const toggleButton =
        document.createElement(
          "div"
        );

      toggleButton.textContent =
        hoverRandomSoundEnabled
          ? "✓ Random hover sound"
          : "Random hover sound";

      Object.assign(
        toggleButton.style,
        {
          padding:
            "8px 12px",

          cursor:
            "pointer",

          borderRadius:
            "5px",

          userSelect:
            "none",
        }
      );

      toggleButton.addEventListener(
        "mouseenter",
        () => {
          toggleButton.style.background =
            "rgba(255,255,255,0.12)";
        }
      );

      toggleButton.addEventListener(
        "mouseleave",
        () => {
          toggleButton.style.background =
            "transparent";
        }
      );

      toggleButton.addEventListener(
        "click",
        () => {
          hoverRandomSoundEnabled =
            !hoverRandomSoundEnabled;

          console.log(
            "Random hover sound:",
            hoverRandomSoundEnabled
          );

          if (
            !hoverRandomSoundEnabled &&
            currentRandomAudio
          ) {
            currentRandomAudio.pause();

            currentRandomAudio.currentTime =
              0;
          }

          contextMenu.style.display =
            "none";
        }
      );

      contextMenu.appendChild(
        toggleButton
      );
    };

  /*
   * Disable normal browser context menu
   */

  app.canvas.addEventListener(
    "contextmenu",
    (event) => {
      event.preventDefault();
    }
  );

  /*
   * Right click on Usagi
   */

  model.on(
    "rightclick",
    (event) => {
      event.stopPropagation();

      console.log(
        "Right click on Usagi"
      );

      updateContextMenu();

      contextMenu.style.left =
        `${event.clientX}px`;

      contextMenu.style.top =
        `${event.clientY}px`;

      contextMenu.style.display =
        "block";
    }
  );

  /*
   * Close context menu when clicking elsewhere
   */

  window.addEventListener(
    "pointerdown",
    (event) => {
      const target =
        event.target as Node;

      if (
        !contextMenu.contains(
          target
        )
      ) {
        contextMenu.style.display =
          "none";
      }
    }
  );

  /*
   * Disable automatic Live2D focus
   */

  model.automator.autoFocus =
    false;

  const focusCenter = {
    x: 0.5,
    y: 0.5,
  };

  /*
   * Mouse tracking
   */

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

  /*
   * FPS counter
   */

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