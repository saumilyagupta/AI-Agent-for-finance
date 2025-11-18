// Chat Interface JavaScript

let currentExecutionId = null;
let currentWebSocket = null;
let totalCost = 0;
let isProcessing = false;
let currentIterationContainer = null;
let currentIteration = 0;
let reasoningCharts = []; // Store charts from reasoning to show with final answer
let finalAnswerShown = false; // Flag to prevent duplicate final answers

// DOM Elements
const messagesContainer = document.getElementById('messagesContainer');
const messageInput = document.getElementById('messageInput');
const sendBtn = document.getElementById('sendBtn');
const statusText = document.getElementById('statusText');
const statusIndicator = document.getElementById('statusIndicator');
const costDisplay = document.getElementById('costDisplay');
const stopBtn = document.getElementById('stopBtn');
const newChatBtn = document.getElementById('newChatBtn');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    // Auto-resize textarea
    messageInput.addEventListener('input', autoResizeTextarea);
    
    // Send message on Enter (Shift+Enter for new line)
    messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
    
    // Send button click
    sendBtn.addEventListener('click', sendMessage);
    
    // New chat button
    newChatBtn.addEventListener('click', startNewChat);
    
    // Example prompts
    document.querySelectorAll('.example-prompt').forEach(btn => {
        btn.addEventListener('click', () => {
            messageInput.value = btn.dataset.prompt;
            messageInput.focus();
            autoResizeTextarea();
        });
    });
    
    // Stop button
    stopBtn.addEventListener('click', stopExecution);
});

function autoResizeTextarea() {
    messageInput.style.height = 'auto';
    messageInput.style.height = messageInput.scrollHeight + 'px';
}

function startNewChat() {
    // Clear messages
    messagesContainer.innerHTML = '';
    
    // Reset state
    currentExecutionId = null;
    totalCost = 0;
    isProcessing = false;
    currentIterationContainer = null;
    currentIteration = 0;
    reasoningCharts = [];
    finalAnswerShown = false;
    
    // Close WebSocket if open
    if (currentWebSocket) {
        currentWebSocket.close();
        currentWebSocket = null;
    }
    
    // Show welcome message
    showWelcomeMessage();
    
    // Update UI
    updateStatus('Ready', 'ready');
    costDisplay.textContent = 'Cost: $0.0000';
    stopBtn.style.display = 'none';
}

function showWelcomeMessage() {
    messagesContainer.innerHTML = `
        <div class="welcome-message">
            <div class="welcome-icon">🚀</div>
            <h2>Welcome to AI Agent Chat!</h2>
            <p>I'm an autonomous AI agent powered by MCP tools. I can help you with:</p>
            <ul class="capabilities-list">
                <li>🔍 Web research and information gathering</li>
                <li>🧮 Mathematical calculations and analysis</li>
                <li>📊 Stock market data and technical analysis</li>
                <li>📁 File operations and data processing</li>
                <li>💻 Code execution and automation</li>
                <li>📈 Data visualization</li>
                <li>🌐 API integration and web interactions</li>
            </ul>
            <p class="welcome-cta">What would you like me to help you with today?</p>
            
            <div class="example-prompts">
                <button class="example-prompt" data-prompt="Plot a graph of y = 2x + 10">
                    📈 Plot equation
                </button>
                <button class="example-prompt" data-prompt="Calculate 156 * 23 and explain the steps">
                    📝 Simple calculation
                </button>
                <button class="example-prompt" data-prompt="Get Apple stock data for the last month and analyze the trend">
                    📊 Stock analysis
                </button>
                <button class="example-prompt" data-prompt="Read the README.md file and summarize the project">
                    📁 File operations
                </button>
            </div>
        </div>
    `;
    
    // Re-attach event listeners to example prompts
    document.querySelectorAll('.example-prompt').forEach(btn => {
        btn.addEventListener('click', () => {
            messageInput.value = btn.dataset.prompt;
            messageInput.focus();
            autoResizeTextarea();
        });
    });
}

