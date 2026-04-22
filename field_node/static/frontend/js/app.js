/**
 * @typedef {{id: number, name: string, sport_type: string, price_per_hour: number, is_active: boolean}} Field
 */

const API_BASE = 'http://localhost:8001';
const UTILITY_BASE = 'http://localhost:8002';
const WS_URL = 'ws://localhost:8001/ws/availability';

const SLOT_START_HOUR = 8; /*ORARIO INIZIALE CALENDARIO*/
const SLOT_END_HOUR = 22; /*ORARIO FINALE CALENDARIO*/
const SLOT_DURATION = 30; /*DURATA SLOT CALENDARIO*/
const WS_MAX_RETRIES = 8;
const FEED_MAX = 50;

/* STATO CHE VERRÀ RIEMPITO DURANTE LA PRENOTAZIONE */
const state = {
    fields: [],
    utilities: [],
    selectedFieldId: null,
    selectedDate: null,
    selectedSlots: [],
    selectedUtilityIds: [],
    userId: '',
    bookings: [],
}

/* RIFERIMENTI DEGLI ELEMENTI DEL DOM */

const dom = {
    userId: document.getElementById('user-id'),
    userIdError: document.getElementById('user-id-error'),
    sportSelect: document.getElementById('sport-select'),
    dateInput: document.getElementById('date-input'),
    slotSkeleton: document.getElementById('slot-skeleton'),
    slotGrid: document.getElementById('slot-grid'),
    alertSlotTaken: document.getElementById('alert-slot-taken'),
    utilitySkeleton: document.getElementById('utility-skeleton'),
    utilityGrid: document.getElementById('utility-grid'),
    bookingTotal: document.getElementById('booking-total'),
    alertConflict: document.getElementById('alert-conflict'),
    alert2pc: document.getElementById('alert-2pc'),
    alertNetwork: document.getElementById('alert-network'),
    confirmBtn: document.getElementById('confirm-btn'),
    feedList: document.getElementById('feed-list'),
    feedEmpty: document.getElementById('feed-empty'),
    wsBadge: document.getElementById('ws-badge'),
    wsStatus: document.getElementById('ws-status'),
}

const show = el => el.removeAttribute('hidden');
const hide = el => el.setAttribute('hidden', '');

/* MINUTI TOTALI */
function slotToMinutes(timeStr) {
    const [h, m] = timeStr.split(':').map(Number);
    return h * 60 + m;
}

/* HH:MM*/
function minutesToSlot(mins){
    return `${String(Math.floor(mins / 60)).padStart(2, '0')}:${String(mins % 60).padStart(2, '0')}`;
}

/* GENERA I VARI SLOT*/
function generateTimeSlots() {
    const slots = [];
    for (let m = SLOT_START_HOUR * 60; m < SLOT_END_HOUR * 60; m += SLOT_DURATION){
        slots.push(minutesToSlot(m));
    }
    return slots;
}

/* COSTRUISICE UNA STRINGA ISO DA DATA E SLOT ORARIO*/
function toISO(date, slotTime){
    return `${date}T${slotTime}:00`;
}

/* DA ISO A ORA LOCALE HH::MM*/
function isoToTime(iso){
    return new Date(iso).toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit'});
}

/* DA ISO A DATA LOCALE*/
function isoToDate(iso){
    return new Date(iso).toLocaleDateString('it-IT', { day: '2-digit', month: 'short'});
}

/* LOADING DEI CAMPI*/
async function loadFields(){
    try{
        const res = await fetch(`${API_BASE}/fields`);
        const data = await res.json();

        state.fields = data.filter(f => f.is_active);

        const sportTypes = [...new Set(state.fields.map(f => f.sport_type))].filter(s => s != null && s !== '');

        dom.sportSelect.innerHTML = '<option value="">Select a sport\u2026</option>';

        sportTypes.forEach(sport => {
            const fieldsOfSport = state.fields.filter(f => f.sport_type === sport);
            const group = document.createElement('optgroup');
            group.label = sport[0].toUpperCase() + sport.slice(1);

            fieldsOfSport.forEach(field => {
                const opt = document.createElement('option');
                opt.value = field.id;
                opt.textContent = `${field.name} \u2014 \u20ac${field.price_per_hour}/h`; /* - E /  */
                group.appendChild(opt);
            });
            dom.sportSelect.appendChild(group);
        });
        dom.sportSelect.disabled = false;
    } catch(error) {
        console.error('[FIELDS] Fetch failed:', error);
        dom.sportSelect.innerHTML = '<option value="">Error Loading Fields</option>';
    }
}

