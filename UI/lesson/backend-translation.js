// Translation task: keyboard interactions, selected answer tracking,
// answer extraction, and validation highlighting.

const translationKeyTemplate = document.getElementById("key-template");
const TRANSLATION_MODE_WORD_BANK = "word-bank";
const TRANSLATION_MODE_TYPING = "typing";

const translationState = {
  selectedWordIds: [],
  rootElement: null,
  mode: TRANSLATION_MODE_WORD_BANK,
  answerContainer: null,
  keyboardContainer: null,
  keyboardBlock: null,
  hintWrap: null,
  typingWrap: null,
  typingInput: null,
  switchController: null,
};

let translationWordIdCounter = 0;

/**
 * Initialize a translation task.
 *
 * @param {HTMLElement} rootElement
 * @param {string} sentenceText
 * @param {string[]} keyboardWords
 * @param {string} [initialMode]
 * @returns {Function} highlightTranslation
 */
function initTranslation(
  rootElement,
  sentenceText,
  keyboardWords,
  initialMode = TRANSLATION_MODE_WORD_BANK,
) {
  const answerContainer = rootElement.querySelector(
    ".task-answer--translation",
  );
  const keyboardContainer = rootElement.querySelector(".task-keyboard");
  const keyboardBlock = rootElement.querySelector(".task-keyboard-block");
  const hintWrap = rootElement.querySelector(".task-hint-wrap");
  const typingWrap = rootElement.querySelector(".task-answer__typing-wrap");
  const typingInput = rootElement.querySelector(".task-answer__typing-input");
  const modeSwitchRoot = rootElement.querySelector(".task-keyboard__mode-switch");
  const promptElement = rootElement.querySelector(".translation-prompt");

  resetTranslationState(
    rootElement,
    answerContainer,
    keyboardContainer,
    keyboardBlock,
    hintWrap,
    typingWrap,
    typingInput,
  );

  promptElement.textContent =
    sentenceText === undefined ? "" : String(sentenceText);

  answerContainer.replaceChildren();
  keyboardContainer.replaceChildren();

  const words = Array.isArray(keyboardWords) ? keyboardWords : [];
  for (let i = 0; i < words.length; i += 1) {
    keyboardContainer.append(createTranslationKey(words[i]));
  }

  lessonTaskUtils.setContinueEnabled(false);

  function handleKeyClick(event) {
    if (translationState.mode !== TRANSLATION_MODE_WORD_BANK) {
      return;
    }

    const clickedKey = event.target.closest(".task-key");
    if (!clickedKey) {
      return;
    }

    const wordId = clickedKey.dataset.id;
    const isInsideKeyboard = keyboardContainer.contains(clickedKey);

    lessonTaskUtils.runFlipAnimation(
      [keyboardContainer, answerContainer],
      function () {
        if (isInsideKeyboard) {
          moveKeyToAnswer(clickedKey, answerContainer, wordId);
        } else {
          moveKeyToKeyboard(clickedKey, keyboardContainer, wordId);
        }

        updateTranslationContinueState();
      },
    );
  }

  keyboardContainer.addEventListener("click", handleKeyClick);
  answerContainer.addEventListener("click", handleKeyClick);
  typingInput.addEventListener("input", updateTranslationContinueState);

  // Initialize shared segmented switch behavior for this task.
  translationState.switchController = window.lessonModeSwitch.attach(
    modeSwitchRoot,
    setTranslationMode,
    initialMode,
  );

  return highlightTranslation;
}

/**
 * Reset internal state for a new translation task.
 *
 * @param {HTMLElement} rootElement
 */
function resetTranslationState(
  rootElement,
  answerContainer,
  keyboardContainer,
  keyboardBlock,
  hintWrap,
  typingWrap,
  typingInput,
) {
  translationState.selectedWordIds = [];
  translationState.rootElement = rootElement;
  translationState.mode = TRANSLATION_MODE_WORD_BANK;
  translationState.answerContainer = answerContainer;
  translationState.keyboardContainer = keyboardContainer;
  translationState.keyboardBlock = keyboardBlock;
  translationState.hintWrap = hintWrap;
  translationState.typingWrap = typingWrap;
  translationState.typingInput = typingInput;
  translationState.switchController = null;
}

/**
 * Create one keyboard key node for a translation word.
 *
 * @param {string} text
 * @returns {HTMLElement}
 */
function createTranslationKey(text) {
  translationWordIdCounter += 1;

  return lessonTaskUtils.createWordKeyNode(
    translationKeyTemplate,
    text,
    translationWordIdCounter,
  );
}

/**
 * Move a key from the keyboard into the answer area.
 *
 * @param {HTMLElement} keyElement
 * @param {HTMLElement} answerContainer
 * @param {string} wordId
 */
