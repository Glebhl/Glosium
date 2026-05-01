const elements = {
  settingsContent: document.getElementById("settings-content"),
};

const DEFAULT_LANGUAGE_LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"];

const DEFAULT_TASKS = [
  {
    id: "explanation",
    label: "Explanation",
    description: "Short teaching step without an answer field.",
  },
  {
    id: "matching",
    label: "Matching",
    description: "Connect words, meanings, or pairs inside one task.",
  },
  {
    id: "filling",
    label: "Fill in the blank",
    description: "Complete short sentences with guided recall.",
  },
  {
    id: "translation",
    label: "Translation",
    description: "Translate short phrases or sentences into English.",
  },
  {
    id: "question",
    label: "Question",
    description: "Read a short passage and answer a comprehension question.",
  },
];

let settings = loadSettingsValues();
let detachScrollFade = null;

// Settings change handler
export function onChange(id, value) {
  console.log(`id=${id} value=${value}`);
}

export function loadSettings({
  availableTasks = DEFAULT_TASKS,
  languageLevels = DEFAULT_LANGUAGE_LEVELS,
  isAdditionalRequestAvailable = true,
} = {}) {
  elements.settingsContent.replaceChildren();
  elements.settingsContent.appendChild(renderLessonProfileGroup(languageLevels));

  const tuningGroup = renderLessonTuningGroup(availableTasks, isAdditionalRequestAvailable);
  if (tuningGroup) {
    elements.settingsContent.appendChild(tuningGroup);
  }

  attachScrollFade(elements.settingsContent);
  updateScrollFade(elements.settingsContent);
}

export function getSettingsValue(key) {
  return settings[key];
}

function loadSettingsValues() {
  return {
    languageLevel: "A1",
    additionalRequest: "",
    disabledTaskIds: [],
  };
}

function emitChange(id, value) {
  onChange(id, value);
}

function createElement(tagName, className, textContent) {
  const element = document.createElement(tagName);

  if (className) {
    element.className = className;
  }

  if (textContent !== undefined) {
    element.textContent = String(textContent);
  }

  return element;
}

function createGroup(title) {
  const groupElement = createElement("section", "settings-group");

  if (title) {
    groupElement.appendChild(createElement("p", "settings-group-title", title));
  }

  return groupElement;
}

function createSettingShell(title, description) {
  const shellElement = createElement("section", "settings-item-shell");
  const headElement = createElement("div", "settings-item-head");

  headElement.appendChild(createElement("p", "settings-item-title", title));

  if (description) {
    headElement.appendChild(createElement("p", "settings-item-description", description));
  }

  shellElement.appendChild(headElement);
  return shellElement;
}

function renderLessonProfileGroup(languageLevels) {
  const groupElement = createGroup("Lesson profile");

  groupElement.appendChild(renderLevelPicker(languageLevels));
  return groupElement;
}

function renderLessonTuningGroup(availableTasks, isAdditionalRequestAvailable) {
  const groupElement = createGroup("Lesson tuning");
  let hasItems = false;

  if (isAdditionalRequestAvailable) {
    groupElement.appendChild(renderAdditionalRequest());
    hasItems = true;
  }

  if (availableTasks.length > 0) {
    groupElement.appendChild(renderTaskToggles(availableTasks));
    hasItems = true;
  }

  return hasItems ? groupElement : null;
}

function renderLevelPicker(languageLevels) {
  const shellElement = createSettingShell(
    "Learner level",
    "Used for lesson pacing, explanations, and task difficulty.",
  );
  const pickerElement = createElement("div", "settings-level-picker");
  const trackElement = createElement("div", "settings-level-track");

  trackElement.style.setProperty("--settings-level-count", String(languageLevels.length || 1));

  languageLevels.forEach(function (level) {
    const levelValue = String(level);
    const buttonElement = createElement("button", "settings-level-step");

    buttonElement.type = "button";
    buttonElement.dataset.value = levelValue;
    buttonElement.setAttribute("aria-pressed", "false");
    buttonElement.appendChild(createElement("span", "settings-level-dot"));
    buttonElement.appendChild(createElement("span", "settings-level-label", levelValue));
    buttonElement.addEventListener("click", function () {
      settings.languageLevel = levelValue;
      setLevelPickerValue(trackElement, levelValue);
      emitChange("languageLevel", levelValue);
    });

    trackElement.appendChild(buttonElement);
  });

  setLevelPickerValue(trackElement, settings.languageLevel);
  pickerElement.appendChild(trackElement);
  shellElement.appendChild(pickerElement);

  return shellElement;
}