/* CALCOLO DEL PREZZO TOTALE */
function calculateTotal() {
    if (!state.selectedFieldId || state.selectedSlots.length < 2) {
        dom.bookingTotal.textContent = '\u2014';
        return;
    }

    const field = state.fields.find(f => f.id === state.selectedFieldId);
    if (!field) { dom.bookingTotal.textContent = '\u2014'; return;}

    const[startTime, endTime] = state.selectedSlots;
    const hours = (slotToMinutes(endTime) + SLOT_DURATION - slotToMinutes(startTime)) / 60;
    const fieldCost = field.price_per_hour * hours;
    const utilityCost = state.utilities
        .filter(u => state.selectedUtilityIds.includes(u.id))
        .reduce((sum, u) => {
            const amount = u.is_hourly ? (u.price_per_hour * hours) : u.price_per_hour
            return sum + amount
        }, 0);

    dom.bookingTotal.textContent = `\u20ac${(fieldCost + utilityCost).toFixed(2)}`;
}

/* RENDERING NELLA PAGINA DELLE UTILITIES */
async function renderUtilities(){
    hide(dom.utilitySkeleton);
    dom.utilityGrid.innerHTML = '';

    if(state.utilities.length === 0){
        dom.utilityGrid.innerHTML = '<span style="font-size: 12px; color: var(--text-tertiary)">No Utilities Available</span>';
        show(dom.utilityGrid);
        return;
    }

    state.utilities.forEach(u => {
        const card = document.createElement('label')
        card.className = 'utility-card';
        card.dataset.utilityId = u.id;
        card.innerHTML = `
        <input type="checkbox" class="utility-checkbox" value="${u.id}" />
        <span class="utility-name">${u.name}</span>
        <span class="utility-price">\u20ac${u.price_per_hour}</span>
        `

        card.addEventListener('change', () => {
            const checked = card.querySelector('input').checked;
            card.classList.toggle('utility-card--selected', checked);

            if(checked){
                state.selectedUtilityIds.push(u.id);
            } else {
                state.selectedUtilityIds = state.selectedUtilityIds.filter(id => id !== u.id);
            }
            calculateTotal();
        });
        dom.utilityGrid.appendChild(card);
    });
    show(dom.utilityGrid);
}

/* LOADING DELLE UTIITIES */
async function loadUtilities(){
    try{
        const res = await fetch(`${UTILITY_BASE}/utilities`);
        const data = await res.json();
        state.utilities = data.filter(u => u.is_active);
        await renderUtilities();
    } catch (error) {
        console.error('[UTILITIES] Fetch failed:', error);
        hide(dom.utilitySkeleton);
        show(dom.utilityGrid);
        dom.utilityGrid.innerHTML = '<span style="font-size: 12px; color: var(--text-tertiary)">Utilities Unavailable</span>';
    }
}

/* RITORNA TRUE SE LO SLOT CHE INIZIA A SLOTTIME SI SOVRAPPONE A UN ALTRA BOOKING*/
function isSlotTaken(slotTime, bookings){
    const slotStart = slotToMinutes(slotTime);
    const slotEnd = slotStart + SLOT_DURATION;

    return bookings.some(b => {
        const status = b.status ? String(b.status).toLowerCase() : '';
        if (!b.start_time || !b.end_time ||  status === 'cancelled' || status === 'aborted' || status === 'failed') return false;

        if (b.field_id !== state.selectedFieldId) return false;

        const bookingDate = b.start_time.substring(0, 10);
        if(bookingDate !== state.selectedDate) return false;

        const bStart = slotToMinutes(b.start_time.substring(11, 16));
        const bEnd = slotToMinutes(b.end_time.substring(11, 16));
        return slotStart < bEnd && slotEnd > bStart;
    })
}

