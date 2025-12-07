/**
 * Kalibr TypeScript SDK
 *
 * Zero-dependency LLM observability SDK matching the Python SDK schema exactly.
 * Compatible with Kalibr SDK v1.0.30+ and Kalibr Backend v1.0+
 *
 * @example
 * ```typescript
 * import { Kalibr, SpanBuilder } from '@kalibr/sdk';
 *
 * // Initialize once
 * Kalibr.init({ apiKey: 'your-api-key', tenantId: 'your-tenant' });
 *
 * // Send a span
 * const span = new SpanBuilder()
 *   .setProvider('openai')
 *   .setModel('gpt-4o')
 *   .setOperation('chat_completion')
 *   .start();
 *
 * // ... do your LLM call ...
 *
 * await span.finish({ inputTokens: 100, outputTokens: 50 });
 * ```
 */

// ============================================================================
// Types matching trace_models.py TraceEvent exactly
// ============================================================================

/** LLM provider types */
export type Provider = 'openai' | 'anthropic' | 'google' | 'cohere' | 'custom';

/** Execution status */
export type Status = 'success' | 'error' | 'timeout';

/** Deployment environment */
export type Environment = 'prod' | 'staging' | 'dev';

/** Data classification */
export type DataClass = 'economic' | 'performance' | 'diagnostic';

/**
 * Kalibr Span interface matching TraceEvent from trace_models.py exactly.
 *
 * Compatible with:
 * - Kalibr SDK v1.0.30+
 * - Kalibr Backend v1.0+
 * - ClickHouse storage schema
 */
export interface KalibrSpan {
  // Schema metadata
  /** Schema version (always "1.0") */
  schema_version: '1.0';

  // Identity (required)
  /** Unique trace identifier (UUID or 16-char alphanumeric, min 16 chars) */
  trace_id: string;
  /** Unique span identifier (UUIDv4 format, min 16 chars) */
  span_id: string;
  /** Parent span ID for nested operations (UUIDv4 format, min 16 chars) */
  parent_span_id?: string | null;

  // Tenant & Context (required: tenant_id)
  /** Tenant identifier (1-64 chars) */
  tenant_id: string;
  /** Workflow identifier for multi-step operations (max 64 chars) */
  workflow_id?: string | null;
  /** Sandbox/VM/Environment identifier (max 64 chars) */
  sandbox_id?: string | null;
  /** Runtime environment (vercel_vm, fly_io, local, etc., max 32 chars) */
  runtime_env?: string | null;

  // LLM Details (required: provider, model_id)
  /** LLM provider */
  provider: Provider;
  /** Model identifier (e.g., gpt-4o, claude-3-opus, 1-64 chars) */
  model_id: string;
  /** Human-readable model name (optional, defaults to model_id) */
  model_name?: string | null;

  // Operation (required)
  /** Operation type (e.g., chat_completion, summarize, refine, 1-64 chars) */
  operation: string;
  /** API endpoint or function name (max 128 chars) */
  endpoint?: string | null;

  // Performance (required)
  /** Total duration in milliseconds */
  duration_ms: number;
  /** Legacy field, same as duration_ms */
  latency_ms?: number | null;

  // Tokens (required)
  /** Number of input tokens */
  input_tokens: number;
  /** Number of output tokens */
  output_tokens: number;
  /** Total tokens (input + output), computed if not provided */
  total_tokens?: number | null;

  // Cost (required: cost_usd)
  /** Total cost in USD */
  cost_usd: number;
  /** Legacy field, same as cost_usd */
  total_cost_usd?: number | null;
  /** Price per token in USD */
  unit_price_usd?: number | null;

  // Status & Errors (required: status)
  /** Execution status */
  status: Status;
  /** Error class name if status is error (max 64 chars) */
  error_type?: string | null;
  /** Error message if status is error (max 512 chars) */
  error_message?: string | null;
  /** Stack trace for errors (optional) */
  stack_trace?: string | null;

