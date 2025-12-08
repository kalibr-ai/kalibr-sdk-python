/**
 * Tests for Kalibr TypeScript SDK
 */

import { describe, it } from 'node:test';
import assert from 'node:assert';
import {
  generateId,
  timestamp,
  calculateCost,
  createSpan,
  Kalibr,
  SpanBuilder,
} from './kalibr';

// ============================================================================
// Utility Function Tests
// ============================================================================

describe('generateId', () => {
  it('should generate a 32-character hex string', () => {
    const id = generateId();
    assert.strictEqual(id.length, 32);
    assert.match(id, /^[0-9a-f]{32}$/);
  });

  it('should generate unique IDs', () => {
    const id1 = generateId();
    const id2 = generateId();
    assert.notStrictEqual(id1, id2);
  });
});

describe('timestamp', () => {
  it('should return an ISO 8601 timestamp', () => {
    const ts = timestamp();
    assert.match(ts, /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/);
  });

  it('should be a valid date', () => {
    const ts = timestamp();
    const date = new Date(ts);
    assert.ok(!isNaN(date.getTime()));
  });
});

// ============================================================================
// Cost Calculation Tests
// ============================================================================

describe('calculateCost', () => {
  it('should calculate OpenAI GPT-4o costs correctly', () => {
    const cost = calculateCost('openai', 'gpt-4o', 1_000_000, 1_000_000);
    // input: 1M tokens * $2.50/1M = $2.50
    // output: 1M tokens * $10.00/1M = $10.00
    // total: $12.50
    assert.strictEqual(cost, 12.5);
  });

  it('should calculate Anthropic Claude-3-Opus costs correctly', () => {
    const cost = calculateCost('anthropic', 'claude-3-opus-20240229', 500_000, 200_000);
    // input: 0.5M * $15.00 = $7.50
    // output: 0.2M * $75.00 = $15.00
    // total: $22.50
    assert.strictEqual(cost, 22.5);
  });

  it('should calculate Google Gemini costs correctly', () => {
    const cost = calculateCost('google', 'gemini-1.5-flash', 1_000_000, 1_000_000);
    // input: 1M * $0.075 = $0.075
    // output: 1M * $0.30 = $0.30
    // total: $0.375
    assert.strictEqual(cost, 0.375);
  });

  it('should handle small token counts', () => {
    const cost = calculateCost('openai', 'gpt-4o', 100, 50);
    // input: 0.0001M * $2.50 = $0.00025
    // output: 0.00005M * $10.00 = $0.0005
    // total: $0.00075
    assert.strictEqual(cost, 0.00075);
  });

  it('should use default pricing for unknown models', () => {
    const cost = calculateCost('custom', 'unknown-model', 1_000_000, 1_000_000);
    // Should use default pricing: $30/$60 per 1M tokens
    assert.strictEqual(cost, 90.0);
  });

  it('should normalize model names correctly', () => {
    const cost1 = calculateCost('openai', 'gpt-4o-2024-05-13', 1_000_000, 1_000_000);
    const cost2 = calculateCost('openai', 'gpt-4o', 1_000_000, 1_000_000);
    assert.strictEqual(cost1, cost2);
  });
});

// ============================================================================
// createSpan Tests
// ============================================================================

