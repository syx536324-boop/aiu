// Responsibility: connect Pi's model adapter to the existing local Ollama service.
import {createModels, createProvider} from '@earendil-works/pi-ai';
import {openAICompletionsApi} from '@earendil-works/pi-ai/api/openai-completions.lazy';

export function createLocalModel(config) {
  const model = {
    id: config.model, name: config.model, api: 'openai-completions', provider: 'ollama',
    baseUrl: `${config.ollamaUrl.replace(/\/$/, '')}/v1`, reasoning: false, input: ['text'],
    cost: {input: 0, output: 0, cacheRead: 0, cacheWrite: 0},
    contextWindow: config.contextWindow, maxTokens: config.maxOutputTokens,
    compat: {supportsDeveloperRole: false, supportsReasoningEffort: false, supportsStore: false, maxTokensField: 'max_tokens'}
  };
  const models = createModels();
  models.setProvider(createProvider({
    id: 'ollama', name: '本机 Ollama', baseUrl: model.baseUrl,
    auth: {apiKey: {name: 'Local Ollama', resolve: async () => ({auth: {apiKey: 'ollama'}})}},
    models: [model], api: openAICompletionsApi()
  }));
  return {model, streamFn: (m, context, options) => models.streamSimple(m, context, {
    ...options, maxTokens: config.maxOutputTokens,
    onPayload: payload => ({...payload, reasoning_effort: 'none'})
  })};
}
export async function modelStatus(config) {
  try {
    const response = await fetch(`${config.ollamaUrl}/api/tags`, {signal: AbortSignal.timeout(2500)});
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const result = await response.json();
    const available = result.models.map(m => m.name);
    return {online: true, model: config.model, available, ready: available.includes(config.model)};
  } catch (error) { return {online: false, ready: false, model: config.model, available: [], error: error.message}; }
}
