(function registerLessonSetupShell(globalObject) {
  const utils = globalObject.lessonSetupSharedUtils;
  const templateElement = document.getElementById("card-template");
  const cardListElement = document.getElementById("cards");
  const deckAmountElement = document.getElementById("deck-amount");
  const hintElement = document.getElementById("hint");
  const promptElement = document.getElementById("prompt");
  const generateButton = document.getElementById("btn-go");
  const startButton = document.getElementById("btn-start");
  const settingsContentElement = document.getElementById("settings-content");

  let isGenerating = false;

  function createElement(tagName, className, textContent) {
    const element = document.createElement(tagName);

    if (className) {
      element.className = className;
    }

    if (textContent !== undefined && textContent !== null) {
      element.textContent = String(textContent);
    }

    return element;
  }

  function createSettingShell(item) {
    const shellElement = createElement("section", "settings-item-shell");
    const headElement = createElement("div", "settings-item-head");
    const titleElement = createElement("p", "settings-item-title", item.label || "");

    headElement.appendChild(titleElement);

    if (item.description) {
      headElement.appendChild(
        createElement("p", "settings-item-description", item.description),
      );
    }

    shellElement.appendChild(headElement);
    return shellElement;
  }

  function emitSettingChange(settingId, value) {
    utils.emitBackendEvent("setting-changed", {
      id: String(settingId || ""),
      value: value,
    });
  }

  function updateDeckLabel() {
    deckAmountElement.textContent = utils.formatDeckLabel(
      cardListElement.querySelectorAll(".lesson-card").length,
    );
  }

  function updateActionState() {
    const hasCards = cardListElement.querySelectorAll(".lesson-card").length > 0;

    generateButton.disabled = isGenerating;
    promptElement.disabled = isGenerating;
    startButton.disabled = isGenerating || !hasCards;
  }

  function hydrateCard(cardElement, card) {
    cardElement.querySelector(".lesson-card__word").textContent = card.word || "";
    cardElement.querySelector(".meta-pill__value--unit").textContent = card.unit || "";
    cardElement.querySelector(".meta-pill__value--part").textContent = card.part || "";
    cardElement.querySelector(".meta-pill__value--level").textContent = card.level || "";
    cardElement.querySelector(".lesson-card__transcription").textContent = card.transcription || "";
    cardElement.querySelector(".lesson-card__translation").textContent = card.translation || "";
    cardElement.querySelector(".lesson-card__definition").textContent = card.definition || "";
    cardElement.querySelector(".lesson-card__example").textContent = card.example || "";
  }

  function finalizeEnter(cardElement) {
    function handleCardEnter(event) {
      if (event.target !== cardElement || event.propertyName !== "opacity") {
        return;
      }

      cardElement.classList.remove("fade-enter", "fade-enter-active");
      cardElement.removeEventListener("transitionend", handleCardEnter);
    }

    cardElement.addEventListener("transitionend", handleCardEnter);
    utils.doubleAnimationFrame(function () {
      cardElement.classList.add("fade-enter-active");
    });
  }

  function createCardElement(card) {
    const fragment = templateElement.content.cloneNode(true);
    const cardElement = fragment.querySelector(".lesson-card");

    cardElement.dataset.cardId = String(card.id || "");
    hydrateCard(cardElement, card);
    cardListElement.append(fragment);
    finalizeEnter(cardElement);

    return cardElement;
  }

  function renderCards(cards) {
    const normalizedCards = Array.isArray(cards) ? cards : [];
    const incomingIds = new Set(
      normalizedCards.map(function (card) {
        return String(card.id || "");
      }),
    );

    Array.from(cardListElement.querySelectorAll(".lesson-card")).forEach(function (cardElement) {
      if (!incomingIds.has(cardElement.dataset.cardId || "")) {
        cardElement.remove();
      }
    });

    normalizedCards.forEach(function (card) {
      const cardId = String(card.id || "");
      let cardElement = cardListElement.querySelector(
        '.lesson-card[data-card-id="' + cardId + '"]',
      );

      if (!cardElement) {
        cardElement = createCardElement(card);
      } else {
        hydrateCard(cardElement, card);
      }

      cardListElement.append(cardElement);
    });

    updateDeckLabel();
    updateActionState();
  }

  function finalizeRemoval(cardElement, previousPositions, callback) {
    cardElement.remove();
    updateDeckLabel();
    updateActionState();
    utils.runFlipAnimation(cardListElement, ".lesson-card", previousPositions, 220);

    if (typeof callback === "function") {
      callback();
    }
  }

  function removeCardElement(cardElement, callback) {
    if (!cardElement || cardElement.classList.contains("fade-exit-active")) {
      return;
    }

    const previousPositions = utils.capturePositions(cardListElement, ".lesson-card");
    cardElement.classList.add("fade-exit");

    utils.doubleAnimationFrame(function () {
      cardElement.classList.add("fade-exit-active");
    });

    function handleCardExit(event) {
      if (event.target !== cardElement || event.propertyName !== "opacity") {
        return;
      }

      cardElement.removeEventListener("transitionend", handleCardExit);
      finalizeRemoval(cardElement, previousPositions, callback);
    }

    cardElement.addEventListener("transitionend", handleCardExit);
  }

  function setHint(hint) {
    hintElement.innerHTML = hint || "";
  }

  function setGenerating(nextGeneratingState) {
    isGenerating = Boolean(nextGeneratingState);
    updateActionState();
  }

  function updateSettingsScrollFade() {
    const maxScrollTop = Math.max(
      settingsContentElement.scrollHeight - settingsContentElement.clientHeight,
      0,
    );
    const fadeRampDistance = 80;
    const topFadeStrength = Math.min(settingsContentElement.scrollTop / fadeRampDistance, 1);
    const bottomFadeStrength = maxScrollTop === 0
      ? 0
      : Math.min((maxScrollTop - settingsContentElement.scrollTop) / fadeRampDistance, 1);

    settingsContentElement.style.setProperty(
      "--settings-top-fade-start-alpha",
      String(1 - topFadeStrength),
    );
    settingsContentElement.style.setProperty(
      "--settings-bottom-fade-start-alpha",
      String(1 - bottomFadeStrength),
    );
  }

  function getPromptText() {
    return promptElement.value;
  }
  
  function createGroupElement(groupId, groupTitle) {
    const groupElement = createElement("section", "settings-group");

    groupElement.dataset.settingsGroupId = groupId;
    if (groupTitle) {
      groupElement.appendChild(createElement("p", "settings-group-title", groupTitle));
    }

    settingsContentElement.appendChild(groupElement);
    return groupElement;
  }

  function getGroupElement(block) {
    const groupId = String(block.group_id || "default");
    let groupElement = Array.from(
      settingsContentElement.querySelectorAll(".settings-group"),
    ).find(function (candidateElement) {
      return candidateElement.dataset.settingsGroupId === groupId;
    });

    if (!groupElement) {
      groupElement = createGroupElement(groupId, block.group_title || "");
    }

    return groupElement;
  }

  function hydrateSettingShell(shellElement, item) {
    const titleElement = shellElement.querySelector(".settings-item-title");
    const descriptionElement = shellElement.querySelector(".settings-item-description");

    if (titleElement) {
      titleElement.textContent = item.label || "";
    }

    if (descriptionElement) {
      descriptionElement.textContent = item.description || "";
    }
  }

  function setLevelPickerValue(trackElement, value) {
    const nextValue = String(value || "");

    Array.from(trackElement.querySelectorAll(".settings-level-step")).forEach(function (buttonElement) {
      const isActive = buttonElement.dataset.value === nextValue;

      buttonElement.classList.toggle("is-active", isActive);
      buttonElement.setAttribute("aria-pressed", isActive ? "true" : "false");
    });
  }

  function renderLevelPickerItem(item) {
    const shellElement = createSettingShell(item);
    const pickerElement = createElement("div", "settings-level-picker");
    const trackElement = createElement("div", "settings-level-track");
    const options = item.options

    trackElement.style.setProperty("--settings-level-count", String(Math.max(options.length, 1)));

    options.forEach(function (option) {
      const optionValue = option.value;
      const buttonElement = createElement(
        "button",
        "settings-level-step" + (optionValue === String(item.value || "") ? " is-active" : ""),
      );

      buttonElement.type = "button";
      buttonElement.dataset.settingControl = "true";
      buttonElement.dataset.value = optionValue;
      buttonElement.setAttribute("aria-pressed", optionValue === String(item.value || "") ? "true" : "false");

      const dotElement = createElement("span", "settings-level-dot");
      const labelElement = createElement(
        "span",
        "settings-level-label",
        option.label,
      );

      buttonElement.appendChild(dotElement);
      buttonElement.appendChild(labelElement);
      buttonElement.addEventListener("click", function () {
        setLevelPickerValue(trackElement, optionValue);
        emitSettingChange(item.id, optionValue);
      });
      trackElement.appendChild(buttonElement);
    });

    pickerElement.appendChild(trackElement);
    shellElement.appendChild(pickerElement);
    return shellElement;
  }

  function renderTextareaItem(item) {
    const shellElement = createSettingShell(item);
    const textareaElement = createElement("textarea", "request-input-area");

    textareaElement.value = item.value || "";
    textareaElement.rows = Number(item.rows) || 4;
    textareaElement.placeholder = item.placeholder || "";
    textareaElement.dataset.settingControl = "true";

    function flushTextareaValue() {
      emitSettingChange(item.id, textareaElement.value);
    }

    textareaElement.addEventListener("change", flushTextareaValue);
    textareaElement.addEventListener("blur", flushTextareaValue);
    shellElement.appendChild(textareaElement);
    return shellElement;
  }

  function syncTextareaBlock(shellElement, item) {
    hydrateSettingShell(shellElement, item);

    const textareaElement = shellElement.querySelector(".request-input-area");
    if (!textareaElement) {
      return;
    }

    textareaElement.rows = Number(item.rows) || 4;
    textareaElement.placeholder = item.placeholder || "";

    if (document.activeElement !== textareaElement) {
      textareaElement.value = item.value || "";
    }
  }

  function renderToggleListItem(item) {
    const shellElement = createSettingShell(item);
    const listElement = createElement("div", "settings-toggle-list");
    const options = Array.isArray(item.options) ? item.options : [];

    function emitDisabledTaskIds() {
      const disabledTaskIds = Array.from(
        listElement.querySelectorAll(".settings-toggle__input"),
      ).filter(function (inputElement) {
        return !inputElement.checked;
      }).map(function (inputElement) {
        return inputElement.value;
      });

      emitSettingChange(item.id, disabledTaskIds);
    }

    options.forEach(function (option) {
      const rowElement = createElement("label", "settings-toggle");
      const switchElement = createElement("span", "switch");
      const inputElement = document.createElement("input");
      const sliderElement = createElement("span", "slider");
      const bodyElement = createElement("span", "settings-toggle__body");
      const labelElement = createElement(
        "span",
        "settings-toggle__label",
        option.label || option.value || "",
      );
      const descriptionElement = createElement(
        "span",
        "settings-toggle__description",
        option.description || "",
      );
      const statusElement = createElement(
        "span",
        "settings-toggle__status",
        option.checked ? "On" : "Off",
      );

      inputElement.type = "checkbox";
      inputElement.className = "settings-toggle__input";
      inputElement.dataset.settingControl = "true";
      inputElement.value = option.value || "";
      inputElement.checked = Boolean(option.checked);

      inputElement.addEventListener("change", function () {
        const checkedCount = listElement.querySelectorAll(
          ".settings-toggle__input:checked",
        ).length;

        if (checkedCount === 0) {
          inputElement.checked = true;
          return;
        }

        statusElement.textContent = inputElement.checked ? "On" : "Off";
        emitDisabledTaskIds();
      });

      switchElement.appendChild(inputElement);
      switchElement.appendChild(sliderElement);
      bodyElement.appendChild(labelElement);
      bodyElement.appendChild(descriptionElement);
      rowElement.appendChild(switchElement);
      rowElement.appendChild(bodyElement);
      rowElement.appendChild(statusElement);
      listElement.appendChild(rowElement);
    });

    shellElement.appendChild(listElement);
    return shellElement;
  }

  function createSettingBlockElement(block) {
    let blockElement = null;

    if (block.type === "choice" || block.type === "level_picker") {
      blockElement = renderLevelPickerItem(block);
    } else if (block.type === "textarea") {
      blockElement = renderTextareaItem(block);
    } else if (block.type === "toggle_list") {
      blockElement = renderToggleListItem(block);
    }

    if (!blockElement) {
      return null;
    }

    blockElement.dataset.settingId = String(block.id || "");
    blockElement.dataset.settingType = String(block.type || "");
    return blockElement;
  }

  function addSettingBlock(block) {
    const settingId = String(block.id);
    const groupElement = getGroupElement(block);
    groupElement.appendChild(createSettingBlockElement(block));
    updateSettingsScrollFade();
  }

  generateButton.addEventListener("click", function () {
    utils.emitBackendEvent("btn-click", { id: "generate", prompt: getPromptText() });
  });

  startButton.addEventListener("click", function () {
    utils.emitBackendEvent("btn-click", { id: "start_lesson" });
  });

  cardListElement.addEventListener("click", function (event) {
    const removeButton = event.target.closest(".action-btn--remove");

    if (!removeButton) {
      return;
    }

    const cardElement = removeButton.closest(".lesson-card");
    const cardId = cardElement ? cardElement.dataset.cardId : "";

    removeCardElement(cardElement, function () {
      utils.emitBackendEvent("card-closed", { id: cardId });
    });
  });

  settingsContentElement.addEventListener("scroll", updateSettingsScrollFade);
  window.addEventListener("resize", updateSettingsScrollFade);

  globalObject.appBridge.observeState("lesson_setup/cards", renderCards, []);
  globalObject.appBridge.observeState("lesson_setup/hint", setHint, "");
  globalObject.appBridge.observeState("lesson_setup/settings_block", addSettingBlock, null);
  globalObject.appBridge.observeState("lesson_setup/is_generating", function (nextIsGenerating) {
    setGenerating(Boolean(nextIsGenerating));
  }, false);

  updateDeckLabel();
  updateSettingsScrollFade();
})(window);
