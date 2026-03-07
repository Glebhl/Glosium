// Shared lesson screen orchestration and utility helpers.

const stage = document.getElementById("taskStage");
const fill = document.getElementById("progressFill");
const ptext = document.getElementById("progressText");
const continueButton = document.getElementById("continue");
const skipButton = document.getElementById("skip");

const taskState = { currentEl: null, transitionFallbackMs: 500 };

const hydrators = {
  explanation: function (el, data) {
    initExplanation(el, data.cards);
  },
  matching: function (el, data) {
    initMatching(el, data.pairs);
  },
  translation: function (el, data) {
    initTranslation(el, data.sentence, data.keyboard);
  },
  filling: function (el, data) {
    initFillBlanks(el, data.sentence, data.keyboard);
  },
  question: function (el, data) {
    if (typeof initQuestion === "function") {
      initQuestion(el, data.question, data.paragraph, data.answers);
    }
  },
};

const lessonTaskUtils = window.lessonTaskUtils ? window.lessonTaskUtils : {};

function setContinueEnabled(enabled) {
  continueButton.disabled = !Boolean(enabled);
}

function collectWordKeys(containers) {
  const result = [];
  for (let i = 0; i != containers.length; i += 1) {
    const nodes = containers[i].querySelectorAll(".word-key");
    for (let j = 0; j != nodes.length; j += 1) {
      result.push(nodes[j]);
    }
  }
  return result;
}

function runFlipAnimation(containers, domMutation, durationMs) {
  const flipDuration = durationMs === undefined ? 200 : durationMs;
  const nodesBefore = collectWordKeys(containers);
  const firstRects = new Map();
  for (let i = 0; i != nodesBefore.length; i += 1) {
    const node = nodesBefore[i];
    firstRects.set(node, node.getBoundingClientRect());
  }
  domMutation();
  const nodesAfter = collectWordKeys(containers);
  for (let i = 0; i != nodesAfter.length; i += 1) {
    const node = nodesAfter[i];
    const first = firstRects.get(node);
    if (!first) {
      continue;
    }
    const last = node.getBoundingClientRect();
    const dx = first.left - last.left;
    const dy = first.top - last.top;
    if (dx === 0) {
      if (dy === 0) {
        continue;
      }
    }
    node.style.transition = "transform\x200s";
    node.style.transform = "translate(" + dx + "px,\x20" + dy + "px)";
    requestAnimationFrame(function () {
      node.style.transition = "transform\x20" + flipDuration + "ms\x20ease";
      node.style.transform = "translate(0,\x200)";
    });
    node.addEventListener(
      "transitionend",
      function () {
        node.style.transition = "";
        node.style.transform = "";
      },
      { once: true },
    );
  }
}

function createWordKeyNode(template, text, id) {
  const fragment = template.content.cloneNode(true);
  const button = fragment.querySelector(".word-key");
  button.textContent = String(text);
  button.dataset.id = String(id);
  return button;
}

function shuffleArrayInPlace(items) {
  for (let i = items.length - 1; i != 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    const current = items[i];
    items[i] = items[j];
    items[j] = current;
  }
  return items;
}

lessonTaskUtils.runFlipAnimation = runFlipAnimation;
lessonTaskUtils.createWordKeyNode = createWordKeyNode;
lessonTaskUtils.setContinueEnabled = setContinueEnabled;
lessonTaskUtils.shuffleArrayInPlace = shuffleArrayInPlace;
window.lessonTaskUtils = lessonTaskUtils;

function hydrate(type, el, data) {
  const payload = data ? data : {};
  if (!type) {
    return;
  }
  if (!hydrators[type]) {
    return;
  }
  hydrators[type](el, payload);
}

function createFromTemplate(templateName) {
  const templateId = "tpl-" + templateName;
  const template = document.getElementById(templateId);
  if (!template) {
    throw new Error("Template_not_found:" + templateId);
  }
  const fragment = template.content.cloneNode(true);
  const taskEl = fragment.querySelector(".task-screen");
  if (!taskEl) {
    throw new Error("Template_has_no_task-screen:" + templateId);
  }
  return taskEl;
}

function setTask(templateName, direction, data) {
  const payload = data ? data : {};
  const moveDirection = direction ? direction : "next";
  setContinueEnabled(false);
  const nextEl = createFromTemplate(templateName);
  hydrate(templateName, nextEl, payload);
  const incomingClass = moveDirection === "prev" ? "is-left" : "is-right";
  const outgoingClass = moveDirection === "prev" ? "is-right" : "is-left";
  nextEl.classList.add(incomingClass);
  stage.append(nextEl);
  nextEl.getBoundingClientRect();
  nextEl.classList.remove("is-left");
  nextEl.classList.remove("is-right");
  nextEl.classList.add("is-center");
  if (taskState.currentEl) {
    taskState.currentEl.classList.remove("is-center");
    taskState.currentEl.classList.add(outgoingClass);
  }
  return waitTransition(nextEl, taskState.transitionFallbackMs).then(
    function () {
      if (taskState.currentEl) {
        taskState.currentEl.remove();
      }
      taskState.currentEl = nextEl;
    },
  );
}

function waitTransition(el, timeoutMs) {
  return new Promise(function (resolve) {
    let done = false;
    let timer = null;
    function finish() {
      if (done) {
        return;
      }
      done = true;
      clearTimeout(timer);
      el.removeEventListener("transitionend", onEnd);
      resolve();
    }
    function onEnd(event) {
      if (event.target !== el) {
        return;
      }
      if (event.propertyName !== "transform") {
        return;
      }
      finish();
    }
    timer = setTimeout(finish, timeoutMs);
    el.addEventListener("transitionend", onEnd);
  });
}

function setStep(stepIndex, stepsTotal) {
  const totalValue = Number(stepsTotal);
  const safeTotal = Number.isFinite(totalValue) ? Math.max(0, totalValue) : 0;
  const stepValue = Number(stepIndex);
  const normalizedStep = Number.isFinite(stepValue) ? stepValue : 0;
  const clamped = Math.max(0, Math.min(normalizedStep, safeTotal));
  const percent = safeTotal === 0 ? 0 : (clamped / safeTotal) * 100;
  fill.style.width = String(percent) + "%";
  ptext.textContent = String(clamped) + "\x20/\x20" + String(safeTotal);
}

function emitBackendEvent(name, payload) {
  if (!backend) {
    return;
  }
  if (typeof backend.emitEvent !== "function") {
    return;
  }
  backend.emitEvent(name, payload);
}

continueButton.addEventListener("click", function () {
  emitBackendEvent("btn-click", { id: "continue" });
});

skipButton.addEventListener("click", function () {
  emitBackendEvent("btn-click", { id: "skip" });
});
