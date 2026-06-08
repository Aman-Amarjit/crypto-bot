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
    
    // Poster Control Elements
    const topicSelect = document.getElementById("run-topic-select");
    const btnTriggerPost = document.getElementById("btn-trigger-post");
    const btnClearTerminal = document.getElementById("btn-clear-terminal");
    const terminalBody = document.getElementById("terminal-body");
    
    // Comment Control Elements
    const btnTriggerReplies = document.getElementById("btn-trigger-replies");
    const commentsTimeline = document.getElementById("comments-timeline");
    const statRepliesSuccess = document.getElementById("stat-replies-success");
    const statRepliesSkipped = document.getElementById("stat-replies-skipped");
    const statRepliesFailed = document.getElementById("stat-replies-failed");
    const statRepliesRate = document.getElementById("stat-replies-rate");

    // History & Config Elements
    const historyGrid = document.getElementById("history-grid");
    const configForm = document.getElementById("config-form");
    const toastContainer = document.getElementById("toast-container");
    
    let isPollingLogs = false;
    let logPollInterval = null;
    let lastLogContent = "";
    
    let isPosterRunning = false;
    let isRepliesRunning = false;

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
                loadHistory(); 
            } else if (sectionId === "comments") {
                sectionTitle.textContent = "Comment Auto-Replies";
                sectionSubtitle.textContent = "Manage replies, view interaction timelines, and audit logs";
                loadRepliesHistory();
            } else if (sectionId === "config") {
                sectionTitle.textContent = "Configuration Manager";
                sectionSubtitle.textContent = "Manage API credentials and system configurations securely";
                loadConfig(); 
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

    // 4. Load Comment Replies History
    async function loadRepliesHistory() {
        try {
            const resp = await fetch("/api/replies/history");
            const data = await resp.json();
            
            if (data.error) {
                showToast(`Failed to load comment history: ${data.error}`, "error");
                return;
            }
            
            // Calculate stats
            let successCount = 0;
            let skippedCount = 0;
            let failedCount = 0;
            let last24HoursCount = 0;
            const now = new Date();
            
            data.forEach(r => {
                if (r.status === 'success') successCount++;
                if (r.status === 'skipped') skippedCount++;
                if (r.status === 'failed') failedCount++;
                
                // Count rolling 24 hour success rate
                const stamp = new Date(r.timestamp);
                if (r.status === 'success' && (now - stamp) < 24 * 60 * 60 * 1000) {
                    last24HoursCount++;
                }
            });
            
            statRepliesSuccess.textContent = successCount;
            statRepliesSkipped.textContent = skippedCount;
            statRepliesFailed.textContent = failedCount;
            statRepliesRate.textContent = `${last24HoursCount} / 20`;
            
            if (data.length > 0) {
                commentsTimeline.innerHTML = "";
                data.forEach(reply => {
                    const row = document.createElement("div");
                    row.className = `timeline-item ${reply.status}`;
                    
                    const stamp = new Date(reply.timestamp).toLocaleString();
                    let replySection = "";
                    if (reply.status === 'success' && reply.reply_text) {
                        replySection = `
                            <div class="timeline-reply">
                                <span class="reply-header"><i class="fa-solid fa-robot"></i> Gemini Generated Response</span>
                                <p class="reply-text">"${reply.reply_text}"</p>
                            </div>
                        `;
                    } else if (reply.status === 'skipped') {
                        replySection = `
                            <div class="timeline-reply skipped">
                                <span class="reply-header"><i class="fa-solid fa-ban"></i> Silently Skipped (ToS Spacing Roll)</span>
                            </div>
                        `;
                    } else if (reply.status === 'failed') {
                        replySection = `
                            <div class="timeline-reply failed">
                                <span class="reply-header"><i class="fa-solid fa-circle-exclamation"></i> Execution Failed</span>
                            </div>
                        `;
                    } else if (reply.status === 'pending') {
                        replySection = `
                            <div class="timeline-reply pending">
                                <span class="reply-header"><i class="fa-solid fa-spinner fa-spin"></i> Processing / Reserved...</span>
                            </div>
                        `;
                    }
                    
                    row.innerHTML = `
                        <div class="timeline-badge"></div>
                        <div class="timeline-content">
                            <div class="timeline-header-info">
                                <span class="timeline-user"><i class="fa-solid fa-user"></i> @${reply.commenter_username || 'unknown'}</span>
                                <span class="timeline-time"><i class="fa-regular fa-clock"></i> ${stamp}</span>
                            </div>
                            <p class="timeline-comment">"${reply.comment_text || 'No comment text retrieved.'}"</p>
                            ${replySection}
                            <div class="timeline-footer">
                                <span class="post-context-id">Post ID: ${reply.post_id || 'unknown'}</span>
                                <a href="https://www.threads.net/post/${reply.post_id}" target="_blank" class="timeline-link">
                                    <i class="fa-brands fa-threads"></i> View Thread
                                </a>
                            </div>
                        </div>
                    `;
                    commentsTimeline.appendChild(row);
                });
            } else {
                commentsTimeline.innerHTML = `
                    <div class="no-history">
                        <i class="fa-solid fa-comment-slash"></i>
                        <p>No comment interactions logged yet.</p>
                    </div>
                `;
            }
        } catch (e) {
            console.error("Error loading comment replies:", e);
        }
    }

    // 5. Load Config Settings
    async function loadConfig() {
        try {
            const resp = await fetch("/api/config");
            const data = await resp.json();
            
            document.getElementById("conf-gemini-key").value = data.GEMINI_API_KEY || "";
            document.getElementById("conf-groq-key").value = data.GROQ_API_KEY || "";
            document.getElementById("conf-pollinations-key").value = data.POLLINATIONS_API_KEY || "";
            document.getElementById("conf-gh-pat").value = data.GH_PAT || "";
            
            document.getElementById("conf-cloudinary-name").value = data.CLOUDINARY_CLOUD_NAME || "";
            document.getElementById("conf-cloudinary-key").value = data.CLOUDINARY_API_KEY || "";
            document.getElementById("conf-cloudinary-secret").value = data.CLOUDINARY_API_SECRET || "";
            
            document.getElementById("conf-threads-user-id").value = data.THREADS_USER_ID || "";
            document.getElementById("conf-threads-token").value = data.THREADS_ACCESS_TOKEN || "";
            
            document.getElementById("conf-automation-paused").checked = data.AUTOMATION_PAUSED === "1";
        } catch (e) {
            showToast("Failed to load configuration", "error");
        }
    }

    // Save Config Settings
    configForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        
        const payload = {
            GEMINI_API_KEY: document.getElementById("conf-gemini-key").value,
            GROQ_API_KEY: document.getElementById("conf-groq-key").value,
            POLLINATIONS_API_KEY: document.getElementById("conf-pollinations-key").value,
            GH_PAT: document.getElementById("conf-gh-pat").value,
            CLOUDINARY_CLOUD_NAME: document.getElementById("conf-cloudinary-name").value,
            CLOUDINARY_API_KEY: document.getElementById("conf-cloudinary-key").value,
            CLOUDINARY_API_SECRET: document.getElementById("conf-cloudinary-secret").value,
            THREADS_USER_ID: document.getElementById("conf-threads-user-id").value,
            THREADS_ACCESS_TOKEN: document.getElementById("conf-threads-token").value,
            AUTOMATION_PAUSED: document.getElementById("conf-automation-paused").checked ? "1" : "0"
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

    // 6. Terminal Console Logging
    function appendTerminalLine(text, type = "info") {
        const line = document.createElement("div");
        line.className = `log-line log-${type}`;
        line.textContent = text;
        terminalBody.appendChild(line);
        terminalBody.scrollTop = terminalBody.scrollHeight;
    }

    function formatAndPrintLogs(rawLogs) {
        if (rawLogs === lastLogContent) return;
        
        const newPart = rawLogs.slice(lastLogContent.length);
        lastLogContent = rawLogs;
        
        if (!newPart.trim()) return;
        
        const lines = newPart.split("\n");
        lines.forEach(line => {
            if (!line.trim()) return;
            
            let type = "info";
            if (line.includes("Failed") || line.includes("Error:") || line.includes("Traceback") || line.includes("Exception") || line.includes("🛑") || line.includes("❌")) {
                type = "error";
            } else if (line.includes("Completed Successfully") || line.includes("successful") || line.includes("Success!") || line.includes("Successful")) {
                type = "success";
            } else if (line.includes("Warning:") || line.includes("⏳") || line.includes("🎲")) {
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

    // 7. Status Polling Loop
    async function checkBotStatus() {
        // A. Check Post Runner Status
        try {
            const resp = await fetch("/api/status");
            const data = await resp.json();
            isPosterRunning = data.running;
            
            if (isPosterRunning) {
                setPosterUIStateRunning();
                if (!isPollingLogs) {
                    isPollingLogs = true;
                    logPollInterval = setInterval(pollLogs, 1000);
                }
            } else {
                setPosterUIStateIdle();
                // If both are idle, clear polling
                if (!isRepliesRunning && isPollingLogs) {
                    isPollingLogs = false;
                    clearInterval(logPollInterval);
                    pollLogs(); 
                    loadHistory(); 
                    showToast("Bot execution completed", "info");
                }
            }
        } catch (e) {
            console.error("Error checking poster status:", e);
        }

        // B. Check Reply Runner Status
        try {
            const resp = await fetch("/api/replies/status");
            const data = await resp.json();
            isRepliesRunning = data.running;
            
            if (isRepliesRunning) {
                setRepliesUIStateRunning();
                if (!isPollingLogs) {
                    isPollingLogs = true;
                    logPollInterval = setInterval(pollLogs, 1000);
                }
            } else {
                setRepliesUIStateIdle();
                if (!isPosterRunning && isPollingLogs) {
                    isPollingLogs = false;
                    clearInterval(logPollInterval);
                    pollLogs(); 
                    loadRepliesHistory(); 
                    showToast("Replies check execution completed", "info");
                }
            }
        } catch (e) {
            console.error("Error checking replies status:", e);
        }

        // C. Update Sidebar Status Badge
        if (isPosterRunning && isRepliesRunning) {
            sidebarStatus.textContent = "Busy (Post & Reply)";
            sidebarStatus.className = "status-badge active-both";
        } else if (isPosterRunning) {
            sidebarStatus.textContent = "Running Poster";
            sidebarStatus.className = "status-badge running";
        } else if (isRepliesRunning) {
            sidebarStatus.textContent = "Checking Replies";
            sidebarStatus.className = "status-badge replying";
        } else {
            sidebarStatus.textContent = "Idle";
            sidebarStatus.className = "status-badge idle";
        }
    }

    function setPosterUIStateRunning() {
        statBotStatus.textContent = "Running Poster";
        btnTriggerPost.disabled = true;
        btnTriggerPost.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Poster In Progress...';
    }

    function setPosterUIStateIdle() {
        statBotStatus.textContent = "Active";
        btnTriggerPost.disabled = false;
        btnTriggerPost.innerHTML = '<i class="fa-solid fa-paper-plane"></i> Trigger Bot Run Now';
    }

    function setRepliesUIStateRunning() {
        btnTriggerReplies.disabled = true;
        btnTriggerReplies.className = "btn btn-secondary btn-block loading";
        btnTriggerReplies.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Replying In Progress...';
    }

    function setRepliesUIStateIdle() {
        btnTriggerReplies.disabled = false;
        btnTriggerReplies.className = "btn btn-secondary btn-block";
        btnTriggerReplies.innerHTML = '<i class="fa-solid fa-magnifying-glass"></i> Check & Reply Now';
    }

    // 8. Action Event Listeners
    btnTriggerPost.addEventListener("click", async () => {
        const selectedTopic = topicSelect.value;
        
        terminalBody.innerHTML = "";
        lastLogContent = "";
        appendTerminalLine("[System] Dispatching poster trigger to thread...", "info");
        
        try {
            const resp = await fetch("/api/run", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ topic: selectedTopic })
            });
            const data = await resp.json();
            
            if (resp.ok) {
                showToast("Bot poster execution started successfully", "success");
                setPosterUIStateRunning();
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

    btnTriggerReplies.addEventListener("click", async () => {
        terminalBody.innerHTML = "";
        lastLogContent = "";
        appendTerminalLine("[System] Dispatching replies check trigger to thread...", "info");
        
        try {
            const resp = await fetch("/api/replies/run", {
                method: "POST",
                headers: { "Content-Type": "application/json" }
            });
            const data = await resp.json();
            
            if (resp.ok) {
                showToast("Comments reply checker started successfully", "success");
                setRepliesUIStateRunning();
                isPollingLogs = true;
                logPollInterval = setInterval(pollLogs, 1000);
            } else {
                showToast(`Replies trigger failed: ${data.error}`, "error");
                appendTerminalLine(`[Error] ${data.error}`, "error");
            }
        } catch (e) {
            showToast("Network error triggering replies", "error");
            appendTerminalLine("[Error] Network request failed.", "error");
        }
    });

    btnClearTerminal.addEventListener("click", () => {
        terminalBody.innerHTML = '<span class="log-info">[System] Console cleared.</span>';
    });

    // 9. Initial Load Setup
    loadHistory();
    loadRepliesHistory();
    loadConfig();
    
    // Status polling loop (runs every 3 seconds to update states)
    setInterval(checkBotStatus, 3000);
    checkBotStatus();
});