/* CONTROLLO POSSIBILI CONFLITTI NEGLI SLOT*/
function checkRangeConflict(startTime, endTime){
    const startMin = slotToMinutes(startTime);
    const endMin = slotToMinutes(endTime);
    const conflict = generateTimeSlots().filter(s => slotToMinutes(s) >= startMin && slotToMinutes(s) <= endMin).some(s => isSlotTaken(s, state.bookings));
    if(conflict){
        show(dom.alertSlotTaken);
    }
    return conflict;
}

/* AGGIORNAMENTO VISIVO DEGLI SLOT */
function updateSlotHighlights(){
    const [startTime, endTime] = state.selectedSlots;
    const startMin = startTime ? slotToMinutes(startTime) : null;
    const endMin = endTime ? slotToMinutes(endTime) : null;

    dom.slotGrid.querySelectorAll('.slot-pill:not(.slot-pill--taken)').forEach( pill =>{
        const m = slotToMinutes(pill.dataset.time);
        let selected = false;
        if (state.selectedSlots.length === 1){
            selected = m === startMin;
        } else if (state.selectedSlots.length === 2){
            selected = m >= startMin && m <= endMin;
        }
        pill.classList.toggle('slot-pill--selected', selected);
        pill.setAttribute('aria-pressed', selected ? 'true' : 'false');
    });
}

/* SELEZIONE DELLO SLOT */
function handleSlotClick(slotTime){
    if(state.selectedSlots.length === 0 || state.selectedSlots.length === 2){
        state.selectedSlots = [slotTime];
    } else {
        const first = state.selectedSlots[0];

        if(slotTime === first){
            state.selectedSlots = [];
        } else {
            const [a, b] = slotToMinutes(first) <= slotToMinutes(slotTime) ? [first, slotTime] : [slotTime, first];

            if(checkRangeConflict(a, b)){
                state.selectedSlots = [];
            } else {
                hide(dom.alertSlotTaken);
                state.selectedSlots = [a,b];
            }
        }
    }
    updateSlotHighlights();
    calculateTotal();
}

/* RENDERING DEGLI SLOTS NELLA PAGINA*/
async function renderSlots(){
    show(dom.slotSkeleton);
    hide(dom.slotGrid);
    hide(dom.alertSlotTaken);
    state.selectedSlots = [];
    calculateTotal()

    try{
        const res = await fetch(`${API_BASE}/bookings?field_id=${state.selectedFieldId}&date=${state.selectedDate}`);
        if(!res.ok) throw new Error(`HTTP ${res.status}`);
        state.bookings = await res.json();

        dom.slotGrid.innerHTML = '';
        generateTimeSlots().forEach(slotTime => {
            const taken = isSlotTaken(slotTime, state.bookings);
            const pill = document.createElement('button');
            pill.type = 'button';
            pill.className = taken ? 'slot-pill slot-pill--taken' : 'slot-pill';
            pill.textContent = slotTime;
            pill.dataset.time = slotTime;
            pill.disabled = taken;
            pill.setAttribute('aria-label', `Slot ${slotTime}${taken ? ' \u2014 occupato' : ''}`);
            if (!taken) {
                pill.addEventListener('click', () => handleSlotClick(slotTime));
            }
            dom.slotGrid.appendChild(pill);
        });

    }catch (error){
        console.error('[BOOKINGS] Fetch Failed:', error);
        state.bookings = [];
        dom.slotGrid.innerHTML = '<p>Error while loading slot</p>';
    } finally{
            hide(dom.slotSkeleton);
            show(dom.slotGrid);
    }
}

