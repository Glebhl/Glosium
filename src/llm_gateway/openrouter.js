const DEFAULT_BASE_URL = "https://openrouter.ai/api/v1";
const DEFAULT_API_KEY = getStoredApiKey();

export class OpenRouterError extends Error {
  constructor(message, details = {}) {
    super(message);
    this.name = "OpenRouterError";
    this.status = details.status;
    this.body = details.body;
  }
}

export class OpenRouterClient {
  constructor(options = {}) {
    this.apiKey = options.apiKey || DEFAULT_API_KEY;
    this.baseUrl = options.baseUrl || DEFAULT_BASE_URL;
    this.fetch = options.fetch || globalThis.fetch.bind(globalThis);
    this.defaultHeaders = options.headers || {};
    this.appTitle = options.appTitle;
    this.siteUrl = options.siteUrl;
  }

  async chat(request, options = {}) {
    const response = await this.postJson("/chat/completions", {
      ...request,
      stream: false,
    }, options);

    return this.readJson(response);
  }

  async *streamChat(request, options = {}) {
    const response = await this.postJson("/chat/completions", {
      ...request,
      stream: true,
    }, options);

    if (!response.ok) {
      await this.throwResponseError(response);
    }

    for await (const eventText of readSseEvents(response.body)) {
      const dataLines = eventText
        .split(/\r?\n/)
        .filter((line) => line.startsWith("data:"))
        .map((line) => line.slice(5).trimStart());

      if (dataLines.length === 0) {
        continue;
      }

      const data = dataLines.join("\n");

      if (data === "[DONE]") {
        return;
      }

      const chunk = JSON.parse(data);

      if (chunk.error) {
        throw new OpenRouterError(chunk.error.message || "OpenRouter stream error", {
          body: chunk,
        });
      }

      yield chunk;
    }
  }

  async listProviders(options = {}) {
    const response = await this.fetch(this.url("/providers"), {
      method: "GET",
      headers: this.headers(options.headers),
      signal: options.signal,
    });
    const body = await this.readJson(response);

    return Array.isArray(body.data) ? body.data : body;
  }

  async postJson(path, body, options = {}) {
    return this.fetch(this.url(path), {
      method: "POST",
      headers: this.headers(options.headers),
      body: JSON.stringify(body),
      signal: options.signal,
    });
  }

  async readJson(response) {
    const body = await readResponseBody(response);

    if (!response.ok) {
      throwResponseBody(response, body);
    }

    return body === "" ? null : JSON.parse(body);
  }

  async throwResponseError(response) {
    throwResponseBody(response, await readResponseBody(response));
  }

  headers(extraHeaders = {}) {
    const headers = {
      Authorization: `Bearer ${this.apiKey}`,
      "Content-Type": "application/json",
      ...this.defaultHeaders,
      ...extraHeaders,
    };

    if (this.siteUrl) {
      headers["HTTP-Referer"] = this.siteUrl;
    }

    if (this.appTitle) {
      headers["X-OpenRouter-Title"] = this.appTitle;
    }

    return headers;
  }

  url(path) {
    return `${this.baseUrl}${path}`;
  }
}

export function createOpenRouterClient(options) {
  return new OpenRouterClient(options);
}

function getStoredApiKey() {
  return globalThis.localStorage?.getItem("openrouter_api_key") || "";
}

async function readResponseBody(response) {
  return response.text();
}

function throwResponseBody(response, body) {
  let message = body || `OpenRouter request failed with status ${response.status}`;
  let parsedBody = body;

  try {
    parsedBody = JSON.parse(body);
    message = parsedBody.error?.message || parsedBody.message || message;
  } catch {
    // Keep the text body as the error message.
  }

  throw new OpenRouterError(message, {
    status: response.status,
    body: parsedBody,
  });
}

async function* readSseEvents(body) {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();

    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split(/\r?\n\r?\n/);
    buffer = events.pop() || "";

    for (const eventText of events) {
      yield eventText;
    }
  }

  buffer += decoder.decode();

  if (buffer.trim() !== "") {
    yield buffer;
  }
}
