/**
 * API client module for Blogger AI Agent.
 * Production hardened with resilient base URLs, connection retries, and strict error handling.
 */

const getApiBase = () => {
  // If running within desktop Electron or local origin
  if (typeof window !== 'undefined' && window.location && window.location.origin && window.location.origin.startsWith('http')) {
    return '';
  }
  return 'http://127.0.0.1:8000';
};

const safeFetch = async (url, options = {}, timeoutMs = 12000) => {
  const fullUrl = url.startsWith('http') ? url : `${getApiBase()}${url}`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const res = await fetch(fullUrl, {
      ...options,
      signal: controller.signal,
    });
    clearTimeout(timer);
    return res;
  } catch (err) {
    clearTimeout(timer);
    if (err.name === 'AbortError') {
      throw new Error(`Request timed out after ${Math.round(timeoutMs / 1000)}s`);
    }
    // Enhance browser "Failed to fetch" message
    if (err.message === 'Failed to fetch' || err.name === 'TypeError') {
      throw new Error('Could not connect to backend service. Please ensure the server is running.');
    }
    throw err;
  }
};

const API = {
  async getDashboardStats() {
    const res = await safeFetch('/api/dashboard/stats');
    if (!res.ok) throw new Error('Failed to load stats');
    return res.json();
  },

  async getTopics() {
    const res = await safeFetch('/api/topics');
    if (!res.ok) throw new Error('Failed to load topics');
    return res.json();
  },

  async discoverTrendingTopics(country = 'IN', category = 'Technology', limit = 12) {
    const res = await safeFetch(`/api/topics/discover/trending?country=${encodeURIComponent(country)}&category=${encodeURIComponent(category)}&limit=${limit}`, {}, 15000);
    if (!res.ok) throw new Error('Failed to discover trending topics');
    return res.json();
  },

  async discoverRandomTopics(mode = 'random', category = 'Technology', difficulty = 'All', audience = 'Developers & Tech Enthusiasts', country = 'IN', limit = 12) {
    const res = await safeFetch(`/api/topics/discover/random?mode=${encodeURIComponent(mode)}&category=${encodeURIComponent(category)}&difficulty=${encodeURIComponent(difficulty)}&audience=${encodeURIComponent(audience)}&country=${encodeURIComponent(country)}&limit=${limit}`, {}, 20000);
    if (!res.ok) throw new Error('Failed to discover topics');
    return res.json();
  },

  async createTopic(data) {
    const res = await safeFetch('/api/topics', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error('Failed to create topic');
    return res.json();
  },

  async deleteTopic(id) {
    const res = await safeFetch(`/api/topics/${id}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Failed to delete topic');
    return res.json();
  },

  async seedDemoTopic() {
    const res = await safeFetch('/api/topics/seed-sample', { method: 'POST' });
    if (!res.ok) throw new Error('Failed to seed demo topic');
    return res.json();
  },

  async getResearchSources(topicId = null, articleId = null) {
    let url = '/api/research/sources?';
    if (topicId) url += `topic_id=${topicId}&`;
    if (articleId) url += `article_id=${articleId}&`;
    const res = await safeFetch(url);
    if (!res.ok) throw new Error('Failed to load research sources');
    return res.json();
  },

  async runResearchForTopic(topicId) {
    const res = await safeFetch(`/api/research/run-for-topic/${topicId}`, { method: 'POST' });
    if (!res.ok) throw new Error('Failed to run research');
    return res.json();
  },

  async getArticles(status = null) {
    const url = status ? `/api/articles?status=${encodeURIComponent(status)}` : '/api/articles';
    const res = await safeFetch(url);
    if (!res.ok) throw new Error('Failed to load articles');
    return res.json();
  },

  async getArticle(id) {
    const res = await safeFetch(`/api/articles/${id}`);
    if (!res.ok) throw new Error('Failed to load article');
    return res.json();
  },

  async updateArticle(id, data) {
    const res = await safeFetch(`/api/articles/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to update article');
    }
    return res.json();
  },

  async deleteArticle(id) {
    const res = await safeFetch(`/api/articles/${id}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Failed to delete article');
    return res.json();
  },

  async startWorkflow(payload) {
    const res = await safeFetch('/api/articles/start-workflow', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }, 180000); // 3 minutes timeout for article generation
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Workflow execution failed');
    }
    return res.json();
  },

  async seedDemoArticle() {
    const res = await safeFetch('/api/articles/seed-demo-article', { method: 'POST' });
    if (!res.ok) throw new Error('Failed to seed demo article');
    return res.json();
  },

  async submitDecision(articleId, decision, feedback = '', blogId = null) {
    let url = `/api/articles/${articleId}/decision`;
    if (blogId) url += `?blog_id=${encodeURIComponent(blogId)}`;
    const res = await safeFetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ decision, feedback }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || data.error || 'Decision failed');
    return data;
  },

  async getBloggerStatus() {
    const res = await safeFetch('/api/blogger/status', {}, 5000);
    if (!res.ok) throw new Error('Failed to fetch Blogger status');
    return res.json();
  },

  async getBloggerBlogs() {
    const res = await safeFetch('/api/blogger/blogs');
    if (!res.ok) throw new Error('Failed to fetch blogs');
    return res.json();
  },

  async getBloggerPosts(blogId = null) {
    const url = blogId ? `/api/blogger/posts?blog_id=${encodeURIComponent(blogId)}` : '/api/blogger/posts';
    const res = await safeFetch(url);
    if (!res.ok) throw new Error('Failed to fetch Blogger posts');
    return res.json();
  },

  async createBloggerDraft(articleId, blogId = null) {
    const res = await safeFetch('/api/blogger/create-draft', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ article_id: articleId, blog_id: blogId }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || data.error || 'Draft creation failed');
    return data;
  },

  async publishBloggerPost(articleId, blogId = null, confirmPublish = true) {
    const res = await safeFetch('/api/blogger/publish', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ article_id: articleId, blog_id: blogId, confirm_publish: confirmPublish }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || data.error || 'Publish failed');
    return data;
  },

  async getSettings() {
    const res = await safeFetch('/api/settings/config');
    if (!res.ok) throw new Error('Failed to load settings');
    return res.json();
  },

  async getAIStatus() {
    const res = await safeFetch('/api/settings/ai-status', {}, 5000);
    if (!res.ok) throw new Error('Failed to check AI status');
    return res.json();
  },

  async testGemini() {
    const res = await safeFetch('/api/settings/test/gemini', { method: 'POST' }, 20000);
    return res.json();
  },

  async testSearch() {
    const res = await safeFetch('/api/settings/test/search', { method: 'POST' }, 15000);
    return res.json();
  },

  async testTrends() {
    const res = await safeFetch('/api/settings/test/trends', { method: 'POST' }, 15000);
    return res.json();
  },

  async testBlogger() {
    const res = await safeFetch('/api/settings/test/blogger', { method: 'POST' }, 15000);
    return res.json();
  },

  async getOllamaModels() {
    const res = await safeFetch('/api/settings/ollama-models', {}, 5000);
    if (!res.ok) throw new Error('Failed to fetch Ollama models');
    return res.json();
  },

  async updateSettings(payload) {
    const res = await safeFetch('/api/settings/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error('Failed to update settings');
    return res.json();
  },

  async getLogs() {
    const res = await safeFetch('/api/settings/logs');
    if (!res.ok) throw new Error('Failed to load logs');
    return res.json();
  },

  async findImagesForArticle(payload) {
    const res = await safeFetch('/api/images/find-for-article', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }, 30000);
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || data.message || 'Image search failed');
    return data;
  },

  async searchImages(query, limit = 8) {
    const res = await safeFetch('/api/images/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, limit }),
    }, 20000);
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || data.message || 'Custom search failed');
    return data;
  },

  async selectFeaturedImage(articleId, image) {
    const res = await safeFetch('/api/images/select-featured', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ articleId, image }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || data.message || 'Failed to save featured image');
    return data;
  },

  async removeFeaturedImage(articleId) {
    const res = await safeFetch('/api/images/remove-featured', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ articleId }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || data.message || 'Failed to remove featured image');
    return data;
  },

  async uploadCustomHeroImage(payload) {
    const res = await safeFetch('/api/images/custom-upload', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || data.message || 'Failed to upload custom image');
    return data;
  },

  async setCustomHeroImageUrl(payload) {
    const res = await safeFetch('/api/images/custom-url', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || data.message || 'Failed to set custom image URL');
    return data;
  },

  async craftImagePrompt(payload) {
    const res = await safeFetch('/api/ai/craft-image-prompt', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error('Failed to craft image query');
    return res.json();
  },

  async generateImage(payload) {
    return this.findImagesForArticle(payload);
  },

  async aiAssist(payload) {
    const res = await safeFetch('/api/articles/ai-assist', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }, 45000);
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || data.message || 'AI Assistant request failed');
    return data;
  },

  async getPublishingHistory() {
    const res = await safeFetch('/api/blogger/history');
    if (!res.ok) throw new Error('Failed to load publishing history');
    return res.json();
  },
};