  // Timestamps (required: timestamp)
  /** Event timestamp (ISO 8601 UTC) */
  timestamp: string;
  /** Operation start time (ISO 8601 UTC) */
  ts_start?: string | null;
  /** Operation end time (ISO 8601 UTC) */
  ts_end?: string | null;

  // Environment
  /** Deployment environment */
  environment?: Environment | null;
  /** Service name (max 64 chars) */
  service?: string | null;

  // User Context
  /** End user identifier (anonymized, max 64 chars) */
  user_id?: string | null;
  /** Request identifier for correlation (max 64 chars) */
  request_id?: string | null;

  // Metadata
  /** Additional custom metadata */
  metadata?: Record<string, unknown> | null;
  /** Data classification */
  data_class?: DataClass | null;

  // Legacy fields
  /** Legacy field, same as provider */
  vendor?: string | null;
}

/**
 * Partial span for building - only required fields need to be set before finish
 */
export type PartialSpan = Partial<KalibrSpan>;

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Generate a 32-character hex ID for trace_id or span_id.
 * Uses crypto.randomUUID() if available, falls back to Math.random().
 */
export function generateId(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID().replace(/-/g, '');
  }
  // Fallback for environments without crypto.randomUUID
  const hex = '0123456789abcdef';
  let result = '';
  for (let i = 0; i < 32; i++) {
    result += hex[Math.floor(Math.random() * 16)];
  }
  return result;
}

/**
 * Generate ISO 8601 timestamp in UTC.
 */
export function timestamp(): string {
  return new Date().toISOString();
}

// ============================================================================
// Pricing Table (matching cost_adapter.py)
// ============================================================================

/** Pricing per 1M tokens */
interface ModelPricing {
  input: number;
  output: number;
}

/** Pricing tables matching cost_adapter.py */
const PRICING: Record<string, Record<string, ModelPricing>> = {
  openai: {
    'gpt-4': { input: 30.0, output: 60.0 },
    'gpt-4-turbo': { input: 10.0, output: 30.0 },
    'gpt-4o': { input: 2.5, output: 10.0 },
    'gpt-3.5-turbo': { input: 0.5, output: 1.5 },
    'gpt-4o-mini': { input: 0.15, output: 0.6 },
  },
  anthropic: {
    'claude-3-opus': { input: 15.0, output: 75.0 },
    'claude-3-sonnet': { input: 3.0, output: 15.0 },
    'claude-3-haiku': { input: 0.25, output: 1.25 },
    'claude-3.5-sonnet': { input: 3.0, output: 15.0 },
  },
  google: {
    'gemini-pro': { input: 1.25, output: 5.0 },
    'gemini-1.5-pro': { input: 1.25, output: 5.0 },
    'gemini-1.5-flash': { input: 0.075, output: 0.3 },
  },
  cohere: {
    command: { input: 1.0, output: 2.0 },
    'command-r': { input: 0.5, output: 1.5 },
    'command-r-plus': { input: 3.0, output: 15.0 },
  },
};

/** Default pricing for unknown models */
const DEFAULT_PRICING: ModelPricing = { input: 30.0, output: 60.0 };

/**
 * Normalize model name to match pricing table.
 */
function normalizeModelName(provider: Provider, modelName: string): string {
  const modelLower = modelName.toLowerCase();

  if (provider === 'openai') {
    if (modelLower.includes('gpt-4o-mini')) return 'gpt-4o-mini';
    if (modelLower.includes('gpt-4o')) return 'gpt-4o';
    if (modelLower.includes('gpt-4-turbo')) return 'gpt-4-turbo';
    if (modelLower.includes('gpt-4')) return 'gpt-4';
    if (modelLower.includes('gpt-3.5')) return 'gpt-3.5-turbo';
  }

  if (provider === 'anthropic') {
    if (modelLower.includes('claude-3.5-sonnet') || modelLower.includes('claude-3-5-sonnet')) {
      return 'claude-3.5-sonnet';
    }
    if (modelLower.includes('claude-3-opus')) return 'claude-3-opus';
    if (modelLower.includes('claude-3-sonnet')) return 'claude-3-sonnet';
    if (modelLower.includes('claude-3-haiku')) return 'claude-3-haiku';
  }

  if (provider === 'google') {
    if (modelLower.includes('gemini-1.5-flash')) return 'gemini-1.5-flash';
    if (modelLower.includes('gemini-1.5-pro')) return 'gemini-1.5-pro';
    if (modelLower.includes('gemini-pro')) return 'gemini-pro';
  }

  if (provider === 'cohere') {
    if (modelLower.includes('command-r-plus')) return 'command-r-plus';
    if (modelLower.includes('command-r')) return 'command-r';
    if (modelLower.includes('command')) return 'command';
  }

  return modelLower;
}

