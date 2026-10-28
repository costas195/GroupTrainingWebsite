/* NF Hybrid — an intentionally small, dependency-free client. All permissions are enforced by the API. */
const $ = (q, root = document) => root.querySelector(q);
const app = $('#app');
const state = { user: null, csrf: '', demo: false, page: 'schedule', data: null, owner: null, month: '', week: '', day: '', today: '', filter: 'All', busy: false };
const icons = {
  calendar: '<rect x="3" y="5" width="18" height="16" rx="3"/><path d="M16 3v4M8 3v4M3 11h18M8 15h2M14 15h2"/>',
  chart: '<path d="M4 4v16h17M8 15l4-5 4 3 5-8"/>',
  users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M22 21v-2a4 4 0 0 0-3-3.87"/><circle cx="9" cy="7" r="4"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
  home: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
  arrow: '<path d="M5 12h14m-6-6 6 6-6 6"/>',
  chevron: '<path d="m9 5 7 7-7 7"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  close: '<path d="m6 6 12 12M6 18 18 6"/>',
  logout: '<path d="M9 4H4v16h5M9 12h12m-5-5 5 5-5 5"/>',
  weight: '<path d="M5 8v8M2 10v4M19 8v8M22 10v4M5 12h14M8 7v10M16 7v10"/>',
  person: '<circle cx="12" cy="8" r="4"/><path d="M4 21v-2a8 8 0 0 1 16 0v2"/>',
  leaf: '<path d="M20 4C8 1 2 8 6 15s16 2 14-11ZM5 20 16 9"/>',
  bolt: '<path d="m13 2-9 12h7l-1 8 10-12h-7z"/>',
  lock: '<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/>',
  trash: '<path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7M14 10v7"/>',
};
function icon(name, cls = '') { return `<svg class="icon ${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[name] || icons.calendar}</svg>`; }
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const dateObj = str => new Date(str.length === 10 ? str + 'T12:00:00' : str);
const dateKey = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
const addDays = (key, n) => { const d = dateObj(key); d.setDate(d.getDate() + n); return dateKey(d); };
const monday = key => { const d = dateObj(key); return addDays(key, -(d.getDay() + 6) % 7); };
const fmt = (key, opts) => dateObj(key).toLocaleDateString('el-GR', opts);
const timeOf = str => str.slice(11, 16);
const monthName = month => fmt(month + '-01', { month: 'long', year: 'numeric' });
const initials = name => name.split(' ').map(p => p[0]).slice(0, 2).join('');
const isOwner = () => state.user?.role === 'owner';
const isPast = c => c.starts_at <= (state.data?.server_now || '');
const classIcon = category => ({ Strength: 'weight', Conditioning: 'bolt', Mobility: 'leaf', Hybrid: 'chart' }[category] || 'weight');
const categoryClass = category => category.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'custom';
const categoryLabel = category => ({Strength:'Δύναμη',Conditioning:'Φυσική κατάσταση',Hybrid:'Συνδυαστική',Mobility:'Κινητικότητα'})[category] || category;
const greetingName = name => { const first = name.split(' ')[0]; return ({Αλέξανδρος:'Αλέξανδρε',Γιάννης:'Γιάννη',Δημήτρης:'Δημήτρη',Νίκος:'Νίκο'})[first] || first; };
const normalizeSearch = value => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('el-GR');
const num = value => new Intl.NumberFormat('el-GR', {maximumFractionDigits: 2}).format(value);
const empty = (title, description, action = '') => `<div class="empty">${icon('calendar')}<h3>${esc(title)}</h3><p>${esc(description)}</p>${action}</div>`;

async function api(path, options = {}) {
  const response = await fetch('/api' + path, {
    ...options,
    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': state.csrf, ...options.headers },
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  });
  let result;
  try { result = await response.json(); } catch { throw new Error('Δεν ήταν δυνατή η σύνδεση. Δοκίμασε ξανά.'); }
  if (!response.ok) {
    if (response.status === 401 && state.user) { state.user = null; renderLanding(); }
    throw new Error(result.error || 'Κάτι πήγε στραβά. Δοκίμασε ξανά.');
  }
  return result;
}
let toastTimer;
function toast(message, error = false) {
  clearTimeout(toastTimer);
  const el = $('#toast');
  el.className = `visible ${error ? 'error' : ''}`;
  el.textContent = message;
  toastTimer = setTimeout(() => el.classList.remove('visible'), 4500);
}
function logo() { return '<span class="brand" role="img" aria-label="NF Hybrid"><span class="brand-mark" aria-hidden="true"></span><span class="brand-wordmark" aria-hidden="true"><strong>NF HYBRID</strong><small>FITNESS</small></span></span>'; }

function renderLanding() {
  closeModal();
  app.innerHTML = `
    <main class="portal-entry">
      <section class="login-card portal-login" aria-labelledby="login-title">
        <div class="portal-brand">${logo()}</div>
        <h1 id="login-title">Σύνδεση</h1>
        <form id="login-form">
          <label>Όνομα χρήστη<input name="username" type="text" placeholder="Το όνομα χρήστη σου" autocomplete="username" autocapitalize="none" spellcheck="false" maxlength="32" required></label>
          <label>Κωδικός<span class="password-wrap"><input name="password" type="password" placeholder="Πληκτρολόγησε τον κωδικό σου" autocomplete="current-password" required><button type="button" class="show-password" aria-label="Εμφάνιση κωδικού">Εμφάνιση</button></span></label>
          <div class="form-error" role="alert"></div>
          <button class="btn dark full" type="submit">Είσοδος ${icon('arrow')}</button>
        </form>
      </section>
    </main>`;
  $('#login-form').addEventListener('submit', async e => {
    e.preventDefault();
    await login(Object.fromEntries(new FormData(e.target)), e.target);
  });
  $('.show-password').onclick = e => {
    const input = $('#login-form [name=password]');
    input.type = input.type === 'password' ? 'text' : 'password';
    e.target.textContent = input.type === 'password' ? 'Εμφάνιση' : 'Απόκρυψη';
    e.target.setAttribute('aria-label', `${input.type === 'password' ? 'Εμφάνιση' : 'Απόκρυψη'} κωδικού`);
  };
}

async function login(credentials, form) {
  const buttons = document.querySelectorAll('.login-card button');
  buttons.forEach(b => b.disabled = true);
  $('.form-error', form).textContent = '';
  try {
    const result = await api('/login', { method: 'POST', body: credentials });
    state.user = result.user; state.csrf = result.csrf;
    if (state.user.must_change_password) { renderFirstPassword(); return; }
    state.page = isOwner() ? 'overview' : 'schedule';
    state.month = state.today.slice(0, 7); state.week = monday(state.today); state.day = state.today;
    await loadData(); selectNextDay(); renderApp(); window.scrollTo(0, 0);
  } catch (err) { $('.form-error', form).textContent = err.message; }
  finally { buttons.forEach(b => b.disabled = false); }
}

async function loadData() {
  const data = await api('/dashboard?month=' + encodeURIComponent(state.month));
  let owner = null;
  if (isOwner()) owner = await api('/owner');
  if (owner) owner.members.sort((a, b) => a.name.localeCompare(b.name, 'el-GR'));
  state.data = data; state.owner = owner; state.user = data.user;
}

function selectNextDay() {
  if (!isOwner() && !state.data.classes.some(c => c.starts_at.slice(0, 10) === state.today && !isPast(c))) {
    const next = state.data.classes.find(c => !isPast(c));
    if (next) { state.day = next.starts_at.slice(0, 10); state.week = monday(state.day); }
  }
}

function navigation() {
  return isOwner()
    ? [['overview', 'home', 'Εικόνα προπονητηρίου'], ['members', 'users', 'Μέλη'], ['schedule', 'calendar', 'Πρόγραμμα'], ['profile', 'person', 'Ο λογαριασμός μου']]
    : [['schedule', 'calendar', 'Η εβδομάδα μου'], ['bookings', 'check', 'Οι κρατήσεις μου'], ['progress', 'chart', 'Η πρόοδός μου'], ['profile', 'person', 'Το προφίλ μου']];
}

