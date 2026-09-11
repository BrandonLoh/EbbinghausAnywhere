/**
 * 后端 API 封装。
 *
 * BASE_URL 指向主站(PythonAnywhere)的 REST API;换环境只改这一行。
 * 端点与 docs/ARCHITECTURE_PLAN.md §2.3 一一对应。
 */

const BASE_URL = 'https://ebbinghaus.pythonanywhere.com/api/v1';

const TOKEN_KEY = 'eaw_token';

function getToken() {
  return wx.getStorageSync(TOKEN_KEY) || '';
}

function setToken(token) {
  wx.setStorageSync(TOKEN_KEY, token);
}

function clearToken() {
  wx.removeStorageSync(TOKEN_KEY);
}

/**
 * 统一请求封装:
 * - 自动注入 Authorization: Token xxx
 * - 401/403 → 清除令牌并跳转登录页
 * - 其余错误 → reject 后端返回的错误信息
 */
function request(path, { method = 'GET', data = null, auth = true } = {}) {
  return new Promise((resolve, reject) => {
    const header = { 'Content-Type': 'application/json' };
    const token = getToken();
    if (auth && token) {
      header.Authorization = `Token ${token}`;
    }

    wx.request({
      url: `${BASE_URL}${path}`,
      method,
      header,
      data,
      timeout: 20000,
      success(res) {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data);
          return;
        }
        if (res.statusCode === 401 || res.statusCode === 403) {
          clearToken();
          wx.showToast({ title: '登录已过期，请重新登录', icon: 'none' });
          wx.reLaunch({ url: '/pages/login/login' });
          reject(new Error('unauthorized'));
          return;
        }
        const detail = (res.data && (res.data.detail || res.data.message)) || `请求失败(${res.statusCode})`;
        reject(new Error(detail));
      },
      fail() {
        reject(new Error('网络异常，请检查网络连接'));
      },
    });
  });
}

module.exports = {
  BASE_URL,
  getToken,
  setToken,
  clearToken,

  /** 账号密码登录(调试兜底) → {token, user} */
  login(username, password) {
    return request('/auth/login/', {
      method: 'POST',
      auth: false,
      data: { username, password },
    });
  },

  /** 微信静默登录 → {token, user} 或 {bind_required: true} */
  wechatLogin(code) {
    return request('/auth/wechat/', {
      method: 'POST',
      auth: false,
      data: { code },
    });
  },

  /** 首次绑定 → {token, user} */
  wechatBind(code, username, password) {
    return request('/auth/wechat/bind/', {
      method: 'POST',
      auth: false,
      data: { code, username, password },
    });
  },

  /** 首页统计 */
  getMe() {
    return request('/me/');
  },

  /** 按日期取复习清单(按类别分组, 组内按间隔天数升序) */
  getReview(date) {
    return request(`/review/?date=${date}`);
  },

  /** 复习反馈: action = yes | no | reset */
  feedback(id, action) {
    return request('/review/feedback/', {
      method: 'POST',
      data: { id, action },
    });
  },

  /** 条目详情(含音标 / TTS / 内容) */
  getItem(id) {
    return request(`/items/${id}/`);
  },

  /** 条目列表(分页 / 搜索) */
  getItems({ page = 1, q = '' } = {}) {
    const query = [`page=${page}`];
    if (q) {
      query.push(`q=${encodeURIComponent(q)}`);
    }
    return request(`/items/?${query.join('&')}`);
  },
};
