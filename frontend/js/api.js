/**
 * api.js
 * ──────
 * All network calls to the Botivate AI backend.
 */

/**
 * Send a message to the backend and return the answer string.
 *
 * @param {string} question          – the user's message
 * @param {Array}  chatHistory       – previous turns (built by ui.buildChatHistory)
 * @returns {Promise<string>}        – the bot's answer
 * @throws  {Error}                  – on non-2xx HTTP or network failure
 */
async function sendChatMessage(question, chatHistory) {
    const url = `${CONFIG.API_BASE_URL}/chat`;

    const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            question,
            chat_history: chatHistory,
        }),
    });

    if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    const data = await response.json();
    return data.answer || "Sorry, I couldn't get a response.";
}

/**
 * Stream a message response from the backend.
 *
 * @param {string} question
 * @param {Array} chatHistory
 * @param {(chunk: string) => void} onChunk
 * @param {(status: string) => void} [onStatus]
 * @returns {Promise<void>}
 */
async function sendChatMessageStream(question, chatHistory, onChunk, onStatus) {
    const url = `${CONFIG.API_BASE_URL}/chat/stream`;

    const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            question,
            chat_history: chatHistory,
        }),
    });

    if (!response.ok || !response.body) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n\n');
        buffer = parts.pop() || '';

        for (const part of parts) {
            const line = part.trim();
            if (!line.startsWith('data:')) continue;
            const jsonText = line.replace(/^data:\s*/, '');
            if (!jsonText) continue;

            const payload = JSON.parse(jsonText);
            if (payload.done) return;
            if (payload.error) throw new Error(payload.error);
            if (payload.status && onStatus) onStatus(payload.status);
            if (payload.chunk) onChunk(payload.chunk);
        }
    }
}
