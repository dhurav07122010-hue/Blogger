/**
 * =========================================================================
 * BLOGGERS DESKTOP STUDIO — MAIN APPLICATION CONTROLLER
 * Comprehensive, production-grade controller for writing, editing,
 * managing, and publishing articles to Google Blogger.
 * =========================================================================
 */

// Ensure API.updateArticle exists even if a cached api.js was loaded
if (typeof API !== 'undefined' && typeof API.updateArticle !== 'function') {
  API.updateArticle = async function(id, data) {
    const res = await fetch(`/api/articles/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to update article');
    }
    return res.json();
  };
}

// ---------------- GLOBAL APPLICATION STATE ----------------
let currentArticleId = null;
let currentArticleData = null;
let allArticlesCache = [];
let currentFilterStatus = 'ALL';
let currentSearchQuery = '';
let currentImageCandidates = [];
let pendingCustomFile = null;
let pendingCustomFileDataUrl = null;
let autosaveTimer = null;
let isRawHtmlMode = false;

// ---------------- TOAST NOTIFICATIONS ----------------
function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  const icon = type === 'success' ? '✓' : (type === 'error' ? '✕' : (type === 'warning' ? '⚠' : 'ℹ'));
  toast.innerHTML = `<span style="font-weight:700;">${icon}</span><span>${message}</span>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.remove();
  }, 4000);
}

// ---------------- THEME CONTROLLER ----------------
function initTheme() {
  const saved = localStorage.getItem('theme') || 'dark';
  setThemeDirect(saved);
}

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme') || 'dark';
  const next = current === 'dark' ? 'light' : 'dark';
  setThemeDirect(next);
}

function setThemeDirect(mode) {
  document.documentElement.setAttribute('data-theme', mode);
  document.body.setAttribute('data-theme', mode);
  localStorage.setItem('theme', mode);
  const icon = document.getElementById('theme-toggle-icon');
  if (icon) icon.innerText = mode === 'dark' ? '🌙' : '☀️';
}

// ---------------- SIDEBAR COLLAPSE CONTROLLER ----------------
function toggleSidebarCollapse() {
  const sidebar = document.getElementById('app-sidebar');
  if (!sidebar) return;
  sidebar.classList.toggle('collapsed');
  const isCollapsed = sidebar.classList.contains('collapsed');
  localStorage.setItem('sidebar_collapsed', isCollapsed ? '1' : '0');
  const icon = document.getElementById('sidebar-toggle-icon');
  if (icon) icon.innerText = isCollapsed ? '▶' : '◀';
}

function initSidebarState() {
  const isCollapsed = localStorage.getItem('sidebar_collapsed') === '1';
  const sidebar = document.getElementById('app-sidebar');
  if (sidebar && isCollapsed) {
    sidebar.classList.add('collapsed');
    const icon = document.getElementById('sidebar-toggle-icon');
    if (icon) icon.innerText = '▶';
  }
}

// Keyboard shortcuts (Ctrl+B to collapse sidebar, Ctrl+K to search)
window.addEventListener('keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'b') {
    e.preventDefault();
    toggleSidebarCollapse();
  } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault();
    const searchInput = document.getElementById('global-search-input');
    if (searchInput) searchInput.focus();
  }
});

// ---------------- TAB NAVIGATION ROUTER ----------------
function switchTab(tabId) {
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));

  const activePanel = document.getElementById(`tab-${tabId}`);
  const activeNav = document.querySelector(`[data-tab="${tabId}"]`);

  if (activePanel) activePanel.classList.add('active');
  if (activeNav) activeNav.classList.add('active');

  const titles = {
    dashboard: 'Dashboard Overview',
    create: 'AI Writing & Creation Studio',
    discovery: 'Internet Topic Discovery',
    articles: 'All Articles & Pipeline',
    drafts: 'Active Drafts',
    published: 'Published Posts',
    research: 'Content Library & Sources',
    templates: 'Article Templates',
    history: 'Publishing History & Token Usage',
    review: 'Quality Audit Gate',
    settings: 'System Configuration',
  };

  const breadcrumbCurrent = document.getElementById('breadcrumb-current');
  if (breadcrumbCurrent) breadcrumbCurrent.innerText = titles[tabId] || 'Studio';

  // Load contextual data for the active tab
  if (tabId === 'dashboard') loadDashboard();
  if (tabId === 'create') ensureStudioLoaded();
  if (tabId === 'discovery') loadDiscoveryTopics();
  if (tabId === 'articles') loadArticles();
  if (tabId === 'drafts') loadDrafts();
  if (tabId === 'published') loadPublished();
  if (tabId === 'research') loadResearch();
  if (tabId === 'history') loadPublishingHistory();
  if (tabId === 'settings') loadSettings();
  if (tabId === 'review' && currentArticleId) openReview(currentArticleId);
}

// ---------------- GLOBAL SEARCH ----------------
function handleGlobalSearch(query) {
  currentSearchQuery = (query || '').toLowerCase().trim();
  const activeTab = document.querySelector('.nav-item.active')?.getAttribute('data-tab');

  if (activeTab === 'articles' || activeTab === 'drafts' || activeTab === 'published') {
    filterAndRenderArticles();
  } else if (currentSearchQuery.length > 1) {
    // Automatically switch to articles view to search
    switchTab('articles');
    const searchBox = document.getElementById('articles-search-filter');
    if (searchBox) searchBox.value = query;
    filterAndRenderArticles();
  }
}

// ---------------- DASHBOARD ----------------
async function loadDashboard() {
  try {
    const stats = await API.getDashboardStats();
    
    // Counts
    document.getElementById('stat-created').innerText = stats.articles_created || 0;
    document.getElementById('stat-drafts').innerText = stats.drafts_count || 0;
    document.getElementById('stat-approval').innerText = stats.awaiting_approval || 0;
    document.getElementById('stat-published').innerText = stats.published_count || 0;
    document.getElementById('stat-images').innerText = stats.images_generated || 0;
    document.getElementById('stat-failed-quality').innerText = stats.failed_quality_checks || 0;
    document.getElementById('stat-tokens').innerText = (stats.total_tokens_est || 0).toLocaleString();

    // Nav Badges
    const badgeArticles = document.getElementById('nav-count-articles');
    const badgeDrafts = document.getElementById('nav-count-drafts');
    const badgePublished = document.getElementById('nav-count-published');
    if (badgeArticles) badgeArticles.innerText = stats.articles_created || 0;
    if (badgeDrafts) badgeDrafts.innerText = stats.drafts_count || 0;
    if (badgePublished) badgePublished.innerText = stats.published_count || 0;

    // API Connection Badges
    const connGemini = document.getElementById('conn-gemini');
    if (connGemini) {
      connGemini.innerText = stats.gemini_connected ? 'Connected' : 'Missing Key';
      connGemini.className = `status-badge ${stats.gemini_connected ? 'status-APPROVED' : 'status-FAILED'}`;
    }

    const connBlogger = document.getElementById('conn-blogger');
    if (connBlogger) {
      connBlogger.innerText = stats.blogger_connected ? 'ByteBlooming' : 'Disconnected';
      connBlogger.className = `status-badge ${stats.blogger_connected ? 'status-READY_FOR_APPROVAL' : 'status-FACT_CHECK'}`;
    }

    // Recent agent runs table
    const tbodyRuns = document.getElementById('recent-runs-table');
    if (tbodyRuns) {
      tbodyRuns.innerHTML = '';
      if (!stats.recent_agent_runs || stats.recent_agent_runs.length === 0) {
        tbodyRuns.innerHTML = '<tr><td colspan="5" style="text-align:center; color: var(--text-secondary);">No recent agent activity.</td></tr>';
      } else {
        stats.recent_agent_runs.forEach(r => {
          const tr = document.createElement('tr');
          tr.innerHTML = `
            <td><strong>${r.agent_name}</strong></td>
            <td><span class="status-badge status-${r.status}">${r.status}</span></td>
            <td>${r.execution_time_seconds}s</td>
            <td>${((r.input_tokens_est || 0) + (r.output_tokens_est || 0)).toLocaleString()}</td>
            <td style="color: var(--text-secondary);">${r.notes || '-'}</td>
          `;
          tbodyRuns.appendChild(tr);
        });
      }
    }

    // Load recent articles into the dashboard table
    const articles = await API.getArticles();
    allArticlesCache = articles || [];
    renderDashboardArticles(articles.slice(0, 5));

  } catch (err) {
    console.warn('[DASHBOARD] Could not load initial stats:', err.message);
    // If backend was still initializing during initial boot, retry once smoothly after 1.5s
    if (!window._dashboardRetried) {
      window._dashboardRetried = true;
      setTimeout(() => loadDashboard(), 1500);
    } else {
      showToast(err.message, 'error');
    }
  }
}

