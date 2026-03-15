// Shared lesson screen orchestration and helper utilities.

// ===== DOM references ========================================================

const stage = document.getElementById("taskStage");
const progressFill = document.getElementById("progressFill");
const progressText = document.getElementById("progressText");
const continueButton = document.getElementById("continue");
const skipButton = document.getElementById("skip");

// ===== Shared state ==========================================================

const taskState = {
  currentElement: null,
  transitionFallbackMs: 500,
  transitionId: 0,
};

// ===== Task hydrators ========================================================
// Each hydrator mounts task-specific content into a freshly created task element.

const hydrators = {
  explanation(el, data) {
    initExplanation(el, data.cards);
  },

  matching(el, data) {
    initMatching(el, data.pairs);
  },

  translation(el, data) {
    initTranslation(el, data.sentence, data.keyboard, data.mode);
  },

  filling(el, data) {
    initFillBlanks(el, data.sentence, data.keyboard, data.mode);
  },

  question(el, data) {
    initQuestion(el, data.question, data.paragraph, data.options, data.answer);
  },
};

// Reuse an existing shared utils object if one already exists.
const lessonTaskUtils = window.lessonTaskUtils || {};

// ===== Basic UI helpers ======================================================

// Enable or disable the footer action button for the current task.
function setContinueEnabled(enabled) {
  continueButton.disabled = !Boolean(enabled);
}

// Update the progress bar and text above the task area.
function setStep(stepIndex, stepsTotal) {
  const total = Number.isFinite(Number(stepsTotal))
    ? Math.max(0, Number(stepsTotal))
    : 0;

  const step = Number.isFinite(Number(stepIndex)) ? Number(stepIndex) : 0;
  const clampedStep = Math.max(0, Math.min(step, total));

  const percent = total === 0 ? 0 : (clampedStep / total) * 100;

  progressFill.style.width = `${percent}%`;
  progressText.textContent = `${clampedStep} / ${total}`;
}

// ===== FLIP animation helpers ===============================================

// Collect all movable key nodes from the provided containers.
function collectTaskKeys(containers) {
  const keys = [];

  for (const container of containers) {
    const nodes = container.querySelectorAll(".task-key");
    for (const node of nodes) {
      keys.push(node);
    }
  }

  return keys;
}

// Run a FLIP animation after the DOM order of task keys changes.
function runFlipAnimation(containers, mutateDom, durationMs = 200) {
  const nodesBefore = collectTaskKeys(containers);
  const firstRects = new Map();

  // Save initial positions before DOM mutation.
  for (const node of nodesBefore) {
    firstRects.set(node, node.getBoundingClientRect());
  }

  // Perform the actual DOM update.
  mutateDom();

  const nodesAfter = collectTaskKeys(containers);

  // Animate each node from its old position to its new one.
  for (const node of nodesAfter) {
    const firstRect = firstRects.get(node);
    if (!firstRect) {
      continue;
    }

    const lastRect = node.getBoundingClientRect();
    const deltaX = firstRect.left - lastRect.left;
    const deltaY = firstRect.top - lastRect.top;

    // Skip nodes that did not move.
    if (deltaX === 0 && deltaY === 0) {
      continue;
    }

    node.style.transition = "transform 0s";
    node.style.transform = `translate(${deltaX}px, ${deltaY}px)`;

    requestAnimationFrame(() => {
      node.style.transition = `transform ${durationMs}ms ease`;
      node.style.transform = "translate(0, 0)";
    });

    node.addEventListener(
      "transitionend",
      () => {
        node.style.transition = "";
        node.style.transform = "";
      },
      { once: true },
    );
  }
}

// ===== Shared task element helpers ==========================================

// Create a keyboard key node from the shared template.
function createWordKeyNode(template, text, id) {
  const fragment = template.content.cloneNode(true);
  const button = fragment.querySelector(".task-key");

  button.textContent = String(text);
  button.dataset.id = String(id);

  return button;
}

// Shuffle an array in place using the Fisher-Yates algorithm.
function shuffleArrayInPlace(items) {
  for (let i = items.length - 1; i > 0; i -= 1) {
    const randomIndex = Math.floor(Math.random() * (i + 1));
    [items[i], items[randomIndex]] = [items[randomIndex], items[i]];
  }

  return items;
}

