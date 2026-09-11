/** 小工具函数 */

/** 本地日期 → 'YYYY-MM-DD' */
function todayStr() {
  const d = new Date();
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  return `${d.getFullYear()}-${mm}-${dd}`;
}

/** 'YYYY-MM-DD' → Date(避免 iOS 对横杠格式的兼容问题) */
function parseDate(str) {
  const parts = String(str).split('-');
  return new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]));
}

/** 轻提示 */
function toast(title) {
  wx.showToast({ title, icon: 'none' });
}

module.exports = { todayStr, parseDate, toast };