dom.sportSelect.addEventListener('change', () =>{
    const selectedFieldId = parseInt(dom.sportSelect.value);
    const field = state.fields.find(f => f.id === selectedFieldId);
    const previewImg = document.getElementById('sport-preview-img');
    const previewContainer = document.getElementById('sport-preview');

    if (field && field.sport_type) {
        previewImg.src = `imgs/${field.sport_type}.png`; // es: imgs/football.png
        previewContainer.removeAttribute('hidden');
    } else {
        previewContainer.setAttribute('hidden', '');
    }
    state.selectedFieldId = dom.sportSelect.value ? parseInt(dom.sportSelect.value) : null;
    state.selectedSlots = [];
    calculateTotal();
    if(state.selectedFieldId && state.selectedDate) renderSlots();
});

dom.dateInput.addEventListener('change', () =>{
    state.selectedDate = dom.dateInput.value || null;
    state.selectedSlots = [];
    calculateTotal();
    if(state.selectedFieldId && state.selectedDate) renderSlots();
});

/* CANCELLAZIONE PRENOTAZIONE*/
async function deleteBooking(id){
    if(!confirm(`Are you sure to cancel the booking #${id}?`)) return;
    try{
        const res = await fetch(`${API_BASE}/bookings/${id}`, {
        method: 'DELETE'});
        if (!res.ok) {
            const error = await res.json();
            throw new Error(error.detail || "Error while cancelling booking");
        }
        console.log(`Cancellation request sent for #${id}`);
    } catch (error){
        console.error("Delete error:", error);
        alert("Impossible to delete booking" + error.message);
    }
}

/* FEED */
function addFeedEvent(event){
    hide(dom.feedEmpty);

    const type = event.event_type;
    const isConfirmed =  type === 'booking_confirmed';
    const isCancelled = type === 'booking_cancelled';
    const isFailed = type === 'booking_failed';

    let dotClass = 'event-dot--failed';
    if (isConfirmed) dotClass = 'event-dot--confirmed';
    if (isCancelled) dotClass = 'event-dot--cancelled';

    let statusText = 'Booking Failed';
    if (isConfirmed) statusText = 'Booking Confirmed';
    if (isCancelled) statusText = 'Booking Cancelled';

    const isMine = event.user_id === state.userId;

    const startTime = event.start_time ? isoToTime(event.start_time) : '';
    const endTime = event.end_time ? isoToTime(event.end_time) : '';
    const dateStr = event.start_time ? isoToDate(event.start_time) : '';

    const field = state.fields.find(f => f.id === event.field_id);
    const sportIcon = (field && field.sport_type) ? `../imgs/mini-${field.sport_type}.png` : '';

    const li = document.createElement('li')
    li.className = 'feed-event';
    if(event.field_booking_id)  li.setAttribute('data-booking-id', event.field_booking_id);
    li.style.cssText = `opacity:0; transform:translatex(12px)`;

    li.innerHTML = ` 
        <div style="display: flex; align-items: center; width: 100%; gap: 8px;">
            ${sportIcon ? `<img src="${sportIcon}" class="event-sport-icon" alt="">` : ''}
            <span class="event-dot ${dotClass}" aria-hidden="true"></span>
            
            <div class="event-body" style="flex-grow: 1;">
                <span class="event-name">
                    ${statusText}
                    <span class="event-id">#${event.field_booking_id ?? '\u2014'}</span>
                </span>
                <span class="event-meta">Field ${event.field_id ?? '?'} \u00b7 ${event.user_id ?? '\u2014'}</span>
                <span class="event-time" style="display: block">${dateStr} ${startTime} - ${endTime} </span>
            </div>   
            
            ${(isConfirmed && isMine && !event.hideDelete) ? `
                <button onclick="deleteBooking(${event.field_booking_id})" class="btn-delete" title="Cancel Booking">
                    &times;
                </button>
            ` : ''}
        </div>`;
    
    dom.feedList.insertBefore(li, dom.feedList.firstChild);

    /* ANIMAZIONE DI ENTRATA NEL FEED*/
    requestAnimationFrame(() => {
        li.style.transition = 'opacity 250ms ease, transform 250ms ease';
        li.style.opacity = '1';
        li.style.transform = 'translateX(0)';
    });

    while(dom.feedList.children.length > FEED_MAX){
        dom.feedList.removeChild(dom.feedList.lastChild);
    }
}