function renderApp() {
  const nav = navigation();
  const active = nav.find(n => n[0] === state.page) || nav[0];
  app.innerHTML = `<div class="app-shell"><aside class="sidebar"><a href="#" class="sidebar-logo" data-nav="${isOwner() ? 'overview' : 'schedule'}" aria-label="Αρχική NF Hybrid">${logo()}</a><div class="studio-label">ΤΟ ΠΡΟΠΟΝΗΤΗΡΙΟ<span>${isOwner() ? 'ΧΩΡΟΣ ΙΔΙΟΚΤΗΤΗ' : 'Ο ΧΩΡΟΣ ΤΟΥ ΜΕΛΟΥΣ'}</span></div><nav aria-label="Κύρια πλοήγηση">${nav.map(([key, ico, label]) => `<button class="nav-item ${state.page === key ? 'active' : ''}" data-nav="${key}" ${state.page === key ? 'aria-current="page"' : ''}>${icon(ico)}<span>${label}</span>${state.page === key ? '<i></i>' : ''}</button>`).join('')}</nav><div class="sidebar-bottom"><div class="sidebar-user"><div class="avatar">${esc(initials(state.user.name))}</div><div><strong>${esc(state.user.name)}</strong><small>${isOwner() ? 'Ιδιοκτήτης' : 'Μέλος'}</small></div><button class="icon-btn logout" aria-label="Αποσύνδεση">${icon('logout')}</button></div></div></aside><div class="workspace"><header class="app-topbar"><span class="mobile-brand">${logo()}</span><div class="breadcrumb">Ο χώρος σου <span>/</span> <strong>${active[2]}</strong></div><div class="topbar-right">${state.demo ? '<span class="demo-pill">ΔΟΚΙΜΑΣΤΙΚΟ</span>' : ''}<span class="topbar-date">${fmt(state.today, { weekday: 'short', day: 'numeric', month: 'short' })}</span><button class="avatar account-nav" aria-label="Άνοιγμα προφίλ">${esc(initials(state.user.name))}</button><button class="icon-btn logout mobile-logout" aria-label="Αποσύνδεση">${icon('logout')}</button></div></header><main class="app-main" id="main-content">${renderPage()}</main><footer class="app-footer"><span>Μικρή ομάδα. Πραγματική πρόοδος.</span><span>NF Hybrid <span class="tiny-dot"></span> ${esc(state.data.month.slice(0, 4))}</span></footer></div><nav class="mobile-nav" aria-label="Πλοήγηση κινητού">${nav.map(([key, ico, label]) => `<button class="${state.page === key ? 'active' : ''}" data-nav="${key}">${icon(ico)}<span>${({ schedule: 'Πρόγραμμα', bookings: 'Κρατήσεις', progress: 'Πρόοδος', profile: 'Προφίλ', overview: 'Εικόνα', members: 'Μέλη' })[key]}</span></button>`).join('')}</nav></div>`;
  bindApp();
}

function pageHeading(kicker, title, description, action = '') {
  return `<div class="page-heading"><div><div class="eyebrow">${kicker}</div><h1>${title}</h1><p>${description}</p></div>${action}</div>`;
}

function renderPage() {
  switch (state.page) {
    case 'schedule': return renderSchedule();
    case 'bookings': return renderBookings();
    case 'progress': return renderProgress();
    case 'profile': return renderProfile();
    case 'overview': return renderOverview();
    case 'members': return renderMembers();
    default: return renderSchedule();
  }
}

function monthOptions() {
  const months = new Set(state.data.access.map(a => a.month));
  for (let i = -2; i < 13; i++) {
    const d = dateObj(state.today); d.setDate(1); d.setMonth(d.getMonth() + i);
    months.add(dateKey(d).slice(0, 7));
  }
  months.add(state.month);
  return [...months].sort().map(m => `<option value="${m}" ${m === state.month ? 'selected' : ''}>${monthName(m)}${!isOwner() && !state.data.access.some(a => a.month === m) ? ' · Χωρίς πρόσβαση' : ''}</option>`).join('');
}

function membershipCard() {
  const access = state.data.access.find(a => a.month === state.month);
  const used = state.data.bookings.filter(c => c.starts_at.slice(0, 7) === state.month && monday(c.starts_at.slice(0, 10)) === state.week).length;
  return `<section class="panel membership"><div class="section-label">Η ΣΥΝΔΡΟΜΗ ΣΟΥ ${icon('check')}</div><h3>${access ? 'Χώρος για εξέλιξη.' : 'Ένας νέος μήνας σε περιμένει.'}</h3><p>${monthName(state.month)}</p>${access ? `<div class="membership-amount">${Math.max(0, access.weekly_limit - used)} <span>/ ${access.weekly_limit} κρατήσεις ακόμη</span></div><div class="booking-dots">${Array.from({ length: access.weekly_limit }, (_, i) => `<span class="${i < used ? 'used' : ''}"></span>`).join('')}</div><small>Για την επιλεγμένη εβδομάδα. Το όριό σου ανανεώνεται κάθε Δευτέρα.</small>` : '<p class="small">Ζήτησε από τον προπονητή σου να ενεργοποιήσει τη συνδρομή για αυτόν τον μήνα.</p>'}<div class="membership-foot">${icon('users')} Μικρή ομάδα. Προσωπική προσοχή.</div></section>`;
}

function nextClassCard() {
  const next = state.data.bookings.find(c => !isPast(c));
  return `<section class="panel next-class"><span class="section-label">Η ΕΠΟΜΕΝΗ ΠΡΟΠΟΝΗΣΗ ΣΟΥ</span>${next ? `<div class="next-icon ${categoryClass(next.category)}">${icon(classIcon(next.category))}</div><h3>${esc(next.title)}</h3><p>${fmt(next.starts_at, { weekday: 'long', day: 'numeric', month: 'short' })} · ${timeOf(next.starts_at)}</p><div class="next-meta">${icon('clock')} ${next.duration} λεπτά <span>·</span> Κόουτς: ${esc(next.coach)}</div><button class="text-link" data-class="${next.id}" data-source="booking">Δες την προπόνησή σου ${icon('arrow')}</button>` : `<h3>Η επόμενη ώρα για σένα.</h3><p>Διάλεξε ένα μάθημα που σε βολεύει. Ο προπονητής σου αναλαμβάνει τα υπόλοιπα.</p>${icon('weight', 'large-icon')}`}</section>`;
}

function renderSchedule() {
  const owner = isOwner();
  const days = Array.from({ length: 7 }, (_, i) => addDays(state.week, i));
  const allowed = owner || state.data.access.some(a => a.month === state.month);
  const selectedClasses = state.data.classes.filter(c => c.starts_at.slice(0, 10) === state.day && (state.filter === 'All' || c.category === state.filter));
  const weekEnd = addDays(state.week, 6);
  return `${pageHeading(owner ? 'ΟΡΓΑΝΩΣΕ ΜΙΑ ΔΥΝΑΤΗ ΕΒΔΟΜΑΔΑ' : 'ΜΙΑ ΠΡΟΠΟΝΗΣΗ ΤΗ ΦΟΡΑ', owner ? 'Το πρόγραμμα του χώρου<span class="green-dot">.</span>' : `Πάμε δυνατά, ${esc(greetingName(state.user.name))}<span class="green-dot">.</span>`, owner ? 'Οργάνωσε το πρόγραμμα. Κράτα τις ομάδες μικρές. Δώσε σε κάθε μέλος χώρο να εξελιχθεί.' : 'Οργάνωσε την εβδομάδα σου. Λίγο πιο δυνατός σε κάθε προπόνηση.', owner ? `<div class="modal-actions"><button class="btn outline" data-action="categories">Κατηγορίες</button><button class="btn dark" data-action="new-class">${icon('plus')} Νέο μάθημα</button></div>` : `<span class="heading-note">${icon('leaf')} Πρόοδος στον ρυθμό σου.</span>`)}
  <div class="schedule-layout"><div class="schedule-main"><section class="week-panel panel"><div class="week-heading"><div><span class="section-label">${owner ? 'ΟΡΓΑΝΩΣΗ ΜΑΘΗΜΑΤΩΝ' : 'Η ΕΒΔΟΜΑΔΑ ΠΡΟΠΟΝΗΣΗΣ ΣΟΥ'}</span><h2>${fmt(state.week, { day: 'numeric', month: 'short' })} – ${fmt(weekEnd, { day: 'numeric', month: 'short' })}</h2></div><div class="calendar-controls"><select id="month-select" aria-label="Επιλογή μήνα">${monthOptions()}</select><div class="week-arrows"><button class="icon-btn" data-week="-7" aria-label="Προηγούμενη εβδομάδα">${icon('chevron', 'flip')}</button><button class="icon-btn" data-week="7" aria-label="Επόμενη εβδομάδα">${icon('chevron')}</button></div></div></div><div class="week-strip">${days.map(day => { const count = state.data.classes.filter(c => c.starts_at.slice(0, 10) === day).length; return `<button class="day ${day === state.day ? 'selected' : ''} ${day === state.today ? 'today' : ''}" data-day="${day}" aria-pressed="${day === state.day}"><span>${fmt(day, { weekday: 'short' })}</span><strong>${dateObj(day).getDate()}</strong><small>${day.slice(0, 7) !== state.month ? fmt(day, { month: 'short' }) : count ? count + ' μαθ.' : 'Ρεπό'}</small></button>`; }).join('')}</div></section>
  <div class="schedule-subheading"><div><h2>${fmt(state.day, { weekday: 'long' })}<span>${fmt(state.day, { day: 'numeric', month: 'long' })}</span></h2><p>${state.day === state.today ? 'Μια καλή μέρα για να αφιερώσεις χρόνο στον εαυτό σου.' : 'Βρες την προπόνησή σου. Κάνε τη δική σου.'}</p></div><button class="btn small outline" data-action="today">Σήμερα</button></div>
  <div class="filter-row" aria-label="Φίλτρο τύπου μαθήματος">${['All', ...(state.owner?.categories || [...new Set(state.data.classes.map(c => c.category))])].map(f => `<button class="filter ${state.filter === f ? 'active' : ''}" data-filter="${esc(f)}" aria-pressed="${state.filter === f}">${f === 'All' ? 'Όλα τα μαθήματα' : esc(categoryLabel(f))}</button>`).join('')}</div>
  <div class="class-list">${!allowed ? empty('Το επόμενο βήμα σου ξεκινά εδώ.', 'Δεν έχει ενεργοποιηθεί ακόμη πρόσβαση για αυτόν τον μήνα. Επικοινώνησε με το προπονητήριο.') : !selectedClasses.length ? empty('Λίγος χρόνος για ξεκούραση.', state.filter === 'All' ? 'Δεν υπάρχουν μαθήματα για αυτή την ημέρα. Δες μια άλλη ημέρα της εβδομάδας.' : 'Δεν υπάρχουν μαθήματα με αυτό το φίλτρο. Δοκίμασε άλλο είδος προπόνησης.', state.filter !== 'All' ? '<button class="btn outline" data-filter="All">Δες όλα τα μαθήματα</button>' : '') : selectedClasses.map(classCard).join('')}</div>
  <div class="schedule-note">${icon('users')} Η θέση σου μετράει. Αν αλλάξει το πρόγραμμά σου, ακύρωσε πριν αρχίσει το μάθημα για να έρθει κάποιος άλλος.</div></div>
  <aside class="schedule-aside">${owner ? ownerDaySummary() : nextClassCard() + membershipCard()}<div class="coach-note"><span class="eyebrow">ΕΝΑ ΜΗΝΥΜΑ ΑΠΟ ΤΟΝ ΠΡΟΠΟΝΗΤΗ ΣΟΥ</span><p>Δεν χρειάζεται να είσαι ο πιο δυνατός στον χώρο. Μόνο λίγο πιο δυνατός από χθες.</p><div><span class="avatar small">ΓΠ</span><span>Γιάννης <small>ΥΠΕΥΘΥΝΟΣ ΠΡΟΠΟΝΗΤΗΣ</small></span></div></div></aside></div>`;
}

