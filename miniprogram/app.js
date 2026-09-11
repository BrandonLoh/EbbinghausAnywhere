const api = require('./utils/api');

App({
  globalData: {
    loginPromise: null,
  },

  onLaunch() {
    // 启动即尝试静默登录(已有令牌直接通过;否则微信 code 换令牌)
    this.globalData.loginPromise = this.silentLogin();
  },

  /**
   * 静默登录:
   * - 已有令牌 → 直接返回
   * - 未绑定微信 / 微信侧不可用 → 返回 null(页面负责跳转登录页)
   */
  silentLogin() {
    const token = api.getToken();
    if (token) {
      return Promise.resolve(token);
    }
    return new Promise((resolve) => {
      wx.login({
        success: (res) => {
          if (!res.code) {
            resolve(null);
            return;
          }
          api
            .wechatLogin(res.code)
            .then((data) => {
              if (data && data.token) {
                api.setToken(data.token);
                resolve(data.token);
              } else {
                resolve(null); // bind_required: 需要用户到登录页绑定一次
              }
            })
            .catch(() => resolve(null));
        },
        fail: () => resolve(null),
      });
    });
  },

  /** 页面调用:确保已登录,返回令牌或 null */
  ensureLogin() {
    const token = api.getToken();
    if (token) {
      return Promise.resolve(token);
    }
    if (!this.globalData.loginPromise) {
      this.globalData.loginPromise = this.silentLogin();
    }
    return this.globalData.loginPromise;
  },
});