function renderDashboardArticles(articles) {
  const tbody = document.getElementById('dashboard-articles-table');
  if (!tbody) return;
  tbody.innerHTML = '';

  if (!articles || articles.length === 0) {
    tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; color: var(--text-secondary); padding:24px;">No articles yet. Click "Generate Complete Article" above to create your first post!</td></tr>';
    return;
  }

  articles.forEach(a => {
    const score = a.overall_quality_score != null ? `${Math.round(a.overall_quality_score)}/100` : 'Pending';
    const postDraft = a.blogger_post_id ? `<span style="color:var(--success)">#${a.blogger_post_id.slice(-6)}</span>` : 'Local';
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><strong>${escapeHtml(a.title)}</strong></td>
      <td><span class="status-badge status-${a.status}">${a.status}</span></td>
      <td><strong>${score}</strong></td>
      <td>${postDraft}</td>
      <td style="white-space:nowrap;">
        <button class="btn btn-primary btn-sm" onclick="openStudioForArticle(${a.id})">✍️ Edit</button>
        <button class="btn btn-secondary btn-sm" onclick="openReview(${a.id})" style="margin-left:4px;">👁️ Review</button>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

async function handleQuickGenerate(e) {
  e.preventDefault();
  const input = document.getElementById('dashboard-title-input');
  const title = input ? input.value.trim() : '';
  if (!title) return;
  if (input) input.value = '';
  await executeFullPipelineForTitle(title);
}

// ---------------- AI ARTICLE WRITING STUDIO (TAB: CREATE) ----------------
function ensureStudioLoaded() {
  if (!currentArticleData && allArticlesCache.length > 0) {
    loadArticleIntoStudio(allArticlesCache[0]);
  } else if (!currentArticleData) {
    initEmptyStudio();
  }
}

function initEmptyStudio() {
  currentArticleId = null;
  currentArticleData = {
    id: null,
    title: '',
    content: '',
    summary: '',
    status: 'DRAFT',
    keywords: [],
    featured_image: null,
    seo_metadata: {},
  };
  const titleInput = document.getElementById('editor-article-title');
  const contentArea = document.getElementById('editor-content-area');
  const rawHtml = document.getElementById('editor-raw-html');
  const topicInput = document.getElementById('studio-topic-input');
  if (titleInput) titleInput.value = '';
  if (contentArea) contentArea.innerHTML = '';
  if (rawHtml) rawHtml.value = '';
  if (topicInput) topicInput.value = '';
  updateWordCountAndReadingTime('');
  populateFeaturedImageUI(currentArticleData, []);
  renderPublicationPreview(currentArticleData);
}

function loadArticleIntoStudio(article) {
  currentArticleId = article.id;
  currentArticleData = article;

  const titleInput = document.getElementById('editor-article-title');
  const contentArea = document.getElementById('editor-content-area');
  const rawHtml = document.getElementById('editor-raw-html');
  const topicInput = document.getElementById('studio-topic-input');
  const seoTitle = document.getElementById('studio-seo-title');
  const audience = document.getElementById('studio-audience');
  const keywords = document.getElementById('studio-keywords');

  if (titleInput) titleInput.value = article.title || '';
  if (topicInput) topicInput.value = article.title || '';
  if (seoTitle) seoTitle.value = article.seo_metadata?.seo_title || article.title || '';
  if (audience) audience.value = article.target_audience || 'General Audience';
  if (keywords) keywords.value = (article.keywords || []).join(', ');

  const content = article.content || '';
  if (contentArea) {
    // If content looks like markdown, convert to HTML for visual editor
    if (content.startsWith('#') || content.includes('\n\n') || !content.includes('<p>')) {
      contentArea.innerHTML = renderMarkdownToHtml(content);
    } else {
      contentArea.innerHTML = sanitizeHtml(content);
    }
  }
  if (rawHtml) rawHtml.value = content;

  updateWordCountAndReadingTime(content);
  populateFeaturedImageUI(article, currentImageCandidates);
  renderPublicationPreview(article);
  setAutosaveStatus('saved', 'All changes saved');
}

function openStudioForArticle(articleId) {
  const found = allArticlesCache.find(a => a.id === articleId);
  if (found) {
    loadArticleIntoStudio(found);
  } else {
    API.getArticle(articleId).then(a => {
      loadArticleIntoStudio(a);
    }).catch(err => showToast(err.message, 'error'));
  }
  switchTab('create');
  switchStudioMode('edit');
}

function openStudioForCurrentArticle() {
  if (currentArticleId) {
    openStudioForArticle(currentArticleId);
  } else {
    switchTab('create');
  }
}

function switchStudioMode(mode) {
  const btnEdit = document.getElementById('btn-studio-edit');
  const btnPreview = document.getElementById('btn-studio-preview');
  const editView = document.getElementById('studio-edit-view');
  const previewView = document.getElementById('studio-preview-view');
  const imageSection = document.getElementById('studio-featured-image-section');

  if (mode === 'preview') {
    btnEdit?.classList.remove('active');
    btnPreview?.classList.add('active');
    if (editView) editView.style.display = 'none';
    if (imageSection) imageSection.style.display = 'none';
    if (previewView) previewView.style.display = 'block';
    refreshStudioPreview();
  } else {
    btnPreview?.classList.remove('active');
    btnEdit?.classList.add('active');
    if (previewView) previewView.style.display = 'none';
    if (editView) editView.style.display = 'flex';
    if (imageSection) imageSection.style.display = 'block';
  }
}

function toggleConfigDrawer() {
  const body = document.getElementById('config-drawer-body');
  const arrow = document.getElementById('config-drawer-arrow');
  if (!body) return;
  const isHidden = body.style.display === 'none';
  body.style.display = isHidden ? 'grid' : 'none';
  if (arrow) arrow.innerText = isHidden ? '▼' : '▲';
}

// ---------------- RICH EDITOR FORMATTING CONTROLS ----------------
function execEditorFormat(command, value = null) {
  const contentArea = document.getElementById('editor-content-area');
  if (!contentArea) return;
  contentArea.focus();
  document.execCommand(command, false, value);
  handleEditorContentChange();
}

function execEditorHeading(level) {
  execEditorFormat('formatBlock', `<${level}>`);
}

function execEditorBlockquote() {
  execEditorFormat('formatBlock', '<blockquote>');
}

function execEditorCodeBlock() {
  execEditorFormat('formatBlock', '<pre>');
}

function execEditorLink() {
  const url = prompt('Enter link URL (e.g. https://example.com):');
  if (url) {
    execEditorFormat('createLink', url);
  }
}

function execEditorClearFormat() {
  execEditorFormat('removeFormat');
}

function toggleRawHtmlMode() {
  const contentArea = document.getElementById('editor-content-area');
  const rawHtml = document.getElementById('editor-raw-html');
  const btn = document.getElementById('btn-toggle-raw-html');

  if (!isRawHtmlMode) {
    // Switch to Raw HTML
    if (rawHtml && contentArea) {
      rawHtml.value = contentArea.innerHTML;
      contentArea.style.display = 'none';
      rawHtml.style.display = 'block';
      rawHtml.focus();
    }
    if (btn) btn.classList.add('active');
    isRawHtmlMode = true;
  } else {
    // Switch to Visual WYSIWYG
    if (rawHtml && contentArea) {
      contentArea.innerHTML = rawHtml.value;
      rawHtml.style.display = 'none';
      contentArea.style.display = 'block';
      contentArea.focus();
    }
    if (btn) btn.classList.remove('active');
    isRawHtmlMode = false;
  }
}

function handleEditorContentChange() {
  setAutosaveStatus('unsaved', 'Unsaved changes');
  const contentArea = document.getElementById('editor-content-area');
  const text = contentArea ? contentArea.innerText : '';
  updateWordCountAndReadingTime(text);

  // Debounced autosave
  clearTimeout(autosaveTimer);
  autosaveTimer = setTimeout(() => {
    autoSaveArticle();
  }, 2500);
}

function handleRawHtmlChange(val) {
  setAutosaveStatus('unsaved', 'Unsaved changes');
  updateWordCountAndReadingTime(val.replace(/<[^>]+>/g, ' '));
  clearTimeout(autosaveTimer);
  autosaveTimer = setTimeout(() => {
    autoSaveArticle();
  }, 2500);
}

function handleArticleTitleChange(val) {
  setAutosaveStatus('unsaved', 'Unsaved changes');
  if (currentArticleData) currentArticleData.title = val;
  clearTimeout(autosaveTimer);
  autosaveTimer = setTimeout(() => {
    autoSaveArticle();
  }, 2500);
}

function handleEditorBlur() {
  autoSaveArticle();
}

function updateWordCountAndReadingTime(text) {
  const words = (text || '').trim().split(/\s+/).filter(Boolean).length;
  const readMins = Math.max(1, Math.ceil(words / 220));

  const elWords = document.getElementById('editor-word-count');
  const elRead = document.getElementById('editor-read-time');
  if (elWords) elWords.innerText = words.toLocaleString();
  if (elRead) elRead.innerText = `${readMins} min`;
}

function setAutosaveStatus(state, msg) {
  const indicator = document.getElementById('studio-autosave-indicator');
  const text = document.getElementById('studio-autosave-text');
  if (!indicator || !text) return;

  indicator.className = `autosave-status ${state}`;
  text.innerText = msg;
}

async function autoSaveArticle() {
  const title = document.getElementById('editor-article-title')?.value?.trim();
  const contentArea = document.getElementById('editor-content-area');
  const rawHtml = document.getElementById('editor-raw-html');
  const content = isRawHtmlMode ? (rawHtml?.value || '') : (contentArea?.innerHTML || '');

  if (!title && !content) return;

  setAutosaveStatus('saving', 'Saving...');

  try {
    if (currentArticleId) {
      await API.updateArticle(currentArticleId, {
        title: title || 'Untitled Article',
        content: content,
        revision_summary: 'Autosave in Writing Studio',
      });
      if (currentArticleData) {
        currentArticleData.title = title;
        currentArticleData.content = content;
      }
    }
    setAutosaveStatus('saved', 'Saved just now');
  } catch (err) {
    setAutosaveStatus('unsaved', 'Failed to autosave');
    console.warn('Autosave failed:', err);
  }
}

// ---------------- AI WRITING ASSISTANT ACTIONS ----------------
async function handleAIAssistAction(action) {
  const contentArea = document.getElementById('editor-content-area');
  const title = document.getElementById('editor-article-title')?.value || '';
  const selection = window.getSelection();
  const selectedText = selection ? selection.toString().trim() : '';
  const fullContent = contentArea ? contentArea.innerText : '';

  showToast(`Running AI Assistant (${action})...`, 'info');

  try {
    const payload = {
      action: action,
      title: title,
      content: fullContent,
      selected_text: selectedText || (action === 'improve' || action === 'rewrite' || action === 'expand' || action === 'shorten' ? fullContent.slice(0, 1000) : ''),
      target_audience: document.getElementById('studio-audience')?.value || 'General Audience',
    };

    const res = await API.aiAssist(payload);
    const result = res.result;

    if (action === 'suggest_titles') {
      showTitlesSuggestionModal(result);
    } else if (action === 'suggest_keywords') {
      const kwInput = document.getElementById('studio-keywords');
      if (kwInput) kwInput.value = result;
      showToast('Keywords updated in Generator parameters!', 'success');
    } else if (action === 'meta_description') {
      const seoDesc = document.getElementById('seo-description');
      if (seoDesc) seoDesc.innerText = result;
      showToast(`Meta Description Generated: "${result}"`, 'success');
      alert(`Generated Meta Description:\n\n${result}`);
    } else if (action === 'generate_toc') {
      // Insert TOC at cursor or at top of contentArea
      insertHtmlIntoEditor(`\n<div class="toc-box" style="background:var(--bg-surface-elevated); border:1px solid var(--border-subtle); border-radius:8px; padding:16px; margin:20px 0;">\n${renderMarkdownToHtml(result)}\n</div>\n`);
    } else if (action === 'fact_check') {
      showFactCheckModal(result);
    } else {
      // improve, rewrite, expand, shorten, regenerate_section
      if (selectedText && selection.rangeCount > 0) {
        const range = selection.getRangeAt(0);
        range.deleteContents();
        range.insertNode(document.createTextNode(result));
        showToast('Text updated in place!', 'success');
      } else {
        insertHtmlIntoEditor(`<p>${result}</p>`);
        showToast('AI suggestion appended to editor.', 'success');
      }
      handleEditorContentChange();
    }
  } catch (err) {
    showToast(`AI Assistant error: ${err.message}`, 'error');
  }
}

function showFactCheckModal(factCheckText) {
  const modal = document.createElement('div');
  modal.className = 'modal-overlay active';
  modal.innerHTML = `
    <div class="modal-content" style="max-width:600px; padding:24px;">
      <div class="modal-header" style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
        <h3 style="margin:0; font-size:16px; display:flex; align-items:center; gap:8px;">
          <span>🔍</span> Factual Verification & Quality Audit
        </h3>
        <button class="btn btn-secondary btn-sm" onclick="this.closest('.modal-overlay').remove()">✕</button>
      </div>
      <div style="background:var(--bg-surface-elevated); padding:16px; border-radius:var(--radius-md); border:1px solid var(--border-subtle); font-size:13px; line-height:1.6; white-space:pre-wrap; max-height:400px; overflow-y:auto; color:var(--text-primary);">
${escapeHtml(factCheckText)}
      </div>
      <div style="display:flex; justify-content:flex-end; margin-top:16px;">
        <button class="btn btn-primary btn-sm" onclick="this.closest('.modal-overlay').remove()">Close Audit</button>
      </div>
    </div>
  `;
  document.body.appendChild(modal);
}

function insertHtmlIntoEditor(html) {
  const contentArea = document.getElementById('editor-content-area');
  if (!contentArea) return;
  contentArea.focus();
  document.execCommand('insertHTML', false, html);
  handleEditorContentChange();
}

function showTitlesSuggestionModal(titlesText) {
  const lines = titlesText.split('\n').filter(l => l.trim().length > 0);
  let html = '<div style="font-size:13px; line-height:1.6; margin-bottom:14px;">Click any title below to apply it to your article:</div><div style="display:flex; flex-direction:column; gap:8px;">';

  lines.forEach(l => {
    const clean = l.replace(/^\d+[\.\)]\s*/, '').replace(/^["']|["']$/g, '').trim();
    html += `<button type="button" class="btn btn-secondary btn-sm" style="text-align:left; justify-content:flex-start; padding:10px 14px;" onclick="applySuggestedTitle('${escapeAttr(clean)}')">📌 ${escapeHtml(clean)}</button>`;
  });
  html += '</div>';

  const modal = document.createElement('div');
  modal.className = 'modal-overlay active';
  modal.innerHTML = `
    <div class="modal-content" style="max-width:520px;">
      <div class="modal-header">
        <div class="card-title">💡 Suggested Article Titles</div>
        <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">×</button>
      </div>
      ${html}
    </div>
  `;
  document.body.appendChild(modal);
}

function applySuggestedTitle(title) {
  const titleInput = document.getElementById('editor-article-title');
  const seoTitle = document.getElementById('studio-seo-title');
  if (titleInput) titleInput.value = title;
  if (seoTitle) seoTitle.value = title;
  handleArticleTitleChange(title);
  document.querySelectorAll('.modal-overlay').forEach(m => m.remove());
  showToast(`Title applied: "${title}"`, 'success');
}

// ---------------- COMPLETE ARTICLE GENERATION ----------------
async function handleStudioGenerateFullArticle() {
  const topic = document.getElementById('studio-topic-input')?.value?.trim();
  const seoTitle = document.getElementById('studio-seo-title')?.value?.trim();
  const audience = document.getElementById('studio-audience')?.value?.trim();
  const tone = document.getElementById('studio-tone')?.value;
  const length = document.getElementById('studio-length')?.value;
  const intent = document.getElementById('studio-intent')?.value;
  const kwStr = document.getElementById('studio-keywords')?.value || '';
  const instructions = document.getElementById('studio-instructions')?.value || '';

  const cleanTitle = topic || seoTitle;
  if (!cleanTitle) {
    showToast('Please enter an article topic or title.', 'warning');
    return;
  }

  const keywords = kwStr.split(',').map(s => s.trim()).filter(Boolean);

  const payload = {
    custom_title: cleanTitle,
    target_audience: audience || 'General Audience',
    search_intent: intent || 'Informational',
    desired_length: length || 'medium (~1500w)',
    keywords: keywords,
  };

  await executeFullPipelineWithPayload(payload);
}

async function executeFullPipelineForTitle(title) {
  await executeFullPipelineWithPayload({ custom_title: title.trim() });
}

async function executeFullPipelineWithPayload(payload) {
  // Pre-flight check
  try {
    const aiStatus = await API.getAIStatus();
    if (aiStatus.ai_generation_mode === 'online') {
      if (!aiStatus.internet_connected) {
        const offMsg = "You're offline. Connect to the internet or switch to Offline AI and connect Ollama.";
        showToast(offMsg, 'error');
        alert(offMsg);
        switchTab('settings');
        return;
      }
      if (!aiStatus.gemini?.healthy) {
        const keyMsg = aiStatus.gemini?.message || "Gemini API key is not configured or invalid. Please check Settings.";
        showToast(keyMsg, 'error');
        alert(keyMsg);
        switchTab('settings');
        return;
      }
    } else if (aiStatus.ai_generation_mode === 'offline') {
      if (!aiStatus.ollama?.healthy) {
        const ollamaMsg = aiStatus.ollama?.message || "Ollama is not running. Please start Ollama before generating.";
        showToast(ollamaMsg, 'error');
        alert(ollamaMsg);
        switchTab('settings');
        return;
      }
    }
  } catch (checkErr) {
    console.warn('Pre-generation status check error:', checkErr);
  }

  const title = payload.custom_title || 'New Article';
  showToast(`Generating complete article for "${title}"...`, 'info');
  const overlay = document.getElementById('loading-overlay');
  overlay?.classList.add('active');

  const updateLoadingStep = (step) => {
    for (let i = 1; i <= 5; i++) {
      const el = document.getElementById(`load-step-${i}`);
      if (!el) continue;
      if (i < step) {
        el.style.color = 'var(--success)';
        el.innerText = el.innerText.replace(/^[○●✓]\s*/, '✓ ');
      } else if (i === step) {
        el.style.color = 'var(--accent)';
        el.style.fontWeight = '600';
        el.innerText = el.innerText.replace(/^[○●✓]\s*/, '● ');
      } else {
        el.style.color = 'var(--text-secondary)';
        el.style.fontWeight = 'normal';
        el.innerText = el.innerText.replace(/^[○●✓]\s*/, '○ ');
      }
    }
  };

  updateLoadingStep(1);
  let currentStep = 1;
  const stepTimer = setInterval(() => {
    if (currentStep < 4) {
      currentStep++;
      updateLoadingStep(currentStep);
    }
  }, 4000);

  try {
    const article = await API.startWorkflow(payload);
    clearInterval(stepTimer);
    updateLoadingStep(5);

    showToast('Complete article generated successfully!', 'success');
    setTimeout(() => {
      overlay?.classList.remove('active');
      allArticlesCache.unshift(article);
      loadArticleIntoStudio(article);
      switchTab('create');
      switchStudioMode('edit');
    }, 450);
  } catch (err) {
    clearInterval(stepTimer);
    overlay?.classList.remove('active');
    const errMsg = err.message || 'Generation failed';
    showToast(`Generation failed: ${errMsg}`, 'error');
    if (confirm(`Article Generation Failed:\n\n${errMsg}\n\nWould you like to retry?`)) {
      executeFullPipelineWithPayload(payload);
    }
  }
}

// ---------------- PRIMARY STUDIO ACTIONS ----------------
async function handleStudioSaveDraft() {
  await autoSaveArticle();
  showToast('Draft saved locally!', 'success');
}

function handleStudioQualityAudit() {
  if (currentArticleId) {
    openReview(currentArticleId);
  } else {
    showToast('Please generate or save an article first.', 'warning');
  }
}

async function handleStudioPushDraft() {
  if (!currentArticleId) {
    showToast('Please save or generate an article first.', 'warning');
    return;
  }
  await autoSaveArticle();

  showToast('Pushing draft to Blogger...', 'info');
  try {
    const res = await API.createBloggerDraft(currentArticleId);
    showToast(`Blogger Draft created successfully! Post ID: ${res.post_id}`, 'success');
    if (currentArticleData) {
      currentArticleData.blogger_post_id = res.post_id;
      currentArticleData.blogger_draft_url = res.post_url;
      currentArticleData.status = 'APPROVED';
    }
    openReview(currentArticleId);
  } catch (err) {
    showToast(`Draft push failed: ${err.message}`, 'error');
  }
}

async function handleStudioPublishLive() {
  if (!currentArticleId) {
    showToast('Please save or generate an article first.', 'warning');
    return;
  }
  if (!confirm('Are you sure you want to publish this article LIVE on Google Blogger?')) return;

  await autoSaveArticle();
  showToast('Publishing live post to Blogger...', 'info');

  try {
    const res = await API.publishBloggerPost(currentArticleId, null, true);
    showToast(res.message || 'Article is now LIVE on Blogger!', 'success');
    if (currentArticleData) {
      currentArticleData.status = 'PUBLISHED';
    }
    openReview(currentArticleId);
  } catch (err) {
    showToast(`Publish failed: ${err.message}`, 'error');
  }
}

// ---------------- PUBLICATION PREVIEW REFRESH ----------------
function refreshStudioPreview() {
  if (!currentArticleData) return;
  const title = document.getElementById('editor-article-title')?.value || currentArticleData.title;
  const contentArea = document.getElementById('editor-content-area');
  const rawHtml = document.getElementById('editor-raw-html');
  const content = isRawHtmlMode ? (rawHtml?.value || '') : (contentArea?.innerHTML || currentArticleData.content);

  const previewObj = {
    ...currentArticleData,
    title: title,
    content: content,
  };
  renderPublicationPreview(previewObj);
}

// ---------------- ALL ARTICLES / DRAFTS / PUBLISHED VIEWS ----------------
async function loadArticles() {
  try {
    const articles = await API.getArticles();
    allArticlesCache = articles || [];
    filterAndRenderArticles();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

function filterArticlesByStatus(status, btnElement) {
  currentFilterStatus = status;
  if (btnElement) {
    document.querySelectorAll('.filter-tab').forEach(b => b.classList.remove('active', 'btn-primary'));
    document.querySelectorAll('.filter-tab').forEach(b => b.classList.add('btn-secondary'));
    btnElement.classList.add('active', 'btn-primary');
    btnElement.classList.remove('btn-secondary');
  }
  filterAndRenderArticles();
}

function handleArticleSearchFilter(query) {
  currentSearchQuery = (query || '').toLowerCase().trim();
  filterAndRenderArticles();
}

function handleArticleSortChange(sortBy) {
  if (!allArticlesCache) return;
  if (sortBy === 'updated_desc') {
    allArticlesCache.sort((a, b) => new Date(b.updated_at || 0) - new Date(a.updated_at || 0));
  } else if (sortBy === 'created_desc') {
    allArticlesCache.sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0));
  } else if (sortBy === 'score_desc') {
    allArticlesCache.sort((a, b) => (b.overall_quality_score || 0) - (a.overall_quality_score || 0));
  } else if (sortBy === 'title_asc') {
    allArticlesCache.sort((a, b) => (a.title || '').localeCompare(b.title || ''));
  }
  filterAndRenderArticles();
}

function filterAndRenderArticles() {
  const tbody = document.getElementById('articles-table');
  if (!tbody) return;

  let filtered = allArticlesCache;

  // Filter status
  if (currentFilterStatus !== 'ALL') {
    filtered = filtered.filter(a => a.status === currentFilterStatus);
  }

  // Filter search query
  if (currentSearchQuery) {
    filtered = filtered.filter(a =>
      (a.title || '').toLowerCase().includes(currentSearchQuery) ||
      (a.summary || '').toLowerCase().includes(currentSearchQuery) ||
      (a.keywords || []).some(k => k.toLowerCase().includes(currentSearchQuery))
    );
  }

  tbody.innerHTML = '';

  if (filtered.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; color: var(--text-secondary); padding:24px;">No matching articles found.</td></tr>';
    return;
  }

  filtered.forEach(a => {
    const score = a.overall_quality_score != null ? `${Math.round(a.overall_quality_score)}/100` : 'Pending';
    const postDraft = a.blogger_post_id ? `<span style="color:var(--success)">#${a.blogger_post_id.slice(-6)}</span>` : 'Local';
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><strong>${escapeHtml(a.title)}</strong></td>
      <td><span class="status-badge status-${a.status}">${a.status}</span></td>
      <td><strong>${score}</strong></td>
      <td>${a.revisions ? a.revisions.length : 1}</td>
      <td>${postDraft}</td>
      <td style="white-space:nowrap;">
        <button class="btn btn-primary btn-sm" onclick="openStudioForArticle(${a.id})">✍️ Edit</button>
        <button class="btn btn-secondary btn-sm" onclick="openReview(${a.id})" style="margin-left:4px;">👁️ Review</button>
        <button class="btn btn-danger btn-sm" onclick="handleDeleteArticle(${a.id})" style="margin-left:4px;" title="Delete">🗑️</button>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

async function loadDrafts() {
  const tbody = document.getElementById('drafts-table');
  if (!tbody) return;
  tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;">Loading drafts...</td></tr>';
  try {
    const articles = await API.getArticles();
    allArticlesCache = articles;
    const drafts = articles.filter(a => a.status === 'DRAFT' || a.status === 'IDEA' || a.status === 'READY_FOR_APPROVAL');
    tbody.innerHTML = '';
    if (drafts.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; color: var(--text-secondary); padding:24px;">No active drafts. Click "+ New Draft" to create one.</td></tr>';
      return;
    }
    drafts.forEach(a => {
      const score = a.overall_quality_score != null ? `${Math.round(a.overall_quality_score)}/100` : 'Pending';
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><strong>${escapeHtml(a.title)}</strong></td>
        <td><span class="status-badge status-${a.status}">${a.status}</span></td>
        <td><strong>${score}</strong></td>
        <td>${a.revisions ? a.revisions.length : 1}</td>
        <td>${a.blogger_post_id ? `#${a.blogger_post_id.slice(-6)}` : 'None'}</td>
        <td style="white-space:nowrap;">
          <button class="btn btn-primary btn-sm" onclick="openStudioForArticle(${a.id})">✍️ Edit</button>
          <button class="btn btn-secondary btn-sm" onclick="openReview(${a.id})" style="margin-left:4px;">Review</button>
        </td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function loadPublished() {
  const tbody = document.getElementById('published-table');
  if (!tbody) return;
  tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;">Loading published posts...</td></tr>';
  try {
    const articles = await API.getArticles('PUBLISHED');
    tbody.innerHTML = '';
    if (!articles || articles.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; color: var(--text-secondary); padding:24px;">No published articles yet. Push an approved draft to Blogger to publish.</td></tr>';
      return;
    }
    articles.forEach(a => {
      const score = a.overall_quality_score != null ? `${Math.round(a.overall_quality_score)}/100` : 'N/A';
      const dateStr = a.updated_at ? new Date(a.updated_at).toLocaleDateString() : 'Recent';
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><strong>${escapeHtml(a.title)}</strong></td>
        <td><span class="status-badge status-PUBLISHED">LIVE</span></td>
        <td><strong>${score}</strong></td>
        <td><code>${a.blogger_post_id || '-'}</code></td>
        <td>${dateStr}</td>
        <td style="white-space:nowrap;">
          <button class="btn btn-secondary btn-sm" onclick="openReview(${a.id})">View Post ↗</button>
        </td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function handleDeleteArticle(articleId) {
  if (!confirm(`Are you sure you want to delete article #${articleId}? This cannot be undone.`)) return;

  try {
    showToast('Deleting article...', 'info');
    await API.deleteArticle(articleId);
    showToast('Article deleted successfully!', 'success');
    allArticlesCache = allArticlesCache.filter(a => a.id !== articleId);
    filterAndRenderArticles();
    loadDashboard();
    if (currentArticleId === articleId) {
      initEmptyStudio();
    }
  } catch (err) {
    showToast(`Failed to delete article: ${err.message}`, 'error');
  }
}

async function handleDeleteCurrentArticle() {
  if (!currentArticleId) return;
  handleDeleteArticle(currentArticleId);
}

// ---------------- TEMPLATES ----------------
function applyTemplate(templateKey) {
  const blueprints = {
    how_to: {
      topic: 'How to Build Real-Time Applications with WebSockets: Complete Guide',
      audience: 'Web Developers & Full-Stack Engineers',
      tone: 'Educational & Beginner-Friendly',
      length: 'medium (~1500w)',
      intent: 'Informational',
      keywords: 'websockets, real-time web, socket programming, architecture, tutorial',
      instructions: '1. Prerequisites & Tooling\n2. Fundamentals of Two-Way Communication\n3. Step-by-Step Server Setup\n4. Client Implementation & Reconnection Handling\n5. Production Benchmarking & Pitfalls\n6. Frequently Asked Questions',
    },
    deep_dive: {
      topic: 'Deep Architectural Breakdown: Modern Distributed Database Engines',
      audience: 'Senior Engineers & System Architects',
      tone: 'Technical & Analytical',
      length: 'long (~2500w)',
      intent: 'Informational',
      keywords: 'distributed systems, consensus, raft algorithm, storage engines, scalability',
      instructions: 'Include formal state diagrams, trade-off matrix, consensus protocol explanation, write-path vs read-path benchmarks, and failure mode recovery.',
    },
    comparison: {
      topic: 'PostgreSQL vs SQLite for Edge Applications: 2026 In-Depth Comparison',
      audience: 'Software Engineers & CTOs',
      tone: 'Professional & Authoritative',
      length: 'medium (~1500w)',
      intent: 'Commercial',
      keywords: 'postgresql, sqlite, edge computing, database comparison, performance',
      instructions: 'Include side-by-side feature comparison table, latency benchmarks, memory footprint analysis, deployment complexity, and exact persona recommendations.',
    },
    listicle: {
      topic: '7 High-Impact Frontend Performance Optimizations Every Developer Should Know',
      audience: 'Frontend Developers & Web Performance Engineers',
      tone: 'Conversational & Engaging',
      length: 'short (~800w)',
      intent: 'Informational',
      keywords: 'frontend performance, web vitals, bundle size, caching, speed optimization',
      instructions: 'Give concrete actionable takeaways for each of the 7 items. Include real metrics (LCP, INP, CLS) and short code snippets.',
    },
    trends: {
      topic: 'Top 5 Architectural Shifts Shaping Enterprise Software in 2026',
      audience: 'Tech Leaders, Architects & Developers',
      tone: 'Professional & Authoritative',
      length: 'medium (~1500w)',
      intent: 'Informational',
      keywords: 'software trends, ai engineering, microservices, cloud infrastructure',
      instructions: 'Ground the discussion in real industry data. Analyze historical precedents, current adoption curves, and 3-year outlook.',
    },
    case_study: {
      topic: 'How We Reduced API P99 Latency from 800ms to 45ms Under Heavy Load',
      audience: 'Backend Developers & SREs',
      tone: 'Storytelling & Narrative',
      length: 'medium (~1500w)',
      intent: 'Informational',
      keywords: 'latency optimization, profiling, redis caching, database queries, backend',
      instructions: 'Structure as Problem Statement -> Root Cause Identification -> Failed Experiments -> The Winning Fix -> Measurable Results.',
    },
  };

  const bp = blueprints[templateKey];
  if (!bp) return;

  switchTab('create');
  switchStudioMode('edit');

  const topicInput = document.getElementById('studio-topic-input');
  const seoTitle = document.getElementById('studio-seo-title');
  const audience = document.getElementById('studio-audience');
  const tone = document.getElementById('studio-tone');
  const length = document.getElementById('studio-length');
  const intent = document.getElementById('studio-intent');
  const keywords = document.getElementById('studio-keywords');
  const instructions = document.getElementById('studio-instructions');

  if (topicInput) topicInput.value = bp.topic;
  if (seoTitle) seoTitle.value = bp.topic;
  if (audience) audience.value = bp.audience;
  if (tone) tone.value = bp.tone;
  if (length) length.value = bp.length;
  if (intent) intent.value = bp.intent;
  if (keywords) keywords.value = bp.keywords;
  if (instructions) instructions.value = bp.instructions;

  // Open the configuration drawer
  const drawerBody = document.getElementById('config-drawer-body');
  if (drawerBody) drawerBody.style.display = 'grid';

  showToast(`Applied ${templateKey.toUpperCase()} Blueprint! Click 'Generate Complete Article' to run.`, 'success');
}

// ---------------- CONTENT LIBRARY (SOURCES & TOPICS) ----------------
function switchContentLibraryTab(mode) {
  const btnSources = document.getElementById('subtab-sources-btn');
  const btnTopics = document.getElementById('subtab-topics-btn');
  const pnlSources = document.getElementById('content-lib-sources-panel');
  const pnlTopics = document.getElementById('content-lib-topics-panel');

  if (mode === 'topics') {
    btnSources?.classList.replace('btn-primary', 'btn-secondary');
    btnTopics?.classList.replace('btn-secondary', 'btn-primary');
    if (pnlSources) pnlSources.style.display = 'none';
    if (pnlTopics) pnlTopics.style.display = 'block';
    loadTopics();
  } else {
    btnTopics?.classList.replace('btn-primary', 'btn-secondary');
    btnSources?.classList.replace('btn-secondary', 'btn-primary');
    if (pnlTopics) pnlTopics.style.display = 'none';
    if (pnlSources) pnlSources.style.display = 'block';
    loadResearch();
  }
}

async function loadResearch() {
  try {
    const sources = await API.getResearchSources();
    const tbody = document.getElementById('sources-table');
    if (!tbody) return;
    tbody.innerHTML = '';
    if (!sources || sources.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; color: var(--text-secondary); padding:24px;">No research sources cataloged yet. Generating an article will automatically conduct online research and cite sources here.</td></tr>';
      return;
    }
    sources.forEach(s => {
      const tr = document.createElement('tr');
      const verified = s.is_verified ? '<span class="status-badge status-APPROVED">VERIFIED</span>' : '<span class="status-badge status-FACT_CHECK">UNVERIFIED</span>';
      const facts = (s.relevant_facts || []).slice(0, 2).join(' • ') || s.notes || 'Ground truth data verified.';
      tr.innerHTML = `
        <td><strong>${escapeHtml(s.title)}</strong></td>
        <td><a href="${s.url}" target="_blank" style="color:var(--accent);">${escapeHtml(s.domain || s.url)} ↗</a></td>
        <td style="font-size:12px; color:var(--text-secondary);">${escapeHtml(facts)}</td>
        <td>${verified}</td>
        <td>${s.publication_date || 'Recent'}</td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function loadTopics() {
  try {
    const topics = await API.getTopics();
    const tbody = document.getElementById('topics-table');
    if (!tbody) return;
    tbody.innerHTML = '';
    if (!topics || topics.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; color: var(--text-secondary); padding:24px;">No topics in queue. Click "New Topic" or "Seed Demo Topic" above.</td></tr>';
      return;
    }
    topics.forEach(t => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><strong>${escapeHtml(t.title)}</strong></td>
        <td>${t.search_intent}</td>
        <td>${t.target_audience}</td>
        <td><span class="status-badge" style="background:var(--accent-light); color:var(--accent);">${t.priority}</span></td>
        <td><span class="status-badge status-${t.status}">${t.status}</span></td>
        <td style="white-space:nowrap;">
          <button class="btn btn-primary btn-sm" onclick="startWorkflowFromTopic(${t.id})">Generate Draft</button>
          <button class="btn btn-danger btn-sm" onclick="handleDeleteTopic(${t.id})" style="margin-left:6px;" title="Delete">🗑️</button>
        </td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function startWorkflowFromTopic(topicId) {
  showToast('Starting autonomous pipeline from topic...', 'info');
  document.getElementById('loading-overlay')?.classList.add('active');
  try {
    const article = await API.startWorkflow({ topic_id: topicId });
    showToast('Article generated from topic!', 'success');
    document.getElementById('loading-overlay')?.classList.remove('active');
    allArticlesCache.unshift(article);
    loadArticleIntoStudio(article);
    switchTab('create');
  } catch (err) {
    document.getElementById('loading-overlay')?.classList.remove('active');
    showToast(`Generation failed: ${err.message}`, 'error');
  }
}

async function handleDeleteTopic(topicId) {
  if (!confirm(`Are you sure you want to delete topic #${topicId}?`)) return;
  try {
    await API.deleteTopic(topicId);
    showToast('Topic deleted!', 'success');
    loadTopics();
  } catch (err) {
    showToast(`Failed: ${err.message}`, 'error');
  }
}

async function handleCreateTopic(e) {
  e.preventDefault();
  const form = e.target;
  const kw = form.keywords.value.split(',').map(s => s.trim()).filter(Boolean);
  const payload = {
    title: form.title.value,
    target_audience: form.target_audience.value,
    country_region: form.country_region.value,
    search_intent: form.search_intent.value,
    desired_length: form.desired_length.value,
    keywords: kw,
    priority: form.priority.value,
    notes: form.notes.value,
  };

  try {
    await API.createTopic(payload);
    showToast('Topic created successfully!', 'success');
    closeModal('topic-modal');
    form.reset();
    loadTopics();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function handleSeedDemoTopic() {
  try {
    await API.seedDemoTopic();
    showToast('Authoritative demo topic seeded!', 'success');
    loadTopics();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function handleSeedDemoArticle() {
  showToast('Synthesizing verified demo article pipeline...', 'info');
  document.getElementById('loading-overlay')?.classList.add('active');
  try {
    const article = await API.seedDemoArticle();
    showToast('Demo article ready!', 'success');
    document.getElementById('loading-overlay')?.classList.remove('active');
    allArticlesCache.unshift(article);
    loadArticleIntoStudio(article);
    switchTab('create');
  } catch (err) {
    document.getElementById('loading-overlay')?.classList.remove('active');
    showToast(err.message, 'error');
  }
}

// ---------------- PUBLISHING HISTORY & TOKEN USAGE ----------------
async function loadPublishingHistory() {
  try {
    const history = await API.getPublishingHistory();
    const tbody = document.getElementById('publishing-history-table');
    if (!tbody) return;
    tbody.innerHTML = '';
    if (!history || history.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; color: var(--text-secondary); padding:24px;">No publishing records in database yet. Draft and publish actions will appear here.</td></tr>';
      return;
    }
    history.forEach(h => {
      const tr = document.createElement('tr');
      const actionBadge = h.action === 'PUBLISH' ? '<span class="status-badge status-PUBLISHED">LIVE PUBLISH</span>' : '<span class="status-badge status-DRAFT">CREATE DRAFT</span>';
      const statusBadge = h.status === 'SUCCESS' ? '<span class="status-badge status-APPROVED">SUCCESS</span>' : '<span class="status-badge status-FAILED">FAILED</span>';
      const dateStr = h.created_at ? new Date(h.created_at).toLocaleString() : '-';
      const link = h.post_url ? `<a href="${h.post_url}" target="_blank" style="color:var(--accent);">View on Blogger ↗</a>` : (h.error_message || 'OK');
      tr.innerHTML = `
        <td><strong>${escapeHtml(h.article_title || 'Article #' + h.article_id)}</strong></td>
        <td>${actionBadge}</td>
        <td>${statusBadge}</td>
        <td><code>${h.blogger_post_id || '-'}</code></td>
        <td>${dateStr}</td>
        <td>${link}</td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    showToast(err.message, 'error');
  }

  loadLogs();
}

async function loadLogs() {
  try {
    const logs = await API.getLogs();
    const usage = logs.usage_summary || {};
    document.getElementById('logs-calls').innerText = usage.total_calls || 0;
    document.getElementById('logs-prompt-tokens').innerText = (usage.prompt_tokens_est || 0).toLocaleString();
    document.getElementById('logs-completion-tokens').innerText = (usage.completion_tokens_est || 0).toLocaleString();
    document.getElementById('logs-cost').innerText = `$${(usage.estimated_cost_usd || 0).toFixed(4)}`;

    const tbody = document.getElementById('logs-runs-table');
    if (!tbody) return;
    tbody.innerHTML = '';
    const runs = logs.recent_runs || [];
    if (runs.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; color: var(--text-secondary);">No logs recorded.</td></tr>';
      return;
    }
    runs.forEach(r => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><strong>${r.agent_name}</strong></td>
        <td><span class="status-badge status-${r.status}">${r.status}</span></td>
        <td>${r.execution_time_seconds}s</td>
        <td>${((r.input_tokens_est || 0) + (r.output_tokens_est || 0)).toLocaleString()}</td>
        <td>${r.created_at ? new Date(r.created_at).toLocaleTimeString() : '-'}</td>
        <td style="color:var(--text-secondary);">${r.notes || '-'}</td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// ---------------- QUALITY GATE & REVIEW SCREEN ----------------
async function openReview(articleId) {
  currentArticleId = articleId;
  switchTab('review');

  try {
    const a = await API.getArticle(articleId);
    currentArticleData = a;

    document.getElementById('review-title').innerText = a.title;
    document.getElementById('review-status-badge').className = `status-badge status-${a.status}`;
    document.getElementById('review-status-badge').innerText = a.status;

    // Quality check scores
    const lastCheck = a.quality_checks && a.quality_checks.length > 0 ? a.quality_checks[0] : null;

    if (lastCheck) {
      document.getElementById('review-overall-score').innerText = `${Math.round(lastCheck.overall_score)}`;
      document.getElementById('qc-accuracy').innerText = lastCheck.factual_accuracy_score;
      document.getElementById('qc-usefulness').innerText = lastCheck.usefulness_score;
      document.getElementById('qc-originality').innerText = lastCheck.originality_score;
      document.getElementById('qc-readability').innerText = lastCheck.readability_score;
      document.getElementById('qc-intent').innerText = lastCheck.search_intent_match_score;
      document.getElementById('qc-seo').innerText = lastCheck.seo_quality_score;
      document.getElementById('qc-source').innerText = lastCheck.source_quality_score;

      // Fact-checks
      const fcList = document.getElementById('fact-check-list');
      fcList.innerHTML = '';
      (lastCheck.fact_check_results || []).forEach(f => {
        const row = document.createElement('div');
        row.style.padding = '8px 0';
        row.style.borderBottom = '1px solid var(--border-subtle)';
        const statusColor = f.status === 'SUPPORTED' ? 'var(--success)' : (f.status === 'UNCERTAIN' ? 'var(--warning)' : 'var(--danger)');
        row.innerHTML = `
          <div style="font-weight:600; color:${statusColor}; font-size:12px;">[${f.status}] ${escapeHtml(f.claim)}</div>
          <div style="font-size:11.5px; color:var(--text-secondary);">Source: ${escapeHtml(f.source)} | Reasoning: ${escapeHtml(f.reason)}</div>
        `;
        fcList.appendChild(row);
      });

      // Detected issues
      const issuesDiv = document.getElementById('detected-issues-list');
      issuesDiv.innerHTML = '';
      if (!lastCheck.detected_issues || lastCheck.detected_issues.length === 0) {
        issuesDiv.innerHTML = '<span style="color:var(--success)">✓ No critical quality or factual issues detected.</span>';
      } else {
        lastCheck.detected_issues.forEach(iss => {
          const div = document.createElement('div');
          div.style.color = 'var(--danger)';
          div.style.marginBottom = '4px';
          div.innerHTML = `⚠️ ${escapeHtml(iss)}`;
          issuesDiv.appendChild(div);
        });
      }
    } else {
      document.getElementById('review-overall-score').innerText = '--';
    }

    // SEO Metadata
    const seo = a.seo_metadata || {};
    document.getElementById('seo-title').innerText = seo.seo_title || a.title;
    document.getElementById('seo-slug').innerText = seo.url_slug || 'n/a';
    document.getElementById('seo-description').innerText = seo.meta_description || 'n/a';

    // Blogger status box
    const bloggerInfo = document.getElementById('blogger-draft-info');
    if (a.status === 'PUBLISHED') {
      bloggerInfo.innerHTML = `
        <div style="background:var(--success-bg); border: 1px solid var(--success-border); padding:16px; border-radius:var(--radius-md); margin-top:16px;">
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <div>
              <strong style="color:var(--success); font-size:14px;">✓ Live Published on Blogger!</strong><br>
              <span style="font-size:12px; color:var(--text-secondary);">Post ID: <code>${a.blogger_post_id}</code></span>
            </div>
            <a href="${a.blogger_draft_url || '#'}" target="_blank" class="btn btn-secondary btn-sm" style="color:var(--accent);">View Live Post ↗</a>
          </div>
        </div>
      `;
    } else if (a.blogger_post_id) {
      bloggerInfo.innerHTML = `
        <div style="background:var(--bg-surface-elevated); border: 1px solid var(--accent); padding:16px; border-radius:var(--radius-md); margin-top:16px;">
          <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;">
            <div>
              <strong style="color:var(--accent); font-size:14px;">📝 Blogger Draft Created & Staged</strong><br>
              <span style="font-size:12px; color:var(--text-secondary);">Post ID: <code>${a.blogger_post_id}</code></span>
            </div>
            <div style="display:flex; gap:10px;">
              <a href="${a.blogger_draft_url || '#'}" target="_blank" class="btn btn-secondary btn-sm">Edit in Blogger ↗</a>
              <button class="btn btn-success btn-sm" onclick="handlePublishLive(${a.id})">🚀 Publish Live</button>
            </div>
          </div>
        </div>
      `;
    } else {
      bloggerInfo.innerHTML = `
        <div style="background:var(--bg-surface-elevated); padding:12px 16px; border-radius:var(--radius-sm); margin-top:14px; border:1px dashed var(--border-subtle); font-size:12.5px; color:var(--text-secondary);">
          ℹ️ Not yet sent to Blogger. Click <strong>[✓ Approve (Push Blogger Draft)]</strong> above to send this post to your Blogger blog as a staged draft.
        </div>
      `;
    }

  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function submitApproval(decision) {
  if (!currentArticleId) return;
  if (decision === 'REVISION') {
    openModal('revision-modal');
    return;
  }

  showToast(`Submitting ${decision}...`, 'info');
  try {
    const res = await API.submitDecision(currentArticleId, decision);
    showToast(res.message || 'Decision processed!', 'success');
    openReview(currentArticleId);
    loadDashboard();
  } catch (err) {
    showToast(`Decision error: ${err.message}`, 'error');
  }
}

async function handleRevisionSubmit(e) {
  e.preventDefault();
  const feedback = document.getElementById('revision-feedback')?.value?.trim();
  if (!feedback || !currentArticleId) return;

  closeModal('revision-modal');
  showToast('Generating targeted editorial revision...', 'info');
  document.getElementById('loading-overlay')?.classList.add('active');

  try {
    const res = await API.submitDecision(currentArticleId, 'REVISION', feedback);
    showToast('Revision generated successfully!', 'success');
    document.getElementById('loading-overlay')?.classList.remove('active');
    openReview(currentArticleId);
  } catch (err) {
    document.getElementById('loading-overlay')?.classList.remove('active');
    showToast(`Revision failed: ${err.message}`, 'error');
  }
}

async function handlePublishLive(articleId) {
  if (!confirm("Are you sure you want to publish this article LIVE on your Blogger blog?")) return;
  showToast("Publishing draft to Blogger...", "info");
  try {
    const res = await API.publishBloggerPost(articleId, null, true);
    showToast(res.message || "Article is now LIVE on Blogger!", "success");
    openReview(articleId);
  } catch (err) {
    showToast(err.message, "error");
  }
}

// ---------------- FEATURED IMAGE UI & WEB IMAGE SEARCH ----------------
function populateFeaturedImageUI(article, candidates = []) {
  currentImageCandidates = candidates || [];
  const activeCard = document.getElementById('image-active-card');
  const btnRemove = document.getElementById('btn-remove-featured');
  const feat = article?.featured_image || article?.featuredImage || {};
  const imgUrl = feat.url || feat.imageUrl || feat.image || '';

  if (imgUrl) {
    if (activeCard) activeCard.style.display = 'block';
    if (btnRemove) btnRemove.style.display = 'inline-block';

    const prev = document.getElementById('image-active-preview');
    const title = document.getElementById('image-active-title');
    const author = document.getElementById('image-active-author');
    const license = document.getElementById('image-active-license');
    const score = document.getElementById('image-active-score');
    const srcLink = document.getElementById('image-active-source-link');

    if (prev) prev.src = imgUrl;
    if (title) title.innerText = feat.title || article.title || 'Hero Poster';
    if (author) author.innerText = feat.author || 'Unknown';
    if (license) license.innerText = feat.license || 'License unknown — verify before commercial use.';
    if (score) score.innerText = feat.relevanceScore ? `${Math.round(feat.relevanceScore)}/100 Relevance` : 'Custom Upload';
    if (srcLink) {
      srcLink.href = feat.sourceUrl || '#';
      srcLink.innerText = feat.sourceName || 'Web Source ↗';
    }
  } else {
    if (activeCard) activeCard.style.display = 'none';
    if (btnRemove) btnRemove.style.display = 'none';
  }

  // Render Candidates Grid
  const candContainer = document.getElementById('image-candidates-container');
  const candGrid = document.getElementById('image-candidates-grid');
  const countTag = document.getElementById('candidates-count-tag');

  if (candidates && candidates.length > 0) {
    if (candContainer) candContainer.style.display = 'block';
    if (countTag) countTag.innerText = `${candidates.length} candidates`;
    if (candGrid) {
      candGrid.innerHTML = '';
      candidates.forEach((c, idx) => {
        const card = document.createElement('div');
        card.style.background = 'var(--bg-surface-elevated)';
        card.style.border = '1px solid var(--border-subtle)';
        card.style.borderRadius = 'var(--radius-md)';
        card.style.overflow = 'hidden';
        card.style.display = 'flex';
        card.style.flexDirection = 'column';
        card.innerHTML = `
          <div style="height:140px; background:#0b1120; overflow:hidden; display:flex; align-items:center; justify-content:center;">
            <img src="${c.thumbnailUrl || c.imageUrl}" alt="${escapeAttr(c.title || '')}" style="width:100%; height:100%; object-fit:cover;" onerror="this.src='/static/icon.png';" />
          </div>
          <div style="padding:10px 12px; flex:1; display:flex; flex-direction:column; justify-content:space-between; font-size:12px;">
            <div>
              <strong style="display:block; margin-bottom:4px; font-size:12px; color:var(--text-primary); overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${escapeHtml(c.title || 'Image')}</strong>
              <div style="color:var(--text-secondary); font-size:11px; margin-bottom:6px;">${escapeHtml(c.sourceName || 'Web')} • Score: <span class="badge" style="background:var(--success); color:#fff; font-size:10px; padding:1px 6px; border-radius:3px;">${Math.round(c.relevanceScore || 0)}</span></div>
            </div>
            <button class="btn btn-primary btn-sm" onclick="selectCandidateImage(${idx})" style="width:100%; margin-top:8px;">Use Image</button>
          </div>
        `;
        candGrid.appendChild(card);
      });
    }
  } else {
    if (candContainer) candContainer.style.display = 'none';
  }
}

async function selectCandidateImage(index) {
  const c = currentImageCandidates[index];
  if (!c) return;

  const imageObj = {
    url: c.imageUrl,
    thumbnailUrl: c.thumbnailUrl,
    sourceUrl: c.sourceUrl,
    sourceName: c.sourceName,
    title: c.title,
    license: c.license || 'License unknown — verify before commercial use.',
    author: c.author || 'Web',
    relevanceScore: c.relevanceScore,
    altText: c.title || 'Featured hero image',
  };

  showToast('Setting featured image...', 'info');
  try {
    if (currentArticleId) {
      await API.selectFeaturedImage(currentArticleId, imageObj);
    }
    if (currentArticleData) {
      currentArticleData.featured_image = imageObj;
      currentArticleData.featuredImage = imageObj;
    }
    populateFeaturedImageUI(currentArticleData, currentImageCandidates);
    renderPublicationPreview(currentArticleData);
    showToast('Featured image updated!', 'success');
  } catch (err) {
    showToast(`Failed to select image: ${err.message}`, 'error');
  }
}

async function handleRemoveFeaturedImage() {
  if (!confirm('Remove the featured hero image from this article?')) return;
  try {
    if (currentArticleId) {
      await API.removeFeaturedImage(currentArticleId);
    }
    if (currentArticleData) {
      currentArticleData.featured_image = null;
      currentArticleData.featuredImage = null;
    }
    populateFeaturedImageUI(currentArticleData, currentImageCandidates);
    renderPublicationPreview(currentArticleData);
    showToast('Featured image removed.', 'info');
  } catch (err) {
    showToast(`Failed: ${err.message}`, 'error');
  }
}

async function handleSearchImagesAgain() {
  const title = document.getElementById('editor-article-title')?.value || currentArticleData?.title;
  if (!title) {
    showToast('Please enter an article title first.', 'warning');
    return;
  }

  const loadingEl = document.getElementById('image-loading-state');
  const bannerNoImg = document.getElementById('image-not-found-banner');
  if (loadingEl) loadingEl.style.display = 'block';
  if (bannerNoImg) bannerNoImg.style.display = 'none';

  try {
    const res = await API.findImagesForArticle({
      article_id: currentArticleId,
      article_title: title,
      article_content: document.getElementById('editor-content-area')?.innerText || '',
      keywords: currentArticleData?.keywords || [],
    });

    if (loadingEl) loadingEl.style.display = 'none';

    if (res.candidates && res.candidates.length > 0) {
      currentImageCandidates = res.candidates;
      if (res.selected_image && currentArticleData) {
        currentArticleData.featured_image = res.selected_image;
      }
      populateFeaturedImageUI(currentArticleData, res.candidates);
      renderPublicationPreview(currentArticleData);
      showToast(`Found ${res.candidates.length} candidate images!`, 'success');
    } else {
      if (bannerNoImg) bannerNoImg.style.display = 'block';
      showToast('No suitable images met the relevance threshold.', 'warning');
    }
  } catch (err) {
    if (loadingEl) loadingEl.style.display = 'none';
    showToast(`Image search failed: ${err.message}`, 'error');
  }
}

function focusCustomSearchInput() {
  const input = document.getElementById('custom-image-query');
  if (input) {
    input.focus();
    input.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
}

async function handleCustomSearchSubmit(e) {
  e.preventDefault();
  const query = document.getElementById('custom-image-query')?.value?.trim();
  if (!query) return;

  const loadingEl = document.getElementById('image-loading-state');
  if (loadingEl) loadingEl.style.display = 'block';

  try {
    const res = await API.searchImages(query, 8);
    if (loadingEl) loadingEl.style.display = 'none';

    if (res.candidates && res.candidates.length > 0) {
      currentImageCandidates = res.candidates;
      populateFeaturedImageUI(currentArticleData, res.candidates);
      showToast(`Found ${res.candidates.length} images for "${query}"`, 'success');
    } else {
      showToast('No images found for this query.', 'warning');
    }
  } catch (err) {
    if (loadingEl) loadingEl.style.display = 'none';
    showToast(`Search error: ${err.message}`, 'error');
  }
}

function handlePublishWithoutImage() {
  const banner = document.getElementById('image-not-found-banner');
  if (banner) banner.style.display = 'none';
  showToast('Article will be published without a featured image.', 'info');
}

// ---------------- CUSTOM HERO POSTER (UPLOAD / URL) ----------------
function toggleCustomImagePanel(forceState = null) {
  const panel = document.getElementById('custom-image-panel');
  if (!panel) return;
  const isShown = forceState !== null ? !forceState : panel.style.display !== 'none';
  panel.style.display = isShown ? 'none' : 'block';
  if (!isShown) {
    panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }
}

function switchCustomImageTab(tab) {
  const pnlFile = document.getElementById('panel-custom-tab-file');
  const pnlUrl = document.getElementById('panel-custom-tab-url');
  const btnFile = document.getElementById('tab-custom-upload-file');
  const btnUrl = document.getElementById('tab-custom-upload-url');

  if (tab === 'url') {
    if (pnlFile) pnlFile.style.display = 'none';
    if (pnlUrl) pnlUrl.style.display = 'block';
    btnFile?.classList.replace('btn-primary', 'btn-secondary');
    btnUrl?.classList.replace('btn-secondary', 'btn-primary');
  } else {
    if (pnlUrl) pnlUrl.style.display = 'none';
    if (pnlFile) pnlFile.style.display = 'block';
    btnUrl?.classList.replace('btn-primary', 'btn-secondary');
    btnFile?.classList.replace('btn-secondary', 'btn-primary');
  }
}

function handleCustomDragOver(e) {
  e.preventDefault();
  const dz = document.getElementById('custom-dropzone');
  if (dz) {
    dz.style.borderColor = 'var(--accent)';
    dz.style.background = 'var(--accent-light)';
  }
}

function handleCustomDragLeave(e) {
  e.preventDefault();
  const dz = document.getElementById('custom-dropzone');
  if (dz) {
    dz.style.borderColor = 'var(--border-medium)';
    dz.style.background = 'var(--bg-surface-elevated)';
  }
}

function handleCustomFileDrop(e) {
  e.preventDefault();
  handleCustomDragLeave(e);
  if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
    processCustomFile(e.dataTransfer.files[0]);
  }
}

function handleCustomFileSelected(e) {
  if (e.target && e.target.files && e.target.files.length > 0) {
    processCustomFile(e.target.files[0]);
  }
}

function processCustomFile(file) {
  if (!file.type.startsWith('image/')) {
    showToast('Please select a valid image file (PNG, JPG, WEBP, etc.)', 'error');
    return;
  }
  if (file.size > 20 * 1024 * 1024) {
    showToast('Image file is too large. Max size is 20MB.', 'error');
    return;
  }

  pendingCustomFile = file;
  const reader = new FileReader();
  reader.onload = function(evt) {
    pendingCustomFileDataUrl = evt.target.result;
    const previewBox = document.getElementById('custom-upload-preview-box');
    const thumb = document.getElementById('custom-upload-thumb');
    const titleInput = document.getElementById('custom-upload-title');
    if (thumb) thumb.src = pendingCustomFileDataUrl;
    if (titleInput && !titleInput.value) {
      titleInput.value = file.name.replace(/\.[^/.]+$/, '').replace(/[-_]/g, ' ');
    }
    if (previewBox) previewBox.style.display = 'block';
  };
  reader.readAsDataURL(file);
}

function cancelCustomUpload() {
  pendingCustomFile = null;
  pendingCustomFileDataUrl = null;
  const previewBox = document.getElementById('custom-upload-preview-box');
  const fileInput = document.getElementById('custom-file-input');
  if (previewBox) previewBox.style.display = 'none';
  if (fileInput) fileInput.value = '';
}

async function submitCustomFileUpload() {
  if (!pendingCustomFileDataUrl || !pendingCustomFile) {
    showToast('Please select an image file first.', 'warning');
    return;
  }

  const titleInput = document.getElementById('custom-upload-title');
  const authorInput = document.getElementById('custom-upload-author');
  const licenseInput = document.getElementById('custom-upload-license');

  const title = titleInput?.value?.trim() || pendingCustomFile.name;
  const author = authorInput?.value?.trim() || 'Author';
  const license = licenseInput?.value?.trim() || 'User Owned / Permitted';
  const articleId = currentArticleData?.id || null;

  showToast('Uploading custom hero poster...', 'info');

  try {
    const res = await API.uploadCustomHeroImage({
      articleId: articleId,
      filename: pendingCustomFile.name,
      data: pendingCustomFileDataUrl,
      title: title,
      author: author,
      license: license,
    });

    const savedImage = res.image;
    if (currentArticleData) {
      currentArticleData.featured_image = savedImage;
      currentArticleData.featuredImage = savedImage;
    }
    populateFeaturedImageUI(currentArticleData, currentImageCandidates);
    renderPublicationPreview(currentArticleData);
    toggleCustomImagePanel(false);
    cancelCustomUpload();
    showToast('Custom hero poster set successfully!', 'success');
  } catch (err) {
    showToast(`Failed: ${err.message}`, 'error');
  }
}

function previewCustomUrl() {
  const urlInput = document.getElementById('custom-url-input');
  const url = urlInput?.value?.trim();
  if (!url) {
    showToast('Please enter an image URL first.', 'warning');
    return;
  }
  const box = document.getElementById('custom-url-preview-box');
  const thumb = document.getElementById('custom-url-thumb');
  if (box && thumb) {
    thumb.style.display = 'inline-block';
    thumb.src = url;
    box.style.display = 'block';
  }
}

async function submitCustomUrl() {
  const urlInput = document.getElementById('custom-url-input');
  const titleInput = document.getElementById('custom-url-title');
  const authorInput = document.getElementById('custom-url-author');
  const url = urlInput?.value?.trim();

  if (!url) {
    showToast('Please enter a valid image URL.', 'warning');
    return;
  }

  const title = titleInput?.value?.trim() || 'Custom Hero Poster';
  const author = authorInput?.value?.trim() || 'User Provided';
  const articleId = currentArticleData?.id || null;

  showToast('Setting image URL as hero poster...', 'info');

  try {
    const res = await API.setCustomHeroImageUrl({
      articleId: articleId,
      url: url,
      title: title,
      author: author,
      license: 'User Provided / Verify Rights',
    });

    const savedImage = res.image;
    if (currentArticleData) {
      currentArticleData.featured_image = savedImage;
      currentArticleData.featuredImage = savedImage;
    }
    populateFeaturedImageUI(currentArticleData, currentImageCandidates);
    renderPublicationPreview(currentArticleData);
    toggleCustomImagePanel(false);
    urlInput.value = '';
    const box = document.getElementById('custom-url-preview-box');
    if (box) box.style.display = 'none';
    showToast('Custom hero poster set successfully!', 'success');
  } catch (err) {
    showToast(`Failed: ${err.message}`, 'error');
  }
}

// ---------------- PUBLICATION PREVIEW RENDERING ----------------
function setPreviewViewport(mode) {
  const stage = document.getElementById('preview-stage');
  const btnDesktop = document.getElementById('btn-view-desktop');
  const btnTablet = document.getElementById('btn-view-tablet');
  const btnMobile = document.getElementById('btn-view-mobile');

  if (!stage) return;

  stage.classList.remove('mode-desktop', 'mode-tablet', 'mode-mobile');
  btnDesktop?.classList.remove('active');
  btnTablet?.classList.remove('active');
  btnMobile?.classList.remove('active');

  if (mode === 'mobile') {
    stage.classList.add('mode-mobile');
    btnMobile?.classList.add('active');
  } else if (mode === 'tablet') {
    stage.classList.add('mode-tablet');
    btnTablet?.classList.add('active');
  } else {
    stage.classList.add('mode-desktop');
    btnDesktop?.classList.add('active');
  }
}

function copyCodeSnippet(btn) {
  const container = btn.closest('.pub-code-container');
  const code = container?.querySelector('code')?.innerText || '';
  navigator.clipboard.writeText(code).then(() => {
    const originalText = btn.innerText;
    btn.innerText = '✓ Copied';
    setTimeout(() => { btn.innerText = originalText; }, 2000);
  });
}

function sanitizeHtml(html) {
  if (!html) return '';
  const temp = document.createElement('div');
  temp.innerHTML = html;
  const scripts = temp.querySelectorAll('script');
  scripts.forEach(s => s.remove());
  const allElements = temp.querySelectorAll('*');
  allElements.forEach(el => {
    Array.from(el.attributes).forEach(attr => {
      if (attr.name.startsWith('on') || (attr.value && attr.value.startsWith('javascript:'))) {
        el.removeAttribute(attr.name);
      }
    });
  });
  return temp.innerHTML;
}

function renderMarkdownToHtml(md) {
  if (!md) return '<p>No content generated.</p>';

  // Escape basic HTML entities in text to prevent markup injection
  let text = md
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  // Extract and preserve code blocks
  const codeBlocks = [];
  text = text.replace(/```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g, (match, lang, code) => {
    const idx = codeBlocks.length;
    const cleanCode = code.trim();
    const langDisplay = lang ? lang.toUpperCase() : 'CODE';
    codeBlocks.push(
      `<div class="pub-code-container" style="background:var(--bg-app); border:1px solid var(--border-subtle); border-radius:8px; margin:20px 0; overflow:hidden;">` +
        `<div style="display:flex; justify-content:space-between; align-items:center; background:var(--bg-surface-elevated); padding:6px 12px; font-size:11px; font-weight:700; color:var(--text-muted); border-bottom:1px solid var(--border-subtle);">` +
          `<span>${langDisplay}</span>` +
          `<button class="btn btn-secondary btn-sm" style="padding:2px 8px; font-size:10px;" onclick="copyCodeSnippet(this)">Copy</button>` +
        `</div>` +
        `<pre style="margin:0; padding:14px; overflow-x:auto; font-family:monospace; font-size:13px; line-height:1.5;"><code>${cleanCode}</code></pre>` +
      `</div>`
    );
    return `\n\n__CODE_BLOCK_${idx}__\n\n`;
  });

  // Extract and preserve Markdown tables
  const tableBlocks = [];
  const tableRegex = /((?:\|[^\n]+\|\n?)+)/g;
  text = text.replace(tableRegex, (match) => {
    const rows = match.trim().split('\n');
    if (rows.length < 2) return match;

    let tableHtml = '<div style="overflow-x:auto; margin:20px 0; border:1px solid var(--border-subtle); border-radius:8px;"><table style="width:100%; border-collapse:collapse; font-size:13px;">';
    let isHeader = true;

    for (let i = 0; i < rows.length; i++) {
      const row = rows[i].trim();
      if (!row || row.includes('---')) {
        isHeader = false;
        continue;
      }
      const cells = row.split('|').filter((_, index, arr) => index > 0 && index < arr.length - 1);
      tableHtml += '<tr>';
      cells.forEach(c => {
        const tag = isHeader ? 'th' : 'td';
        const bg = isHeader ? 'background:var(--bg-surface-elevated); font-weight:700;' : '';
        tableHtml += `<${tag} style="padding:10px 14px; border-bottom:1px solid var(--border-subtle); ${bg}">${c.trim()}</${tag}>`;
      });
      tableHtml += '</tr>';
    }
    tableHtml += '</table></div>';
    const idx = tableBlocks.length;
    tableBlocks.push(tableHtml);
    return `\n\n__TABLE_BLOCK_${idx}__\n\n`;
  });

  // Inline images: ![alt](url)
  text = text.replace(/!\[(.*?)\]\((.*?)\)/g, (match, alt, url) => {
    return `<div style="text-align:center; margin:24px 0;"><img src="${url}" alt="${alt}" loading="lazy" style="max-width:100%; border-radius:8px; display:inline-block;" /><div style="font-size:12px; color:var(--text-muted); font-style:italic; margin-top:6px;">${alt}</div></div>`;
  });

  // Inline links: [text](url)
  text = text.replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer" style="color:var(--accent);">$1</a>');

  // Headings
  text = text.replace(/^###\s+(.*)$/gm, '<h3 style="font-size:18px; font-weight:700; margin:24px 0 10px 0;">$1</h3>');
  text = text.replace(/^##\s+(.*)$/gm, '<h2 style="font-size:22px; font-weight:800; margin:32px 0 12px 0; border-bottom:1px solid var(--border-subtle); padding-bottom:6px;">$1</h2>');
  text = text.replace(/^#\s+(.*)$/gm, '<h2 style="font-size:24px; font-weight:800; margin:32px 0 12px 0;">$1</h2>');

  // Bold & Italic
  text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  text = text.replace(/\*(.*?)\*/g, '<em>$1</em>');

  // Inline code: `code`
  text = text.replace(/`([^`]+)`/g, '<code style="background:var(--bg-surface-elevated); padding:2px 6px; border-radius:4px; font-family:monospace; font-size:12px;">$1</code>');

  // Blockquotes
  text = text.replace(/^&gt;\s+(.*)$/gm, '<blockquote style="border-left:3px solid var(--accent); padding:10px 18px; margin:20px 0; background:var(--bg-surface-elevated); font-style:italic; color:var(--text-secondary);">$1</blockquote>');

  // Horizontal rules
  text = text.replace(/^---$/gm, '<hr style="border:none; border-top:1px solid var(--border-subtle); margin:24px 0;" />');

  // Process paragraphs & lists cleanly
  const lines = text.split('\n');
  const output = [];
  let currentListType = null;
  let listItems = [];

  function flushList() {
    if (currentListType && listItems.length > 0) {
      output.push(`<${currentListType} style="margin:14px 0 18px 24px;">\n${listItems.join('\n')}\n</${currentListType}>`);
      currentListType = null;
      listItems = [];
    }
  }

  for (let line of lines) {
    const trimmed = line.trim();
    if (!trimmed) {
      flushList();
      continue;
    }

    if (trimmed.startsWith('__CODE_BLOCK_') || trimmed.startsWith('__TABLE_BLOCK_') ||
        trimmed.startsWith('<h2') || trimmed.startsWith('<h3') || trimmed.startsWith('<blockquote') ||
        trimmed.startsWith('<hr') || trimmed.startsWith('<div')) {
      flushList();
      output.push(trimmed);
    } else if (trimmed.match(/^[-*]\s+/)) {
      if (currentListType !== 'ul') {
        flushList();
        currentListType = 'ul';
      }
      listItems.push(`  <li style="margin-bottom:6px;">${trimmed.replace(/^[-*]\s+/, '')}</li>`);
    } else if (trimmed.match(/^\d+\.\s+/)) {
      if (currentListType !== 'ol') {
        flushList();
        currentListType = 'ol';
      }
      listItems.push(`  <li style="margin-bottom:6px;">${trimmed.replace(/^\d+\.\s+/, '')}</li>`);
    } else {
      flushList();
      output.push(`<p style="margin-bottom:16px;">${trimmed}</p>`);
    }
  }
  flushList();

  let finalHtml = output.join('\n');

  codeBlocks.forEach((cb, idx) => {
    finalHtml = finalHtml.replace(`__CODE_BLOCK_${idx}__`, cb);
  });
  tableBlocks.forEach((tb, idx) => {
    finalHtml = finalHtml.replace(`__TABLE_BLOCK_${idx}__`, tb);
  });

  return sanitizeHtml(finalHtml);
}

function renderPublicationPreview(article) {
  if (!article) return;

  const titleEl = document.getElementById('pub-header-title');
  const excerptEl = document.getElementById('pub-header-excerpt');
  const catEl = document.getElementById('pub-category');
  const dateEl = document.getElementById('pub-date');
  const readtimeEl = document.getElementById('pub-byline-readtime');
  const tagsContainer = document.getElementById('pub-tags-container');

  const words = (article.content || '').split(/\s+/).filter(Boolean).length;
  const readMins = Math.max(1, Math.ceil(words / 220));

  if (titleEl) titleEl.innerText = article.title || 'Untitled Article';
  if (excerptEl) excerptEl.innerText = article.summary || (article.content || '').slice(0, 160) + '...';
  if (catEl) catEl.innerText = article.search_intent ? `${article.search_intent} Article` : 'Editorial Guide';
  if (dateEl) dateEl.innerText = new Date(article.created_at || Date.now()).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  if (readtimeEl) readtimeEl.innerText = `${readMins} min read`;

  const tbRead = document.getElementById('preview-read-time');
  const tbWords = document.getElementById('preview-word-count');
  if (tbRead) tbRead.innerText = `${readMins} min read`;
  if (tbWords) tbWords.innerText = `${words.toLocaleString()} words`;

  if (tagsContainer) {
    tagsContainer.innerHTML = '';
    const keywords = article.keywords || [];
    keywords.forEach(k => {
      const tag = document.createElement('span');
      tag.className = 'status-badge';
      tag.style.background = 'var(--bg-surface-elevated)';
      tag.style.color = 'var(--text-secondary)';
      tag.innerText = `#${k}`;
      tagsContainer.appendChild(tag);
    });
  }

  // Hero Image
  const heroContainer = document.getElementById('pub-hero-container');
  const heroImg = document.getElementById('pub-hero-image');
  const heroCaption = document.getElementById('pub-hero-caption');

  const feat = article.featured_image || article.featuredImage || {};
  const imgUrl = feat.url || feat.imageUrl || feat.image || '';

  if (imgUrl) {
    if (heroContainer) heroContainer.style.display = 'block';
    if (heroImg) {
      heroImg.src = imgUrl;
      heroImg.alt = feat.title || feat.altText || `Hero image for ${article.title}`;
      heroImg.onerror = function() {
        if (heroContainer) heroContainer.style.display = 'none';
      };
    }
    const authorText = feat.author && feat.author !== 'Unknown' ? `Photo: ${feat.author} • ` : '';
    const srcText = feat.sourceName ? `Source: ${feat.sourceName} • ` : '';
    const licText = feat.license ? `License: ${feat.license}` : 'License unknown — verify before commercial use.';
    if (heroCaption) {
      heroCaption.innerText = `${feat.title || article.title} (${authorText}${srcText}${licText})`;
    }
  } else {
    if (heroContainer) heroContainer.style.display = 'none';
  }

  // Render Body
  const bodyEl = document.getElementById('pub-article-body');
  if (bodyEl) {
    let content = article.content || '';
    content = content.replace(/^#\s+[^\n]+\n+/, '');
    content = content.replace(/^\s*!\[.*?\]\(.*?\)\s*(\*[^*]*\*\s*)?/, '');
    bodyEl.innerHTML = renderMarkdownToHtml(content.trim());
  }

  updateQualityChecklist(article);
}

function updateQualityChecklist(article) {
  const titleBadge = document.getElementById('qc-item-title');
  const imgBadge = document.getElementById('qc-item-image');
  const bodyBadge = document.getElementById('qc-item-content');
  const h2Badge = document.getElementById('qc-item-headings');
  const altBadge = document.getElementById('qc-item-alt');

  const content = article.content || '';
  const feat = article.featured_image || article.featuredImage || {};
  const hasImage = Boolean(feat.url || feat.imageUrl || feat.image);

  if (titleBadge) {
    if (article.title && article.title.length > 5) {
      titleBadge.className = 'qc-badge qc-pass';
      titleBadge.innerText = '✓ Title Configured';
    } else {
      titleBadge.className = 'qc-badge qc-warn';
      titleBadge.innerText = '⚠ Title Missing or Short';
    }
  }

  if (imgBadge) {
    if (hasImage) {
      imgBadge.className = 'qc-badge qc-pass';
      imgBadge.innerText = '✓ Featured Image Ready';
    } else {
      imgBadge.className = 'qc-badge qc-warn';
      imgBadge.innerText = '⚠ Featured Image Missing';
    }
  }

  if (bodyBadge) {
    if (content.length > 200) {
      bodyBadge.className = 'qc-badge qc-pass';
      bodyBadge.innerText = '✓ Article Body Formatted';
    } else {
      bodyBadge.className = 'qc-badge qc-warn';
      bodyBadge.innerText = '⚠ Insufficient Content';
    }
  }

  if (h2Badge) {
    if (content.includes('## ') || content.includes('<h2')) {
      h2Badge.className = 'qc-badge qc-pass';
      h2Badge.innerText = '✓ Clear H2/H3 Structure';
    } else {
      h2Badge.className = 'qc-badge qc-warn';
      h2Badge.innerText = '⚠ No H2 Sections Found';
    }
  }

  if (altBadge) {
    if (feat.altText || feat.title) {
      altBadge.className = 'qc-badge qc-pass';
      altBadge.innerText = '✓ Alt Text Verified';
    } else {
      altBadge.className = 'qc-badge qc-warn';
      altBadge.innerText = '⚠ Image Alt Text Missing';
    }
  }
}

// ---------------- SETTINGS & SYSTEM CONFIGURATION ----------------
async function loadSettings() {
  try {
    const config = await API.getSettings();

    // AI Mode radio setup
    const mode = config.ai_generation_mode || 'online';
    selectAIMode(mode);

    // API Key status
    const geminiKeyStatus = document.getElementById('settings-gemini-key-status');
    if (geminiKeyStatus) {
      geminiKeyStatus.innerText = config.gemini_api_key_configured ? 'Configured' : 'Missing Key';
      geminiKeyStatus.style.background = config.gemini_api_key_configured ? 'var(--success-bg)' : 'var(--danger-bg)';
      geminiKeyStatus.style.color = config.gemini_api_key_configured ? 'var(--success)' : 'var(--danger)';
    }

    const geminiModel = document.getElementById('settings-gemini-model');
    if (geminiModel && config.gemini_model) geminiModel.value = config.gemini_model;

    // Ollama URL & Model
    const ollamaUrl = document.getElementById('settings-ollama-url');
    if (ollamaUrl && config.ollama_base_url) ollamaUrl.value = config.ollama_base_url;

    // Blogger OAuth status
    const oauthStatus = document.getElementById('settings-oauth-status');
    if (oauthStatus) {
      oauthStatus.innerText = config.oauth_configured ? 'Connected (ByteBlooming)' : 'Not Connected';
      oauthStatus.style.color = config.oauth_configured ? 'var(--success)' : 'var(--warning)';
    }

    const blogIdInput = document.getElementById('settings-blog-id');
    if (blogIdInput && config.blogger_blog_id) blogIdInput.value = config.blogger_blog_id;

    // Image config
    const imgSrc = document.getElementById('settings-image-source');
    if (imgSrc && config.image_source) imgSrc.value = config.image_source;

    const imgAuto = document.getElementById('settings-image-auto-select');
    if (imgAuto) imgAuto.checked = config.image_auto_select !== false;

    const imgGate = document.getElementById('settings-image-min-relevance');
    if (imgGate && config.image_min_relevance) imgGate.value = config.image_min_relevance;

    // Quality threshold & flags
    const thresh = document.getElementById('settings-threshold');
    const threshDisp = document.getElementById('threshold-display');
    if (thresh && config.quality_threshold) {
      thresh.value = config.quality_threshold;
      if (threshDisp) threshDisp.innerText = `${config.quality_threshold}/100`;
    }

    const demoMode = document.getElementById('settings-demo-mode');
    if (demoMode) demoMode.checked = Boolean(config.demo_mode);

    const autoPub = document.getElementById('settings-auto-publish');
    if (autoPub) autoPub.checked = Boolean(config.auto_publish);

    // Search & Trends config
    const searchProv = document.getElementById('settings-search-provider');
    if (searchProv && config.search_provider) {
      searchProv.value = config.search_provider;
      handleSearchProviderChange(config.search_provider);
    }
    const trendsGeo = document.getElementById('settings-trends-geo');
    if (trendsGeo && config.trends_geo) trendsGeo.value = config.trends_geo;

    // Validation warnings
    const warningsList = document.getElementById('settings-warnings');
    if (warningsList) {
      warningsList.innerHTML = '';
      if (config.validation_warnings && config.validation_warnings.length > 0) {
        config.validation_warnings.forEach(w => {
          const li = document.createElement('li');
          li.innerText = w;
          warningsList.appendChild(li);
        });
      } else {
        warningsList.innerHTML = '<li style="color:var(--success);">All startup validations passed cleanly.</li>';
      }
    }

    // Load available Blogger blogs
    loadBloggerBlogsList();

  } catch (err) {
    showToast(`Failed to load settings: ${err.message}`, 'error');
  }
}

function selectAIMode(mode) {
  const radioOnline = document.getElementById('mode-radio-online');
  const radioOffline = document.getElementById('mode-radio-offline');
  const cardOnline = document.getElementById('card-mode-online');
  const cardOffline = document.getElementById('card-mode-offline');
  const groupOnline = document.getElementById('settings-group-online');
  const groupOffline = document.getElementById('settings-group-offline');

  if (mode === 'offline') {
    if (radioOffline) radioOffline.checked = true;
    if (cardOffline) {
      cardOffline.style.borderColor = 'var(--accent)';
      cardOffline.style.borderWidth = '2px';
    }
    if (cardOnline) {
      cardOnline.style.borderColor = 'var(--border-subtle)';
      cardOnline.style.borderWidth = '1px';
    }
    if (groupOnline) groupOnline.style.display = 'none';
    if (groupOffline) groupOffline.style.display = 'block';
  } else {
    if (radioOnline) radioOnline.checked = true;
    if (cardOnline) {
      cardOnline.style.borderColor = 'var(--accent)';
      cardOnline.style.borderWidth = '2px';
    }
    if (cardOffline) {
      cardOffline.style.borderColor = 'var(--border-subtle)';
      cardOffline.style.borderWidth = '1px';
    }
    if (groupOffline) groupOffline.style.display = 'none';
    if (groupOnline) groupOnline.style.display = 'block';
  }
}

async function checkOllamaConnection() {
  const statusBox = document.getElementById('ollama-status-box');
  const statusText = document.getElementById('ollama-status-text');
  if (statusText) statusText.innerText = 'Testing Ollama connection at configured endpoint...';

  try {
    const res = await API.getOllamaModels();
    if (res.healthy) {
      if (statusText) {
        statusText.innerHTML = `<strong style="color:var(--success);">✓ Ollama Connected!</strong> Found ${res.models?.length || 0} installed model(s): [${(res.models || []).join(', ')}]`;
      }
      populateOllamaModelSelect(res.models || []);
      showToast('Ollama connection verified!', 'success');
    } else {
      if (statusText) {
        statusText.innerHTML = `<strong style="color:var(--danger);">✕ Ollama Unreachable:</strong> ${res.message || 'Make sure Ollama is running.'}`;
      }
      showToast('Ollama is not reachable.', 'error');
    }
  } catch (err) {
    if (statusText) {
      statusText.innerHTML = `<strong style="color:var(--danger);">✕ Error:</strong> ${err.message}`;
    }
    showToast(`Ollama test failed: ${err.message}`, 'error');
  }
}

async function refreshOllamaModels() {
  checkOllamaConnection();
}

function populateOllamaModelSelect(models) {
  const select = document.getElementById('settings-ollama-model-select');
  if (!select) return;
  select.innerHTML = '';
  if (!models || models.length === 0) {
    select.innerHTML = '<option value="">No local models found in Ollama</option>';
    return;
  }
  models.forEach(m => {
    const opt = document.createElement('option');
    opt.value = m;
    opt.innerText = m;
    select.appendChild(opt);
  });
}

function handleOllamaModelSelectChange(sel) {
  const customBox = document.getElementById('ollama-custom-model-box');
  if (customBox) {
    customBox.style.display = sel.value === 'custom' ? 'block' : 'none';
  }
}

async function loadBloggerBlogsList() {
  const sel = document.getElementById('settings-blog-selector');
  if (!sel) return;
  try {
    const blogs = await API.getBloggerBlogs();
    sel.innerHTML = '';
    if (!blogs || blogs.length === 0) {
      sel.innerHTML = '<option value="">No Blogger blogs found or OAuth disconnected</option>';
      return;
    }
    blogs.forEach(b => {
      const opt = document.createElement('option');
      opt.value = b.id;
      opt.innerText = `${b.name} (${b.id})`;
      sel.appendChild(opt);
    });
    const defaultBlogId = document.getElementById('settings-blog-id')?.value;
    if (defaultBlogId) sel.value = defaultBlogId;
  } catch (err) {
    sel.innerHTML = '<option value="">Blogger OAuth not connected</option>';
  }
}

function handleBlogSelectionChange(blogId) {
  const input = document.getElementById('settings-blog-id');
  if (input && blogId) input.value = blogId;
}

async function handleSaveSettings() {
  const modeRadio = document.querySelector('input[name="ai_mode_choice"]:checked');
  const aiMode = modeRadio ? modeRadio.value : 'online';

  const geminiKeyInput = document.getElementById('input-gemini-key');
  const geminiModel = document.getElementById('settings-gemini-model')?.value;

  const ollamaUrl = document.getElementById('settings-ollama-url')?.value?.trim();
  const ollamaModel = document.getElementById('settings-ollama-model-select')?.value;

  const blogId = document.getElementById('settings-blog-id')?.value?.trim();
  const imgSrc = document.getElementById('settings-image-source')?.value;
  const imgAuto = document.getElementById('settings-image-auto-select')?.checked;
  const imgGate = document.getElementById('settings-image-min-relevance')?.value;
  const thresh = parseInt(document.getElementById('settings-threshold')?.value || '85');
  const demo = document.getElementById('settings-demo-mode')?.checked;
  const autoPub = document.getElementById('settings-auto-publish')?.checked;
  const searchProv = document.getElementById('settings-search-provider')?.value || 'auto';
  const serpapiKey = document.getElementById('input-serpapi-key')?.value?.trim();
  const tavilyKey = document.getElementById('input-tavily-key')?.value?.trim();
  const trendsGeo = document.getElementById('settings-trends-geo')?.value || 'IN';

  const payload = {
    ai_generation_mode: aiMode,
    gemini_model: geminiModel,
    ollama_base_url: ollamaUrl,
    ollama_model: ollamaModel,
    blogger_blog_id: blogId,
    image_source: imgSrc,
    image_auto_select: imgAuto,
    image_min_relevance: imgGate,
    quality_threshold: thresh,
    demo_mode: demo,
    auto_publish: autoPub,
    search_provider: searchProv,
    trends_geo: trendsGeo,
  };

  if (geminiKeyInput && geminiKeyInput.value.trim()) {
    payload.gemini_api_key = geminiKeyInput.value.trim();
  }
  if (serpapiKey) {
    payload.serpapi_api_key = serpapiKey;
  }
  if (tavilyKey) {
    payload.tavily_api_key = tavilyKey;
  }

  showToast('Saving settings...', 'info');

  try {
    await API.updateSettings(payload);
    showToast('Configuration saved successfully!', 'success');
    if (geminiKeyInput) geminiKeyInput.value = '';
    const serpInput = document.getElementById('input-serpapi-key');
    if (serpInput) serpInput.value = '';
    const tavInput = document.getElementById('input-tavily-key');
    if (tavInput) tavInput.value = '';
    loadSettings();
    updateConnIndicator();
  } catch (err) {
    showToast(`Failed to save settings: ${err.message}`, 'error');
  }
}

// ---------------- CONNECTION STATUS INDICATOR (TOP BAR & SIDEBAR) ----------------
async function updateConnIndicator() {
  const dotTop = document.getElementById('conn-indicator-dot');
  const textTop = document.getElementById('conn-indicator-text');
  const dotSide = document.getElementById('sidebar-status-dot');
  const tagSide = document.getElementById('sidebar-model-tag');
  const bloggerPill = document.getElementById('blogger-pill-text');

  try {
    const aiStatus = await API.getAIStatus();
    const mode = aiStatus.ai_generation_mode || 'online';
    const isOnline = aiStatus.internet_connected;
    const isReady = aiStatus.ready;

    if (mode === 'online') {
      if (textTop) textTop.innerText = isOnline ? (isReady ? 'Online Gemini' : 'Gemini Key Missing') : 'Offline (No Internet)';
      if (dotTop) {
        dotTop.className = `status-dot ${isOnline && isReady ? '' : 'error'}`;
      }
      if (dotSide) {
        dotSide.className = `status-dot ${isOnline && isReady ? '' : 'error'}`;
      }
      if (tagSide) tagSide.innerText = aiStatus.active_model || 'Gemini Flash';
    } else {
      // Offline mode
      if (textTop) textTop.innerText = isReady ? `Local Ollama (${aiStatus.active_model})` : 'Ollama Disconnected';
      if (dotTop) {
        dotTop.className = `status-dot ${isReady ? '' : 'offline'}`;
      }
      if (dotSide) {
        dotSide.className = `status-dot ${isReady ? '' : 'offline'}`;
      }
      if (tagSide) tagSide.innerText = aiStatus.active_model || 'Ollama';
    }

    // Blogger status
    const bStatus = await API.getBloggerStatus();
    if (bloggerPill) {
      bloggerPill.innerText = bStatus.is_authenticated ? 'ByteBlooming' : 'Disconnected';
    }

  } catch (err) {
    if (textTop) textTop.innerText = 'AI Offline';
    if (dotTop) dotTop.className = 'status-dot error';
  }
}

// ---------------- ESCAPING & UTILITIES ----------------
function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function escapeAttr(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

// ---------------- MODAL CONTROLLER ----------------
function openModal(id) {
  const m = document.getElementById(id);
  if (m) m.classList.add('active');
}

function closeModal(id) {
  const m = document.getElementById(id);
  if (m) m.classList.remove('active');
}

// ---------------- DOM INITIALIZATION ----------------
document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  initSidebarState();
  switchTab('dashboard');
  updateConnIndicator();
  setInterval(updateConnIndicator, 30000);

  // Threshold range listener
  const slider = document.getElementById('settings-threshold');
  if (slider) {
    slider.addEventListener('input', (e) => {
      const disp = document.getElementById('threshold-display');
      if (disp) disp.innerText = `${e.target.value}/100`;
    });
  }
});

// =========================================================================
// SEARCH PROVIDER & INTEGRATION DIAGNOSTICS CONTROLLER
// =========================================================================

function handleSearchProviderChange(val) {
  const boxSerp = document.getElementById('settings-box-serpapi');
  const boxTav = document.getElementById('settings-box-tavily');
  if (boxSerp) boxSerp.style.display = val === 'serpapi' ? 'block' : 'none';
  if (boxTav) boxTav.style.display = val === 'tavily' ? 'block' : 'none';
}

async function runTestConnection(service) {
  const badge = document.getElementById(`card-status-badge-${service}`);
  const msg = document.getElementById(`card-msg-${service}`);
  const tested = document.getElementById(`card-tested-${service}`);

  if (badge) {
    badge.className = 'status-badge status-DRAFT';
    badge.innerText = 'Testing...';
  }
  if (tested) tested.innerText = 'Testing now...';

  try {
    let res = null;
    if (service === 'gemini') res = await API.testGemini();
    else if (service === 'search') res = await API.testSearch();
    else if (service === 'trends') res = await API.testTrends();
    else if (service === 'blogger') res = await API.testBlogger();

    const isOk = res && (res.status === 'connected' || res.status === 'authenticated');
    if (badge) {
      badge.className = isOk ? 'status-badge status-APPROVED' : 'status-badge status-FAILED';
      badge.innerText = isOk ? (res.status === 'authenticated' ? 'Connected' : 'Connected') : 'Error';
    }
    if (msg) {
      msg.innerHTML = escapeHtml(res.message || res.detail || 'Test completed.');
    }
    if (tested) {
      const now = new Date();
      tested.innerText = `Last tested: ${now.toLocaleTimeString()}`;
    }
    showToast(`${service.toUpperCase()} connection test: ${isOk ? 'Success' : 'Failed'}`, isOk ? 'success' : 'error');
  } catch (err) {
    if (badge) {
      badge.className = 'status-badge status-FAILED';
      badge.innerText = 'Error';
    }
    if (msg) {
      msg.innerHTML = `<span style="color:var(--danger);">${escapeHtml(err.message)}</span>`;
    }
    if (tested) {
      tested.innerText = 'Last tested: Failed';
    }
    showToast(`${service.toUpperCase()} test failed: ${err.message}`, 'error');
  }
}

// =========================================================================
// INTERNET TOPIC DISCOVERY CONTROLLER
// =========================================================================

let currentDiscoveryMode = 'trending';
let cachedDiscoveryTopics = [];

async function loadDiscoveryTopics() {
  if (cachedDiscoveryTopics.length > 0) {
    renderDiscoveryTopicCards(cachedDiscoveryTopics);
    return;
  }
  await refreshDiscoveryTopics();
}

function switchDiscoveryMode(mode) {
  currentDiscoveryMode = mode;
  const btnTrending = document.getElementById('btn-discover-trending');
  const btnEvergreen = document.getElementById('btn-discover-evergreen');
  const btnRandom = document.getElementById('btn-discover-random');
  const diffBox = document.getElementById('filter-difficulty-box');

  if (btnTrending) btnTrending.className = mode === 'trending' ? 'btn btn-primary btn-sm' : 'btn btn-secondary btn-sm';
  if (btnEvergreen) btnEvergreen.className = mode === 'evergreen' ? 'btn btn-primary btn-sm' : 'btn btn-secondary btn-sm';
  if (btnRandom) btnRandom.className = mode === 'random' ? 'btn btn-primary btn-sm' : 'btn btn-secondary btn-sm';

  if (diffBox) diffBox.style.display = (mode === 'evergreen' || mode === 'random') ? 'block' : 'none';

  const sourceNotice = document.getElementById('discovery-source-notice');
  if (sourceNotice) {
    if (mode === 'trending') {
      const geo = document.getElementById('discovery-country')?.value || 'IN';
      sourceNotice.innerHTML = `<span>📡 Sources: Google Trends Live RSS (${escapeHtml(geo)}) • Google News Technology RSS</span>`;
    } else if (mode === 'evergreen') {
      sourceNotice.innerHTML = `<span>🌲 Sources: ByteBlooming Tech Taxonomy & Evergreen Engineering Benchmarks</span>`;
    } else {
      sourceNotice.innerHTML = `<span>🎲 Sources: Curated Developer Innovation Ideas & Deep Architectural Concepts</span>`;
    }
  }

  refreshDiscoveryTopics();
}

function handleDiscoveryFilterChange() {
  refreshDiscoveryTopics();
}

async function refreshDiscoveryTopics() {
  const loading = document.getElementById('discovery-topics-loading');
  const grid = document.getElementById('discovery-topics-grid');

  if (loading) loading.style.display = 'block';
  if (grid) grid.innerHTML = '';

  const country = document.getElementById('discovery-country')?.value || 'IN';
  const category = document.getElementById('discovery-category')?.value || 'Technology';
  const difficulty = document.getElementById('discovery-difficulty')?.value || 'All';
  const audience = document.getElementById('discovery-audience')?.value || 'Developers & Tech Enthusiasts';

  try {
    let topics = [];
    if (currentDiscoveryMode === 'trending') {
      topics = await API.discoverTrendingTopics(country, category, 15);
    } else {
      topics = await API.discoverRandomTopics(category, difficulty, audience, currentDiscoveryMode === 'evergreen', 12);
    }

    cachedDiscoveryTopics = topics || [];
    renderDiscoveryTopicCards(cachedDiscoveryTopics);
  } catch (err) {
    if (grid) {
      grid.innerHTML = `
        <div style="grid-column: 1 / -1; padding:32px; text-align:center; background:var(--bg-surface-elevated); border-radius:var(--radius-md); border:1px solid var(--border-subtle);">
          <div style="color:var(--danger); font-weight:700; font-size:15px; margin-bottom:8px;">✕ Failed to discover topics</div>
          <div style="color:var(--text-secondary); font-size:12.5px; margin-bottom:16px;">${escapeHtml(err.message)}</div>
          <button class="btn btn-secondary btn-sm" onclick="refreshDiscoveryTopics()">🔄 Retry</button>
        </div>
      `;
    }
    showToast(`Discovery error: ${err.message}`, 'error');
  } finally {
    if (loading) loading.style.display = 'none';
  }
}

function renderDiscoveryTopicCards(topics) {
  const grid = document.getElementById('discovery-topics-grid');
  if (!grid) return;
  grid.innerHTML = '';

  if (!topics || topics.length === 0) {
    grid.innerHTML = `
      <div style="grid-column: 1 / -1; padding:48px; text-align:center; color:var(--text-secondary);">
        <div style="font-size:28px; margin-bottom:8px;">💡</div>
        <div style="font-weight:600; font-size:14px; color:var(--text-primary);">No topics found for this filter combination.</div>
        <div style="font-size:12px; margin-top:4px;">Try selecting 'Technology' or resetting country to India (IN).</div>
      </div>
    `;
    return;
  }

  topics.forEach((t, idx) => {
    const card = document.createElement('div');
    card.className = 'card';
    card.id = `topic-card-${idx}`;
    card.style.margin = '0';
    card.style.display = 'flex';
    card.style.flexDirection = 'column';
    card.style.justifyContent = 'space-between';
    card.style.padding = '18px';
    card.style.border = '1px solid var(--border-subtle)';
    card.style.transition = 'transform 0.15s ease, box-shadow 0.15s ease';

    // Difficulty badge color
    const diffColor = t.estimated_difficulty === 'Beginner' ? 'var(--success)' : (t.estimated_difficulty === 'Advanced' ? 'var(--danger)' : 'var(--warning)');
    const modeBadge = t.discovery_mode === 'trending' ? '🔥 Trending' : (t.discovery_mode === 'evergreen' ? '🌲 Evergreen' : '🎲 Idea');

    // Source link
    const sourceLink = t.source_url ? `<a href="${escapeAttr(t.source_url)}" target="_blank" style="color:var(--accent); font-weight:600; text-decoration:none;">${escapeHtml(t.source || 'Internet Source')} ↗</a>` : `<span>${escapeHtml(t.source || 'Curated')}</span>`;

    // Trend evidence
    const trendEvidence = t.trend_evidence ? `<div style="font-size:11px; color:var(--success); margin-top:4px; font-weight:600;">📈 ${escapeHtml(t.trend_evidence)}</div>` : '';

    card.innerHTML = `
      <div>
        <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:8px; margin-bottom:10px;">
          <span class="status-badge" style="background:var(--accent-light); color:var(--accent); font-size:10.5px; padding:3px 8px;">${modeBadge}</span>
          <span style="font-size:11px; font-weight:700; color:${diffColor};">[Est. ${escapeHtml(t.estimated_difficulty || 'Intermediate')}]</span>
        </div>

        <h3 style="font-size:15px; font-weight:700; color:var(--text-primary); margin:0 0 8px 0; line-height:1.4;">
          ${escapeHtml(t.title)}
        </h3>

        <p style="font-size:12.5px; color:var(--text-secondary); line-height:1.5; margin:0 0 12px 0;">
          ${escapeHtml(t.explanation || t.description || '')}
        </p>

        <div style="background:var(--bg-surface-elevated); padding:8px 10px; border-radius:var(--radius-sm); font-size:11px; color:var(--text-muted); margin-bottom:14px; border:1px solid var(--border-subtle);">
          <div style="display:flex; justify-content:space-between; margin-bottom:3px;">
            <span>Source:</span>
            <span>${sourceLink}</span>
          </div>
          <div style="display:flex; justify-content:space-between; margin-bottom:3px;">
            <span>Search Intent:</span>
            <strong style="color:var(--text-primary);">${escapeHtml(t.search_intent || 'Informational')}</strong>
          </div>
          <div style="display:flex; justify-content:space-between;">
            <span>Audience Fit:</span>
            <span style="color:var(--text-secondary);">${escapeHtml(t.audience_fit || 'Broad Tech')}</span>
          </div>
          ${trendEvidence}
        </div>
      </div>

      <div style="border-top:1px solid var(--border-subtle); padding-top:12px; display:flex; gap:6px; flex-wrap:wrap;">
        <button class="btn btn-secondary btn-sm" onclick="handleTopicResearchAction(${idx})" style="flex:1; min-width:80px;" title="Deep dive research using live sources">
          🔍 Research
        </button>
        <button class="btn btn-primary btn-sm" onclick="handleTopicGenerateArticle(${idx})" style="flex:1.2; min-width:110px;" title="Send topic to Writing Studio and generate">
          🚀 Generate
        </button>
        <button class="btn btn-secondary btn-sm" onclick="handleTopicSaveAction(${idx})" style="padding:6px 9px;" title="Save topic to database">
          💾
        </button>
        <button class="btn btn-secondary btn-sm" onclick="handleTopicDismissAction(${idx})" style="padding:6px 9px; color:var(--text-muted);" title="Dismiss card">
          ✕
        </button>
      </div>
    `;

    grid.appendChild(card);
  });
}

function handleTopicDismissAction(idx) {
  const card = document.getElementById(`topic-card-${idx}`);
  if (card) {
    card.style.opacity = '0';
    card.style.transform = 'scale(0.95)';
    setTimeout(() => {
      card.remove();
      if (cachedDiscoveryTopics[idx]) {
        cachedDiscoveryTopics.splice(idx, 1);
      }
    }, 150);
  }
}

async function handleTopicSaveAction(idx) {
  const topic = cachedDiscoveryTopics[idx];
  if (!topic) return;

  try {
    showToast('Saving topic to ideas database...', 'info');
    await API.saveTopic({
      title: topic.title,
      description: topic.explanation || topic.description || '',
      category: topic.category || 'Technology',
      search_intent: topic.search_intent || 'Informational',
      estimated_difficulty: topic.estimated_difficulty || 'Intermediate',
      audience_fit: topic.audience_fit || 'Developers',
      source: topic.source || 'Discovery',
      source_url: topic.source_url || '',
      discovery_mode: topic.discovery_mode || currentDiscoveryMode,
      trend_evidence: topic.trend_evidence || '',
    });
    showToast(`Topic "${topic.title}" saved to database!`, 'success');
  } catch (err) {
    showToast(`Failed to save topic: ${err.message}`, 'error');
  }
}

function handleTopicGenerateArticle(idx) {
  const topic = cachedDiscoveryTopics[idx];
  if (!topic) return;

  switchTab('create');
  initEmptyStudio();

  const titleInput = document.getElementById('editor-article-title');
  const topicInput = document.getElementById('studio-topic-input');
  const seoTitleInput = document.getElementById('studio-seo-title');
  const intentSelect = document.getElementById('studio-intent');
  const instructionsInput = document.getElementById('studio-instructions');

  if (titleInput) titleInput.value = topic.title;
  if (topicInput) topicInput.value = topic.title;
  if (seoTitleInput) seoTitleInput.value = topic.title;
  if (intentSelect && topic.search_intent) intentSelect.value = topic.search_intent;
  if (instructionsInput && topic.explanation) {
    instructionsInput.value = `Focus on: ${topic.explanation}\nSource Reference: ${topic.source_url || topic.source || 'Real web search'}`;
  }

  showToast(`Topic "${topic.title}" loaded into Studio. Click "Generate Complete Article" or draft directly!`, 'info');
}

async function handleTopicResearchAction(idx) {
  const topic = cachedDiscoveryTopics[idx];
  if (!topic) return;

  showToast(`Conducting deep research for "${topic.title}"...`, 'info');

  try {
    const saved = await API.saveTopic({
      title: topic.title,
      description: topic.explanation || topic.description || '',
      category: topic.category || 'Technology',
      search_intent: topic.search_intent || 'Informational',
      estimated_difficulty: topic.estimated_difficulty || 'Intermediate',
      audience_fit: topic.audience_fit || 'Developers',
      source: topic.source || 'Discovery',
      source_url: topic.source_url || '',
      discovery_mode: topic.discovery_mode || currentDiscoveryMode,
      trend_evidence: topic.trend_evidence || '',
    });

    const res = await API.conductResearch(saved.id);
    switchTab('research');
    showToast(`Research finished with ${res.sources?.length || 0} real citations!`, 'success');
  } catch (err) {
    showToast(`Research error: ${err.message}`, 'error');
  }
}