function classCard(c) {
  const left = Math.max(0, c.capacity - c.booked);
  const past = isPast(c);
  return `<article class="class-card ${c.booking_id ? 'is-booked' : ''} ${past ? 'past' : ''}"><div class="class-time"><strong>${timeOf(c.starts_at)}</strong><span>${c.duration} ΛΕΠΤΑ</span></div><div class="class-symbol ${categoryClass(c.category)}">${icon(classIcon(c.category))}</div><div class="class-info"><span class="category-label ${categoryClass(c.category)}">${esc(categoryLabel(c.category))}</span><h3><button data-class="${c.id}">${esc(c.title)}</button></h3><p>Κόουτς: ${esc(c.coach)} <span>·</span> Για όλα τα επίπεδα</p></div><div class="class-availability"><span class="seats ${left <= 2 ? 'low' : ''}">${c.booking_id ? icon('check') + ' Έχεις κράτηση' : past ? 'Ολοκληρώθηκε' : left ? `<i></i> ${left} από ${c.capacity} θέσεις διαθέσιμες` : 'Πλήρες'}</span>${isOwner() ? `<button class="btn outline small" data-class="${c.id}">Διαχείριση μαθήματος ${icon('arrow')}</button>` : `<button class="btn small ${c.booking_id ? 'booked' : past || !left ? 'outline' : 'dark'}" data-class="${c.id}">${c.booking_id ? 'Δες την κράτηση' : past ? 'Δες το μάθημα' : !left ? 'Δες το μάθημα' : 'Δες και κλείσε'} ${icon(c.booking_id ? 'check' : 'arrow')}</button>`}</div></article>`;
}

function renderBookings() {
  const upcoming = state.data.bookings.filter(c => !isPast(c));
  const past = state.data.bookings.filter(isPast).reverse();
  return `${pageHeading('ΜΙΑ ΜΙΚΡΗ ΔΕΣΜΕΥΣΗ ΣΤΟΝ ΕΑΥΤΟ ΣΟΥ', 'Η θέση σου είναι κλεισμένη<span class="green-dot">.</span>', 'Οι επόμενες προπονήσεις σου και όσα έχεις ήδη καταφέρει.')}<div class="section-heading"><h2>Προσεχώς <span class="count-badge">${upcoming.length}</span></h2><button class="text-link" data-nav="schedule">Βρες μάθημα ${icon('arrow')}</button></div><div class="booking-grid">${upcoming.length ? upcoming.map(c => bookingCard(c)).join('') : empty('Η επόμενη προπόνησή σου σε περιμένει.', 'Δες την εβδομάδα σου και κλείσε μια θέση.', '<button class="btn dark" data-nav="schedule">Δες το πρόγραμμα</button>')}</div><div class="section-heading"><h2>Προηγούμενες προπονήσεις <span class="count-badge">${past.length}</span></h2></div><div class="booking-grid">${past.length ? past.map(c => bookingCard(c)).join('') : empty('Κάθε διαδρομή ξεκινά με μια προπόνηση.', 'Εδώ θα εμφανίζονται οι προπονήσεις που ολοκλήρωσες.')}</div>`;
}

function bookingCard(c) {
  return `<article class="panel booking-card"><div class="booking-card-top"><span class="tag ${categoryClass(c.category)}">${esc(categoryLabel(c.category))}</span><span class="small muted">${isPast(c) ? c.attended ? 'Παρουσία ✓' : 'Ολοκληρώθηκε' : 'Κράτηση ✓'}</span></div><h3>${esc(c.title)}</h3><p>${fmt(c.starts_at, { weekday: 'long', day: 'numeric', month: 'short' })} · ${timeOf(c.starts_at)}</p><p class="small muted">${c.duration} λεπτά · Κόουτς: ${esc(c.coach)}</p><button class="text-link" data-class="${c.id}" data-source="booking">${isPast(c) ? 'Δες το πρόγραμμα' : 'Διαχείριση κράτησης'} ${icon('arrow')}</button></article>`;
}

function chart(logs) {
  if (logs.length < 2) return '<div class="chart-empty">Πρόσθεσε τουλάχιστον δύο καταγραφές για να δεις την πορεία σου.</div>';
  const values = logs.map(l => l.weight);
  const min = Math.min(...values) - 0.3, max = Math.max(...values) + 0.3;
  const y = v => 145 - (v - min) / (max - min) * 115;
  const points = logs.map((l, i) => `${25 + i / (logs.length - 1) * 550},${y(l.weight)}`);
  return `<svg viewBox="0 0 600 190" class="progress-chart" role="img" aria-label="Πορεία σωματικού βάρους από ${num(values[0])} έως ${num(values.at(-1))} κιλά"><defs><linearGradient id="chart-fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#b2d7b2" stop-opacity=".5"/><stop offset="100%" stop-color="#b2d7b2" stop-opacity="0"/></linearGradient></defs>${[40, 90, 145].map(v => `<line x1="25" x2="575" y1="${v}" y2="${v}" stroke="#e8ebe4" stroke-dasharray="4 5"/>`).join('')}<polygon points="25,155 ${points.join(' ')} 575,155" fill="url(#chart-fill)"/><polyline points="${points.join(' ')}" fill="none" stroke="#356b4b" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/>${logs.map((l, i) => `<circle cx="${25 + i / (logs.length - 1) * 550}" cy="${y(l.weight)}" r="4.5" fill="#356b4b"><title>${l.logged_on}: ${num(l.weight)} κιλά</title></circle>`).join('')}<text x="25" y="183" fill="#7a8178" font-size="12">${fmt(logs[0].logged_on, { day: 'numeric', month: 'short' })}</text><text x="575" y="183" text-anchor="end" fill="#7a8178" font-size="12">${fmt(logs.at(-1).logged_on, { day: 'numeric', month: 'short' })}</text></svg>`;
}

