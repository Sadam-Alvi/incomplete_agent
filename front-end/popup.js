
const API_BASE = "https://new-repo.fastapicloud.dev";
// const API_BASE = "http://127.0.0.1:8000";

// ==========================================
// 1. DOM ELEMENTS
// ==========================================

const analyzeScreen = document.getElementById("analyze-screen");
const chatScreen = document.getElementById("chat-screen");

const pageUrlInput = document.getElementById("page-url");
const loadingText = document.getElementById("loading-text");
const progressBar = document.getElementById("progress-bar");
const progressPercent = document.getElementById("progress-percent");
const statusElement = document.getElementById("status");
const retryBtn = document.getElementById("retry-btn");

const chatMessages = document.getElementById("chat-messages");
const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("question");
const sendButton = document.getElementById("send-btn");
const chatPageTitle = document.getElementById("chat-page-title");

// ==========================================
// 2. APPLICATION STATE
// ==========================================

let currentUrl = "";
let currentSessionId = "";
let chatHistory = [];
let analysisInProgress = false;
let requestInProgress = false;
let progressPollTimer = null;

// ==========================================
// 3. STORAGE KEYS
// ==========================================

function getChatKey(url) {
    return "Webby_chat_" + encodeURIComponent(url);
}

function getSessionKey(url) {
    return "Webby_session_" + encodeURIComponent(url);
}

// ==========================================
// 4. SAVE AND LOAD CHAT HISTORY
// ==========================================

async function saveChat(url, history) {
    if (!url) return;

    try {
        await chrome.storage.local.set({
            [getChatKey(url)]: history
        });
    } catch (error) {
        console.error("Failed to save chat:", error);
    }
}

async function loadChat(url) {
    try {
        const result = await chrome.storage.local.get(getChatKey(url));
        const savedHistory = result[getChatKey(url)];

        return Array.isArray(savedHistory) ? savedHistory : [];
    } catch (error) {
        console.error("Failed to load chat:", error);
        return [];
    }
}

async function clearChat(url) {
    if (!url) return;

    try {
        await chrome.storage.local.remove(getChatKey(url));
        chatHistory = [];
        chatMessages.replaceChildren();
    } catch (error) {
        console.error("Failed to clear chat:", error);
    }
}

// ==========================================
// 5. SESSION MANAGEMENT
// ==========================================

async function getOrCreateSessionId(url) {
    const key = getSessionKey(url);

    try {
        const result = await chrome.storage.local.get(key);

        if (result[key]) {
            return result[key];
        }

        const sessionId = crypto.randomUUID();

        await chrome.storage.local.set({
            [key]: sessionId
        });

        return sessionId;
    } catch (error) {
        console.error("Session ID error:", error);
        return crypto.randomUUID();
    }
}

async function saveSessionId(url, sessionId) {
    if (!url || !sessionId) return;

    await chrome.storage.local.set({
        [getSessionKey(url)]: sessionId
    });
}

function updateSessionDisplay() {
    if (chatPageTitle) {
        try {
            chatPageTitle.textContent = new URL(currentUrl).hostname;
        } catch {
            chatPageTitle.textContent = "Webby Chat";
        }
    }
}

// ==========================================
// 6. API HELPER
// ==========================================

async function apiRequest(endpoint, options = {}) {
    const response = await fetch(`${API_BASE}${endpoint}`, {
        ...options,
        headers: {
            "Content-Type": "application/json",
            ...(options.headers || {})
        }
    });

    if (!response.ok) {
        const errorText = await response.text();

        throw new Error(
            `HTTP ${response.status}: ${errorText || response.statusText}`
        );
    }

    return response.json();
}

// ==========================================
// 7. GET CURRENT TAB URL
// ==========================================

async function getCurrentTabUrl() {
    const tabs = await chrome.tabs.query({
        active: true,
        currentWindow: true
    });

    if (!tabs.length || !tabs[0].url) {
        throw new Error("Could not determine the current tab URL.");
    }

    return tabs[0].url;
}

function isRestrictedUrl(url) {
    return (
        url.startsWith("chrome://") ||
        url.startsWith("edge://") ||
        url.startsWith("about:") ||
        url.startsWith("chrome-extension://") ||
        url.startsWith("https://chrome.google.com/webstore") ||
        url.startsWith("https://microsoftedge.microsoft.com/addons")
    );
}

