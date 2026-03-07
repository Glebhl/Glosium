function initQuestion(el, question, pargraph, options, answer) {
  el.querySelector(".question-content").textContent = question;
  el.querySelector(".question-paragraph").textContent = pargraph;

  const answerField = el.querySelector(".answer-field");
  const label = answerField.querySelector(".lesson-card__label");
  answerField.dataset.locked = "false";
  const normalizedAnswer =
    Number.isInteger(answer) && answer >= 0 && answer < options.length
      ? String(options[answer])
      : answer === undefined
        ? ""
        : String(answer);

  answerField.replaceChildren();

  if (label) {
    answerField.append(label);
  }

  lessonTaskUtils.setContinueEnabled(false);

  options.forEach((optionText) => {
    answerField.append(createAnswerNode(optionText, normalizedAnswer));
  });
}

function createAnswerNode(text, correctAnswer) {
  const node = document.createElement("div");
  const normalizedText = text === undefined ? "" : String(text);

  node.className = "item unselected";
  node.textContent = normalizedText;
  node.dataset.answer = normalizedText;
  node.tabIndex = 0;
  node.setAttribute("role", "button");

  const selectAnswer = () => {
    const answerField = node.parentElement;
    if (!answerField || answerField.dataset.locked === "true") {
      return;
    }

    const items = answerField.querySelectorAll(".item");
    const isCorrect = normalizedText === correctAnswer;

    items.forEach((item) => {
      item.className = "item unselected";
    });

    node.className = "item";
    node.classList.add(isCorrect ? "correct" : "wrong");
    lessonTaskUtils.setContinueEnabled(isCorrect);

    if (isCorrect) {
      answerField.dataset.locked = "true";

      items.forEach((item) => {
        item.tabIndex = -1;
        item.setAttribute("aria-disabled", "true");
      });
    }
  };

  node.addEventListener("click", selectAnswer);
  node.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" && event.key !== " ") {
      return;
    }

    event.preventDefault();
    selectAnswer();
  });

  return node;
}
