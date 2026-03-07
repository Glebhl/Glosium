// Explanation task renderer.

const cardTemplate = document.getElementById("article-template");

function initExplanation(el, cardsContent) {
  lessonTaskUtils.setContinueEnabled(true);
  const cards = Array.isArray(cardsContent) ? cardsContent : [];
  const fragment = document.createDocumentFragment();
  for (let i = 0; i != cards.length; i += 1) {
    const card = cards[i] ? cards[i] : Object.create(null);
    fragment.append(
      createCardNode(
        card.name ? card.name : "",
        card.content ? card.content : "",
      ),
    );
  }
  el.replaceChildren(fragment);
}

function createCardNode(name, content) {
  const node = cardTemplate.content.cloneNode(true);
  const cardName = node.querySelector(".field-label");
  const cardContent = node.querySelector(".md-content");
  cardName.textContent = name;
  cardContent.innerHTML = content;
  return node;
}
