// Fill-in-the-blanks task interactions and answer extraction.

// Template used to create a keyboard key.
const fillingKeyTemplate = document.getElementById("key-template");
const FILLING_MODE_WORD_BANK = "word-bank";
const FILLING_MODE_TYPING = "typing";

// Shared state for the current fill-in-the-blanks task.
const fillingState = {
  filledWordIds: [],
  blankNodes: [],
  root: null,
  mode: FILLING_MODE_WORD_BANK,
  answer: null,
  keyboard: null,
  switchController: null,
};

// Incremental unique ID for word keys.
let fillingWordIdSeq = 0;

// Initialize the fill-in-the-blanks task:
// - render sentence fragments and blanks
// - render keyboard keys
// - attach click handlers
function initFillBlanks(el, fragmentsArray, keyboardArray) {
  const answer = el.querySelector(".task-answer--filling");
  const keyboard = el.querySelector(".task-keyboard");
  const modeSwitchRoot = el.querySelector(".task-keyboard__mode-switch");

  const fragments = Array.isArray(fragmentsArray) ? fragmentsArray : [];
  const words = Array.isArray(keyboardArray) ? keyboardArray : [];

  resetFillingState(el, answer, keyboard);

  // Clear previous content.
  answer.replaceChildren();
  keyboard.replaceChildren();

  buildFillingAnswerLayout(answer, fragments);

  // Cache blank nodes and reset filled values.
  fillingState.blankNodes = [...answer.querySelectorAll(".task-blank")];
  fillingState.filledWordIds = Array(fillingState.blankNodes.length).fill(null);

  // Render all keyboard words.
  for (let i = 0; i !== words.length; i += 1) {
    keyboard.append(createFillingKey(words[i]));
  }

  // Update continue button state after initial render.
  updateFillingContinueState();

  // Handle both:
  // - moving a word from keyboard to the first empty blank
  // - moving a word back from a blank to the keyboard
  function onKeyClick(event) {
    if (fillingState.mode !== FILLING_MODE_WORD_BANK) {
      return;
    }

    const button = event.target.closest(".task-key");

    if (!button) {
      return;
    }

    const id = button.dataset.id;
    const inKeyboard = keyboard.contains(button);

    lessonTaskUtils.runFlipAnimation([keyboard, answer], function () {
      if (inKeyboard) {
        const blankIndex = firstEmptyBlankIndex();

        if (blankIndex === -1) {
          return;
        }

        fillingState.blankNodes[blankIndex].append(button);
        fillingState.filledWordIds[blankIndex] = id;
      } else {
        const blankIndex = findFilledBlankIndex(id);

        if (blankIndex !== -1) {
          fillingState.filledWordIds[blankIndex] = null;
        }

        keyboard.append(button);
      }

      updateFillingContinueState();
    });
  }

  // Listen for clicks in both areas.
  keyboard.addEventListener("click", onKeyClick);
  answer.addEventListener("click", onKeyClick);

  for (let i = 0; i < fillingState.blankNodes.length; i += 1) {
    const input = fillingState.blankNodes[i].querySelector(".task-blank__input");

    if (!input) {
      continue;
    }

    input.addEventListener("input", updateFillingContinueState);
  }

  fillingState.switchController = window.lessonModeSwitch.attach(
    modeSwitchRoot,
    setFillingMode,
    FILLING_MODE_WORD_BANK,
  );
}

function resetFillingState(root, answer, keyboard) {
  fillingState.filledWordIds = [];
  fillingState.blankNodes = [];
  fillingState.root = root;
  fillingState.mode = FILLING_MODE_WORD_BANK;
  fillingState.answer = answer;
  fillingState.keyboard = keyboard;
  fillingState.switchController = null;
}

function buildFillingAnswerLayout(container, fragments) {
  for (let i = 0; i !== fragments.length; i += 1) {
    container.append(createFillingTextNode(fragments[i]));

    if (i !== fragments.length - 1) {
      container.append(createBlankNode());
    }
  }
}

// Create a plain text fragment between blank slots.
function createFillingTextNode(text) {
  const node = document.createElement("span");

  node.className = "filling-text";
  node.textContent = text === undefined ? "" : String(text);

  return node;
}

// Create an empty blank slot that can hold one selected word key or text input.
function createBlankNode() {
  const node = document.createElement("span");
  const inputWrap = document.createElement("span");
  const input = document.createElement("input");

  node.className = "task-blank";
  inputWrap.className = "task-blank__input-wrap";
  input.className = "task-blank__input";
  input.type = "text";
  input.autocomplete = "off";
  input.spellcheck = false;

  inputWrap.append(input);
  node.append(inputWrap);

  return node;
}

// Create a selectable keyboard key and assign it a unique ID.
function createFillingKey(text) {
  fillingWordIdSeq += 1;

  return lessonTaskUtils.createWordKeyNode(
    fillingKeyTemplate,
    text,
    fillingWordIdSeq,
  );
}

