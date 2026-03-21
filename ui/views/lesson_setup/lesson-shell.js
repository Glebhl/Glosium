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

  function hydrateCard(cardElement, word, unit, part, level, transcription, translation, defenition, example) {
    cardElement.querySelector(".lesson-card__word").textContent = word;
    cardElement.querySelector(".meta-pill__value--unit").textContent = unit;
    cardElement.querySelector(".meta-pill__value--part").textContent = part;
    cardElement.querySelector(".meta-pill__value--level").textContent = level;
    cardElement.querySelector(".lesson-card__transcription").textContent = transcription;
    cardElement.querySelector(".lesson-card__translation").textContent = translation;
    cardElement.querySelector(".lesson-card__definition").textContent = defenition;
    cardElement.querySelector(".lesson-card__example").textContent = example;
  }

  function addCard(word, unit, part, level, transcription, translation, defenition, example, cardId) {
    const fragment = templateElement.content.cloneNode(true);
    const cardElement = fragment.querySelector(".lesson-card");
    const resolvedCardId =
      cardId || "card-" + Date.now() + "-" + Math.random().toString(16).slice(2);

    cardElement.dataset.cardId = resolvedCardId;
    hydrateCard(
      cardElement,
      word,
      unit,
      part,
      level,
      transcription,
      translation,
      defenition,
      example,
    );

    cardListElement.append(fragment);

    utils.doubleAnimationFrame(function () {
      cardElement.classList.add("fade-enter-active");
    });

    function handleCardEnter(event) {
      if (event.target !== cardElement || event.propertyName !== "opacity") {
        return;
      }

      cardElement.classList.remove("fade-enter", "fade-enter-active");
      cardElement.removeEventListener("transitionend", handleCardEnter);
    }

    cardElement.addEventListener("transitionend", handleCardEnter);

    updateDeckLabel();
    return resolvedCardId;
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

  function removeCard(cardId) {
    const cardElement = cardListElement.querySelector('.lesson-card[data-card-id="' + cardId + '"]');
    removeCardElement(cardElement);
  }

  function setHint(hint) {
    hintElement.innerHTML = hint || "";
  }

  function setGenerating(isGenerating) {
    generateButton.disabled = Boolean(isGenerating);
    startButton.disabled = Boolean(isGenerating);
    promptElement.disabled = Boolean(isGenerating);
  }

  function getPromtText() {
    return promptElement.value;
  }

  generateButton.addEventListener("click", function () {
    utils.emitBackendEvent("btn-click", { id: "generate" });
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

  globalObject.addCard = addCard;
  globalObject.getPromtText = getPromtText;
  globalObject.removeCard = removeCard;
  globalObject.setGenerating = setGenerating;
  globalObject.setHint = setHint;

  updateDeckLabel();
})(window);