async function sendMessage() {
    const message = messageInput.value.trim();
    
    if (!message || isProcessing) return;
    
    // Clear welcome message if present
    const welcomeMsg = document.querySelector('.welcome-message');
    if (welcomeMsg) {
        welcomeMsg.remove();
    }
    
    // Add user message to chat
    addMessage('user', message);
    
    // Clear input
    messageInput.value = '';
    autoResizeTextarea();
    
    // Reset state for new execution
    currentIterationContainer = null;
    currentIteration = 0;
    reasoningCharts = [];
    finalAnswerShown = false;
    
    // Update UI state
    isProcessing = true;
    sendBtn.disabled = true;
    stopBtn.style.display = 'block';
    updateStatus('Processing...', 'thinking');
    
    try {
        // Create execution
        const response = await fetch('/api/v1/goals', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ goal: message }),
        });
        
        if (!response.ok) throw new Error('Failed to create execution');
        
        const data = await response.json();
        currentExecutionId = data.execution_id;
        
        // Connect WebSocket for streaming
        connectWebSocket(currentExecutionId);
        
    } catch (error) {
        console.error('Error:', error);
        addMessage('system', `Error: ${error.message}`);
        updateStatus('Error', 'error');
        isProcessing = false;
        sendBtn.disabled = false;
        stopBtn.style.display = 'none';
    }
}

