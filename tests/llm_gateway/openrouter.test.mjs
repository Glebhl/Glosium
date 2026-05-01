import assert from "node:assert/strict";
import test from "node:test";

import {
  OpenRouterClient,
  OpenRouterError,
} from "../../src/llm_gateway/openrouter.js";

function createJsonResponse(body, init = {}) {
  return new Response(JSON.stringify(body), {
    status: init.status || 200,
    headers: {
      "content-type": "application/json",
      ...(init.headers || {}),
    },
  });
}

function createStreamResponse(events) {
  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    start(controller) {
      for (const event of events) {
        controller.enqueue(encoder.encode(event));
      }
      controller.close();
    },
  });

  return new Response(stream, {
    status: 200,
    headers: { "content-type": "text/event-stream" },
  });
}

test("chat sends an OpenRouter chat completion request", async () => {
  let capturedRequest;
  const fetchFn = async (url, options) => {
    capturedRequest = { url, options };
    return createJsonResponse({
      choices: [{ message: { role: "assistant", content: "Hello" } }],
    });
  };

  const client = new OpenRouterClient({
    apiKey: "or-key",
    appTitle: "Glosium",
    siteUrl: "https://glosium.local",
    fetch: fetchFn,
  });

  const response = await client.chat({
    model: "openai/gpt-5.2",
    messages: [{ role: "user", content: "Hi" }],
    temperature: 0.2,
  });

  assert.equal(capturedRequest.url, "https://openrouter.ai/api/v1/chat/completions");
  assert.equal(capturedRequest.options.method, "POST");
  assert.equal(capturedRequest.options.headers.Authorization, "Bearer or-key");
  assert.equal(capturedRequest.options.headers["Content-Type"], "application/json");
  assert.equal(capturedRequest.options.headers["X-OpenRouter-Title"], "Glosium");
  assert.equal(capturedRequest.options.headers["HTTP-Referer"], "https://glosium.local");
  assert.deepEqual(JSON.parse(capturedRequest.options.body), {
    model: "openai/gpt-5.2",
    messages: [{ role: "user", content: "Hi" }],
    temperature: 0.2,
    stream: false,
  });
  assert.equal(response.choices[0].message.content, "Hello");
});

test("chat uses the global fetch receiver when no fetch is injected", async () => {
  const originalFetch = globalThis.fetch;

  globalThis.fetch = async function () {
    assert.equal(this, globalThis);
    return createJsonResponse({ choices: [] });
  };

  try {
    const client = new OpenRouterClient({ apiKey: "or-key" });

    await client.chat({
      model: "openai/gpt-5.2",
      messages: [{ role: "user", content: "Hi" }],
    });
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("chat passes provider preferences through for OpenRouter BYOK routing", async () => {
  let requestBody;
  const fetchFn = async (url, options) => {
    requestBody = JSON.parse(options.body);
    return createJsonResponse({ choices: [] });
  };

  const client = new OpenRouterClient({ apiKey: "or-key", fetch: fetchFn });

  await client.chat({
    model: "anthropic/claude-sonnet-4.5",
    messages: [{ role: "user", content: "Hi" }],
    provider: {
      order: ["anthropic", "google-vertex"],
      only: ["anthropic", "google-vertex"],
      allow_fallbacks: false,
    },
  });

  assert.deepEqual(requestBody.provider, {
    order: ["anthropic", "google-vertex"],
    only: ["anthropic", "google-vertex"],
    allow_fallbacks: false,
  });
});

test("streamChat parses OpenRouter SSE chunks and ignores comments", async () => {
  const fetchFn = async () =>
    createStreamResponse([
      ": OPENROUTER PROCESSING\n\n",
      'data: {"choices":[{"delta":{"content":"Hel"}}]}\n\n',
      'data: {"choices":[{"delta":{"content":"lo"}}]}\n\n',
      "data: [DONE]\n\n",
    ]);

  const client = new OpenRouterClient({ apiKey: "or-key", fetch: fetchFn });
  const chunks = [];

  for await (const chunk of client.streamChat({
    model: "openai/gpt-5.2",
    messages: [{ role: "user", content: "Hi" }],
  })) {
    chunks.push(chunk.choices[0].delta.content);
  }

  assert.deepEqual(chunks, ["Hel", "lo"]);
});

test("listProviders reads OpenRouter provider metadata without hardcoded slugs", async () => {
  let capturedUrl;
  const fetchFn = async (url) => {
    capturedUrl = url;
    return createJsonResponse({
      data: [
        { name: "OpenAI", slug: "openai" },
        { name: "Google Vertex", slug: "google-vertex" },
      ],
    });
  };

  const client = new OpenRouterClient({ apiKey: "or-key", fetch: fetchFn });
  const providers = await client.listProviders();

  assert.equal(capturedUrl, "https://openrouter.ai/api/v1/providers");
  assert.deepEqual(
    providers.map((provider) => provider.slug),
    ["openai", "google-vertex"],
  );
});

test("OpenRouter errors include status and provider message", async () => {
  const fetchFn = async () =>
    createJsonResponse(
      { error: { message: "No allowed providers are available" } },
      { status: 503 },
    );

  const client = new OpenRouterClient({ apiKey: "or-key", fetch: fetchFn });

  await assert.rejects(
    () =>
      client.chat({
        model: "openai/gpt-5.2",
        messages: [{ role: "user", content: "Hi" }],
      }),
    (error) => {
      assert.equal(error instanceof OpenRouterError, true);
      assert.equal(error.status, 503);
      assert.equal(error.message, "No allowed providers are available");
      return true;
    },
  );
});

test("llm_gateway index re-exports the OpenRouter wrapper", async () => {
  const gateway = await import("../../src/llm_gateway/index.js");

  assert.equal(gateway.OpenRouterClient, OpenRouterClient);
  assert.equal(typeof gateway.createOpenRouterClient, "function");
});
