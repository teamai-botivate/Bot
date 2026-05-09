/**
 * app.js
 * ──────
 * Application entry-point.
 * Wires together ui.js, api.js, and CONFIG from config.js.
 * All three must be loaded before this script runs.
 */

// ── Event listeners ──────────────────────────────────────────────────────────

sendButton.addEventListener('click', handleSend);

messageInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSend();
    }
});

setupInputAutoGrow();

// ── Core send handler ─────────────────────────────────────────────────────────

async function handleSend() {
    const userInput = messageInput.value.trim();
    if (!userInput) return;

    // 1. Render user message & snapshot history BEFORE resetting input
    addMessage('user', userInput);
    const chatHistory = buildChatHistory(CONFIG.HISTORY_TURNS_TO_KEEP);
    resetInput();

    // 2. Show loading bubble
    const loadingEl = addMessage('bot', createLoadingHTML());

    // 3. Call backend (streaming)
    try {
        let streamedText = '';
        let hasStreamed = false;

        await sendChatMessageStream(
            userInput,
            chatHistory,
            (chunk) => {
                hasStreamed = true;
                streamedText += chunk;
                // Show plain text while streaming so every token is immediately visible.
                // Full markdown is applied only once streaming is done.
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
                // Only show status while no text has streamed yet.
                if (!hasStreamed) {
                    updateMessageContent(
                        loadingEl,
                        `<span class="status-text">${DOMPurify.sanitize(status)}</span>`
                    );
                }
            }
        );

        // Replace plain streaming text with fully-parsed markdown when done.
        if (streamedText) {
            updateMessageContent(loadingEl, DOMPurify.sanitize(marked.parse(streamedText)));
        }
    } catch (err) {
        console.error('Chat API error:', err);
        updateMessageContent(
            loadingEl,
            '<p>⚠️ An error occurred. Please try again later.</p>'
        );
    }
}

// ── Initialisation ────────────────────────────────────────────────────────────

function initializeChat() {
    // Inject greeting into the pre-rendered bot bubble
    document.getElementById('initial-greeting').innerHTML =
        buildGreetingHTML(CONFIG.DIRECTOR_NAME);

    sendButton.disabled = true;
}

initializeChat();