/**
 * Calculate cost in USD based on provider, model, and token counts.
 * Matches cost_adapter.py pricing tables.
 *
 * @param provider - LLM provider
 * @param modelId - Model identifier
 * @param inputTokens - Number of input tokens
 * @param outputTokens - Number of output tokens
 * @returns Cost in USD (rounded to 6 decimal places)
 */
export function calculateCost(
  provider: Provider,
  modelId: string,
  inputTokens: number,
  outputTokens: number
): number {
  const providerPricing = PRICING[provider] || {};
  const normalizedModel = normalizeModelName(provider, modelId);
  const pricing = providerPricing[normalizedModel] || DEFAULT_PRICING;

  const inputCost = (inputTokens / 1_000_000) * pricing.input;
  const outputCost = (outputTokens / 1_000_000) * pricing.output;

  return Math.round((inputCost + outputCost) * 1_000_000) / 1_000_000;
}

// ============================================================================
// Kalibr Client Configuration
// ============================================================================

/** Configuration options for Kalibr client */
export interface KalibrConfig {
  /** API key for authentication (X-API-Key header) */
  apiKey: string;
  /** Tenant identifier */
  tenantId: string;
  /** API endpoint URL (default: https://api.kalibr.systems/api/ingest) */
  endpoint?: string;
  /** Default environment */
  environment?: Environment;
  /** Default service name */
  service?: string;
  /** Enable debug logging */
  debug?: boolean;
  /** Custom fetch function (for testing or custom implementations) */
  fetch?: typeof fetch;
}

// ============================================================================
// Kalibr Client Class
// ============================================================================

/**
 * Kalibr client for sending LLM observability data.
 *
 * Can be used as a singleton via static methods or instantiated directly.
 *
 * @example
 * ```typescript
 * // Singleton pattern
 * Kalibr.init({ apiKey: 'key', tenantId: 'tenant' });
 * await Kalibr.sendSpan(span);
 *
 * // Direct instantiation
 * const client = new Kalibr({ apiKey: 'key', tenantId: 'tenant' });
 * await client.sendSpan(span);
 * ```
 */
export class Kalibr {
  private static instance: Kalibr | null = null;

  private readonly config: Required<
    Pick<KalibrConfig, 'apiKey' | 'tenantId' | 'endpoint' | 'debug'>
  > &
    Pick<KalibrConfig, 'environment' | 'service' | 'fetch'>;

  private readonly fetchFn: typeof fetch;

  constructor(config: KalibrConfig) {
    this.config = {
      apiKey: config.apiKey,
      tenantId: config.tenantId,
      endpoint: config.endpoint || 'https://api.kalibr.systems/api/ingest',
      environment: config.environment,
      service: config.service,
      debug: config.debug || false,
      fetch: config.fetch,
    };

    // Use provided fetch or global fetch
    this.fetchFn = config.fetch || globalThis.fetch;

    if (!this.fetchFn) {
      throw new Error(
        'fetch is not available. Please provide a fetch implementation or use Node.js 18+.'
      );
    }
  }

  /**
   * Initialize the singleton Kalibr client.
   */
  static init(config: KalibrConfig): Kalibr {
    Kalibr.instance = new Kalibr(config);
    return Kalibr.instance;
  }

  /**
   * Get the singleton instance (throws if not initialized).
   */
  static getInstance(): Kalibr {
    if (!Kalibr.instance) {
      throw new Error('Kalibr not initialized. Call Kalibr.init() first.');
    }
    return Kalibr.instance;
  }

