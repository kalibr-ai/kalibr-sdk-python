# @kalibr/sdk

Zero-dependency TypeScript SDK for Kalibr LLM observability. Track costs, latency, and token usage across OpenAI, Anthropic, Google, and Cohere models.

## Features

- **Zero dependencies** - Uses native `fetch`, works in Node.js 18+, Edge runtimes, and browsers
- **Schema compatible** - Matches Kalibr Python SDK schema exactly
- **Fluent API** - SpanBuilder with auto-timing and method chaining
- **Cost calculation** - Built-in pricing tables for all major LLM providers
- **NDJSON batching** - Efficient batch sending of multiple spans
- **TypeScript-first** - Full type definitions with strict mode

## Installation

```bash
npm install @kalibr/sdk
# or
yarn add @kalibr/sdk
# or
pnpm add @kalibr/sdk
```

## Quick Start

### 1. Initialize the SDK

```typescript
import { Kalibr } from '@kalibr/sdk';

// Initialize once at app startup
Kalibr.init({
  apiKey: process.env.KALIBR_API_KEY!,
  tenantId: process.env.KALIBR_TENANT_ID!,
  environment: 'prod',    // optional: 'prod' | 'staging' | 'dev'
  service: 'my-app',      // optional: service name
  debug: true,            // optional: enable console logging
});
```

### 2. Track LLM Calls with SpanBuilder (Recommended)

```typescript
import { SpanBuilder } from '@kalibr/sdk';
import OpenAI from 'openai';

const openai = new OpenAI();

async function chat(prompt: string) {
  // Start timing
  const span = new SpanBuilder()
    .setProvider('openai')
    .setModel('gpt-4o')
    .setOperation('chat_completion')
    .setEndpoint('chat.completions.create')
    .start();

  try {
    // Make the LLM call
    const response = await openai.chat.completions.create({
      model: 'gpt-4o',
      messages: [{ role: 'user', content: prompt }],
    });

    // Finish and send span (auto-calculates duration and cost)
    await span.finish({
      inputTokens: response.usage?.prompt_tokens ?? 0,
      outputTokens: response.usage?.completion_tokens ?? 0,
    });

    return response.choices[0]?.message?.content;
  } catch (error) {
    // Record error and send span
    await span.error(error as Error, {
      inputTokens: 0,
      outputTokens: 0,
    });
    throw error;
  }
}
```

### 3. Track Nested Spans (Multi-step Workflows)

```typescript
import { SpanBuilder, generateId } from '@kalibr/sdk';

async function processDocument(document: string) {
  // Create a shared trace ID for the workflow
  const traceId = generateId();

  // Step 1: Summarize
  const summarySpan = new SpanBuilder()
    .setTraceId(traceId)
    .setProvider('openai')
    .setModel('gpt-4o')
    .setOperation('summarize')
    .setWorkflowId('document-processor')
    .start();

  const summary = await callLLM('Summarize this: ' + document);

  await summarySpan.finish({
    inputTokens: summary.usage.prompt_tokens,
    outputTokens: summary.usage.completion_tokens,
  });

  // Step 2: Extract entities (child span)
  const extractSpan = new SpanBuilder()
    .setTraceId(traceId)
    .setParentSpanId(summarySpan.getSpanId())
    .setProvider('anthropic')
    .setModel('claude-3-sonnet-20240229')
    .setOperation('extract_entities')
    .setWorkflowId('document-processor')
    .start();

  const entities = await callClaude('Extract entities: ' + summary.text);

  await extractSpan.finish({
    inputTokens: entities.usage.input_tokens,
    outputTokens: entities.usage.output_tokens,
  });

  return { summary: summary.text, entities: entities.text };
}
```

## API Reference

### Kalibr (Client)

The main client class with singleton support.

```typescript
// Singleton pattern
Kalibr.init(config);
await Kalibr.sendSpan(span);
await Kalibr.sendSpans([span1, span2]);

// Direct instantiation
const client = new Kalibr(config);
await client.sendSpan(span);
```

