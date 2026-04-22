/**
 * Novel by Agents - Desktop App JavaScript
 */

// 状态管理
let state = {
    workflowId: null,
    ws: null,
    status: 'idle', // idle, creating, running, completed, error
    outline: null,
    characters: null,
    chapters: [],
    currentChapter: null
};

// DOM 元素
const elements = {
    userIntent: document.getElementById('userIntent'),
    modelName: document.getElementById('modelName'),
    minChapters: document.getElementById('minChapters'),
    volume: document.getElementById('volume'),
    masterOutline: document.getElementById('masterOutline'),
    createBtn: document.getElementById('createBtn'),
    cancelBtn: document.getElementById('cancelBtn'),
    progressSection: document.getElementById('progressSection'),
    progressFill: document.getElementById('progressFill'),
    progressText: document.getElementById('progressText'),
    currentNode: document.getElementById('currentNode'),
    outlineSection: document.getElementById('outlineSection'),
    outlineContent: document.getElementById('outlineContent'),
    charactersSection: document.getElementById('charactersSection'),
    charactersContent: document.getElementById('charactersContent'),
    chaptersSection: document.getElementById('chaptersSection'),
    chapterList: document.getElementById('chapterList'),
    chapterContentSection: document.getElementById('chapterContentSection'),
    chapterTitle: document.getElementById('chapterTitle'),
    chapterContent: document.getElementById('chapterContent'),
    backToListBtn: document.getElementById('backToListBtn'),
    evaluationSection: document.getElementById('evaluationSection'),
    evaluationContent: document.getElementById('evaluationContent')
};

// API 基础路径
const API_BASE = '/api/v1';

// 事件绑定
elements.createBtn.addEventListener('click', createNovel);
elements.cancelBtn.addEventListener('click', cancelNovel);
elements.backToListBtn.addEventListener('click', showChapterList);

