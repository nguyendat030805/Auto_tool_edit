// Shared DOM selector for the browser UI.
const $ = s => document.querySelector(s);
let bg = null, items = [], mode = 'tts';
const MAX_IMG = 6;

// Check the configured GitHub release and show an update prompt when needed.
async function checkForUpdates() {
  const status = $('#updateStatus');
  const statusText = $('#updateStatusText');
  const notice = $('#updateNotice');
  try {
    const response = await fetch('/api/update');
    if (!response.ok) throw new Error('HTTP ' + response.status);
    const update = await response.json();
    $('#appVersion').textContent = 'v' + update.current_version;
    notice.hidden = true;
    status.hidden = true;

    if (update.update_available) {
      $('#updateTitle').textContent = 'Đã có phiên bản mới: v' + update.latest_version;
      $('#updateMessage').textContent = 'Bản hiện tại: v' + update.current_version + '. Tải bản cập nhật để tiếp tục sử dụng.';
      const link = $('#updateLink');
      link.href = update.download_url || update.release_url;
      link.textContent = update.download_url ? 'Tải bản mới' : 'Xem bản phát hành';
      notice.hidden = false;
    } else if (update.error) {
      statusText.textContent = update.error;
      status.hidden = false;
    } else {
      statusText.textContent = 'Bạn đang dùng phiên bản mới nhất.';
      status.hidden = false;
    }
  } catch (error) {
    $('#appVersion').textContent = 'v1.0.0';
    statusText.textContent = 'Không kiểm tra được cập nhật. ' + (error.message || error);
    status.hidden = false;
  }
}

$('#checkUpdate').addEventListener('click', checkForUpdates);
checkForUpdates();

// Compare upload names in natural numeric order.
const natCmp = (a, b) => a.name.localeCompare(b.name, undefined, {numeric: true});
// Check whether a selected file name matches a given extension pattern.
const isExt = (f, re) => re.test(f.name);
// Identify supported video, image, and audio uploads.
const isVideo = f => f.type.startsWith('video/') || isExt(f, /\.(mp4|mov|m4v|webm|mkv|avi)$/i);
const isImage = f => f.type.startsWith('image/') || isExt(f, /\.(png|jpe?g|webp|bmp)$/i);
const isAudio = f => f.type.startsWith('audio/') || isExt(f, /\.(mp3|wav|m4a|aac|ogg|flac)$/i);

// tránh việc trình duyệt mở file khi thả nhầm ra ngoài vùng kéo thả
['dragover', 'drop'].forEach(ev => window.addEventListener(ev, e => e.preventDefault()));

// Initialize drag-and-drop and file-picker behavior for an upload zone.
function setupDrop(zone, input, handler) {
  ['dragenter', 'dragover'].forEach(ev => zone.addEventListener(ev, e => { e.preventDefault(); zone.classList.add('over'); }));
  ['dragleave', 'drop'].forEach(ev => zone.addEventListener(ev, e => { e.preventDefault(); zone.classList.remove('over'); }));
  zone.addEventListener('drop', e => handler([...e.dataTransfer.files]));
  zone.addEventListener('click', () => input.click());
  input.addEventListener('change', () => { handler([...input.files]); input.value = ''; });
}

// Show a status message in the video-creation view.
function showMsg(t, isErr) { const m = $('#msg'); m.textContent = t; m.className = 'msg' + (isErr ? ' err' : ''); }
const mb = n => (n / 1048576).toFixed(1) + ' MB';

// --- video nền
// Store the selected background video and update its preview.
function setBg(f) {
  bg = f;
  $('#bgInfo').hidden = false;
  $('#bgPrev').src = URL.createObjectURL(f);
  $('#bgName').textContent = f.name + ' (' + mb(f.size) + ')';
  showMsg('');
}
setupDrop($('#dropBg'), $('#inBg'), files => {
  const f = files.find(isVideo);
  if (!f) { showMsg('Vui lòng chọn file video.', true); return; }
  setBg(f);
});