// Expose shared helpers for task modules.
lessonTaskUtils.runFlipAnimation = runFlipAnimation;
lessonTaskUtils.createWordKeyNode = createWordKeyNode;
lessonTaskUtils.setContinueEnabled = setContinueEnabled;
lessonTaskUtils.shuffleArrayInPlace = shuffleArrayInPlace;
window.lessonTaskUtils = lessonTaskUtils;

// ===== Task creation and hydration ==========================================

// Run task-specific mounting logic for a given task type.
function hydrate(type, element, data = {}) {
  if (!type || !hydrators[type]) {
    return;
  }

  hydrators[type](element, data);
}

// Clone a task element from its HTML template.
function createFromTemplate(templateName) {
  const templateId = `tpl-${templateName}`;
  const template = document.getElementById(templateId);

  if (!template) {
    throw new Error(`Template_not_found:${templateId}`);
  }

  const fragment = template.content.cloneNode(true);
  const taskElement = fragment.querySelector(".lesson-task");

  if (!taskElement) {
    throw new Error(`Template_has_no_lesson-task:${templateId}`);
  }

  return taskElement;
}

// Return CSS classes used for slide-in / slide-out transitions.
function getTransitionClasses(direction) {
  const isPrevious = direction === "prev";

  return {
    incoming: isPrevious ? "is-enter-from-left" : "is-enter-from-right",
    outgoing: isPrevious ? "is-enter-from-right" : "is-enter-from-left",
  };
}

// Remove every mounted task except the one that should remain on stage.
function cleanupTaskElements(keepElement = null) {
  const mountedTasks = stage.querySelectorAll(".lesson-task");

  for (const taskElement of mountedTasks) {
    if (taskElement === keepElement) {
      continue;
    }

    taskElement.remove();
  }
}

// Mount a new task, animate it in, and remove the previous one after transition.
function setTask(templateName, direction = "next", data = {}) {
  setContinueEnabled(false);

  const transitionId = taskState.transitionId + 1;
  taskState.transitionId = transitionId;

  const previousElement = taskState.currentElement;
  const nextElement = createFromTemplate(templateName);

  hydrate(templateName, nextElement, data);
  taskState.currentElement = nextElement;

  const { incoming, outgoing } = getTransitionClasses(direction);

  cleanupTaskElements(previousElement);

  // Prepare the new element in its off-screen position.
  nextElement.classList.add(incoming);
  stage.append(nextElement);

  // Force layout so the browser registers the starting position
  // before we remove the enter class.
  void nextElement.offsetWidth;

  // Start the enter animation.
  nextElement.classList.remove("is-enter-from-left", "is-enter-from-right");
  nextElement.classList.add("is-active");

  // Start the exit animation for the current element, if any.
  if (previousElement) {
    previousElement.classList.remove("is-active");
    previousElement.classList.add(outgoing);
  }

  return waitTransition(nextElement, taskState.transitionFallbackMs).then(() => {
    if (taskState.transitionId !== transitionId) {
      cleanupTaskElements(taskState.currentElement);
      return;
    }

    cleanupTaskElements(nextElement);
  });
}

// Resolve when the transition ends, or after a fallback timeout.
function waitTransition(element, timeoutMs) {
  return new Promise((resolve) => {
    let isFinished = false;

    const finish = () => {
      if (isFinished) {
        return;
      }

      isFinished = true;
      clearTimeout(timeoutId);
      element.removeEventListener("transitionend", handleTransitionEnd);
      resolve();
    };

    const handleTransitionEnd = (event) => {
      if (event.target !== element) {
        return;
      }

      if (event.propertyName !== "transform") {
        return;
      }

      finish();
    };

    const timeoutId = setTimeout(finish, timeoutMs);
    element.addEventListener("transitionend", handleTransitionEnd);
  });
}

// ===== Backend bridge ========================================================

// Forward a UI event to the backend bridge if it exists.
function emitBackendEvent(name, payload) {
  if (!backend || typeof backend.emitEvent !== "function") {
    return;
  }

  backend.emitEvent(name, payload);
}

// Forward footer button clicks to the backend.
continueButton.addEventListener("click", () => {
  emitBackendEvent("btn-click", { id: "continue" });
});

skipButton.addEventListener("click", () => {
  emitBackendEvent("btn-click", { id: "skip" });
});