function connectWebSocket(executionId) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/execute/${executionId}`;
    
    currentWebSocket = new WebSocket(wsUrl);
    let lastMessageDiv = null;
    
    currentWebSocket.onopen = () => {
        console.log('WebSocket connected');
        updateStatus('Connected', 'thinking');
        
        // Show thinking indicator
        lastMessageDiv = addThinkingIndicator();
        
        // Add initial message
        addMessage('system', '🚀 Agent is starting up and loading tools...');
    };
    
    currentWebSocket.onmessage = (event) => {
        try {
            const eventData = JSON.parse(event.data);
            handleExecutionEvent(eventData, lastMessageDiv);
            
        } catch (e) {
            console.error('Failed to parse WebSocket message:', e);
        }
    };
    
    currentWebSocket.onerror = (error) => {
        console.error('WebSocket error:', error);
        updateStatus('Error', 'error');
        removeThinkingIndicator(lastMessageDiv);
    };
    
    currentWebSocket.onclose = () => {
        console.log('WebSocket closed');
        currentWebSocket = null;
        isProcessing = false;
        sendBtn.disabled = false;
        stopBtn.style.display = 'none';
        removeThinkingIndicator(lastMessageDiv);
    };
}

function handleExecutionEvent(event, thinkingDiv) {
    console.log('Event:', event.type, event);
    
    switch (event.type) {
        case 'system_info':
            removeThinkingIndicator(thinkingDiv);
            addMessage('system', `ℹ️ ${event.message}`);
            // Show thinking again after system info
            thinkingDiv = addThinkingIndicator();
            break;
            
        case 'iteration_started':
            const iteration = event.data?.iteration || 0;
            currentIteration = iteration;
            updateStatus(`Thinking (Step ${iteration})...`, 'thinking');
            removeThinkingIndicator(thinkingDiv);
            
            // Create or update iteration container
            if (!currentIterationContainer) {
                currentIterationContainer = createIterationContainer(iteration);
            } else {
                updateIterationContainer(iteration);
            }
            
            thinkingDiv = addThinkingIndicator();
            break;
            
        case 'model_thinking':
            removeThinkingIndicator(thinkingDiv);
            const thinking = event.data?.content || event.message;
            // Don't show thinking if it contains "FINAL ANSWER" - wait for final_answer event
            // Also filter out any final answer text that might appear
            const cleanThinking = thinking.replace(/FINAL ANSWER:\s*/gi, '').trim();
            if (cleanThinking && !thinking.toUpperCase().includes('FINAL ANSWER')) {
                addMessage('assistant', `💭 ${cleanThinking}`);
            }
            break;
            
        case 'tool_call_initiated':
            removeThinkingIndicator(thinkingDiv);
            const tool = event.data?.tool || 'unknown';
            const args = event.data?.arguments || {};
            addToolCall(tool, args);
            updateStatus(`Using ${tool}...`, 'thinking');
            break;
            
        case 'tool_result_received':
            const result = event.data?.result || {};
            const success = result.success !== false;
            const chartInfo = addToolResult(result, success);
            
            // Store chart if it's a visualization
            if (chartInfo && chartInfo.isChart) {
                reasoningCharts.push(chartInfo);
            }
            break;
            
        case 'model_response':
            const cost = event.data?.cost || 0;
            totalCost += cost;
            costDisplay.textContent = `Cost: $${totalCost.toFixed(4)}`;
            break;
            
        case 'final_answer':
            removeThinkingIndicator(thinkingDiv);
            // Only show final answer once
            if (!finalAnswerShown) {
                const answer = event.data?.answer || event.message;
                addFinalAnswer(answer);
                finalAnswerShown = true;
            }
            updateStatus('Completed', 'ready');
            break;
            
        case 'execution_completed':
            removeThinkingIndicator(thinkingDiv);
            updateStatus('Ready', 'ready');
            isProcessing = false;
            sendBtn.disabled = false;
            stopBtn.style.display = 'none';
            currentIterationContainer = null;
            break;
            
        case 'execution_failed':
            removeThinkingIndicator(thinkingDiv);
            addMessage('system', `❌ ${event.message}`);
            updateStatus('Error', 'error');
            isProcessing = false;
            sendBtn.disabled = false;
            stopBtn.style.display = 'none';
            break;
    }
    
    // Auto-scroll to bottom
    scrollToBottom();
}

function createIterationContainer(iteration) {
    const containerDiv = document.createElement('div');
    containerDiv.className = 'message reasoning-container';
    containerDiv.id = 'currentIterationContainer';
    
    containerDiv.innerHTML = `
        <div class="message-content">
            <div class="iteration-header" onclick="toggleReasoningPath(this)">
                <div class="iteration-header-left">
                    <span class="iteration-toggle-icon">▼</span>
                    <span class="iteration-title">🔄 Reasoning Path</span>
                    <span class="iteration-badge">Step ${iteration}</span>
                </div>
                <span class="iteration-toggle-hint">Click to expand</span>
            </div>
            <div class="iteration-content collapsed" id="iterationContent">
                <!-- Tool calls and results will be added here -->
            </div>
        </div>
    `;
    
    messagesContainer.appendChild(containerDiv);
    return containerDiv;
}

function updateIterationContainer(iteration) {
    if (currentIterationContainer) {
        const badge = currentIterationContainer.querySelector('.iteration-badge');
        if (badge) {
            badge.textContent = `Step ${iteration}`;
        }
    }
}

// Make toggleReasoningPath globally accessible
window.toggleReasoningPath = function(headerElement) {
    const container = headerElement.closest('.reasoning-container');
    if (!container) return;
    
    const content = container.querySelector('.iteration-content');
    const icon = headerElement.querySelector('.iteration-toggle-icon');
    const hint = headerElement.querySelector('.iteration-toggle-hint');
    
    if (content.classList.contains('collapsed')) {
        content.classList.remove('collapsed');
        icon.textContent = '▲';
        hint.textContent = 'Click to collapse';
        
        // Re-render all charts in the expanded container
        setTimeout(() => {
            const charts = content.querySelectorAll('.plotly-chart');
            charts.forEach(chartElement => {
                const chartId = chartElement.id;
                // Check if chart needs to be rendered (if it's empty or has error)
                if (chartElement.children.length === 0 || chartElement.querySelector('p[style*="color: red"]')) {
                    // Try to find the figure data from stored charts
                    const storedChart = reasoningCharts.find(c => c.chartId === chartId);
                    if (storedChart && storedChart.figure) {
                        renderChart(chartId, storedChart.figure);
                    }
                } else {
                    // Chart exists, trigger resize
                    if (typeof Plotly !== 'undefined' && Plotly.Plots) {
                        Plotly.Plots.resize(chartId);
                    }
                }
            });
        }, 300); // Wait for animation to complete
    } else {
        content.classList.add('collapsed');
        icon.textContent = '▼';
        hint.textContent = 'Click to expand';
    }
};

function addMessage(type, content) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}`;
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.innerHTML = formatMessageContent(content);
    
    messageDiv.appendChild(contentDiv);
    messagesContainer.appendChild(messageDiv);
    
    // Render LaTeX/Math after DOM update
    setTimeout(() => {
        if (typeof renderMathInElement !== 'undefined') {
            try {
                renderMathInElement(contentDiv, {
                    delimiters: [
                        {left: "$$", right: "$$", display: true},
                        {left: "$", right: "$", display: false},
                        {left: "\\[", right: "\\]", display: true},
                        {left: "\\(", right: "\\)", display: false}
                    ],
                    throwOnError: false
                });
            } catch (e) {
                console.error('KaTeX rendering error:', e);
            }
        } else if (typeof katex !== 'undefined') {
            renderMathManually(contentDiv);
        }
    }, 100);
    
    // Add smooth scroll with slight delay for animation
    setTimeout(() => {
        scrollToBottom();
    }, 100);
    
    return messageDiv;
}

