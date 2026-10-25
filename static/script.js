
const form = document.getElementById("chat-form");
const input = document.getElementById("message-input");
const messages = document.getElementById("messages");
const typing = document.getElementById("typing");
const sendButton = document.getElementById("send-button");

const suggestions = document.querySelectorAll("[data-message]");

const REQUEST_TIMEOUT = 30000;

// Display a chat message safely.
function addMessage(text, sender) {
    const bubble = document.createElement("div");
    bubble.className = `message ${sender}`;
    bubble.textContent = text;

    messages.appendChild(bubble);
    scrollToBottom();

    return bubble;
}

// Display a PDF download card.
function addPdfCard(parent, pdf) {
    if (!pdf || !pdf.name || !pdf.url) {
        return;
    }

    const card = document.createElement("div");
    card.className = "pdf-card";

    const title = document.createElement("div");
    title.className = "pdf-title";
    title.textContent = `📄 ${pdf.name}`;

    const link = document.createElement("a");
    link.className = "download-link";
    link.href = pdf.url;
    link.textContent = "Download PDF";
    link.setAttribute("download", "");

    card.appendChild(title);
    card.appendChild(link);
    parent.appendChild(card);

    scrollToBottom();
}

// Keep the latest message visible.
function scrollToBottom() {
    const panel = document.querySelector(".chat-panel");

    if (panel) {
        panel.scrollTop = panel.scrollHeight;
    }
}

// Send a request to the Flask backend.
async function sendMessage(message) {
    message = message.trim();

    if (!message || sendButton.disabled) {
        return;
    }

    addMessage(message, "user");

    input.value = "";
    input.disabled = true;
    sendButton.disabled = true;
    typing.hidden = false;

    const controller = new AbortController();

    const timeoutId = setTimeout(() => {
        controller.abort();
    }, REQUEST_TIMEOUT);

    try {
        const response = await fetch("/api/chat", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                message: message
            }),
            signal: controller.signal
        });

        let data;

        try {
            data = await response.json();
        } catch {
            throw new Error(
                `The server returned an invalid response (HTTP ${response.status}).`
            );
        }

        if (!response.ok) {
            throw new Error(
                data.reply ||
                `The server returned error ${response.status}.`
            );
        }

        const reply = addMessage(
            data.reply || "I couldn't find a response.",
            "bot"
        );

        if (data.pdf) {
            addPdfCard(reply, data.pdf);
        }

    } catch (error) {
        console.error("Chatbot request error:", error);

        let errorMessage;

        if (error.name === "AbortError") {
            errorMessage =
                "The request took too long. Please check your Flask terminal and try again.";
        } else if (error instanceof TypeError) {
            errorMessage =
                "Unable to connect to the server. Check that Flask is running.";
        } else {
            errorMessage =
                error.message ||
                "Something went wrong. Please try again.";
        }

        addMessage(errorMessage, "bot");

    } finally {
        clearTimeout(timeoutId);

        typing.hidden = true;
        input.disabled = false;
        sendButton.disabled = false;

        input.focus();
        scrollToBottom();
    }
}

// Handle the message form.
form.addEventListener("submit", function (event) {
    event.preventDefault();
    sendMessage(input.value);
});

// Handle the suggested prompts.
suggestions.forEach(function (button) {
    button.addEventListener("click", function () {
        sendMessage(button.dataset.message || "");
    });
});
