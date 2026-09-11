const api = require('../../utils/api');
const util = require('../../utils/util');

Page({
  data: {
    date: '',
    groups: [],
    totalCount: 0,
    loading: true,
  },

  onLoad(query) {
    this.setData({ date: query.date || util.todayStr() });
  },

  onShow() {
    // 从条目详情返回时自动刷新(反馈可能改变列表)
    this.loadReview();
  },

  onPickDate(e) {
    this.setData({ date: e.detail.value });
    this.loadReview();
  },

  loadReview() {
    this.setData({ loading: true });
    api
      .getReview(this.data.date)
      .then((data) => {
        const groups = (data.categories || []).filter((g) => g.items.length > 0);
        const totalCount = groups.reduce((sum, g) => sum + g.items.length, 0);
        this.setData({ groups, totalCount, loading: false });
      })
      .catch((err) => {
        this.setData({ loading: false });
        util.toast(err.message || '加载失败');
      });
  },

  goItem(e) {
    wx.navigateTo({ url: `/pages/item/item?id=${e.currentTarget.dataset.id}` });
  },
});
