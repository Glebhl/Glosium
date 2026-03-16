// ID counter
let nextId = 0;

const tpl = document.getElementById('card-template');
const list = document.getElementById('cards');

function renumberCards() {
  const cards = list.querySelectorAll('.card');

  cards.forEach((card, i) => {
    card.dataset.id = String(i);
  });

  nextId = cards.length;
  document.getElementById('deck-amount').textContent = 'Deck: ' + nextId + ' cards'
}

function addCard(word, unit, part, level, transcription, translation, defenition, example) {
  const node = tpl.content.cloneNode(true);
  const id = String(nextId++);

  node.querySelector('.card').dataset.id = id;
  node.querySelector('.word').textContent = word;
  node.querySelector('.tag--purple').textContent = unit;
  node.querySelector('.tag--green').textContent = part;
  node.querySelector('.tag--amber').textContent = level;
  node.querySelector('.transcription').textContent = transcription;
  node.querySelector('.translation').textContent = translation;
  node.querySelector('.defenition').textContent = defenition;
  node.querySelector('.example').textContent = example;
  
  list.append(node);
  renumberCards();

  return id;
}

function removeCard(id) {
  const el = list.querySelector(`item[data-id="${id}"]`);
  el.parentNode.removeChild(el);
  renumberCards();
}

list.addEventListener('click', (e) => {
  const btn = e.target.closest('.remove-btn');
  if (!btn) return;

  const item = btn.closest('.card');
  item.remove();
  renumberCards();

  backend.emitEvent('card-closed', { id: item.dataset.id });
});

function setHint(hint) {
  document.getElementById('hint').innerHTML = hint;
}

// UI actions (JS -> Python)
document.getElementById('btn-go').addEventListener('click', () => {
  backend.emitEvent('btn-click', { id: "go" });
});

document.getElementById("btn-start").addEventListener('click', () => {
  backend.emitEvent('btn-click', { id: 'start' });
});