function renderProgress() {
  const logs = state.data.logs;
  const weights = logs.filter(l => l.kind === 'bodyweight');
  const lifts = logs.filter(l => l.kind === 'lift');
  const attended = state.data.bookings.filter(c => c.attended).length;
  const uniqueLifts = [...new Set(lifts.map(l => l.exercise))];
  return `${pageHeading('ΟΙ ΜΙΚΡΕΣ ΝΙΚΕΣ ΜΕΤΡΑΝΕ', 'Δες πόσο έχεις προχωρήσει<span class="green-dot">.</span>', 'Η διαδρομή σου, στον ρυθμό σου. Κατέγραψε όσα έχουν αξία για σένα.', `<button class="btn dark" data-action="log-progress">${icon('plus')} Καταγραφή προόδου</button>`)}<div class="stats-grid three"><div class="stat-card">${icon('check')}<span>Παρουσίες σε μαθήματα</span><strong>${attended}<small>ώρες για τον εαυτό σου</small></strong></div><div class="stat-card">${icon('person')}<span>Τελευταίο σωματικό βάρος</span><strong>${weights.length ? num(weights.at(-1).weight) : '—'}<small>${weights.length ? 'κιλά · ' + fmt(weights.at(-1).logged_on, { day: 'numeric', month: 'short' }) : 'Ώρα για την πρώτη καταγραφή'}</small></strong></div><div class="stat-card">${icon('weight')}<span>Ασκήσεις που καταγράφεις</span><strong>${uniqueLifts.length}<small>${lifts.length} καταγραφές προπόνησης</small></strong></div></div><div class="progress-grid"><section class="panel chart-panel"><div class="section-heading"><div><span class="eyebrow">ΟΙ ΚΑΤΑΓΡΑΦΕΣ ΣΟΥ</span><h2>Σωματικό βάρος</h2></div><span class="tag neutral">ΚΙΛΑ</span></div>${chart(weights)}<p class="small muted">Ένα μόνο κομμάτι της εικόνας. Η συνέπεια, η δύναμη και το πώς αισθάνεσαι μετράνε εξίσου.</p></section><section class="panel focus-card"><span class="eyebrow">ΠΟΥ ΕΣΤΙΑΖΕΙΣ ΤΩΡΑ</span>${icon('leaf', 'large-icon')}<h3>${esc(state.user.goal || 'Δώσε λίγο χώρο στην πρόοδο.')}</h3><p>${esc(state.user.priority || 'Όρισε την προτεραιότητά σου στο προφίλ και προχώρα μία προπόνηση τη φορά.')}</p><button class="text-link" data-nav="profile">Άλλαξε προτεραιότητα ${icon('arrow')}</button></section></div><div class="section-heading"><h2>Το ημερολόγιο δύναμής σου</h2><span class="small muted">Οι καλύτερες επιδόσεις σου, ανά άσκηση</span></div><div class="strength-grid">${uniqueLifts.length ? uniqueLifts.map(exercise => { const records = lifts.filter(l => l.exercise === exercise), latest = records.at(-1), best = Math.max(...records.map(l => l.weight)); return `<section class="panel lift-card">${icon('weight')}<h3>${esc(exercise)}</h3><strong>${num(best)} <span>κιλά καλύτερη επίδοση</span></strong><p>Τελευταία: ${num(latest.weight)} κιλά × ${latest.reps} επαναλήψεις</p><span class="small muted">${fmt(latest.logged_on, { day: 'numeric', month: 'short' })} · ${records.length} καταγραφές</span></section>`; }).join('') : empty('Ξεκίνα τη διαδρομή της δύναμής σου.', 'Κατέγραψε την άσκηση, τα κιλά και τις επαναλήψεις μετά την προπόνηση.')}</div><div class="section-heading"><h2>Οι σημειώσεις προπόνησής σου</h2><span class="small muted">${logs.length} καταγραφές</span></div><div class="panel table-wrap"><table><thead><tr><th>Ημερομηνία</th><th>Καταγραφή / άσκηση</th><th>Αποτέλεσμα</th><th>Σημειώσεις</th><th><span class="sr-only">Ενέργειες</span></th></tr></thead><tbody>${[...logs].reverse().map(l => `<tr><td>${fmt(l.logged_on, { day: 'numeric', month: 'short' })}</td><td><strong>${esc(l.exercise)}</strong></td><td>${num(l.weight)} κιλά${l.reps ? ' × ' + l.reps : ''}</td><td class="notes-cell">${esc(l.note || '—')}</td><td><button class="icon-btn" data-delete-log="${l.id}" aria-label="Διαγραφή καταγραφής ${esc(l.exercise)}">${icon('trash')}</button></td></tr>`).join('') || '<tr><td colspan="5">Δεν υπάρχουν καταγραφές ακόμη. Ξεκίνα στην επόμενη προπόνησή σου.</td></tr>'}</tbody></table></div>`;
}

function renderProfile() {
  return `${pageHeading('Ο ΧΩΡΟΣ ΣΟΥ, Η ΙΣΤΟΡΙΑ ΣΟΥ', isOwner() ? 'Καλώς ήρθες, κόουτς<span class="green-dot">.</span>' : 'Λίγα λόγια για σένα<span class="green-dot">.</span>', 'Κράτα ενημερωμένα τα στοιχεία και τις προτεραιότητές σου.')}<div class="profile-grid"><section class="panel profile-panel"><div class="profile-avatar">${esc(initials(state.user.name))}</div><h2>${esc(state.user.name)}</h2><p>${esc(state.user.username)}</p>${state.user.email ? `<p class="small muted">${esc(state.user.email)}</p>` : ''}<span class="tag mint">${isOwner() ? 'ΙΔΙΟΚΤΗΤΗΣ' : 'ΜΕΛΟΣ'}</span>${!isOwner() ? '<p class="small muted">Ο προπονητής διαχειρίζεται την πρόσβαση της συνδρομής σου. Για αλλαγές, επικοινώνησε με τον χώρο.</p>' : ''}</section><section class="panel form-panel"><h2>Τα στοιχεία σου</h2><form id="profile-form"><label>Όνομα χρήστη<input name="username" value="${esc(state.user.username)}" minlength="3" maxlength="32" pattern="[a-zA-Z0-9][a-zA-Z0-9._\\-]{2,31}" autocomplete="username" autocapitalize="none" spellcheck="false" required></label><label>Το όνομά σου<input name="name" value="${esc(state.user.name)}" minlength="2" maxlength="80" required autocomplete="name"></label><label>Ο στόχος σου<textarea name="goal" maxlength="300" rows="3" placeholder="Τι θα ήθελες να πετύχεις;">${esc(state.user.goal)}</textarea></label><label>Πού θέλεις να εστιάσεις<textarea name="priority" maxlength="300" rows="3" placeholder="Συνέπεια, μια άσκηση, κινητικότητα — ό,τι χρειάζεσαι.">${esc(state.user.priority)}</textarea></label><div class="form-error" role="alert"></div><button class="btn dark" type="submit">Αποθήκευση στοιχείων ${icon('check')}</button></form></section><section class="panel form-panel password-panel"><h2>Αλλαγή κωδικού</h2><form id="password-form"><label>Τρέχων κωδικός<input name="current_password" type="password" autocomplete="current-password" required></label><label>Νέος κωδικός<input name="new_password" type="password" autocomplete="new-password" required></label><div class="form-error" role="alert"></div><button type="submit" class="btn outline">Ενημέρωση κωδικού ${icon('lock')}</button></form></section></div>`;
}

function renderOverview() {
  const members = state.owner.members;
  const active = members.filter(m => m.access.some(a => a.month === state.today.slice(0, 7)));
  const dayClasses = state.data.classes.filter(c => c.starts_at.slice(0, 10) === state.today);
  const weekBookings = state.owner.bookings.filter(b => monday(b.starts_at.slice(0, 10)) === monday(state.today));
  const upcoming = state.data.classes.filter(c => !isPast(c)).slice(0, 5);
  return `${pageHeading('ΜΙΑ ΚΑΛΗ ΜΕΡΑ ΓΙΑ ΚΑΤΙ ΔΥΝΑΤΟ', `Γεια σου, ${esc(greetingName(state.user.name))}<span class="green-dot">.</span>`, 'Μια εικόνα των ανθρώπων και των προπονήσεων του χώρου σου.', `<button class="btn dark" data-action="new-class">${icon('plus')} Νέο μάθημα</button>`)}<div class="owner-welcome"><div><span class="eyebrow">Ο ΧΩΡΟΣ ΣΟΥ ΜΕ ΜΙΑ ΜΑΤΙΑ</span><h2>Μικρές ομάδες.<br>Μεγάλες αλλαγές.</h2><p>${active.length} ενεργά μέλη. Πολλές δυνατότητες.</p><button class="text-link" data-nav="members">Δες τα μέλη σου ${icon('arrow')}</button></div><div class="welcome-art" aria-hidden="true"><div class="art-circle"><img src="/static/brand/hybrid-fitness.png" alt="" width="170" height="170"></div><span class="art-caption">STRONGER TOGETHER</span></div></div><div class="stats-grid"><div class="stat-card">${icon('users')}<span>Ενεργά μέλη αυτόν τον μήνα</span><strong>${active.length}<small>από ${members.length} μέλη</small></strong></div><div class="stat-card">${icon('calendar')}<span>Σημερινά μαθήματα</span><strong>${dayClasses.length}<small>${dayClasses.reduce((n, c) => n + c.capacity, 0)} συνολικές θέσεις</small></strong></div><div class="stat-card">${icon('check')}<span>Κρατήσεις εβδομάδας</span><strong>${weekBookings.length}<small>Δευτέρα έως Κυριακή</small></strong></div><div class="stat-card">${icon('chart')}<span>Σημερινή πληρότητα</span><strong>${dayClasses.length ? Math.round(dayClasses.reduce((n, c) => n + c.booked, 0) / dayClasses.reduce((n, c) => n + c.capacity, 0) * 100) : 0}<small>τοις εκατό των διαθέσιμων θέσεων</small></strong></div></div><div class="section-heading"><h2>Προσεχώς στον χώρο</h2><button class="text-link" data-nav="schedule">Άνοιγμα προγράμματος ${icon('arrow')}</button></div><div class="class-list">${upcoming.map(c => `<div class="overview-class-date">${fmt(c.starts_at, { weekday: 'short', day: 'numeric', month: 'short' })}</div>${classCard(c)}`).join('') || empty('Οργάνωσε μια δυνατή εβδομάδα.', 'Δημιούργησε το πρώτο μάθημα και οργάνωσε το πρόγραμμα των μελών σου.')}</div>`;
}

