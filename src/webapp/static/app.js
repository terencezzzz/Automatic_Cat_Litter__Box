/* Local PawLog preview with vision visit history. */
'use strict';
const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const icon = name => `<svg class="icon" aria-hidden="true"><use href="#i-${name}"/></svg>`;
const asset = name => `/static/assets/${name}`;
const photo = asset('demo-litter-box.png');
const pill = (label, type = 'neutral', symbol = '') => `<span class="pill ${type}">${symbol ? icon(symbol) : ''}${escapeHtml(label)}</span>`;
const arrowLink = (label, href) => `<a class="text-link" href="${href}">${escapeHtml(label)}${icon('arrow')}</a>`;
const names = {overview:'Overview',camera:'Camera',history:'History',detail:'Observation',cleaning:'Cleaning',cats:'My Cats',notifications:'Notifications',settings:'Settings'};
const defaultCameraIp = 'pawlog-cam.local';
const cameraIpStorageKey = 'pawlog.cameraIp';
function loadCameraIp() {
  try {
    const saved = localStorage.getItem(cameraIpStorageKey);
    if (saved && validCameraIp(saved)) return saved;
  } catch {}
  return defaultCameraIp;
}
function saveCameraIp(value) {
  try {
    localStorage.setItem(cameraIpStorageKey, value);
    return true;
  } catch {
    return false;
  }
}
const defaultSettings = () => ({cameraIp:defaultCameraIp,streamOverride:'',port:'COM3',model:'Visual model (not connected)',monitor:false,cloud:false,notifications:true});
const historyCategories = [
  {name:'Box visit', icon:'paw'}, {name:'Manual photo', icon:'camera'},
];
const boxStatuses = [
  {name:'In use', tone:'blue'}, {name:'Needs cleaning', tone:'amber'}, {name:'Available', tone:'green'},
];
const defaultFilters = () => ({date:'', cat:'', category:'', query:''});
const state = {
  cats: [
    {id:'mochi',name:'Mochi',age:2,breed:'Brown & white tabby',photo:asset('mochi.jpg')},
    {id:'luna',name:'Luna',age:3,breed:'British Shorthair',photo:asset('luna.jpg')},
  ],
  events: [
    {id:'sample-1',time:'10:42 AM',date:'2026-11-08',kind:'Manual photo',catId:'',status:'Review image'},
    {id:'sample-2',time:'9:18 AM',date:'2026-11-08',kind:'Box visit',catId:'',status:'Review image'},
    {id:'sample-3',time:'8:05 AM',date:'2026-11-08',kind:'Box visit',catId:'luna',status:'Pending'},
    {id:'sample-4',time:'7:21 AM',date:'2026-11-08',kind:'Box visit',catId:'',status:'Failed'},
    {id:'sample-5',time:'5:03 PM',date:'2026-11-07',kind:'Box visit',catId:'mochi',status:'Review image'},
  ],
  filters:defaultFilters(), sortAscending:false, selectedRecordId:'',
  boxes:[{id:1, status:0}], cameraStream:null, cameraError:'',
  analysisTimer:null, simTimer:null, simStage:'idle', commands:[],
  read:false, notificationFilter:'all', settings:{...defaultSettings(),cameraIp:loadCameraIp()},
};
const catById = id => state.cats.find(cat => cat.id === id);
const catName = id => catById(id)?.name || 'Unassigned';
const catOptions = (selected = '', all = false) => `${all ? '<option value="">All cats</option><option value="unassigned">Unassigned</option>' : '<option value="">Unassigned</option>'}${state.cats.map(cat=>`<option value="${escapeHtml(cat.id)}" ${selected===cat.id?'selected':''}>${escapeHtml(cat.name)}</option>`).join('')}`;
const catAvatar = cat => cat?.photo ? `<img src="${escapeHtml(cat.photo)}" alt="${escapeHtml(cat.name)}" width="40" height="40">` : `<span class="observation-icon">${icon('cat')}</span>`;
const heading = (title, subtitle = '', actions = '') => `<div class="page-heading"><div><h1>${title}</h1>${subtitle ? `<p>${subtitle}</p>` : ''}</div>${actions ? `<div class="heading-actions">${actions}</div>` : ''}</div>`;
const viewPhotosButton = () => `<a class="button" href="#history">${icon('camera')}View photos</a>`;
const snapshot = (className = '') => `<div class="snapshot ${className}"><img src="${photo}" alt="Gray tabby beside a clean litter tray" width="1536" height="1024"><span class="sample-label">Sample image</span></div>`;
const empty = (title, description) => `<div class="empty-state">${icon('cat')}<h2>${title}</h2><p>${description}</p></div>`;
function toast(message) {
  const element = $('#toast');
  clearTimeout(toast.timer);
  element.textContent = message;
  element.hidden = false;
  toast.timer = setTimeout(() => { element.hidden = true; }, 5000);
}
function overview() {
  const visits = state.events.filter(event => event.kind === 'Box visit' && event.date==='2026-11-08');
  return `${heading('Overview', '', viewPhotosButton())}
  <div class="dashboard-grid">
    <div class="stack">
      <article class="panel snapshot-panel">
        <div class="panel-heading"><h2>Latest sample photo</h2>${arrowLink('Open camera','#camera')}</div>
        ${snapshot()}
        <div class="snapshot-meta"><span>${icon('clock')}Nov 8 · 10:42 AM</span><span>Manual photo</span></div>
        <div class="snapshot-result"><p>No stool visible in this sample.</p>${arrowLink('View observation','#detail/sample-1')}</div>
      </article>
      <article class="panel"><div class="panel-heading"><h2>Recent visits</h2>${arrowLink('History','#history')}</div>${visits.map(event=>`<a class="visit-row" href="#detail/${event.id}">${catAvatar(catById(event.catId))}<div><strong>${escapeHtml(catName(event.catId))}</strong><small>Box visit · Sample</small></div><time>${event.time}</time>${icon('chevron')}</a>`).join('')}</article>
    </div>
    <div class="dashboard-side">
      <article class="panel status-panel"><div class="panel-heading"><h2>Device status</h2></div><dl class="status-list"><div class="status-row">${icon('camera')}<dt>Camera</dt><dd>${state.cameraError ? pill('Connection failed','amber') : pill('Open Camera to view')}</dd></div><div class="status-row">${icon('cat')}<dt>Cat presence</dt><dd>${pill('Unknown','amber')}</dd></div><div class="status-row">${icon('clean')}<dt>Motor</dt><dd>${pill('Locked','amber','lock')}</dd></div></dl>${arrowLink('Check device connection','#settings')}</article>
      <article class="panel"><div class="panel-heading"><h2>My Cats</h2>${arrowLink('View cats','#cats')}</div><div class="cat-chips">${state.cats.slice(0,2).map(cat=>`<a class="cat-chip" href="#cats">${catAvatar(cat)}<span><strong>${escapeHtml(cat.name)}</strong><small>${escapeHtml(cat.age)} years old</small></span></a>`).join('')}</div></article>
    </div>
  </div><div id="box-overview">${boxOverview()}</div>`;
}
function camera() {
  const urls = cameraEndpoints(state.settings);
  const stream = state.cameraStream;
  const status = stream ? (stream.ready ? 'Live' : 'Connecting…') : state.cameraError;
  return `${heading('Camera','',viewPhotosButton())}<div class="split-layout">
    <article class="panel">
      <div class="panel-heading"><h2>Live camera</h2></div>
      <div class="camera-view">${stream
        ? `<div id="camera-stream"></div>`
        : `<div class="offline-view">${icon('camera')}<h3>Stream is off</h3></div>`}</div>
      <p class="fine" id="camera-status" role="status">${escapeHtml(status)}</p>
      <div class="action-row">
        <button class="button" data-action="toggle-stream">${stream?'Stop live stream':'Start live stream'}</button>
        <a class="button secondary" href="${escapeHtml(urls.home)}" target="_blank" rel="noopener noreferrer">Open camera</a>
        <a class="text-link" href="${escapeHtml(urls.stream)}" target="_blank" rel="noopener noreferrer">Open stream in new tab</a>
      </div>
    </article>
    <article class="panel">
      <h2>Camera connection</h2>
      <p class="fine">${escapeHtml(state.settings.cameraIp)}</p>
      <p class="fine">Join the same Wi-Fi or hotspot as the camera. If prompted, allow local network access.</p>
      ${arrowLink('Camera settings','#settings')}
    </article>
  </div>`;
}

