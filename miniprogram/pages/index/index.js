const api = require('../../utils/api');
const util = require('../../utils/util');

Page({
  data: {
    displayName: '',
    stats: { total_items: 0, days_since_first_item: 0, today_due: 0 },
    today: '',
    loading: true,
  },

  onShow() {
    this.setData({ today: util.todayStr() });
    getApp()
      .ensureLogin()
      .then((token) => {
        if (!token) {
          wx.reLaunch({ url: '/pages/login/login' });
          return;
        }
        this.loadMe();
      });
  },

  loadMe() {
    api
      .getMe()
      .then((data) => {
        this.setData({
          displayName: data.user.display_name,
          stats: data.stats,
          loading: false,
        });
      })
      .catch((err) => {
        this.setData({ loading: false });
        util.toast(err.message || '加载失败');
      });
  },

  /** 复习今天 */
  goToday() {
    wx.navigateTo({ url: `/pages/review/review?date=${this.data.today}` });
  },

  /** 复习指定日期 */
  onPickDate(e) {
    wx.navigateTo({ url: `/pages/review/review?date=${e.detail.value}` });
  },

  onLogout() {
    wx.showModal({
      title: '退出登录',
      content: '退出后需要重新绑定才能使用，确定吗？',
      success: (res) => {
        if (res.confirm) {
          api.clearToken();
          wx.reLaunch({ url: '/pages/login/login' });
        }
      },
    });
  },
});