// --- ảnh comment
let pasteSeq = 0;
// ảnh dán từ clipboard đều tên "image.png", đặt tên riêng để dễ nhận biết
// Give pasted images a useful unique filename when browsers provide a generic name.
function named(f) {
  if (f.name && !/^image\.\w+$/i.test(f.name)) return f;
  const ext = (f.type.split('/')[1] || 'png').replace('jpeg', 'jpg');
  return new File([f], 'dan-' + (++pasteSeq) + '.' + ext, {type: f.type});
}
// Add selected comment images to the video job, respecting the upload limit.
function addComments(files) {
  const imgs = files.filter(isImage).map(named);
  if (!imgs.length) { showMsg('Vui lòng chọn file ảnh.', true); return 0; }
  let added = 0;
  for (const f of imgs) {
    if (items.length >= MAX_IMG) { showMsg('Tối đa ' + MAX_IMG + ' ảnh comment.', true); break; }
    items.push({file: f, url: URL.createObjectURL(f), text: '', audio: null});
    added++;
  }
  renderItems();
  return added;
}
setupDrop($('#dropImg'), $('#inImg'), files => addComments(files.sort(natCmp)));

// Rebuild the comment rows after an item or its order changes.
function renderItems() {
  const box = $('#items');
  box.innerHTML = '';
  items.forEach((it, i) => {
    const row = document.createElement('div'); row.className = 'item';
    const num = document.createElement('div'); num.className = 'num'; num.textContent = i + 1;
    const img = document.createElement('img'); img.src = it.url;
    const body = document.createElement('div'); body.className = 'body';
    if (mode === 'tts') {
      const ta = document.createElement('textarea');
      ta.placeholder = 'Gõ lời đọc cho comment này...';
      ta.value = it.text;
      ta.addEventListener('input', () => { it.text = ta.value; });
      body.appendChild(ta);
    } else {
      const tag = document.createElement('div');
      tag.className = 'audio-tag' + (it.audio ? ' ok' : '');
      tag.textContent = it.audio ? 'Audio: ' + it.audio.name : 'Chưa có file audio (kéo vào ô ở mục 4)';
      body.appendChild(tag);
    }
    const btns = document.createElement('div'); btns.className = 'btns';
    // Create a compact action button and attach its handler.
    const mk = (label, title, fn) => {
      const b = document.createElement('button'); b.className = 'mini'; b.textContent = label; b.title = title;
      b.addEventListener('click', fn); return b;
    };
    btns.appendChild(mk('↑', 'Lên', () => move(i, -1)));
    btns.appendChild(mk('↓', 'Xuống', () => move(i, 1)));
    btns.appendChild(mk('✕', 'Xoá', () => { items.splice(i, 1); renderItems(); }));
    row.append(num, img, body, btns);
    box.appendChild(row);
  });
}
// Move one comment image up or down in the display order.
function move(i, d) {
  const j = i + d;
  if (j < 0 || j >= items.length) return;
  [items[i], items[j]] = [items[j], items[i]];
  renderItems();
}

// --- bài viết chính (tuỳ chọn)
let post = null;
// Synchronize the main-post image and narration controls with current state.
function syncPost() {
  $('#postBox').hidden = !post;
  $('#dropPost').hidden = !!post;
  if (!post) return;
  $('#postImg').src = post.url;
  const isTts = mode === 'tts';
  $('#postText').hidden = !isTts;
  $('#postAudioTag').hidden = isTts;
  $('#dropPostAudio').hidden = isTts;
  const tag = $('#postAudioTag');
  tag.textContent = post.audio ? 'Audio: ' + post.audio.name : 'Chưa có file audio đọc bài viết';
  tag.className = 'audio-tag' + (post.audio ? ' ok' : '');
}
// Set or replace the optional main-post image used in the video.
function setPostImage(f) {
  post = {file: named(f), url: URL.createObjectURL(f), text: $('#postText').value || '', audio: post ? post.audio : null};
  showMsg('');
  syncPost();
}
setupDrop($('#dropPost'), $('#inPost'), files => {
  const f = files.find(isImage);
  if (!f) { showMsg('Vui lòng chọn file ảnh.', true); return; }
  setPostImage(f);
});
$('#postText').addEventListener('input', e => { if (post) post.text = e.target.value; });
$('#postRemove').addEventListener('click', () => { post = null; $('#postText').value = ''; syncPost(); });
setupDrop($('#dropPostAudio'), $('#inPostAudio'), files => {
  const f = files.find(isAudio);
  if (!f || !post) { showMsg('Vui lòng chọn file audio.', true); return; }
  post.audio = f; showMsg(''); syncPost();
});

