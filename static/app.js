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
    
    // Thoughts Control Elements
    const btnTriggerThought = document.getElementById("btn-trigger-thought");
    const thoughtsTimeline = document.getElementById("thoughts-timeline");
    const btnSyncGithub = document.getElementById("btn-sync-github");

    // Questions Control Elements
    const btnTriggerQuestion = document.getElementById("btn-trigger-question");
    const questionsTimeline = document.getElementById("questions-timeline");
    
    let isPollingLogs = false;
    let logPollInterval = null;
    let lastLogContent = "";
    
    let isPosterRunning = false;
    let isRepliesRunning = false;
    let isThoughtsRunning = false;
    let isQuestionsRunning = false;

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
            } else if (sectionId === "thoughts") {
                sectionTitle.textContent = "Daily Thoughts Log";
                sectionSubtitle.textContent = "View text-only thoughts and developer reflections posted to Threads";
                loadThoughtsHistory();
            } else if (sectionId === "questions") {
                sectionTitle.textContent = "Daily Questions Log";
                sectionSubtitle.textContent = "Browse and view history of all cybersecurity and developer questions";
                loadQuestionsHistory();
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
                    
                    const isExt = reply.is_external === 1;
                    const badgeHtml = isExt ? ` <span class="badge" style="background: rgba(100, 108, 255, 0.2); color: var(--primary); border: 1px solid rgba(100, 108, 255, 0.4); font-size: 10px; font-weight: 600; padding: 1px 6px; border-radius: 4px; margin-left: 6px; display: inline-block; vertical-align: middle;">External Reply</span>` : '';
                    const labelText = isExt ? 'Original Post Content' : 'User Comment';

                    row.innerHTML = `
                        <div class="timeline-badge"></div>
                        <div class="timeline-content">
                            <div class="timeline-header-info">
                                <span class="timeline-user"><i class="fa-solid fa-user"></i> @${reply.commenter_username || 'unknown'}${badgeHtml}</span>
                                <span class="timeline-time"><i class="fa-regular fa-clock"></i> ${stamp}</span>
                            </div>
                            <p class="timeline-comment"><strong>${labelText}:</strong> "${reply.comment_text || 'No text retrieved.'}"</p>
                            ${replySection}
                            <div class="timeline-footer">
                                <span class="post-context-id">${isExt ? 'Target Media' : 'Post'} ID: ${reply.post_id || 'unknown'}</span>
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

    // 4b. Load Daily Thoughts History
    async function loadThoughtsHistory() {
        try {
            const resp = await fetch("/api/thoughts/history");
            const data = await resp.json();
            
            if (data.error) {
                showToast(`Failed to load thoughts: ${data.error}`, "error");
                return;
            }
            
            if (data.length > 0) {
                thoughtsTimeline.innerHTML = "";
                data.slice().reverse().forEach(thought => {
                    const row = document.createElement("div");
                    row.className = "timeline-item success";
                    
                    const stamp = new Date(thought.timestamp).toLocaleString();
                    
                    row.innerHTML = `
                        <div class="timeline-badge"></div>
                        <div class="timeline-content">
                            <div class="timeline-header-info">
                                <span class="timeline-user"><i class="fa-solid fa-quote-left"></i> Developer Thought</span>
                                <span class="timeline-time"><i class="fa-regular fa-clock"></i> ${stamp}</span>
                            </div>
                            <p class="timeline-comment" style="font-size: 1.05rem; line-height: 1.5; color: var(--text-primary);">
                                "${thought.thought}"
                            </p>
                            <div class="timeline-footer">
                                <span class="post-context-id">Post ID: ${thought.post_id || 'unknown'}</span>
                                <a href="https://www.threads.net/post/${thought.post_id}" target="_blank" class="timeline-link">
                                    <i class="fa-brands fa-threads"></i> View on Threads
                                </a>
                            </div>
                        </div>
                    `;
                    thoughtsTimeline.appendChild(row);
                });
            } else {
                thoughtsTimeline.innerHTML = `
                    <div class="no-history">
                        <i class="fa-solid fa-comment-slash"></i>
                        <p>No daily thoughts posted yet.</p>
                    </div>
                `;
            }
        } catch (e) {
            console.error("Error loading thoughts history:", e);
        }
    }

    // 4c. Load Daily Questions History
    async function loadQuestionsHistory() {
        try {
            const resp = await fetch("/api/questions/history");
            const data = await resp.json();
            
            if (data.error) {
                showToast(`Failed to load questions: ${data.error}`, "error");
                return;
            }
            
            if (data.length > 0) {
                questionsTimeline.innerHTML = "";
                data.slice().reverse().forEach(q => {
                    const row = document.createElement("div");
                    row.className = "timeline-item success";
                    
                    const stamp = new Date(q.timestamp).toLocaleString();
                    
                    row.innerHTML = `
                        <div class="timeline-badge"></div>
                        <div class="timeline-content">
                            <div class="timeline-header-info">
                                <span class="timeline-user"><i class="fa-solid fa-circle-question"></i> Question of the Day</span>
                                <span class="timeline-time"><i class="fa-regular fa-clock"></i> ${stamp}</span>
                            </div>
                            <p class="timeline-comment" style="font-size: 1.05rem; line-height: 1.5; color: var(--text-primary);">
                                "${q.question}"
                            </p>
                            <div class="timeline-footer">
                                <span class="post-context-id">Post ID: ${q.post_id || 'unknown'}</span>
                                <a href="https://www.threads.net/post/${q.post_id}" target="_blank" class="timeline-link">
                                    <i class="fa-brands fa-threads"></i> View on Threads
                                </a>
                            </div>
                        </div>
                    `;
                    questionsTimeline.appendChild(row);
                });
            } else {
                questionsTimeline.innerHTML = `
                    <div class="no-history">
                        <i class="fa-solid fa-comment-slash"></i>
                        <p>No daily questions posted yet.</p>
                    </div>
                `;
            }
        } catch (e) {
            console.error("Error loading questions history:", e);
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
            document.getElementById("conf-hf-token").value = data.HF_API_TOKEN || "";
            document.getElementById("conf-gh-pat").value = data.GH_PAT || "";
            
            document.getElementById("conf-cloudflare-token").value = data.CLOUDFLARE_API_TOKEN || "";
            document.getElementById("conf-cloudflare-account-id").value = data.CLOUDFLARE_ACCOUNT_ID || "";
            
            document.getElementById("conf-cloudinary-name").value = data.CLOUDINARY_CLOUD_NAME || "";
            document.getElementById("conf-cloudinary-key").value = data.CLOUDINARY_API_KEY || "";
            document.getElementById("conf-cloudinary-secret").value = data.CLOUDINARY_API_SECRET || "";
            
            document.getElementById("conf-threads-user-id").value = data.THREADS_USER_ID || "";
            document.getElementById("conf-threads-token").value = data.THREADS_ACCESS_TOKEN || "";
            
            document.getElementById("conf-persona-name").value = data.PERSONA_NAME || "";
            document.getElementById("conf-persona-bio").value = data.PERSONA_BIO || "";
            document.getElementById("conf-persona-tone").value = data.PERSONA_TONE || "";
            
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
            HF_API_TOKEN: document.getElementById("conf-hf-token").value,
            GH_PAT: document.getElementById("conf-gh-pat").value,
            CLOUDFLARE_API_TOKEN: document.getElementById("conf-cloudflare-token").value,
            CLOUDFLARE_ACCOUNT_ID: document.getElementById("conf-cloudflare-account-id").value,
            CLOUDINARY_CLOUD_NAME: document.getElementById("conf-cloudinary-name").value,
            CLOUDINARY_API_KEY: document.getElementById("conf-cloudinary-key").value,
            CLOUDINARY_API_SECRET: document.getElementById("conf-cloudinary-secret").value,
            THREADS_USER_ID: document.getElementById("conf-threads-user-id").value,
            THREADS_ACCESS_TOKEN: document.getElementById("conf-threads-token").value,
            PERSONA_NAME: document.getElementById("conf-persona-name").value,
            PERSONA_BIO: document.getElementById("conf-persona-bio").value,
            PERSONA_TONE: document.getElementById("conf-persona-tone").value,
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
                // If all are idle, clear polling
                if (!isRepliesRunning && !isThoughtsRunning && !isQuestionsRunning && isPollingLogs) {
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
                if (!isPosterRunning && !isThoughtsRunning && !isQuestionsRunning && isPollingLogs) {
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

        // C. Check Thought Runner Status
        try {
            const resp = await fetch("/api/thoughts/status");
            const data = await resp.json();
            isThoughtsRunning = data.running;
            
            if (isThoughtsRunning) {
                setThoughtsUIStateRunning();
                if (!isPollingLogs) {
                    isPollingLogs = true;
                    logPollInterval = setInterval(pollLogs, 1000);
                }
            } else {
                setThoughtsUIStateIdle();
                if (!isPosterRunning && !isRepliesRunning && !isQuestionsRunning && isPollingLogs) {
                    isPollingLogs = false;
                    clearInterval(logPollInterval);
                    pollLogs(); 
                    loadThoughtsHistory(); 
                    showToast("Daily thought execution completed", "info");
                }
            }
        } catch (e) {
            console.error("Error checking thoughts status:", e);
        }

        // D. Check Question Runner Status
        try {
            const resp = await fetch("/api/questions/status");
            const data = await resp.json();
            isQuestionsRunning = data.running;
            
            if (isQuestionsRunning) {
                setQuestionsUIStateRunning();
                if (!isPollingLogs) {
                    isPollingLogs = true;
                    logPollInterval = setInterval(pollLogs, 1000);
                }
            } else {
                setQuestionsUIStateIdle();
                if (!isPosterRunning && !isRepliesRunning && !isThoughtsRunning && isPollingLogs) {
                    isPollingLogs = false;
                    clearInterval(logPollInterval);
                    pollLogs(); 
                    loadQuestionsHistory(); 
                    showToast("Daily question execution completed", "info");
                }
            }
        } catch (e) {
            console.error("Error checking questions status:", e);
        }

        // E. Update Sidebar Status Badge
        const activeRunners = [];
        if (isPosterRunning) activeRunners.push("Poster");
        if (isRepliesRunning) activeRunners.push("Replies");
        if (isThoughtsRunning) activeRunners.push("Thoughts");
        if (isQuestionsRunning) activeRunners.push("Questions");

        if (activeRunners.length > 0) {
            sidebarStatus.textContent = `Running ${activeRunners.join(" & ")}`;
            sidebarStatus.className = `status-badge running`;
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

    function setThoughtsUIStateRunning() {
        btnTriggerThought.disabled = true;
        btnTriggerThought.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Thought In Progress...';
    }

    function setThoughtsUIStateIdle() {
        btnTriggerThought.disabled = false;
        btnTriggerThought.innerHTML = '<i class="fa-solid fa-paper-plane"></i> Post Today\'s Thought Now';
    }

    function setQuestionsUIStateRunning() {
        btnTriggerQuestion.disabled = true;
        btnTriggerQuestion.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Question In Progress...';
    }

    function setQuestionsUIStateIdle() {
        btnTriggerQuestion.disabled = false;
        btnTriggerQuestion.innerHTML = '<i class="fa-solid fa-paper-plane"></i> Post Today\'s Question Now';
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

    btnTriggerThought.addEventListener("click", async () => {
        terminalBody.innerHTML = "";
        lastLogContent = "";
        appendTerminalLine("[System] Dispatching thought trigger to thread...", "info");
        
        try {
            const resp = await fetch("/api/thoughts/run", {
                method: "POST",
                headers: { "Content-Type": "application/json" }
            });
            const data = await resp.json();
            
            if (resp.ok) {
                showToast("Daily thought post started successfully", "success");
                setThoughtsUIStateRunning();
                isPollingLogs = true;
                logPollInterval = setInterval(pollLogs, 1000);
            } else {
                showToast(`Thought trigger failed: ${data.error}`, "error");
                appendTerminalLine(`[Error] ${data.error}`, "error");
            }
        } catch (e) {
            showToast("Network error triggering thought execution", "error");
            appendTerminalLine("[Error] Network request failed.", "error");
        }
    });

    btnTriggerQuestion.addEventListener("click", async () => {
        terminalBody.innerHTML = "";
        lastLogContent = "";
        appendTerminalLine("[System] Dispatching question trigger to thread...", "info");
        
        try {
            const resp = await fetch("/api/questions/run", {
                method: "POST",
                headers: { "Content-Type": "application/json" }
            });
            const data = await resp.json();
            
            if (resp.ok) {
                showToast("Daily question post started successfully", "success");
                setQuestionsUIStateRunning();
                isPollingLogs = true;
                logPollInterval = setInterval(pollLogs, 1000);
            } else {
                showToast(`Question trigger failed: ${data.error}`, "error");
                appendTerminalLine(`[Error] ${data.error}`, "error");
            }
        } catch (e) {
            showToast("Network error triggering question execution", "error");
            appendTerminalLine("[Error] Network request failed.", "error");
        }
    });

    btnSyncGithub.addEventListener("click", async () => {
        btnSyncGithub.disabled = true;
        btnSyncGithub.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Syncing...';
        
        try {
            const resp = await fetch("/api/sync", {
                method: "POST"
            });
            const data = await resp.json();
            
            if (resp.ok) {
                showToast("Dashboard synchronized with GitHub successfully!", "success");
                loadHistory();
                loadRepliesHistory();
                loadThoughtsHistory();
                loadQuestionsHistory();
            } else {
                showToast(`Sync failed: ${data.error}`, "error");
            }
        } catch (e) {
            showToast("Network error synchronizing with GitHub", "error");
        } finally {
            btnSyncGithub.disabled = false;
            btnSyncGithub.innerHTML = '<i class="fa-solid fa-rotate"></i> Sync with GitHub';
        }
    });

    // 8b. External Post Reply Logic
    const extPostUrlInput = document.getElementById("ext-post-url");
    const extMediaIdGroup = document.getElementById("ext-media-id-group");
    const extMediaIdInput = document.getElementById("ext-media-id");
    const extPostTextInput = document.getElementById("ext-post-text");
    const extPostTextCharCount = document.getElementById("ext-post-text-char-count");
    const extPreviewStatus = document.getElementById("ext-preview-status");
    const btnTriggerExternalReply = document.getElementById("btn-trigger-external-reply");

    let previewDebounceTimeout = null;
    let resolvedUsername = "";

    function validateExternalForm() {
        const hasUrlOrId = extPostUrlInput.value.trim().length > 0 || extMediaIdInput.value.trim().length > 0;
        const hasText = extPostTextInput.value.trim().length > 0;
        btnTriggerExternalReply.disabled = !(hasUrlOrId && hasText);
    }

    // Debounced URL Preview Resolution
    function handleUrlChange() {
        clearTimeout(previewDebounceTimeout);
        
        const url = extPostUrlInput.value.trim();
        const mediaIdOverride = extMediaIdInput.value.trim();

        if (!url && !mediaIdOverride) {
            extPreviewStatus.style.display = "none";
            extPreviewStatus.innerHTML = "";
            resolvedUsername = "";
            validateExternalForm();
            return;
        }

        // Wait 800ms after typing stops before querying preview
        previewDebounceTimeout = setTimeout(async () => {
            extPreviewStatus.style.display = "block";
            extPreviewStatus.className = "timeline-reply pending";
            extPreviewStatus.innerHTML = `
                <span class="reply-header"><i class="fa-solid fa-spinner fa-spin"></i> Resolving Threads URL & verifying visibility...</span>
            `;

            try {
                const queryParams = new URLSearchParams();
                if (url) queryParams.append("url", url);
                if (mediaIdOverride) queryParams.append("media_id", mediaIdOverride);

                const resp = await fetch(`/api/replies/external/preview?${queryParams.toString()}`);
                const data = await resp.json();

                if (resp.ok && data.accessible) {
                    extPreviewStatus.className = "timeline-reply success";
                    extPreviewStatus.innerHTML = `
                        <span class="reply-header" style="color: var(--success);"><i class="fa-solid fa-circle-check"></i> Post Verification Successful</span>
                        <div style="margin-top: 8px; font-size: 13px; color: var(--text-secondary);">
                            <div><strong>Resolved ID:</strong> ${data.resolved_id}</div>
                            <div><strong>Author:</strong> @${data.username}</div>
                            <div style="margin-top: 4px; font-style: italic; color: var(--text-muted);">"${data.text || '[No text content]'}"</div>
                        </div>
                    `;
                    
                    // Auto-fill inputs if empty
                    if (!extMediaIdInput.value.trim()) {
                        extMediaIdInput.value = data.resolved_id;
                    }
                    if (!extPostTextInput.value.trim() && data.text) {
                        extPostTextInput.value = data.text;
                        extPostTextCharCount.textContent = `${data.text.length} characters`;
                    }
                    extMediaIdGroup.style.display = "block"; // Show the group so they can see resolved ID
                    resolvedUsername = data.username;
                } else {
                    extPreviewStatus.className = "timeline-reply failed";
                    const errorMsg = data.error || "Failed to fetch post metadata.";
                    extPreviewStatus.innerHTML = `
                        <span class="reply-header" style="color: var(--danger);"><i class="fa-solid fa-triangle-exclamation"></i> Verification Failed</span>
                        <div style="margin-top: 4px; font-size: 12px; color: var(--text-muted);">${errorMsg}</div>
                    `;
                    // If resolution failed, show media ID override input group
                    extMediaIdGroup.style.display = "block";
                }
            } catch (err) {
                extPreviewStatus.className = "timeline-reply failed";
                extPreviewStatus.innerHTML = `
                    <span class="reply-header" style="color: var(--danger);"><i class="fa-solid fa-circle-xmark"></i> Network Error</span>
                    <div style="margin-top: 4px; font-size: 12px; color: var(--text-muted);">${err.message}</div>
                `;
                extMediaIdGroup.style.display = "block";
            } finally {
                validateExternalForm();
            }
        }, 800);
    }

    extPostUrlInput.addEventListener("input", handleUrlChange);
    extMediaIdInput.addEventListener("input", handleUrlChange);

    // Textarea input char count and validation
    extPostTextInput.addEventListener("input", () => {
        const len = extPostTextInput.value.length;
        extPostTextCharCount.textContent = `${len} characters`;
        validateExternalForm();
    });

    // Trigger External Reply POST
    btnTriggerExternalReply.addEventListener("click", async () => {
        const url = extPostUrlInput.value.trim();
        const mediaId = extMediaIdInput.value.trim();
        const postText = extPostTextInput.value.trim();

        // 1. Show loading state in button
        btnTriggerExternalReply.disabled = true;
        btnTriggerExternalReply.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Simulating Typing & Publishing...`;
        
        extPostUrlInput.disabled = true;
        extMediaIdInput.disabled = true;
        extPostTextInput.disabled = true;

        appendTerminalLine("[System] Starting manual external reply generation sequence...", "info");
        appendTerminalLine(`[System] Jitter typing delay of 10-30 seconds active...`, "warning");

        try {
            const resp = await fetch("/api/replies/external", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    url: url,
                    media_id: mediaId,
                    post_text: postText,
                    author_username: resolvedUsername || "creator"
                })
            });
            const data = await resp.json();

            if (resp.ok) {
                showToast("External post reply published successfully!", "success");
                appendTerminalLine(`[Success] Reply published! Post ID: ${data.media_id}, Reply Thread ID: ${data.thread_id}`, "success");
                appendTerminalLine(`[Gemini Reply] "${data.reply_text}"`, "info");
                
                // Clear fields
                extPostUrlInput.value = "";
                extMediaIdInput.value = "";
                extPostTextInput.value = "";
                extPostTextCharCount.textContent = "0 characters";
                extPreviewStatus.style.display = "none";
                extPreviewStatus.innerHTML = "";
                extMediaIdGroup.style.display = "none";
                resolvedUsername = "";
                
                // Reload replies history
                loadRepliesHistory();
            } else {
                showToast(`Failed to post reply: ${data.error}`, "error");
                appendTerminalLine(`[Error] ${data.error}`, "error");
            }
        } catch (err) {
            showToast(`Network error posting reply: ${err.message}`, "error");
            appendTerminalLine(`[Error] Network error during fetch: ${err.message}`, "error");
        } finally {
            // Restore input states
            extPostUrlInput.disabled = false;
            extMediaIdInput.disabled = false;
            extPostTextInput.disabled = false;
            
            btnTriggerExternalReply.innerHTML = `<i class="fa-solid fa-reply"></i> Generate & Post Reply`;
            validateExternalForm();
        }
    });

    // 9. Initial Load Setup
    loadHistory();
    loadRepliesHistory();
    loadThoughtsHistory();
    loadQuestionsHistory();
    loadConfig();
    
    // Status polling loop (runs every 3 seconds to update states)
    setInterval(checkBotStatus, 3000);
    checkBotStatus();
});
