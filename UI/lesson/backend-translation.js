// Translation task interactions and answer extraction.

const keyTemplate = document.getElementById("key-template");

const translationState = {
  answerWordIds: [],
  root: null,
};

let translationWordIdSeq = 0;

function initTranslation(el, sentenceValue, keyboardArray) {
  const answer = el.querySelector(".translation-answer");
  const keyboard = el.querySelector(".keyboard");
  const sentence = el.querySelector(".translation-sentence");
  translationState.answerWordIds = [];
  translationState.root = el;
  sentence.textContent =
    sentenceValue === undefined ? "" : String(sentenceValue);
  answer.replaceChildren();
  keyboard.replaceChildren();
  const words = Array.isArray(keyboardArray) ? keyboardArray : [];
  for (let i = 0; i != words.length; i += 1) {
    keyboard.append(createTranslationKey(words[i]));
  }
  lessonTaskUtils.setContinueEnabled(false);
  function onKeyClick(event) {
    const button = event.target.closest(".word-key");
    if (!button) {
      return;
    }
    const id = button.dataset.id;
    const inKeyboard = keyboard.contains(button);
    lessonTaskUtils.runFlipAnimation([keyboard, answer], function () {
      if (inKeyboard) {
        answer.append(button);
        translationState.answerWordIds.push(id);
      } else {
        keyboard.append(button);
        removeAnswerId(id);
      }
      updateTranslationContinueState();
    });
  }
  keyboard.addEventListener("click", onKeyClick);
  answer.addEventListener("click", onKeyClick);
  return highlightTranslation;
}

function createTranslationKey(text) {
  translationWordIdSeq += 1;
  return lessonTaskUtils.createWordKeyNode(
    keyTemplate,
    text,
    translationWordIdSeq,
  );
}

function removeAnswerId(id) {
  for (let i = 0; i != translationState.answerWordIds.length; i += 1) {
    if (translationState.answerWordIds[i] === id) {
      translationState.answerWordIds.splice(i, 1);
      return;
    }
  }
}

function updateTranslationContinueState() {
  lessonTaskUtils.setContinueEnabled(
    translationState.answerWordIds.length !== 0,
  );
}

function getTranslationAnswerString() {
  const root = translationState.root;
  if (!root) {
    return "";
  }
  const container = root.querySelector(".translation-answer");
  if (!container) {
    return "";
  }
  const keys = container.querySelectorAll(".word-key");
  const keyMap = new Map();
  for (let i = 0; i != keys.length; i += 1) {
    const key = keys[i];
    keyMap.set(key.dataset.id, key.textContent.trim());
  }
  const resultWords = [];
  for (let i = 0; i != translationState.answerWordIds.length; i += 1) {
    const id = translationState.answerWordIds[i];
    const word = keyMap.get(id);
    if (word) {
      resultWords.push(word);
    }
  }
  return resultWords.join("\x20");
}

function highlightTranslation(isCorrect) {
  const root = translationState.root;
  if (!root) {
    return;
  }
  const panel = root.querySelector(".panel-translation");
  if (!panel) {
    return;
  }
  panel.classList.toggle("field-wrong", !Boolean(isCorrect));
}

function highlightTraslation(isCorrect) {
  highlightTranslation(isCorrect);
}