// --- dán ảnh bằng Ctrl+V (không cần lưu file)
// Ảnh dán vào vùng mà chuột đang đứng: "Bài viết chính" hoặc "Ảnh comment" (mặc định: comment).
let pasteTarget = 'comments';
// Highlight the video section that should receive a pasted image.
function setPasteTarget(t) {
  pasteTarget = t;
  $('#secPost').classList.toggle('paste-on', t === 'post');
  $('#secImg').classList.toggle('paste-on', t === 'comments');
}
$('#secPost').addEventListener('pointerenter', () => setPasteTarget('post'));
$('#secImg').addEventListener('pointerenter', () => setPasteTarget('comments'));
setPasteTarget('comments');

// Route pasted video and image files to the currently active upload target.
function handlePasted(files) {
  const vids = files.filter(isVideo), imgs = files.filter(isImage);
  if (!vids.length && !imgs.length) return false;
  const done = [];
  if (vids.length) { setBg(vids[0]); done.push('video nền'); }
  if (imgs.length) {
    if (pasteTarget === 'post') { setPostImage(imgs[0]); done.push('bài viết chính'); }
    else { const n = addComments(imgs); if (n) done.push(n + ' ảnh comment'); }
  }
  if (done.length) showMsg('Đã dán: ' + done.join(', ') + '.');
  return true;
}
document.addEventListener('paste', e => {
  const files = [...((e.clipboardData && e.clipboardData.files) || [])];
  if (!files.length) return;
  const imgs = files.filter(isImage);
  if (!imgs.length) return;
  if (currentTab === 'video') {
    if (handlePasted(files)) e.preventDefault();
  } else if (currentTab === 'post') {
    e.preventDefault();
    if (pPostImageTarget === 'comment') {
      let index = pPostCommentIndex;
      if (index < 0) {
        if (pComments.length >= MAX_PC) return;
        pComments.push('');
        pCommentImages.push(null);
        index = pComments.length - 1;
        renderPC();
      }
      setCommentPostImage(index, imgs[0]);
    } else {
      setMainPostImage(imgs[0]);
    }
  }
});

// --- tab: Tạo video | Tạo bài viết từ template
let currentTab = 'video';
// Switch between video creation and template-post creation views.
function showTab(t) {
  currentTab = t;
  $('#viewVideo').hidden = t !== 'video';
  $('#viewPost').hidden = t !== 'post';
  document.querySelectorAll('.tab').forEach(b => b.classList.toggle('on', b.dataset.tab === t));
  if (t === 'post') schedulePost(0);
}
document.querySelectorAll('.tab').forEach(b => b.addEventListener('click', () => showTab(b.dataset.tab)));

// --- module tạo bài viết từ template
const MAX_PC = 3;
let pComments = [''];
let pTimer = null, pBlob = null, pUrl = null, pSeq = 0;
let pTemplateId = null;
let pTemplateUrl = null;
let pMainImage = null;
let pMainImageId = null;
let pMainImageUrl = null;
let pCommentImages = [null];
let pPostImageTarget = 'main';
let pPostCommentIndex = 0;

// Read supported plain-text template content from a selected file.
async function readTextFile(file) {
  if (!/\.(txt|md|csv)$/i.test(file.name)) throw new Error('Chỉ hỗ trợ file .txt, .md hoặc .csv.');
  return await file.text();
}

// Paste plain text from the clipboard into the specified input.
async function pasteTextInto(target) {
  if (!navigator.clipboard || !navigator.clipboard.readText) {
    target.focus();
    showPostError('Trình duyệt chưa hỗ trợ dán tự động. Hãy chọn ô rồi bấm Ctrl+V.');
    return;
  }
  try {
    const text = await navigator.clipboard.readText();
    if (!text) { showPostError('Clipboard chưa có văn bản.'); return; }
    target.value = text;
    target.dispatchEvent(new Event('input', {bubbles: true}));
  } catch (e) {
    target.focus();
    showPostError('Không đọc được clipboard. Hãy cho phép quyền truy cập hoặc bấm Ctrl+V.');
  }
}

// Show a template-post validation or upload error.
function showPostError(text) {
  setPStatus(text, true);
}