function stopCameraStream() {
  const stream = state.cameraStream;
  if (!stream) return;
  clearInterval(stream.frameCheck);
  stream.image.onerror = null;
  stream.image.removeAttribute('src');
  state.cameraStream = null;
}

function startCameraStream() {
  const url = new URL(cameraEndpoints(state.settings).stream);
  url.searchParams.set('_', Date.now());
  const image = new Image();
  image.className = 'live-camera-frame';
  image.alt = 'Live view from your ESP32-CAM';
  const stream = {image, ready:false, frameCheck:null};
  state.cameraStream = stream;
  state.cameraError = '';

  const fail = () => {
    stopCameraStream();
    state.cameraError = 'Could not play the stream. Check the Wi-Fi and local network permission, or open the stream in a new tab.';
    if (currentRoute().page === 'camera') render();
  };
  const deadline = Date.now() + 12000;
  image.onerror = fail;
  // An MJPEG response stays open, so check for the first decoded frame.
  stream.frameCheck = setInterval(() => {
    if (image.naturalWidth > 0) {
      clearInterval(stream.frameCheck);
      stream.ready = true;
      $('#camera-status').textContent = 'Live';
    } else if (Date.now() >= deadline) {
      fail();
    }
  }, 250);

  render();
  image.src = url.href;
}

let visionVisits = [];
let visitStatus = 'Checking for camera visits…';

async function refreshVisionVisits() {
  try {
    const response = await fetch('/api/vision-visits', {cache:'no-store', signal:AbortSignal.timeout(4000)});
    if (!response.ok) throw new Error('Visit request failed');
    const records = await response.json();
    const previousIds = visionVisits.map(event => event.id).join(',');
    visionVisits = records.map(record => {
      const captured = new Date(record.capturedAt);
      return {
        id:record.id, real:true, catId:'', kind:'Box visit',
        date:captured.toLocaleDateString('sv-SE',{timeZone:'Asia/Kuala_Lumpur'}),
        time:captured.toLocaleTimeString('en-US',{timeZone:'Asia/Kuala_Lumpur',hour:'numeric',minute:'2-digit'}),
        timestamp:captured.getTime(),
        status:record.wasteDetected?'Waste detected':'No waste detected',
      };
    });
    visitStatus = visionVisits.length ? '' : 'Waiting for the first completed camera visit.';
    if (currentRoute().page === 'history') {
      $('#vision-status').textContent = visitStatus;
      if (previousIds !== visionVisits.map(event => event.id).join(',')) refreshHistory();
    } else if (currentRoute().page === 'detail' && previousIds !== visionVisits.map(event => event.id).join(',')) {
      render();
    }
  } catch {
    visitStatus = 'Could not read camera visits. Retrying…';
    if (currentRoute().page === 'history') $('#vision-status').textContent = visitStatus;
  }
}

const visitImage = (event, file) => `/visit-image/${encodeURIComponent(event.id)}/${file}`;