#### Config Options

| Option | Type | Required | Description |
|--------|------|----------|-------------|
| `apiKey` | `string` | Yes | API key for X-API-Key header |
| `tenantId` | `string` | Yes | Your tenant identifier |
| `endpoint` | `string` | No | API URL (default: `https://api.kalibr.systems/api/ingest`) |
| `environment` | `'prod' \| 'staging' \| 'dev'` | No | Deployment environment |
| `service` | `string` | No | Service name |
| `debug` | `boolean` | No | Enable debug logging |
| `fetch` | `typeof fetch` | No | Custom fetch implementation |

### SpanBuilder

Fluent builder for creating spans with automatic timing.

```typescript
const span = new SpanBuilder()
  // Required
  .setProvider('openai')           // 'openai' | 'anthropic' | 'google' | 'cohere' | 'custom'
  .setModel('gpt-4o')              // Model ID
  .setOperation('chat_completion') // Operation type

  // Optional identity
  .setTraceId(traceId)             // Link spans together
  .setParentSpanId(parentId)       // Create hierarchy
  .setTenantId(tenantId)           // Override client default

  // Optional context
  .setWorkflowId('my-workflow')
  .setSandboxId('sandbox-123')
  .setRuntimeEnv('vercel_vm')
  .setEndpoint('api/chat')
  .setEnvironment('prod')
  .setService('chat-service')

  // Optional user context
  .setUserId('user-123')
  .setRequestId('req-456')

  // Optional metadata
  .setMetadata({ custom: 'data' })
  .setDataClass('economic')

  // Start timing
  .start();
```

#### StartedSpan Methods

```typescript
// Get IDs
span.getTraceId();  // Returns trace ID
span.getSpanId();   // Returns span ID

// Finish successfully
await span.finish({
  inputTokens: 100,
  outputTokens: 50,
  status: 'success',      // optional, default: 'success'
  costUsd: 0.001,         // optional, auto-calculated if omitted
  metadata: { key: 'val' }, // optional, merged with builder metadata
  autoSend: true,         // optional, default: true
});

// Finish with error
await span.error(error, { inputTokens: 0, outputTokens: 0 });

// Finish with timeout
await span.timeout({ inputTokens: 100, outputTokens: 0 });
```

### Utility Functions

```typescript
import { generateId, timestamp, calculateCost, createSpan, withSpan } from '@kalibr/sdk';

// Generate 32-char hex ID
const id = generateId(); // e.g., "a1b2c3d4e5f6789012345678abcdef01"

// Get ISO 8601 timestamp
const ts = timestamp(); // e.g., "2024-01-15T10:30:00.000Z"

// Calculate cost from tokens
const cost = calculateCost('openai', 'gpt-4o', 1000, 500); // $0.0075

// Create a span manually
const span = createSpan({
  tenantId: 'my-tenant',
  provider: 'anthropic',
  modelId: 'claude-3-opus-20240229',
  operation: 'generate',
  durationMs: 1500,
  inputTokens: 500,
  outputTokens: 200,
});

// Wrap a function with automatic span tracking
const result = await withSpan(
  { provider: 'openai', modelId: 'gpt-4o', operation: 'chat' },
  async () => {
    const response = await llmCall();
    return {
      result: response.text,
      inputTokens: response.usage.prompt_tokens,
      outputTokens: response.usage.completion_tokens,
    };
  }
);
```

### KalibrSpan Type

Full type definition matching the Python SDK's TraceEvent:

