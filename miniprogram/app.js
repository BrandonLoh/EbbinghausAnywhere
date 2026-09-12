const api = require('./utils/api');

App({
  globalData: {
    loginPromise: null,
  },

  onLaunch() {
    // 与网页版保持一致:西文使用 Source Sans Pro(字体文件由主站托管)
    this.loadWebFont();

    // 启动即尝试静默登录(已有令牌直接通过;否则微信 code 换令牌)
    this.globalData.loginPromise = this.silentLogin();
  },

  /**
   * 加载网页版同款字体(Source Sans Pro,latin 子集)。
   * 尽力而为:加载失败(离线/域名受限且未开调试/低版本基础库)时静默回退系统字体。
   */
  loadWebFont() {
    const fontUrl =
      api.BASE_URL.replace(/\/api\/v1\/?$/, '') +
      '/static/fonts/Source%20Sans%20Pro-14e45a5c291394f5223ada25527b21cd.woff2';
    try {
      wx.loadFontFace({
        global: true,
        family: 'Source Sans Pro',
        source: `url("${fontUrl}")`,
        success: () => {},
        fail: () => {},
      });
    } catch (e) {
      // 低版本基础库不支持 loadFontFace 时忽略
    }
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