  /**
   * Check if the singleton is initialized.
   */
  static isInitialized(): boolean {
    return Kalibr.instance !== null;
  }

  /**
   * Send a single span (singleton method).
   */
  static async sendSpan(span: KalibrSpan): Promise<void> {
    return Kalibr.getInstance().sendSpan(span);
  }

  /**
   * Send multiple spans in batch (singleton method).
   */
  static async sendSpans(spans: KalibrSpan[]): Promise<void> {
    return Kalibr.getInstance().sendSpans(spans);
  }

  /**
   * Get the tenant ID from config.
   */
  getTenantId(): string {
    return this.config.tenantId;
  }

  /**
   * Get the default environment from config.
   */
  getEnvironment(): Environment | undefined {
    return this.config.environment;
  }

  /**
   * Get the default service from config.
   */
  getService(): string | undefined {
    return this.config.service;
  }

  /**
   * Log debug message if debug mode is enabled.
   */
  private log(message: string, ...args: unknown[]): void {
    if (this.config.debug) {
      console.log(`[Kalibr SDK] ${message}`, ...args);
    }
  }

  /**
   * Send a single span to the Kalibr API.
   */
  async sendSpan(span: KalibrSpan): Promise<void> {
    return this.sendSpans([span]);
  }

  /**
   * Send multiple spans to the Kalibr API in NDJSON format.
   */
  async sendSpans(spans: KalibrSpan[]): Promise<void> {
    if (spans.length === 0) {
      return;
    }

    // Convert to NDJSON format
    const ndjson = spans.map((span) => JSON.stringify(span)).join('\n') + '\n';

    this.log(`Sending ${spans.length} span(s) to ${this.config.endpoint}`);

    try {
      const response = await this.fetchFn(this.config.endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-ndjson',
          'X-API-Key': this.config.apiKey,
        },
        body: ndjson,
      });

      if (!response.ok) {
        const errorText = await response.text().catch(() => 'Unknown error');
        throw new Error(`Kalibr API error ${response.status}: ${errorText}`);
      }

      this.log(
        `Successfully sent ${spans.length} span(s):`,
        spans.map((s) => `${s.operation} (${s.duration_ms}ms, $${s.cost_usd.toFixed(6)})`)
      );
    } catch (error) {
      this.log('Failed to send spans:', error);
      throw error;
    }
  }
}

// ============================================================================
// Span Builder
// ============================================================================

/**
 * Fluent builder for creating Kalibr spans with automatic timing.
 *
 * @example
 * ```typescript
 * const span = new SpanBuilder()
 *   .setProvider('openai')
 *   .setModel('gpt-4o')
 *   .setOperation('chat_completion')
 *   .setTraceId(existingTraceId)  // optional, for linking spans
 *   .start();
 *
 * // ... perform LLM call ...
 *
 * await span.finish({
 *   inputTokens: 100,
 *   outputTokens: 50,
 *   status: 'success',
 * });
 * ```
 */
export class SpanBuilder {
  private span: PartialSpan = {
    schema_version: '1.0',
  };

  private startTime: number | null = null;
  private startTimestamp: string | null = null;
  private client: Kalibr | null = null;

  /**
   * Set the trace ID (optional, generates one if not set).
   */
  setTraceId(traceId: string): this {
    this.span.trace_id = traceId;
    return this;
  }

  /**
   * Set the span ID (optional, generates one if not set).
   */
  setSpanId(spanId: string): this {
    this.span.span_id = spanId;
    return this;
  }

  /**
   * Set the parent span ID for nested operations.
   */
  setParentSpanId(parentSpanId: string | null): this {
    this.span.parent_span_id = parentSpanId;
    return this;
  }

  /**
   * Set the tenant ID (uses client config if not set).
   */
  setTenantId(tenantId: string): this {
    this.span.tenant_id = tenantId;
    return this;
  }

  /**
   * Set the workflow ID.
   */
  setWorkflowId(workflowId: string): this {
    this.span.workflow_id = workflowId;
    return this;
  }

