(function registerLessonSetupSharedUtils(globalObject) {
  function emitBackendEvent(eventName, payload) {
    if (globalObject.backend && typeof globalObject.backend.emitEvent === "function") {
      globalObject.backend.emitEvent(eventName, payload || {});
    }
  }

  function formatDeckLabel(count) {
    const normalizedCount = Number.isFinite(Number(count)) ? Math.max(0, Number(count)) : 0;
    return "Deck: " + normalizedCount + " card" + (normalizedCount === 1 ? "" : "s");
  }

  function doubleAnimationFrame(callback) {
    requestAnimationFrame(function () {
      requestAnimationFrame(callback);
    });
  }

  function capturePositions(container, selector) {
    const positions = new Map();

    for (const element of container.querySelectorAll(selector)) {
      positions.set(element, element.getBoundingClientRect());
    }

    return positions;
  }

  function clearFlipState(node) {
    if (node._flipAnimation) {
      node._flipAnimation.cancel();
      node._flipAnimation = null;
    }

    if (typeof node._cleanupFlipTransition === "function") {
      node._cleanupFlipTransition();
    }

    node.style.transition = "";
    node.style.transform = "";
  }

  function runFlipAnimation(container, selector, previousPositions, durationMs) {
    const trackedNodes = Array.from(container.querySelectorAll(selector));
    const startingRects = new Map();

    for (const [node, rect] of previousPositions.entries()) {
      startingRects.set(node, rect);
    }

    for (const node of trackedNodes) {
      clearFlipState(node);
    }

    for (const node of trackedNodes) {
      const firstRect = startingRects.get(node);
      if (!firstRect) {
        continue;
      }

      const finalRect = node.getBoundingClientRect();
      const deltaX = firstRect.left - finalRect.left;
      const deltaY = firstRect.top - finalRect.top;

      if (deltaX === 0 && deltaY === 0) {
        continue;
      }

      if (typeof node.animate === "function") {
        node._flipAnimation = node.animate(
          [
            { transform: "translate(" + deltaX + "px, " + deltaY + "px)" },
            { transform: "translate(0, 0)" },
          ],
          {
            duration: durationMs,
            easing: "ease",
          },
        );

        node._flipAnimation.addEventListener("finish", function () {
          node._flipAnimation = null;
        });

        node._flipAnimation.addEventListener("cancel", function () {
          node._flipAnimation = null;
        });

        continue;
      }

      node.style.transition = "none";
      node.style.transform = "translate(" + deltaX + "px, " + deltaY + "px)";

      node.getBoundingClientRect();

      node.style.transition = "transform " + durationMs + "ms ease";
      node.style.transform = "translate(0, 0)";

      function handleFlipTransitionEnd(event) {
        if (event.target !== node || event.propertyName !== "transform") {
          return;
        }

        cleanupFlipTransition();
      }

      function cleanupFlipTransition() {
        node.style.transition = "";
        node.style.transform = "";
        node.removeEventListener("transitionend", handleFlipTransitionEnd);
        node._cleanupFlipTransition = null;
      }

      node._cleanupFlipTransition = cleanupFlipTransition;
      node.addEventListener("transitionend", handleFlipTransitionEnd);
    }
  }

  globalObject.lessonSetupSharedUtils = {
    capturePositions: capturePositions,
    doubleAnimationFrame: doubleAnimationFrame,
    emitBackendEvent: emitBackendEvent,
    formatDeckLabel: formatDeckLabel,
    runFlipAnimation: runFlipAnimation,
  };
})(window);
