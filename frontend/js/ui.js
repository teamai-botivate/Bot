/**
 * ui.js
 * ─────
 * Pure DOM helpers. No fetch, no business logic.
 */

const messageList = document.getElementById('message-list');
const messageInput = document.getElementById('message-input');
const sendButton = document.getElementById('send-button');

/**
 * Append a message bubble to the chat list.
 * @param {'user'|'bot'} sender
 * @param {string} htmlContent  – inner HTML for the bubble
 * @returns {HTMLElement}       – the created .message element
 */
function addMessage(sender, htmlContent) {
    const el = document.createElement('div');
    el.classList.add('message', sender);

    const avatarHtml = sender === 'user'
        ? '<span class="material-symbols-outlined">person</span>'
        : '<img src="/static/B%20PNG%20(1).png" alt="Botivate logo" />';

    el.innerHTML = `
        <div class="avatar">
            ${avatarHtml}
        </div>
        <div class="message-content">
            ${htmlContent}
        </div>
    `;

    messageList.appendChild(el);
    scrollToBottom();
    return el;
}

/** Replace a message bubble's inner HTML (used to swap loading → answer). */
function updateMessageContent(messageEl, htmlContent) {
    messageEl.querySelector('.message-content').innerHTML = htmlContent;
    scrollToBottom();
}

/** Show the animated three-dot typing indicator. */
function createLoadingHTML() {
    return `
        <div class="typing-indicator">
            <span></span><span></span><span></span>
        </div>
    `;
}

/** Smooth-scroll the message list to the bottom. */
function scrollToBottom() {
    messageList.scrollTop = messageList.scrollHeight;
}

/**
 * Auto-grow the textarea and toggle the send button.
 */
function setupInputAutoGrow() {
    messageInput.addEventListener('input', () => {
        messageInput.style.height = 'auto';
        messageInput.style.height = `${messageInput.scrollHeight}px`;
        sendButton.disabled = messageInput.value.trim().length === 0;
    });
}

/** Reset the textarea back to its default single-row height. */
function resetInput() {
    messageInput.value = '';
    messageInput.style.height = 'auto';
    sendButton.disabled = true;
}

/**
 * Render time-of-day greeting HTML.
 * @param {string} name  – director's first name
 * @returns {string}
 */
function buildGreetingHTML(name) {
    const hour = new Date().getHours();
    let timeOfDay;

    if (hour >= 5 && hour < 12) {
        timeOfDay = 'Morning';
    } else if (hour >= 12 && hour < 17) {
        timeOfDay = 'Afternoon';
    } else {
        timeOfDay = 'Evening';
    }

    return `
        <p>Good ${timeOfDay} ${name} Sir,</p>
        <p>I can provide you reports on Purchase, PO Pending, Sales Orders, and more.</p>
        <p>I can also create tasks for you.</p>
        <p>Please let me know which report you'd like to see today.</p>
        <p>For any other queries, please provide context, and what you want to see.</p>
    `;
}

/**
 * Collect the last N conversation turns from the DOM
 * and return them as the format the backend expects.
 * @param {number} turnsToKeep
 * @returns {Array<{type: string, content: string}>}
 */
function buildChatHistory(turnsToKeep) {
    const history = [];
    const allMessages = Array.from(messageList.querySelectorAll('.message'));

    // Exclude the very last message (which is still being composed / loading)
    const historyMessages = allMessages.slice(0, -1);
    const recentMessages = historyMessages.slice(-(turnsToKeep * 2));

    for (const msg of recentMessages) {
        const type = msg.classList.contains('user') ? 'human' : 'ai';
        const content = msg.querySelector('.message-content').innerText;
        if (content) {
            history.push({ type, content });
        }
    }

    return history;
}
