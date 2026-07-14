/* ============================================
 * 索克家居 · 创始人故事聊天叙事
 * 将 our-story.html 从文章排版改造为聊天对话风格
 * ============================================ */

const StoryNarrative = {
  // ── 故事剧本（老徐与 TRAE 的对话） ──
  script: [
    // === 第一幕：退休那年 ===
    { type: 'system', content: '── 2024 年 · 退休那年 ──' },
    {
      type: 'text', is_self: true, display_name: '老徐', timestamp: '2024-06-15T10:00:00',
      content: '我叫老徐，大半辈子和土地、庄稼、畜禽打交道——农业科研、田间试验、饲料营养、行政管理，干到 2024 年退休，创立了 OPC 公司。',
    },
    {
      type: 'text', is_self: true, display_name: '老徐', timestamp: '2024-06-15T10:02:00',
      content: '中间做过一段家装设计与施工管理，从量房、画图、跑工地，到管预算、盯进度、协调工长和供应商。装修这行的苦和累，我比谁都清楚。',
    },
    {
      type: 'text', is_self: true, display_name: '老徐', timestamp: '2026-01-10T09:00:00',
      content: '2026 年，索克生活 APP 快上线了。想把以前做装修踩过的坑，变成一套普通人也能用起来的智能装修平台。',
    },

    // === 第二幕：遇见 TRAE ===
    { type: 'system', content: '── 2026 年 · 遇见 TRAE ──' },
    {
      type: 'text', agent: 'master', display_name: '🤖 TRAE', timestamp: '2026-01-10T09:05:00',
      content: '你好老徐！我来帮你规划 PRD。从 F1 AR 空间测量到 F40 三方协作 IM，整整 40 个功能模块。',
    },
    {
      type: 'text', agent: 'master', display_name: '🤖 TRAE', timestamp: '2026-01-10T09:08:00',
      content: '每当你不知道先做什么后做什么，我就把需求拆成一个一个可执行的模块：厨房设计器、卫生间设计器、灯光方案、定制家具、智能家居……你一个一个说需求，我一个一个帮你实现。',
    },
    {
      type: 'text', is_self: true, display_name: '老徐', timestamp: '2026-03-15T14:00:00',
      content: '最难的一关是集成阶段。34 个路由模块、300 多个 API 端点、69 张数据表。每次新增功能都要同步更新 models/__init__.py 和 app/main.py，牵一发动全身。',
    },
    {
      type: 'text', agent: 'master', display_name: '🤖 TRAE', timestamp: '2026-03-15T14:10:00',
      content: '我一个文件一个文件修——Python 的、Flutter 的、Shell 脚本的——修完自己跑测试验证。',
    },

    // === 第三幕：测试通过 ===
    {
      type: 'narrative', timestamp: '2026-03-15T14:30:00',
      payload: {
        variant: 'stat', tag: '测试结果', display_name: '🤖 TRAE',
        title: '全量测试通过',
        stat_value: '302 / 311',
        stat_label: '项测试通过 · 9 项跳过',
        body: '看着终端里绿色的"302 项测试全部通过"，老徐觉得：以前觉得搞不定的事，不是因为难，是因为没人帮你一步一步走。',
      },
    },
    {
      type: 'text', is_self: true, display_name: '老徐', timestamp: '2026-04-20T10:00:00',
      content: '鸿蒙适配也是坎。Flutter 官方不支持 HarmonyOS，要配置 DevEco Studio、ohpm、签名证书……折腾两天没搞定。',
    },
    {
      type: 'text', agent: 'master', display_name: '🤖 TRAE', timestamp: '2026-04-20T11:00:00',
      content: '我帮你查文档、改配置、写升级指南。Flutter-OH 3.35.7 + DevEco Studio 6.0.2 + Java 17 + Dart 3.9.2，配齐了。',
    },
    {
      type: 'text', is_self: true, display_name: '老徐', timestamp: '2026-04-20T16:00:00',
      content: '看着 Flutter 应用在 MatePad 上跑起来的那一刻，我对着屏幕笑出了声。',
    },

    // === 第四幕：全量交付 ===
    {
      type: 'narrative', timestamp: '2026-07-01T10:00:00',
      payload: {
        variant: 'stat', tag: '项目成果', display_name: '🤖 TRAE',
        title: '索克家居 · 全量交付',
        stat_value: '40 模块 · 321 API',
        stat_label: '302 项测试通过 · 69 张数据表',
        body: 'Nginx 安全头配置、proxy_pass 尾部斜杠的坑、CSP 策略调试、响应式断点、无障碍属性……这些坑，TRAE 帮我一个一个填了。',
      },
    },

    // === 第五幕：感悟与 CTA ===
    {
      type: 'narrative', timestamp: '2026-07-01T10:05:00',
      payload: {
        variant: 'brand', tag: '老徐的感悟', display_name: '老徐',
        title: '创业很难吗？有了 TRAE，专业背景不再决定你能走多远',
        body: '你只需要深耕一个领域，知道这个领域真正的痛点是什么。剩下的，它会陪你走完。',
      },
    },
    {
      type: 'narrative', timestamp: '2026-07-01T10:06:00',
      payload: {
        variant: 'cta', tag: '开始你的故事', display_name: '🤖 TRAE',
        title: '其实，只要敢想，有了 TRAE 你完全可以飞起来',
        body: '索克家居 · 8 AI 智能体 7×24 自治运营。从测量到结算，一站式 AI 装修平台。',
        cta_text: '返回首页，开始你的 AI 装修之旅', cta_action: 'home',
      },
    },
  ],

  firstScreenCount: 5,
  playInterval: 1800,
  state: { currentIndex: 0, isPlaying: false, hasPaused: false, timer: null },
  dom: { list: null, controls: null, playBtn: null, replayBtn: null, skipBtn: null },

  init() {
    this.dom.list = document.getElementById('story-message-list');
    this.dom.controls = document.getElementById('story-controls');
    this.dom.playBtn = document.getElementById('story-play-btn');
    this.dom.replayBtn = document.getElementById('story-replay-btn');
    this.dom.skipBtn = document.getElementById('story-skip-btn');
    if (!this.dom.list) return;

    this._bindEvents();

    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduceMotion) {
      this._showControls();
      this._appendMessage(this.script[0]);
      this.state.currentIndex = 1;
    } else {
      setTimeout(() => this.play(), 600);
    }
  },

  play() {
    if (this.state.isPlaying) return;
    if (this.state.currentIndex >= this.script.length) { this._onEnd(); return; }
    this.state.isPlaying = true;
    this._updateBtn('pause');
    this._playNext();
  },
  pause() {
    this.state.isPlaying = false;
    if (this.state.timer) { clearTimeout(this.state.timer); this.state.timer = null; }
    this._updateBtn('play');
  },
  replay() {
    this.pause();
    this.state.currentIndex = 0;
    this.state.hasPaused = false;
    this.dom.list.innerHTML = '';
    this.play();
  },
  skip() {
    this.pause();
    while (this.state.currentIndex < this.script.length) {
      this._appendMessage(this.script[this.state.currentIndex]);
      this.state.currentIndex++;
    }
    this._onEnd();
  },
  _playNext() {
    if (!this.state.isPlaying) return;
    if (this.state.currentIndex >= this.script.length) { this._onEnd(); return; }
    this._appendMessage(this.script[this.state.currentIndex]);
    this.state.currentIndex++;
    if (this.state.currentIndex === this.firstScreenCount && !this.state.hasPaused) {
      this.state.hasPaused = true;
      this.pause();
      this._showControls();
      return;
    }
    this.state.timer = setTimeout(() => this._playNext(), this.playInterval);
  },
  _onEnd() {
    this.state.isPlaying = false;
    this._updateBtn('done');
    this._showControls();
  },

  _appendMessage(msg) {
    const html = MessageRenderers.render(msg, 'owner');
    if (!html) return;
    this.dom.list.insertAdjacentHTML('beforeend', html);
    this.dom.list.scrollTop = this.dom.list.scrollHeight;
  },

  _showControls() {
    if (this.dom.controls) {
      this.dom.controls.classList.add('visible');
      this.dom.controls.setAttribute('aria-hidden', 'false');
    }
  },
  _updateBtn(state) {
    if (!this.dom.playBtn) return;
    const icons = { play: '▶', pause: '⏸', done: '✓' };
    const labels = { play: '继续播放', pause: '暂停', done: '播放完毕' };
    this.dom.playBtn.textContent = icons[state] || '▶';
    this.dom.playBtn.setAttribute('aria-label', labels[state] || '播放');
  },

  _bindEvents() {
    if (this.dom.playBtn) {
      this.dom.playBtn.addEventListener('click', () => {
        if (this.state.isPlaying) this.pause();
        else if (this.state.currentIndex >= this.script.length) this.replay();
        else this.play();
      });
    }
    if (this.dom.replayBtn) this.dom.replayBtn.addEventListener('click', () => this.replay());
    if (this.dom.skipBtn) this.dom.skipBtn.addEventListener('click', () => this.skip());

    // CTA 事件委托
    document.addEventListener('click', (e) => {
      const cta = e.target.closest('[data-narrative-cta]');
      if (cta) {
        const action = cta.dataset.narrativeCta;
        if (action === 'home') window.location.href = 'index.html';
        else if (action === 'login') window.location.href = 'login.html';
        else if (action === 'lead') window.location.href = 'index.html';
      }
    });
  },
};

window.StoryNarrative = StoryNarrative;
