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
const hide = el => el.setAttribute('hidden');

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

        state.fields = data.filter(f => f.isActive());

        const sportTypes = [...new Set(state.fields.map(f => f.sport_type))].filter(s => s != null && s !== '');

        dom.sportSelect.innerHTML = <option value="">Select a sport\u2026</option>;

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
    const hours = (slotToMinutes(endTime)) + SLOT_DURATION - slotToMinutes(startTime) / 60;
    const fieldCost = field.price_per_hour * hours;
    const utilityCost = state.utilities
        .filter(u => state.selectedUtilityIds.includes(u.id))
        .reduce((sum, u) => sum + u.price_per_hour * hours, 0);

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
        <input type="checkbox" class="utility-checkbox value="${u.id} />
        <span class="utility-name">${u.name}</span>
        <span class="utility-price">${u.price_per_hour}</span>
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
        const res = await fetch(`${API_BASE}/utilities`);
        const data = await res.json();
        state.utilities = data.filter(u => u.isActive());
        renderUtilities();
    } catch (error) {
        console.error('[UTILITIES] Fetch failed:', error);
        hide(dom.utilitySkeleton);
        show(dom.utilityGrid);
        dom.utilityGrid.innerHTML = '<span style="font-size: 12px; color: var(--text-tertiary)">Utilities Unavailable</span>';
    }
}



