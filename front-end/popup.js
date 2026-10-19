
"use strict";

// ========================================
// CONFIGURATION
// ========================================

const API_BASE = "https://new-repo.fastapicloud.dev";

// ========================================
// DOM ELEMENTS
// ========================================
 
const analyzeScreen = document.getElementById("analyze-screen");
const chatScreen = document.getElementById("chat-screen");
const pageUrlEl = document.getElementById("page-url");
const loadingText = document.getElementById("loading-text");
const progressBar = document.getElementById("progress-bar");
const progressPercent = document.getElementById("progress-percent");
const statusEl = document.getElementById("status");
const retryBtn = document.getElementById("retry-btn");
const chatMessages = document.getElementById("chat-messages");
const chatForm = document.getElementById("chat-form");
const questionInput = document.getElementById("question");
const chatPageTitle = document.getElementById("chat-page-title");
const sendBtn = document.getElementById("send-btn");

// ========================================
// APPLICATION STATE
// ========================================

let currentUrl = "";
let chatHistory = [];
let isPolling = false;
let activeTaskId = null;
let isSending = false;

// ========================================
// STORAGE HELPERS
// ========================================

function getChatKey(url) {
  // Stable, consistent key for each page URL.
  return "Webby_chat_" + encodeURIComponent(url);
}

async function saveChat(url, history) {
  try {
    if (!url || !chrome.storage?.local) return;

    await chrome.storage.local.set({
      [getChatKey(url)]: history
    });
  } catch (error) {
    console.error("Chat save error:", error);
  }
}

async function loadChat(url) {
  try {
    if (!url || !chrome.storage?.local) return [];

    const key = getChatKey(url);
    const result = await chrome.storage.local.get(key);

    return Array.isArray(result[key]) ? result[key] : [];
  } catch (error) {
    console.error("Chat load error:", error);
    return [];
  }
}

async function clearChat(url) {
  try {
    if (url && chrome.storage?.local) {
      await chrome.storage.local.remove(getChatKey(url));
    }
  } catch (error) {
    console.error("Chat clear error:", error);
  }
}

// ========================================
// API HELPER
// ========================================