function addThinkingIndicator() {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message thinking assistant';
    messageDiv.id = 'thinkingIndicator';
    
    messageDiv.innerHTML = `
        <div class="message-content">
            <div class="thinking-dots">
                <div class="thinking-dot"></div>
                <div class="thinking-dot"></div>
                <div class="thinking-dot"></div>
            </div>
            <span>Thinking...</span>
        </div>
    `;
    
    messagesContainer.appendChild(messageDiv);
    scrollToBottom();
    return messageDiv;
}

function removeThinkingIndicator(div) {
    if (div && div.parentNode) {
        div.remove();
    }
    const indicator = document.getElementById('thinkingIndicator');
    if (indicator) {
        indicator.remove();
    }
}

function addToolCall(tool, args) {
    // Special handling for code_executor to display code nicely
    let argsHtml = '';
    if (tool === 'code_executor' && args.code) {
        // Extract code and other parameters
        const code = args.code;
        const timeout = args.timeout || 'default';
        const language = detectCodeLanguage(code);
        
        argsHtml = `
            <div class="code-executor-args">
                <div class="code-block-wrapper">
                    <div class="code-block-header">
                        <span class="code-language">${language}</span>
                        ${timeout !== 'default' ? `<span class="code-timeout">Timeout: ${timeout}s</span>` : ''}
                    </div>
                    <pre class="code-block"><code class="language-${language}">${escapeHtml(code)}</code></pre>
                </div>
                ${Object.keys(args).filter(k => k !== 'code' && k !== 'timeout').length > 0 ? `
                    <details class="code-extra-params">
                        <summary>Additional Parameters</summary>
                        <pre class="tool-call-args">${escapeHtml(JSON.stringify(Object.fromEntries(Object.entries(args).filter(([k]) => k !== 'code' && k !== 'timeout')), null, 2))}</pre>
                    </details>
                ` : ''}
            </div>
        `;
    } else {
        // Default JSON formatting for other tools
        let argsStr;
        try {
            argsStr = JSON.stringify(args, null, 2);
        } catch (e) {
            argsStr = String(args);
        }
        argsHtml = `<pre class="tool-call-args">${escapeHtml(argsStr)}</pre>`;
    }
    
    // Add to iteration container if it exists
    if (currentIterationContainer) {
        const contentDiv = currentIterationContainer.querySelector('#iterationContent');
        if (contentDiv) {
            const toolCallDiv = document.createElement('div');
            toolCallDiv.className = 'reasoning-item tool-call-item';
            toolCallDiv.innerHTML = `
                <div class="tool-call">
                    <div class="tool-call-header">
                        🔧 <code>${escapeHtml(tool)}</code>
                    </div>
                    ${argsHtml}
                </div>
            `;
            contentDiv.appendChild(toolCallDiv);
            scrollToBottom();
            return;
        }
    }
    
    // Fallback to standalone message
    const toolDiv = document.createElement('div');
    toolDiv.className = 'message system';
    
    toolDiv.innerHTML = `
        <div class="message-content">
            <div class="tool-call">
                <div class="tool-call-header">
                    🔧 Calling tool: <code>${escapeHtml(tool)}</code>
                </div>
                ${argsHtml}
            </div>
        </div>
    `;
    
    messagesContainer.appendChild(toolDiv);
    scrollToBottom();
}

function detectCodeLanguage(code) {
    // Simple language detection based on code patterns
    if (code.includes('import numpy') || code.includes('import pandas') || code.includes('import matplotlib')) {
        return 'python';
    }
    if (code.includes('import ') && code.includes('from ')) {
        return 'python';
    }
    if (code.includes('def ') || code.includes('class ')) {
        return 'python';
    }
    if (code.includes('function ') || code.includes('const ') || code.includes('let ')) {
        return 'javascript';
    }
    if (code.includes('<?php')) {
        return 'php';
    }
    if (code.includes('#include') || code.includes('int main')) {
        return 'cpp';
    }
    if (code.includes('SELECT') || code.includes('INSERT') || code.includes('UPDATE')) {
        return 'sql';
    }
    return 'python'; // Default to Python
}

