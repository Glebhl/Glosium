// Fill-in-the-blanks task interactions and answer extraction.

const fillingKeyTemplate = document.getElementById("key-template");

const fillingState = {
  filledWordIds: [],
  blankNodes: [],
  root: null,
};

let fillingWordIdSeq = 0;

function initFillBlanks(el, fragmentsArray, keyboardArray) {
  const answer = el.querySelector(".filling-answer");
  const keyboard = el.querySelector(".keyboard");
  const fragments = Array.isArray(fragmentsArray) ? fragmentsArray : [];
  const words = Array.isArray(keyboardArray) ? keyboardArray : [];
  fillingState.root = el;
  answer.replaceChildren();
  keyboard.replaceChildren();
  for (let i = 0; i != fragments.length; i += 1) {
    answer.append(createFillingTextNode(fragments[i]));
    if (i !== fragments.length - 1) {
      answer.append(createBlankNode());
    }
  }
  fillingState.blankNodes = [...answer.querySelectorAll(".blank")];
  fillingState.filledWordIds = Array(fillingState.blankNodes.length).fill(null);
  for (let i = 0; i != words.length; i += 1) {
    keyboard.append(createFillingKey(words[i]));
  }
  updateFillingContinueState();
  function onKeyClick(event) {
    const button = event.target.closest(".word-key");
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
  keyboard.addEventListener("click", onKeyClick);
  answer.addEventListener("click", onKeyClick);
}

function createFillingTextNode(text) {
  const node = document.createElement("span");
  node.className = "filling-text";
  node.textContent = text === undefined ? "" : String(text);
  return node;
}

function createBlankNode() {
  const node = document.createElement("span");
  node.className = "blank";
  return node;
}

function createFillingKey(text) {
  fillingWordIdSeq += 1;
  return lessonTaskUtils.createWordKeyNode(
    fillingKeyTemplate,
    text,
    fillingWordIdSeq,
  );
}

function firstEmptyBlankIndex() {
  for (let i = 0; i != fillingState.filledWordIds.length; i += 1) {
    if (fillingState.filledWordIds[i] === null) {
      return i;
    }
  }
  return -1;
}

function findFilledBlankIndex(id) {
  for (let i = 0; i != fillingState.filledWordIds.length; i += 1) {
    if (fillingState.filledWordIds[i] === id) {
      return i;
    }
  }
  return -1;
}

function updateFillingContinueState() {
  if (fillingState.blankNodes.length === 0) {
    lessonTaskUtils.setContinueEnabled(true);
    return;
  }
  for (let i = 0; i != fillingState.filledWordIds.length; i += 1) {
    if (fillingState.filledWordIds[i] === null) {
      lessonTaskUtils.setContinueEnabled(false);
      return;
    }
  }
  lessonTaskUtils.setContinueEnabled(true);
}

function getFillingAnswerString() {
  const root = fillingState.root;
  if (!root) {
    return "[]";
  }
  const container = root.querySelector(".filling-answer");
  if (!container) {
    return "[]";
  }
  const keys = container.querySelectorAll(".word-key");
  const keyMap = new Map();
  for (let i = 0; i != keys.length; i += 1) {
    keyMap.set(keys[i].dataset.id, keys[i].textContent.trim());
  }
  const result = [];
  for (let i = 0; i != fillingState.filledWordIds.length; i += 1) {
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

function highlightFilling(isCorrect) {
  const root = fillingState.root;
  if (!root) {
    return;
  }
  const panel = root.querySelector(".panel-filling");
  if (!panel) {
    return;
  }
  panel.classList.toggle("field-wrong", !Boolean(isCorrect));
}