  /**
   * Set the sandbox ID.
   */
  setSandboxId(sandboxId: string): this {
    this.span.sandbox_id = sandboxId;
    return this;
  }

  /**
   * Set the runtime environment.
   */
  setRuntimeEnv(runtimeEnv: string): this {
    this.span.runtime_env = runtimeEnv;
    return this;
  }

  /**
   * Set the LLM provider.
   */
  setProvider(provider: Provider): this {
    this.span.provider = provider;
    this.span.vendor = provider; // Legacy field
    return this;
  }

  /**
   * Set the model ID.
   */
  setModel(modelId: string): this {
    this.span.model_id = modelId;
    this.span.model_name = modelId; // Default model_name to model_id
    return this;
  }

  /**
   * Set the model name (human-readable).
   */
  setModelName(modelName: string): this {
    this.span.model_name = modelName;
    return this;
  }

  /**
   * Set the operation type.
   */
  setOperation(operation: string): this {
    this.span.operation = operation;
    return this;
  }

  /**
   * Set the endpoint/function name.
   */
  setEndpoint(endpoint: string): this {
    this.span.endpoint = endpoint;
    return this;
  }

  /**
   * Set the environment.
   */
  setEnvironment(environment: Environment): this {
    this.span.environment = environment;
    return this;
  }

  /**
   * Set the service name.
   */
  setService(service: string): this {
    this.span.service = service;
    return this;
  }

  /**
   * Set the user ID.
   */
  setUserId(userId: string): this {
    this.span.user_id = userId;
    return this;
  }

  /**
   * Set the request ID.
   */
  setRequestId(requestId: string): this {
    this.span.request_id = requestId;
    return this;
  }

  /**
   * Set custom metadata.
   */
  setMetadata(metadata: Record<string, unknown>): this {
    this.span.metadata = metadata;
    return this;
  }

  /**
   * Set the data classification.
   */
  setDataClass(dataClass: DataClass): this {
    this.span.data_class = dataClass;
    return this;
  }

  /**
   * Use a specific Kalibr client (instead of singleton).
   */
  useClient(client: Kalibr): this {
    this.client = client;
    return this;
  }

  /**
   * Start timing the span.
   * Records the start timestamp and returns a StartedSpan.
   */
  start(): StartedSpan {
    this.startTime = Date.now();
    this.startTimestamp = timestamp();

    // Generate IDs if not set
    if (!this.span.trace_id) {
      this.span.trace_id = generateId();
    }
    if (!this.span.span_id) {
      this.span.span_id = generateId();
    }

    // Get client (use provided or singleton)
    const client = this.client || (Kalibr.isInitialized() ? Kalibr.getInstance() : null);

    // Apply defaults from client config
    if (client) {
      if (!this.span.tenant_id) {
        this.span.tenant_id = client.getTenantId();
      }
      if (!this.span.environment && client.getEnvironment()) {
        this.span.environment = client.getEnvironment();
      }
      if (!this.span.service && client.getService()) {
        this.span.service = client.getService();
      }
    }

    return new StartedSpan(
      this.span,
      this.startTime,
      this.startTimestamp,
      client
    );
  }
}

/**
 * Options for finishing a span.
 */
export interface FinishOptions {
  /** Number of input tokens */
  inputTokens: number;
  /** Number of output tokens */
  outputTokens: number;
  /** Execution status (default: 'success') */
  status?: Status;
  /** Error type if status is 'error' */
  errorType?: string;
  /** Error message if status is 'error' */
  errorMessage?: string;
  /** Stack trace if status is 'error' */
  stackTrace?: string;
  /** Override calculated cost */
  costUsd?: number;
  /** Custom metadata to merge */
  metadata?: Record<string, unknown>;
  /** Whether to send automatically (default: true) */
  autoSend?: boolean;
}

/**
 * A started span that can be finished to record duration and send.
 */
export class StartedSpan {
  private readonly span: PartialSpan;
  private readonly startTime: number;
  private readonly startTimestamp: string;
  private readonly client: Kalibr | null;

