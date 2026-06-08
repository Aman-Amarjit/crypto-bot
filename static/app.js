document.addEventListener("DOMContentLoaded", () => {
    // Nav Elements
    const navItems = document.querySelectorAll(".nav-item");
    const sections = document.querySelectorAll(".content-section");
    const sectionTitle = document.getElementById("section-title");
    const sectionSubtitle = document.getElementById("section-subtitle");
    
    // Status Elements
    const sidebarStatus = document.getElementById("sidebar-status");
    const statBotStatus = document.getElementById("stat-bot-status");
    const statActiveTopic = document.getElementById("stat-active-topic");
    const statTotalPosts = document.getElementById("stat-total-posts");
    
    // Control Elements
    const topicSelect = document.getElementById("run-topic-select");
    const btnTrigger = document.getElementById("btn-trigger-post");
    const btnClearTerminal = document.getElementById("btn-clear-terminal");
    const terminalBody = document.getElementById("terminal-body");
    
    // History & Config Elements
    const historyGrid = document.getElementById("history-grid");
    const configForm = document.getElementById("config-form");
    const toastContainer = document.getElementById("toast-container");
    
    let isPollingLogs = false;
    let logPollInterval = null;
    let lastLogContent = "";

    // 1. Navigation Logic
    navItems.forEach(item => {
        item.addEventListener("click", (e) => {
            e.preventDefault();
            const sectionId = item.getAttribute("data-section");
            
            navItems.forEach(nav => nav.classList.remove("active"));
            sections.forEach(sec => sec.classList.remove("active"));
            
            item.classList.add("active");
            document.getElementById(`sec-${sectionId}`).classList.add("active");
            
            // Update Headers
            if (sectionId === "overview") {
                sectionTitle.textContent = "Dashboard Overview";
                sectionSubtitle.textContent = "Real-time automation analytics and control panel";
            } else if (sectionId === "history") {
                sectionTitle.textContent = "Published Posts Log";
                sectionSubtitle.textContent = "Browse and view history of all social media posts";
                loadHistory(); // Reload history when visiting section
            } else if (sectionId === "config") {
                sectionTitle.textContent = "Configuration Manager";
                sectionSubtitle.textContent = "Manage API credentials and system configurations securely";
                loadConfig(); // Reload config when visiting section
            }
        });
    });

    // 2. Toast Notifications
    function showToast(message, type = "info") {
        const toast = document.createElement("div");
        toast.className = `toast ${type}`;
        
        let iconClass = "fa-circle-info";
        if (type === "success") iconClass = "fa-circle-check";
        if (type === "error") iconClass = "fa-triangle-exclamation";
        
        toast.innerHTML = `
            <i class="fa-solid ${iconClass} toast-icon"></i>
            <span class="toast-message">${message}</span>
        `;
        
        toastContainer.appendChild(toast);
        
        // Remove after 4 seconds
        setTimeout(() => {
            toast.style.animation = "slideOut 0.3s forwards cubic-bezier(0.175, 0.885, 0.32, 1.275)";
            setTimeout(() => {
                toast.remove();
            }, 300);
        }, 4000);
    }

    // 3. Load Stats & History
    async function loadHistory() {
        try {
            const resp = await fetch("/api/history");
            const data = await resp.json();
            
            if (data.error) {
                showToast(`Failed to load history: ${data.error}`, "error");
                return;
            }
            
            statTotalPosts.textContent = data.length;
            
            if (data.length > 0) {
                const lastPost = data[data.length - 1];
                // Determine next topic rotation in UI preview
                const topics = ["tech news", "robotics", "artificial intelligence", "cybersecurity"];
                try {
                    const lastIndex = topics.indexOf(lastPost.topic.toLowerCase());
                    const nextIndex = (lastIndex + 1) % topics.length;
                    statActiveTopic.textContent = topics[nextIndex].split(' ').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
                } catch(e) {
                    statActiveTopic.textContent = "Tech News";
                }
                
                // Build history cards
                historyGrid.innerHTML = "";
                // Show in reverse chronological order
                data.slice().reverse().forEach(post => {
                    const card = document.createElement("div");
                    card.className = "history-card";
                    
                    const topicClass = post.topic.toLowerCase().replace(/\s+/g, '-');
                    const postDate = new Date(post.timestamp).toLocaleString();
                    
                    card.innerHTML = `
                        <div class="card-media">
                            <img src="${post.image_url}" alt="Post image visual description">
                            <span class="card-badge ${topicClass}">${post.topic}</span>
                        </div>
                        <div class="card-content">
                            <span class="card-time"><i class="fa-regular fa-clock"></i> ${postDate}</span>
                            <p class="card-caption">${post.caption}</p>
                            <span class="card-prompt-toggle"><i class="fa-solid fa-chevron-down"></i> View Image Prompt</span>
                            <p class="card-prompt-text">${post.image_prompt}</p>
                        </div>
                        <div class="card-footer">
                            <a href="https://www.threads.net/post/${post.post_id}" target="_blank" class="btn-card">
                                <i class="fa-brands fa-threads"></i> View on Threads
                            </a>
                        </div>
                    `;
                    
                    // Add toggle prompt event
                    const toggle = card.querySelector(".card-prompt-toggle");
                    const promptText = card.querySelector(".card-prompt-text");
                    toggle.addEventListener("click", () => {
                        promptText.classList.toggle("show");
                        toggle.querySelector("i").classList.toggle("fa-chevron-up");
                        toggle.querySelector("i").classList.toggle("fa-chevron-down");
                    });
                    
                    historyGrid.appendChild(card);
                });
            } else {
                statActiveTopic.textContent = "Tech News";
                historyGrid.innerHTML = `
                    <div class="no-history">
                        <i class="fa-solid fa-box-open"></i>
                        <p>No posts published yet.</p>
                    </div>
                `;
            }
        } catch (e) {
            console.error("Error fetching history:", e);
        }
    }

    // 4. Load Config Settings
    async function loadConfig() {
        try {
            const resp = await fetch("/api/config");
            const data = await resp.json();
            
            document.getElementById("conf-groq-key").value = data.GROQ_API_KEY || "";
            document.getElementById("conf-pollinations-key").value = data.POLLINATIONS_API_KEY || "";
            document.getElementById("conf-gh-pat").value = data.GH_PAT || "";
            
            document.getElementById("conf-cloudinary-name").value = data.CLOUDINARY_CLOUD_NAME || "";
            document.getElementById("conf-cloudinary-key").value = data.CLOUDINARY_API_KEY || "";
            document.getElementById("conf-cloudinary-secret").value = data.CLOUDINARY_API_SECRET || "";
            
            document.getElementById("conf-threads-user-id").value = data.THREADS_USER_ID || "";
            document.getElementById("conf-threads-token").value = data.THREADS_ACCESS_TOKEN || "";
        } catch (e) {
            showToast("Failed to load configuration", "error");
        }
    }

    // Save Config Settings
    configForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        
        const payload = {
            GROQ_API_KEY: document.getElementById("conf-groq-key").value,
            POLLINATIONS_API_KEY: document.getElementById("conf-pollinations-key").value,
            GH_PAT: document.getElementById("conf-gh-pat").value,
            CLOUDINARY_CLOUD_NAME: document.getElementById("conf-cloudinary-name").value,
            CLOUDINARY_API_KEY: document.getElementById("conf-cloudinary-key").value,
            CLOUDINARY_API_SECRET: document.getElementById("conf-cloudinary-secret").value,
            THREADS_USER_ID: document.getElementById("conf-threads-user-id").value,
            THREADS_ACCESS_TOKEN: document.getElementById("conf-threads-token").value
        };
        
        try {
            const resp = await fetch("/api/config", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
            const data = await resp.json();
            
            if (resp.ok) {
                showToast("Configuration saved successfully", "success");
            } else {
                showToast(`Save failed: ${data.error}`, "error");
            }
        } catch (e) {
            showToast("Network error saving settings", "error");
        }
    });

    // 5. Terminal & Output Log Polling
    function appendTerminalLine(text, type = "info") {
        const line = document.createElement("div");
        line.className = `log-line log-${type}`;
        line.textContent = text;
        terminalBody.appendChild(line);
        terminalBody.scrollTop = terminalBody.scrollHeight;
    }

    function formatAndPrintLogs(rawLogs) {
        if (rawLogs === lastLogContent) return;
        
        // Find new logs
        const newPart = rawLogs.slice(lastLogContent.length);
        lastLogContent = rawLogs;
        
        if (!newPart.trim()) return;
        
        const lines = newPart.split("\n");
        lines.forEach(line => {
            if (!line.trim()) return;
            
            let type = "info";
            if (line.includes("Failed") || line.includes("Error:") || line.includes("Traceback") || line.includes("Exception")) {
                type = "error";
            } else if (line.includes("Completed Successfully") || line.includes("successful") || line.includes("Success!")) {
                type = "success";
            } else if (line.includes("Warning:")) {
                type = "warning";
            }
            
            appendTerminalLine(line, type);
        });
    }

    async function pollLogs() {
        try {
            const resp = await fetch("/api/logs");
            const data = await resp.json();
            if (data.logs) {
                formatAndPrintLogs(data.logs);
            }
        } catch (e) {
            console.error("Error polling logs:", e);
        }
    }

    async function checkBotStatus() {
        try {
            const resp = await fetch("/api/status");
            const data = await resp.json();
            
            if (data.running) {
                setUIStateRunning();
                if (!isPollingLogs) {
                    isPollingLogs = true;
                    logPollInterval = setInterval(pollLogs, 1000);
                }
            } else {
                setUIStateIdle();
                if (isPollingLogs) {
                    isPollingLogs = false;
                    clearInterval(logPollInterval);
                    pollLogs(); // One final poll to get last logs
                    loadHistory(); // Reload history to display newly published post
                    showToast("Bot execution completed", "info");
                }
            }
        } catch (e) {
            console.error("Error checking status:", e);
        }
    }

    function setUIStateRunning() {
        sidebarStatus.textContent = "Running";
        sidebarStatus.className = "status-badge running";
        statBotStatus.textContent = "Running";
        btnTrigger.disabled = true;
        btnTrigger.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Execution In Progress...';
    }

    function setUIStateIdle() {
        sidebarStatus.textContent = "Idle";
        sidebarStatus.className = "status-badge idle";
        statBotStatus.textContent = "Active";
        btnTrigger.disabled = false;
        btnTrigger.innerHTML = '<i class="fa-solid fa-paper-plane"></i> Trigger Bot Run Now';
    }

    // Trigger Bot Execution
    btnTrigger.addEventListener("click", async () => {
        const selectedTopic = topicSelect.value;
        
        terminalBody.innerHTML = "";
        lastLogContent = "";
        appendTerminalLine("[System] Dispatching trigger to execution thread...", "info");
        
        try {
            const resp = await fetch("/api/run", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ topic: selectedTopic })
            });
            const data = await resp.json();
            
            if (resp.ok) {
                showToast("Bot execution started successfully", "success");
                setUIStateRunning();
                
                // Immediately start polling logs
                isPollingLogs = true;
                logPollInterval = setInterval(pollLogs, 1000);
            } else {
                showToast(`Trigger failed: ${data.error}`, "error");
                appendTerminalLine(`[Error] ${data.error}`, "error");
            }
        } catch (e) {
            showToast("Network error triggering execution", "error");
            appendTerminalLine("[Error] Network request failed.", "error");
        }
    });

    btnClearTerminal.addEventListener("click", () => {
        terminalBody.innerHTML = '<span class="log-info">[System] Console cleared.</span>';
    });

    // 6. Initial Load Setup
    loadHistory();
    loadConfig();
    
    // Status polling loop (runs every 3 seconds to update states)
    setInterval(checkBotStatus, 3000);
    // Do an immediate status check on load
    checkBotStatus();
});