function ownerDaySummary() {
  const classes = state.data.classes.filter(c => c.starts_at.slice(0, 10) === state.day);
  return `<section class="panel membership"><span class="section-label">Η ΗΜΕΡΑ ΜΕ ΜΙΑ ΜΑΤΙΑ</span><h3>${classes.length} μαθήματα.<br>Πολλές δυνατότητες.</h3><div class="day-summary"><div><strong>${classes.reduce((n, c) => n + c.booked, 0)}</strong><span>κλεισμένες θέσεις</span></div><div><strong>${classes.reduce((n, c) => n + c.capacity - c.booked, 0)}</strong><span>διαθέσιμες θέσεις</span></div></div><p class="small">Άνοιξε ένα μάθημα για να δεις το πρόγραμμα, να ορίσεις θέσεις και να ελέγξεις τις συμμετοχές.</p></section>`;
}

function renderMembers() {
  const members = state.owner.members;
  return `${pageHeading('ΟΙ ΑΝΘΡΩΠΟΙ ΚΑΝΟΥΝ ΤΟΝ ΧΩΡΟ', 'Η προπονητική σου παρέα<span class="green-dot">.</span>', 'Καλωσόρισε νέα μέλη, όρισε πρόσβαση ανά μήνα και βοήθησέ τα να μείνουν συνεπή.', `<button class="btn dark" data-action="new-member">${icon('plus')} Νέο μέλος</button>`)}<div class="panel members-panel"><div class="section-heading"><h2>Όλα τα μέλη <span class="count-badge">${members.length}</span></h2><input type="search" id="member-search" placeholder="Αναζήτηση ονόματος ή username…" aria-label="Αναζήτηση μελών"></div><div class="table-wrap"><table class="members-table"><thead><tr><th>Μέλος</th><th>Πρόσβαση αυτού του μήνα</th><th>Εβδομαδιαίο όριο</th><th>Συνολικές κρατήσεις</th><th></th></tr></thead><tbody>${members.map(m => { const access = m.access.find(a => a.month === state.today.slice(0, 7)); return `<tr data-member-row="${esc(normalizeSearch(m.name + ' ' + m.username + ' ' + m.email))}"><td><div class="member-cell"><span class="avatar">${esc(initials(m.name))}</span><span><strong>${esc(m.name)}</strong><small>${esc(m.username)}</small></span></div></td><td><span class="status-pill ${access ? 'active' : ''}"><i></i>${access ? 'Ενεργή' : 'Χωρίς πρόσβαση'}</span></td><td>${access ? access.weekly_limit + ' μαθήματα / εβδομάδα' : '—'}</td><td>${m.bookings}</td><td><button class="btn outline small" data-member="${m.id}">Διαχείριση πρόσβασης ${icon('arrow')}</button></td></tr>`; }).join('') || '<tr><td colspan="5">Ξεκίνα προσθέτοντας το πρώτο μέλος σου.</td></tr>'}</tbody></table></div><div id="no-member-results" class="hidden empty"><h3>Δεν βρέθηκαν μέλη</h3><p>Δοκίμασε άλλο όνομα ή username.</p></div></div><div class="info-strip">${icon('lock')}<p>Τα μέλη βλέπουν μαθήματα μόνο για τους ενεργούς μήνες τους. Τα εβδομαδιαία όρια ισχύουν Δευτέρα–Κυριακή, ξεχωριστά ανά μήνα όταν η εβδομάδα περιλαμβάνει δύο μήνες.</p></div>`;
}

function bindApp() {
  document.querySelectorAll('[data-nav]').forEach(b => b.onclick = e => { e.preventDefault(); navigate(b.dataset.nav); });
  document.querySelectorAll('.logout').forEach(b => b.onclick = async () => { try { await api('/logout', { method: 'POST' }); state.user = null; const s = await api('/session'); state.csrf = s.csrf; renderLanding(); } catch (e) { toast(e.message, true); } });
  $('.account-nav').onclick = () => navigate('profile');
  document.querySelectorAll('[data-class]').forEach(b => b.onclick = () => showClass(Number(b.dataset.class), b.dataset.source));
  document.querySelectorAll('[data-action]').forEach(b => b.onclick = () => ({ 'new-class': () => classForm(), categories: categoryManager, 'new-member': memberForm, 'log-progress': progressForm, today: goToday }[b.dataset.action]?.()));
  document.querySelectorAll('[data-filter]').forEach(b => b.onclick = () => { state.filter = b.dataset.filter; renderApp(); });
  document.querySelectorAll('[data-day]').forEach(b => b.onclick = async () => {
    const day = b.dataset.day;
    if (day.slice(0, 7) !== state.month) await changeMonth(day.slice(0, 7), day);
    else { state.day = day; renderApp(); }
  });
  document.querySelectorAll('[data-week]').forEach(b => b.onclick = async () => {
    const nextWeek = addDays(state.week, Number(b.dataset.week));
    const target = addDays(state.day, Number(b.dataset.week));
    await changeMonth(target.slice(0, 7), target, nextWeek);
  });
  if ($('#month-select')) $('#month-select').onchange = e => changeMonth(e.target.value);
  if ($('#member-search')) $('#member-search').oninput = e => {
    const query = normalizeSearch(e.target.value).trim(); let count = 0;
    document.querySelectorAll('[data-member-row]').forEach(row => { const visible = row.dataset.memberRow.includes(query); row.hidden = !visible; if (visible) count++; });
    $('#no-member-results').classList.toggle('hidden', count > 0);
  };
  document.querySelectorAll('[data-member]').forEach(b => {
    const member = state.owner.members.find(m => m.id === Number(b.dataset.member));
    b.onclick = () => accessForm(member.id);
    if (member.invitation) {
      const status = document.createElement('small');
      status.textContent = invitationLabel(member.invitation);
      $('.member-cell > span:last-child', b.closest('tr')).append(status);
    }
  });
  document.querySelectorAll('[data-delete-log]').forEach(b => b.onclick = () => confirmAction('Διαγραφή καταγραφής;', 'Αυτή η καταγραφή θα διαγραφεί οριστικά από το ημερολόγιό σου.', async () => { await api('/progress/' + b.dataset.deleteLog, { method: 'DELETE' }); await refresh(); toast('Η καταγραφή διαγράφηκε.'); }));
  if ($('#profile-form')) bindForm($('#profile-form'), async data => { await api('/profile', { method: 'PUT', body: data }); await refresh(); toast('Τα στοιχεία σου ενημερώθηκαν.'); });
  if ($('#password-form')) bindForm($('#password-form'), async data => { await api('/password', { method: 'PUT', body: data }); $('#password-form').reset(); toast('Ο κωδικός ενημερώθηκε.'); });
}

function navigate(page) { state.page = page; state.filter = 'All'; renderApp(); window.scrollTo({ top: 0, behavior: 'smooth' }); }
async function refresh() { await loadData(); renderApp(); }
async function changeMonth(month, day, week) {
  const previous = { month: state.month, day: state.day, week: state.week };
  state.month = month; state.day = day || (month === state.today.slice(0, 7) ? state.today : month + '-01'); state.week = week || monday(state.day);
  try { await refresh(); } catch (e) { Object.assign(state, previous); toast(e.message, true); }
}
async function goToday() { await changeMonth(state.today.slice(0, 7), state.today); }

let modalReturnFocus;
function modal(title, content, subtitle = '') {
  if (!$('#modal-root').children.length) modalReturnFocus = document.activeElement;
  $('#modal-root').innerHTML = `<div class="modal-backdrop"><section class="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title"><div class="modal-heading"><div><h2 id="modal-title">${title}</h2>${subtitle ? `<p>${subtitle}</p>` : ''}</div><button class="icon-btn" id="close-modal" aria-label="Κλείσιμο παραθύρου">${icon('close')}</button></div>${content}</section></div>`;
  document.body.classList.add('modal-open');
  $('#close-modal').onclick = closeModal;
  $('.modal-backdrop').onclick = e => { if (e.target === e.currentTarget) closeModal(); };
  $('#close-modal').focus();
}
function closeModal() {
  const wasOpen = !!$('#modal-root').children.length;
  $('#modal-root').innerHTML = ''; document.body.classList.remove('modal-open');
  if (wasOpen && modalReturnFocus?.isConnected) modalReturnFocus.focus();
}
document.addEventListener('keydown', e => {
  const dialog = $('.modal');
  if (!dialog) return;
  if (e.key === 'Escape') closeModal();
  if (e.key === 'Tab') {
    const items = [...dialog.querySelectorAll('button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), a[href]')].filter(el => el.getClientRects().length);
    const first = items[0], last = items.at(-1);
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last?.focus(); }
    if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first?.focus(); }
  }
});

function bindForm(form, handler) {
  form.onsubmit = async e => {
    e.preventDefault();
    const button = $('button[type=submit]', form), label = button.innerHTML;
    button.disabled = true; button.textContent = 'Αποθήκευση…'; $('.form-error', form).textContent = '';
    try { await handler(Object.fromEntries(new FormData(form))); }
    catch (err) { if (form.isConnected) $('.form-error', form).textContent = err.message; else toast(err.message, true); }
    finally { button.disabled = false; button.innerHTML = label; }
  };
}