  constructor(
    span: PartialSpan,
    startTime: number,
    startTimestamp: string,
    client: Kalibr | null
  ) {
    this.span = span;
    this.startTime = startTime;
    this.startTimestamp = startTimestamp;
    this.client = client;
  }

  /**
   * Get the trace ID.
   */
  getTraceId(): string {
    return this.span.trace_id!;
  }

  /**
   * Get the span ID.
   */
  getSpanId(): string {
    return this.span.span_id!;
  }

  /**
   * Finish the span, calculate duration, and optionally send.
   *
   * @returns The completed KalibrSpan
   */
  async finish(options: FinishOptions): Promise<KalibrSpan> {
    const endTime = Date.now();
    const endTimestamp = timestamp();
    const durationMs = endTime - this.startTime;

    // Validate required fields
    if (!this.span.provider) {
      throw new Error('SpanBuilder: provider is required');
    }
    if (!this.span.model_id) {
      throw new Error('SpanBuilder: model_id is required (use setModel())');
    }
    if (!this.span.operation) {
      throw new Error('SpanBuilder: operation is required');
    }
    if (!this.span.tenant_id) {
      throw new Error('SpanBuilder: tenant_id is required');
    }

    // Calculate cost if not provided
    const costUsd =
      options.costUsd ??
      calculateCost(this.span.provider, this.span.model_id, options.inputTokens, options.outputTokens);

    // Merge metadata
    const metadata =
      this.span.metadata || options.metadata
        ? { ...this.span.metadata, ...options.metadata }
        : undefined;

    // Build complete span
    const completeSpan: KalibrSpan = {
      schema_version: '1.0',
      trace_id: this.span.trace_id!,
      span_id: this.span.span_id!,
      parent_span_id: this.span.parent_span_id ?? null,
      tenant_id: this.span.tenant_id!,
      workflow_id: this.span.workflow_id ?? null,
      sandbox_id: this.span.sandbox_id ?? null,
      runtime_env: this.span.runtime_env ?? null,
      provider: this.span.provider,
      model_id: this.span.model_id,
      model_name: this.span.model_name ?? this.span.model_id,
      operation: this.span.operation,
      endpoint: this.span.endpoint ?? null,
      duration_ms: durationMs,
      latency_ms: durationMs, // Legacy field
      input_tokens: options.inputTokens,
      output_tokens: options.outputTokens,
      total_tokens: options.inputTokens + options.outputTokens,
      cost_usd: costUsd,
      total_cost_usd: costUsd, // Legacy field
      status: options.status ?? 'success',
      error_type: options.errorType ?? null,
      error_message: options.errorMessage ?? null,
      stack_trace: options.stackTrace ?? null,
      timestamp: endTimestamp,
      ts_start: this.startTimestamp,
      ts_end: endTimestamp,
      environment: this.span.environment ?? null,
      service: this.span.service ?? null,
      user_id: this.span.user_id ?? null,
      request_id: this.span.request_id ?? null,
      metadata: metadata ?? null,
      data_class: this.span.data_class ?? null,
      vendor: this.span.vendor ?? this.span.provider, // Legacy field
    };

    // Auto-send if enabled (default) and client available
    if (options.autoSend !== false && this.client) {
      await this.client.sendSpan(completeSpan);
    }

    return completeSpan;
  }

  /**
   * Mark the span as errored and finish.
   */
  async error(
    error: Error | { type?: string; message: string; stack?: string },
    options: Omit<FinishOptions, 'status' | 'errorType' | 'errorMessage' | 'stackTrace'>
  ): Promise<KalibrSpan> {
    const errorType = error instanceof Error ? error.constructor.name : (error.type ?? 'Error');
    const errorMessage = error.message;
    const stackTrace = error instanceof Error ? error.stack : error.stack;

    return this.finish({
      ...options,
      status: 'error',
      errorType,
      errorMessage,
      stackTrace,
    });
  }

  /**
   * Mark the span as timed out and finish.
   */
  async timeout(
    options: Omit<FinishOptions, 'status'>
  ): Promise<KalibrSpan> {
    return this.finish({
      ...options,
      status: 'timeout',
    });
  }
}