// ==========================================
// 8. SCREEN MANAGEMENT
// ==========================================

function showAnalyzeScreen() {
    if (analyzeScreen) analyzeScreen.hidden = false;
    if (chatScreen) chatScreen.hidden = true;
}
function showChatScreen() {
    console.log("Switching to chat screen");

    if (analyzeScreen) {
        analyzeScreen.hidden = true;
        analyzeScreen.style.display = "none";
    }

    if (chatScreen) {
        chatScreen.hidden = false;
        chatScreen.style.display = "flex";
    }
}

// ==========================================
// 9. CHAT MESSAGE CREATION
// ==========================================

function createMessage(content, role) {
    const message = document.createElement("div");

    const isUser = role === "user";
    message.className = isUser ? "message user" : "message bot";

    if (content) {
        if (isUser) {
            message.textContent = content;
        } else {
            renderMarkdown(message, content);
        }
    }

    chatMessages.appendChild(message);
    scrollChatToBottom();

    return message;
}

function scrollChatToBottom() {
    if (chatMessages) {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
}

// ==========================================
// 10. MARKDOWN RENDERING
// ==========================================

function renderMarkdown(element, content) {
    // Use Marked if it is included in popup.html.
    if (typeof marked !== "undefined" && typeof marked.parse === "function") {
        element.innerHTML = marked.parse(content);
    } else {
        // Safe fallback if Marked is not loaded.
        element.textContent = content;
    }
}

// ==========================================
// 11. START PAGE ANALYSIS
// ==========================================

async function startAnalysis() {
    if (analysisInProgress) return;

    analysisInProgress = true;
    showAnalyzeScreen();

    if (retryBtn) retryBtn.hidden = true;
    if (statusElement) statusElement.textContent = "";
    if (loadingText) loadingText.textContent = "Starting page analysis...";

    if (progressBar) progressBar.style.width = "0%";
    if (progressPercent) progressPercent.textContent = "0%";

    try {
        const result = await apiRequest("/analyze", {
            method: "POST",
            body: JSON.stringify({
                url: currentUrl
            })
        });

        if (!result.task_id) {
            throw new Error("The server did not return an analysis task ID.");
        }

        await pollProgress(result.task_id);

    } catch (error) {
        console.error("Analysis error:", error);

        if (loadingText) {
            loadingText.textContent = "Page analysis failed.";
        }

        if (statusElement) {
            statusElement.textContent = error.message;
        }

        if (retryBtn) retryBtn.hidden = false;

    } finally {
        analysisInProgress = false;
    }
}

// ==========================================
// 12. POLL ANALYSIS PROGRESS
// ==========================================

async function pollProgress(taskId) {
    const maxAttempts = 600;
    const delayMs = 1000;

    for (let attempt = 0; attempt < maxAttempts; attempt++) {
        const task = await apiRequest(
            `/progress/${encodeURIComponent(taskId)}`
        );

        if (task.message && loadingText) {
            loadingText.textContent = task.message;
        }

        const progress = Number(task.progress);

        if (Number.isFinite(progress)) {
            const boundedProgress = Math.max(
                0,
                Math.min(100, progress)
            );

            if (progressBar) {
                progressBar.style.width = `${boundedProgress}%`;
            }

            if (progressPercent) {
                progressPercent.textContent =
                    `${Math.round(boundedProgress)}%`;
            }
        }

        if (task.error || task.stage === "error") {
            throw new Error(
                task.message || "The server could not analyze this page."
            );
        }

        if (task.stage === "complete") {
            if (progressBar) progressBar.style.width = "100%";
            if (progressPercent) progressPercent.textContent = "100%";

            await openChat();
            return;
        }

        await new Promise(resolve => setTimeout(resolve, delayMs));
    }

    throw new Error("Analysis timed out. Please try again.");
}

// ==========================================
// 13. OPEN CHAT AFTER ANALYSIS
// ==========================================

async function openChat() {
    chatHistory = await loadChat(currentUrl);

    showChatScreen();
    updateSessionDisplay();

    chatMessages.replaceChildren();

    // Restore previous messages for this URL.
    for (const item of chatHistory) {
        if (!item || typeof item.content !== "string") continue;

        const role = item.role === "user" ? "user" : "bot";
        createMessage(item.content, role);
    }

    scrollChatToBottom();

    if (chatInput) chatInput.focus();
}

// ==========================================
// 14. STREAM ANSWER FROM FASTAPI
// Uses /ask/stream ONLY
// ==========================================

async function streamAnswer(question, url, sessionId, messageElement) {
    const response = await fetch(`${API_BASE}/ask/stream`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            question: question,
            url: url,
            session_id: sessionId
        })
    });

    if (!response.ok) {
        const errorText = await response.text();

        throw new Error(
            `HTTP ${response.status}: ${errorText || response.statusText}`
        );
    }

    if (!response.body) {
        throw new Error("The server did not provide a streaming response.");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");

    let answer = "";

    try {
        while (true) {
            const { value, done } = await reader.read();

            if (done) break;

            answer += decoder.decode(value, {
                stream: true
            });

            // Show plain text while tokens are arriving.
            messageElement.textContent = answer;

            scrollChatToBottom();
        }

        // Flush any remaining bytes in the decoder.
        answer += decoder.decode();

        messageElement.textContent = answer;
        scrollChatToBottom();

    } catch (error) {
        try {
            await reader.cancel();
        } catch {
            // Ignore cancellation errors.
        }

        throw error;
    }

    if (!answer.trim()) {
        throw new Error("The model returned an empty answer.");
    }

    return answer;
}