// Upload an image used by the post-template renderer and return its server id.
async function uploadPostImage(file) {
  if (!file || (!file.type.startsWith('image/') && !isExt(file, /\.(png|jpe?g|webp|bmp)$/i))) {
    throw new Error('Vui lòng chọn file ảnh.');
  }
  const r = await fetch('/api/post-content-image', {
    method: 'POST',
    headers: {'Content-Type': 'application/octet-stream'},
    body: file,
  });
  const data = await r.json();
  if (!r.ok) throw new Error(data.error || 'Không tải được ảnh.');
  return data.id;
}

// Upload and preview the main image used by the template-post renderer.
async function setMainPostImage(file) {
  try {
    setPStatus('Đang tải ảnh bài viết...');
    pMainImageId = await uploadPostImage(file);
    if (pMainImageUrl) URL.revokeObjectURL(pMainImageUrl);
    pMainImageUrl = URL.createObjectURL(file);
    pMainImage = file;
    $('#pMainImageThumb').src = pMainImageUrl;
    $('#pMainImagePreview').hidden = false;
    setPStatus('');
    schedulePost(0);
  } catch (e) { showPostError(String(e.message || e)); }
}

// Upload and preview an image assigned to one comment panel.
async function setCommentPostImage(index, file) {
  try {
    setPStatus('Đang tải ảnh comment...');
    const id = await uploadPostImage(file);
    if (pCommentImages[index] && pCommentImages[index].url) URL.revokeObjectURL(pCommentImages[index].url);
    pCommentImages[index] = {id, url: URL.createObjectURL(file), name: file.name};
    setPStatus('');
    renderPC();
    schedulePost(0);
  } catch (e) { showPostError(String(e.message || e)); }
}

// Paste a clipboard image into the main post or a selected comment panel.
async function pastePostImage(index) {
  if (!navigator.clipboard || !navigator.clipboard.read) {
    showPostError('Trình duyệt chưa hỗ trợ nút dán ảnh. Hãy bấm Ctrl+V sau khi copy ảnh.');
    return;
  }
  try {
    const files = [];
    for (const item of await navigator.clipboard.read()) {
      const type = item.types.find(t => t.startsWith('image/'));
      if (type) files.push(new File([await item.getType(type)], 'dan-' + Date.now() + '.' + type.split('/')[1], {type}));
    }
    if (!files.length) { showPostError('Clipboard chưa có ảnh. Hãy copy/chụp ảnh trước.'); return; }
    if (index === null) await setMainPostImage(files[0]);
    else await setCommentPostImage(index, files[0]);
  } catch (e) { showPostError('Không đọc được clipboard ảnh. Hãy cho phép quyền dán hoặc bấm Ctrl+V.'); }
}

// Upload a custom template and request a new preview.
async function setPostTemplate(file) {
  if (!file || (!file.type.includes('png') && !/\.png$/i.test(file.name))) {
    showPostError('Vui lòng chọn file template PNG.');
    return;
  }
  try {
    setPStatus('Đang tải template...');
    const r = await fetch('/api/post-template', {method: 'POST', headers: {'Content-Type': 'application/octet-stream', 'X-File-Name': encodeURIComponent(file.name)}, body: file});
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || 'Không tải được template.');
    pTemplateId = data.id;
    if (pTemplateUrl) URL.revokeObjectURL(pTemplateUrl);
    pTemplateUrl = URL.createObjectURL(file);
    $('#postTemplateImg').src = pTemplateUrl;
    $('#postTemplateName').textContent = file.name;
    $('#postTemplatePreview').hidden = false;
    $('#dropPostTemplate').hidden = true;
    setPStatus('');
    schedulePost(0);
  } catch (e) {
    showPostError(String(e.message || e));
  }
}

$('#postMainSection').addEventListener('pointerenter', () => { pPostImageTarget = 'main'; });
$('#postCommentSection').addEventListener('pointerenter', () => {
  pPostImageTarget = 'comment';
  if (!pComments.length) pPostCommentIndex = -1;
  else pPostCommentIndex = Math.min(pPostCommentIndex, pComments.length - 1);
});
setupDrop($('#dropPostTemplate'), $('#inPostTemplate'), files => setPostTemplate(files.find(f => isImage(f))));
$('#postTemplateRemove').addEventListener('click', () => {
  pTemplateId = null;
  if (pTemplateUrl) URL.revokeObjectURL(pTemplateUrl);
  pTemplateUrl = null;
  $('#postTemplatePreview').hidden = true;
  $('#dropPostTemplate').hidden = false;
  $('#inPostTemplate').value = '';
  schedulePost(0);
});

