/**
 * 客户端 Markdown 渲染。
 *
 * - 页面中所有带 data-markdown 属性的元素,其文本内容会被解析为 Markdown 后渲染。
 * - 渲染前先把公式片段($...$、$$...$$、\(...\)、\[...\])替换为占位符,
 *   避免 Markdown 语法(如 _斜体_)破坏公式;渲染后再还原并交给 MathJax。
 * - 输出经过 DOMPurify 消毒,防止存储型 XSS。
 * - marked 或 DOMPurify 加载失败时,保留原始文本不渲染(优雅降级)。
 *
 * AJAX 动态插入内容后,请手动调用: window.renderMarkdown(containerEl)
 */
(function () {
    'use strict';

    if (typeof marked === 'undefined' || typeof DOMPurify === 'undefined') {
        return; // 依赖库未加载,保留原始文本
    }

    // breaks: 单个换行渲染为 <br>,与旧版 white-space: pre-line 的显示行为保持一致,
    // 兼容既有按行组织的词典释义数据
    marked.setOptions({ gfm: true, breaks: true });

    function escapeHtml(s) {
        return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }

    function renderElement(el) {
        var raw = el.textContent;
        if (!raw.trim()) {
            return;
        }

        // 1. 暂存公式片段,避免被 Markdown 语法破坏
        var mathStore = [];
        function stashMath(match) {
            mathStore.push(match);
            return 'MATHPLACEHOLDER' + (mathStore.length - 1) + 'ENDMATH';
        }
        var text = raw
            .replace(/\$\$[\s\S]+?\$\$/g, stashMath)
            .replace(/\\\[[\s\S]+?\\\]/g, stashMath)
            .replace(/\\\([\s\S]+?\\\)/g, stashMath)
            .replace(/\$[^$\n]+?\$/g, stashMath);

        // 2. Markdown -> HTML,并消毒
        var html = DOMPurify.sanitize(marked.parse(text), {
            USE_PROFILES: { html: true },
        });

        // 3. 还原公式(HTML 转义后作为纯文本插入,交给 MathJax 渲染)
        html = html.replace(/MATHPLACEHOLDER(\d+)ENDMATH/g, function (m, i) {
            return escapeHtml(mathStore[Number(i)]);
        });

        el.innerHTML = html;
        el.classList.add('md-rendered'); // 关闭 pre-line 兜底,使用 Markdown 块级排版
    }

    function typesetMath(scope) {
        // MathJax 尚未加载完成时跳过——MathJax 加载后会自行对全页做初始排版;
        // 已加载完成时通过 startup.promise 排队执行,避免与其它排版请求竞争
        if (window.MathJax && window.MathJax.startup && window.MathJax.startup.promise) {
            window.MathJax.startup.promise.then(function () {
                window.MathJax.typesetPromise([scope]).catch(function () {});
            }).catch(function () {});
        }
    }

    function renderAll(scope) {
        var root = scope || document;
        var nodes = root.querySelectorAll('[data-markdown]');
        nodes.forEach(renderElement);
        if (nodes.length > 0) {
            typesetMath(root);
        }
        return nodes.length;
    }

    window.renderMarkdown = renderAll;

    document.addEventListener('DOMContentLoaded', function () {
        renderAll(document);
    });
})();