```typescript
interface KalibrSpan {
  // Required fields
  schema_version: '1.0';
  trace_id: string;       // min 16 chars
  span_id: string;        // min 16 chars
  tenant_id: string;
  provider: 'openai' | 'anthropic' | 'google' | 'cohere' | 'custom';
  model_id: string;
  operation: string;
  duration_ms: number;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  status: 'success' | 'error' | 'timeout';
  timestamp: string;      // ISO 8601

  // Optional fields
  parent_span_id?: string | null;
  workflow_id?: string | null;
  sandbox_id?: string | null;
  runtime_env?: string | null;
  model_name?: string | null;
  endpoint?: string | null;
  latency_ms?: number | null;
  total_tokens?: number | null;
  total_cost_usd?: number | null;
  unit_price_usd?: number | null;
  error_type?: string | null;
  error_message?: string | null;
  stack_trace?: string | null;
  ts_start?: string | null;
  ts_end?: string | null;
  environment?: 'prod' | 'staging' | 'dev' | null;
  service?: string | null;
  user_id?: string | null;
  request_id?: string | null;
  metadata?: Record<string, unknown> | null;
  data_class?: 'economic' | 'performance' | 'diagnostic' | null;
  vendor?: string | null;  // legacy, same as provider
}
```

## Next.js Integration

### App Router (app/layout.tsx)

```typescript
// lib/kalibr.ts
import { Kalibr } from '@kalibr/sdk';

// Initialize once
if (!Kalibr.isInitialized()) {
  Kalibr.init({
    apiKey: process.env.KALIBR_API_KEY!,
    tenantId: process.env.KALIBR_TENANT_ID!,
    environment: process.env.NODE_ENV === 'production' ? 'prod' : 'dev',
    service: 'my-nextjs-app',
  });
}

export { Kalibr, SpanBuilder } from '@kalibr/sdk';
```

### API Route Handler

```typescript
// app/api/chat/route.ts
import { NextResponse } from 'next/server';
import { SpanBuilder } from '@/lib/kalibr';
import OpenAI from 'openai';

const openai = new OpenAI();

export async function POST(request: Request) {
  const { messages } = await request.json();

  const span = new SpanBuilder()
    .setProvider('openai')
    .setModel('gpt-4o')
    .setOperation('chat_completion')
    .setEndpoint('/api/chat')
    .setRequestId(request.headers.get('x-request-id') ?? undefined)
    .start();

  try {
    const response = await openai.chat.completions.create({
      model: 'gpt-4o',
      messages,
    });

    await span.finish({
      inputTokens: response.usage?.prompt_tokens ?? 0,
      outputTokens: response.usage?.completion_tokens ?? 0,
    });

    return NextResponse.json({
      message: response.choices[0]?.message?.content,
    });
  } catch (error) {
    await span.error(error as Error, { inputTokens: 0, outputTokens: 0 });
    return NextResponse.json({ error: 'Failed' }, { status: 500 });
  }
}
```

## Pricing Tables

Built-in pricing for automatic cost calculation (per 1M tokens):

### OpenAI
| Model | Input | Output |
|-------|-------|--------|
| gpt-4 | $30.00 | $60.00 |
| gpt-4-turbo | $10.00 | $30.00 |
| gpt-4o | $2.50 | $10.00 |
| gpt-4o-mini | $0.15 | $0.60 |
| gpt-3.5-turbo | $0.50 | $1.50 |

### Anthropic
| Model | Input | Output |
|-------|-------|--------|
| claude-3-opus | $15.00 | $75.00 |
| claude-3-sonnet | $3.00 | $15.00 |
| claude-3.5-sonnet | $3.00 | $15.00 |
| claude-3-haiku | $0.25 | $1.25 |

### Google
| Model | Input | Output |
|-------|-------|--------|
| gemini-pro | $1.25 | $5.00 |
| gemini-1.5-pro | $1.25 | $5.00 |
| gemini-1.5-flash | $0.075 | $0.30 |

### Cohere
| Model | Input | Output |
|-------|-------|--------|
| command | $1.00 | $2.00 |
| command-r | $0.50 | $1.50 |
| command-r-plus | $3.00 | $15.00 |

## Environment Variables

```bash
KALIBR_API_KEY=your-api-key
KALIBR_TENANT_ID=your-tenant-id
```

## Requirements

- Node.js 18+ (for native fetch)
- TypeScript 5.0+ (optional, for type checking)

## License

MIT
