(function registerLessonSetupShell(globalObject) {
  const utils = globalObject.lessonSetupSharedUtils;
  const templateElement = document.getElementById("card-template");
  const cardListElement = document.getElementById("cards");
  const deckAmountElement = document.getElementById("deck-amount");
  const hintElement = document.getElementById("hint");
  const promptElement = document.getElementById("prompt");
  const generateButton = document.getElementById("btn-go");
  const startButton = document.getElementById("btn-start");

  function updateDeckLabel() {
    deckAmountElement.textContent = utils.formatDeckLabel(
      cardListElement.querySelectorAll(".lesson-card").length,
    );
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
  }

  function finalizeRemoval(cardElement, previousPositions, callback) {
    cardElement.remove();
    updateDeckLabel();
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

  function setGenerating(isGenerating) {
    generateButton.disabled = Boolean(isGenerating);
    startButton.disabled = Boolean(isGenerating);
    promptElement.disabled = Boolean(isGenerating);
  }

  function getPromptText() {
    return promptElement.value;
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

  globalObject.appBridge.observeState("lesson_setup/cards", renderCards, []);
  globalObject.appBridge.observeState("lesson_setup/hint", setHint, "");
  globalObject.appBridge.observeState("lesson_setup/is_generating", function (isGenerating) {
    setGenerating(Boolean(isGenerating));
  }, false);

  updateDeckLabel();
})(window);