// ============================================================================
// Convenience Functions
// ============================================================================

/**
 * Create a complete span manually (without using SpanBuilder).
 * Useful for cases where timing is handled externally.
 */
export function createSpan(options: {
  tenantId: string;
  provider: Provider;
  modelId: string;
  operation: string;
  durationMs: number;
  inputTokens: number;
  outputTokens: number;
  status?: Status;
  traceId?: string;
  spanId?: string;
  parentSpanId?: string | null;
  costUsd?: number;
  environment?: Environment;
  service?: string;
  workflowId?: string;
  sandboxId?: string;
  runtimeEnv?: string;
  endpoint?: string;
  userId?: string;
  requestId?: string;
  metadata?: Record<string, unknown>;
  dataClass?: DataClass;
  errorType?: string;
  errorMessage?: string;
  stackTrace?: string;
}): KalibrSpan {
  const now = timestamp();
  const costUsd =
    options.costUsd ??
    calculateCost(options.provider, options.modelId, options.inputTokens, options.outputTokens);

  return {
    schema_version: '1.0',
    trace_id: options.traceId ?? generateId(),
    span_id: options.spanId ?? generateId(),
    parent_span_id: options.parentSpanId ?? null,
    tenant_id: options.tenantId,
    workflow_id: options.workflowId ?? null,
    sandbox_id: options.sandboxId ?? null,
    runtime_env: options.runtimeEnv ?? null,
    provider: options.provider,
    model_id: options.modelId,
    model_name: options.modelId,
    operation: options.operation,
    endpoint: options.endpoint ?? null,
    duration_ms: options.durationMs,
    latency_ms: options.durationMs,
    input_tokens: options.inputTokens,
    output_tokens: options.outputTokens,
    total_tokens: options.inputTokens + options.outputTokens,
    cost_usd: costUsd,
    total_cost_usd: costUsd,
    status: options.status ?? 'success',
    error_type: options.errorType ?? null,
    error_message: options.errorMessage ?? null,
    stack_trace: options.stackTrace ?? null,
    timestamp: now,
    ts_start: null,
    ts_end: now,
    environment: options.environment ?? null,
    service: options.service ?? null,
    user_id: options.userId ?? null,
    request_id: options.requestId ?? null,
    metadata: options.metadata ?? null,
    data_class: options.dataClass ?? null,
    vendor: options.provider,
  };
}

/**
 * Wrap an async function with automatic span creation and sending.
 *
 * @example
 * ```typescript
 * const result = await withSpan(
 *   {
 *     provider: 'openai',
 *     modelId: 'gpt-4o',
 *     operation: 'chat_completion',
 *   },
 *   async () => {
 *     const response = await openai.chat.completions.create({...});
 *     return {
 *       result: response,
 *       inputTokens: response.usage.prompt_tokens,
 *       outputTokens: response.usage.completion_tokens,
 *     };
 *   }
 * );
 * ```
 */
export async function withSpan<T>(
  options: {
    provider: Provider;
    modelId: string;
    operation: string;
    traceId?: string;
    parentSpanId?: string | null;
    workflowId?: string;
    endpoint?: string;
    metadata?: Record<string, unknown>;
  },
  fn: () => Promise<{ result: T; inputTokens: number; outputTokens: number }>
): Promise<T> {
  const builder = new SpanBuilder()
    .setProvider(options.provider)
    .setModel(options.modelId)
    .setOperation(options.operation);

  if (options.traceId) builder.setTraceId(options.traceId);
  if (options.parentSpanId) builder.setParentSpanId(options.parentSpanId);
  if (options.workflowId) builder.setWorkflowId(options.workflowId);
  if (options.endpoint) builder.setEndpoint(options.endpoint);
  if (options.metadata) builder.setMetadata(options.metadata);

  const span = builder.start();

  try {
    const { result, inputTokens, outputTokens } = await fn();
    await span.finish({ inputTokens, outputTokens, status: 'success' });
    return result;
  } catch (error) {
    await span.error(error as Error, { inputTokens: 0, outputTokens: 0 });
    throw error;
  }
}
