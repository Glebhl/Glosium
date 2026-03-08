// Shared mode switch helper used by tasks that have segmented toggle buttons.
(function registerLessonModeSwitch(globalObject) {
  /**
   * Attach mode switch behavior to a button group.
   *
   * @param {HTMLElement} switchRoot
   * @param {(mode: string) => void} onModeChange
   * @param {string} initialMode
   * @returns {{setMode: Function, getMode: Function}}
   */
  function attachLessonModeSwitch(switchRoot, onModeChange, initialMode) {
    if (!switchRoot) {
      return {
        setMode: function () {},
        getMode: function () {
          return "";
        },
      };
    }

    const buttons = Array.from(
      switchRoot.querySelectorAll(".task-keyboard__mode-button[data-mode]"),
    );

    let currentMode = "";

    function setMode(mode, emitChange = true) {
      const nextMode = String(mode || "");

      // Ignore mode values that are not represented by a button.
      if (!buttons.some((button) => button.dataset.mode === nextMode)) {
        return;
      }

      currentMode = nextMode;

      // Keep only the active button marked with .is-active.
      for (let i = 0; i < buttons.length; i += 1) {
        const button = buttons[i];
        button.classList.toggle("is-active", button.dataset.mode === nextMode);
      }

      if (emitChange && typeof onModeChange === "function") {
        onModeChange(nextMode);
      }
    }

    for (let i = 0; i < buttons.length; i += 1) {
      const button = buttons[i];
      button.addEventListener("click", function () {
        setMode(button.dataset.mode, true);
      });
    }

    if (buttons.length > 0) {
      const fallbackMode = buttons[0].dataset.mode;
      const preferredMode =
        buttons.find((button) => button.dataset.mode === initialMode)?.dataset
          .mode || fallbackMode;

      setMode(preferredMode, true);
    }

    return {
      setMode: function (mode) {
        setMode(mode, true);
      },
      getMode: function () {
        return currentMode;
      },
    };
  }

  globalObject.lessonModeSwitch = globalObject.lessonModeSwitch || {};
  globalObject.lessonModeSwitch.attach = attachLessonModeSwitch;
})(window);
