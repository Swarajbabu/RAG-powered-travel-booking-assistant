document.addEventListener("DOMContentLoaded", () => {
    const button = document.getElementById("travel-guide-button");
    const panel = document.getElementById("travel-guide-panel");
    const closeButton = document.getElementById("travel-guide-close");
    const clearButton = document.getElementById("travel-guide-clear");
    const form = document.getElementById("travel-guide-form");
    const input = document.getElementById("travel-guide-input");
    const sendButton = document.getElementById("travel-guide-send");
    const messages = document.getElementById("travel-guide-messages");

    if (!button || !panel || !closeButton || !clearButton || !form || !input || !sendButton || !messages) {
        return;
    }

    let history = [];
    let isSending = false;
    let revealVersion = 0;

    function appendFormattedText(container, text) {
        const lines = String(text || "").replace(/\r/g, "").split("\n");
        let bulletList = null;

        lines.forEach((line) => {
            const trimmed = line.trim();
            if (!trimmed) {
                bulletList = null;
                return;
            }

            const bullet = trimmed.match(/^[-*]\s+(.+)$/);
            if (bullet) {
                if (!bulletList) {
                    bulletList = document.createElement("ul");
                    bulletList.className = "travel-guide-answer-list";
                    container.append(bulletList);
                }
                const item = document.createElement("li");
                appendInlineFormatting(item, bullet[1]);
                bulletList.append(item);
                return;
            }

            bulletList = null;
            const paragraph = document.createElement("p");
            paragraph.className = "travel-guide-answer-paragraph";
            appendInlineFormatting(paragraph, trimmed);
            container.append(paragraph);
        });
    }

    function appendInlineFormatting(container, text) {
        const pattern = /(\*\*[^*]+\*\*)/g;
        String(text).split(pattern).forEach((part) => {
            if (!part) return;
            if (part.startsWith("**") && part.endsWith("**")) {
                const strong = document.createElement("strong");
                strong.textContent = part.slice(2, -2);
                container.append(strong);
            } else {
                container.append(document.createTextNode(part));
            }
        });
    }

    function appendMessage(role, text) {
        const message = document.createElement("article");
        message.className = `travel-guide-message travel-guide-message-${role}`;

        const label = document.createElement("strong");
        label.textContent = role === "user" ? "You" : "Wanderlust";

        const content = document.createElement("div");
        content.className = "travel-guide-message-content";
        content.textContent = role === "assistant" ? text : text;

        message.append(label, content);
        messages.append(message);
        messages.scrollTop = messages.scrollHeight;
        return message;
    }

    function cleanSourceName(sourceFile) {
        return String(sourceFile || "Wanderlust guide")
            .replace(/^\d+\.\s*/, "")
            .replace(/\.pdf$/i, "")
            .replace(/_/g, " ")
            .replace(/\b\w/g, (letter) => letter.toUpperCase());
    }

    function appendSources(sources) {
        if (!Array.isArray(sources) || sources.length === 0) return;

        const details = document.createElement("details");
        details.className = "travel-guide-sources";

        const summary = document.createElement("summary");
        summary.textContent = `Sources · ${sources.length}`;

        const sourceList = document.createElement("div");
        sourceList.className = "travel-guide-source-list";

        sources.forEach((source) => {
            const item = document.createElement("span");
            item.className = "travel-guide-source";
            item.textContent = cleanSourceName(source.sourceFile);
            item.title = `${source.sourceFile || "Source"}, page ${source.pageNumber || "?"}`;
            sourceList.append(item);
        });

        details.append(summary, sourceList);
        messages.append(details);
        messages.scrollTop = messages.scrollHeight;
    }

    function revealAssistantAnswer(message, text) {
        const content = message.querySelector(".travel-guide-message-content");
        if (!content) return Promise.resolve();

        const words = String(text || "")
            .replace(/\r/g, "")
            .replace(/^#{1,6}\s+/gm, "")
            .replace(/\*{3,}/g, "")
            .replace(/\*\*([^*]+)\*\*/g, "$1")
            .replace(/(^|\n)[*_]{1,3}(\s+)/g, "$1")
            .replace(/\*\s+/g, "")
            .replace(/\b_([^_]+)_\b/g, "$1")
            .replace(/[`]/g, "")
            .trim()
            .split(/(\s+)/)
            .filter((part) => part.length > 0);

        content.textContent = "";
        const currentVersion = ++revealVersion;

        return new Promise((resolve) => {
            let index = 0;
            const timer = window.setInterval(() => {
                if (currentVersion !== revealVersion) {
                    window.clearInterval(timer);
                    resolve();
                    return;
                }

                content.textContent += words[index] || "";
                index += 1;
                messages.scrollTop = messages.scrollHeight;

                if (index >= words.length) {
                    window.clearInterval(timer);
                    resolve();
                }
            }, words[index]?.trim().length > 8 ? 45 : 65);
        });
    }

    function setOpen(open) {
        if (!open) revealVersion += 1;
        panel.hidden = !open;
        button.setAttribute("aria-expanded", String(open));
        if (open) input.focus();
    }

    function resetConversation() {
        revealVersion += 1;
        history = [];
        messages.replaceChildren();
        appendMessage("assistant", "Ask me about listings, bookings, room sharing, host rules, or Wanderlust policies.");
        input.focus();
    }

    button.addEventListener("click", () => setOpen(panel.hidden));
    closeButton.addEventListener("click", () => setOpen(false));
    clearButton.addEventListener("click", resetConversation);

    document.querySelectorAll("[data-travel-guide-prompt]").forEach((promptButton) => {
        promptButton.addEventListener("click", () => {
            input.value = promptButton.dataset.travelGuidePrompt || "";
            form.requestSubmit();
        });
    });

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (isSending) return;

        const message = input.value.trim();
        if (!message) return;

        isSending = true;
        input.value = "";
        input.disabled = true;
        sendButton.disabled = true;
        appendMessage("user", message);

        const loadingMessage = appendMessage("assistant", "Searching the Wanderlust documents...");
        loadingMessage.classList.add("travel-guide-loading");

        const csrfInput = form.querySelector('[name="_csrf"]');

        try {
            const response = await fetch("/api/chat", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRF-Token": csrfInput?.value || ""
                },
                body: JSON.stringify({
                    message,
                    history,
                    pageContext: window.location.pathname
                })
            });

            const payload = await response.json().catch(() => null);
            loadingMessage.remove();

            if (!response.ok) {
                appendMessage("assistant", payload?.error || "The travel assistant could not answer right now.");
                return;
            }

            const answerMessage = appendMessage("assistant", "");
            await revealAssistantAnswer(answerMessage, payload.answer);
            appendSources(payload.sources);

            history = history.concat([
                { role: "user", content: message },
                { role: "assistant", content: payload.answer }
            ]).slice(-4);
        } catch (error) {
            loadingMessage.remove();
            appendMessage("assistant", "The travel assistant could not answer right now. Please try again.");
        } finally {
            isSending = false;
            input.disabled = false;
            sendButton.disabled = false;
            input.focus();
        }
    });

    resetConversation();
});