/* LISTENER SPORT CON ANTEPRIMA GRANDE */
dom.sportSelect.addEventListener('change', () => {
    const selectedFieldId = parseInt(dom.sportSelect.value);
    const field = state.fields.find(f => f.id === selectedFieldId);
    const previewImg = document.getElementById('sport-preview-img');
    const previewContainer = document.getElementById('sport-preview');

    if (field && field.sport_type) {
        previewImg.src = `../imgs/${field.sport_type}.png`;
        show(previewContainer);
    } else {
        hide(previewContainer);
    }

    state.selectedFieldId = selectedFieldId || null;
    state.selectedSlots = [];
    calculateTotal();
    if(state.selectedFieldId && state.selectedDate) renderSlots();
});

/* GESTIONE DELLE WEBSOCKET */

function handleWsEvent(event){
    addFeedEvent(event);
    if(event.event_type === 'booking_cancelled') {
        const selector = `li[data-booking-id="${event.field_booking_id}"] .btn-delete`;
        const oldConfirmedBtn = document.querySelector(selector);
        if (oldConfirmedBtn) {
            oldConfirmedBtn.remove();
        }
    }
    if(event.event_type === 'booking_cancelled' || event.event_type === 'booking_confirmed') {
        if (state.selectedFieldId && state.selectedDate && event.field_id === state.selectedFieldId && event.start_time?.substring(0, 10) === state.selectedDate) {
            renderSlots();
        }
    }
}

function scheduleWsReconnect(){
    if(wsRetry >= WS_MAX_RETRIES){
        console.warn('[WS] Max Retries Reached - Giving Up...');
        return;
    }
    const delay = Math.min(1000 * Math.pow(2, wsRetry), 30_000);
    wsRetry++;
    console.info(`[WS] Reconnect in ${delay}ms (attempt ${wsRetry}/${WS_MAX_RETRIES})`);
    setTimeout(connectWebSocket, delay);
}

let ws = null;
let wsRetry = 0;

function connectWebSocket(){
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
        return
    }
    ws = new WebSocket(WS_URL);
    ws.addEventListener('open', ()=>{
        wsRetry = 0;
        dom.wsBadge.classList.add('live-badge--online');
        dom.wsStatus.textContent = 'LIVE';
        console.info('[WS] Connected!');
    });
    ws.addEventListener('message', e=>{
        try{
            handleWsEvent(JSON.parse(e.data));
        } catch(error){
            console.error('[WS] Parse error:', error);
        }
    });
    ws.addEventListener('close', ()=>{
        dom.wsBadge.classList.remove('live-badge--online');
        dom.wsStatus.textContent = 'OFFLINE';
        scheduleWsReconnect();
    });
    ws.addEventListener('error', () =>{})
}

const USER_ID_RE = /^[a-zA-Z0-9_]{3,32}$/;

/* VALIDAZIONE DELL ID UTENTE */
function validateUserId(){
    const val = dom.userId.value.trim();
    if(!val){
        dom.userIdError.textContent = 'User ID is required!';
        show(dom.userIdError);
        return false;
    }

    if (!USER_ID_RE.test(val)){
        dom.userIdError.textContent = 'UserID must be 3\u201332 alphanumeric characters or underscores.';
        show(dom.userIdError);
        return false;
    }

    hide(dom.userIdError);
    state.userId = val;
    sessionStorage.setItem('court_user_id', val);
    return true;
}

dom.userId.addEventListener('input', () =>{
    if(!dom.userIdError.hidden){
        validateUserId();
    }
})

/* GESTIONE DELLO STATO DEL BOTTONE */
function setBtnState(s){
    dom.confirmBtn.dataset.state = s;
    dom.confirmBtn.disabled = (s === 'loading' || s === 'success');
}

