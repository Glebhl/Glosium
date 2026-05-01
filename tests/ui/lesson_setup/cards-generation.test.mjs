import assert from "node:assert/strict";
import test from "node:test";

globalThis.localStorage = {
  getItem() {
    return "or-test-key";
  },
};

const { CardsGeneration } = await import("../../../src/ui/views/lesson_setup/cards-generation.js");

test("CardsGeneration.create loads the vocabulary prompt asynchronously", async () => {
  const cardsGeneration = await CardsGeneration.create("en", {
    fetch: async (url) => {
      assert.match(String(url), /src\/prompts\/en\/vocabulary_card_generation\.txt$/);
      return new Response("system prompt");
    },
    client: { streamChat() {} },
  });

  assert.equal(cardsGeneration.prompt, "system prompt");
});

test("generate streams parsed cards with the loaded prompt", async () => {
  const streamedRequests = [];
  const client = {
    async *streamChat(request) {
      streamedRequests.push(request);
      yield { choices: [{ delta: { content: '{"word":"hello"}' } }] };
      yield { choices: [{ delta: { content: "\n" } }] };
    },
  };

  const cardsGeneration = await CardsGeneration.create("en", {
    fetch: async () => new Response("system prompt"),
    client,
    model: "test-model",
  });
  const cards = [];

  await cardsGeneration.generate({
    learnerRequest: "travel words",
    learnerLanguage: "ru",
    callback(card) {
      cards.push(card);
    },
  });

  assert.deepEqual(cards, [{ word: "hello" }]);
  assert.equal(streamedRequests[0].model, "test-model");
  assert.deepEqual(streamedRequests[0].messages, [
    { role: "system", content: "system prompt" },
    { role: "user", content: "LEARNER_REQUEST: travel words\nLEARNER_LANGUAGE: ru" },
  ]);
});
