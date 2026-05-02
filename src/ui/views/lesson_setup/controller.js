import { addCard } from "./cards.js";
import { loadSettings } from "./settings.js";
import { showHint } from "./hint.js";
import { initLessonSetupTabs } from "./tabs.js";
import { CardsGeneration } from "./cards-generation.js";

const elements = {
  btnGenerate: document.getElementById("btn-go"),
  btnStart: document.getElementById("btn-start"),
  prompt: document.getElementById("prompt"),
};

const testCard = {
  lexeme: "negotiate",
  unit: "negotiate",
  part_of_speech: "verb",
  level: "B2",
  transcription: "/nəˈɡəʊʃieɪt/",
  translation: "вести переговоры",
  definition: "To discuss something in order to reach an agreement.",
  example: '"We need to negotiate the contract terms."',
}

export class Controller {
  learnerLanguage = "ru";
  lessonLanguage = "en";

  constructor() {
    this.router;
    this.cardsGeneration;
  }

  // Options are empty for initial page
  async mount(router, options = {}) {
    this.router = router;
    this.cardsGeneration = await CardsGeneration.create(this.lessonLanguage);
    initLessonSetupTabs();
    loadSettings(options.settings);
    showHint();

    addCard(testCard);
    addCard(testCard);
    addCard(testCard);
    addCard(testCard);
    addCard(testCard);
    
    elements.btnGenerate.addEventListener("click", this.generateCards.bind(this));
    elements.btnStart.addEventListener("click", () => {});
  }

  async unmount() {

  }

  generateCards() {
    // console.log("Test");
    const learnerRequest = elements.prompt.value;
    const learnerLanguage = this.learnerLanguage;
    this.cardsGeneration.generate({ learnerRequest, learnerLanguage, callback: addCard });
  }
}
