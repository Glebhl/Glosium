(function registerLessonShell(globalObject) {
  const utils = globalObject.lessonSharedUtils;
  const stageElement = document.getElementById("taskStage");
  const progressFillElement = document.getElementById("progressFill");
  const progressTextElement = document.getElementById("progressText");
  const continueButton = document.getElementById("continue");
  const skipButton = document.getElementById("skip");

  const shellState = {
    activeTaskController: createEmptyTaskController(),
    activeTaskElement: null,
    activeTaskIndex: null,
    validationMarker: null,
    transitionFallbackMs: 500,
    transitionToken: 0,
  };

  function createEmptyTaskController() {
    return {
      destroy: function () {},
      getAnswer: function () {
        return "";
      },
      setValidity: function () {},
    };
  }

  function setStep(stepIndex, totalSteps) {
    const normalizedTotal = Number.isFinite(Number(totalSteps))
      ? Math.max(0, Number(totalSteps))
      : 0;
    const normalizedStep = Number.isFinite(Number(stepIndex))
      ? Math.max(0, Math.min(Number(stepIndex), normalizedTotal))
      : 0;
    const progressPercent =
      normalizedTotal === 0 ? 0 : (normalizedStep / normalizedTotal) * 100;

    progressFillElement.style.width = progressPercent + "%";
    progressTextElement.textContent = normalizedStep + " / " + normalizedTotal;
  }

  function createTaskElement(taskType) {
    return utils.cloneTemplateElement("tpl-" + taskType, ".lesson-task");
  }

  function getTaskTransitionClasses(direction) {
    if (direction === "prev") {
      return {
        incomingClassName: "is-enter-from-left",
        outgoingClassName: "is-enter-from-right",
      };
    }

    return {
      incomingClassName: "is-enter-from-right",
      outgoingClassName: "is-enter-from-left",
    };
  }

  function waitForTransition(element, timeoutMs) {
    return new Promise(function (resolve) {
      let finished = false;

      function finalize() {
        if (finished) {
          return;
        }

        finished = true;
        clearTimeout(timeoutId);
        element.removeEventListener("transitionend", handleTransitionEnd);
        resolve();
      }

      function handleTransitionEnd(event) {
        if (event.target === element && event.propertyName === "transform") {
          finalize();
        }
      }

      const timeoutId = setTimeout(finalize, timeoutMs);
      element.addEventListener("transitionend", handleTransitionEnd);
    });
  }

  function cleanupStage(keepElement) {
    const mountedTasks = stageElement.querySelectorAll(".lesson-task");

    for (const taskElement of mountedTasks) {
      if (taskElement !== keepElement) {
        taskElement.remove();
      }
    }
  }

  function mountTask(taskType, taskElement, payload) {
    const taskController = globalObject.lessonTaskRegistry.create(
      taskType,
      taskElement,
      payload || {},
    );

    if (!taskController) {
      throw new Error("Task_module_not_found:" + taskType);
    }

    return Object.assign(createEmptyTaskController(), taskController);
  }

  function setTask(taskType, direction, payload) {
    const transitionDirection = direction || "next";
    const nextTaskElement = createTaskElement(taskType);
    const previousTaskElement = shellState.activeTaskElement;
    const previousTaskController = shellState.activeTaskController;
    const transitionToken = shellState.transitionToken + 1;
    const transitionClasses = getTaskTransitionClasses(transitionDirection);

    shellState.transitionToken = transitionToken;
    shellState.activeTaskElement = nextTaskElement;

    utils.setContinueEnabled(false);
    skipButton.disabled = taskType === "loading";
    shellState.activeTaskController = mountTask(taskType, nextTaskElement, payload || {});

    if (previousTaskController && typeof previousTaskController.destroy === "function") {
      previousTaskController.destroy();
    }

    cleanupStage(previousTaskElement);

    nextTaskElement.classList.add(transitionClasses.incomingClassName);
    stageElement.append(nextTaskElement);

    void nextTaskElement.offsetWidth;

    nextTaskElement.classList.remove("is-enter-from-left", "is-enter-from-right");
    nextTaskElement.classList.add("is-active");

    if (previousTaskElement) {
      previousTaskElement.classList.remove("is-active");
      previousTaskElement.classList.add(transitionClasses.outgoingClassName);
    }

    return waitForTransition(nextTaskElement, shellState.transitionFallbackMs).then(function () {
      if (shellState.transitionToken !== transitionToken) {
        cleanupStage(shellState.activeTaskElement);
        return;
      }

      cleanupStage(nextTaskElement);
    });
  }

  function getActiveTaskAnswerString() {
    return shellState.activeTaskController.getAnswer();
  }

  function setActiveTaskValidity(isCorrect) {
    shellState.activeTaskController.setValidity(Boolean(isCorrect));
  }

  continueButton.addEventListener("click", function () {
    globalObject.appBridge.emitBackendEvent("btn-click", {
      id: "continue",
      answer: getActiveTaskAnswerString(),
    });
  });

  skipButton.addEventListener("click", function () {
    globalObject.appBridge.emitBackendEvent("btn-click", { id: "skip" });
  });

  globalObject.appBridge.observeState("lesson_flow/progress", function (progressState) {
    const nextState = progressState || {};
    setStep(nextState.stepIndex || 0, nextState.totalSteps || 0);
  }, {
    stepIndex: 0,
    totalSteps: 0,
  });

  globalObject.appBridge.observeState("lesson_flow/task", function (taskState) {
    if (!taskState) {
      return;
    }

    // if (taskState.taskIndex === shellState.activeTaskIndex) {
    //   return;
    // }

    shellState.activeTaskIndex = taskState.taskIndex;
    shellState.validationMarker = null;
    setTask(taskState.type, taskState.direction, taskState.payload);
  }, null);

  globalObject.appBridge.observeState("lesson_flow/validation", function (validationState) {
    if (!validationState) {
      shellState.validationMarker = null;
      setActiveTaskValidity(true);
      return;
    }

    const nextMarker = validationState.isCorrect ? "correct" : "incorrect";

    if (shellState.validationMarker === nextMarker) {
      return;
    }
    
    shellState.validationMarker = nextMarker;
    setActiveTaskValidity(validationState.isCorrect);
  }, null);
  setTask(
    "filling",
    "next",
    {
      "task_id": "filling",
      "sentence": ["I bougheffffffft fef ef efefefefe ef f ", "new car yestefef e fe ef fefefeferday.", "car is verye fe efefefef ef fast."],
      "keyboard": ["a", "The"],
      "mode": "word-bank",
      "typing_language": "en",
      "answers": ["a", "The"],
      "audio": false
    }
  )
})(window);