async function apiRequest(endpoint, options = {}) {
  const response = await fetch(`${API_BASE}${endpoint}`, options);
  const raw = await response.text();

  console.log(`${endpoint} HTTP status:`, response.status);
  console.log(`${endpoint} response:`, raw);

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${raw}`);
  }

  try {
    return JSON.parse(raw);
  } catch {
    throw new Error(`${endpoint} did not return valid JSON.`);
  }
}

// ========================================
// CURRENT TAB
// ========================================

async function getCurrentTabUrl() {
  const tabs = await chrome.tabs.query({
    active: true,
    currentWindow: true
  });

  return tabs[0]?.url || null;
}

function isRestrictedUrl(url) {
  return !url ||
    /^(chrome|chrome-extension|edge|about|devtools):/i.test(url);
}

// ========================================
// SCREEN MANAGEMENT
// ========================================

function showAnalyzeScreen() {
  analyzeScreen.hidden = false;
  analyzeScreen.style.display = "flex";

  chatScreen.hidden = true;
  chatScreen.style.display = "none";
}

function showChatScreen() {
  analyzeScreen.hidden = true;
  analyzeScreen.style.display = "none";

  chatScreen.hidden = false;
  chatScreen.style.display = "flex";

  chatPageTitle.textContent = currentUrl;
  chatMessages.replaceChildren();

  if (chatHistory.length === 0) {
    createMessage(
      "Hi! I've analyzed this page. Ask me anything about it.",
      "bot"
    );
  } else {
    chatHistory.forEach((message) => {
      createMessage(
        message.content,
        message.role === "user" ? "user" : "bot"
      );
    });
  }

  scrollChatToBottom();
}

// ========================================
// MESSAGE RENDERING
// ========================================


function createMessage(content, role = "bot") {
    const element = document.createElement("div");

    element.className = `message ${role}`;
    element.id =
        "msg-" + Date.now() + "-" +
        Math.random().toString(36).slice(2);

    if (role === "bot" || role === "assistant") {
        renderMarkdown(element, content);
    } else {
        element.textContent = String(content ?? "");
    }

    chatMessages.appendChild(element);
    scrollChatToBottom();

    return element;
}

function scrollChatToBottom() {
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

// ========================================
// START PAGE ANALYSIS
// ========================================

async function startAnalysis() {
  isPolling = false;
  activeTaskId = null;

  try {
    statusEl.textContent = "";
    retryBtn.hidden = true;
    progressBar.style.width = "0%";
    progressPercent.textContent = "0%";
    loadingText.textContent = "Checking webpage...";

    showAnalyzeScreen();

    currentUrl = await getCurrentTabUrl();

    if (isRestrictedUrl(currentUrl)) {
      pageUrlEl.textContent = "Cannot analyze this page";
      statusEl.textContent =
        "Open a normal webpage and try again.";
      retryBtn.hidden = false;
      return;
    }

    pageUrlEl.textContent = currentUrl;

    // Restore previous conversation for this URL.
    chatHistory = await loadChat(currentUrl);

    if (chatHistory.length > 0) {
      showChatScreen();
      return;
    }

    loadingText.textContent = "Starting analysis...";

    const data = await apiRequest("/analyze", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        url: currentUrl
      })
    });

    if (!data.task_id) {
      throw new Error("The /analyze response is missing task_id.");
    }

    activeTaskId = data.task_id;
    isPolling = true;

    await pollProgress(data.task_id);

  } catch (error) {
    console.error("Analysis failed:", error);

    isPolling = false;
    activeTaskId = null;

    loadingText.textContent = "Analysis failed";
    statusEl.textContent = error.message;
    retryBtn.hidden = false;
  }
}

// ========================================
// POLL ANALYSIS PROGRESS
// ========================================

async function pollProgress(taskId) {
  while (isPolling && activeTaskId === taskId) {
    try {
      const data = await apiRequest(
        `/progress/${encodeURIComponent(taskId)}`
      );

      loadingText.textContent =
        data.message || "Analyzing webpage...";

      const progress = Math.max(
        0,
        Math.min(100, Number(data.progress) || 0)
      );

      progressBar.style.width = `${progress}%`;
      progressPercent.textContent = `${progress}%`;

      if (data.error || data.stage === "failed") {
        throw new Error(
          typeof data.error === "string"
            ? data.error
            : data.message || "Page analysis failed."
        );
      }

      if (data.stage === "complete" || progress >= 100) {
        isPolling = false;
        activeTaskId = null;

        chatHistory = await loadChat(currentUrl);
        showChatScreen();
        return;
      }

      await new Promise((resolve) => setTimeout(resolve, 1000));

    } catch (error) {
      console.error("Progress polling failed:", error);

      isPolling = false;
      activeTaskId = null;

      loadingText.textContent = "Analysis failed";
      statusEl.textContent = error.message;
      retryBtn.hidden = false;
      return;
    }
  }
}

// ========================================
// EXTRACT LLM ANSWER
// ========================================

function extractAnswer(data) {
  let answer = data?.answer;

  if (answer == null) {
    throw new Error("The API response does not contain an answer.");
  }

  if (typeof answer === "object") {
    answer =
      answer.content ??
      answer.output ??
      answer.text ??
      JSON.stringify(answer, null, 2);
  }

  if (typeof answer !== "string") {
    answer = String(answer);
  }

  if (!answer.trim()) {
    throw new Error("The LLM returned an empty answer.");
  }

  return answer;
}

// ========================================
// CHAT SUBMISSION
// ========================================

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  if (isSending) return;

  const question = questionInput.value.trim();

  if (!question) return;

  if (!currentUrl) {
    createMessage("No webpage is selected. Reopen PagePal.", "bot");
    return;
  }

  isSending = true;
  questionInput.disabled = true;
  sendBtn.disabled = true;

  // Display the question immediately.
  createMessage(question, "user");
  questionInput.value = "";

  // Add a visible placeholder for the LLM response.
  const replyElement = createMessage("Thinking...", "bot thinking");

  // Remember history length so a failed exchange can be rolled back.
  const previousHistoryLength = chatHistory.length;

  chatHistory.push({
    role: "user",
    content: question
  });

  try {
    await saveChat(currentUrl, chatHistory);

    const data = await apiRequest("/ask", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        url: currentUrl,
        question: question
      })
    });

    console.log("Complete /ask response:", data);

    const answer = extractAnswer(data);

    // Plain text rendering avoids Markdown-renderer failures.
    replyElement.className = "message bot";
    renderMarkdown(replyElement, answer);

    chatHistory.push({
      role: "assistant",
      content: answer
    });

    await saveChat(currentUrl, chatHistory);

    console.log("LLM answer displayed:", answer);

  } catch (error) {
    console.error("Chat failed:", error);

    replyElement.className = "message bot";
    replyElement.textContent = `Error: ${error.message}`;

    // Do not save a failed exchange as a completed conversation.
    chatHistory = chatHistory.slice(0, previousHistoryLength);
    await saveChat(currentUrl, chatHistory);

  } finally {
    isSending = false;
    questionInput.disabled = false;
    sendBtn.disabled = false;
    questionInput.focus();

    scrollChatToBottom();
  }
});

// ========================================
// RETRY BUTTON
// ========================================

retryBtn.addEventListener("click", () => {
  startAnalysis();
});

// ========================================
// INITIALIZE
// ========================================

document.addEventListener("DOMContentLoaded", () => {
  startAnalysis();
});

function renderMarkdown(element, content) {
    const markdown = String(content ?? "");

    if (typeof marked === "undefined" ||
        typeof DOMPurify === "undefined") {
        element.textContent = markdown;
        return;
    }

    const html = marked.parse(markdown);

    element.innerHTML = DOMPurify.sanitize(html);
}