// ==========================================
// 15. CHAT FORM SUBMISSION
// All responses stream through /ask/stream
// ==========================================

if (chatForm) {
    chatForm.addEventListener("submit", async event => {
        event.preventDefault();

        if (requestInProgress) return;

        const question = chatInput.value.trim();

        if (!question || !currentUrl || !currentSessionId) {
            return;
        }

        requestInProgress = true;

        chatInput.value = "";
        chatInput.disabled = true;

        if (sendButton) {
            sendButton.disabled = true;
        }

        // Show the user's message.
        createMessage(question, "user");

        // Show the assistant's response as it streams.
        const replyElement = createMessage("", "bot");

        try {
            const answer = await streamAnswer(
                question,
                currentUrl,
                currentSessionId,
                replyElement
            );

            // Render Markdown once the complete response arrives.
            renderMarkdown(replyElement, answer);

            // Save the complete exchange.
            chatHistory.push(
                {
                    role: "user",
                    content: question
                },
                {
                    role: "assistant",
                    content: answer
                }
            );

            await saveChat(currentUrl, chatHistory);

        } catch (error) {
            console.error("Chat streaming error:", error);

            replyElement.textContent =
                `Sorry, I couldn't generate an answer. ${error.message}`;

        } finally {
            requestInProgress = false;
            chatInput.disabled = false;

            if (sendButton) {
                sendButton.disabled = false;
            }

            chatInput.focus();
            scrollChatToBottom();
        }
    });
}

// ==========================================
// 16. RETRY ANALYSIS
// ==========================================

if (retryBtn) {
    retryBtn.addEventListener("click", () => {
        startAnalysis();
    });
}

// ==========================================
// 17. INITIALIZE EXTENSION
// ==========================================

async function initialize() {
    try {
        currentUrl = await getCurrentTabUrl();

        if (pageUrlInput) {
            pageUrlInput.value = currentUrl;
        }

        if (isRestrictedUrl(currentUrl)) {
            showAnalyzeScreen();

            if (loadingText) {
                loadingText.textContent =
                    "Webby Chat cannot analyze browser-internal pages. Open a regular website or YouTube video.";
            }

            if (retryBtn) retryBtn.hidden = true;
            return;
        }

        currentSessionId = await getOrCreateSessionId(currentUrl);

        await saveSessionId(currentUrl, currentSessionId);

        updateSessionDisplay();

        // If analysis is already complete on the backend,
        // this starts a new analysis task for the current URL.
        // The backend should handle duplicate URL analysis appropriately.
        await startAnalysis();

    } catch (error) {
        console.error("Initialization error:", error);

        showAnalyzeScreen();

        if (loadingText) {
            loadingText.textContent = "Webby Chat could not start.";
        }

        if (statusElement) {
            statusElement.textContent = error.message;
        }

        if (retryBtn) retryBtn.hidden = false;
    }
}

document.addEventListener("DOMContentLoaded", initialize);

// Handle the case where this script runs after DOMContentLoaded.
if (document.readyState !== "loading") {
    initialize();
}
