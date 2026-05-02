import { createOpenRouterClient } from "../../../llm_gateway/index.js";

export class CardsGeneration {
  constructor(lessonLanguage, options = {}) {
    this.lessonLanguage = lessonLanguage;
    this.options = options;
    this.model = options.model || "google/gemini-3.1-flash-lite-preview";
    this.fetch = options.fetch || globalThis.fetch.bind(globalThis);
    this.client = options.client || createOpenRouterClient(options.openRouter || options);
    this.prompt = "";
  }

  static async create(lessonLanguage, options = {}) {
    const cardsGeneration = new CardsGeneration(lessonLanguage, options);
    await cardsGeneration.loadPrompt();
    return cardsGeneration;
  }

  async loadPrompt() {
    const promptPath = new URL(
      `../../../prompts/${this.lessonLanguage}/vocabulary_card_generation.txt`,
      import.meta.url,
    );
    const response = await this.fetch(promptPath);

    if (!response.ok) {
      throw new Error(`Could not load prompt from ${promptPath}. Status: ${response.status}`);
    }

    this.prompt = await response.text();
  }

  async generate({ learnerRequest, learnerLanguage, callback }) {
    console.info(`Generating cards. learnerRequest=${learnerRequest} learnerLanguage=${learnerLanguage}`);
    const userPrompt = this.buildUserPrompt({ learnerRequest, learnerLanguage });
    await this.streamCards({ userPrompt, callback });
  }
  
  async streamCards({ userPrompt, callback }) {
    let buffer = "";
    
    for await (const chunk of this.client.streamChat({
      model: this.model,
      messages: [
        { role: "system", content: this.prompt },
        { role: "user", content: userPrompt },
      ],
    })) {
      const token = chunk.choices?.[0]?.delta?.content || "";
      buffer += token;
      const lines = buffer.split("\n");
      buffer = lines.pop();
      lines.forEach((line) => {callback(JSON.parse(line.trim()))});
    }

    if (buffer) {
      callback(JSON.parse(buffer.trim()));
    }
  }
  
  buildUserPrompt({ learnerRequest, learnerLanguage }) {
    const lines = []
    lines.push(`LEARNER_REQUEST: ${learnerRequest}`);
    lines.push(`LEARNER_LANGUAGE: ${learnerLanguage}`);
    return lines.join("\n");
  }
}
