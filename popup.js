const API_BASE = "http://127.0.0.1:8000";

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

let currentUrl = "";
let isPolling = false;

async function getCurrentTabUrl() {
  return new Promise((resolve) => {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      resolve(tabs[0]?.url || null);
    });
  });
}

async function startAnalysis() {
  try {
    // Reset UI
    statusEl.textContent = "";
    retryBtn.hidden = true;
    progressBar.style.width = "0%";
    progressPercent.textContent = "0%";
    loadingText.textContent = "Starting analysis...";
    analyzeScreen.hidden = false;
    chatScreen.hidden = true;
    isPolling = false;

    currentUrl = await getCurrentTabUrl();

    if (!currentUrl || currentUrl.startsWith("chrome://") || currentUrl.startsWith("chrome-extension://") || currentUrl.startsWith("about:")) {
      pageUrlEl.textContent = "Cannot analyze this page";
      statusEl.textContent = "Please open a normal webpage (http/https) and try again.";
      retryBtn.hidden = false;
      return;
    }

    pageUrlEl.textContent = currentUrl;

    const res = await fetch(`${API_BASE}/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: currentUrl }),
    });

    if (!res.ok) throw new Error("Failed to start analysis");

    const data = await res.json();
    isPolling = true;
    pollProgress(data.task_id);

  } catch (err) {
    console.error(err);
    statusEl.textContent = "Error: " + err.message;
    retryBtn.hidden = false;
  }
}

async function pollProgress(taskId) {
  if (!isPolling) return;

  try {
    const res = await fetch(`${API_BASE}/progress/${taskId}`);
    if (!res.ok) throw new Error("Failed to get progress");

    const data = await res.json();

    // Update progress UI
    loadingText.textContent = data.message || "Working...";
    const progress = Number(data.progress) || 0;
    progressBar.style.width = `${progress}%`;
    progressPercent.textContent = `${progress}%`;

    // Error case
    if (data.error === true) {
      isPolling = false;
      statusEl.textContent = data.message || "Something went wrong";
      retryBtn.hidden = false;
      return;
    }

    // SUCCESS - stop polling and switch to chat
    // SUCCESS - stop polling and switch to chat
  if (data.stage === "complete" || progress >= 100) {
  isPolling = false;

  // Force hide analyze screen completely
  analyzeScreen.style.display = "none";
  analyzeScreen.hidden = true;

  // Show only chat
  chatScreen.hidden = false;
  chatScreen.style.display = "flex";

  chatPageTitle.textContent = currentUrl;

  // Clear previous messages (optional)
  chatMessages.innerHTML = "";

  // Welcome message
  addMessage("Hi! I've analyzed this page. Ask me anything about it.", "bot");
  return;
}

    // Continue polling
    setTimeout(() => pollProgress(taskId), 600);

  } catch (err) {
    console.error(err);
    isPolling = false;
    statusEl.textContent = "Connection error. Is the backend running?";
    retryBtn.hidden = false;
  }
}

// Chat form
chatForm.addEventListener("submit", async (e) => {
  e.preventDefault();

  const question = questionInput.value.trim();
  if (!question) return;

  // Disable input while waiting
  questionInput.disabled = true;
  sendBtn.disabled = true;

  addMessage(question, "user");
  questionInput.value = "";

  const thinkingId = addMessage("Thinking...", "bot thinking");

  try {
    const res = await fetch(`${API_BASE}/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url: currentUrl,
        question: question,
      }),
    });

    const data = await res.json();
    const answer = data.answer || "No answer received.";

    // Replace "Thinking..." with real answer
    const thinkingEl = document.getElementById(thinkingId);
    if (thinkingEl) {
      thinkingEl.classList.remove("thinking");
      thinkingEl.textContent = answer;
    }
  } catch (err) {
    const thinkingEl = document.getElementById(thinkingId);
    if (thinkingEl) {
      thinkingEl.classList.remove("thinking");
      thinkingEl.textContent = "Sorry, something went wrong. Please try again.";
    }
  } finally {
    questionInput.disabled = false;
    sendBtn.disabled = false;
    questionInput.focus();
  }
});

function addMessage(text, type) {
  const div = document.createElement("div");
  div.className = `message ${type}`;

  if (type.includes("bot")) {
    // Convert simple markdown → HTML
    div.innerHTML = markdownToHtml(text);
    div.id = "msg-" + Date.now() + Math.random().toString(36).slice(2);
  } else {
    // User messages stay plain text
    div.textContent = text;
  }

  chatMessages.appendChild(div);
  chatMessages.scrollTop = chatMessages.scrollHeight;

  return div.id;
}

// Simple markdown converter (no external library needed)
function markdownToHtml(text) {
  // Escape HTML first for safety
  let html = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  // Bold **text**
  html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");

  // Italic *text* or _text_
  html = html.replace(/\*(.+?)\*/g, "<em>$1</em>");
  html = html.replace(/_(.+?)_/g, "<em>$1</em>");

  // Headers
  html = html.replace(/^### (.+)$/gm, "<h4>$1</h4>");
  html = html.replace(/^## (.+)$/gm, "<h3>$1</h3>");
  html = html.replace(/^# (.+)$/gm, "<h3>$1</h3>");

  // Bullet points
  html = html.replace(/^- (.+)$/gm, "<li>$1</li>");
  html = html.replace(/(<li>.*<\/li>)/gs, "<ul>$1</ul>");

  // Numbered lists
  html = html.replace(/^\d+\. (.+)$/gm, "<li>$1</li>");

  // Line breaks
  html = html.replace(/\n/g, "<br>");

  // Clean up extra <br> inside lists
  html = html.replace(/<ul><br>/g, "<ul>");
  html = html.replace(/<br><\/ul>/g, "</ul>");
  html = html.replace(/<\/li><br>/g, "</li>");

  return html;
}

retryBtn.addEventListener("click", startAnalysis);

// Start when popup opens
document.addEventListener("DOMContentLoaded", startAnalysis);