function confirmAction(title, description, action) {
  modal(esc(title), `<p class="confirm-description">${esc(description)}</p><div class="form-error" role="alert"></div><div class="modal-actions"><button class="btn outline" id="keep-button">Διατήρηση</button><button class="btn danger" id="confirm-button">Ναι, διαγραφή ${icon('trash')}</button></div>`);
  $('#keep-button').onclick = closeModal;
  $('#confirm-button').onclick = async e => { e.currentTarget.disabled = true; try { await action(); closeModal(); } catch (err) { const box = $('.modal .form-error'); if (box) box.textContent = err.message; const btn = $('#confirm-button'); if (btn) btn.disabled = false; } };
}

function showClass(id, source) {
  const original = source === 'booking' ? state.data.bookings.find(c => c.id === id) : state.data.classes.find(c => c.id === id);
  const c = original || state.data.bookings.find(c => c.id === id) || state.data.classes.find(c => c.id === id);
  if (!c) return toast('Αυτό το μάθημα δεν είναι πλέον διαθέσιμο.', true);
  const booking = state.data.bookings.find(b => b.id === id);
  const left = c.capacity - (c.booked || 0);
  const roster = isOwner() ? state.owner.bookings.filter(b => b.class_id === id) : [];
  modal(esc(c.title), `<div class="class-detail-meta"><span class="tag ${categoryClass(c.category)}">${esc(categoryLabel(c.category))}</span><span>${fmt(c.starts_at, { weekday: 'short', day: 'numeric', month: 'short' })} · ${timeOf(c.starts_at)}</span><span>${c.duration} λεπτά · Κόουτς: ${esc(c.coach)}</span></div><p class="class-description">${esc(c.description)}</p><div class="workout"><div><span class="workout-number">01</span><div><h3>Προθέρμανση και προετοιμασία</h3><p>${esc(c.warmup).replace(/\n/g, '<br>')}</p></div></div><div><span class="workout-number">02</span><div><h3>Κυρίως πρόγραμμα</h3><p>${esc(c.main).replace(/\n/g, '<br>')}</p></div></div><div><span class="workout-number">03</span><div><h3>Τελική προσπάθεια και αποθεραπεία</h3><p>${esc(c.finisher).replace(/\n/g, '<br>')}</p></div></div></div>${isOwner() ? `<div class="section-heading"><h3>Συμμετοχές μαθήματος <span class="count-badge">${roster.length} / ${c.capacity}</span></h3></div><div class="roster">${roster.map(b => `<div><span class="avatar small">${esc(initials(b.name))}</span><span>${esc(b.name)}</span><button class="btn small ${b.attended ? 'booked' : 'outline'}" data-attendance="${b.id}" data-attended="${b.attended}" ${!isPast(c) ? 'disabled title="Διαθέσιμο μετά την έναρξη του μαθήματος"' : ''}>${b.attended ? 'Παρουσία ✓' : 'Καταχώριση παρουσίας'}</button></div>`).join('') || '<p class="muted small">Δεν υπάρχουν ακόμη κρατήσεις.</p>'}</div><div class="modal-actions"><button class="btn outline" id="delete-class">Ακύρωση</button><button class="btn outline" id="duplicate-class">Αντιγραφή</button><button class="btn dark" id="edit-class" ${isPast(c) ? 'disabled' : ''}>Επεξεργασία ${icon('arrow')}</button></div>` : `<div class="detail-booking-note">${icon(booking ? 'check' : 'users')} ${booking ? isPast(c) ? booking.attended ? 'Έδωσες το παρών. Αυτό μετράει.' : 'Αυτό το μάθημα ολοκληρώθηκε.' : 'Η θέση σου είναι κλεισμένη. Τα λέμε στον χώρο.' : isPast(c) ? 'Αυτό το μάθημα ολοκληρώθηκε.' : left > 0 ? `${left} από ${c.capacity} διαθέσιμες θέσεις · Για όλα τα επίπεδα` : 'Το μάθημα είναι πλήρες. Δες κάποια άλλη ώρα.'}</div><div class="form-error" role="alert"></div><button class="btn full ${booking ? 'outline' : 'dark'}" id="booking-action" ${isPast(c) || (!booking && left <= 0) ? 'disabled' : ''}>${booking ? 'Ακύρωση κράτησης' : 'Κράτηση θέσης'} ${icon(booking ? 'close' : 'arrow')}</button><p class="small muted center">${booking ? 'Ακύρωσε πριν από την έναρξη για να ελευθερωθεί η θέση σου.' : 'Ισχύουν η μηνιαία συνδρομή και το εβδομαδιαίο όριό σου.'}</p>`}`);
  if (isOwner()) {
    $('#edit-class').onclick = () => classForm(c);
    $('#duplicate-class').onclick = () => classForm(c, true);
    $('#delete-class').onclick = () => confirmAction('Ακύρωση αυτού του μαθήματος;', `Το μάθημα θα αφαιρεθεί και θα ελευθερωθούν ${roster.length} κλεισμένες θέσεις. Τα μέλη θα δουν την αλλαγή στον λογαριασμό τους.`, async () => { await api('/owner/classes/' + c.id, { method: 'DELETE' }); await refresh(); toast('Το μάθημα ακυρώθηκε.'); });
    document.querySelectorAll('[data-attendance]').forEach(b => b.onclick = async () => { b.disabled = true; try { await api('/owner/bookings/' + b.dataset.attendance, { method: 'PUT', body: { attended: b.dataset.attended !== '1' } }); await refresh(); showClass(id); toast('Η παρουσία ενημερώθηκε.'); } catch (e) { b.disabled = false; toast(e.message, true); } });
  } else {
    $('#booking-action').onclick = async e => {
      if (booking) return confirmAction('Να ελευθερωθεί η θέση σου;', 'Η κράτησή σου θα ακυρωθεί και η θέση θα είναι διαθέσιμη για άλλο μέλος.', async () => { await api('/bookings/' + booking.booking_id, { method: 'DELETE' }); await refresh(); toast('Η κράτηση ακυρώθηκε. Θα τα πούμε στην επόμενη προπόνηση.'); });
      e.currentTarget.disabled = true;
      try { await api('/bookings', { method: 'POST', body: { class_id: c.id } }); await refresh(); closeModal(); toast('Έκλεισες θέση! Σε περιμένουμε.'); }
      catch (err) { $('.modal .form-error').textContent = err.message; $('#booking-action').disabled = false; }
    };
  }
}

function progressForm() {
  modal('Κάθε μικρή νίκη μετράει.', `<form id="progress-form"><label>Τι καταγράφεις;<select name="kind" id="log-kind"><option value="lift">Άσκηση με βάρη</option><option value="bodyweight">Σωματικό βάρος</option></select></label><label>Ημερομηνία<input type="date" name="logged_on" value="${state.today}" max="${state.today}" required></label><label id="exercise-field">Άσκηση<input name="exercise" placeholder="π.χ. Κάθισμα με μπάρα" maxlength="80" required list="exercise-suggestions"><datalist id="exercise-suggestions">${[...new Set(['Κάθισμα με μπάρα', 'Άρση θανάτου', 'Πιέσεις στήθους με αλτήρες', 'Πιέσεις ώμων', ...state.data.logs.filter(l => l.kind === 'lift').map(l => l.exercise)])].map(n => `<option value="${esc(n)}"></option>`).join('')}</datalist></label><div class="form-row"><label>Βάρος σε κιλά<input name="weight" type="number" min="0" max="1000" step="0.1" placeholder="π.χ. 40" required></label><label id="reps-field">Επαναλήψεις<input name="reps" type="number" min="1" max="1000" placeholder="π.χ. 8" required></label></div><label>Μια σημείωση για σένα <span class="optional">προαιρετικό</span><textarea name="note" rows="3" maxlength="500" placeholder="Πώς αισθάνθηκες;"></textarea></label><div class="form-error" role="alert"></div><button type="submit" class="btn dark full">Αποθήκευση προόδου ${icon('check')}</button></form>`, 'Μια άσκηση, μια καταγραφή, ένα βήμα μπροστά. Σημείωσέ το.');
  $('#log-kind').onchange = e => { const lift = e.target.value === 'lift'; $('#exercise-field').hidden = !lift; $('#reps-field').hidden = !lift; $('[name=exercise]', $('#progress-form')).required = lift; $('[name=reps]', $('#progress-form')).required = lift; $('[name=weight]', $('#progress-form')).min = lift ? '0' : '0.1'; };
  bindForm($('#progress-form'), async data => { await api('/progress', { method: 'POST', body: data }); await refresh(); closeModal(); toast('Η πρόοδός σου καταγράφηκε. Καλή δουλειά.'); });
}