function moveKeyToAnswer(keyElement, answerContainer, wordId) {
  answerContainer.append(keyElement);
  translationState.selectedWordIds.push(wordId);
}

/**
 * Move a key from the answer area back into the keyboard.
 *
 * @param {HTMLElement} keyElement
 * @param {HTMLElement} keyboardContainer
 * @param {string} wordId
 */
function moveKeyToKeyboard(keyElement, keyboardContainer, wordId) {
  keyboardContainer.append(keyElement);
  removeSelectedWordId(wordId);
}

/**
 * Remove a word id from the selected answer order.
 *
 * @param {string} wordId
 */
function removeSelectedWordId(wordId) {
  const ids = translationState.selectedWordIds;

  for (let i = 0; i < ids.length; i += 1) {
    if (ids[i] === wordId) {
      ids.splice(i, 1);
      return;
    }
  }
}

/**
 * Continue button becomes enabled when at least one word is selected.
 */
function updateTranslationContinueState() {
  if (translationState.mode === TRANSLATION_MODE_TYPING) {
    const typedText = getTypingAnswerString();
    lessonTaskUtils.setContinueEnabled(typedText.length > 0);
    return;
  }

  lessonTaskUtils.setContinueEnabled(translationState.selectedWordIds.length > 0);
}

/**
 * Switch between word bank and typing modes.
 *
 * @param {string} nextMode
 */
function setTranslationMode(nextMode) {
  const mode =
    nextMode === TRANSLATION_MODE_TYPING
      ? TRANSLATION_MODE_TYPING
      : TRANSLATION_MODE_WORD_BANK;

  translationState.mode = mode;

  const isWordBankMode = mode === TRANSLATION_MODE_WORD_BANK;

  // Toggle root classes to drive smooth CSS transitions for mode panels.
  translationState.rootElement?.classList.toggle(
    "is-translation-word-bank",
    isWordBankMode,
  );
  translationState.rootElement?.classList.toggle(
    "is-translation-typing",
    !isWordBankMode,
  );

  // Prefill typing mode from current word-bank answer for easier switching.
  if (!isWordBankMode && translationState.typingInput) {
    const currentText = normalizeTranslationText(translationState.typingInput.value);
    if (currentText.length === 0) {
      translationState.typingInput.value = getWordBankAnswerString();
    }
    translationState.typingInput.focus();
  }

  updateTranslationContinueState();
}

/**
 * Return normalized typing-mode answer.
 *
 * @returns {string}
 */
function getTypingAnswerString() {
  if (!translationState.typingInput) {
    return "";
  }

  return normalizeTranslationText(translationState.typingInput.value);
}

/**
 * Normalize answer text so both input modes produce the same format.
 *
 * @param {string} text
 * @returns {string}
 */
function normalizeTranslationText(text) {
  return String(text || "")
    .replace(/\s+/g, " ")
    .trim();
}

/**
 * Build the selected translation answer as a space-separated string.
 *
 * @returns {string}
 */
function getTranslationAnswerString() {
  if (translationState.mode === TRANSLATION_MODE_TYPING) {
    return getTypingAnswerString();
  }

  return getWordBankAnswerString();
}

/**
 * Build the selected answer from word-bank mode.
 *
 * @returns {string}
 */
function getWordBankAnswerString() {
  const rootElement = translationState.rootElement;
  if (!rootElement) {
    return "";
  }

  const answerContainer = rootElement.querySelector(
    ".task-answer--translation",
  );
  if (!answerContainer) {
    return "";
  }

  const keyElements = answerContainer.querySelectorAll(".task-key");
  const textById = new Map();

  for (let i = 0; i < keyElements.length; i += 1) {
    const keyElement = keyElements[i];
    textById.set(keyElement.dataset.id, keyElement.textContent.trim());
  }

  const resultWords = [];

  for (let i = 0; i < translationState.selectedWordIds.length; i += 1) {
    const wordId = translationState.selectedWordIds[i];
    const wordText = textById.get(wordId);

    if (wordText) {
      resultWords.push(wordText);
    }
  }

  return normalizeTranslationText(resultWords.join(" "));
}

/**
 * Highlight the answer area depending on correctness.
 *
 * @param {boolean} isCorrect
 */
function highlightTranslation(isCorrect) {
  const rootElement = translationState.rootElement;
  if (!rootElement) {
    return;
  }

  const answerShell = rootElement.querySelector(
    ".task-answer-shell--translation",
  );
  if (!answerShell) {
    return;
  }

  answerShell.classList.toggle("task-answer--invalid", !Boolean(isCorrect));
}
