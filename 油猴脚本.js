// ==UserScript==
// @name         WNACG 封面标记工具
// @namespace    http://tampermonkey.net/
// @version      1.4
// @description  在WNACG漫画封面上进行标记，并支持数据导入导出及同步到Gemini书架（移除了同步延迟）。
// @author       Gemini
// @match        *://*.wnacg.com/*
// @grant        GM_addStyle
// @grant        GM_registerMenuCommand
// @grant        GM_xmlhttpRequest
// @connect      127.0.0.1
// @connect      localhost
// ==/UserScript==

(function() {
    'use strict';

    // --- 存储设置 (Key定义) ---
    const MASK_STORAGE_KEY = 'processedWnacgImages_alt';
    const LINK_STORAGE_KEY = 'wnacgComicLinks_alt';
    const TITLE_STORAGE_KEY = 'wnacgComicTitles_alt';
    const SRC_STORAGE_KEY = 'wnacgComicSrcs_alt';
    const TIME_STORAGE_KEY = 'wnacgComicTimes_v8';
    const TAGS_STORAGE_KEY = 'wnacgComicTags_v1';
    const AUTO_SYNC_KEY = 'wnacgAutoSyncEnabled_v1'; // 新增：自动同步开关

    // --- 内存数据存储 ---
    const GM_STORE = {
        processedKeys: new Set(),
        links: {},
        titles: {},
        srcs: {},
        times: {},
        tags: {},
        autoSyncEnabled: false, // 新增：自动同步状态
    };

    // --- 数据加载与保存 ---
    function loadDataFromLocalStorage() {
        console.log("[WNACG MOD] 正在从 localStorage 加载数据到内存...");
        try {
            GM_STORE.processedKeys = new Set(JSON.parse(localStorage.getItem(MASK_STORAGE_KEY) || '[]'));
            GM_STORE.links = JSON.parse(localStorage.getItem(LINK_STORAGE_KEY) || '{}');
            GM_STORE.titles = JSON.parse(localStorage.getItem(TITLE_STORAGE_KEY) || '{}');
            GM_STORE.srcs = JSON.parse(localStorage.getItem(SRC_STORAGE_KEY) || '{}');
            GM_STORE.times = JSON.parse(localStorage.getItem(TIME_STORAGE_KEY) || '{}');
            GM_STORE.tags = JSON.parse(localStorage.getItem(TAGS_STORAGE_KEY) || '{}');
            GM_STORE.autoSyncEnabled = JSON.parse(localStorage.getItem(AUTO_SYNC_KEY) || 'false'); // 新增
        } catch (e) {
            console.error("[WNACG MOD] 加载 localStorage 数据失败:", e);
        }
    }

    function saveStoreToLocalStorage() {
        console.log("[WNACG MOD] 正在将内存数据持久化到 localStorage...");
        localStorage.setItem(MASK_STORAGE_KEY, JSON.stringify(Array.from(GM_STORE.processedKeys)));
        localStorage.setItem(LINK_STORAGE_KEY, JSON.stringify(GM_STORE.links));
        localStorage.setItem(TITLE_STORAGE_KEY, JSON.stringify(GM_STORE.titles));
        localStorage.setItem(SRC_STORAGE_KEY, JSON.stringify(GM_STORE.srcs));
        localStorage.setItem(TIME_STORAGE_KEY, JSON.stringify(GM_STORE.times));
        localStorage.setItem(TAGS_STORAGE_KEY, JSON.stringify(GM_STORE.tags));
    }

    // --- 辅助函数 ---
    function stripHtml(html) {
        if (!html) return '';
        let d = document.createElement('div');
        d.innerHTML = html;
        return (d.textContent || d.innerText || '').trim();
    }



    // 新增：获取格式化日期函数 YYYY/MM/DD
    function getFormattedDate() {
        const today = new Date();
        const year = today.getFullYear();
        const month = (today.getMonth() + 1).toString().padStart(2, '0'); // 月份从0开始
        const day = today.getDate().toString().padStart(2, '0');
        return `${year}/${month}/${day}`;
    }

    // --- 我的收藏页面相关函数 ---
    function createFavoritesPage() {
        // 创建页面容器
        const container = document.createElement('div');
        container.id = 'favorites-page';
        container.innerHTML = `
            <div class="favorites-header">
                <h1>我的收藏 <span id="favorites-count"></span></h1>
                <div class="favorites-controls">
                    <input type="text" id="favorites-search" placeholder="搜索漫画...">
                    <select id="favorites-sort">
                        <option value="date_desc">按添加时间 (最新)</option>
                        <option value="date_asc">按添加时间 (最早)</option>
                        <option value="title_asc">按漫画名称 (A-Z)</option>
                        <option value="title_desc">按漫画名称 (Z-A)</option>
                    </select>
                    <button id="batch-manage-btn">批量管理</button>
                </div>
            </div>
            <div id="batch-actions-bar" class="batch-actions-bar" style="display: none;">
                <button id="select-all-btn">全选</button>
                <button id="deselect-all-btn">取消全选</button>
                <button id="delete-selected-btn">删除选中</button>
                <span id="selected-count">已选中 0 项</span>
                <button id="cancel-batch-btn">取消</button>
            </div>
            <div id="favorites-content" class="favorites-content">
                <div id="favorites-grid" class="favorites-grid"></div>
                <div id="favorites-empty" class="favorites-empty" style="display: none;">
                    <p>您的收藏夹还是空的。快去漫画页面点击「收藏」按钮（或打钩）来添加吧！</p>
                </div>
            </div>
        `;
        return container;
    }

    function showFavoritesPage() {
        // 隐藏原页面内容
        const originalContent = document.body.innerHTML;
        document.body.innerHTML = '';
        
        // 创建返回按钮
        const backButton = document.createElement('button');
        backButton.textContent = '← 返回';
        backButton.id = 'back-button';
        backButton.addEventListener('click', () => {
            document.body.innerHTML = originalContent;
            // 重新初始化脚本
            initScript();
        });
        
        // 创建收藏页面
        const favoritesPage = createFavoritesPage();
        
        // 添加到页面
        document.body.appendChild(backButton);
        document.body.appendChild(favoritesPage);
        
        // 添加样式
        addFavoritesStyles();
        
        // 加载并显示收藏内容
        renderFavorites();
        
        // 绑定事件
        bindFavoritesEvents();
    }

    function addFavoritesStyles() {
        GM_addStyle(`
            #back-button {
                position: fixed;
                top: 20px;
                left: 20px;
                padding: 10px 15px;
                background-color: #444;
                color: white;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                z-index: 1000;
            }
            
            #back-button:hover {
                background-color: #555;
            }
            
            #favorites-page {
                padding: 20px;
                padding-top: 70px;
                background-color: #121212;
                color: #e0e0e0;
                min-height: 100vh;
            }
            
            .favorites-header {
                margin-bottom: 30px;
            }
            
            .favorites-header h1 {
                font-size: 2rem;
                margin-bottom: 20px;
            }
            
            .favorites-controls {
                display: flex;
                gap: 15px;
                align-items: center;
                flex-wrap: wrap;
            }
            
            #favorites-search {
                padding: 8px 12px;
                border-radius: 4px;
                border: 1px solid #333;
                background-color: #1e1e1e;
                color: #e0e0e0;
                min-width: 250px;
            }
            
            #favorites-sort {
                padding: 8px 12px;
                border-radius: 4px;
                border: 1px solid #333;
                background-color: #1e1e1e;
                color: #e0e0e0;
            }
            
            #batch-manage-btn, #select-all-btn, #deselect-all-btn, #delete-selected-btn, #cancel-batch-btn {
                padding: 8px 15px;
                border-radius: 4px;
                border: none;
                background-color: #333;
                color: #e0e0e0;
                cursor: pointer;
            }
            
            #batch-manage-btn:hover, #select-all-btn:hover, #deselect-all-btn:hover, 
            #delete-selected-btn:hover, #cancel-batch-btn:hover {
                background-color: #444;
            }
            
            .batch-actions-bar {
                display: flex;
                gap: 10px;
                align-items: center;
                margin: 20px 0;
                padding: 15px;
                background-color: #1e1e1e;
                border-radius: 4px;
            }
            
            /* 浮动批量操作栏样式 */
            .batch-actions-bar.floating {
                position: fixed;
                bottom: 20px;
                left: 50%;
                transform: translateX(-50%);
                z-index: 1000;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
                margin: 0;
                border-radius: 30px;
                padding: 12px 20px;
            }
            
            #selected-count {
                margin-left: auto;
                margin-right: 10px;
            }
            
            .favorites-grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
                gap: 20px;
            }
            
            @media (min-width: 768px) {
                .favorites-grid {
                    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
                }
            }
            
            @media (min-width: 1200px) {
                .favorites-grid {
                    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
                }
            }
            
            .favorite-card {
                background-color: #1e1e1e;
                border-radius: 8px;
                overflow: hidden;
                cursor: pointer;
                transition: transform 0.2s, box-shadow 0.2s;
                position: relative;
            }
            
            .favorite-card:hover {
                transform: translateY(-5px);
                box-shadow: 0 5px 15px rgba(0, 0, 0, 0.5);
            }
            
            .favorite-card.selected {
                box-shadow: 0 0 0 3px #bb86fc;
            }
            
            .favorite-card-checkbox {
                position: absolute;
                top: 10px;
                right: 10px;
                width: 24px;
                height: 24px;
                background-color: rgba(255, 255, 255, 0.2);
                border-radius: 4px;
                display: flex;
                align-items: center;
                justify-content: center;
                z-index: 10;
                display: none;
            }
            
            .favorite-card.selected .favorite-card-checkbox::after {
                content: "✓";
                color: white;
                font-weight: bold;
            }
            
            .favorite-card.batch-mode .favorite-card-checkbox {
                display: flex;
            }
            
            .favorite-card.selected::after {
                content: "";
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background-color: rgba(187, 134, 252, 0.3);
                pointer-events: none;
            }
            
            .favorite-cover {
                width: 100%;
                aspect-ratio: 1/1.4;
                object-fit: cover;
                background-color: #333;
            }
            
            .favorite-title {
                padding: 10px;
                font-size: 0.9rem;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }
            
            .favorites-empty {
                text-align: center;
                padding: 50px;
                font-size: 1.2rem;
                color: #aaa;
            }
            
            .lazy-image {
                background-color: #333;
            }
            
            .lazy-image.loaded {
                background-color: transparent;
            }
        `);
    }

    function renderFavorites(filteredData = null) {
        const grid = document.getElementById('favorites-grid');
        const empty = document.getElementById('favorites-empty');
        const count = document.getElementById('favorites-count');
        
        // 获取数据
        let data = filteredData;
        if (!data) {
            data = [];
            GM_STORE.processedKeys.forEach(key => {
                data.push({
                    key: key,
                    title: GM_STORE.titles[key],
                    link: GM_STORE.links[key],
                    src: GM_STORE.srcs[key],
                    time: GM_STORE.times[key],
                    tags: GM_STORE.tags[key]
                });
            });
            
            // 默认按时间倒序排列（最新的在前面）
            data.sort((a, b) => new Date(b.time) - new Date(a.time));
        }
        
        // 更新计数
        count.textContent = `共收藏 ${data.length} 部漫画`;
        
        // 显示/隐藏空状态
        if (data.length === 0) {
            empty.style.display = 'block';
            grid.style.display = 'none';
            return;
        }
        
        empty.style.display = 'none';
        grid.style.display = 'grid';
        
        // 渲染卡片
        grid.innerHTML = '';
        data.forEach(item => {
            const card = document.createElement('div');
            card.className = 'favorite-card';
            card.dataset.key = item.key;
            
            card.innerHTML = `
                <div class="favorite-card-checkbox"></div>
                <img class="favorite-cover lazy-image" data-src="${item.src}" alt="${item.title}">
                <div class="favorite-title" title="${item.title}">${item.title}</div>
            `;
            
            card.addEventListener('click', (e) => {
                if (document.body.classList.contains('batch-mode')) {
                    e.stopPropagation();
                    toggleCardSelection(card);
                } else {
                    window.open(item.link, '_blank');
                }
            });
            
            grid.appendChild(card);
        });
        
        // 应用懒加载
        applyLazyLoading();
    }

    function applyLazyLoading() {
        const imageObserver = new IntersectionObserver((entries, observer) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    img.src = img.dataset.src;
                    img.classList.add('loaded');
                    observer.unobserve(img);
                }
            });
        });
        
        document.querySelectorAll('.lazy-image').forEach(img => {
            imageObserver.observe(img);
        });
    }

    function bindFavoritesEvents() {
        // 搜索功能
        const searchInput = document.getElementById('favorites-search');
        let searchTimeout;
        searchInput.addEventListener('input', () => {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                const keyword = searchInput.value.toLowerCase().trim();
                if (!keyword) {
                    renderFavorites();
                    return;
                }
                
                const filtered = [];
                GM_STORE.processedKeys.forEach(key => {
                    const title = GM_STORE.titles[key].toLowerCase();
                    if (title.includes(keyword)) {
                        filtered.push({
                            key: key,
                            title: GM_STORE.titles[key],
                            link: GM_STORE.links[key],
                            src: GM_STORE.srcs[key],
                            time: GM_STORE.times[key],
                            tags: GM_STORE.tags[key]
                        });
                    }
                });
                
                renderFavorites(filtered);
            }, 300);
        });
        
        // 排序功能
        const sortSelect = document.getElementById('favorites-sort');
        sortSelect.addEventListener('change', () => {
            const sortValue = sortSelect.value;
            let data = [];
            
            GM_STORE.processedKeys.forEach(key => {
                data.push({
                    key: key,
                    title: GM_STORE.titles[key],
                    link: GM_STORE.links[key],
                    src: GM_STORE.srcs[key],
                    time: GM_STORE.times[key],
                    tags: GM_STORE.tags[key]
                });
            });
            
            switch (sortValue) {
                case 'date_desc':
                    data.sort((a, b) => new Date(b.time) - new Date(a.time));
                    break;
                case 'date_asc':
                    data.sort((a, b) => new Date(a.time) - new Date(b.time));
                    break;
                case 'title_asc':
                    data.sort((a, b) => a.title.localeCompare(b.title));
                    break;
                case 'title_desc':
                    data.sort((a, b) => b.title.localeCompare(a.title));
                    break;
            }
            
            renderFavorites(data);
        });
        
        // 批量管理功能
        const batchManageBtn = document.getElementById('batch-manage-btn');
        const batchActionsBar = document.getElementById('batch-actions-bar');
        const cancelBatchBtn = document.getElementById('cancel-batch-btn');
        
        batchManageBtn.addEventListener('click', () => {
            document.body.classList.add('batch-mode');
            batchActionsBar.style.display = 'flex';
            batchActionsBar.classList.add('floating'); // 添加浮动样式
            document.querySelectorAll('.favorite-card').forEach(card => {
                card.classList.add('batch-mode');
            });
        });
        
        cancelBatchBtn.addEventListener('click', () => {
            exitBatchMode();
        });
        
        // 全选/取消全选
        const selectAllBtn = document.getElementById('select-all-btn');
        const deselectAllBtn = document.getElementById('deselect-all-btn');
        
        selectAllBtn.addEventListener('click', () => {
            document.querySelectorAll('.favorite-card').forEach(card => {
                card.classList.add('selected');
            });
            updateSelectedCount();
        });
        
        deselectAllBtn.addEventListener('click', () => {
            document.querySelectorAll('.favorite-card').forEach(card => {
                card.classList.remove('selected');
            });
            updateSelectedCount();
        });
        
        // 删除选中
        const deleteSelectedBtn = document.getElementById('delete-selected-btn');
        deleteSelectedBtn.addEventListener('click', () => {
            const selectedCards = document.querySelectorAll('.favorite-card.selected');
            if (selectedCards.length === 0) return;
            
            if (confirm(`您确定要删除选中的 ${selectedCards.length} 部漫画吗？此操作不可撤销。`)) {
                selectedCards.forEach(card => {
                    const key = card.dataset.key;
                    GM_STORE.processedKeys.delete(key);
                    delete GM_STORE.links[key];
                    delete GM_STORE.titles[key];
                    delete GM_STORE.srcs[key];
                    delete GM_STORE.times[key];
                    delete GM_STORE.tags[key];
                    card.remove();
                });
                
                saveStoreToLocalStorage();
                updateFavoritesCount();
                exitBatchMode();
                
                // 删除完成后自动同步到Gemini书架
                syncDataToBookshelf();
            }
        });
    }

    function toggleCardSelection(card) {
        card.classList.toggle('selected');
        updateSelectedCount();
    }

    function updateSelectedCount() {
        const selectedCount = document.querySelectorAll('.favorite-card.selected').length;
        document.getElementById('selected-count').textContent = `已选中 ${selectedCount} 项`;
    }

    function updateFavoritesCount() {
        const count = document.getElementById('favorites-count');
        count.textContent = `共收藏 ${GM_STORE.processedKeys.size} 部漫画`;
        
        const empty = document.getElementById('favorites-empty');
        const grid = document.getElementById('favorites-grid');
        if (GM_STORE.processedKeys.size === 0) {
            empty.style.display = 'block';
            grid.style.display = 'none';
        }
    }

    function exitBatchMode() {
        document.body.classList.remove('batch-mode');
        const batchActionsBar = document.getElementById('batch-actions-bar');
        batchActionsBar.style.display = 'none';
        batchActionsBar.classList.remove('floating'); // 移除浮动样式
        document.querySelectorAll('.favorite-card').forEach(card => {
            card.classList.remove('batch-mode', 'selected');
        });
    }

    // --- 数据管理核心功能 ---

    // 1. 导出
    function downloadAsFile(filename, text) {
        try {
            const blob = new Blob([text], { type: 'application/json;charset=utf-8' });
            const url = URL.createObjectURL(blob);
            const e = document.createElement('a');
            e.href = url;
            e.download = filename;
            e.style.display = 'none';
            document.body.appendChild(e);
            e.click();
            document.body.removeChild(e);
            URL.revokeObjectURL(url);
            console.log("[WNACG MOD] 数据导出成功。");
            window.alert("数据导出成功！");
        } catch (error) {
            console.error("[WNACG MOD] 数据导出失败:", error);
            window.alert("数据导出失败。请检查浏览器控制台获取更多信息。");
        }
    }

    function exportData() {
        const dataToExport = {
            processedImages: Array.from(GM_STORE.processedKeys),
            comicLinks: GM_STORE.links,
            comicTitles: GM_STORE.titles,
            comicSrcs: GM_STORE.srcs,
            comicTags: GM_STORE.tags,
            comicTimes: GM_STORE.times,
        };
        const jsonText = JSON.stringify(dataToExport, null, 2);
        downloadAsFile(`wnacg-backup-${new Date().toISOString().replace(/[:.]/g, '-')}.json`, jsonText);
    }

    // 2. 导入
    function handleFileImport(file) {
        const reader = new FileReader();
        reader.onload = (e) => {
            let data;
            try {
                data = JSON.parse(e.target.result);
                if (typeof data !== 'object' || data === null) throw new Error('无效的JSON文件');
            } catch (err) {
                window.alert('读取文件失败: ' + err.message);
                return;
            }

            // 合并数据到内存 STORE
            const importedKeys = data.processedImages || [];

            let newKeysCount = 0;
            importedKeys.forEach(k => { if (!GM_STORE.processedKeys.has(k)) { GM_STORE.processedKeys.add(k); newKeysCount++; } });

            Object.assign(GM_STORE.links, data.comicLinks || {});
            Object.assign(GM_STORE.titles, data.comicTitles || {});
            Object.assign(GM_STORE.srcs, data.comicSrcs || {});
            Object.assign(GM_STORE.times, data.comicTimes || {});
            Object.assign(GM_STORE.tags, data.comicTags || {});

            saveStoreToLocalStorage();
            
            window.alert(`导入成功！\n- 新增 ${newKeysCount} 条漫画记录。\n- 其他数据已合并。\n\n请刷新页面查看更新。`);
            location.reload();
        };
        reader.readAsText(file);
    }

    function importData() {
        let input = document.createElement('input');
        input.type = 'file';
        input.accept = '.json,.txt';
        input.style.display = 'none';
        input.onchange = (e) => {
            const file = e.target.files[0];
            if (file) {
                handleFileImport(file);
            }
            document.body.removeChild(input);
        };
        document.body.appendChild(input);
        input.click();
    }

    // 3. 清空数据
    function clearAllData() {
        if (window.confirm('警告：此操作将永久删除所有已标记的漫画数据，无法撤销！\n\n确定要清空全部数据吗？')) {
            const keysToRemove = [
                MASK_STORAGE_KEY, LINK_STORAGE_KEY, TITLE_STORAGE_KEY, SRC_STORAGE_KEY,
                TIME_STORAGE_KEY, TAGS_STORAGE_KEY,
                AUTO_SYNC_KEY // 新增
            ];
            keysToRemove.forEach(key => localStorage.removeItem(key));

            // Clear in-memory store as well
            GM_STORE.processedKeys.clear();
            GM_STORE.links = {};
            GM_STORE.titles = {};
            GM_STORE.srcs = {};
            GM_STORE.times = {};
            GM_STORE.tags = {};
            GM_STORE.autoSyncEnabled = false; // 新增

            window.alert('全部数据已清空。页面将刷新。');
            location.reload();
        }
    }

    // --- 与Gemini书架同步的功能 ---
    function syncDataToBookshelf() {
        console.log("[WNACG MOD] 开始同步数据到Gemini书架...");

        const dataToSync = {
            processedImages: Array.from(GM_STORE.processedKeys),
            comicLinks: GM_STORE.links,
            comicTitles: GM_STORE.titles,
            comicSrcs: GM_STORE.srcs,
            comicTags: GM_STORE.tags,
            comicTimes: GM_STORE.times,
        };

        const jsonPayload = JSON.stringify(dataToSync);

        GM_xmlhttpRequest({
            method: "POST",
            url: "http://127.0.0.1:5000/api/tampermonkey/sync",
            headers: { "Content-Type": "application/json" },
            data: jsonPayload,
            onload: function(response) {
                console.log("[WNACG MOD] 同步响应:", response.responseText);
                try {
                    const respData = JSON.parse(response.responseText);
                    if (respData.status === 'success') {
                        // 自动同步成功时，不在前台提示，只在控制台输出
                        console.log("[WNACG MOD] 自动同步成功！");
                    } else {
                        window.alert("同步失败: " + (respData.message || "未知错误"));
                    }
                } catch (e) {
                    console.error("[WNACG MOD] 解析同步响应失败:", e);
                    window.alert("同步请求成功，但无法解析服务器响应。请检查控制台。");
                }
            },
            onerror: function(response) {
                console.error("[WNACG MOD] 同步数据时发生网络错误:", response);
                window.alert("无法连接到Gemini书架服务器。请确保您的本地服务器程序(main.py)正在运行。");
            }
        });
    }



    // 新增：切换自动同步状态的函数
    function toggleAutoSync() {
        GM_STORE.autoSyncEnabled = !GM_STORE.autoSyncEnabled;
        localStorage.setItem(AUTO_SYNC_KEY, JSON.stringify(GM_STORE.autoSyncEnabled));
        const status = GM_STORE.autoSyncEnabled ? '开启' : '关闭';
        alert(`自动同步已 ${status}。`);
    }

    // --- 注册油猴菜单 ---
    function registerMenuCommands() {
        const autoSyncStatus = GM_STORE.autoSyncEnabled ? '✅ (已开启)' : '❌ (已关闭)';
        GM_registerMenuCommand(`切换自动同步 ${autoSyncStatus}`, toggleAutoSync);
        GM_registerMenuCommand('手动同步到Gemini书架', syncDataToBookshelf);
        GM_registerMenuCommand('导出全部数据', exportData);
        GM_registerMenuCommand('导入数据 (合并)', importData);
        GM_registerMenuCommand('清空全部数据', clearAllData);
    }

    // --- 添加收藏夹按钮 ---
    function addFavoritesButton() {
        // 在页面合适位置添加"我的收藏"按钮
        const targetElement = document.querySelector('#bodywrap > div:nth-child(2)') || 
                             document.querySelector('#navbar') || 
                             document.querySelector('header') || 
                             document.body;
        
        if (targetElement) {
            const button = document.createElement('button');
            button.id = 'my-favorites-btn';
            button.textContent = '我的收藏';
            button.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                padding: 10px 15px;
                background-color: #bb86fc;
                color: #121212;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                z-index: 9999;
                font-weight: bold;
                box-shadow: 0 2px 10px rgba(0, 0, 0, 0.3);
            `;
            
            button.addEventListener('click', showFavoritesPage);
            
            targetElement.appendChild(button);
        }
    }

    // --- 封面标记功能 ---
    const ANIMATION_KEYFRAMES = `
        @keyframes gm-heartbeat {
            0%, 100% { transform: scale(1); }
            25% { transform: scale(1.2); }
            50% { transform: scale(1); }
            75% { transform: scale(1.1); }
        }
        @keyframes gm-shake {
            0%, 100% { transform: translateX(0); }
            20%, 60% { transform: translateX(0px); }
            40%, 80% { transform: translateX(0px); }
        }
        @keyframes gm-spinner {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    `;

    const coverButtonStyles = `
            ${ANIMATION_KEYFRAMES}
            /* Container for the image, which will hold the button and mask */
            .gm-cover-image-container {
                position: relative;
                display: inline-block; /* Make container shrink to fit the image */
                font-size: 0; /* Fix extra space issues with inline-block */
                overflow: hidden; /* 确保蒙版不超出容器 */
                line-height: 0; /* Fix extra space issues with inline-block */
            }
            .gm-cover-mask {
                position: absolute;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%; /* 确保蒙版覆盖整个图片 */
                background-color: rgba(0, 0, 0, 0.6);
                z-index: 998; /* Below the button */
                pointer-events: none;
                opacity: 0;
                transition: opacity 0.2s ease;
            }
            .gm-cover-button.checked ~ .gm-cover-mask {
                opacity: 1;
            }
            .gm-cover-button {
                position: absolute; top: 8px; right: 8px;
                width: 36px;
                height: 36px;
                background-color: rgba(0, 0, 0, 0.3);
                border: 2px solid white;
                border-radius: 50%;
                box-shadow: 0 1px 3px rgba(0,0,0,0.5);
                color: white;
                cursor: pointer;
                z-index: 999;
                box-sizing: border-box;
                display: flex;
                align-items: center;
                justify-content: center;
                transition: background-color 0.2s ease, border-color 0.2s ease, transform 0.2s ease;
            }
            .gm-cover-button:hover { background-color: rgba(0, 0, 0, 0.6); }
            /* Add active state for touch feedback */
            .gm-cover-button:active {
                 background-color: rgba(0, 0, 0, 0.8);
                 transform: scale(0.95);
            }
            .gm-cover-button::after {
                content: '✓';
                font-size: 20px;
                font-weight: bold;
                line-height: 1;
                opacity: 0;
                transform: scale(0.5);
                transition: opacity 0.2s ease, transform 0.2s ease;
            }
            .gm-cover-button.checked {
                background-color: rgba(30, 150, 30, 0.8);
                border-color: #c3e6cb;
            }
            .gm-cover-button.checked::after { opacity: 1; transform: scale(1); }
            .gm-cover-button.pop { animation: gm-heartbeat 0.3s ease-out; }
            .gm-cover-card-processed.shake { animation: gm-shake 0.3s ease-in-out; }
            .gm-cover-button.loading::after {
                content: '';
                border: 3px solid rgba(255, 255, 255, 0.3);
                border-top: 3px solid #fff;
                border-radius: 50%;
                width: 18px;
                height: 18px;
                animation: gm-spinner 0.8s linear infinite;
                opacity: 1;
                transform: scale(1);
            }
            .gm-cover-button.loading { 
                pointer-events: none; 
                background-color: rgba(0, 0, 0, 0.5); 
                border-color: rgba(255, 255, 255, 0.5); 
            }
            .gm-cover-button.loading::after { content: ''; }
    
            /* --- Mobile Styles --- */
            @media (max-width: 768px) {
                .gm-cover-button {
                    width: 32px;
                    height: 32px;
                    top: 4px;
                    right: 4px;
                    border-width: 1px;
                }
                .gm-cover-button::after {
                    font-size: 16px;
                }
            }
    
            /* For very small screens */
            @media (max-width: 480px) {
                .gm-cover-button {
                    width: 28px;
                    height: 28px;
                    top: 2px;
                    right: 2px;
                }
                .gm-cover-button::after {
                    font-size: 14px;
                }
            }
            
            /* 收藏按钮样式 */
            #my-favorites-btn:hover {
                background-color: #d0bcff;
                transform: translateY(-2px);
            }
        `;
    function observeAndProcessGalleries() {
        const processedSet = GM_STORE.processedKeys;
        const isDetailPage = window.location.pathname.startsWith('/photos-');
        const cardSelector = isDetailPage
            ? '.asTBcell.uwthumb'
            : '.gallary_item, .pic_box, .li, .ub, .item_box';

        const processCard = (card) => {
            if (card.querySelector('.gm-cover-button') || card.parentElement.closest('.gm-cover-card-processed')) {
                return;
            }

            const imgElement = card.querySelector('img');
            if (!imgElement) return;

            card.classList.add('gm-cover-card-processed');

            let container, comicTitle, comicLink, comicTags = [];

            if (isDetailPage) {
                const tagElements = document.querySelectorAll('.addtags a.tagshow');
                tagElements.forEach(tagEl => {
                    comicTags.push(tagEl.textContent.trim());
                });

                const wrapper = document.createElement('div');
                imgElement.parentNode.insertBefore(wrapper, imgElement);
                wrapper.appendChild(imgElement);
                container = wrapper;

                const pageTitleElement = document.querySelector('#main > h2');
                comicTitle = stripHtml(pageTitleElement?.innerHTML) || imgElement.alt;
                comicLink = window.location.href;

                const applySize = () => {
                    const imgWidth = imgElement.offsetWidth;
                    const imgHeight = imgElement.offsetHeight;
                    if (imgWidth > 0 && imgHeight > 0) {
                        container.style.width = `${imgWidth}px`;
                        container.style.height = `${imgHeight}px`;
                        container.style.position = 'relative';
                        container.style.display = 'inline-block';
                    }
                    imgElement.style.position = 'relative';
                    imgElement.style.zIndex = '997';
                };

                if (imgElement.complete) {
                    applySize();
                } else {
                    imgElement.addEventListener('load', applySize, { once: true });
                }

            } else {
                container = card.querySelector('a');
                if (!container || !container.contains(imgElement)) {
                    return;
                }
                const titleElement = card.querySelector('p, .title');
                comicTitle = stripHtml(titleElement?.innerHTML) || container.title || '无标题';
                comicLink = container.href;
            }

            if (!comicTitle || !container) {
                console.log('[WNACG MOD] Could not process card, missing title or container.', card);
                return;
            }

            container.classList.add('gm-cover-image-container');

            const comicKey = comicTitle;

            const coverButton = document.createElement('div');
            coverButton.className = 'gm-cover-button';
            const mask = document.createElement('div');
            mask.className = 'gm-cover-mask';

            const updateButtonState = () => {
                if (processedSet.has(comicKey)) {
                    coverButton.classList.add('checked');
                    coverButton.title = '已标记，点击取消';
                } else {
                    coverButton.classList.remove('checked');
                    coverButton.title = '点击标记';
                }
            };

            const triggerAutoSync = () => {
                if (GM_STORE.autoSyncEnabled) {
                    console.log('[WNACG MOD] 自动同步已开启，调用同步函数。');
                    syncDataToBookshelf();
                }
            };

            coverButton.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();

                if (processedSet.has(comicKey)) {
                    processedSet.delete(comicKey);
                    delete GM_STORE.links[comicKey];
                    delete GM_STORE.titles[comicKey];
                    delete GM_STORE.srcs[comicKey];
                    delete GM_STORE.times[comicKey];
                    delete GM_STORE.tags[comicKey];
                    card.classList.add('shake');
                    setTimeout(() => card.classList.remove('shake'), 300);
                    saveStoreToLocalStorage();
                    updateButtonState();
                    triggerAutoSync(); // 修改点
                } else {
                    if (isDetailPage) {
                        processedSet.add(comicKey);
                        GM_STORE.links[comicKey] = comicLink;
                        GM_STORE.titles[comicKey] = comicTitle;
                        GM_STORE.srcs[comicKey] = imgElement.src;
                        GM_STORE.times[comicKey] = getFormattedDate();
                        GM_STORE.tags[comicKey] = comicTags;

                        saveStoreToLocalStorage();
                        updateButtonState();
                        coverButton.classList.add('pop');
                        setTimeout(() => coverButton.classList.remove('pop'), 300);
                        triggerAutoSync(); // 修改点
                    } else {
                        coverButton.classList.add('loading');

                        GM_xmlhttpRequest({
                            method: "GET",
                            url: comicLink,
                            onload: function(response) {
                                coverButton.classList.remove('loading');
                                const parser = new DOMParser();
                                const doc = parser.parseFromString(response.responseText, "text/html");
                                const fetchedTags = [];
                                doc.querySelectorAll('.addtags a.tagshow').forEach(tagEl => {
                                    fetchedTags.push(tagEl.textContent.trim());
                                });

                                processedSet.add(comicKey);
                                GM_STORE.links[comicKey] = comicLink;
                                GM_STORE.titles[comicKey] = comicTitle;
                                GM_STORE.srcs[comicKey] = imgElement.src;
                                GM_STORE.times[comicKey] = getFormattedDate();
                                GM_STORE.tags[comicKey] = fetchedTags;

                                saveStoreToLocalStorage();
                                updateButtonState();
                                coverButton.classList.add('pop');
                                setTimeout(() => coverButton.classList.remove('pop'), 300);
                                triggerAutoSync(); // 修改点
                            },
                            onerror: function(response) {
                                coverButton.classList.remove('loading');
                                console.error('[WNACG MOD] Failed to fetch tags:', response);
                                alert('获取漫画Tag失败，请检查网络或查看控制台。');
                            }
                        });
                    }
                }
            });

            container.appendChild(coverButton);
            container.appendChild(mask);
            updateButtonState();
        };

        const observer = new MutationObserver((mutations) => {
            for (const mutation of mutations) {
                if (mutation.addedNodes.length) {
                    mutation.addedNodes.forEach(node => {
                        if (node.nodeType === 1) {
                            node.querySelectorAll(cardSelector).forEach(processCard);
                            if (node.matches && node.matches(cardSelector)) {
                                processCard(node);
                            }
                        }
                    });
                }
            }
        });

        observer.observe(document.body, { childList: true, subtree: true });

        document.querySelectorAll(cardSelector).forEach(processCard);
    }

    // --- 初始化 ---
    function initScript() {
        if (!window.location.hash.startsWith('#bookmarks')) {
            loadDataFromLocalStorage();
            registerMenuCommands(); // 修改点：注册所有菜单
            GM_addStyle(coverButtonStyles);
            addFavoritesButton();
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', observeAndProcessGalleries);
            } else {
                observeAndProcessGalleries();
            }
        }
    }
    
    // 启动脚本
    initScript();

})();