/**
 * app.js
 * ------
 * Application entry-point.
 * Wires together ui.js, api.js, and CONFIG from config.js.
 * All three must be loaded before this script runs.
 */

sendButton.addEventListener('click', handleSend);

messageInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSend();
    }
});

setupInputAutoGrow();
const latencyChip = document.getElementById('latency-chip');

async function handleSend() {
    const userInput = messageInput.value.trim();
    if (!userInput) return;

    addMessage('user', userInput);
    const chatHistory = buildChatHistory(CONFIG.HISTORY_TURNS_TO_KEEP);
    resetInput();

    const loadingEl = addMessage('bot', createLoadingHTML());

    try {
        const startedAt = performance.now();
        let streamedText = '';
        let hasStreamed = false;

        await sendChatMessageStream(
            userInput,
            chatHistory,
            (chunk) => {
                hasStreamed = true;
                streamedText += chunk;
                const escaped = streamedText
                    .replace(/&/g, '&amp;')
                    .replace(/</g, '&lt;')
                    .replace(/>/g, '&gt;');
                updateMessageContent(
                    loadingEl,
                    `<span class="streaming-text">${escaped}</span><span class="streaming-cursor"></span>`
                );
            },
            (status) => {
                if (!hasStreamed) {
                    updateMessageContent(
                        loadingEl,
                        `<span class="status-text">${DOMPurify.sanitize(status)}</span>`
                    );
                }
            }
        );

        if (streamedText) {
            updateMessageContent(loadingEl, DOMPurify.sanitize(marked.parse(streamedText)));
        }

        const elapsedMs = performance.now() - startedAt;
        if (latencyChip) {
            latencyChip.textContent = `Last response: ${(elapsedMs / 1000).toFixed(2)}s`;
        }
    } catch (err) {
        console.error('Chat API error:', err);
        updateMessageContent(
            loadingEl,
            '<p>An error occurred. Please try again later.</p>'
        );
        if (latencyChip) {
            latencyChip.textContent = 'Last response: failed';
        }
    }
}

function initializeChat() {
    document.getElementById('initial-greeting').innerHTML =
        buildGreetingHTML(CONFIG.DIRECTOR_NAME);

    sendButton.disabled = true;
}

initializeChat();