function addToolResult(result, success) {
    const icon = success ? '✅' : '❌';
    const resultText = result.result || result.error || 'No result';
    let chartInfo = null;
    
    // Check if this is a visualizer result with Plotly figure
    if (success && typeof resultText === 'object' && resultText.format === 'json' && resultText.figure) {
        const chartId = `chart-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
        chartInfo = { isChart: true, chartId, figure: resultText.figure };
        
        // Add to iteration container if it exists
        if (currentIterationContainer) {
            const contentDiv = currentIterationContainer.querySelector('#iterationContent');
            if (contentDiv) {
                const resultDiv = document.createElement('div');
                resultDiv.className = 'reasoning-item tool-result-item';
                resultDiv.innerHTML = `
                    <div class="tool-result">
                        <strong>${icon} Tool Result: Interactive Graph</strong>
                        <div id="${chartId}" class="plotly-chart" style="width: 100%; height: 400px; margin-top: 10px;"></div>
                    </div>
                `;
                contentDiv.appendChild(resultDiv);
                
                // Render chart (will handle collapsed state)
                setTimeout(() => {
                    renderChart(chartId, resultText.figure);
                    // Also store for re-rendering if needed
                    chartInfo.element = resultDiv;
                }, 100);
                scrollToBottom();
                return chartInfo;
            }
        }
        
        // Fallback to standalone
        const resultDiv = document.createElement('div');
        resultDiv.className = 'message system';
        resultDiv.innerHTML = `
            <div class="message-content">
                <div class="tool-result">
                    <strong>${icon} Tool Result: Interactive Graph Generated</strong>
                    <div id="${chartId}" class="plotly-chart" style="width: 100%; height: 500px; margin-top: 10px; border-radius: 8px; background: white;"></div>
                </div>
            </div>
        `;
        messagesContainer.appendChild(resultDiv);
        setTimeout(() => renderChart(chartId, resultText.figure), 100);
        scrollToBottom();
        return chartInfo;
    } else if (success && typeof resultText === 'object' && resultText.format === 'html' && resultText.html) {
        // Handle HTML output
        if (currentIterationContainer) {
            const contentDiv = currentIterationContainer.querySelector('#iterationContent');
            if (contentDiv) {
                const resultDiv = document.createElement('div');
                resultDiv.className = 'reasoning-item tool-result-item';
                resultDiv.innerHTML = `
                    <div class="tool-result">
                        <strong>${icon} Tool Result: Interactive Graph (HTML)</strong>
                        <div class="html-content" style="margin-top: 10px;">
                            ${resultText.html}
                        </div>
                    </div>
                `;
                contentDiv.appendChild(resultDiv);
                scrollToBottom();
                return null;
            }
        }
        
        const resultDiv = document.createElement('div');
        resultDiv.className = 'message system';
        resultDiv.innerHTML = `
            <div class="message-content">
                <div class="tool-result">
                    <strong>${icon} Tool Result: Interactive Graph Generated (HTML)</strong>
                    <div class="html-content" style="margin-top: 10px;">
                        ${resultText.html}
                    </div>
                </div>
            </div>
        `;
        messagesContainer.appendChild(resultDiv);
        scrollToBottom();
        return null;
    } else {
        // Default handling for non-visualization results
        let displayText;
        if (typeof resultText === 'string') {
            displayText = resultText;
        } else if (resultText === null || resultText === undefined) {
            displayText = 'null';
        } else {
            displayText = JSON.stringify(resultText, null, 2);
        }
        
        // Don't truncate - show full content with scroll
        const escapedText = escapeHtml(displayText);
        
        // Add to iteration container if it exists
        if (currentIterationContainer) {
            const contentDiv = currentIterationContainer.querySelector('#iterationContent');
            if (contentDiv) {
                const resultDiv = document.createElement('div');
                resultDiv.className = 'reasoning-item tool-result-item';
                resultDiv.innerHTML = `
                    <div class="tool-result ${success ? '' : 'error'}">
                        <strong>${icon} Tool Result:</strong>
                        <pre class="tool-result-text">${escapedText}</pre>
                    </div>
                `;
                contentDiv.appendChild(resultDiv);
                scrollToBottom();
                return null;
            }
        }
        
        // Fallback to standalone
        const resultDiv = document.createElement('div');
        resultDiv.className = 'message system';
        resultDiv.innerHTML = `
            <div class="message-content">
                <div class="tool-result ${success ? '' : 'error'}">
                    <strong>${icon} Tool Result:</strong>
                    <pre class="tool-result-text">${escapedText}</pre>
                </div>
            </div>
        `;
        messagesContainer.appendChild(resultDiv);
        scrollToBottom();
        return null;
    }
}

function renderChart(chartId, figure) {
    // Check if element exists and is visible
    const element = document.getElementById(chartId);
    if (!element) {
        console.warn(`Chart element ${chartId} not found`);
        return;
    }
    
    // Check if parent is collapsed
    const isCollapsed = element.closest('.collapsed') !== null;
    
    // If collapsed, wait for it to be expanded before rendering
    if (isCollapsed) {
        // Store the chart info for later rendering
        const observer = new MutationObserver((mutations, obs) => {
            const stillCollapsed = element.closest('.collapsed') !== null;
            if (!stillCollapsed) {
                obs.disconnect();
                // Small delay to ensure element is fully visible
                setTimeout(() => {
                    renderChartNow(chartId, figure);
                }, 100);
            }
        });
        
        // Observe the parent container
        const container = element.closest('.iteration-content');
        if (container) {
            observer.observe(container, { attributes: true, attributeFilter: ['class'] });
        }
        
        // Also try to render after a delay in case observer doesn't catch it
        setTimeout(() => {
            if (!element.closest('.collapsed')) {
                renderChartNow(chartId, figure);
            }
        }, 2000);
    } else {
        renderChartNow(chartId, figure);
    }
}

function renderChartNow(chartId, figure) {
    try {
        const element = document.getElementById(chartId);
        if (!element) return;
        
        // Clear any existing content
        element.innerHTML = '';
        
        if (typeof Plotly === 'undefined') {
            setTimeout(() => {
                if (typeof Plotly !== 'undefined') {
                    Plotly.newPlot(chartId, figure.data, figure.layout, {
                        responsive: true,
                        displayModeBar: true
                    });
                } else {
                    element.innerHTML = '<p style="color: red; padding: 20px;">❌ Chart rendering failed: Plotly library not loaded.</p>';
                }
            }, 1000);
        } else {
            Plotly.newPlot(chartId, figure.data, figure.layout, {
                responsive: true,
                displayModeBar: true
            });
        }
    } catch (e) {
        console.error('Failed to render Plotly chart:', e);
        const element = document.getElementById(chartId);
        if (element) {
            element.innerHTML = `<p style="color: red; padding: 20px;">❌ Failed to render chart: ${escapeHtml(e.message)}</p>`;
        }
    }
}

function addFinalAnswer(answer) {
    // Check if final answer already exists
    const existingFinalAnswer = messagesContainer.querySelector('.final-answer');
    if (existingFinalAnswer) {
        // Update existing final answer instead of creating new one
        const finalAnswerText = existingFinalAnswer.querySelector('.final-answer-text');
        if (finalAnswerText) {
            const cleanedAnswer = formatAnswer(answer);
            finalAnswerText.innerHTML = formatMessageContent(cleanedAnswer);
            
            // Re-render math if needed
            setTimeout(() => {
                renderMathInFinalAnswer(existingFinalAnswer);
            }, 200);
        }
        scrollToBottom();
        return;
    }
    
    const finalDiv = document.createElement('div');
    finalDiv.className = 'message final-answer';
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content final-answer-content';
    
    const cleanedAnswer = formatAnswer(answer);
    
    let html = `
        <div class="final-answer-header">
            <span class="final-answer-icon">✨</span>
            <span class="final-answer-title">Final Answer</span>
        </div>
        <div class="final-answer-text">
            ${formatMessageContent(cleanedAnswer)}
        </div>
    `;
    
    // Add any charts from reasoning
    if (reasoningCharts.length > 0) {
        html += '<div class="final-answer-charts">';
        reasoningCharts.forEach((chartInfo, index) => {
            const chartId = `final-chart-${Date.now()}-${index}`;
            html += `
                <div class="final-chart-container">
                    <div id="${chartId}" class="plotly-chart" style="width: 100%; height: 500px; margin-top: 15px;"></div>
                </div>
            `;
            // Render chart after DOM update
            setTimeout(() => renderChart(chartId, chartInfo.figure), 100);
        });
        html += '</div>';
    }
    
    contentDiv.innerHTML = html;
    finalDiv.appendChild(contentDiv);
    messagesContainer.appendChild(finalDiv);
    
    // Render LaTeX/Math in final answer after DOM is updated
    setTimeout(() => {
        renderMathInFinalAnswer(finalDiv);
    }, 300);
    
    scrollToBottom();
}

function formatMessageContent(content) {
    if (!content) return '';
    
    // Use marked.js for markdown rendering if available
    if (typeof marked !== 'undefined') {
        try {
            // Configure marked options
            marked.setOptions({
                breaks: true,
                gfm: true,
                headerIds: true,
                mangle: false
            });
            
            // Render markdown
            let html = marked.parse(content);
            
            return html;
        } catch (e) {
            console.error('Markdown rendering error:', e);
            // Fallback to basic formatting
            return escapeHtml(content)
                .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                .replace(/\*(.*?)\*/g, '<em>$1</em>')
                .replace(/`(.*?)`/g, '<code>$1</code>')
                .replace(/\n/g, '<br>');
        }
    }
    
    // Fallback: Basic markdown-like formatting
    return escapeHtml(content)
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/`(.*?)`/g, '<code>$1</code>')
        .replace(/\n/g, '<br>');
}

function renderMathInFinalAnswer(finalDiv) {
    const finalAnswerText = finalDiv.querySelector('.final-answer-text');
    if (!finalAnswerText) return;
    
    let autoRendered = false;
    
    if (typeof renderMathInElement !== 'undefined') {
        try {
            // Use auto-render with comprehensive delimiters
            renderMathInElement(finalAnswerText, {
                delimiters: [
                    {left: "$$", right: "$$", display: true},
                    {left: "$", right: "$", display: false},
                    {left: "\\[", right: "\\]", display: true},
                    {left: "\\(", right: "\\)", display: false},
                    {left: "\\begin{equation}", right: "\\end{equation}", display: true},
                    {left: "\\begin{align}", right: "\\end{align}", display: true},
                    {left: "\\begin{matrix}", right: "\\end{matrix}", display: true},
                    {left: "\\begin{pmatrix}", right: "\\end{pmatrix}", display: true},
                    {left: "\\begin{bmatrix}", right: "\\end{bmatrix}", display: true},
                    {left: "[", right: "]", display: true, asciiMath: true}
                ],
                throwOnError: false,
                strict: false
            });
            autoRendered = true;
        } catch (e) {
            console.error('KaTeX auto-render error:', e);
            // Fallback to manual rendering
            renderMathManually(finalAnswerText);
        }
    } else if (typeof katex !== 'undefined') {
        renderMathManually(finalAnswerText);
    }
    
    // Some constructs (like bare [ ... ] blocks) may still need manual handling
    if (typeof katex !== 'undefined' && autoRendered) {
        renderMathManually(finalAnswerText);
    }
}

function renderMathManually(element) {
    // Manual KaTeX rendering for math expressions
    if (typeof katex === 'undefined') return;
    
    let html = element.innerHTML;
    
    // First, handle all LaTeX environments (bmatrix, pmatrix, etc.) - do this first before bracket matching
    const latexEnvironments = ['bmatrix', 'pmatrix', 'vmatrix', 'Vmatrix', 'matrix', 'align', 'equation', 'alignat', 'gather'];
    
    latexEnvironments.forEach(env => {
        // Handle both escaped and unescaped backslashes in HTML
        const pattern1 = new RegExp(`\\\\begin\\{${env}\\}([\\s\\S]*?)\\\\end\\{${env}\\}`, 'g');
        const pattern2 = new RegExp(`\\\\\\\\begin\\{${env}\\}([\\s\\S]*?)\\\\\\\\end\\{${env}\\}`, 'g');
        
        html = html.replace(pattern1, (match, content) => {
            try {
                const fullEnv = `\\begin{${env}}${content}\\end{${env}}`;
                return katex.renderToString(fullEnv, { displayMode: true, throwOnError: false });
            } catch (e) {
                return match;
            }
        });
        
        html = html.replace(pattern2, (match, content) => {
            try {
                // Unescape double backslashes
                const unescapedContent = content.replace(/\\\\/g, '\\');
                const fullEnv = `\\begin{${env}}${unescapedContent}\\end{${env}}`;
                return katex.renderToString(fullEnv, { displayMode: true, throwOnError: false });
            } catch (e) {
                return match;
            }
        });
    });
    
    // Handle block math with \[ \]
    html = html.replace(/\\\[([\s\S]*?)\\\]/g, (match, math) => {
        try {
            return katex.renderToString(math.trim(), { displayMode: true, throwOnError: false });
        } catch (e) {
            return match;
        }
    });
    
    // Handle inline math with \( \)
    html = html.replace(/\\\(([\s\S]*?)\\\)/g, (match, math) => {
        try {
            return katex.renderToString(math.trim(), { displayMode: false, throwOnError: false });
        } catch (e) {
            return match;
        }
    });
    
    // Handle display math with $$
    html = html.replace(/\$\$([\s\S]*?)\$\$/g, (match, math) => {
        try {
            return katex.renderToString(math.trim(), { displayMode: true, throwOnError: false });
        } catch (e) {
            return match;
        }
    });
    
    // Handle inline math with $
    html = html.replace(/\$([^$\n]+)\$/g, (match, math) => {
        try {
            return katex.renderToString(math.trim(), { displayMode: false, throwOnError: false });
        } catch (e) {
            return match;
        }
    });
    
    // Handle [ ... ] as display math - this should come AFTER processing LaTeX environments
    // Match patterns like [ \begin{bmatrix} ... \end{bmatrix} ] or [ A^{10} = ... ]
    html = html.replace(/\[\s*([^\]]+?)\s*\]/g, (match, math) => {
        // Skip if already processed by KaTeX (contains katex class)
        if (match.includes('katex') || match.includes('katex-display')) {
            return match;
        }
        
        const trimmedMath = math.trim();
        
        // Check if it contains LaTeX commands or math symbols
        const hasLatexCommands = trimmedMath.includes('\\begin') || trimmedMath.includes('\\end') || 
                                 trimmedMath.includes('\\') || trimmedMath.includes('^') || 
                                 trimmedMath.includes('_') || trimmedMath.includes('=');
        
        if (hasLatexCommands) {
            try {
                // Unescape HTML entities if needed
                let processedMath = trimmedMath;
                // Handle escaped backslashes in HTML
                processedMath = processedMath.replace(/\\\\/g, '\\');
                // Handle HTML entities
                processedMath = processedMath.replace(/&amp;/g, '&');
                processedMath = processedMath.replace(/&lt;/g, '<');
                processedMath = processedMath.replace(/&gt;/g, '>');
                
                return katex.renderToString(processedMath, { displayMode: true, throwOnError: false });
            } catch (e) {
                console.warn('KaTeX rendering failed for bracket math:', trimmedMath, e);
                return match;
            }
        }
        return match;
    });
    
    element.innerHTML = html;
}

function formatAnswer(answer) {
    if (!answer) return '';
    // Remove "FINAL ANSWER:" prefix if present (case insensitive, multiple variations)
    return answer
        .replace(/^FINAL ANSWER:\s*/gi, '')
        .replace(/^FINAL\s+ANSWER\s*:\s*/gi, '')
        .replace(/^##\s*FINAL\s+ANSWER\s*:?\s*/gi, '')
        .replace(/^###\s*FINAL\s+ANSWER\s*:?\s*/gi, '')
        .trim();
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function updateStatus(text, state) {
    statusText.textContent = text;
    statusIndicator.className = `status-indicator ${state}`;
}

function scrollToBottom() {
    messagesContainer.scrollTo({
        top: messagesContainer.scrollHeight,
        behavior: 'smooth'
    });
}

function stopExecution() {
    if (currentWebSocket) {
        currentWebSocket.close();
        currentWebSocket = null;
    }
    
    addMessage('system', '⏹️ Execution stopped by user');
    updateStatus('Stopped', 'ready');
    isProcessing = false;
    sendBtn.disabled = false;
    stopBtn.style.display = 'none';
}