describe('createSpan', () => {
  it('should create a valid span with required fields', () => {
    const span = createSpan({
      tenantId: 'test-tenant',
      provider: 'openai',
      modelId: 'gpt-4o',
      operation: 'chat_completion',
      durationMs: 1500,
      inputTokens: 100,
      outputTokens: 50,
    });

    assert.strictEqual(span.schema_version, '1.0');
    assert.strictEqual(span.tenant_id, 'test-tenant');
    assert.strictEqual(span.provider, 'openai');
    assert.strictEqual(span.model_id, 'gpt-4o');
    assert.strictEqual(span.operation, 'chat_completion');
    assert.strictEqual(span.duration_ms, 1500);
    assert.strictEqual(span.input_tokens, 100);
    assert.strictEqual(span.output_tokens, 50);
    assert.strictEqual(span.total_tokens, 150);
    assert.strictEqual(span.status, 'success');
    assert.strictEqual(span.trace_id.length, 32);
    assert.strictEqual(span.span_id.length, 32);
  });

  it('should auto-calculate cost if not provided', () => {
    const span = createSpan({
      tenantId: 'test-tenant',
      provider: 'openai',
      modelId: 'gpt-4o',
      operation: 'chat',
      durationMs: 1000,
      inputTokens: 1_000_000,
      outputTokens: 1_000_000,
    });

    assert.strictEqual(span.cost_usd, 12.5);
    assert.strictEqual(span.total_cost_usd, 12.5);
  });

  it('should use provided cost if specified', () => {
    const span = createSpan({
      tenantId: 'test-tenant',
      provider: 'openai',
      modelId: 'gpt-4o',
      operation: 'chat',
      durationMs: 1000,
      inputTokens: 100,
      outputTokens: 50,
      costUsd: 0.123,
    });

    assert.strictEqual(span.cost_usd, 0.123);
  });

  it('should handle optional fields', () => {
    const span = createSpan({
      tenantId: 'test-tenant',
      provider: 'anthropic',
      modelId: 'claude-3-opus-20240229',
      operation: 'generate',
      durationMs: 2000,
      inputTokens: 500,
      outputTokens: 200,
      traceId: 'custom-trace-id',
      parentSpanId: 'parent-span-id',
      workflowId: 'my-workflow',
      environment: 'prod',
      service: 'my-service',
      metadata: { key: 'value' },
    });

    assert.strictEqual(span.trace_id, 'custom-trace-id');
    assert.strictEqual(span.parent_span_id, 'parent-span-id');
    assert.strictEqual(span.workflow_id, 'my-workflow');
    assert.strictEqual(span.environment, 'prod');
    assert.strictEqual(span.service, 'my-service');
    assert.deepStrictEqual(span.metadata, { key: 'value' });
  });

  it('should set error fields when status is error', () => {
    const span = createSpan({
      tenantId: 'test-tenant',
      provider: 'openai',
      modelId: 'gpt-4o',
      operation: 'chat',
      durationMs: 500,
      inputTokens: 0,
      outputTokens: 0,
      status: 'error',
      errorType: 'TimeoutError',
      errorMessage: 'Request timed out',
    });

    assert.strictEqual(span.status, 'error');
    assert.strictEqual(span.error_type, 'TimeoutError');
    assert.strictEqual(span.error_message, 'Request timed out');
  });
});

// ============================================================================
// Kalibr Client Tests
// ============================================================================

