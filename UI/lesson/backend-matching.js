// Matching task interactions and completion tracking.

const itemTemplate = document.getElementById("item-template");

const matchingState = {
  pickedLeft: null,
  pickedRight: null,
  totalPairs: 0,
  solvedPairs: 0,
  madeMistake: false,
};

function initMatching(el, pairs) {
  if (!Array.isArray(pairs)) {
    throw new TypeError("pairs_must_be_array");
  }
  const grid = el.querySelector(".grid");
  const column1 = el.querySelector(".col1");
  const column2 = el.querySelector(".col2");
  column1.replaceChildren();
  column2.replaceChildren();
  matchingState.pickedLeft = null;
  matchingState.pickedRight = null;
  matchingState.totalPairs = pairs.length;
  matchingState.solvedPairs = 0;
  matchingState.madeMistake = false;
  lessonTaskUtils.setContinueEnabled(false);
  const rightItems = [];
  for (let i = 0; i != pairs.length; i += 1) {
    const pair = Array.isArray(pairs[i]) ? pairs[i] : [];
    const leftText = pair[0] === undefined ? "" : String(pair[0]);
    const rightText = pair[1] === undefined ? "" : String(pair[1]);
    column1.append(createItemNode(leftText, i, "left"));
    rightItems.push({ text: rightText, pairId: i });
  }
  lessonTaskUtils.shuffleArrayInPlace(rightItems);
  for (let i = 0; i != rightItems.length; i += 1) {
    column2.append(
      createItemNode(rightItems[i].text, rightItems[i].pairId, "right"),
    );
  }
  if (matchingState.totalPairs === 0) {
    lessonTaskUtils.setContinueEnabled(true);
  }
  grid.addEventListener("click", function (event) {
    const item = event.target.closest(".item");
    if (!item) {
      return;
    }
    handleItemClick(item);
  });
}

function handleItemClick(item) {
  if (item.classList.contains("correct")) {
    return;
  }
  const side = item.dataset.side;
  if (!side) {
    return;
  }
  if (item.classList.contains("selected")) {
    setState(item, "unselected");
    setPicked(side, null);
    return;
  }
  const currentPicked = getPicked(side);
  if (currentPicked) {
    if (currentPicked !== item) {
      setState(currentPicked, "unselected");
    }
  }
  setPicked(side, item);
  setState(item, "selected");
  if (!matchingState.pickedLeft) {
    return;
  }
  if (!matchingState.pickedRight) {
    return;
  }
  const isCorrect =
    matchingState.pickedLeft.dataset.pairId ===
    matchingState.pickedRight.dataset.pairId;
  if (isCorrect) {
    setState(matchingState.pickedLeft, "correct");
    setState(matchingState.pickedRight, "correct");
    matchingState.solvedPairs += 1;
    if (matchingState.solvedPairs === matchingState.totalPairs) {
      lessonTaskUtils.setContinueEnabled(true);
    }
  } else {
    matchingState.madeMistake = true;
    setState(matchingState.pickedLeft, "wrong");
    setState(matchingState.pickedRight, "wrong");
  }
  matchingState.pickedLeft = null;
  matchingState.pickedRight = null;
}

function createItemNode(text, pairId, side) {
  const node = itemTemplate.content.cloneNode(true);
  const item = node.querySelector(".item");
  item.textContent = String(text);
  item.dataset.pairId = String(pairId);
  item.dataset.side = side;
  item.className = "item unselected";
  return node;
}

function setState(item, state) {
  item.className = "item";
  item.classList.add(state);
}

function getPicked(side) {
  if (side === "left") {
    return matchingState.pickedLeft;
  }
  return matchingState.pickedRight;
}

function setPicked(side, item) {
  if (side === "left") {
    matchingState.pickedLeft = item;
    return;
  }
  matchingState.pickedRight = item;
}

function getMatchingResults() {
  return matchingState.madeMistake;
}
