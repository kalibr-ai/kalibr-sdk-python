/**
 * Kalibr TypeScript SDK
 *
 * Zero-dependency LLM observability SDK for Next.js and TypeScript applications.
 *
 * @example
 * ```typescript
 * import { Kalibr, SpanBuilder } from '@kalibr/sdk';
 *
 * // Initialize once (e.g., in app/layout.tsx or pages/_app.tsx)
 * Kalibr.init({
 *   apiKey: process.env.KALIBR_API_KEY!,
 *   tenantId: process.env.KALIBR_TENANT_ID!,
 * });
 *
 * // Use SpanBuilder for automatic timing
 * const span = new SpanBuilder()
 *   .setProvider('openai')
 *   .setModel('gpt-4o')
 *   .setOperation('chat_completion')
 *   .start();
 *
 * const response = await openai.chat.completions.create({...});
 *
 * await span.finish({
 *   inputTokens: response.usage.prompt_tokens,
 *   outputTokens: response.usage.completion_tokens,
 * });
 * ```
 *
 * @packageDocumentation
 */

// Main exports
export {
  // Client
  Kalibr,
  type KalibrConfig,
  // Builder
  SpanBuilder,
  StartedSpan,
  type FinishOptions,
  // Types
  type KalibrSpan,
  type PartialSpan,
  type Provider,
  type Status,
  type Environment,
  type DataClass,
  // Utilities
  generateId,
  timestamp,
  calculateCost,
  createSpan,
  withSpan,
} from './kalibr';