// 创建小说
async function createNovel() {
    const userIntent = elements.userIntent.value.trim();
    if (!userIntent) {
        alert('请输入创作意图');
        return;
    }

    const modelName = elements.modelName.value.trim();
    if (!modelName) {
        alert('请输入模型名称');
        return;
    }

    state.status = 'creating';
    updateUI();

    try {
        const response = await fetch(`${API_BASE}/novels`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                user_intent: userIntent,
                model_name: modelName,
                model_type: 'api',
                api_type: 'anthropic',
                min_chapters: parseInt(elements.minChapters.value) || 10,
                volume: parseInt(elements.volume.value) || 1,
                master_outline: elements.masterOutline.checked
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();
        state.workflowId = data.workflow_id;
        state.status = 'running';

        // 启动执行并监听进度
        await startExecution();
        connectWebSocket();

    } catch (error) {
        console.error('创建失败:', error);
        alert('创建失败: ' + error.message);
        state.status = 'error';
        updateUI();
    }
}

// 启动执行
async function startExecution() {
    try {
        const response = await fetch(`${API_BASE}/novels/${state.workflowId}/execute`, {
            method: 'POST'
        });

        if (!response.ok) {
            throw new Error('启动执行失败');
        }
    } catch (error) {
        console.error('启动执行失败:', error);
    }
}

// WebSocket 连接
function connectWebSocket() {
    if (!state.workflowId) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}${API_BASE}/novels/${state.workflowId}/ws`;

    state.ws = new WebSocket(wsUrl);

    state.ws.onopen = () => {
        console.log('WebSocket connected');
        // 心跳
        setInterval(() => {
            if (state.ws && state.ws.readyState === WebSocket.OPEN) {
                state.ws.send('ping');
            }
        }, 25000);
    };

    state.ws.onmessage = (event) => {
        if (event.data === 'pong') return;
        handleProgress(JSON.parse(event.data));
    };

    state.ws.onclose = () => {
        console.log('WebSocket disconnected');
        // 重新连接
        if (state.status === 'running') {
            setTimeout(connectWebSocket, 1000);
        }
    };

    state.ws.onerror = (error) => {
        console.error('WebSocket error:', error);
    };
}

// 处理进度更新
function handleProgress(data) {
    console.log('Progress:', data);

    const progress = data.progress || 0;
    const node = data.current_node || '';
    const status = data.status || '';

    // 更新进度条
    elements.progressFill.style.width = `${progress * 100}%`;
    elements.progressText.textContent = `${Math.round(progress * 100)}%`;
    elements.currentNode.textContent = node;

    // 更新状态
    if (status === 'completed') {
        state.status = 'completed';
        loadResults();
    } else if (status === 'error') {
        state.status = 'error';
        elements.progressText.textContent = '发生错误';
    }

    updateUI();
}

// 加载结果
async function loadResults() {
    try {
        const response = await fetch(`${API_BASE}/novels/${state.workflowId}`);
        const data = await response.json();

        // 显示大纲
        if (data.outline) {
            state.outline = data.outline;
            renderOutline(data.outline);
        }

        // 显示角色
        if (data.characters) {
            state.characters = data.characters;
            renderCharacters(data.characters);
        }

        // 显示章节
        if (data.chapters) {
            state.chapters = data.chapters;
            renderChapterList(data.chapters);
        }

    } catch (error) {
        console.error('加载结果失败:', error);
    }
}

// 渲染大纲
function renderOutline(outline) {
    let html = `<h3>${outline.title || '未命名小说'}</h3>`;
    html += `<p><strong>类型：</strong>${outline.genre || '未知'}</p>`;
    html += `<p><strong>简介：</strong>${outline.summary || '无'}</p>`;

    if (outline.volumes) {
        html += '<h3>分卷</h3><ul>';
        outline.volumes.forEach(v => {
            html += `<li><strong>第${v.volume_number}卷 ${v.volume_title}</strong>: ${v.summary}</li>`;
        });
        html += '</ul>';
    }

    if (outline.chapters) {
        html += `<h3>章节 (${outline.chapters.length}章)</h3><ul>`;
        outline.chapters.slice(0, 5).forEach(c => {
            html += `<li>第${c.chapter_number}章: ${c.title}</li>`;
        });
        if (outline.chapters.length > 5) {
            html += `<li>... 还有 ${outline.chapters.length - 5} 章</li>`;
        }
        html += '</ul>';
    }

    elements.outlineContent.innerHTML = html;
    elements.outlineSection.style.display = 'block';
}

// 渲染角色
function renderCharacters(characters) {
    let html = '';

    if (Array.isArray(characters)) {
        characters.forEach(char => {
            html += `<div style="margin-bottom: 15px; padding-bottom: 15px; border-bottom: 1px solid var(--surface);">`;
            html += `<h3>${char.name}</h3>`;
            html += `<p><strong>背景：</strong>${char.background || '未知'}</p>`;
            html += `<p><strong>性格：</strong>${char.personality || '未知'}</p>`;
            html += `<p><strong>目标：</strong>${char.goals || '未知'}</p>`;
            html += `<p><strong>冲突：</strong>${char.conflicts || '未知'}</p>`;
            html += `<p><strong>成长：</strong>${char.arc || '未知'}</p>`;
            html += `</div>`;
        });
    } else {
        html = '<p>暂无角色信息</p>';
    }

    elements.charactersContent.innerHTML = html;
    elements.charactersSection.style.display = 'block';
}

// 渲染章节列表
function renderChapterList(chapters) {
    let html = '';

    chapters.forEach((chapter, index) => {
        const isGenerated = chapter.content && chapter.content.length > 0;
        html += `
            <div class="chapter-item ${isGenerated ? '' : 'generating'}" data-index="${index}">
                <span class="chapter-name">第${chapter.chapter_number}章: ${chapter.title}</span>
                <span class="chapter-status">${isGenerated ? '✓' : '生成中'}</span>
            </div>
        `;
    });

    elements.chapterList.innerHTML = html;

    // 绑定点击事件
    document.querySelectorAll('.chapter-item').forEach(item => {
        item.addEventListener('click', () => {
            const index = parseInt(item.dataset.index);
            showChapter(index);
        });
    });

    elements.chaptersSection.style.display = 'block';
}

// 显示章节内容
function showChapter(index) {
    const chapter = state.chapters[index];
    if (!chapter) return;

    state.currentChapter = index;
    elements.chapterTitle.textContent = `第${chapter.chapter_number}章: ${chapter.title}`;

    let content = chapter.content || '内容生成中...';
    if (Array.isArray(content)) {
        content = content.join('\n\n');
    }

    elements.chapterContent.textContent = content;
    elements.chaptersSection.style.display = 'none';
    elements.chapterContentSection.style.display = 'block';
}

// 返回章节列表
function showChapterList() {
    elements.chapterContentSection.style.display = 'none';
    elements.chaptersSection.style.display = 'block';
}

// 取消生成
async function cancelNovel() {
    if (!state.workflowId) return;

    try {
        await fetch(`${API_BASE}/novels/${state.workflowId}`, {method: 'DELETE'});
        state.status = 'idle';
        state.workflowId = null;
        if (state.ws) {
            state.ws.close();
            state.ws = null;
        }
        updateUI();
    } catch (error) {
        console.error('取消失败:', error);
    }
}

// 更新 UI
function updateUI() {
    // 按钮状态
    elements.createBtn.disabled = state.status !== 'idle';
    elements.cancelBtn.disabled = state.status === 'idle';

    // 进度区域
    elements.progressSection.style.display = (state.status === 'running' || state.status === 'creating') ? 'block' : 'none';

    // 重置进度
    if (state.status === 'idle') {
        elements.progressFill.style.width = '0%';
        elements.progressText.textContent = '';
        elements.currentNode.textContent = '';
    }
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    console.log('Novel by Agents initialized');
    updateUI();
});