// Rebuild the text and image controls for each template comment.
function renderPC() {
  const box = $('#pcList');
  box.innerHTML = '';
  pComments.forEach((t, i) => {
    const row = document.createElement('div');
    row.style.cssText = 'display:grid;grid-template-columns:1fr auto;gap:10px;align-items:start;margin-bottom:10px';
    row.addEventListener('pointerenter', () => {
      pPostImageTarget = 'comment';
      pPostCommentIndex = i;
    });
    const left = document.createElement('div');
    const actions = document.createElement('div');
    actions.className = 'field-actions';
    const paste = document.createElement('button');
    paste.className = 'mini'; paste.type = 'button'; paste.textContent = '📋 Dán văn bản';
    const load = document.createElement('button');
    load.className = 'mini'; load.type = 'button'; load.textContent = '📄 Tải file văn bản';
    const pasteImage = document.createElement('button');
    pasteImage.className = 'mini'; pasteImage.type = 'button'; pasteImage.textContent = '🖼️ Dán ảnh';
    const loadImage = document.createElement('button');
    loadImage.className = 'mini'; loadImage.type = 'button'; loadImage.textContent = '📷 Tải ảnh';
    const input = document.createElement('input');
    input.type = 'file'; input.accept = '.txt,.md,.csv,text/plain,text/markdown,text/csv'; input.hidden = true;
    const imageInput = document.createElement('input');
    imageInput.type = 'file'; imageInput.accept = 'image/*'; imageInput.hidden = true;
    const ta = document.createElement('textarea');
    ta.placeholder = 'Nội dung comment ' + (i + 1) + '...';
    ta.value = t;
    ta.addEventListener('input', () => { pComments[i] = ta.value; schedulePost(); });
    paste.addEventListener('click', () => pasteTextInto(ta));
    load.addEventListener('click', () => input.click());
    pasteImage.addEventListener('click', () => pastePostImage(i));
    loadImage.addEventListener('click', () => imageInput.click());
    input.addEventListener('change', async () => {
      if (!input.files[0]) return;
      try {
        const text = await readTextFile(input.files[0]);
        ta.value = text;
        pComments[i] = text;
        schedulePost();
      } catch (e) { showPostError(String(e.message || e)); }
      input.value = '';
    });
    imageInput.addEventListener('change', async () => {
      if (imageInput.files[0]) await setCommentPostImage(i, imageInput.files[0]);
      imageInput.value = '';
    });
    actions.append(paste, load, pasteImage, loadImage, input, imageInput);
    const preview = document.createElement('div');
    preview.hidden = !pCommentImages[i];
    preview.style.margin = '8px 0';
    const thumb = document.createElement('img');
    thumb.alt = 'Ảnh comment ' + (i + 1);
    thumb.style.cssText = 'max-width:220px;max-height:150px;border-radius:8px;border:1px solid var(--line)';
    if (pCommentImages[i]) thumb.src = pCommentImages[i].url;
    const removeImage = document.createElement('button');
    removeImage.className = 'mini'; removeImage.type = 'button'; removeImage.textContent = 'Xoá ảnh';
    removeImage.style.marginLeft = '8px';
    removeImage.addEventListener('click', () => {
      if (pCommentImages[i] && pCommentImages[i].url) URL.revokeObjectURL(pCommentImages[i].url);
      pCommentImages[i] = null;
      renderPC(); schedulePost();
    });
    preview.append(thumb, removeImage);
    left.append(actions, preview, ta);
    const rm = document.createElement('button');
    rm.className = 'mini'; rm.type = 'button'; rm.textContent = '✕ Xoá'; rm.title = 'Xoá comment này';
    rm.addEventListener('click', () => {
      if (pCommentImages[i] && pCommentImages[i].url) URL.revokeObjectURL(pCommentImages[i].url);
      pComments.splice(i, 1);
      pCommentImages.splice(i, 1);
      renderPC(); schedulePost();
    });
    row.append(left, rm);
    box.appendChild(row);
  });
  if (!pComments.length) {
    const p = document.createElement('p');
    p.style.cssText = 'color:var(--muted);margin:0';
    p.textContent = 'Chưa có comment nào, ảnh chỉ gồm bài viết chính.';
    box.appendChild(p);
  }
  $('#pcAdd').hidden = pComments.length >= MAX_PC;
}
$('#pcAdd').addEventListener('click', () => {
  if (pComments.length < MAX_PC) { pComments.push(''); pCommentImages.push(null); renderPC(); }
});
$('#pMainPaste').addEventListener('click', () => pasteTextInto($('#pMain')));
$('#pMainLoad').addEventListener('click', () => $('#pMainFile').click());
$('#pMainPasteImage').addEventListener('click', () => pastePostImage(null));
$('#pMainLoadImage').addEventListener('click', () => $('#pMainImageFile').click());
$('#pMainImageFile').addEventListener('change', async () => {
  if ($('#pMainImageFile').files[0]) await setMainPostImage($('#pMainImageFile').files[0]);
  $('#pMainImageFile').value = '';
});
$('#pMainImageRemove').addEventListener('click', () => {
  pMainImage = null;
  pMainImageId = null;
  if (pMainImageUrl) URL.revokeObjectURL(pMainImageUrl);
  pMainImageUrl = null;
  $('#pMainImagePreview').hidden = true;
  schedulePost(0);
});
$('#pMainFile').addEventListener('change', async () => {
  const file = $('#pMainFile').files[0];
  if (!file) return;
  try {
    $('#pMain').value = await readTextFile(file);
    $('#pMain').dispatchEvent(new Event('input', {bubbles: true}));
  } catch (e) { showPostError(String(e.message || e)); }
  $('#pMainFile').value = '';
});
$('#pMain').addEventListener('input', () => schedulePost());
$('#pAlign').addEventListener('change', () => schedulePost(0));

