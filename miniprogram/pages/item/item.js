const api = require('../../utils/api');
const util = require('../../utils/util');

Page({
  data: {
    id: null,
    item: null,
    loading: true,
    feedbacking: false,
  },

  onLoad(query) {
    this.setData({ id: query.id });
    this.loadItem();
  },

  loadItem() {
    api
      .getItem(this.data.id)
      .then((item) => {
        this.setData({ item, loading: false });
      })
      .catch((err) => {
        this.setData({ loading: false });
        util.toast(err.message || '加载失败');
      });
  },

  /** 播放发音(百度 TTS 链接) */
  playTts() {
    const item = this.data.item;
    if (!item || !item.src_tts) {
      util.toast('该条目没有发音');
      return;
    }
    const audio = wx.createInnerAudioContext();
    audio.src = item.src_tts;
    audio.onError(() => util.toast('发音播放失败'));
    audio.play();
  },

  /** 复习反馈: yes / no / reset */
  onFeedback(e) {
    const action = e.currentTarget.dataset.action;
    if (this.data.feedbacking) {
      return;
    }
    this.setData({ feedbacking: true });
    api
      .feedback(this.data.id, action)
      .then((res) => {
        if (!res.success) {
          util.toast(res.message || '操作失败');
          return;
        }
        util.toast(`${res.mastery} ✓`);
        if (action === 'reset') {
          // 重置后条目不再属于当天复习,直接返回列表
          setTimeout(() => wx.navigateBack(), 600);
        } else {
          // yes/no 仅更新熟练度,刷新本页展示
          this.loadItem();
        }
      })
      .catch((err) => util.toast(err.message || '操作失败'))
      .then(() => this.setData({ feedbacking: false }));
  },
});
