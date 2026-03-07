function initQuestion(el, question, pargraph, answers) {
  document.getElementById("continue").disabled = false;

  el.querySelector(".question-content").textContent = question;
  el.querySelector(".question-paragraph").textContent = pargraph;

  const answer_field = el.querySelector(".answer-field");
  answers.forEach(answer => {
    answer_field.append(createAnswerNode(answer));
  });
}

function createAnswerNode(text) {
  const node = document.createElement('div');

  node.classList.add("item", "unselected");
  node.textContent = text;

  return node;
}

elem = document.getElementById("taskStage")
initQuestion(elem, "What is the sky color according to the text?", "The sky is blue.", ["blue", "green", "red"])
