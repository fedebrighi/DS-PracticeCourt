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