const { createApp } = Vue;

const app = createApp({
  data() {
    return {
      activeTab: "dashboard",
      systemStatus: {
        status: "stopped",
        monitor: null,
        senders: [],
        queue_size: 0,
        monitor_session_exists: false,
        worker_running: false,
        worker_count: 0,
      },
      // 本地 sessions 列表（sessions 目录下的 .session 文件名，不含后缀）
      localSessions: [],
      config: {
        telegram: {},
        proxy: {},
        filter: {},
        system: {},
      },
      logs: [],
      stats: {
        total_messages: 0,
        total_senders: 0,
        stats: [],
      },
      logFilter: "",
      sourceGroupsInput: "",
      myGroupsInput: "",
      filterKeywordsInput: "",
      newSenderName: "",
      loading: false,
      scriptLoading: false,
      scriptRunning: false,
      autoRefreshInterval: null,
      avatarCacheBuster: 0,
      nicknameDialog: {
        visible: false,
        sessionName: "",
        targetType: "sender",
        nickname: "",
        updatePhoto: false,
        photoFile: null,
        photoName: "",
        submitting: false,
      },
    };
  },

  computed: {
    filteredLogs() {
      if (!this.logFilter) {
        return this.logs;
      }
      return this.logs.filter((log) => log.level === this.logFilter);
    },
    // 合并本地 session 与后台返回的 senders 状态
    allSessions() {
      const activeMap = {};
      (this.systemStatus.senders || []).forEach((s) => {
        activeMap[s.session_name] = s;
      });

      let workingUsed = 0;
      const workingLimit = this.workingCount;
      const names = [...this.localSessions];
      (this.systemStatus.senders || []).forEach((s) => {
        if (s.session_name && !names.includes(s.session_name)) {
          names.push(s.session_name);
        }
      });

      return names.map((name) => {
        const active = activeMap[name];
        const hasLocalFile = this.localSessions.includes(name);
        const isActive = active ? active.is_active : false;
        const isWorking =
          this.systemStatus.worker_running &&
          isActive &&
          workingUsed < workingLimit;
        if (isWorking) {
          workingUsed += 1;
        }
        return {
          session_name: name,
          has_local_file: hasLocalFile,
          username: active ? active.username : "",
          display_name: active ? active.display_name : "",
          phone_number: active ? active.phone_number : "",
          user_id: active ? active.user_id : "",
          is_active: isActive,
          is_working: isWorking,
          target_groups_configured: active ? active.target_groups_configured : undefined,
          target_groups_ok: active ? active.target_groups_ok : undefined,
          target_groups_missing: active ? active.target_groups_missing : [],
        };
      });
    },
    workingCount() {
      if (typeof this.systemStatus.worker_count === "number") {
        return this.systemStatus.worker_count;
      }
      if (this.systemStatus.worker_running) {
        const maxTasks = this.config?.system?.max_concurrent_tasks;
        return typeof maxTasks === "number" ? maxTasks : 0;
      }
      return 0;
    },
    sourceGroupsText() {
      const groups = this.config?.telegram?.source_groups || [];
      return Array.isArray(groups) ? groups.join(", ") : `${groups || ""}`;
    },
    targetGroupsText() {
      const groups = this.config?.telegram?.my_groups || [];
      return Array.isArray(groups) ? groups.join(", ") : `${groups || ""}`;
    },
    monitorListening() {
      return !!(this.systemStatus.monitor && this.systemStatus.monitor.listening);
    },
  },

  methods: {
    // API 调用方法
    async apiCall(method, endpoint, data = null) {
      try {
        const url = endpoint;
        const config = {
          method: method,
          headers: {
            "Content-Type": "application/json",
          },
          timeout: 120000, // 120秒超时（登录需要扫码，可能很慢）
        };

        if (data) {
          config.data = data;
        }

        const response = await axios(url, config);
        return response.data;
      } catch (error) {
        console.error("API 错误:", error);

        // 处理不同类型的错误
        let errorMsg = "请求失败";
        if (error.code === "ECONNABORTED") {
          errorMsg = "请求超时（120秒）- 请检查网络或代理配置";
        } else if (error.response?.data?.error) {
          errorMsg = error.response.data.error;
        } else if (error.message) {
          errorMsg = error.message;
        }

        this.showMessage(errorMsg, "error");
        throw error;
      }
    },

    // 系统相关
    async refreshStatus() {
      try {
        const prevMonitor = this.systemStatus.monitor;
        const prevMonitorSessionExists = this.systemStatus.monitor_session_exists;
        const data = await this.apiCall("GET", "/api/system/status");
        // 标记 API 在线
        this.systemStatus = data;
        this.systemStatus.api_up = true;

        // 脚本运行状态由接口中的 status 字段提供
        this.scriptRunning = data && data.status === "running";
        // 供模板使用的脚本运行标志
        this.systemStatus.script_running = this.scriptRunning;

        // 保留监控号的扩展字段（监听/源群状态），避免被自动刷新覆盖
        if (prevMonitor && this.systemStatus.monitor) {
          this.systemStatus.monitor.listening = prevMonitor.listening;
          this.systemStatus.monitor.source_groups_configured = prevMonitor.source_groups_configured;
          this.systemStatus.monitor.source_groups_ok = prevMonitor.source_groups_ok;
          this.systemStatus.monitor.source_groups_missing = prevMonitor.source_groups_missing;
          this.systemStatus.monitor.display_name = prevMonitor.display_name;
          this.systemStatus.monitor.username = prevMonitor.username;
        }
        if (typeof prevMonitorSessionExists !== "undefined") {
          this.systemStatus.monitor_session_exists = prevMonitorSessionExists;
        }
      } catch (error) {
        console.error("刷新状态失败:", error);
        // API 不可达或发生错误，重置状态并标记 API 离线
        this.systemStatus = {
          status: "stopped",
          monitor: null,
          senders: [],
          queue_size: 0,
          worker_running: false,
          worker_count: 0,
          api_up: false,
          script_running: false,
        };
        this.scriptRunning = false;
      }
    },

    // 加载 sessions 目录下的会话文件列表
    async loadSessionFiles() {
      try {
        const data = await this.apiCall("GET", "/api/sessions/list");
        this.localSessions = data.sessions || [];
      } catch (error) {
        console.error("加载会话文件列表失败:", error);
        this.localSessions = [];
      }
    },

    // 刷新监控号状态（单独）
    // 如果 silent 为 true，则不弹提示（用于自动刷新场景）
    async refreshMonitorStatus(silent = false) {
      try {
        const data = await this.apiCall("POST", "/api/monitor/refresh");
        // 记录是否存在本地 monitor.session
        if (data && typeof data.session_file_exists !== "undefined") {
          this.systemStatus.monitor_session_exists = !!data.session_file_exists;
        }
        // 如果返回的是 {status: 'offline'}，则没有 monitor 对象
        if (data && data.status && data.status === "offline") {
          this.systemStatus.monitor = null;
          if (!silent) {
            if (this.systemStatus.monitor_session_exists) {
              this.showMessage("检测到本地监控会话文件，未登录", "info");
            } else {
              this.showMessage("监控号未登录或离线", "error");
            }
          }
        } else {
          this.systemStatus.monitor = data;
          const alive = data && data.is_active;
          if (!silent) {
            this.showMessage(
              alive ? "监控号活跃" : "监控号未激活/离线",
              alive ? "success" : "error",
            );
          }
        }
      } catch (error) {
        console.error("刷新监控号失败:", error);
      }
    },
    async refreshSendersList() {
      await this.loadSessionFiles();
      await this.refreshSendersStatus();
    },

    triggerMonitorUpload() {
      if (this.$refs && this.$refs.monitorUploadInput) {
        this.showMessage("仅允许上传 1 个监控号 .session 文件，上传新文件会替换旧文件", "info");
        this.$refs.monitorUploadInput.click();
      }
    },

    async uploadMonitorSessions(event) {
      try {
        const files = event && event.target ? event.target.files : null;
        if (!files || files.length === 0) {
          return;
        }
        const formData = new FormData();
        for (const f of files) {
          formData.append("files", f);
        }

        const url = "/api/monitor/upload-sessions";
        const response = await axios.post(url, formData, {
          timeout: 120000,
        });
        const data = response.data || {};
        this.showMessage(data.message || "上传完成", "success");
        await this.loadSessionFiles();
      } catch (error) {
        console.error("上传会话文件失败:", error);
        let errorMsg = "上传失败";
        if (error.code === "ECONNABORTED") {
          errorMsg = "上传超时（120秒）";
        } else if (error.response?.data?.error) {
          errorMsg = error.response.data.error;
        } else if (error.message) {
          errorMsg = error.message;
        }
        this.showMessage(errorMsg, "error");
      } finally {
        if (event && event.target) {
          event.target.value = "";
        }
      }
    },

    triggerSenderUpload() {
      if (this.$refs && this.$refs.senderUploadInput) {
        this.$refs.senderUploadInput.click();
      }
    },

    async uploadSenderSessions(event) {
      try {
        const files = event && event.target ? event.target.files : null;
        if (!files || files.length === 0) {
          return;
        }
        const formData = new FormData();
        for (const f of files) {
          formData.append("files", f);
        }

        const url = "/api/sessions/upload";
        const response = await axios.post(url, formData, {
          timeout: 120000,
        });
        const data = response.data || {};
        this.showMessage(data.message || "上传完成", "success");
        await this.loadSessionFiles();
      } catch (error) {
        console.error("上传会话文件失败:", error);
        let errorMsg = "上传失败";
        if (error.code === "ECONNABORTED") {
          errorMsg = "上传超时（120秒）";
        } else if (error.response?.data?.error) {
          errorMsg = error.response.data.error;
        } else if (error.message) {
          errorMsg = error.message;
        }
        this.showMessage(errorMsg, "error");
      } finally {
        if (event && event.target) {
          event.target.value = "";
        }
      }
    },

    // 刷新所有克隆号状态
    async refreshSendersStatus() {
      try {
        const data = await this.apiCall("POST", "/api/senders/refresh?check=1");
        if (data && data.senders) {
          this.systemStatus.senders = data.senders;
          this.showMessage("已刷新克隆号状态", "success");
        } else {
          this.showMessage("刷新克隆号失败或无数据", "error");
        }
      } catch (error) {
        console.error("刷新克隆号失败:", error);
      }
    },

    // 刷新单个克隆号并给出提示
    async refreshSender(sessionName) {
      try {
        const data = await this.apiCall("POST", "/api/senders/refresh?check=1");
        if (data && data.senders) {
          this.systemStatus.senders = data.senders;
          const s = data.senders.find((x) => x.session_name === sessionName);
          if (s) {
            this.showMessage(
              s.is_active ? `${sessionName} 活跃` : `${sessionName} 离线`,
              s.is_active ? "success" : "error",
            );
          } else {
            this.showMessage(`${sessionName} 未找到`, "error");
          }
        }
      } catch (error) {
        console.error(`刷新 ${sessionName} 失败:`, error);
      }
    },

    async updateSenderProfile(sessionName) {
      try {
        this.showMessage(`正在更新 ${sessionName} 的资料...`, "info");
        const result = await this.apiCall(
          "POST",
          `/api/senders/update-profile/${sessionName}`,
          { random_name: true, random_photo: true },
        );
        this.showMessage(result.message || "已更新资料", "success");
        this.avatarCacheBuster = Date.now();
      } catch (error) {
        console.error(`更新 ${sessionName} 资料失败:`, error);
      }
    },

    async updateSenderNicknameManual(sessionName) {
      const s = (this.systemStatus.senders || []).find(
        (x) => x.session_name === sessionName,
      );
      if (!s || !s.is_active) {
        this.showMessage("请先登录后再修改", "error");
        return;
      }
      this.openNicknameDialog(sessionName, "sender");
    },

    async updateMonitorProfileManual() {
      if (!this.systemStatus.monitor || !this.systemStatus.monitor.is_active) {
        this.showMessage("请先登录监控号后再修改", "error");
        return;
      }
      this.openNicknameDialog("monitor", "monitor");
    },

    openNicknameDialog(sessionName, targetType = "sender") {
      this.nicknameDialog.visible = true;
      this.nicknameDialog.sessionName = sessionName;
      this.nicknameDialog.targetType = targetType;
      this.nicknameDialog.nickname = "";
      this.nicknameDialog.updatePhoto = false;
      this.nicknameDialog.photoFile = null;
      this.nicknameDialog.photoName = "";
      this.nicknameDialog.submitting = false;
    },

    closeNicknameDialog() {
      this.nicknameDialog.visible = false;
      this.nicknameDialog.sessionName = "";
      this.nicknameDialog.targetType = "sender";
      this.nicknameDialog.nickname = "";
      this.nicknameDialog.updatePhoto = false;
      this.nicknameDialog.photoFile = null;
      this.nicknameDialog.photoName = "";
      this.nicknameDialog.submitting = false;
    },

    onNicknamePhotoChange(event) {
      const file = event && event.target ? event.target.files[0] : null;
      if (file) {
        this.nicknameDialog.photoFile = file;
        this.nicknameDialog.photoName = file.name;
        this.nicknameDialog.updatePhoto = true;
      } else {
        this.nicknameDialog.photoFile = null;
        this.nicknameDialog.photoName = "";
        this.nicknameDialog.updatePhoto = false;
      }
    },

    async submitNicknameDialog() {
      try {
        const name = (this.nicknameDialog.nickname || "").trim();
        if (!name && !this.nicknameDialog.photoFile) {
          this.showMessage("请填写昵称或选择头像", "error");
          return;
        }
        this.nicknameDialog.submitting = true;
        this.showMessage(`正在更新 ${this.nicknameDialog.sessionName} 的资料...`, "info");

        const formData = new FormData();
        if (name) {
          formData.append("name", name);
        }
        if (this.nicknameDialog.photoFile) {
          formData.append("photo", this.nicknameDialog.photoFile);
        }

        const url =
          this.nicknameDialog.targetType === "monitor"
            ? "/api/monitor/update-profile-manual"
            : `/api/senders/update-profile-manual/${this.nicknameDialog.sessionName}`;
        const response = await axios.post(url, formData, {
          timeout: 120000,
        });
        const result = response.data || {};
        this.showMessage(result.message || "资料已更新", "success");
        this.avatarCacheBuster = Date.now();
        this.closeNicknameDialog();
      } catch (error) {
        console.error(`更新 ${this.nicknameDialog.sessionName} 昵称失败:`, error);
        this.nicknameDialog.submitting = false;
        let errorMsg = "更新失败";
        if (error.response?.data?.error) {
          errorMsg = error.response.data.error;
        } else if (error.message) {
          errorMsg = error.message;
        }
        this.showMessage(errorMsg, "error");
      }
    },

    getSenderAvatarUrl(sessionName) {
      const ts = this.avatarCacheBuster || 0;
      return `/api/senders/avatar/${encodeURIComponent(
        sessionName,
      )}?t=${ts}`;
    },

    getMonitorAvatarUrl() {
      const ts = this.avatarCacheBuster || 0;
      return `/api/monitor/avatar?t=${ts}`;
    },

    onAvatarError(event) {
      if (event && event.target) {
        event.target.style.display = "none";
      }
    },

    async startScript() {
      // 防护：如果脚本已在运行，提示并返回
      if (this.scriptRunning) {
        this.showMessage("脚本已经在运行", "error");
        return;
      }

      try {
        this.scriptLoading = true;
        this.showMessage("正在启动脚本...（这可能需要 10-30 秒）", "info");
        const result = await this.apiCall("POST", "/api/script/start");
        this.showMessage(
          result.message ? result.message : "启动成功",
          "success",
        );
        await this.refreshStatus();
      } catch (error) {
        console.error("启动脚本失败:", error);
      } finally {
        this.scriptLoading = false;
      }
    },

    async stopScript() {
      // 防护：如果脚本未运行，则提示并返回
      if (!this.scriptRunning) {
        this.showMessage("脚本没有运行", "error");
        return;
      }

      try {
        this.scriptLoading = true;
        this.showMessage("正在停止脚本...", "info");
        const result = await this.apiCall("POST", "/api/script/stop");
        this.showMessage(
          result.message ? result.message : "停止成功",
          "success",
        );
        await this.refreshStatus();
      } catch (error) {
        console.error("停止脚本失败:", error);
      } finally {
        this.scriptLoading = false;
      }
    },

    // 配置相关
    async loadConfig() {
      try {
        const data = await this.apiCall("GET", "/api/config/all");
        this.config = data;
        this.sourceGroupsInput = data.telegram.source_groups.join(", ");
        if (Array.isArray(data.telegram.my_groups)) {
          this.myGroupsInput = data.telegram.my_groups.join(", ");
        } else if (data.telegram.my_group) {
          this.myGroupsInput = data.telegram.my_group;
        } else {
          this.myGroupsInput = "";
        }
        this.filterKeywordsInput = data.filter.keywords.join(", ");
      } catch (error) {
        console.error("加载配置失败:", error);
      }
    },

    async updateTelegramConfig() {
      try {
        const payload = {
          ...this.config.telegram,
          source_groups: this.sourceGroupsInput.split(",").map((s) => s.trim()).filter(Boolean),
          my_groups: this.myGroupsInput.split(",").map((s) => s.trim()).filter(Boolean),
        };
        await this.apiCall("POST", "/api/config/telegram", payload);
        this.showMessage("✅ Telegram 配置已更新", "success");
      } catch (error) {
        console.error("更新配置失败:", error);
      }
    },

    async updateProxyConfig() {
      try {
        await this.apiCall("POST", "/api/config/proxy", this.config.proxy);
        this.showMessage("✅ 代理配置已更新", "success");
      } catch (error) {
        console.error("更新代理配置失败:", error);
      }
    },

    async updateFilterConfig() {
      try {
        const payload = {
          ...this.config.filter,
          keywords: this.filterKeywordsInput.split(",").map((s) => s.trim()),
        };
        await this.apiCall("POST", "/api/config/filter", payload);
        this.showMessage("✅ 过滤配置已更新", "success");
      } catch (error) {
        console.error("更新过滤配置失败:", error);
      }
    },

    async updateSystemConfig() {
      try {
        await this.apiCall("POST", "/api/config/system", this.config.system);
        this.showMessage("✅ 系统配置已更新", "success");
      } catch (error) {
        console.error("更新系统配置失败:", error);
      }
    },

    // 监控号相关
    async loginMonitor() {
      try {
        this.showMessage(
          "⏳ 正在登录监控号，请扫码...（这可能需要 30-120 秒）",
          "info",
        );
        const result = await this.apiCall("POST", "/api/monitor/login");
        this.showMessage(result.message, "success");
        await this.refreshStatus();
      } catch (error) {
        console.error("监控号登录失败:", error);
      }
    },

    async logoutMonitor() {
      try {
        const result = await this.apiCall("POST", "/api/monitor/logout");
        this.showMessage(result.message, "success");
        await this.refreshStatus();
      } catch (error) {
        console.error("监控号离线失败:", error);
      }
    },

    async joinMonitorAlertGroup() {
      try {
        const result = await this.apiCall("POST", "/api/monitor/join-alert-group");
        this.showMessage(result.message || "alert group joined", "success");
      } catch (error) {
        console.error("Join alert group failed", error);
      }
    },

    async joinMonitorSourceGroups() {
      try {
        const result = await this.apiCall("POST", "/api/monitor/join-source-groups");
        const msg = result && typeof result.joined === 'number'
          ? `joined ${result.joined} source groups`
          : (result.message || "source groups joined");
        this.showMessage(msg, "success");
      } catch (error) {
        console.error("Join source groups failed", error);
      }
    },


    // 开始/停止监控监听（只控制监听任务）
    async startMonitorListening() {
      if (this.monitorListening) {
        this.showMessage("监听已在运行", "info");
        return;
      }
      try {
        this.showMessage("正在启动监控监听...", "info");
        const result = await this.apiCall("POST", "/api/monitor/start-listen");
        this.showMessage(result.message || "已启动监听", "success");
        await this.refreshMonitorStatus(true);
      } catch (error) {
        console.error("启动监控监听失败:", error);
      }
    },

    async stopMonitorListening() {
      if (!this.monitorListening) {
        this.showMessage("监听未运行", "info");
        return;
      }
      try {
        this.showMessage("正在停止监控监听...", "info");
        const result = await this.apiCall("POST", "/api/monitor/stop-listen");
        this.showMessage(result.message || "已停止监听", "success");
        await this.refreshMonitorStatus(true);
      } catch (error) {
        console.error("停止监控监听失败:", error);
      }
    },

    // 克隆号相关
    async loginAllSenders() {
      try {
        const result = await this.apiCall("POST", "/api/senders/login-all");
        this.showMessage(result.message, "success");
        await this.refreshStatus();
      } catch (error) {
        console.error("批量登录失败:", error);
      }
    },

    async createNewSender() {
      try {
        if (!this.newSenderName.trim()) {
          this.showMessage("请输入会话名", "error");
          return;
        }

        this.showMessage(
          "⏳ 正在创建克隆号，请扫码...（这可能需要 30-120 秒）",
          "info",
        );
        const result = await this.apiCall(
          "POST",
          `/api/senders/create/${this.newSenderName.trim()}`,
        );
        this.showMessage(result.message, "success");
        this.newSenderName = "";
        await this.refreshStatus();
      } catch (error) {
        console.error("创建克隆号失败:", error);
      }
    },

    async logoutAllSenders() {
      try {
        const result = await this.apiCall("POST", "/api/senders/logout-all");
        this.showMessage(result.message, "success");
        await this.refreshStatus();
      } catch (error) {
        console.error("批量离线失败:", error);
      }
    },

    async loginSender(sessionName) {
      try {
        const result = await this.apiCall(
          "POST",
          `/api/senders/login/${sessionName}`,
        );
        this.showMessage(result.message, "success");
        await this.refreshStatus();
      } catch (error) {
        console.error(`登录 ${sessionName} 失败:`, error);
      }
    },

    async logoutSender(sessionName) {
      try {
        const result = await this.apiCall(
          "POST",
          `/api/senders/logout/${sessionName}`,
        );
        this.showMessage(result.message, "success");
        await this.refreshStatus();
      } catch (error) {
        console.error(`离线 ${sessionName} 失败:`, error);
      }
    },


    async deleteSender(sessionName) {
      try {
        const ok = window.confirm(`Delete sender ${sessionName}? This will remove its session file and clear list records.`);
        if (!ok) {
          return;
        }
        const result = await this.apiCall(
          "DELETE",
          `/api/senders/delete/${encodeURIComponent(sessionName)}`,
        );
        this.showMessage(result.message || `${sessionName} deleted`, "success");
        this.localSessions = this.localSessions.filter((name) => name !== sessionName);
        this.systemStatus.senders = (this.systemStatus.senders || []).filter(
          (s) => s.session_name !== sessionName,
        );
        await this.refreshSendersList();
      } catch (error) {
        console.error(`Delete ${sessionName} failed:`, error);
      }
    },

    // 日志相关
    async refreshLogs() {
      try {
        const data = await this.apiCall("GET", "/api/logs/recent?limit=200");
        this.logs = data.logs || [];
      } catch (error) {
        console.error("刷新日志失败:", error);
      }
    },

    // 统计相关
    async loadStats() {
      try {
        const data = await this.apiCall("GET", "/api/system/stats?days=7");
        this.stats = data;
      } catch (error) {
        console.error("加载统计失败:", error);
      }
    },

    // 工具方法
    formatTime(timestamp) {
      try {
        const date = new Date(timestamp);
        return date.toLocaleTimeString("zh-CN");
      } catch (e) {
        return timestamp;
      }
    },

    showMessage(message, type = "info") {
      // 简单的消息显示（可以集成更复杂的通知系统）
      console.log(`[${type.toUpperCase()}] ${message}`);

      // 可选：添加页面上的消息显示
      const msgEl = document.createElement("div");
      msgEl.className = `message message-${type}`;
      msgEl.textContent = message;
      msgEl.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                padding: 12px 16px;
                background-color: ${type === "success" ? "#4caf50" : type === "error" ? "#f44336" : "#2196f3"};
                color: white;
                border-radius: 4px;
                z-index: 9999;
                animation: slideIn 0.3s ease;
            `;
      document.body.appendChild(msgEl);

      setTimeout(() => msgEl.remove(), 3000);
    },

    startAutoRefresh() {
      this.autoRefreshInterval = setInterval(() => {
        if (this.activeTab !== "accounts") {
          this.refreshStatus();
        }
        if (this.activeTab === "logs") {
          this.refreshLogs();
        }
      }, 5000);
    },

    stopAutoRefresh() {
      if (this.autoRefreshInterval) {
        clearInterval(this.autoRefreshInterval);
      }
    },
  },

  watch: {
    activeTab(newTab) {
      // 切换标签页时加载相关数据
      if (newTab === "config") {
        this.loadConfig();
      } else if (newTab === "accounts") {
        this.refreshSendersList();
        this.refreshMonitorStatus(true);
      } else if (newTab === "logs") {
        this.refreshLogs();
      } else if (newTab === "stats") {
        this.loadStats();
      }
    },
  },

  mounted() {
    // 初始化
    this.refreshStatus();
    this.loadConfig();
    this.refreshSendersList();
    if (this.activeTab === "accounts") {
      this.refreshMonitorStatus(true);
    }
    this.startAutoRefresh();

    // 页面卸载时清理
    window.addEventListener("beforeunload", () => {
      this.stopAutoRefresh();
    });
  },

  beforeUnmount() {
    this.stopAutoRefresh();
  },
});

app.mount("#app");

// 添加一些全局样式
const style = document.createElement("style");
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(400px);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
`;
document.head.appendChild(style);