// Display a status message in the template-post view.
function setPStatus(text, isErr) { const s = $('#pStatus'); s.textContent = text; s.className = 'msg' + (isErr ? ' err' : ''); }
// Debounce preview requests while the user is editing template content.
function schedulePost(delay) {
  clearTimeout(pTimer);
  pTimer = setTimeout(genPost, delay === undefined ? 600 : delay);
}
// Request and display the current rendered template-post preview.
async function genPost() {
  const main = $('#pMain').value.trim();
  if (!main && !pMainImageId) { setPStatus('Nhập/nạp văn bản hoặc ảnh cho bài viết chính để xem trước.'); return; }
  const seq = ++pSeq;
  setPStatus('Đang tạo ảnh...');
  try {
    const r = await fetch('/api/post-image', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        main,
        comments: pComments.map(s => s.trim()),
        align: $('#pAlign').value,
        template: pTemplateId,
        main_image: pMainImageId,
        comment_images: pCommentImages.map(v => v ? v.id : ''),
      }),
    });
    if (!r.ok) {
      let msg = 'Không tạo được ảnh.';
      try { msg = (await r.json()).error || msg; } catch (e) { /* giữ nguyên thông báo */ }
      throw new Error(msg);
    }
    const blob = await r.blob();
    if (seq !== pSeq) return;            // đã có yêu cầu mới hơn, bỏ kết quả cũ
    pBlob = blob;
    if (pUrl) URL.revokeObjectURL(pUrl);
    pUrl = URL.createObjectURL(blob);
    $('#pPrev').src = pUrl;
    $('#pDl').href = pUrl;
    $('#pOut').hidden = false;
    setPStatus('');
  } catch (e) {
    if (seq === pSeq) setPStatus(String(e.message || e), true);
  }
}
$('#pToVideo').addEventListener('click', () => {
  if (!pBlob) return;
  setPostImage(new File([pBlob], 'bai-viet.png', {type: 'image/png'}));
  showTab('video');
  showMsg('Đã đưa ảnh bài viết vào mục 2. Hãy gõ lời đọc cho bài viết chính (hoặc chọn file audio) rồi bấm Tạo video.');
  $('#secPost').scrollIntoView({behavior: 'smooth'});
});
renderPC();
// Read an image from the clipboard for the selected video upload section.
async function pasteFromButton(target) {
  setPasteTarget(target);
  if (!navigator.clipboard || !navigator.clipboard.read) {
    showMsg('Trình duyệt này chưa hỗ trợ nút dán, hãy bấm Ctrl+V.', true); return;
  }
  try {
    const files = [];
    for (const it of await navigator.clipboard.read()) {
      const type = it.types.find(t => t.startsWith('image/'));
      if (type) files.push(new File([await it.getType(type)], 'image.' + type.split('/')[1], {type}));
    }
    if (!files.length) { showMsg('Clipboard chưa có ảnh. Hãy chụp màn hình hoặc copy ảnh trước.', true); return; }
    handlePasted(files);
  } catch (err) {
    showMsg('Không đọc được clipboard (hãy cho phép quyền dán) hoặc bấm Ctrl+V.', true);
  }
}
$('#pasteImgBtn').addEventListener('click', () => pasteFromButton('comments'));
$('#pastePostBtn').addEventListener('click', () => pasteFromButton('post'));