describe('Kalibr', () => {
  it('should initialize with required config', () => {
    const client = new Kalibr({
      apiKey: 'test-key',
      tenantId: 'test-tenant',
    });

    assert.ok(client);
  });

  it('should initialize singleton instance', () => {
    Kalibr.init({
      apiKey: 'test-key',
      tenantId: 'test-tenant',
    });

    assert.ok(Kalibr.isInitialized());
  });

  it('should send a single span with mocked fetch', async () => {
    let fetchUrl: string | undefined;
    let fetchOptions: RequestInit | undefined;

    const mockFetch: typeof fetch = async (input, init) => {
      fetchUrl = input.toString();
      fetchOptions = init;
      return {
        ok: true,
        status: 200,
        statusText: 'OK',
        text: async () => 'OK',
      } as Response;
    };

    const client = new Kalibr({
      apiKey: 'test-key',
      tenantId: 'test-tenant',
      fetch: mockFetch,
    });

    const span = createSpan({
      tenantId: 'test-tenant',
      provider: 'openai',
      modelId: 'gpt-4o',
      operation: 'test',
      durationMs: 100,
      inputTokens: 10,
      outputTokens: 5,
    });

    await client.sendSpan(span);

    assert.strictEqual(fetchUrl, 'https://api.kalibr.systems/api/ingest');
    assert.ok(fetchOptions);
    assert.strictEqual(fetchOptions.method, 'POST');

    const headers = fetchOptions.headers as Record<string, string>;
    assert.strictEqual(headers['X-API-Key'], 'test-key');
    assert.strictEqual(headers['Content-Type'], 'application/x-ndjson');
  });

  it('should send multiple spans as batch with mocked fetch', async () => {
    let fetchOptions: RequestInit | undefined;

    const mockFetch: typeof fetch = async (_input, init) => {
      fetchOptions = init;
      return {
        ok: true,
        status: 200,
        statusText: 'OK',
        text: async () => 'OK',
      } as Response;
    };

    const client = new Kalibr({
      apiKey: 'test-key',
      tenantId: 'test-tenant',
      fetch: mockFetch,
    });

    const spans = [
      createSpan({
        tenantId: 'test-tenant',
        provider: 'openai',
        modelId: 'gpt-4o',
        operation: 'test1',
        durationMs: 100,
        inputTokens: 10,
        outputTokens: 5,
      }),
      createSpan({
        tenantId: 'test-tenant',
        provider: 'openai',
        modelId: 'gpt-4o',
        operation: 'test2',
        durationMs: 200,
        inputTokens: 20,
        outputTokens: 10,
      }),
    ];

    await client.sendSpans(spans);

    assert.ok(fetchOptions);
    const body = fetchOptions.body as string;

    // NDJSON should have 2 lines
    const lines = body.trim().split('\n');
    assert.strictEqual(lines.length, 2);
    const line1 = lines[0];
    const line2 = lines[1];
    assert.ok(line1 && JSON.parse(line1));
    assert.ok(line2 && JSON.parse(line2));
  });
});

// ============================================================================
// SpanBuilder Tests
// ============================================================================

