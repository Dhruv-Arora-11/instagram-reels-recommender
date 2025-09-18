(() => {
  const API_BASE = 'https://instagram-reels-recommender.onrender.com';

  const els = {
      authSection: document.getElementById('auth-section'),
      authForm: document.getElementById('auth-form'),
      usernameInput: document.getElementById('username-input'),
      authError: document.getElementById('auth-error'),
      reelsSection: document.getElementById('reels-section'),
      currentUsername: document.getElementById('current-username'),
      logoutBtn: document.getElementById('logout-btn'),
      reelContainer: document.getElementById('reel-container'),
      prevBtn: document.getElementById('prev-btn'),
      nextBtn: document.getElementById('next-btn'),
      likeBtn: document.getElementById('like-btn'),
      commentsBtn: document.getElementById('comments-btn'),
      commentsPanel: document.getElementById('comments-panel'),
      commentsClose: document.getElementById('comments-close'),
      commentsList: document.getElementById('comments-list'),
      commentForm: document.getElementById('comment-form'),
      commentInput: document.getElementById('comment-input'),
      muteToggle: document.getElementById('mute-toggle'),
  };

  let state = {
      username: null,
      queue: [],      // upcoming recommendations: {pid, cluster_label}
      index: 0,       // current index in queue
      history: new Set(), // viewed pids for this session
      loading: false,
  };

  // This will store the map of PID -> Cluster
  let pidToClusterMap = {};

  function show(view) {
      els.authSection.classList.toggle('active', view === 'auth');
      els.reelsSection.classList.toggle('active', view === 'reels');
  }

  function persistUsername(username) {
      localStorage.setItem('reels_username', username);
  }
  function restoreUsername() {
      return localStorage.getItem('reels_username');
  }
  function clearUsername() {
      localStorage.removeItem('reels_username');
  }

  async function api(path, options = {}) {
      const res = await fetch(`${API_BASE}${path}`, {
          headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
          ...options,
      });
      if (!res.ok) {
          const error = new Error(`Request failed with status ${res.status}`);
          error.status = res.status;
          try { error.body = await res.json(); } catch { error.body = await res.text(); }
          throw error;
      }
      const contentType = res.headers.get('content-type') || '';
      return contentType.includes('application/json') ? res.json() : res.text();
  }

  async function loginOrSignUp(username) {
      try {
          await api(`/users/${encodeURIComponent(username)}/`);
      } catch (err) {
          if (err.status === 404) {
              await api('/users/', { method: 'POST', body: JSON.stringify({ username }) });
          } else {
              throw err;
          }
      }
      state.username = username;
      persistUsername(username);
      els.currentUsername.textContent = username;
  }

  async function fetchRecommendations() {
      if (!state.username || state.loading) return;
      console.log("Fetching recommendations...");
      // Show loading state
      if (els.reelContainer && !els.reelContainer.children.length) {
          const loading = document.createElement('div');
          loading.className = 'loading-text';
          loading.textContent = 'Loading…';
          els.reelContainer.appendChild(loading);
      }
      state.loading = true;
      try {
          const data = await api(`/users/${encodeURIComponent(state.username)}/recommendations/`);
          const recs = Array.isArray(data.recommendations) ? data.recommendations : [];
          const fresh = recs.filter(item => !state.history.has(item.pid) && !state.queue.find(q => q.pid === item.pid));
          state.queue.push(...fresh);
          console.log("Updated queue:", state.queue);
      } catch(err) {
          console.error("Failed to fetch recommendations:", err);
          // Surface an error to the UI
          if (els.reelContainer) {
              els.reelContainer.innerHTML = '';
              const msg = document.createElement('div');
              msg.className = 'empty-text';
              msg.textContent = 'Could not load recommendations. Please try again later.';
              els.reelContainer.appendChild(msg);
          }
      } finally {
          state.loading = false;
      }
  }

  async function recordInteraction(pid, clusterLabel) {
      if (!state.username || clusterLabel === -1) return; // Don't record likes for unknown clusters
      console.log(`Recording interaction for pid: ${pid}, cluster: ${clusterLabel}`);
      const body = JSON.stringify({ pid, cluster_label: clusterLabel });
      try {
          await api(`/users/${encodeURIComponent(state.username)}/interaction/`, { method: 'POST', body });
      } catch (err) {
          console.warn('Interaction recording failed', err);
      }
  }

  function renderCurrent() {
      els.reelContainer.innerHTML = '';
      if (state.index >= state.queue.length) {
          const empty = document.createElement('div');
          empty.className = 'empty-text';
          empty.textContent = 'No more recommendations. Try liking some videos!';
          els.reelContainer.appendChild(empty);
          return;
      }

      const currentItem = state.queue[state.index];
      const card = document.createElement('div');
      card.className = 'reel-card active';

      // Use a placeholder video, but you would construct the real URL here
      const video = document.createElement('video');
      video.src = `https://fi.ee.tsinghua.edu.cn/datasets/short-video-dataset/raw_file/${currentItem.pid}.mp4`;
      video.autoplay = true;
      video.muted = false; // Sound ON by default; note: some browsers may block autoplay until user interacts
      video.controls = true;
      video.loop = true;
      card.appendChild(video);

      const meta = document.createElement('div');
      meta.className = 'reel-meta';
      meta.textContent = `PID: ${currentItem.pid} | Cluster: ${currentItem.cluster_label}`;
      card.appendChild(meta);

      els.reelContainer.appendChild(card);

      // Update mute button state
      if (els.muteToggle) {
          els.muteToggle.textContent = video.muted ? '🔇' : '🔊';
          els.muteToggle.onclick = () => {
              video.muted = !video.muted;
              els.muteToggle.textContent = video.muted ? '🔇' : '🔊';
          };
      }
  }

  async function likeCurrentVideo() {
      if (state.index >= state.queue.length) return;
      const currentItem = state.queue[state.index];
      try {
          await recordInteraction(currentItem.pid, currentItem.cluster_label);
      } catch (err) {
          console.warn('Like failed', err);
      }
      // Heart animation overlay
      const heart = document.createElement('div');
      heart.className = 'like-heart';
      heart.textContent = '❤';
      els.reelContainer.appendChild(heart);
      setTimeout(() => {
          if (heart.parentNode) heart.parentNode.removeChild(heart);
      }, 1000);
  }


  async function goNext(like = false) {
      if (state.index >= state.queue.length) return;
      
      const currentItem = state.queue[state.index];
      state.history.add(currentItem.pid);

      if (like) {
          await recordInteraction(currentItem.pid, currentItem.cluster_label);
      }

      state.index += 1;
      
      // Prefetch when nearing the end of the queue
      if (state.queue.length - state.index <= 3) {
          fetchRecommendations();
      }
      
      renderCurrent();
  }

  function goPrev() {
      state.index = Math.max(0, state.index - 1);
      renderCurrent();
  }
  
  function setupInteractions() {
      // ... (your existing setupInteractions code can go here)
      els.prevBtn.addEventListener('click', () => goPrev());
      els.nextBtn.addEventListener('click', () => goNext(false));
      els.likeBtn.addEventListener('click', () => likeCurrentVideo());

      // Keyboard navigation
      window.addEventListener('keydown', (e) => {
          if (e.target.tagName === 'INPUT') return; // Don't interfere with typing
          if (e.key === 'ArrowDown' || e.key.toLowerCase() === 'j') goNext(false);
          if (e.key === 'ArrowUp' || e.key.toLowerCase() === 'k') goPrev();
          if (e.key.toLowerCase() === 'l') goNext(true);
      });

      // Comments toggle
      if (els.commentsBtn && els.commentsPanel) {
          els.commentsBtn.addEventListener('click', async () => {
              els.commentsPanel.classList.toggle('hidden');
              if (!els.commentsPanel.classList.contains('hidden')) {
                  await loadCommentsForCurrent();
              }
          });
      }
      if (els.commentsClose) {
          els.commentsClose.addEventListener('click', () => {
              els.commentsPanel.classList.add('hidden');
          });
      }

      // Comment form submit
      if (els.commentForm) {
          els.commentForm.addEventListener('submit', async (e) => {
              e.preventDefault();
              const text = (els.commentInput.value || '').trim();
              if (!text) return;
              const item = state.queue[state.index];
              try {
                  await api(`/videos/${encodeURIComponent(item.pid)}/comments`, { method: 'POST', body: JSON.stringify({ username: state.username, text }) });
                  els.commentInput.value = '';
                  await loadCommentsForCurrent();
              } catch (err) {
                  console.warn('Failed to post comment', err);
              }
          });
      }
  }

  async function loadCommentsForCurrent() {
      if (state.index >= state.queue.length) return;
      const item = state.queue[state.index];
      try {
          const data = await api(`/videos/${encodeURIComponent(item.pid)}/comments`);
          const comments = Array.isArray(data.comments) ? data.comments : [];
          els.commentsList.innerHTML = '';
          if (!comments.length) {
              const empty = document.createElement('div');
              empty.className = 'empty-text';
              empty.textContent = 'No comments yet';
              els.commentsList.appendChild(empty);
              return;
          }
          comments.forEach(c => {
              const row = document.createElement('div');
              row.textContent = `${c.username}: ${c.text}`;
              els.commentsList.appendChild(row);
          });
      } catch (err) {
          console.warn('Failed to load comments', err);
      }
  }

  async function enterReels() {
      show('reels');
      state.queue = [];
      state.index = 0;
      state.history.clear();
      await fetchRecommendations(); // Fetch initial batch
      renderCurrent();
  }

  async function handleAuthSubmit(e) {
      e.preventDefault();
      els.authError.textContent = '';
      const username = (els.usernameInput.value || '').trim();
      if (!username) {
          els.authError.textContent = 'Username is required';
          return;
      }
      try {
          await loginOrSignUp(username);
          await enterReels();
      } catch (err) {
          els.authError.textContent = err.message || 'Failed to sign in';
      }
  }
  
  function handleLogout() {
      clearUsername();
      state.username = null;
      els.usernameInput.value = '';
      show('auth');
  }

  async function init() {
      els.authForm.addEventListener('submit', handleAuthSubmit);
      els.logoutBtn.addEventListener('click', handleLogout);
      setupInteractions();
      
      const savedUsername = restoreUsername();
      if (savedUsername) {
          try {
              await loginOrSignUp(savedUsername);
              await enterReels();
          } catch {
              clearUsername();
              show('auth');
          }
      } else {
          show('auth');
      }
  }

  window.addEventListener('load', init);
})();