// Find the first blank that does not contain a selected word yet.
function firstEmptyBlankIndex() {
  for (let i = 0; i !== fillingState.filledWordIds.length; i += 1) {
    if (fillingState.filledWordIds[i] === null) {
      return i;
    }
  }

  return -1;
}

// Find the blank index that currently contains the given word ID.
function findFilledBlankIndex(id) {
  for (let i = 0; i !== fillingState.filledWordIds.length; i += 1) {
    if (fillingState.filledWordIds[i] === id) {
      return i;
    }
  }

  return -1;
}

// Enable the continue button only when all blanks are filled.
function updateFillingContinueState() {
  const blankCount = fillingState.blankNodes.length;

  if (blankCount === 0) {
    lessonTaskUtils.setContinueEnabled(true);
    return;
  }

  if (fillingState.mode === FILLING_MODE_TYPING) {
    for (let i = 0; i !== fillingState.blankNodes.length; i += 1) {
      const value = getTypingBlankValue(i);

      if (value.length === 0) {
        lessonTaskUtils.setContinueEnabled(false);
        return;
      }
    }

    lessonTaskUtils.setContinueEnabled(true);
    return;
  }

  for (let i = 0; i !== fillingState.filledWordIds.length; i += 1) {
    if (fillingState.filledWordIds[i] === null) {
      lessonTaskUtils.setContinueEnabled(false);
      return;
    }
  }

  lessonTaskUtils.setContinueEnabled(true);
}

// Extract selected answers in their current order and return them as JSON.
function getFillingAnswerString() {
  if (fillingState.mode === FILLING_MODE_TYPING) {
    const typedAnswers = [];

    for (let i = 0; i < fillingState.blankNodes.length; i += 1) {
      typedAnswers.push(getTypingBlankValue(i));
    }

    return JSON.stringify(typedAnswers);
  }

  const container = fillingState.answer;

  if (!container) {
    return "[]";
  }

  // Build a map: key ID -> displayed word text.
  const keys = container.querySelectorAll(".task-key");
  const keyMap = new Map();

  for (let i = 0; i !== keys.length; i += 1) {
    keyMap.set(keys[i].dataset.id, keys[i].textContent.trim());
  }

  // Collect answers in blank order.
  const result = [];

  for (let i = 0; i !== fillingState.filledWordIds.length; i += 1) {
    const id = fillingState.filledWordIds[i];

    if (!id) {
      continue;
    }

    const value = keyMap.get(id);

    if (value) {
      result.push(value);
    }
  }

  return JSON.stringify(result);
}

function setFillingMode(nextMode) {
  const mode =
    nextMode === FILLING_MODE_TYPING
      ? FILLING_MODE_TYPING
      : FILLING_MODE_WORD_BANK;

  fillingState.mode = mode;

  const isWordBankMode = mode === FILLING_MODE_WORD_BANK;

  fillingState.root?.classList.toggle("is-filling-word-bank", isWordBankMode);
  fillingState.root?.classList.toggle("is-filling-typing", !isWordBankMode);

  if (!isWordBankMode) {
    syncTypingInputsFromWordBank();
    focusFirstTypingBlank();
  }

  updateFillingContinueState();
}

function syncTypingInputsFromWordBank() {
  for (let i = 0; i < fillingState.blankNodes.length; i += 1) {
    const input = fillingState.blankNodes[i].querySelector(".task-blank__input");

    if (!input) {
      continue;
    }

    input.value = getWordBankBlankValue(i);
  }
}

function focusFirstTypingBlank() {
  for (let i = 0; i < fillingState.blankNodes.length; i += 1) {
    const input = fillingState.blankNodes[i].querySelector(".task-blank__input");

    if (!input) {
      continue;
    }

    input.focus();
    return;
  }
}

function getTypingBlankValue(index) {
  const blankNode = fillingState.blankNodes[index];
  const input = blankNode?.querySelector(".task-blank__input");

  return normalizeFillingText(input?.value || "");
}

function getWordBankBlankValue(index) {
  const wordId = fillingState.filledWordIds[index];

  if (!wordId || !fillingState.answer) {
    return "";
  }

  const keyElement = fillingState.answer.querySelector(
    `.task-key[data-id="${String(wordId)}"]`,
  );

  return normalizeFillingText(keyElement?.textContent || "");
}

function normalizeFillingText(text) {
  return String(text || "")
    .replace(/\s+/g, " ")
    .trim();
}

// Highlight the answer panel when the answer is incorrect.
function highlightFilling(isCorrect) {
  const root = fillingState.root;

  if (!root) {
    return;
  }

  const panel = root.querySelector(".task-answer-shell--filling");

  if (!panel) {
    return;
  }

  panel.classList.toggle("task-answer--invalid", !Boolean(isCorrect));
}