function setLevelPickerValue(trackElement, value) {
  Array.from(trackElement.querySelectorAll(".settings-level-step")).forEach(function (buttonElement) {
    const isActive = buttonElement.dataset.value === value;

    buttonElement.classList.toggle("is-active", isActive);
    buttonElement.setAttribute("aria-pressed", isActive ? "true" : "false");
  });
}

function renderAdditionalRequest() {
  const shellElement = createSettingShell(
    "Lesson request",
    "Optional note for tone, context, grammar focus, or extra guidance.",
  );
  const textareaElement = createElement("textarea", "request-input-area");

  textareaElement.value = settings.additionalRequest;
  textareaElement.rows = 4;
  textareaElement.placeholder = 'For example: "More explanations and travel context"';
  textareaElement.addEventListener("input", function () {
    settings.additionalRequest = textareaElement.value;
    emitChange("additionalRequest", settings.additionalRequest);
  });

  shellElement.appendChild(textareaElement);
  return shellElement;
}

function renderTaskToggles(availableTasks) {
  const shellElement = createSettingShell(
    "Exercise types",
    "Turn off formats you do not want in this lesson.",
  );
  const listElement = createElement("div", "settings-toggle-list");

  availableTasks.forEach(function (task) {
    listElement.appendChild(createTaskToggle(task, listElement));
  });

  shellElement.appendChild(listElement);
  return shellElement;
}

function createTaskToggle(task, listElement) {
  const taskId = String(task.id ?? task.value ?? "");
  const rowElement = createElement("label", "settings-toggle");
  const switchElement = createElement("span", "switch");
  const inputElement = document.createElement("input");
  const sliderElement = createElement("span", "slider");
  const bodyElement = createElement("span", "settings-toggle__body");
  const statusElement = createElement("span", "settings-toggle__status");

  inputElement.type = "checkbox";
  inputElement.className = "settings-toggle__input";
  inputElement.value = taskId;
  inputElement.checked = !settings.disabledTaskIds.includes(taskId);

  bodyElement.appendChild(createElement("span", "settings-toggle__label", task.label || taskId));
  bodyElement.appendChild(createElement("span", "settings-toggle__description", task.description || ""));
  updateTaskStatus(statusElement, inputElement.checked);

  inputElement.addEventListener("change", function () {
    // A generated lesson needs at least one exercise type.
    // TODO replace with inputElement.disabled = true;
    if (!inputElement.checked && countCheckedTasks(listElement) === 0) {
      inputElement.checked = true;
      return;
    }

    updateTaskStatus(statusElement, inputElement.checked);
    settings.disabledTaskIds = getDisabledTaskIds(listElement);
    emitChange("disabledTaskIds", settings.disabledTaskIds.slice());
  });

  switchElement.appendChild(inputElement);
  switchElement.appendChild(sliderElement);
  rowElement.appendChild(switchElement);
  rowElement.appendChild(bodyElement);
  rowElement.appendChild(statusElement);

  return rowElement;
}

function countCheckedTasks(listElement) {
  return listElement.querySelectorAll(".settings-toggle__input:checked").length;
}

function getDisabledTaskIds(listElement) {
  return Array.from(listElement.querySelectorAll(".settings-toggle__input"))
    .filter(function (inputElement) {
      return !inputElement.checked;
    })
    .map(function (inputElement) {
      return inputElement.value;
    });
}

function updateTaskStatus(statusElement, isChecked) {
  statusElement.textContent = isChecked ? "On" : "Off";
}

function attachScrollFade(rootElement) {
  if (detachScrollFade) {
    detachScrollFade();
  }

  function handleScrollFade() {
    updateScrollFade(rootElement);
  }

  rootElement.addEventListener("scroll", handleScrollFade);
  window.addEventListener("resize", handleScrollFade);

  detachScrollFade = function () {
    rootElement.removeEventListener("scroll", handleScrollFade);
    window.removeEventListener("resize", handleScrollFade);
  };
}

function updateScrollFade(rootElement) {
  const maxScrollTop = Math.max(rootElement.scrollHeight - rootElement.clientHeight, 0);
  const fadeDistance = 80;
  const topFade = Math.min(rootElement.scrollTop / fadeDistance, 1);
  const bottomFade = maxScrollTop === 0
    ? 0
    : Math.min((maxScrollTop - rootElement.scrollTop) / fadeDistance, 1);

  rootElement.style.setProperty("--settings-top-fade-start-alpha", String(1 - topFade));
  rootElement.style.setProperty("--settings-bottom-fade-start-alpha", String(1 - bottomFade));
}