function memberForm() {
  modal('Νέο μέλος', `<form id="member-form"><div class="form-row"><label>Όνομα<input name="first_name" maxlength="39" autocomplete="given-name" required></label><label>Επώνυμο<input name="surname" maxlength="39" autocomplete="family-name" required></label></div><label>Email επικοινωνίας <span class="optional">προαιρετικό</span><input name="email" type="email" maxlength="254" autocomplete="email"></label><label>Κινητό με κωδικό χώρας<input name="phone" type="tel" autocomplete="tel" maxlength="16" pattern="[+][1-9][0-9]{7,14}" placeholder="+35799123456" required></label><p class="small muted">Το σύστημα δημιουργεί μοναδικό όνομα χρήστη και προσωρινό κωδικό και τα στέλνει με SMS. Με ελληνικό όνομα δημιουργείται τυχαίο username. Στην πρώτη σύνδεση το μέλος επιλέγει νέο κωδικό.${state.demo ? ' Στη δοκιμή δεν στέλνονται SMS.' : ''}</p><label>Στόχος <span class="optional">προαιρετικό</span><textarea name="goal" rows="2" maxlength="300"></textarea></label><label>Προτεραιότητα <span class="optional">προαιρετικό</span><input name="priority" maxlength="300"></label><div class="form-error" role="alert"></div><button type="submit" class="btn dark full">Δημιουργία και αποστολή SMS ${icon('arrow')}</button></form>`);
  bindForm($('#member-form'), async data => { const result = await api('/owner/members', { method: 'POST', body: { ...data, delivery_channel: 'sms' } }); await refresh(); accessForm(result.id, result); toast(result.delivery_error ? 'Το μέλος δημιουργήθηκε, αλλά η αποστολή δεν επιβεβαιώθηκε.' : 'Το μέλος δημιουργήθηκε. Όρισε τώρα την πρόσβασή του.', !!result.delivery_error); });
}

function deliveryFields(channel = 'email', phone = '') {
  return `<label>Αποστολή πρόσκλησης<select name="delivery_channel"><option value="email" ${channel === 'email' ? 'selected' : ''}>Email</option><option value="sms" ${channel === 'sms' ? 'selected' : ''}>SMS</option></select></label><label data-phone-field ${channel === 'sms' ? '' : 'hidden'}>Κινητό με κωδικό χώρας<input name="phone" type="tel" autocomplete="tel" maxlength="16" pattern="[+][1-9][0-9]{7,14}" placeholder="+35799123456" value="${esc(phone)}" ${channel === 'sms' ? 'required' : 'disabled'}></label>`;
}

function bindDeliveryFields(form) {
  if (!$('[name=delivery_channel]', form)) return;
  $('[name=delivery_channel]', form).onchange = e => {
    const sms = e.target.value === 'sms';
    $('[data-phone-field]', form).hidden = !sms;
    $('[name=phone]', form).required = sms;
    $('[name=phone]', form).disabled = !sms;
  };
}

function invitationLabel(invite) {
  if (!invite) return '';
  return ({ demo: 'Δοκιμαστική πρόσκληση · χωρίς αποστολή', pending: 'Η αποστολή δεν έχει επιβεβαιωθεί', accepted: 'Υποβλήθηκε για αποστολή · αναμονή ενεργοποίησης', failed: 'Η αποστολή δεν επιβεβαιώθηκε · ξαναστείλε πρόσκληση', expired: 'Η πρόσκληση έληξε · ξαναστείλε πρόσκληση', used: 'Ο λογαριασμός ενεργοποιήθηκε' })[invite.status] || 'Αναμονή ενεργοποίησης';
}

function invitationPanel(member, result) {
  const invite = member.invitation;
  if (!invite) return '';
  const temporary = invite.kind === 'temporary_password';
  return `<section class="invitation-panel"><h3>${temporary ? 'Στοιχεία σύνδεσης με SMS' : 'Πρόσκληση μέλους'}</h3><p role="status">${esc(invitationLabel(invite))}</p><p class="small muted">${invite.channel === 'sms' ? 'SMS' : 'Email'} · ${esc(invite.recipient)}</p>${result?.delivery_error ? `<p class="form-error" role="alert">${esc(result.delivery_error)}</p>` : ''}${result?.demo_activation_url ? `<a class="btn outline small" href="${esc(result.demo_activation_url)}" target="_blank" rel="noopener">Προεπισκόπηση ενεργοποίησης ${icon('arrow')}</a>` : ''}${result?.demo_credentials ? `<p class="small muted">Μόνο για τη δοκιμή · Username: <strong>${esc(result.demo_credentials.username)}</strong><br>Προσωρινός κωδικός: <code>${esc(result.demo_credentials.temporary_password)}</code></p>` : ''}${invite.used_at === null ? `<form id="invitation-form">${temporary ? `<label>Κινητό<input name="phone" type="tel" value="${esc(invite.recipient)}" pattern="[+][1-9][0-9]{7,14}" maxlength="16" required></label>` : deliveryFields(invite.channel, invite.channel === 'sms' ? invite.recipient : '')}<p class="small muted">${temporary ? 'Η νέα αποστολή ακυρώνει τον προηγούμενο προσωρινό κωδικό.' : 'Η νέα πρόσκληση ακυρώνει τον προηγούμενο σύνδεσμο.'} Μπορείς να ξαναστείλεις μετά από ένα λεπτό.</p><div class="form-error" role="alert"></div><button class="btn outline small" type="submit">Νέα αποστολή πρόσκλησης ${icon('arrow')}</button></form>` : ''}</section>`;
}

function accessForm(uid, deliveryResult = null) {
  const member = state.owner.members.find(m => m.id === uid);
  modal('Συνδρομή: ' + esc(member.name) + '.', `<div class="member-modal-card"><span class="avatar">${esc(initials(member.name))}</span><div><strong>${esc(member.name)}</strong><small>${esc(member.username)} · ID ${member.id}</small>${member.email ? `<small>${esc(member.email)}</small>` : ''}</div></div>${member.goal ? `<p class="small muted">Στόχος: ${esc(member.goal)}</p>` : ''}${member.priority ? `<p class="small muted">Προτεραιότητα: ${esc(member.priority)}</p>` : ''}<h3 class="modal-section-title">Μήνες συνδρομής</h3><div class="access-list">${member.access.map(a => `<div><div><strong>${monthName(a.month)}</strong><small>${a.weekly_limit} κρατήσεις ανά εβδομάδα</small></div><button class="icon-btn" data-revoke="${a.month}" aria-label="Αφαίρεση πρόσβασης για ${monthName(a.month)}">${icon('trash')}</button></div>`).join('') || '<p class="small muted">Δεν υπάρχουν ενεργοί μήνες. Πρόσθεσε τον πρώτο παρακάτω.</p>'}</div><form id="access-form"><h3 class="modal-section-title">Προσθήκη ή αλλαγή πρόσβασης</h3><label>Μήνας έναρξης<input name="month" type="month" value="${state.today.slice(0, 7)}" required></label><div class="form-row"><label>Αριθμός μηνών<input name="months" type="number" value="1" min="1" max="12" required></label><label>Κρατήσεις ανά εβδομάδα<input name="weekly_limit" type="number" value="3" min="1" max="21" required></label></div><p class="small muted">Η πρόσβαση καλύπτει τους επιλεγμένους μήνες. Οι υπάρχοντες μήνες ενημερώνονται με το νέο όριο. Οι υπάρχουσες κρατήσεις διατηρούνται αν μειωθεί το όριο.</p><div class="form-error" role="alert"></div><button type="submit" class="btn dark full">Αποθήκευση πρόσβασης ${icon('check')}</button></form>`);
  $('.member-modal-card').insertAdjacentHTML('afterend', invitationPanel(member, deliveryResult));
  $('.member-modal-card').insertAdjacentHTML('afterend', `<form id="member-username-form"><label>Όνομα χρήστη<input name="username" value="${esc(member.username)}" minlength="3" maxlength="32" pattern="[a-zA-Z0-9][a-zA-Z0-9._\\-]{2,31}" autocapitalize="none" spellcheck="false" required></label><p class="small muted">Το ID παραμένει ίδιο. Μετά από αλλαγή ενημέρωσε το μέλος για το νέο όνομα σύνδεσης.</p><div class="form-error" role="alert"></div><button class="btn outline small" type="submit">Αλλαγή username</button></form>`);
  bindForm($('#member-username-form'), async data => { await api('/owner/members/' + uid + '/username', {method:'PUT',body:data}); await refresh(); accessForm(uid); toast('Το όνομα χρήστη ενημερώθηκε.'); });
  if ($('#invitation-form')) {
    bindDeliveryFields($('#invitation-form'));
    bindForm($('#invitation-form'), async data => {
      const result = await api('/owner/members/' + uid + '/invitation', { method: 'POST', body: data });
      await refresh(); accessForm(uid, result);
    });
  }
  bindForm($('#access-form'), async data => { await api('/owner/members/' + uid + '/access', { method: 'PUT', body: data }); await refresh(); accessForm(uid, deliveryResult); toast('Η πρόσβαση της συνδρομής ενημερώθηκε.'); });
  document.querySelectorAll('[data-revoke]').forEach(b => b.onclick = () => confirmAction('Αφαίρεση πρόσβασης για αυτόν τον μήνα;', `Η πρόσβαση για ${monthName(b.dataset.revoke)} και όλες οι μελλοντικές κρατήσεις αυτού του μήνα θα αφαιρεθούν για το μέλος ${member.name}.`, async () => { await api(`/owner/members/${uid}/access/${b.dataset.revoke}`, { method: 'DELETE' }); await refresh(); toast('Η πρόσβαση αφαιρέθηκε και οι μελλοντικές θέσεις ελευθερώθηκαν.'); }));
}