// --- nhạc nền (tuỳ chọn)
let bgm = null;
// Update the background-music controls for the selected file state.
function syncBgm() {
  $('#bgmInfo').hidden = !bgm;
  $('#bgmOpts').hidden = !bgm;
  $('#dropBgm').hidden = !!bgm;
  if (bgm) $('#bgmName').textContent = 'Nhạc nền: ' + bgm.name + ' (' + mb(bgm.size) + ')';
}
setupDrop($('#dropBgm'), $('#inBgm'), files => {
  const f = files.find(isAudio);
  if (!f) { showMsg('Vui lòng chọn file nhạc (mp3, wav...).', true); return; }
  bgm = f; showMsg(''); syncBgm();
});
$('#bgmRemove').addEventListener('click', () => { bgm = null; syncBgm(); });
$('#bgmVol').addEventListener('input', e => { $('#bgmVolVal').textContent = e.target.value + '%'; });

// --- chế độ giọng đọc
document.querySelectorAll('input[name=mode]').forEach(r => r.addEventListener('change', () => {
  mode = r.value;
  syncPost();
  $('#audioBox').hidden = mode !== 'audio';
  $('#ttsOpts').hidden = mode !== 'tts';
  renderItems();
}));
setupDrop($('#dropAudio'), $('#inAudio'), files => {
  const au = files.filter(isAudio).sort(natCmp);
  if (!au.length) { showMsg('Vui lòng chọn file audio.', true); return; }
  if (!items.length) { showMsg('Hãy thêm ảnh comment trước, rồi mới kéo audio vào.', true); return; }
  au.slice(0, items.length).forEach((f, i) => { items[i].audio = f; });
  if (au.length > items.length) showMsg('Có ' + au.length + ' audio nhưng chỉ ' + items.length + ' ảnh, đã bỏ phần dư.', true);
  else showMsg('');
  renderItems();
});

// --- thanh trượt
$('#rate').addEventListener('input', e => { const v = +e.target.value; $('#rateVal').textContent = (v >= 0 ? '+' : '') + v + '%'; });
$('#dim').addEventListener('input', e => { $('#dimVal').textContent = e.target.value + '%'; });
$('#off').addEventListener('input', e => {
  const v = +e.target.value;
  $('#offVal').textContent = v === 0 ? 'giữa' : (v < 0 ? 'lên ' + (-v) : 'xuống ' + v) + ' px';
});

// --- tiếng hiệu ứng
let sfxFile = null;
// Update visibility of custom effect-sound and volume controls.
function syncSfx() {
  const v = $('#sfx').value;
  $('#sfxBox').hidden = v !== 'custom';
  $('#sfxVolBox').hidden = v === 'none';
}
$('#sfx').addEventListener('change', syncSfx);
$('#sfxVol').addEventListener('input', e => { $('#sfxVolVal').textContent = e.target.value + '%'; });
setupDrop($('#dropSfx'), $('#inSfx'), files => {
  const f = files.find(isAudio);
  if (!f) { showMsg('Vui lòng chọn file âm thanh.', true); return; }
  sfxFile = f;
  $('#sfxName').textContent = 'Đã chọn: ' + f.name;
  $('#sfxName').className = 'audio-tag ok';
  showMsg('');
});

