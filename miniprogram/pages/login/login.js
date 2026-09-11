const api = require('../../utils/api');
const util = require('../../utils/util');

Page({
  data: {
    username: '',
    password: '',
    submitting: false,
  },

  onLoad() {
    // 已有令牌则直接回首页
    if (api.getToken()) {
      wx.reLaunch({ url: '/pages/index/index' });
    }
  },

  onUsername(e) {
    this.setData({ username: e.detail.value });
  },

  onPassword(e) {
    this.setData({ password: e.detail.value });
  },

  /** 主流程:微信 code + 账号密码 → 绑定并登录 */
  onBind() {
    const { username, password } = this.data;
    if (!username || !password) {
      util.toast('请填写账号和密码');
      return;
    }
    this.setData({ submitting: true });
    wx.login({
      success: (res) => {
        if (!res.code) {
          this.setData({ submitting: false });
          util.toast('微信登录失败，请重试');
          return;
        }
        api
          .wechatBind(res.code, username, password)
          .then((data) => {
            api.setToken(data.token);
            wx.reLaunch({ url: '/pages/index/index' });
          })
          .catch((err) => {
            util.toast(err.message || '绑定失败');
          })
          .then(() => this.setData({ submitting: false }));
      },
      fail: () => {
        this.setData({ submitting: false });
        util.toast('微信登录失败，请重试');
      },
    });
  },

  /** 调试兜底:只用账号密码登录(PA 未配置微信密钥时可用) */
  onDirectLogin() {
    const { username, password } = this.data;
    if (!username || !password) {
      util.toast('请填写账号和密码');
      return;
    }
    this.setData({ submitting: true });
    api
      .login(username, password)
      .then((data) => {
        api.setToken(data.token);
        wx.reLaunch({ url: '/pages/index/index' });
      })
      .catch((err) => util.toast(err.message || '登录失败'))
      .then(() => this.setData({ submitting: false }));
  },
});