/* CONFERMA DELLA PRENOTAZIONE*/
async function confirmBooking(){
    [dom.alertConflict, dom.alert2pc, dom.alertNetwork].forEach(hide);

    if(!validateUserId()){
        dom.userId.focus();
        return;
    }

    if(!state.selectedFieldId){
        dom.alertConflict.textContent = 'Please select a Field';
        show(dom.alertConflict)
        dom.sportSelect.focus();
        return;
    }

    if(!state.selectedDate){
        dom.alertConflict.textContent = 'Please select a Date';
        show(dom.alertConflict)
        dom.dateInput.focus();
        return;
    }

    if(state.selectedSlots.length < 2){
        dom.alertConflict.textContent = 'Please select a Time Range: click a start slot, then an end slot.';
        show(dom.alertConflict)
        return;
    }

    const [startSlot, endSlot] = state.selectedSlots;
    const endMinutes = slotToMinutes(endSlot)+SLOT_DURATION;
    const startISO = toISO(state.selectedDate, startSlot);
    const endISO = toISO(state.selectedDate, minutesToSlot(endMinutes));

    const body = {
        field_id: state.selectedFieldId,
        user_id: state.userId,
        start_time: startISO,
        end_time: endISO,
        utility_ids: [...state.selectedUtilityIds]
    };
    setBtnState('loading');

    try{
        const res = await fetch(`${API_BASE}/bookings/2pc`,{
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(body),
        });
        if(!res.ok) throw new Error(`HTTP ${res.status}`);

        const data = await res.json();

        if(data.status === 'confirmed'){
            setBtnState('success');

            setTimeout(()=>{
                setBtnState('idle');
                state.selectedSlots = [];
                renderSlots();
            }, 2500);
        } else {
            setBtnState('error');
            dom.alert2pc.textContent = `Transaction Aborted: ${data.reason ?? 'Slot Already Taken'}`;
            show(dom.alert2pc);

            addFeedEvent({
                event_type: 'booking_failed',
                field_id: state.selectedFieldId,
                booking_id: null,
                start_time: startISO,
                end_time: endISO,
                user_id: state.userId,
            });

            setTimeout(()=>{
                setBtnState('idle');
                renderSlots();
            }, 2500);
        }
    } catch (error){
        console.error('[BOOKING] Error:', error);
        setBtnState('error');
        show(dom.alertNetwork);
        setTimeout(()=> setBtnState('idle'), 2500);
    }
}

dom.confirmBtn.addEventListener('click', confirmBooking);

/* CARICA LA CRONOLOGIA DELLE PRENOTAZIONI NEL FEED*/
async function loadFeedHistory() {
    try {
        const res = await fetch(`${API_BASE}/bookings`);
        let history = await res.json();
        history.sort((a, b) => a.id - b.id);

        history.forEach((booking) => {
            const status = String(booking.status).toLowerCase();

            if (status === 'cancelled') {
                addFeedEvent({
                    event_type: 'booking_confirmed',
                    field_booking_id: booking.id,
                    field_id: booking.field_id,
                    user_id: booking.user_id,
                    start_time: booking.start_time,
                    end_time: booking.end_time,
                    hideDelete: true
                });

                addFeedEvent({
                    event_type: 'booking_cancelled',
                    field_booking_id: booking.id,
                    field_id: booking.field_id,
                    user_id: booking.user_id,
                    start_time: booking.start_time,
                    end_time: booking.end_time
                });
            }
            else {
                const eventTypeMap = {
                    'confirmed': 'booking_confirmed',
                    'failed': 'booking_failed'
                };

                addFeedEvent({
                    event_type: eventTypeMap[status] || 'booking_failed',
                    field_booking_id: booking.id,
                    field_id: booking.field_id,
                    user_id: booking.user_id,
                    start_time: booking.start_time,
                    end_time: booking.end_time
                });
            }
        });
    } catch (error) {
        console.error('[FEED] History load failed:', error);
    }
}
/* INIZIALIZZAZIONE*/
async function init(){
    const today = new Date().toISOString().split('T')[0];
    const savedUser = sessionStorage.getItem('court_user_id');
    if(savedUser){
        dom.userId.value = savedUser;
        state.userId = savedUser;
    }
    dom.dateInput.min = today;  // PER NON PRENOTARE DATE PASSATE
    dom.dateInput.value = today;
    state.selectedDate = today;
    setBtnState('idle');
    await Promise.all([loadFields(), loadUtilities()]);
    await loadFeedHistory();
    connectWebSocket();
}

init().catch(console.error);