function matchingHistoryEvents() {
  const {date, cat, query} = state.filters;
  const keyword = query.trim().toLowerCase();
  return visionVisits.filter(event =>
    (!date || event.date === date) &&
    (!cat || (cat === 'unassigned' ? !event.catId : event.catId === cat)) &&
    [catName(event.catId), event.kind, event.status, event.date, event.time, event.id]
      .some(value => value.toLowerCase().includes(keyword))
  );
}
function eventTimestamp(event) {
  if (event.real) return event.timestamp;
  const [hour, minute, period] = event.time.split(/[: ]/);
  const hour24 = Number(hour) % 12 + (period === 'PM' ? 12 : 0);
  return Date.parse(event.date) + (hour24 * 60 + Number(minute)) * 60_000;
}
function historyResults() {
  const {category} = state.filters;
  const matches = matchingHistoryEvents();
  const events = matches.filter(event => !category || event.kind === category);
  const direction = state.sortAscending ? 1 : -1;
  events.sort((first, second) => direction * (eventTimestamp(first) - eventTimestamp(second)));
  const selected = events.find(event => event.id === state.selectedRecordId) || events[0];
  state.selectedRecordId = selected?.id || '';

  return `<div class="history-workspace">
    <section class="panel" aria-label="History results">
      <div class="history-categories" role="group" aria-label="Record category">
        ${historyCategories.map(item => `<button type="button" class="button secondary category-filter" data-action="history-category" data-category="${item.name}" aria-pressed="${category === item.name}">${icon(item.icon)}${item.name}<strong>${matches.filter(event => event.kind === item.name).length}</strong></button>`).join('')}
      </div>
      <p class="history-count" role="status">${events.length} ${events.length === 1 ? 'record' : 'records'}</p>
      ${events.length ? `<table class="history-table"><thead><tr>
        <th scope="col" aria-sort="${state.sortAscending ? 'ascending' : 'descending'}"><button class="text-link" type="button" data-action="history-sort">Capture time <span aria-hidden="true">${state.sortAscending ? '↑' : '↓'}</span></button></th>
        <th scope="col">Cat</th><th scope="col" class="type-column">Event</th><th scope="col">Observation</th>
      </tr></thead><tbody>${events.map(event => {
        const active = event.id === selected.id;
        return `<tr class="${active ? 'selected-record' : ''}" data-history-row="${event.id}">
          <td><button class="record-time history-record" type="button" data-action="history-record" data-id="${event.id}" aria-pressed="${active}"><img src="${visitImage(event,'cat.jpg')}" alt="" width="65" height="46"><span><strong>${event.time}</strong><small>${event.date}</small></span></button></td>
          <td>${escapeHtml(catName(event.catId))}</td><td class="type-column">${event.kind}</td>
          <td>${pill(event.status, event.status === 'Failed' ? 'red' : event.status === 'Pending' ? 'neutral' : 'amber')}</td>
        </tr>`;
      }).join('')}</tbody></table>` : empty('No records found', visionVisits.length ? 'Try another search or filter.' : 'Completed camera visits will appear here automatically.')}
    </section>
    <aside class="panel history-detail" aria-labelledby="history-detail-title">
      <h2 id="history-detail-title">Record details</h2>
      <div id="history-selected">${selected ? historyRecordDetails(selected) : '<p class="fine">No record selected.</p>'}</div>
    </aside>
  </div>`;
}
function historyRecordDetails(event) {
  const portrait = visitImage(event,'cat.jpg');
  return `<div class="snapshot"><img src="${escapeHtml(portrait)}" alt="Cat visit from your camera"></div>
    <h3>${escapeHtml(catName(event.catId))}</h3>
    <dl class="status-list">
      <div class="status-row"><dt>Captured</dt><dd>${event.date} · ${event.time}</dd></div>
      <div class="status-row"><dt>Event</dt><dd>${event.kind}</dd></div>
      <div class="status-row"><dt>Observation</dt><dd>${event.status}</dd></div>
    </dl>
    ${arrowLink('Open full record', '#detail/' + event.id)}`;
}
function history() {
  const {date, cat, query} = state.filters;
  return `${heading('History')}<p class="fine" id="vision-status" role="status">${escapeHtml(visitStatus)}</p><form id="history-filter" class="panel filter-bar">
    <label>Search records<input type="search" name="query" value="${escapeHtml(query)}" placeholder="Cat, event or status"></label>
    <button class="text-link" type="button" data-action="clear-history-search">Clear search</button>
    <label>Date (Malaysia time)<input type="date" name="date" value="${escapeHtml(date)}"></label>
    <label>Cat<select name="cat">${catOptions(cat,true)}</select></label>
    <button class="text-link" type="button" data-action="reset-filters">Reset filters</button>
  </form><div id="history-results">${historyResults()}</div>`;
}
function refreshHistory(focusSelector) {
  $('#history-results').innerHTML = historyResults();
  if (focusSelector) $(focusSelector)?.focus({preventScroll:true});
}
function boxOverview() {
  return `<section class="panel spaced" aria-labelledby="box-title">
    <div class="panel-heading"><h2 id="box-title">Litter box</h2>${pill('Demo')}</div>
    <dl class="box-counts">
      <div><dt>Total</dt><dd>${state.boxes.length}</dd></div>
      ${boxStatuses.map((status, index) => `<div><dt>${status.name}</dt><dd>${state.boxes.filter(box => box.status === index).length}</dd></div>`).join('')}
    </dl>
    ${state.boxes.map(box => {
      const current = boxStatuses[box.status];
      const next = boxStatuses[(box.status + 1) % boxStatuses.length];
      return `<button type="button" class="box-row" data-action="cycle-box" data-id="${box.id}" aria-label="Litter box: ${current.name}. Set ${next.name}"><strong>Litter box</strong>${pill(current.name, current.tone)}${icon('arrow')}</button>`;
    }).join('')}
  </section>`;
}
function visitPhotos(event) {
  if(event.kind!=='Box visit') return `<div class="callout">${icon('cat')}<p>Cat photos are saved for box visits. ${arrowLink('Explore a sample visit','#detail/sample-2')}</p></div>`;
  // One sample portrait is reused with different presentation styles, not real captured frames.
  event.visitPhoto ||= catById(event.catId)?.photo || asset('mochi.jpg');
  event.coverFrame ??= 1;
  const frames=['Partial view','Full body','Less clear'];
  const selected=event.coverFrame;
  return `<article class="panel visit-photo-panel"><div class="panel-heading"><h2>Visit photos</h2>${pill('3 sample frames','blue')}</div><ol class="selection-flow"><li>Collect visit photos</li><li>AI suggests a cover</li><li>You confirm the cat</li></ol><div class="cover-preview"><div class="selected-cat-photo frame-${selected}"><img src="${escapeHtml(event.visitPhoto)}" alt="Selected sample cat photo, ${frames[selected].toLowerCase()}"><span class="sample-label">Demo image</span></div><div class="cover-explanation"><span>${pill(event.selecting?'Choosing…':event.manualCover?'Your cover choice':'Suggested cover · Demo',event.manualCover?'blue':'green')}</span><h3>${event.selecting?'Choosing a sample frame…':`Frame 0${selected+1} · ${frames[selected]}`}</h3> ${!event.selecting && selected===1?'<p>Full body and markings visible.</p>':''}<button class="button secondary" data-action="pick-cover" data-id="${event.id}" ${event.selecting?'disabled aria-busy="true"':''}>${icon('clean')}${event.selecting?'Selecting…':'Preview AI pick'}</button><p class="fine">Confirm the cat under Cat assignment.</p></div></div><div class="visit-filmstrip" aria-label="All cat photos from this sample visit">${frames.map((label,index)=>`<button class="visit-frame" data-action="choose-cover" data-id="${event.id}" data-frame="${index}" aria-pressed="${selected===index}" aria-label="Use frame 0${index+1}: ${label}" ${event.selecting?'disabled':''}><span class="frame-image frame-${index}"><img src="${escapeHtml(event.visitPhoto)}" alt=""></span><span><strong>Frame 0${index+1}</strong><small>${label}${selected===index?' · Cover':''}</small></span></button>`).join('')}</div><p class="fine no-margin spaced">These frames use different crops and effects from one sample photo.</p></article>`;
}
function detail(identifier) {
  const event=visionVisits.find(item=>item.id===identifier) || state.events.find(item=>item.id===identifier);
  if(event?.real) {
    const images = [
      ['Cat visit','cat.jpg'],
      ['After the visit','waste-original.png'],
      ['Waste detection','detection.jpg'],
    ];
    return `${arrowLink('Back to History','#history')}${heading('Camera visit',`${event.date} · ${event.time} MYT`)}
      <p>${pill(event.status)}</p><div class="split-layout">${images.map(([label,file])=>`
        <article class="panel"><h2>${label}</h2><div class="snapshot"><img src="${visitImage(event,file)}" alt="${label}"></div></article>
      `).join('')}</div>`;
  }
  if(!event) return `${heading('Record not found')}${arrowLink('Back to History','#history')}`;
  const pending=event.status==='Pending' || event.status==='Analyzing';
  const failed=event.status==='Failed';
  return `<a class="back-link" href="#history">${icon('arrow')}Back to History</a>${heading('Photo details','Sample photo observation · Nov '+event.date.slice(-2)+', '+event.time,`<button class="button secondary" data-action="retry" data-id="${event.id}" ${pending?'disabled':''}>${icon('clean')}${pending?'Analysis pending':'Preview analysis again'}</button>`)}<div class="split-layout"><div class="stack">${visitPhotos(event)}<article class="panel"><div class="panel-heading"><h2>Litter box photos</h2>${pill('Demo image')}</div><div class="detail-pictures"><div><h3>Original image</h3>${snapshot()}</div><div><h3>Detection image</h3><div class="detection-placeholder">${icon('camera')}No detection output.<br>Detector not connected.</div></div></div><div class="snapshot-meta"><span>${event.kind} · Sample record</span><span>No inference performed</span></div></article><article class="panel"><div class="panel-heading"><h2>Photo observation</h2>${pill(event.status,failed?'red':'amber')}</div>${pending?`<div class="callout">${icon('clock')}<p>Simulated analysis pending.<br><button class="text-link" data-action="finish-analysis" data-id="${event.id}">Show sample result ${icon('arrow')}</button></p></div>`:failed?`<div class="callout red">${icon('info')}<p>Sample analysis failed. The original photo is above.</p></div>`:`<div class="observation-intro"><span class="observation-icon">${icon('clean')}</span><div><h3>No visible stool in this sample.</h3></div></div><dl class="detail-observations"><div><dt>Observed color</dt><dd>Unable to assess</dd></div><div><dt>Observed shape</dt><dd>Unable to assess</dd></div><div><dt>Visible changes</dt><dd>Unable to assess</dd></div><div><dt>Image limitations</dt><dd>Generated sample image</dd></div></dl><div class="callout spaced">${icon('info')}<p><strong>Care guidance</strong><br>Contact your vet if you are concerned about your cat.</p></div>`}<p class="detail-disclaimer">Photo observations are not a diagnosis.</p></article></div><div class="stack"><article class="panel"><h2>Cat assignment</h2>${event.kind==='Box visit'?`<div class="identity-photo"><img src="${escapeHtml(event.visitPhoto)}" class="identity-frame-${event.coverFrame}" alt="Sample cover to help you identify the visiting cat"></div><p class="fine">${event.manualCover?'Your chosen':'Suggested'} cover · Frame 0${event.coverFrame+1} · Demo</p>`:''}<form id="assign-form" data-id="${event.id}" class="form-stack"><label>Assign to a cat<select name="cat">${catOptions(event.catId)}</select></label><button class="button" type="submit">Save assignment</button></form><p class="fine spaced">Changes reset on reload.</p></article></div></div>`;
}
function cats() {
  return `${heading('My Cats','',`<button class="button" data-action="add-cat">${icon('plus')}Add a cat</button>`)}<div class="cat-grid">${state.cats.map((cat,index)=>`<article class="panel cat-profile"><div class="cat-cover ${index%2?'luna':''}">${icon('paw')}<img class="cat-avatar" src="${escapeHtml(cat.photo)}" alt="${escapeHtml(cat.name)}'s sample portrait" width="83" height="83"></div><div class="cat-profile-body"><div class="cat-title"><h2>${escapeHtml(cat.name)}</h2>${pill('Sample profile')}</div><p>${escapeHtml(cat.breed||'Breed not set')}</p><dl class="cat-facts"><div><dt>Age</dt><dd>${escapeHtml(cat.age)} years old</dd></div><div><dt>Assigned records</dt><dd>${state.events.filter(event=>event.catId===cat.id).length} sample records</dd></div></dl><div class="cat-card-bottom"><button class="text-link" data-action="cat-history" data-id="${escapeHtml(cat.id)}">View history ${icon('arrow')}</button><button class="icon-button" data-action="edit-cat" data-id="${escapeHtml(cat.id)}" aria-label="Edit ${escapeHtml(cat.name)}">${icon('edit')}</button></div></div></article>`).join('')}<button class="panel cat-add" data-action="add-cat">${icon('cat')}<span class="text-link">${icon('plus')}Add a cat</span></button></div>`;
}
function cleaning() {
  const stages=['Queued','Running','Completed'];
  const active={queued:0,running:1,completed:2}[state.simStage];
  const simText={idle:'Ready to preview. No physical motor movement.',queued:'Sample request queued. Checking simulated conditions…',running:'Sample cycle running. No startup command was sent.',completed:'Sample cycle completed. No real cleaning was performed.',stopped:'Simulation stopped. Real motor state is unknown.',failed:'Sample request rejected: the selected condition is not clear.'}[state.simStage];
  return `${heading('Cleaning')}<div class="panel cleaning-lock"><span class="lock-symbol">${icon('lock')}</span><div>${pill('Real cleaning locked','amber','lock')}<h2>Hardware testing in progress</h2><div class="cleaning-controls" role="group" aria-label="Cleaning controls"><button class="button" disabled>${icon('lock')}Start cleaning</button><button class="button danger" data-action="stop">${icon('stop')}Simulate stop request</button></div></div></div><div class="split-layout spaced"><article class="panel"><div class="panel-heading"><h2>Cleaning simulation</h2>${pill('Simulation only','blue')}</div><label>Simulated conditions<select id="scenario" ${['queued','running'].includes(state.simStage)?'disabled':''}><option value="clear">All conditions clear</option><option value="cat">Cat detected</option><option value="unknown">Vision unknown / expired</option><option value="sensor">Sensor unavailable</option><option value="offline">Communication lost</option></select></label><div class="simulation-track">${stages.map((stage,index)=>`<div class="simulation-step ${active!==undefined&&index<=active?'active':''}"><span>${active!==undefined&&index<active?icon('check'):index+1}</span>${stage}</div>`).join('')}</div><p class="simulation-state" role="status">${simText}</p><div class="action-row"><button class="button secondary" data-action="simulate" ${['queued','running'].includes(state.simStage)?'disabled':''}>${icon('clean')}Run simulation</button><button class="text-link" data-action="hazard" ${['queued','running'].includes(state.simStage)?'':'disabled'}>Simulate interruption</button></div></article><article class="panel"><h2>Hardware checks required</h2><div class="checklist"><div>${icon('clock')}Home / end position feedback</div><div>${icon('clock')}Return-to-home behavior</div><div>${icon('clock')}Jam detection and stopping</div><div>${icon('clock')}Physical stop mechanism</div><div>${icon('clock')}Assembled hardware validation</div></div><div class="callout amber">${icon('info')}<p>Confirm the motor has stopped on the device.</p></div></article></div><article class="panel spaced"><div class="panel-heading"><h2>Control activity</h2>${pill('Preview session')}</div>${state.commands.length?state.commands.map(command=>`<div class="command-row">${icon(command.action==='stop'?'stop':'clean')}<div><strong>${escapeHtml(command.title)}</strong><small>${escapeHtml(command.reason)} · ${escapeHtml(command.time)}</small></div>${pill(command.status,command.status==='Rejected'?'red':'neutral')}</div>`).join(''):empty('No control activity','Run a simulation to see it here.')}</article>`;
}
function notifications() {
  const records=[{type:'observation',icon:'clean',title:'A photo is ready for a closer look',text:'Sample observation: no visible stool. Review the image and assign it to a cat.',time:'10:42 AM · Sample',href:'#detail/sample-1',unread:true},{type:'system',icon:'wifi',title:'Camera connection needs attention',text:'Example device notice. This preview is not connected to your camera.',time:'10:30 AM · Sample',unread:true},{type:'system',icon:'shield',title:'Real cleaning is locked',text:'Physical motor controls stay unavailable while the mechanism is being validated.',time:'9:00 AM · Sample'}].filter(record=>state.notificationFilter==='all'||record.type===state.notificationFilter);
  return `${heading('Notifications','',`<button class="button secondary" data-action="mark-read">${icon('check')}${state.read?'All read':'Mark all as read'}</button>`)}<article class="panel"><div class="segmented" aria-label="Notification filter">${[['all','All'],['observation','Observations'],['system','Devices']].map(([value,label])=>`<button data-notification-filter="${value}" aria-pressed="${state.notificationFilter===value}">${label}</button>`).join('')}</div>${records.map(record=>`<div class="notification-row ${!state.read&&record.unread?'unread':''}"><span class="notification-icon">${icon(record.icon)}</span><div><h3>${record.title}</h3><p>${record.text}</p><time>${record.time}</time>${record.href?`<br>${arrowLink('View observation',record.href)}`:''}</div></div>`).join('')}</article>`;
}
function validCameraIp(value) {
  if (/^(?=.{1,63}\.local$)[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.local$/i.test(value.trim())) return true;
  const parts=value.trim().split('.');
  return parts.length===4&&parts.every(part=>/^(0|[1-9]\d{0,2})$/.test(part)&&Number(part)<=255);
}
function cameraEndpoints(config) {
  const valid=validCameraIp(config.cameraIp);
  return {
    home:valid?`http://${config.cameraIp.trim()}/`:'',
    stream:config.streamOverride.trim()||(valid?`http://${config.cameraIp.trim()}:81/stream`:''),
  };
}
function cameraConnectionFields(config) {
  const urls=cameraEndpoints(config);
  return `<label>Camera address<input name="cameraIp" value="${escapeHtml(config.cameraIp)}" placeholder="${defaultCameraIp}" required maxlength="69" autocomplete="off" spellcheck="false"></label><dl class="camera-endpoints"><div><dt>Live stream URL <span id="stream-source">${config.streamOverride?'Custom override':'Automatic'}</span></dt><dd><output id="stream-preview">${escapeHtml(urls.stream)||'Enter a valid Camera address'}</output></dd></div></dl><details class="camera-advanced" ${config.streamOverride?'open':''}><summary>Advanced settings</summary><div class="form-stack"><p class="fine no-margin">Custom URLs stay fixed when you change the Camera address.</p><label>Live stream URL override<input name="streamOverride" type="url" value="${escapeHtml(config.streamOverride)}" placeholder="Automatic: port 81 /stream" maxlength="300" spellcheck="false"><small>Leave blank to use the automatic URL.</small></label><button class="text-link" data-action="automatic-camera-urls" type="button">Use automatic URLs ${icon('arrow')}</button></div></details>`;
}
function syncCameraFields(form) {
  const config={cameraIp:form.elements.cameraIp.value,streamOverride:form.elements.streamOverride.value};
  const urls=cameraEndpoints(config);
  $('#stream-preview').textContent=urls.stream||'Enter a valid Camera address';
  $('#stream-source').textContent=config.streamOverride.trim()?'Custom override':'Automatic';
}
function settings() {
  const config=state.settings;
  return `${heading('Settings')}<div class="settings-layout"><form id="settings-form" class="panel"><section class="settings-section"><h2>Device connections</h2><div class="form-stack">${cameraConnectionFields(config)}<label>Arduino port<input name="port" value="${escapeHtml(config.port)}" maxlength="20" placeholder="COM3"></label></div><label class="setting-toggle"><span>Automatic visit observation</span><input name="monitor" type="checkbox" ${config.monitor?'checked':''}></label></section><section class="settings-section"><h3>Photo observations</h3><label class="setting-toggle"><span>Cloud AI analysis<small>Sends photos to the AI service when connected.</small></span><input name="cloud" type="checkbox" ${config.cloud?'checked':''}></label><div class="key-status">${icon('lock')}API key not configured</div><label class="spaced">Visual model<input value="${escapeHtml(config.model)}" disabled></label></section><section class="settings-section"><h3>Notifications</h3><label class="setting-toggle"><span>In-app notifications</span><input name="notifications" type="checkbox" ${config.notifications?'checked':''}></label></section><div class="action-row"><button class="button" type="submit">Save preview settings</button><button class="text-link" type="button" data-action="reset-settings">Reset</button></div><p class="fine spaced no-margin">Camera address is saved in this browser. Other settings apply to this tab.</p></form><div class="stack"><article class="panel"><h2>Account</h2><div class="cat-chip"><span class="owner-avatar">Y</span><span><strong>Cat parent</strong><small>Single-owner account</small></span></div><button class="button secondary" data-action="account-info">Account settings</button></article><article class="panel"><h2>Remote access</h2><div class="key-status">${icon('shield')}Not configured</div></article><article class="panel"><h2>About this preview</h2><p class="fine">Sample records only</p><button class="text-link" data-action="reset-demo">Reset demo session ${icon('arrow')}</button></article></div></div>`;
}
function currentRoute() {
  const parts=location.hash.slice(1).split('/');
  return {page:names[parts[0]]?parts[0]:'overview',id:parts[1]||'sample-1'};
}
function render(moveFocus=false) {
  const route=currentRoute();
  const views={overview,camera,history,cleaning,cats,notifications,settings,detail:()=>detail(route.id)};
  $('#main').innerHTML=views[route.page]();
  if (route.page === 'camera' && state.cameraStream) $('#camera-stream').append(state.cameraStream.image);
  document.title=`PawLog · ${names[route.page]}`;
  $('#breadcrumb-page').textContent=names[route.page];
  const navPage=route.page==='detail'?'history':route.page;
  $$('[data-nav]').forEach(link=>{if(link.dataset.nav===navPage)link.setAttribute('aria-current','page');else link.removeAttribute('aria-current');});
  const more=$('#more-button');
  if(['cleaning','notifications','settings'].includes(route.page))more.setAttribute('aria-current','page');else more.removeAttribute('aria-current');
  $$('.notification-count').forEach(element=>{element.textContent=state.read?'0':'2';element.hidden=state.read;});
  $('.notification-dot').hidden=state.read;
  $('.notification-link').setAttribute('aria-label',`Notifications, ${state.read?'0':'2'} unread`);
  $('.workspace small').textContent=`${state.cats.length} cats`;
  if(route.page==='history')$('#history-filter').elements.cat.value=state.filters.cat;
  if(moveFocus){$('#main').focus({preventScroll:true});window.scrollTo({top:0,behavior:'instant'});}
}
function openCatForm(identifier='') {
  const form=$('#cat-form'); form.reset(); $('#cat-error').textContent='';
  const cat=catById(identifier);
  $('#cat-dialog-title').textContent=cat?`Edit ${cat.name}`:'Add a cat';
  form.elements.id.value=identifier;
  if(cat){form.elements.name.value=cat.name;form.elements.age.value=cat.age;form.elements.breed.value=cat.breed;}
  $('#cat-dialog').showModal();
}
function addCommand(title,reason,status,action='simulation') {
  state.commands.unshift({title,reason,status,action,time:new Date().toLocaleTimeString('en-MY',{hour:'numeric',minute:'2-digit'})});
}
function finishSimulation(stage) {
  clearTimeout(state.simTimer);state.simStage=stage;
  const command=state.commands.find(item=>item.status==='Running'||item.status==='Queued');
  if(command)command.status=stage==='completed'?'Completed':'Stopped';
  if(currentRoute().page==='cleaning')render();
}
document.addEventListener('click',event=>{
  if(event.target.closest('.skip-link')){event.preventDefault();$('#main').focus();return;}
  const close=event.target.closest('.close-dialog');
  if(close){close.closest('dialog').close();return;}
  const button=event.target.closest('[data-action]');
  if(button&&!button.disabled){
    const action=button.dataset.action;
    if(action==='automatic-camera-urls'){
      const form=$('#settings-form');
      for(const name of ['streamOverride']){form.elements[name].value='';form.elements[name].setCustomValidity('');}
      syncCameraFields(form);
    }
    if(action==='choose-cover'){
      const record=visionVisits.find(item=>item.id===button.dataset.id);
      record.coverFrame=Number(button.dataset.frame);record.manualCover=true;render();
      toast('Sample cover changed. Cat identity still needs your confirmation.');
    }
    if(action==='pick-cover'){
      const record=visionVisits.find(item=>item.id===button.dataset.id);
      if(record.selecting)return;
      record.selecting=true;render();
      setTimeout(()=>{record.selecting=false;record.coverFrame=1;record.manualCover=false;if(currentRoute().page==='detail'&&currentRoute().id===record.id)render();toast('Demo: full-body frame suggested. No photos were uploaded or analyzed.');},1100);
    }
    if(action==='account')location.hash='settings';
    if(action==='account-info')toast('Account settings are a design preview. No real sign-in or credentials are used.');
    if(action==='add-cat')openCatForm();
    if(action==='edit-cat')openCatForm(button.dataset.id);
    if(action==='cat-history'){state.filters={...defaultFilters(),cat:button.dataset.id};state.selectedRecordId='';location.hash='history';}
    if(action==='reset-filters'){
      state.filters=defaultFilters();
      render();
      $('[data-action="reset-filters"]').focus();
    }
    if(action==='history-category'){
      const {category}=button.dataset;
      state.filters.category=state.filters.category===category ? '' : category;
      refreshHistory(`[data-category="${category}"]`);
    }
    if(action==='history-sort'){
      state.sortAscending=!state.sortAscending;
      refreshHistory('[data-action="history-sort"]');
    }
    if(action==='clear-history-search'){
      state.filters.query='';
      const search=$('#history-filter').elements.query;
      search.value='';
      refreshHistory();
      search.focus();
    }
    if(action==='cycle-box'){
      const box=state.boxes.find(item=>String(item.id)===button.dataset.id);
      box.status=(box.status+1)%boxStatuses.length;
      $('#box-overview').innerHTML=boxOverview();
      $(`[data-action="cycle-box"][data-id="${box.id}"]`).focus({preventScroll:true});
    }
    if(action==='toggle-stream'){
      if(state.cameraStream){stopCameraStream();render();}
      else startCameraStream();
      $('[data-action="toggle-stream"]').focus({preventScroll:true});
    }
    if(action==='retry'){
      const item=state.events.find(record=>record.id===button.dataset.id);if(!item)return;
      item.status='Analyzing';render();
      clearTimeout(state.analysisTimer);
      state.analysisTimer=setTimeout(()=>{item.status='Review image';if(currentRoute().page==='detail')render();toast('Sample observation displayed. No cloud AI request was made.');},1200);
    }
    if(action==='finish-analysis'){const item=state.events.find(record=>record.id===button.dataset.id);item.status='Review image';render();}
    if(action==='mark-read'){state.read=true;render();toast('All sample notifications marked as read.');}
    if(action==='stop'||action==='hazard'){
      finishSimulation('stopped');
      addCommand(action==='hazard'?'Sample interruption':'Stop button preview','No device connected; physical motor state unknown','Not sent','stop');
      if(currentRoute().page==='cleaning')render();
      toast('Simulation stopped. No hardware stop was sent; no motor is connected.');
    }
    if(action==='simulate'&&!['running','queued'].includes(state.simStage)){
      const scenario=$('#scenario').value;
      if(scenario!=='clear'){
        state.simStage='failed';addCommand('Sample clean request',`${$('#scenario').selectedOptions[0].textContent} — start blocked`,'Rejected');render();
      }else{
        state.simStage='queued';addCommand('Sample cleaning cycle','UI simulation only — no physical motor movement','Queued');render();
        state.simTimer=setTimeout(()=>{state.simStage='running';state.commands[0].status='Running';if(currentRoute().page==='cleaning')render();state.simTimer=setTimeout(()=>finishSimulation('completed'),2400);},900);
      }
    }
    if(action==='reset-settings'){
      state.settings=defaultSettings();
      state.cameraError='';
      const saved=saveCameraIp(defaultCameraIp);
      render();
      toast(saved?'Preview settings reset.':'Settings reset for this tab. Browser storage is unavailable.');
    }
    if(action==='reset-demo')location.reload();
  }
  const historyRow=event.target.closest('[data-history-row]');
  if(historyRow) {
    const selected = visionVisits.find(record => record.id === historyRow.dataset.historyRow);
    state.selectedRecordId = selected.id;
    $$('[data-history-row]').forEach(row => {
      const active = row === historyRow;
      row.classList.toggle('selected-record', active);
      $('[data-action="history-record"]', row).setAttribute('aria-pressed', active);
    });
    $('#history-selected').innerHTML = historyRecordDetails(selected);
  }
  const filter=event.target.closest('[data-notification-filter]');if(filter){state.notificationFilter=filter.dataset.notificationFilter;render();}
  if(event.target.closest('#more-button'))$('#more-dialog').showModal();
  if(event.target.closest('#more-dialog a'))$('#more-dialog').close();
});
document.addEventListener('input',event=>{
  if(event.target.closest('#settings-form')&&['cameraIp','streamOverride'].includes(event.target.name)){
    event.target.setCustomValidity('');syncCameraFields(event.target.form);
    const value=event.target.value.trim();
    if(event.target.name==='cameraIp'&&validCameraIp(value)){
      if (state.settings.cameraIp !== value) {
        state.cameraError='';
      }
      state.settings.cameraIp=value;
      saveCameraIp(value);
    }
  }
});
document.addEventListener('input', event => {
  if(event.target.form?.id !== 'history-filter' || event.target.name !== 'query') return;
  state.filters.query=event.target.value;
  refreshHistory();
});
document.addEventListener('change',event=>{
  if(event.target.form?.id==='history-filter' && ['date','cat'].includes(event.target.name)){
    state.filters[event.target.name]=event.target.value;
    refreshHistory();
  }
});
document.addEventListener('submit',async event=>{
  event.preventDefault();
  const form=event.target;
  const formId=form.getAttribute('id');
  if(formId==='history-filter') return;
  if(formId==='assign-form'){
    const record=state.events.find(item=>item.id===form.dataset.id);
    record.catId=form.elements.cat.value;render();toast('Sample assignment updated for this tab.');
  }
  if(formId==='settings-form'){
    if(!validCameraIp(form.elements.cameraIp.value)){
      form.elements.cameraIp.setCustomValidity('Enter a .local name or an IPv4 address.');
      form.elements.cameraIp.reportValidity();return;
    }
    for(const name of ['streamOverride']){
      const field=form.elements[name];
      if(field.value.trim()){
        let valid=false;
        try{const url=new URL(field.value.trim());valid=['http:','https:'].includes(url.protocol)&&!!url.hostname&&!url.username&&!url.password&&url.pathname.replace(/\/+$/,'').toLowerCase()!=='/capture';}catch{}
        if(!valid){$('#settings-form details').open=true;field.setCustomValidity('Enter a live stream URL, such as http://pawlog-cam.local:81/stream.');field.reportValidity();return;}
      }
    }
    state.settings={...state.settings,cameraIp:form.elements.cameraIp.value.trim(),streamOverride:form.elements.streamOverride.value.trim(),port:form.elements.port.value,monitor:form.elements.monitor.checked,cloud:form.elements.cloud.checked,notifications:form.elements.notifications.checked};
    state.cameraError='';
    const saved=saveCameraIp(state.settings.cameraIp);
    toast(saved?'Camera address saved in this browser.':'Settings applied for this tab. Browser storage is unavailable.');
  }
  if(formId==='cat-form'){
    const name=form.elements.name.value.trim();if(!name){$('#cat-error').textContent='Please enter a name.';return;}
    const existing=catById(form.elements.id.value);
    const file=form.elements.photo.files[0];let image=existing?.photo||asset('mochi.jpg');
    if(file){
      if(!['image/jpeg','image/png','image/webp'].includes(file.type)||file.size>5*1024*1024){$('#cat-error').textContent='Choose a JPG, PNG or WebP photo under 5 MB.';return;}
      const url=URL.createObjectURL(file);
      try{const check=new Image();check.src=url;await check.decode();image=url;}catch{URL.revokeObjectURL(url);$('#cat-error').textContent='This file could not be opened as a photo.';return;}
    }
    const cat={id:existing?.id||`cat-${Date.now()}`,name,age:Number(form.elements.age.value),breed:form.elements.breed.value.trim(),photo:image};
    if(existing){if(existing.photo!==image&&existing.photo.startsWith('blob:'))URL.revokeObjectURL(existing.photo);Object.assign(existing,cat);}else state.cats.push(cat);
    $('#cat-dialog').close();render();toast('Sample cat profile saved. It will reset on reload.');
  }
});
window.addEventListener('hashchange',()=>{
  if (currentRoute().page !== 'camera') stopCameraStream();
  render(true);
});
window.addEventListener('pagehide',stopCameraStream);
render();

refreshVisionVisits();
setInterval(refreshVisionVisits,5000);