// --- tạo video
// Validate all required video inputs before uploading or starting a job.
function validate() {
  if (!bg) return 'Chưa có video nền.';
  if (items.length < 1) return 'Chưa có ảnh comment.';
  if ($('#sfx').value === 'custom' && !sfxFile) return 'Bạn chọn dùng file tiếng hiệu ứng riêng nhưng chưa kéo file vào.';
  if (post) {
    if (mode === 'tts' && !post.text.trim()) return 'Bài viết chính chưa có lời đọc.';
    if (mode === 'audio' && !post.audio) return 'Bài viết chính chưa có file audio.';
  }
  if (mode === 'tts') {
    const i = items.findIndex(it => !it.text.trim());
    if (i >= 0) return 'Comment số ' + (i + 1) + ' chưa có lời đọc.';
  } else {
    const i = items.findIndex(it => !it.audio);
    if (i >= 0) return 'Comment số ' + (i + 1) + ' chưa có file audio.';
  }
  return '';
}

// Upload one input file to the active server-side video job.
async function upload(job, kind, idx, file) {
  const url = `/api/upload?job=${job}&kind=${kind}&idx=${idx}&name=${encodeURIComponent(file.name)}`;
  const r = await fetch(url, {method: 'POST', body: file});
  if (!r.ok) throw new Error('Tải ' + file.name + ' lên thất bại');
}

// Upload selected inputs and start video rendering with current settings.
async function generate() {
  const err = validate();
  if (err) { showMsg(err, true); return; }
  const go = $('#go'); go.disabled = true;
  $('#result').hidden = true;
  const log = $('#log'); log.hidden = true; log.textContent = '';
  showMsg('Đang nạp file...');
  try {
    const {job} = await (await fetch('/api/new', {method: 'POST'})).json();
    await upload(job, 'bg', 0, bg);
    if ($('#sfx').value === 'custom') await upload(job, 'sfx', 0, sfxFile);
    if (post) {
      await upload(job, 'post', 0, post.file);
      if (mode === 'audio') await upload(job, 'postaudio', 0, post.audio);
    }
    if (bgm) await upload(job, 'bgm', 0, bgm);
    for (let i = 0; i < items.length; i++) {
      await upload(job, 'img', i, items[i].file);
      if (mode === 'audio') await upload(job, 'audio', i, items[i].audio);
    }
    const opts = {
      mode, count: items.length,
      texts: items.map(it => it.text.trim()),
      voice: $('#voice').value,
      engine: $('#engine').value,
      rate: (+$('#rate').value >= 0 ? '+' : '') + $('#rate').value + '%',
      dim: +$('#dim').value / 100,
      offset_y: +$('#off').value,
      size: $('#size').value,
      sfx: $('#sfx').value,
      sfx_volume: +$('#sfxVol').value / 100,
      post: !!post,
      post_text: post ? post.text.trim() : '',
      bgm: !!bgm,
      bgm_volume: +$('#bgmVol').value / 100,
      bgm_duck: $('#bgmDuck').checked,
    };
    const r = await fetch('/api/run?job=' + job, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(opts)});
    if (!r.ok) throw new Error((await r.json()).error || 'Không chạy được');
    showMsg('Đang tạo video, vui lòng đợi...');
    log.hidden = false;
    poll(job);
  } catch (e) {
    showMsg(String(e.message || e), true);
    go.disabled = false;
  }
}

// Poll job status and update progress or show the finished video.
async function poll(job) {
  try {
    const s = await (await fetch('/api/status?job=' + job)).json();
    const log = $('#log');
    log.textContent = s.log.join('\n');
    log.scrollTop = log.scrollHeight;
    if (s.state === 'running') { setTimeout(() => poll(job), 1000); return; }
    $('#go').disabled = false;
    if (s.state === 'done') {
      showMsg('Hoàn thành!');
      $('#outVideo').src = '/result/' + job + '?t=' + Date.now();
      $('#dl').href = '/result/' + job;
      $('#result').hidden = false;
      $('#result').scrollIntoView({behavior: 'smooth'});
    } else {
      showMsg('Có lỗi, xem chi tiết ở khung bên dưới.', true);
    }
  } catch (e) {
    showMsg('Mất kết nối với tool. Hãy kiểm tra cửa sổ lệnh còn chạy không.', true);
    $('#go').disabled = false;
  }
}
$('#go').addEventListener('click', generate);
