document.addEventListener('DOMContentLoaded', () => {
    // --- 全局DOM元素 ---
    const comicShelf = document.getElementById('comic-shelf');
    const cardTemplate = document.getElementById('comic-card-template');
    const filterAllButton = document.getElementById('filter-all');
    const filterFavoritesButton = document.getElementById('filter-favorites');
    const filterDropdownButton = document.getElementById('filter-dropdown-button');
    const filterOptions = document.getElementById('filter-options');
    const refreshButton = document.getElementById('refresh-button');
    const searchInput = document.getElementById('search-input');
    const sortButton = document.getElementById('sort-button');
    const sortOptions = document.getElementById('sort-options');
    const readerView = document.getElementById('reader-view');
    const readerControls = document.getElementById('reader-controls');
    const readerImageContainer = document.getElementById('reader-image-container');
    const readerCloseButton = document.getElementById('reader-close-button');
    const pageSlider = document.getElementById('page-slider');
    const pageInfoStart = document.getElementById('page-info-start');
    const pageInfoEnd = document.getElementById('page-info-end');
    const pageInfoCurrent = document.getElementById('page-info-current');
    const viewModeSingle = document.getElementById('view-mode-single');
    const viewModeDouble = document.getElementById('view-mode-double');
    const viewModeLong = document.getElementById('view-mode-long');
    const directionToggleButton = document.getElementById('direction-toggle-button');
    const zoomSmallButton = document.getElementById('zoom-small');
    const zoomMediumButton = document.getElementById('zoom-medium');
    const zoomLargeButton = document.getElementById('zoom-large');
    const coverModeToggle = document.getElementById('cover-mode-toggle');


    // --- 文件夹/分类功能 DOM 元素 ---
    const addFolderButton = document.getElementById('add-folder-button');
    const customFoldersContainer = document.getElementById('custom-folders-container');
    const folderModal = document.getElementById('folder-modal');
    const closeModalButton = document.getElementById('close-modal-button');
    const folderList = document.getElementById('folder-list');
    const comicContextMenu = document.getElementById('comic-context-menu');
    
    // --- Folder Modal V2 DOM Elements ---
    const folderListView = document.getElementById('folder-list-view');
    const folderEditView = document.getElementById('folder-edit-view');
    const addFolderConfirmButton = document.getElementById('add-folder-confirm-button');
    const newFolderNameInput = document.getElementById('new-folder-name');
    const editFolderTitle = document.getElementById('edit-folder-title');
    const folderNameEditInput = document.getElementById('folder-name-edit');
    const folderAutoToggle = document.getElementById('folder-auto-toggle');
    const autoClassificationRules = document.getElementById('auto-classification-rules');
    const folderNameIncludesInput = document.getElementById('folder-name-includes');
    const folderTagIncludesInput = document.getElementById('folder-tag-includes');
    const saveFolderChangesButton = document.getElementById('save-folder-changes-button');
    const backToFolderListButton = document.getElementById('back-to-folder-list-button');

    // --- 设置模块 DOM 元素 ---
    const settingsButton = document.getElementById('settings-button');
    const settingsModal = document.getElementById('settings-modal');
    const closeSettingsModalButton = document.getElementById('close-settings-modal-button');
    const managedFoldersList = document.getElementById('managed-folders-list');
    const newManagedFolderPathInput = document.getElementById('new-managed-folder-path');
    const addManagedFolderButton = document.getElementById('add-managed-folder-button');

    // --- 确认弹窗 DOM 元素 ---
    const confirmModal = document.getElementById('confirm-modal');
    const confirmModalTitle = document.getElementById('confirm-modal-title');
    const confirmModalMessage = document.getElementById('confirm-modal-message');
    const confirmModalCancel = document.getElementById('confirm-modal-cancel');
    const confirmModalConfirm = document.getElementById('confirm-modal-confirm');

    // --- 批量操作 DOM 元素 ---
    const batchSelectButton = document.getElementById('batch-select-button');
    const batchActionsBar = document.getElementById('batch-actions-bar');
    const batchSelectAllButton = document.getElementById('batch-select-all');
    const batchSelectionCount = document.getElementById('batch-selection-count');
    const batchAddFavoriteButton = document.getElementById('batch-add-favorite');
    const batchRemoveFavoriteButton = document.getElementById('batch-remove-favorite');
    const batchRemoveFromFolderButton = document.getElementById('batch-remove-from-folder');
    const batchDeleteButton = document.getElementById('batch-delete');
    const batchMergeButton = document.getElementById('batch-merge');
    const batchCancelButton = document.getElementById('batch-cancel');
    const loadingIndicator = document.getElementById('loading-indicator');

    // --- 详情页 DOM 元素 ---
    const detailsView = document.getElementById('details-view');
    const detailsCloseButton = document.getElementById('details-close-button');
    const detailsCover = document.getElementById('details-cover');
    const detailsTitle = document.getElementById('details-title');
    const detailsFolder = document.getElementById('details-folder');
    const detailsTags = document.getElementById('details-tags');
    const detailsPages = document.getElementById('details-pages');
    const detailsAddedDate = document.getElementById('details-added-date');
    const detailsLocalPath = document.getElementById('details-local-path');
    const detailsOnlineUrl = document.getElementById('details-online-url');
    const detailsFolderContainer = document.getElementById('details-folder-container');
    const detailsTagsContainer = document.getElementById('details-tags-container');
    const detailsPagesContainer = document.getElementById('details-pages-container');
    const detailsAddedDateContainer = document.getElementById('details-added-date-container');
    const detailsLocalSource = document.getElementById('details-local-source');
    const detailsOnlineSource = document.getElementById('details-online-source');
    const editDisplayNameButton = document.getElementById('edit-display-name-button');
    const displayNameEditContainer = document.getElementById('display-name-edit-container');
    const displayNameEditInput = document.getElementById('display-name-edit-input');
    const saveDisplayNameButton = document.getElementById('save-display-name-button');
    const cancelDisplayNameButton = document.getElementById('cancel-display-name-button');
    const detailsOriginalTitle = document.getElementById('details-original-title');
    const detailsOriginalTitleContainer = document.getElementById('details-original-title-container');


    // --- 扫描进度条 DOM 元素 ---
    const scanProgressContainer = document.getElementById('scan-progress-container');
    const scanProgressBarInner = document.getElementById('scan-progress-bar-inner');
    const scanProgressText = document.getElementById('scan-progress-text');

    // --- 全局状态 ---
    let allComics = [];
    let customFolders = [];
    let readerState = { isOpen: false, comic: null, pages: [], currentPage: 0, viewMode: 'double', direction: 'ltr' };
    let shelfState = { filter: 'all', sort: { by: 'date', order: 'desc' }, searchTerm: '', zoomLevel: 'medium' };
    let contextMenuState = { isOpen: false, comic: null };
    let progressUpdateTimer = null;
    let selectionMode = false;
    let selectedComics = new Set();
    let confirmCallback = null;

    // Pagination state
    let currentPage = 1;
    const comicsPerPage = 30; // Adjust as needed
    let hasMoreComics = true;
    let isLoadingMore = false;

    // --- SVG 图标 ---
    const icons = {
        all: `<svg viewBox="0 0 24 24"><path d="M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8V11h-8v10zm0-18v6h8V3h-8z"/></svg>`,
        favorite: `<svg viewBox="0 0 24 24"><path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/></svg>`,
        web: `<svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L8 12v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1h-2v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z"/></svg>`,
        online: `<svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.5 14H8c-1.66 0-3-1.34-3-3s1.34-3 3-3h1.5v-2H8c-.55 0-1-.45-1-1s.45-1 1-1h4.5c1.66 0 3 1.34 3 3s-1.34 3-3 3h-1.5v2H16c.55 0 1 .45 1 1s-.45 1-1 1z"/></svg>`,
        refresh: `<svg viewBox="0 0 24 24"><path d="M17.65 6.35C16.2 4.9 14.21 4 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08c-.82 2.33-3.04 4-5.65 4-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/></svg>`,
        heart: `<svg viewBox="0 0 24 24"><path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/></svg>`,
        direction: `<svg viewBox="0 0 24 24"><path d="M20 9V5h-4l4-4 4 4h-4v4h-4zm-6 8v4h4l-4 4-4-4h4v-4h4zM4 9V5H0l4-4 4 4H4v4H0z" transform="rotate(90 12 12)"/></svg>`,
        sort: `<svg viewBox="0 0 24 24"><path d="M3 18h6v-2H3v2zM3 6v2h18V6H3zm0 7h12v-2H3v2z"/></svg>`,
        plus: `<svg viewBox="0 0 24 24"><path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/></svg>`,
        trash: `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/></svg>`,
        pencil: `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04c.39-.39.39-1.02 0-1.41l-2.34-2.34c-.39-.39-1.02-.39-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/></svg>`,
        checklist: `<svg viewBox="0 0 24 24"><path d="M14 10H2v2h12v-2zm0-4H2v2h12V6zm4 8v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zM2 16h8v-2H2v2z"/></svg>`,
        settings: `<svg viewBox="0 0 24 24"><path d="M19.43 12.98c.04-.32.07-.64.07-.98s-.03-.66-.07-.98l2.11-1.65c.19-.15.24-.42.12-.64l-2-3.46c-.12-.22-.39-.3-.61-.22l-2.49 1c-.52-.4-1.08-.73-1.69-.98l-.38-2.65C14.46 2.18 14.25 2 14 2h-4c-.25 0-.46.18-.49.42l-.38 2.65c-.61.25-1.17.59-1.69.98l-2.49-1c-.23-.09-.49 0-.61.22l-2 3.46c-.13.22-.07.49.12.64l2.11 1.65c-.04.32-.07.65-.07.98s.03.66.07.98l-2.11 1.65c-.19.15-.24.42-.12-.64l2 3.46c.12.22.39.3.61.22l2.49-1c.52.4 1.08.73 1.69.98l.38 2.65c.03.24.24.42.49.42h4c.25 0 .46-.18.49.42l.38-2.65c.61-.25 1.17-.59 1.69.98l2.49 1c.23.09.49 0 .61.22l2-3.46c.12-.22-.07-.49-.12-.64l-2.11-1.65zM12 15.5c-1.93 0-3.5-1.57-3.5-3.5s1.57-3.5 3.5-3.5 3.5 1.57 3.5 3.5-1.57 3.5-3.5 3.5z"/></svg>`
    };

    function initIcons() {
        refreshButton.innerHTML = icons.refresh;
        directionToggleButton.innerHTML = icons.direction;
        sortButton.innerHTML = icons.sort;
        addFolderButton.innerHTML = icons.plus;
        batchSelectButton.innerHTML = icons.checklist;
        settingsButton.innerHTML = icons.settings;
    }

    // --- 数据加载与渲染 ---
    async function fetchAndRenderComics(page = 1, limit = comicsPerPage, append = false) {
        if (isLoadingMore && append) return; // 防止无限滚动时重复加载

        if (!append) {
            window.scrollTo(0, 0);
            if (selectionMode) {
                toggleSelectionMode();
            }
        }

        try {
            isLoadingMore = true;
            loadingIndicator.style.display = 'block';
            refreshButton.classList.add('loading');

            const params = new URLSearchParams({
                page: page,
                limit: limit,
                sort_by: shelfState.sort.by,
                sort_order: shelfState.sort.order,
                filter: shelfState.filter,
                search: shelfState.searchTerm
            });

            const response = await fetch(`/api/comics?${params.toString()}`);
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.message || '无法加载漫画库');
            }
            const data = await response.json();

            const searchResultsCount = document.getElementById('search-results-count');
            if (data.total_comics !== null && data.total_comics !== undefined) {
                searchResultsCount.textContent = `${data.total_comics} 结果`;
                searchResultsCount.style.display = 'block';
            } else {
                searchResultsCount.style.display = 'none';
            }
            
            if (!append) {
                comicShelf.innerHTML = '';
                allComics = data.comics;
            } else {
                allComics = allComics.concat(data.comics);
            }
            
            renderShelf(data.comics);

            currentPage = data.page;
            hasMoreComics = allComics.length < data.total_comics;

        } catch (error) {
            console.error('错误:', error);
            comicShelf.innerHTML = `<p class="shelf-message">${error.message}</p>`;
        } finally {
            setTimeout(() => refreshButton.classList.remove('loading'), 500);
            loadingIndicator.style.display = 'none';
            isLoadingMore = false;
        }
    }

    function getCoverUrlForCurrentZoom(comic) {
        const zoomLevel = shelfState.zoomLevel || 'medium';
        if (comic.cover_paths_local) {
            switch (zoomLevel) {
                case 'large':
                    return comic.cover_paths_local.large || comic.cover_paths_local.medium || comic.cover_paths_local.thumbnail;
                case 'small':
                    return comic.cover_paths_local.thumbnail;
                case 'medium':
                default:
                    return comic.cover_paths_local.medium || comic.cover_paths_local.thumbnail;
            }
        }
        return comic.cover_url_online;
    }

    function renderShelf(comics) {
        if (comics.length === 0 && comicShelf.children.length === 0) {
            comicShelf.innerHTML = `<p class="shelf-message">没有找到匹配的漫画。</p>`;
            return;
        }

        const existingTitles = new Set(Array.from(comicShelf.children).map(card => card.dataset.title));

        comics.forEach(comic => {
            if (existingTitles.has(comic.title)) {
                return;
            }

            const card = cardTemplate.content.cloneNode(true).querySelector('.comic-card');
            card.dataset.title = comic.title;

            const localSource = comic.sources.find(s => s.type === 'local');
            const onlineSource = comic.sources.find(s => s.type === 'online');

            const coverUrl = getCoverUrlForCurrentZoom(comic);
            if (coverUrl) {
                card.querySelector('.comic-cover').src = coverUrl;
            }
            card.querySelector('.comic-cover').alt = comic.title;
            
            const comicTitleElement = card.querySelector('.comic-title');
            comicTitleElement.textContent = comic.displayName;
            
            const comicInfoElement = card.querySelector('.comic-info');
            comicInfoElement.addEventListener('click', (e) => {
                e.stopPropagation(); // 阻止事件冒泡到卡片本身
                openDetailsView(comic.title);
            });
            
            const favoriteButton = card.querySelector('.favorite-button');
            favoriteButton.innerHTML = icons.heart;
            if (comic.is_favorite) card.classList.add('favorite');
            favoriteButton.addEventListener('click', e => {
                e.stopPropagation();
                toggleFavorite(comic, card);
            });

            if (onlineSource) {
                card.classList.add('has-online-source');
                const onlineIcon = card.querySelector('.online-icon');
                onlineIcon.innerHTML = icons.online;
                onlineIcon.addEventListener('click', e => {
                    e.stopPropagation();
                    window.open(onlineSource.url, '_blank');
                });
            }

            const comicCoverContainer = card.querySelector('.comic-cover-container');
            comicCoverContainer.addEventListener('click', () => {
                if (selectionMode) {
                    toggleComicSelection(card, comic.title);
                } else {
                    if (localSource) {
                        openReader(comic);
                    } else if (onlineSource) {
                        window.open(onlineSource.url, '_blank');
                    }
                }
            });

            card.addEventListener('click', () => {
                if (selectionMode) {
                    toggleComicSelection(card, comic.title);
                }
            });

            card.addEventListener('contextmenu', e => {
                if (selectionMode) {
                    e.preventDefault();
                } else {
                    showContextMenu(e, comic);
                }
            });

            if (localSource) {
                updateProgressBar(card, comic.currentPage, comic.totalPages);
            } else {
                card.querySelector('.progress-bar-container').style.display = 'none';
            }

            comicShelf.appendChild(card);
        });
    }

    let currentDetailComic = null; // 用于存储当前详情页的完整漫画数据

    // --- 详情页功能 ---
    async function openDetailsView(comicTitle) {
        try {
            const response = await fetch(`/api/comic/${encodeURIComponent(comicTitle)}`);
            if (!response.ok) {
                throw new Error('无法加载漫画详情');
            }
            currentDetailComic = await response.json();
            renderDetails(currentDetailComic);
            detailsView.style.display = 'flex';
        } catch (error) {
            console.error(error);
            showConfirmationModal('加载失败', error.message, null, true);
        }
    }

        function renderDetails(comic) {

            detailsCover.src = comic.local_info?.cover_paths?.large || comic.online_info?.cover_url || '';

            detailsTitle.textContent = comic.displayName || comic.title;

            detailsOriginalTitle.textContent = comic.title;
            detailsOriginalTitleContainer.style.display = 'block';

    

            // Reset edit state

            displayNameEditContainer.style.display = 'none';

            detailsTitle.style.display = 'block';

            editDisplayNameButton.style.display = 'inline-flex';

    

            if (comic.folder) {

                detailsFolder.textContent = comic.folder;

                detailsFolderContainer.style.display = 'block';

            } else {

                detailsFolderContainer.style.display = 'none';

            }

    

            renderTagsForDetails();

    

            if (comic.totalPages > 0) {

                detailsPages.textContent = `${comic.currentPage} / ${comic.totalPages}`;

                detailsPagesContainer.style.display = 'block';

            } else {

                detailsPagesContainer.style.display = 'none';

            }

    

            if (comic.date_added) {

                detailsAddedDate.textContent = new Date(comic.date_added * 1000).toLocaleDateString();

                detailsAddedDateContainer.style.display = 'block';

            } else {

                detailsAddedDateContainer.style.display = 'none';

            }

    

            if (comic.local_info?.path) {

                detailsLocalPath.textContent = comic.local_info.path;

                detailsLocalSource.style.display = 'block';

            } else {

                detailsLocalSource.style.display = 'none';

            }

    

            if (comic.online_info?.url) {

                detailsOnlineUrl.href = comic.online_info.url;

                detailsOnlineUrl.textContent = comic.online_info.url;

                detailsOnlineSource.style.display = 'block';

            } else {

                detailsOnlineSource.style.display = 'none';

            }

        }

    

        function toggleDisplayNameEditMode() {

            if (!currentDetailComic) return;

    

            if (displayNameEditContainer.style.display === 'none') {

                // Enter edit mode

                displayNameEditInput.value = currentDetailComic.displayName || currentDetailComic.title;

                displayNameEditContainer.style.display = 'flex';

                detailsTitle.style.display = 'none';

                editDisplayNameButton.style.display = 'none';

                displayNameEditInput.focus();

            } else {

                // Exit edit mode

                displayNameEditContainer.style.display = 'none';

                detailsTitle.style.display = 'block';

                editDisplayNameButton.style.display = 'inline-flex';

            }

        }

    

        async function saveDisplayName() {

            if (!currentDetailComic) return;

    

            const newDisplayName = displayNameEditInput.value.trim();

            if (!newDisplayName || newDisplayName === (currentDetailComic.displayName || currentDetailComic.title)) {

                toggleDisplayNameEditMode(); // Exit edit mode if no change or empty

                return;

            }

    

            try {

                const response = await fetch(`/api/comic/${encodeURIComponent(currentDetailComic.title)}/display_name`, {

                    method: 'PUT',

                    headers: { 'Content-Type': 'application/json' },

                    body: JSON.stringify({ displayName: newDisplayName })

                });

    

                if (!response.ok) {

                    const err = await response.json();

                    throw new Error(err.message || '更新显示名称失败');

                }

    

                currentDetailComic.displayName = newDisplayName;

                detailsTitle.textContent = newDisplayName; // Update UI immediately

                

                // Also update the comic in allComics array

                const comicInAllComics = allComics.find(c => c.title === currentDetailComic.title);

                if (comicInAllComics) {

                    comicInAllComics.displayName = newDisplayName;

                }

    

                toggleDisplayNameEditMode(); // Exit edit mode

                showConfirmationModal('成功', '显示名称已更新。', null, true);

            } catch (error) {

                console.error('更新显示名称失败:', error);

                showConfirmationModal('错误', error.message, null, true);

            }

        }

    

        function cancelDisplayNameEdit() {

            toggleDisplayNameEditMode(); // Exit edit mode without saving

        }

    

        function renderTagsForDetails() {
        if (!currentDetailComic) return;

        const { source_tags = [], added_tags = [], removed_tags = [] } = currentDetailComic;
        const finalTags = [...new Set([...source_tags, ...added_tags].filter(t => !removed_tags.includes(t)))].sort();
        
        detailsTags.innerHTML = '';
        const isEditMode = detailsTagsContainer.classList.contains('edit-mode');

        if (finalTags.length > 0) {
            finalTags.forEach(tag => {
                const tagEl = document.createElement('span');
                tagEl.className = 'details-tag clickable-tag'; // Add clickable-tag class
                tagEl.textContent = tag;
                tagEl.addEventListener('click', () => {
                    searchByTag(tag);
                });
                if (isEditMode) {
                    const removeBtn = document.createElement('button');
                    removeBtn.className = 'remove-tag-btn';
                    removeBtn.innerHTML = '&times;';
                    removeBtn.dataset.tag = tag;
                    tagEl.appendChild(removeBtn);
                }
                detailsTags.appendChild(tagEl);
            });
            detailsTagsContainer.style.display = 'block';
        } else {
            // Keep the container visible even if no tags, to allow adding new tags
            detailsTagsContainer.style.display = 'block';
        }

        if (isEditMode) {
            const addTagForm = document.createElement('div');
            addTagForm.className = 'add-tag-form';
            addTagForm.innerHTML = `
                <input type="text" class="add-tag-input" placeholder="添加新标签...">
                <button class="add-tag-button nav-button">添加</button>
            `;
            detailsTags.appendChild(addTagForm);
            detailsTagsContainer.style.display = 'block';
        }
    }

    function toggleTagEditMode() {
        detailsTagsContainer.classList.toggle('edit-mode');
        renderTagsForDetails();
    }

    async function handleTagUpdate(action, tag) {
        if (!currentDetailComic || !tag) return;

        try {
            const response = await fetch(`/api/comic/${encodeURIComponent(currentDetailComic.title)}/tags`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action, tag })
            });

            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.message || '标签更新失败');
            }

            // Optimistically update UI
            const { source_tags = [], added_tags = [], removed_tags = [] } = currentDetailComic;
            if (action === 'add') {
                currentDetailComic.removed_tags = removed_tags.filter(t => t !== tag);
                if (!source_tags.includes(tag)) {
                    currentDetailComic.added_tags = [...new Set([...added_tags, tag])];
                }
            } else if (action === 'remove') {
                currentDetailComic.added_tags = added_tags.filter(t => t !== tag);
                if (source_tags.includes(tag)) {
                     currentDetailComic.removed_tags = [...new Set([...removed_tags, tag])];
                }
            }
            renderTagsForDetails();

        } catch (error) {
            console.error('Tag update error:', error);
            showConfirmationModal('错误', error.message, null, true);
            // Re-fetch to get the ground truth if optimistic update fails
            openDetailsView(currentDetailComic.title);
        }
    }

    function closeDetailsView() {
        detailsView.style.display = 'none';
        currentDetailComic = null;
        detailsTagsContainer.classList.remove('edit-mode');
    }

    function searchByTag(tag) {
        shelfState.searchTerm = tag;
        searchInput.value = tag;
        closeDetailsView();
        currentPage = 1;
        hasMoreComics = true;
        fetchAndRenderComics(currentPage, comicsPerPage, false);
    }

    // --- 批量操作功能 ---
    function toggleSelectionMode() {
        selectionMode = !selectionMode;
        document.body.classList.toggle('selection-mode', selectionMode);
        batchSelectButton.classList.toggle('active', selectionMode);

        if (!selectionMode) {
            selectedComics.clear();
            document.querySelectorAll('.comic-card.selected').forEach(card => card.classList.remove('selected'));
            updateSelectionCount();
        }
        const isFolderView = !['all', 'favorites', 'web', 'downloaded', 'undownloaded'].includes(shelfState.filter);
        batchRemoveFromFolderButton.style.display = isFolderView ? 'flex' : 'none';
    }

    function toggleComicSelection(card, comicTitle) {
        if (selectedComics.has(comicTitle)) {
            selectedComics.delete(comicTitle);
            card.classList.remove('selected');
        } else {
            selectedComics.add(comicTitle);
            card.classList.add('selected');
        }
        updateSelectionCount();
    }

    function updateSelectionCount() {
        const count = selectedComics.size;
        batchSelectionCount.textContent = `已选择 ${count} 项`;

        if (count === 2) {
            batchMergeButton.style.display = 'inline-flex';
        } else {
            batchMergeButton.style.display = 'none';
        }

        const allVisibleCards = comicShelf.querySelectorAll('.comic-card:not(.hidden)').length;
        if (count > 0 && count === allVisibleCards) {
            batchSelectAllButton.textContent = '取消全选';
        } else {
            batchSelectAllButton.textContent = '全选';
        }
    }

    function handleSelectAll() {
        const allVisibleCards = comicShelf.querySelectorAll('.comic-card:not(.hidden)');
        const allTitles = Array.from(allVisibleCards).map(card => card.dataset.title).filter(Boolean);
        if (allTitles.length === 0) return;

        const allSelected = allTitles.length > 0 && allTitles.every(title => selectedComics.has(title));

        allVisibleCards.forEach(card => {
            const title = card.dataset.title;
            if (!title) return;
            if (allSelected) {
                selectedComics.delete(title);
                card.classList.remove('selected');
            } else {
                if (!selectedComics.has(title)) {
                    selectedComics.add(title);
                    card.classList.add('selected');
                }
            }
        });
        updateSelectionCount();
    }

    async function batchUpdateFavorites(isFavorite) {
        const titles = Array.from(selectedComics);
        if (titles.length === 0) return;

        try {
            await fetch('/api/comics/favorite', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ titles, favorite: isFavorite })
            });
            
            if (shelfState.filter === 'favorites') {
                fetchAndRenderComics(1, comicsPerPage, false);
            } else {
                titles.forEach(title => {
                    const card = comicShelf.querySelector(`.comic-card[data-title="${title}"]`);
                    if (card) card.classList.toggle('favorite', isFavorite);
                });
                updateComicCounts();
            }
            toggleSelectionMode();
        } catch (error) {
            console.error('批量更新最爱失败:', error);
        }
    }

    async function batchRemoveFromFolder() {
        const titles = Array.from(selectedComics);
        const folderName = shelfState.filter;
        if (titles.length === 0 || ['all', 'favorites', 'web', 'downloaded', 'undownloaded'].includes(folderName)) return;

        try {
            await fetch('/api/comics/folder', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ titles, folder: null })
            });
            fetchAndRenderComics(1, comicsPerPage, false);
        } catch (error) {
            console.error('批量移出文件夹失败:', error);
        }
    }

    async function batchDelete() {
        const titles = Array.from(selectedComics);
        if (titles.length === 0) return;

        showConfirmationModal(
            `删除漫画`,
            `您确定要永久删除这 ${titles.length} 本漫画吗？这将删除本地漫画文件、在线信息以及所有相关封面。此操作无法撤销。`,
            async () => {
                try {
                    const response = await fetch('/api/comics/delete_full', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ titles })
                    });
                    if (!response.ok) {
                        const errorData = await response.json();
                        throw new Error(errorData.message || '删除失败');
                    }

                    // Optimistically remove deleted comics from UI and allComics array
                    const deletedTitlesSet = new Set(titles);
                    allComics = allComics.filter(comic => !deletedTitlesSet.has(comic.title));
                    titles.forEach(title => {
                        const card = comicShelf.querySelector(`.comic-card[data-title="${title}"]`);
                        if (card) card.remove();
                    });

                    // Update comic counts and potentially load more if needed
                    await updateComicCounts();
                    if (allComics.length < comicsPerPage && hasMoreComics) {
                        // If we deleted enough comics to create a gap, try to fill it
                        await fetchAndRenderComics(currentPage, comicsPerPage, true);
                    }
                    showConfirmationModal('删除成功', `成功删除了 ${titles.length} 本漫画。`, null, true);
                    toggleSelectionMode();
                } catch (error) {
                    console.error('批量删除失败:', error);
                    showConfirmationModal('删除失败', error.message, null, true);
                }
            }
        );
    }

    async function handleMergeComics() {
        if (selectedComics.size !== 2) {
            showConfirmationModal('合并错误', '请选择且仅选择两本漫画进行合并。', null, true);
            return;
        }

        const [title1, title2] = Array.from(selectedComics);
        const comic1 = allComics.find(c => c.title === title1);
        const comic2 = allComics.find(c => c.title === title2);

        if (!comic1 || !comic2) {
            showConfirmationModal('合并错误', '未能找到所选漫画的详细信息。', null, true);
            return;
        }

        let onlineComic = null;
        let localComic = null;

        // Try to auto-determine online/local based on existing info
        if (comic1.online_info && !comic1.local_info && comic2.local_info && !comic2.online_info) {
            onlineComic = comic1;
            localComic = comic2;
        } else if (comic2.online_info && !comic2.local_info && comic1.local_info && !comic1.online_info) {
            onlineComic = comic2;
            localComic = comic1;
        } else {
            // If auto-determination fails or both have mixed info, ask user
            showConfirmationModal(
                '选择合并类型',
                `请选择哪本漫画作为合并后的在线漫画（将保留其在线信息并接收本地信息）：<br><br>` +
                `<button id="select-online-comic1" class="nav-button">${comic1.title}</button>` +
                `<button id="select-online-comic2" class="nav-button">${comic2.title}</button>`,
                () => {
                    // This callback will be handled by specific button clicks within the modal
                },
                false // Not an alert, requires user interaction
            );

            // Attach event listeners to the dynamically created buttons
            document.getElementById('select-online-comic1').onclick = async () => {
                onlineComic = comic1;
                localComic = comic2;
                hideConfirmationModal();
                await performMerge(onlineComic, localComic);
            };
            document.getElementById('select-online-comic2').onclick = async () => {
                onlineComic = comic2;
                localComic = comic1;
                hideConfirmationModal();
                await performMerge(onlineComic, localComic);
            };
            return; // Exit to wait for user selection
        }

        await performMerge(onlineComic, localComic);
    }

    async function performMerge(onlineComic, localComic) {
        if (!onlineComic || !localComic) {
            showConfirmationModal('合并错误', '未能正确识别在线漫画和本地漫画。', null, true);
            return;
        }

        showConfirmationModal(
            '确认合并',
            `您确定要将本地漫画 <b>${localComic.title}</b> 合并到在线漫画 <b>${onlineComic.title}</b> 吗？<br>` +
            `此操作将删除本地漫画源文件，并将本地路径信息和封面添加到在线漫画。`,
            async () => {
                try {
                    const response = await fetch('/api/comics/merge', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            online_comic_title: onlineComic.title,
                            local_comic_title: localComic.title
                        })
                    });

                    const result = await response.json();
                    if (!response.ok) {
                        throw new Error(result.message || '合并失败');
                    }

                    showConfirmationModal('合并成功', result.message, null, true);
                    fetchAndRenderComics(1, comicsPerPage, false);
                } catch (error) {
                    console.error('合并漫画失败:', error);
                    showConfirmationModal('合并失败', error.message, null, true);
                } finally {
                    toggleSelectionMode();
                }
            }
        );
    }

    function updateProgressBar(card, current, total) {
        const progressBar = card.querySelector('.progress-bar');
        if (total > 0 && current > 0) {
            const progress = Math.min((current / total) * 100, 100);
            progressBar.style.width = `${progress}%`;
        } else {
            progressBar.style.width = '0%';
        }
    }

    async function updateComicCounts() {
        try {
            const response = await fetch('/api/comics/stats');
            if (!response.ok) return;
            const stats = await response.json();

            document.getElementById('count-all').textContent = stats.all || 0;
            document.getElementById('count-favorites').textContent = stats.favorites || 0;
            document.getElementById('count-web').textContent = stats.web || 0;
            document.getElementById('count-downloaded').textContent = stats.downloaded || 0;
            document.getElementById('count-undownloaded').textContent = stats.undownloaded || 0;

            customFolders.forEach(folder => {
                const countElement = document.getElementById(`count-folder-${folder.name}`);
                if (countElement) {
                    countElement.textContent = '0';
                }
            });

            if (stats.folders) {
                for (const folderName in stats.folders) {
                    const countElement = document.getElementById(`count-folder-${folderName}`);
                    if (countElement) {
                        countElement.textContent = stats.folders[folderName] || 0;
                    }
                }
            }
            return stats;
        } catch (error) {
            console.error('Failed to update comic counts:', error);
            return null;
        }
    }

    // --- 文件夹/分类管理 V2 ---
    let currentEditingFolder = null;

    async function loadCustomFolders() {
        try {
            const response = await fetch('/api/folders');
            if (!response.ok) throw new Error('无法加载文件夹');
            customFolders = await response.json();
            renderCustomFolders();
        } catch (error) {
            console.error('加载自定义文件夹失败:', error);
        }
    }

    function renderCustomFolders() {
        customFoldersContainer.innerHTML = '';
        customFolders.forEach(folder => {
            const button = document.createElement('button');
            button.className = 'custom-folder-button nav-button';
            button.dataset.folder = folder.name;
            button.innerHTML = `<span>${folder.name}</span><span class="comic-count" id="count-folder-${folder.name}">0</span>`;

            button.addEventListener('click', () => {
                shelfState.filter = folder.name;
                setActiveFilter(button);
                currentPage = 1;
                hasMoreComics = true;
                fetchAndRenderComics(currentPage, comicsPerPage, false);
            });
            customFoldersContainer.appendChild(button);
        });
    }

    function openFolderModal() {
        renderModalFolderList();
        showListView();
        folderModal.style.display = 'flex';
        newFolderNameInput.focus();
    }

    function closeFolderModal() {
        folderModal.style.display = 'none';
        currentEditingFolder = null;
    }

    function showEditView(folder) {
        currentEditingFolder = folder;
        
        editFolderTitle.textContent = `编辑文件夹: ${folder.name}`;
        folderNameEditInput.value = folder.name;
        folderAutoToggle.checked = folder.auto;
        folderNameIncludesInput.value = (folder.name_includes || []).join(', ');
        folderTagIncludesInput.value = (folder.tag_includes || []).join(', ');

        autoClassificationRules.style.display = folder.auto ? 'block' : 'none';

        folderListView.style.display = 'none';
        folderEditView.style.display = 'block';
    }

    function showListView() {
        currentEditingFolder = null;
        folderListView.style.display = 'block';
        folderEditView.style.display = 'none';
    }

    function renderModalFolderList() {
        folderList.innerHTML = '';
        if (customFolders.length === 0) {
            folderList.innerHTML = '<p>还没有创建文件夹。</p>';
            return;
        }
        customFolders.forEach(folder => {
            const item = document.createElement('div');
            item.className = 'folder-list-item';
            item.dataset.folderName = folder.name;

            item.innerHTML = `
                <div class="folder-item-main">
                    <span class="folder-name">${folder.name}</span>
                </div>
                <div class="folder-item-controls">
                    <button class="folder-edit-button icon-button" title="编辑规则">${icons.pencil}</button>
                    <button class="folder-delete-button icon-button" title="删除">${icons.trash}</button>
                </div>
            `;
            item.querySelector('.folder-edit-button').addEventListener('click', () => {
                const latestFolder = customFolders.find(f => f.name === folder.name);
                showEditView(latestFolder);
            });
            item.querySelector('.folder-delete-button').addEventListener('click', () => handleDeleteFolder(folder.name));
            folderList.appendChild(item);
        });
    }

    async function handleAddNewFolder() {
        const newName = newFolderNameInput.value.trim();
        if (!newName) return;

        try {
            const response = await fetch('/api/folders', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ folder: { name: newName, auto: false, name_includes: [], tag_includes: [] } })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.message || '创建文件夹失败');
            }

            await loadCustomFolders();
            renderModalFolderList();
            updateComicCounts();
            newFolderNameInput.value = '';
        } catch (error) {
            console.error('创建文件夹失败:', error);
            showConfirmationModal('创建失败', error.message, null, true);
        }
    }

    async function handleSaveFolderChanges() {
        if (!currentEditingFolder) return;

        const originalName = currentEditingFolder.name;
        const updatedFolder = {
            name: folderNameEditInput.value.trim(),
            auto: folderAutoToggle.checked,
            name_includes: folderNameIncludesInput.value.split(',').map(s => s.trim()).filter(Boolean),
            tag_includes: folderTagIncludesInput.value.split(',').map(s => s.trim()).filter(Boolean)
        };

        if (!updatedFolder.name) {
            showConfirmationModal('保存失败', '文件夹名称不能为空。', null, true);
            return;
        }

        try {
            const response = await fetch(`/api/folders/${encodeURIComponent(originalName)}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(updatedFolder)
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.message || '保存失败');
            }
            
            await loadCustomFolders();
            renderModalFolderList();
            showListView();
            
            // If auto-categorization was turned on or folder was renamed, refresh shelf
            if (updatedFolder.auto || originalName !== updatedFolder.name) {
                await fetch('/api/scan', { method: 'POST' });
                if (shelfState.filter === originalName) {
                    shelfState.filter = updatedFolder.name;
                }
                fetchAndRenderComics(1, comicsPerPage, false);
            } else {
                updateComicCounts();
            }

        } catch (error) {
            console.error('保存文件夹更改失败:', error);
            showConfirmationModal('保存失败', error.message, null, true);
        }
    }

    async function handleDeleteFolder(folderName) {
        showConfirmationModal(
            `删除文件夹 '${folderName}'`,
            `您确定要删除此文件夹吗？文件夹内的漫画将不会被删除，仅恢复为未分类状态。此操作无法撤销。`,
            async () => {
                try {
                    await fetch(`/api/folders/${encodeURIComponent(folderName)}`, {
                        method: 'DELETE'
                    });

                    await loadCustomFolders();
                    renderModalFolderList();
                    
                    if (shelfState.filter === folderName) {
                        shelfState.filter = 'all';
                        setActiveFilter(filterAllButton);
                        fetchAndRenderComics(1, comicsPerPage, false);
                    } else {
                        updateComicCounts();
                    }
                } catch (error) {
                    console.error('删除文件夹失败:', error);
                    showConfirmationModal('删除失败', error.message, null, true);
                }
            }
        );
    }

    // --- 右键菜单 --- 
    function showContextMenu(event, comic) {
        event.preventDefault();
        if (selectionMode) return;

        contextMenuState.comic = comic;
        contextMenuState.isOpen = true;

        comicContextMenu.innerHTML = '';

        const title = document.createElement('div');
        title.className = 'context-menu-item';
        title.style.fontWeight = 'bold';
        title.style.cursor = 'default';
        title.textContent = '移动到文件夹:';
        comicContextMenu.appendChild(title);

        if (customFolders.length > 0) {
            customFolders.forEach(folder => {
                const item = document.createElement('div');
                item.className = 'context-menu-item';
                item.textContent = folder.name;
                item.addEventListener('click', () => {
                    setComicFolder(comic, folder.name);
                    hideContextMenu();
                });
                comicContextMenu.appendChild(item);
            });
        }
        
        if (comic.folder) {
            const divider = document.createElement('div');
            divider.className = 'context-menu-divider';
            comicContextMenu.appendChild(divider);

            const removeItem = document.createElement('div');
            removeItem.className = 'context-menu-item';
            removeItem.textContent = '从未分类移出';
            removeItem.addEventListener('click', () => {
                setComicFolder(comic, null);
                hideContextMenu();
            });
            comicContextMenu.appendChild(removeItem);
        }


        comicContextMenu.style.display = 'block';
        const { clientX: mouseX, clientY: mouseY } = event;
        const { x, y, width, height } = comicContextMenu.getBoundingClientRect();
        const { innerWidth, innerHeight } = window;
        
        comicContextMenu.style.left = `${mouseX + width > innerWidth ? innerWidth - width - 5 : mouseX}px`;
        comicContextMenu.style.top = `${mouseY + height > innerHeight ? innerHeight - height - 5 : mouseY}px`;
    }

    function hideContextMenu() {
        contextMenuState.isOpen = false;
        comicContextMenu.style.display = 'none';
    }

    async function setComicFolder(comic, folderName) {
        try {
            await fetch('/api/comics/folder', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ titles: [comic.title], folder: folderName })
            });
            
            if (shelfState.filter !== 'all' && shelfState.filter !== folderName) {
                const card = comicShelf.querySelector(`.comic-card[data-title="${comic.title}"]`);
                if (card) card.remove();
            }
            comic.folder = folderName;
            updateComicCounts();
        } catch (error) {
            console.error('更新漫画文件夹失败:', error);
        }
    }

    // --- 阅读器核心逻辑 ---
    async function openReader(comic) {
        if (selectionMode) return;
        
        const localSource = comic.sources.find(s => s.type === 'local');
        if (!localSource) {
            console.error("无法打开阅读器：找不到本地漫画路径。");
            return;
        }

        readerState.comic = comic;
        readerState.isOpen = true;
        readerState.direction = comic.direction || 'ltr';
        readerView.style.display = 'flex';
        document.body.classList.add('reader-open');
        readerView.addEventListener('mousemove', handleReaderMouseMove);

        try {
            const response = await fetch(`/api/comic/pages?path=${encodeURIComponent(localSource.path)}`);
            readerState.pages = await response.json();
            readerState.currentPage = comic.currentPage || 0;
            
            updateDirectionButton();
            renderCurrentPage();
        } catch (error) {
            console.error("无法加载页面列表:", error);
            readerImageContainer.innerHTML = `<p class="shelf-message">无法加载漫画页面</p>`;
        }
    }

    async function closeReader() {
        clearTimeout(progressUpdateTimer);
        const { comic, currentPage, direction } = readerState;
        const localSource = comic.sources.find(s => s.type === 'local');

        if (localSource) {
            try {
                await fetch('/api/comic/progress', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ path: localSource.path, page: currentPage, direction: direction })
                });
                
                const localComic = allComics.find(c => c.title === comic.title);
                if (localComic) {
                    localComic.currentPage = currentPage;
                    localComic.totalPages = readerState.pages.length;
                    const card = comicShelf.querySelector(`.comic-card[data-title="${comic.title}"]`);
                    if (card) {
                        updateProgressBar(card, currentPage, readerState.pages.length);
                    }
                }
            } catch (err) {
                console.error("关闭时保存进度失败:", err);
            }
        }

        readerState.isOpen = false;
        readerView.style.display = 'none';
        document.body.classList.remove('reader-open');
        readerImageContainer.innerHTML = '';
        readerView.removeEventListener('mousemove', handleReaderMouseMove);
        readerImageContainer.removeEventListener('scroll', handleLongStripScroll);
        readerControls.classList.remove('controls-visible');
        readerCloseButton.classList.remove('controls-visible');
    }

    function handleReaderMouseMove(e) {
        const isTop = e.clientY < window.innerHeight * 0.15;
        const isBottom = e.clientY > window.innerHeight * 0.85;

        if (isBottom) {
            readerControls.classList.add('controls-visible');
        } else {
            readerControls.classList.remove('controls-visible');
        }

        if (isTop || isBottom) {
            readerCloseButton.classList.add('controls-visible');
        } else {
            readerCloseButton.classList.remove('controls-visible');
        }
    }

    function setupReaderControls() {
        pageSlider.max = readerState.pages.length > 0 ? readerState.pages.length - 1 : 0;
        pageInfoEnd.textContent = readerState.pages.length;
        updateViewModeButtons();
        updateDirectionButton();
    }
    function handleLongStripScroll() {
        if (readerState.viewMode !== 'long' || !readerState.isOpen) return;
        const container = readerImageContainer;

        if (container.scrollHeight > container.clientHeight) {
            const scrollPercent = container.scrollTop / (container.scrollHeight - container.clientHeight);
            pageSlider.isUpdatingFromScroll = true;
            pageSlider.value = scrollPercent * pageSlider.max;
        }

        let currentPageInStrip = 0;
        const images = container.querySelectorAll('img');
        const containerMidPoint = container.scrollTop + (container.clientHeight / 2);
        for (let i = 0; i < images.length; i++) {
            if (images[i].offsetTop + images[i].offsetHeight > containerMidPoint) {
                currentPageInStrip = i;
                break;
            }
        }
        readerState.currentPage = currentPageInStrip;

        pageInfoStart.textContent = readerState.currentPage + 1;
        pageInfoCurrent.textContent = `${readerState.currentPage + 1} / ${readerState.pages.length}`;

        saveProgress();
    }

    function renderCurrentPage() {
        if (!readerState.isOpen) return;

        readerImageContainer.innerHTML = '';
        readerImageContainer.className = 'reader-image-container';
        readerImageContainer.removeEventListener('scroll', handleLongStripScroll);

        const totalPages = readerState.pages.length;
        if (totalPages === 0) return;
        
        const localSource = readerState.comic.sources.find(s => s.type === 'local');
        if (!localSource) return;

        const getPageURL = (index) => `/api/comic/page?path=${encodeURIComponent(localSource.path)}&page=${encodeURIComponent(readerState.pages[index])}`;

        if (readerState.viewMode === 'long') {
            readerImageContainer.classList.add('long-strip');
            pageSlider.max = 1000;

            let imagesLoaded = 0;
            const images = [];

            readerState.pages.forEach((_, i) => {
                const img = document.createElement('img');
                images.push(img);
                img.onload = () => {
                    imagesLoaded++;
                    if (imagesLoaded === totalPages) {
                        const savedPage = readerState.currentPage || 0;
                        if (images.length > savedPage) {
                            readerImageContainer.scrollTop = images[savedPage].offsetTop;
                        } else {
                            readerImageContainer.scrollTop = 0;
                        }
                        handleLongStripScroll();
                    }
                };
                img.src = getPageURL(i);
                readerImageContainer.appendChild(img);
            });

            readerImageContainer.addEventListener('scroll', handleLongStripScroll, { passive: true });

        } else {
            readerImageContainer.scrollTop = 0;
            setupReaderControls();

            const pageIndex = readerState.currentPage;
            if (readerState.viewMode === 'double') {
                readerImageContainer.classList.add('double-page');
                if (pageIndex > 0 && pageIndex % 2 !== 0) {
                    readerState.currentPage = pageIndex - 1;
                }
                const currentPage = readerState.currentPage;

                const img1 = document.createElement('img');
                img1.src = getPageURL(currentPage);
                
                if (currentPage + 1 < totalPages) {
                    const img2 = document.createElement('img');
                    img2.src = getPageURL(currentPage + 1);
                    if (readerState.direction === 'rtl') {
                        readerImageContainer.append(img2, img1);
                    } else {
                        readerImageContainer.append(img1, img2);
                    }
                } else {
                    readerImageContainer.append(img1);
                }
            } else { // single
                const img = document.createElement('img');
                img.src = getPageURL(pageIndex);
                readerImageContainer.appendChild(img);
            }
        }

        updateControlsUI();
        saveProgress();
    }

    function updateControlsUI() {
        if (readerState.viewMode === 'long') {
            const initialPage = readerState.currentPage || 0;
            pageInfoStart.textContent = initialPage + 1;
            pageInfoCurrent.textContent = `${initialPage + 1} / ${readerState.pages.length}`;
        } else {
            pageSlider.value = readerState.currentPage;
            pageInfoStart.textContent = readerState.currentPage + 1;
            pageInfoCurrent.textContent = `${readerState.currentPage + 1} / ${readerState.pages.length}`;
        }
    }

    function changePage(delta) {
        if (!readerState.isOpen) return;
        const totalPages = readerState.pages.length;
        const step = readerState.viewMode === 'double' ? 2 : 1;
        const directionDelta = readerState.direction === 'rtl' && readerState.viewMode === 'double' ? -delta : delta;
        let newPage = readerState.currentPage + (directionDelta * step);
        readerState.currentPage = Math.max(0, Math.min(newPage, totalPages - 1));
        renderCurrentPage();
    }

    function jumpToPage(pageIndex) {
        if (readerState.viewMode === 'long') return;
        readerState.currentPage = parseInt(pageIndex, 10);
        renderCurrentPage();
    }

    function changeViewMode(mode) {
        readerState.viewMode = mode;
        updateViewModeButtons();
        renderCurrentPage();
    }

    function changeDirection() {
        readerState.direction = readerState.direction === 'ltr' ? 'rtl' : 'ltr';
        readerState.comic.direction = readerState.direction;
        updateDirectionButton();
        renderCurrentPage();
    }

    function updateViewModeButtons() {
        [viewModeSingle, viewModeDouble, viewModeLong].forEach(btn => btn.classList.remove('active'));
        if (readerState.viewMode === 'single') viewModeSingle.classList.add('active');
        else if (readerState.viewMode === 'double') viewModeDouble.classList.add('active');
        else viewModeLong.classList.add('active');
        directionToggleButton.style.display = readerState.viewMode === 'double' ? 'flex' : 'none';
    }

    function updateDirectionButton() {
        if (readerState.direction === 'rtl') {
            directionToggleButton.classList.add('active');
            directionToggleButton.title = '阅读方向: 从右到左';
        } else {
            directionToggleButton.classList.remove('active');
            directionToggleButton.title = '阅读方向: 从左到右';
        }
    }

    function saveProgress() {
        clearTimeout(progressUpdateTimer);
        progressUpdateTimer = setTimeout(() => {
            const { comic, currentPage, direction } = readerState;
            const localSource = comic.sources.find(s => s.type === 'local');
            if (!localSource) return;

            comic.currentPage = currentPage;
            comic.totalPages = readerState.pages.length;
            comic.direction = direction;
            fetch('/api/comic/progress', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path: localSource.path, page: currentPage, direction: direction })
            }).catch(err => console.error("保存进度失败:", err));
        }, 500);
    }

    async function toggleFavorite(comic, card) {
        const isFavorite = !card.classList.contains('favorite');
        try {
            await fetch('/api/comics/favorite', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ titles: [comic.title], favorite: isFavorite })
            });
            comic.is_favorite = isFavorite;
            card.classList.toggle('favorite', isFavorite);
            updateComicCounts();

            const favoriteButton = card.querySelector('.favorite-button');
            if (isFavorite) {
                favoriteButton.classList.add('popping');
                favoriteButton.addEventListener('animationend', () => {
                    favoriteButton.classList.remove('popping');
                }, { once: true });
            }

            if (shelfState.filter === 'favorites' && !isFavorite) {
                card.remove();
            }
        } catch (error) {
            console.error('切换最爱状态失败:', error);
        }
    }

    function setActiveFilter(activeButton) {
        document.querySelectorAll('.navigation .active, .custom-folders-container .active').forEach(b => b.classList.remove('active'));
        if (activeButton) {
            activeButton.classList.add('active');
        }
    }

    // --- 确认弹窗逻辑 ---
    function showConfirmationModal(title, message, onConfirm, isAlert = false) {
        confirmModalTitle.textContent = title;
        confirmModalMessage.innerHTML = message;
        confirmCallback = onConfirm;

        if (isAlert) {
            confirmModalCancel.style.display = 'none';
            confirmModalConfirm.textContent = '好的';
        } else {
            confirmModalCancel.style.display = 'inline-flex';
            confirmModalConfirm.textContent = '确认';
        }

        confirmModal.style.display = 'flex';
    }

    function hideConfirmationModal() {
        confirmModal.style.display = 'none';
        confirmCallback = null;
    }

    // --- 事件绑定 ---
    function setupEventListeners() {
        searchInput.addEventListener('input', e => {
            clearTimeout(searchInput.timer);
            searchInput.timer = setTimeout(() => {
                shelfState.searchTerm = e.target.value;
                currentPage = 1;
                hasMoreComics = true;
                fetchAndRenderComics(currentPage, comicsPerPage, false);
            }, 300);
        });

        sortButton.addEventListener('click', () => sortOptions.classList.toggle('visible'));

        function updateSortButtons() {
            sortOptions.querySelectorAll('.sort-option').forEach(button => {
                const [sortBy, sortOrder] = button.dataset.sort.split('_');
                const orderIndicator = button.querySelector('.sort-order');

                if (shelfState.sort.by === sortBy) {
                    button.classList.add('active');
                    if (shelfState.sort.order === 'desc') {
                        orderIndicator.innerHTML = ' &darr;';
                    } else {
                        orderIndicator.innerHTML = ' &uarr;';
                    }
                } else {
                    button.classList.remove('active');
                    orderIndicator.innerHTML = '';
                }
            });
        }

        sortOptions.querySelectorAll('.sort-option').forEach(button => {
            button.addEventListener('click', async e => {
                const [sortBy, defaultOrder] = e.currentTarget.dataset.sort.split('_');

                if (shelfState.sort.by === sortBy) {
                    shelfState.sort.order = shelfState.sort.order === 'asc' ? 'desc' : 'asc';
                } else {
                    shelfState.sort.by = sortBy;
                    shelfState.sort.order = defaultOrder || 'desc';
                }

                updateSortButtons();
                sortOptions.classList.remove('visible');
                currentPage = 1;
                hasMoreComics = true;
                await fetchAndRenderComics(currentPage, comicsPerPage, false);
            });
        });

        filterAllButton.addEventListener('click', async () => {
            shelfState.filter = 'all';
            setActiveFilter(filterAllButton);
            currentPage = 1;
            hasMoreComics = true;
            await fetchAndRenderComics(currentPage, comicsPerPage, false);
        });
    
        filterFavoritesButton.addEventListener('click', async () => {
            shelfState.filter = 'favorites';
            setActiveFilter(filterFavoritesButton);
            currentPage = 1;
            hasMoreComics = true;
            await fetchAndRenderComics(currentPage, comicsPerPage, false);
        });
    
        filterDropdownButton.addEventListener('click', () => filterOptions.classList.toggle('visible'));
    
        filterOptions.querySelectorAll('.filter-option').forEach(button => {
            button.addEventListener('click', async e => {
                const filterValue = e.currentTarget.dataset.filter;
                shelfState.filter = filterValue;
                setActiveFilter(filterDropdownButton);
                filterOptions.classList.remove('visible');
                currentPage = 1;
                hasMoreComics = true;
                await fetchAndRenderComics(currentPage, comicsPerPage, false);
            });
        });

        refreshButton.addEventListener('click', async () => {
            try {
                await fetch('/api/scan', { method: 'POST' });
                currentPage = 1;
                hasMoreComics = true;
                await fetchAndRenderComics(currentPage, comicsPerPage, false);
            } catch (error) {
                console.error('刷新书架时出错:', error);
            }
        });

        batchSelectButton.addEventListener('click', toggleSelectionMode);
        batchCancelButton.addEventListener('click', toggleSelectionMode);
        batchSelectAllButton.addEventListener('click', handleSelectAll);
        batchAddFavoriteButton.addEventListener('click', () => batchUpdateFavorites(true));
        batchRemoveFavoriteButton.addEventListener('click', () => batchUpdateFavorites(false));
        batchRemoveFromFolderButton.addEventListener('click', batchRemoveFromFolder);
        batchMergeButton.addEventListener('click', handleMergeComics);
        batchDeleteButton.addEventListener('click', batchDelete);

        // --- Folder Modal V2 Listeners ---
        addFolderButton.addEventListener('click', openFolderModal);
        closeModalButton.addEventListener('click', closeFolderModal);
        folderModal.addEventListener('click', e => {
            if (e.target === folderModal) closeFolderModal();
        });

        addFolderConfirmButton.addEventListener('click', handleAddNewFolder);
        newFolderNameInput.addEventListener('keyup', e => {
            if (e.key === 'Enter') handleAddNewFolder();
        });

        backToFolderListButton.addEventListener('click', showListView);
        saveFolderChangesButton.addEventListener('click', handleSaveFolderChanges);

        folderAutoToggle.addEventListener('change', () => {
            autoClassificationRules.style.display = folderAutoToggle.checked ? 'block' : 'none';
        });

        settingsButton.addEventListener('click', openSettingsModal);
        closeSettingsModalButton.addEventListener('click', () => settingsModal.style.display = 'none');
        settingsModal.addEventListener('click', e => {
            if (e.target === settingsModal) settingsModal.style.display = 'none';
        });
        addManagedFolderButton.addEventListener('click', handleAddManagedFolder);
        newManagedFolderPathInput.addEventListener('keyup', e => {
            if (e.key === 'Enter') handleAddManagedFolder();
        });
        managedFoldersList.addEventListener('click', e => {
            const deleteButton = e.target.closest('.folder-delete-button');
            if (deleteButton) {
                handleDeleteManagedFolder(deleteButton.dataset.path);
            }
            const relocateButton = e.target.closest('.folder-relocate-button');
            if (relocateButton) {
                handleRelocateFolder(relocateButton.dataset.path);
            }
        });

        document.getElementById('clean-cache-button').addEventListener('click', handleCleanCache);
        document.getElementById('cleanup-db-button').addEventListener('click', handleCleanupDatabase);
        const clearAllDataButton = document.getElementById('clear-all-data-button');
        if (clearAllDataButton) {
            clearAllDataButton.addEventListener('click', handleClearAllData);
        }


        confirmModalCancel.addEventListener('click', hideConfirmationModal);
        confirmModalConfirm.addEventListener('click', () => {
            if (confirmCallback) {
                confirmCallback();
            }
            hideConfirmationModal();
        });
        confirmModal.addEventListener('click', e => {
            if (e.target === confirmModal) hideConfirmationModal();
        });

        detailsView.addEventListener('click', e => {
            if (e.target.id === 'details-close-button' || e.target === detailsView) {
                closeDetailsView();
            }
            if (e.target.closest('#edit-tags-button')) {
                toggleTagEditMode();
            }
            if (e.target.closest('#edit-display-name-button')) {
                toggleDisplayNameEditMode();
            }
            if (e.target.id === 'save-display-name-button') {
                saveDisplayName();
            }
            if (e.target.id === 'cancel-display-name-button') {
                cancelDisplayNameEdit();
            }
            if (e.target.classList.contains('remove-tag-btn')) {
                const tag = e.target.dataset.tag;
                handleTagUpdate('remove', tag);
            }
            if (e.target.classList.contains('add-tag-button')) {
                const input = detailsView.querySelector('.add-tag-input');
                const tag = input.value.trim();
                if (tag) {
                    handleTagUpdate('add', tag);
                }
            }
        });

        detailsView.addEventListener('keyup', e => {
            if (e.key === 'Enter' && e.target.classList.contains('add-tag-input')) {
                const tag = e.target.value.trim();
                if (tag) {
                    handleTagUpdate('add', tag);
                }
            }
        });


        document.addEventListener('click', (e) => {
            if (!sortButton.contains(e.target) && !sortOptions.contains(e.target)) {
                sortOptions.classList.remove('visible');
            }
            if (!filterDropdownButton.contains(e.target) && !filterOptions.contains(e.target)) {
                filterOptions.classList.remove('visible');
            }
            if (contextMenuState.isOpen && !comicContextMenu.contains(e.target)) {
                hideContextMenu();
            }
        });
        
        readerCloseButton.addEventListener('click', closeReader);
        directionToggleButton.addEventListener('click', changeDirection);
        pageSlider.addEventListener('input', (e) => {
            if (pageSlider.isUpdatingFromScroll) {
                pageSlider.isUpdatingFromScroll = false;
                return;
            }
            if (readerState.viewMode === 'long') {
                const container = readerImageContainer;
                if (container.scrollHeight > container.clientHeight) {
                    const newScrollTop = (e.target.value / pageSlider.max) * (container.scrollHeight - container.clientHeight);
                    container.scrollTop = newScrollTop;
                    handleLongStripScroll();
                }
            } else {
                jumpToPage(e.target.value);
            }
        });
        viewModeSingle.addEventListener('click', () => changeViewMode('single'));
        viewModeDouble.addEventListener('click', () => changeViewMode('double'));
        viewModeLong.addEventListener('click', () => changeViewMode('long'));
        readerView.addEventListener('click', (e) => {
            if (e.target === readerView || e.target === readerImageContainer) {
                const clickX = e.clientX / window.innerWidth;
                const isRTL = readerState.direction === 'rtl' && readerState.viewMode === 'double';
                const leftClickArea = isRTL ? 0.6 : 0.4;
                const rightClickArea = isRTL ? 0.4 : 0.6;
                if (clickX < rightClickArea) changePage(-1);
                if (clickX > leftClickArea) changePage(1);
            }
        });
        window.addEventListener('keydown', (e) => {
            if (!readerState.isOpen) return;
            const isRTL = readerState.direction === 'rtl' && readerState.viewMode === 'double';
            if (e.key === 'ArrowRight') changePage(isRTL ? -1 : 1);
            if (e.key === 'ArrowLeft') changePage(isRTL ? 1 : -1);
            if (e.key === 'Escape') closeReader();
        });
        readerView.addEventListener('wheel', (e) => {
            if (readerState.viewMode !== 'long') {
                e.preventDefault();
                if (e.deltaY > 0) changePage(1);
                if (e.deltaY < 0) changePage(-1);
            }
        }, { passive: false });

        zoomSmallButton.addEventListener('click', () => setZoomLevel('small'));
        zoomMediumButton.addEventListener('click', () => setZoomLevel('medium'));
        zoomLargeButton.addEventListener('click', () => setZoomLevel('large'));
        coverModeToggle.addEventListener('click', toggleCoverMode);

        window.addEventListener('scroll', async () => {
            if (hasMoreComics && !isLoadingMore && 
                (window.innerHeight + window.scrollY) >= document.body.offsetHeight - 400) {
                currentPage++;
                await fetchAndRenderComics(currentPage, comicsPerPage, true);
            }
        });
    }
    function setZoomLevel(level) {
        shelfState.zoomLevel = level;
        updateZoomButtons();
        
        const root = document.documentElement;
        let newMinWidth;
        switch(level) {
            case 'small':
                newMinWidth = '120px';
                break;
            case 'large':
                newMinWidth = '240px';
                break;
            case 'medium':
            default:
                newMinWidth = '180px';
                break;
        }
        root.style.setProperty('--comic-card-min-width', newMinWidth);

        document.querySelectorAll('.comic-card').forEach(card => {
            const comicTitle = card.dataset.title;
            const comic = allComics.find(c => c.title === comicTitle);
            if (comic) {
                const coverImg = card.querySelector('.comic-cover');
                const newCoverUrl = getCoverUrlForCurrentZoom(comic);
                if (coverImg.src !== newCoverUrl) {
                    coverImg.src = newCoverUrl;
                }
            }
        });
    }

    function updateZoomButtons() {
        [zoomSmallButton, zoomMediumButton, zoomLargeButton].forEach(btn => btn.classList.remove('active'));
        switch(shelfState.zoomLevel) {
            case 'small':
                zoomSmallButton.classList.add('active');
                break;
            case 'medium':
                zoomMediumButton.classList.add('active');
                break;
            case 'large':
                zoomLargeButton.classList.add('active');
                break;
        }
    }

    function toggleCoverMode() {
        const isEnabled = document.body.classList.toggle('cover-only-mode');
        localStorage.setItem('coverModeEnabled', isEnabled);
        coverModeToggle.classList.toggle('active', isEnabled);
    }

    // --- 设置模块逻辑 ---
    async function openSettingsModal() {
        try {
            const response = await fetch('/api/settings');
            if (!response.ok) {
                throw new Error(`无法加载设置。服务器返回状态: ${response.status} ${response.statusText}`);
            }
            const config = await response.json();
            renderManagedFolders(config.managed_folders || []);

            settingsModal.style.display = 'flex';
        } catch (error) {
            console.error('打开设置时出错:', error);
            let alertMessage = '打开设置时发生未知错误。';
            if (error instanceof TypeError) {
                alertMessage = '网络错误，无法连接到服务器。请检查服务器是否正在运行以及浏览器是否能访问127.0.0.1。';
            } else {
                alertMessage = error.message;
            }
            showConfirmationModal('加载设置失败', alertMessage, null, true);
        }
    }

    function renderManagedFolders(folders) {
        managedFoldersList.innerHTML = '';
        if (folders.length === 0) {
            managedFoldersList.innerHTML = '<p>还没有受控文件夹。</p>';
            return;
        }
        folders.forEach(folder => {
            const item = document.createElement('div');
            item.className = 'folder-list-item';
            
            const nameSpan = document.createElement('span');
            nameSpan.className = 'folder-name';
            nameSpan.title = folder;
            nameSpan.textContent = folder;
            
            const controlsDiv = document.createElement('div');
            controlsDiv.className = 'folder-item-controls';
            controlsDiv.innerHTML = `
                <button class="folder-relocate-button icon-button" data-path="${folder.replace(/"/g, '&quot;')}" title="迁移路径">${icons.pencil}</button>
                <button class="folder-delete-button icon-button" data-path="${folder.replace(/"/g, '&quot;')}" title="删除">${icons.trash}</button>
            `;

            item.appendChild(nameSpan);
            item.appendChild(controlsDiv);
            managedFoldersList.appendChild(item);
        });
    }

    async function handleAddManagedFolder() {
        const path = newManagedFolderPathInput.value.trim();
        if (!path) return;

        try {
            const response = await fetch('/api/settings/folders', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path })
            });
            const result = await response.json();
            if (!response.ok) {
                throw new Error(result.message || '添加失败');
            }
            newManagedFolderPathInput.value = '';
            await openSettingsModal();
            startScanPolling(); 
        } catch (error) {
            console.error('添加受控文件夹失败:', error);
            showConfirmationModal('添加失败', error.message, null, true);
        }
    }

    async function handleDeleteManagedFolder(path) {
        if (!path) return;
        showConfirmationModal(
            `移除文件夹`,
            `您确定要移除文件夹 "${path}" 吗？<br>这将会从书架中移除所有来自该文件夹的漫画。`,
            async () => {
                try {
                    await fetch('/api/settings/folders', {
                        method: 'DELETE',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ path })
                    });
                    await openSettingsModal();
                    await fetchAndRenderComics(1, comicsPerPage, false);
                } catch (error) {
                    console.error('删除漫画库路径失败:', error);
                    showConfirmationModal('删除失败', error.message, null, true);
                }
            }
        );
    }

    async function handleRelocateFolder(oldPath) {
        const newPath = prompt(`请输入文件夹 "${oldPath}" 的新位置:`, oldPath);

        if (!newPath || newPath.trim() === '' || newPath.trim() === oldPath) {
            return; // User cancelled or didn't change the path
        }

        try {
            const response = await fetch('/api/settings/folders/relocate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ old_path: oldPath, new_path: newPath.trim() })
            });

            const result = await response.json();
            if (!response.ok) {
                throw new Error(result.message || '迁移失败');
            }
            
            showConfirmationModal('迁移成功', result.message, null, true);
            await openSettingsModal(); // Refresh the settings modal
            // Also refresh the main comic list in case the current view is affected
            await fetchAndRenderComics(1, comicsPerPage, false);

        } catch (error) {
            console.error('迁移文件夹失败:', error);
            showConfirmationModal('迁移失败', error.message, null, true);
        }
    }

    async function handleCleanCache() {
        showConfirmationModal(
            '清理封面缓存',
            '您确定要清理无效的封面缓存吗？<br>此操作将删除所有不存在于当前书架中的封面图片。',
            async () => {
                try {
                    const response = await fetch('/api/clean_cover_cache', { method: 'POST' });
                    const result = await response.json();
                    if (!response.ok) {
                        throw new Error(result.message || '清理失败');
                    }
                    showConfirmationModal('清理完成', `成功删除了 ${result.deleted_files} 个无效的封面文件。`, null, true);
                } catch (error) {
                    console.error('清理封面缓存失败:', error);
                    showConfirmationModal('清理失败', error.message, null, true);
                }
            }
        );
    }

    async function handleCleanupDatabase() {
        showConfirmationModal(
            '清理数据库',
            '您确定要清理数据库吗？<br>此操作将永久移除所有指向已删除或移动的本地漫画文件的记录。',
            async () => {
                try {
                    const response = await fetch('/api/cleanup', { method: 'POST' });
                    const result = await response.json();
                    if (!response.ok) {
                        throw new Error(result.message || '清理失败');
                    }
                    showConfirmationModal('清理完成', `成功删除了 ${result.cleaned_count} 个无效的数据库条目。`, null, true);
                    await fetchAndRenderComics(1, comicsPerPage, false);
                } catch (error) {
                    console.error('清理数据库失败:', error);
                    showConfirmationModal('清理失败', error.message, null, true);
                }
            }
        );
    }

    async function handleClearAllData() {
        showConfirmationModal(
            '清除所有数据',
            '您确定要清除所有漫画数据、文件夹设置和配置吗？此操作将清空书架，但不会删除本地漫画源文件。此操作无法撤销。',
            async () => {
                try {
                    const response = await fetch('/api/clear_all_data', { method: 'POST' });
                    const result = await response.json();
                    if (!response.ok) {
                        throw new Error(result.message || '清除失败');
                    }
                    showConfirmationModal('清除完成', result.message, null, true);
                    // After clearing, re-fetch everything to update the UI
                    await fetchAndRenderComics(1, comicsPerPage, false);
                    await loadCustomFolders(); // Reload folders as they are cleared
                    await openSettingsModal(); // Re-open settings to show updated managed folders (empty)
                } catch (error) {
                    console.error('清除所有数据失败:', error);
                    showConfirmationModal('清除失败', error.message, null, true);
                }
            }
        );
    }

    // --- 扫描进度轮询 ---
    let scanPollInterval = null;

    function startScanPolling() {
        if (scanPollInterval) {
            clearInterval(scanPollInterval);
        }
        scanPollInterval = setInterval(pollScanProgress, 500);
    }

    async function pollScanProgress() {
        try {
            const response = await fetch('/api/scan/progress');
            if (!response.ok) {
                // If the server returns an error, stop polling
                clearInterval(scanPollInterval);
                scanPollInterval = null;
                scanProgressContainer.style.display = 'none';
                return;
            }
            const progress = await response.json();

            if (progress.in_progress) {
                scanProgressContainer.style.display = 'flex';
                const percentage = progress.total > 0 ? (progress.current / progress.total) * 100 : 0;
                scanProgressBarInner.style.width = `${percentage}%`;
                scanProgressText.textContent = `${progress.message} (${progress.current}/${progress.total})`;
                scanProgressText.title = `${progress.message} (${progress.current}/${progress.total})`;
            } else {
                clearInterval(scanPollInterval);
                scanPollInterval = null;
                scanProgressContainer.style.display = 'none';
                // Once scanning is complete, refresh the comics and counts
                await fetchAndRenderComics(1, comicsPerPage, false);
                await updateComicCounts();
            }
        } catch (error) {
            console.error('轮询扫描进度失败:', error);
            clearInterval(scanPollInterval);
            scanPollInterval = null;
            scanProgressContainer.style.display = 'none';
        }
    }


    // --- 初始加载 ---
    async function initialize() {
        initIcons();
        setupEventListeners();
        await loadCustomFolders();
        await openSettingsModal();
        settingsModal.style.display = 'none';
        await fetchAndRenderComics(currentPage, comicsPerPage, false);
        updateZoomButtons();
        updateSortButtons();
        // Check if a scan is already in progress on page load
        pollScanProgress();
    }

        // Initialize cover mode from localStorage
        const savedCoverMode = localStorage.getItem('coverModeEnabled');
        if (savedCoverMode === 'true') {
            document.body.classList.add('cover-only-mode');
            coverModeToggle.classList.add('active');
        }

        initIcons();
        setupEventListeners();
        loadCustomFolders();
        fetchAndRenderComics();
        startScanPolling();
    });