function categoryManager() {
  const categories = state.owner.categories;
  modal('Κατηγορίες προγράμματος', `<div class="access-list">${categories.map(name => `<div><strong>${esc(name)}</strong><button class="icon-btn" data-delete-category="${esc(name)}" aria-label="Διαγραφή κατηγορίας ${esc(name)}">${icon('trash')}</button></div>`).join('')}</div><form id="category-form"><label>Νέα κατηγορία<input name="name" minlength="2" maxlength="30" placeholder="π.χ. Lower Body" required></label><div class="form-error" role="alert"></div><button class="btn dark full" type="submit">${icon('plus')} Προσθήκη κατηγορίας</button></form>`, 'Πρόσθεσε τις κατηγορίες που χρησιμοποιείς όταν οργανώνεις τα μαθήματα.');
  bindForm($('#category-form'), async data => {
    await api('/owner/categories', { method: 'POST', body: data });
    await loadData(); categoryManager(); toast('Η κατηγορία προστέθηκε.');
  });
  document.querySelectorAll('[data-delete-category]').forEach(button => button.onclick = () => {
    const name = button.dataset.deleteCategory;
    confirmAction('Διαγραφή κατηγορίας;', `Να διαγραφεί η κατηγορία ${name};`, async () => {
      await api('/owner/categories/' + encodeURIComponent(name), { method: 'DELETE' });
      await loadData(); categoryManager(); toast('Η κατηγορία διαγράφηκε.');
    });
  });
}

function classForm(c = null, duplicate = false) {
  const categories = state.owner.categories;
  const d = c || { title: '', starts_at: `${state.day < state.today ? state.today : state.day || state.today}T18:00`, duration: 50, capacity: 6, category: categories[0], coach: state.user.name.split(' ')[0], description: '', warmup: '', main: '', finisher: '' };
  const editing = c && !duplicate;
  modal(editing ? 'Προσάρμοσε την προπόνηση.' : duplicate ? 'Αντίγραφο προπόνησης' : 'Δημιούργησε μια καλή προπόνηση.', `<form id="class-form"><label>Τίτλος μαθήματος<input name="title" value="${esc(d.title)}" minlength="2" maxlength="80" placeholder="π.χ. Βάσεις δύναμης για όλο το σώμα" required></label><div class="form-row"><label>Ημερομηνία και ώρα<input name="starts_at" type="datetime-local" value="${d.starts_at}" required></label><label>Είδος προπόνησης<select name="category">${categories.map(cat => `<option value="${esc(cat)}" ${d.category === cat ? 'selected' : ''}>${esc(categoryLabel(cat))}</option>`).join('')}</select></label></div><div class="form-row"><label>Διάρκεια σε λεπτά<input name="duration" type="number" value="${d.duration}" min="15" max="180" required></label><label>Διαθέσιμες θέσεις<input name="capacity" type="number" value="${d.capacity}" min="1" max="50" required></label></div><label>Προπονητής<input name="coach" value="${esc(d.coach)}" minlength="2" maxlength="80" required></label><label>Τι περιλαμβάνει το μάθημα<textarea name="description" rows="2" minlength="5" maxlength="800" placeholder="Μια σύντομη περιγραφή της προπόνησης." required>${esc(d.description)}</textarea></label><label>01 · Προθέρμανση<textarea name="warmup" rows="3" minlength="3" maxlength="800" placeholder="Γράψε τις ασκήσεις προθέρμανσης, μία ανά γραμμή." required>${esc(d.warmup)}</textarea></label><label>02 · Κυρίως πρόγραμμα<textarea name="main" rows="4" minlength="3" maxlength="1600" placeholder="Ασκήσεις, σετ, επαναλήψεις και διαλείμματα. Μία άσκηση ανά γραμμή." required>${esc(d.main)}</textarea></label><label>03 · Τελικό μέρος και αποθεραπεία<textarea name="finisher" rows="3" minlength="3" maxlength="800" placeholder="Η τελική προσπάθεια και λίγος χρόνος για αποθεραπεία." required>${esc(d.finisher)}</textarea></label><div class="form-error" role="alert"></div><button type="submit" class="btn dark full">${editing ? 'Αποθήκευση αλλαγών' : 'Προσθήκη στο πρόγραμμα'} ${icon('check')}</button></form>`, `Όλες οι ώρες είναι στη ζώνη ${esc(state.timezone || 'ώρας του προπονητηρίου')}. Τα μέλη βλέπουν ολόκληρο το πρόγραμμα.`);
  bindForm($('#class-form'), async data => { await api('/owner/classes' + (editing ? '/' + c.id : ''), { method: editing ? 'PUT' : 'POST', body: data }); state.month = data.starts_at.slice(0, 7); state.day = data.starts_at.slice(0, 10); state.week = monday(state.day); await refresh(); closeModal(); toast(editing ? 'Το μάθημα ενημερώθηκε.' : 'Η προπόνηση προστέθηκε στο πρόγραμμα.'); });
}

function renderFirstPassword() {
  closeModal();
  app.innerHTML = `<main class="portal-entry"><section class="login-card portal-login"><div class="portal-brand">${logo()}</div><h1>Νέος κωδικός</h1><p>Για να συνεχίσεις, όρισε τον προσωπικό σου κωδικό.</p><form id="first-password-form"><label>Νέος κωδικός<input name="new_password" type="password" autocomplete="new-password" required></label><label>Επανάληψη κωδικού<input name="confirm_password" type="password" autocomplete="new-password" required></label><div class="form-error" role="alert"></div><button class="btn dark full" type="submit">Αποθήκευση και συνέχεια ${icon('arrow')}</button></form><button class="text-link" id="first-password-logout" type="button">Αποσύνδεση</button></section></main>`;
  bindForm($('#first-password-form'), async data => {
    if (data.new_password !== data.confirm_password) throw new Error('Οι κωδικοί δεν ταιριάζουν.');
    await api('/password', {method:'PUT',body:{new_password:data.new_password}});
    $('#first-password-form').reset();
    const result = await api('/session'); state.user = result.user; state.csrf = result.csrf;
    state.page = isOwner() ? 'overview' : 'schedule';
    await loadData(); selectNextDay(); renderApp(); window.scrollTo(0,0);
  });
  $('#first-password-logout').onclick = async () => { try { await api('/logout',{method:'POST'}); state.user=null; const result=await api('/session'); state.csrf=result.csrf; renderLanding(); } catch(e) { toast(e.message,true); } };
}

function renderActivation(token) {
  closeModal();
  app.innerHTML = `<main class="activation-page"><section class="login-card"><div class="login-card-top">${logo()}</div><h1>Καλώς ήρθες στην παρέα.</h1><p>Διάλεξε τον προσωπικό σου κωδικό για να ενεργοποιήσεις τον λογαριασμό σου.</p><form id="activation-form"><label>Νέος κωδικός<input name="new_password" type="password" autocomplete="new-password" required></label><label>Επανάληψη κωδικού<input name="confirm_password" type="password" autocomplete="new-password" required></label><div class="form-error" role="alert"></div><button class="btn dark full" type="submit">Ενεργοποίηση λογαριασμού ${icon('arrow')}</button></form></section></main>`;
  bindForm($('#activation-form'), async data => {
    if (data.new_password !== data.confirm_password) throw new Error('Οι κωδικοί δεν ταιριάζουν.');
    const result = await api('/invitations/accept', { method: 'POST', body: { token, new_password: data.new_password } });
    app.innerHTML = `<main class="activation-page"><section class="login-card"><div class="login-card-top">${logo()}</div><h1>Ο λογαριασμός σου είναι έτοιμος.</h1><p>Συνδέσου με όνομα χρήστη <strong>${esc(result.username)}</strong> και τον κωδικό που μόλις όρισες.</p><a class="btn dark full" href="/">Μετάβαση στη σύνδεση ${icon('arrow')}</a></section></main>`;
  });
}

function openInvitationFromLocation() {
  const token = new URLSearchParams(location.hash.slice(1)).get('activate');
  if (!token) return false;
  history.replaceState(null, '', location.pathname + location.search);
  renderActivation(token);
  return true;
}

window.addEventListener('hashchange', () => { if (state.csrf) openInvitationFromLocation(); });

async function init() {
  try {
    const result = await api('/session');
    Object.assign(state, { user: result.user, csrf: result.csrf, demo: result.demo, today: result.today, timezone: result.timezone, month: result.today.slice(0, 7), week: monday(result.today), day: result.today });
    if (openInvitationFromLocation()) return;
    if (state.user?.must_change_password) { renderFirstPassword(); return; }
    if (state.user) { state.page = isOwner() ? 'overview' : 'schedule'; await loadData(); selectNextDay(); renderApp(); }
    else renderLanding();
  } catch (e) { app.innerHTML = `<div class="boot">${logo()}<h2>Δεν μπορέσαμε να ανοίξουμε τον χώρο σου.</h2><p>${esc(e.message)}</p><button class="btn dark" id="retry-init">Δοκίμασε ξανά</button></div>`; $('#retry-init').onclick = init; }
}
init();
