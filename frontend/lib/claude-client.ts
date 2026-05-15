/**
 * Claude API 클라이언트 — Vertex AI / Bedrock / Direct API 자동 선택
 *
 * 환경변수 우선순위:
 * 1. CLAUDE_PROVIDER=vertex → Google Vertex AI
 * 2. CLAUDE_PROVIDER=bedrock → AWS Bedrock
 * 3. ANTHROPIC_API_KEY → Direct API
 *
 * [공식] Vertex SDK: https://github.com/anthropics/anthropic-sdk-python (vertex-sdk README)
 * [공식] Bedrock SDK: https://github.com/anthropics/anthropic-sdk-python (bedrock-sdk README)
 */

import Anthropic from "@anthropic-ai/sdk";
import { AnthropicVertex } from "@anthropic-ai/vertex-sdk";
import { AnthropicBedrock } from "@anthropic-ai/bedrock-sdk";

export type ClaudeClient = Anthropic | AnthropicVertex | AnthropicBedrock;

let _client: ClaudeClient | null = null;
let _model: string = "";

function getProvider(): "vertex" | "bedrock" | "direct" {
  const p = process.env.CLAUDE_PROVIDER?.toLowerCase();
  if (p === "vertex") return "vertex";
  if (p === "bedrock") return "bedrock";
  if (process.env.ANTHROPIC_API_KEY) return "direct";
  // fallback: Vertex if project ID exists
  if (process.env.GOOGLE_VERTEX_PROJECT_ID || process.env.ANTHROPIC_VERTEX_PROJECT_ID) return "vertex";
  if (process.env.AWS_REGION) return "bedrock";
  return "vertex"; // default
}

export function getClient(): { client: ClaudeClient; model: string } {
  if (_client) return { client: _client, model: _model };

  const provider = getProvider();

  switch (provider) {
    case "vertex": {
      const projectId = process.env.GOOGLE_VERTEX_PROJECT_ID
        || process.env.ANTHROPIC_VERTEX_PROJECT_ID
        || "";
      const region = process.env.GOOGLE_VERTEX_REGION
        || process.env.CLOUD_ML_REGION
        || "us-east5";
      _client = new AnthropicVertex({ projectId, region });
      _model = process.env.CLAUDE_MODEL || "claude-sonnet-4-20250514";
      console.log(`[Claude] Vertex AI — project=${projectId}, region=${region}, model=${_model}`);
      break;
    }
    case "bedrock": {
      const region = process.env.AWS_REGION || "us-east-1";
      _client = new AnthropicBedrock({ awsRegion: region });
      _model = process.env.CLAUDE_MODEL || "anthropic.claude-sonnet-4-20250514-v1:0";
      console.log(`[Claude] Bedrock — region=${region}, model=${_model}`);
      break;
    }
    case "direct": {
      _client = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });
      _model = process.env.CLAUDE_MODEL || "claude-sonnet-4-20250514";
      console.log(`[Claude] Direct API — model=${_model}`);
      break;
    }
  }

  return { client: _client!, model: _model };
}

export async function callClaude(prompt: string, maxTokens: number = 2048): Promise<string> {
  const { client, model } = getClient();
  const msg = await client.messages.create({
    model,
    max_tokens: maxTokens,
    messages: [{ role: "user", content: prompt }],
  });
  const block = msg.content[0];
  if (block.type === "text") return block.text;
  return "";
}

export function parseJSON<T>(text: string, fallback: T): T {
  const m = text.match(/[\[{][\s\S]*[\]}]/);
  if (m) {
    try {
      return JSON.parse(m[0]) as T;
    } catch {
      // ignore
    }
  }
  return fallback;
}