describe('SpanBuilder', () => {
  it('should build a span with fluent API', () => {
    const builder = new SpanBuilder()
      .setProvider('openai')
      .setModel('gpt-4o')
      .setOperation('chat_completion')
      .setEnvironment('prod')
      .setService('test-service');

    const span = builder.start();
    assert.ok(span);
  });

  it('should generate trace and span IDs automatically', () => {
    const span = new SpanBuilder()
      .setProvider('openai')
      .setModel('gpt-4o')
      .setOperation('test')
      .start();

    const traceId = span.getTraceId();
    const spanId = span.getSpanId();

    assert.strictEqual(traceId.length, 32);
    assert.strictEqual(spanId.length, 32);
    assert.notStrictEqual(traceId, spanId);
  });

  it('should allow custom trace and span IDs', () => {
    const customTraceId = 'custom-trace-id-123456789012';
    const span = new SpanBuilder()
      .setProvider('openai')
      .setModel('gpt-4o')
      .setOperation('test')
      .setTraceId(customTraceId)
      .start();

    assert.strictEqual(span.getTraceId(), customTraceId);
  });

  it('should finish with success status', async () => {
    const mockFetch: typeof fetch = async () =>
      ({
        ok: true,
        status: 200,
        statusText: 'OK',
        text: async () => 'OK',
      }) as Response;

    Kalibr.init({
      apiKey: 'test-key',
      tenantId: 'test-tenant',
      fetch: mockFetch,
    });

    const span = new SpanBuilder()
      .setProvider('openai')
      .setModel('gpt-4o')
      .setOperation('test')
      .start();

    // Simulate some delay
    await new Promise((resolve) => setTimeout(resolve, 10));

    const result = await span.finish({
      inputTokens: 100,
      outputTokens: 50,
    });

    assert.strictEqual(result.status, 'success');
    assert.strictEqual(result.input_tokens, 100);
    assert.strictEqual(result.output_tokens, 50);
    assert.ok(result.duration_ms > 0);
    assert.ok(result.cost_usd > 0);
  });

  it('should finish with error status', async () => {
    const mockFetch: typeof fetch = async () =>
      ({
        ok: true,
        status: 200,
        statusText: 'OK',
        text: async () => 'OK',
      }) as Response;

    Kalibr.init({
      apiKey: 'test-key',
      tenantId: 'test-tenant',
      fetch: mockFetch,
    });

    const span = new SpanBuilder()
      .setProvider('openai')
      .setModel('gpt-4o')
      .setOperation('test')
      .start();

    const error = new Error('Test error');
    const result = await span.error(error, {
      inputTokens: 0,
      outputTokens: 0,
    });

    assert.strictEqual(result.status, 'error');
    assert.strictEqual(result.error_type, 'Error');
    assert.strictEqual(result.error_message, 'Test error');
    assert.ok(result.stack_trace);
  });

  it('should finish with timeout status', async () => {
    const mockFetch: typeof fetch = async () =>
      ({
        ok: true,
        status: 200,
        statusText: 'OK',
        text: async () => 'OK',
      }) as Response;

    Kalibr.init({
      apiKey: 'test-key',
      tenantId: 'test-tenant',
      fetch: mockFetch,
    });

    const span = new SpanBuilder()
      .setProvider('openai')
      .setModel('gpt-4o')
      .setOperation('test')
      .start();

    const result = await span.timeout({
      inputTokens: 100,
      outputTokens: 0,
    });

    assert.strictEqual(result.status, 'timeout');
  });

  it('should merge metadata from builder and finish', async () => {
    const mockFetch: typeof fetch = async () =>
      ({
        ok: true,
        status: 200,
        statusText: 'OK',
        text: async () => 'OK',
      }) as Response;

    Kalibr.init({
      apiKey: 'test-key',
      tenantId: 'test-tenant',
      fetch: mockFetch,
    });

    const span = new SpanBuilder()
      .setProvider('openai')
      .setModel('gpt-4o')
      .setOperation('test')
      .setMetadata({ builderKey: 'builderValue' })
      .start();

    const result = await span.finish({
      inputTokens: 100,
      outputTokens: 50,
      metadata: { finishKey: 'finishValue' },
    });

    assert.deepStrictEqual(result.metadata, {
      builderKey: 'builderValue',
      finishKey: 'finishValue',
    });
  });

  it('should support parent-child span relationships', async () => {
    const mockFetch: typeof fetch = async () =>
      ({
        ok: true,
        status: 200,
        statusText: 'OK',
        text: async () => 'OK',
      }) as Response;

    Kalibr.init({
      apiKey: 'test-key',
      tenantId: 'test-tenant',
      fetch: mockFetch,
    });

    const traceId = generateId();

    const parentSpan = new SpanBuilder()
      .setProvider('openai')
      .setModel('gpt-4o')
      .setOperation('parent')
      .setTraceId(traceId)
      .start();

    const childSpan = new SpanBuilder()
      .setProvider('openai')
      .setModel('gpt-4o')
      .setOperation('child')
      .setTraceId(traceId)
      .setParentSpanId(parentSpan.getSpanId())
      .start();

    const parentResult = await parentSpan.finish({ inputTokens: 100, outputTokens: 50 });
    const childResult = await childSpan.finish({ inputTokens: 50, outputTokens: 25 });

    assert.strictEqual(parentResult.trace_id, traceId);
    assert.strictEqual(childResult.trace_id, traceId);
    assert.strictEqual(childResult.parent_span_id, parentSpan.getSpanId());
  });

  it('should not auto-send when autoSend is false', async () => {
    let fetchCalled = false;
    const mockFetch: typeof fetch = async () => {
      fetchCalled = true;
      return {
        ok: true,
        status: 200,
        statusText: 'OK',
        text: async () => 'OK',
      } as Response;
    };

    Kalibr.init({
      apiKey: 'test-key',
      tenantId: 'test-tenant',
      fetch: mockFetch,
    });

    const span = new SpanBuilder()
      .setProvider('openai')
      .setModel('gpt-4o')
      .setOperation('test')
      .start();

    await span.finish({
      inputTokens: 100,
      outputTokens: 50,
      autoSend: false,
    });

    // Should not have called fetch
    assert.strictEqual(fetchCalled, false);
  });
});
