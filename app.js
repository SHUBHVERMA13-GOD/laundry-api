/**
 * app.js - Logic for LaundryFlow Frontend
 */

const API_BASE = window.location.origin;

// State
let currentTab = 'dashboard';
let orders = [];
let stats = {};

// Selectors
const tabButtons = document.querySelectorAll('.sidebar li');
const tabContents = document.querySelectorAll('.tab-content');
const ordersList = document.getElementById('orders-list');
const createOrderForm = document.getElementById('create-order-form');
const itemsContainer = document.getElementById('items-container');
const addItemBtn = document.getElementById('add-item-btn');
const refreshBtn = document.getElementById('refresh-data');
const orderModal = document.getElementById('order-modal');
const modalBody = document.getElementById('modal-body');
const closeModal = document.querySelector('.close-modal');

// --- Initialization ---
document.addEventListener('DOMContentLoaded', () => {
    initApp();
});

function initApp() {
    // Tab switching
    tabButtons.forEach(btn => {
        btn.addEventListener('click', () => switchTab(btn.dataset.tab));
    });

    // Add item row
    addItemBtn.addEventListener('click', () => addItemRow());

    // Form submission
    createOrderForm.addEventListener('submit', handleCreateOrder);

    // Filters
    document.getElementById('filter-status').addEventListener('change', fetchOrders);
    document.getElementById('filter-name').addEventListener('input', debounce(fetchOrders, 500));
    document.getElementById('filter-phone').addEventListener('input', debounce(fetchOrders, 500));
    document.getElementById('global-search').addEventListener('input', debounce((e) => {
        const val = e.target.value;
        if (currentTab !== 'orders') switchTab('orders');
        document.getElementById('filter-name').value = val;
        fetchOrders();
    }, 500));

    // Refresh
    refreshBtn.addEventListener('click', () => {
        refreshBtn.classList.add('fa-spin');
        Promise.all([fetchStats(), fetchOrders()]).finally(() => {
            setTimeout(() => refreshBtn.classList.remove('fa-spin'), 500);
        });
    });

    // Form auto-total calculation
    createOrderForm.addEventListener('input', updateFormTotal);

    // Modal close
    closeModal.addEventListener('click', () => orderModal.style.display = 'none');
    window.onclick = (event) => {
        if (event.target == orderModal) orderModal.style.display = 'none';
    };

    // Initial data fetch
    fetchStats();
    fetchOrders();
    
    // Auto-refresh every 30 seconds
    setInterval(() => {
        fetchStats();
        if (currentTab === 'orders') fetchOrders();
    }, 30000);
}

// --- Navigation ---
function switchTab(tabId) {
    currentTab = tabId;
    
    // Update Sidebar
    tabButtons.forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tabId);
    });

    // Update Content
    tabContents.forEach(content => {
        content.classList.toggle('active', content.id === `tab-${tabId}`);
    });

    // Update Header
    const titles = {
        'dashboard': { t: 'Dashboard Summary', s: 'Real-time business overview' },
        'orders': { t: 'All Orders', s: 'Manage and track customer requests' },
        'new-order': { t: 'Create New Order', s: 'Fill details to start a new laundry job' }
    };
    document.getElementById('page-title').textContent = titles[tabId].t;
    document.getElementById('page-subtitle').textContent = titles[tabId].s;

    if (tabId === 'dashboard') fetchStats();
    if (tabId === 'orders') fetchOrders();
}

// --- API Calls ---
async function fetchStats() {
    try {
        const res = await fetch(`${API_BASE}/dashboard`);
        stats = await res.json();
        updateDashboardUI();
    } catch (err) {
        showToast('Error fetching dashboard stats', 'error');
    }
}

async function fetchOrders() {
    const status = document.getElementById('filter-status').value;
    const name = document.getElementById('filter-name').value;
    const phone = document.getElementById('filter-phone').value;

    let url = `${API_BASE}/orders?`;
    if (status) url += `status=${status}&`;
    if (name) url += `customer_name=${name}&`;
    if (phone) url += `phone=${phone}&`;

    try {
        const res = await fetch(url);
        orders = await res.json();
        renderOrders();
        if (currentTab === 'dashboard') renderRecentActivity();
    } catch (err) {
        showToast('Error fetching orders', 'error');
    }
}

async function handleCreateOrder(e) {
    e.preventDefault();
    
    const items = [];
    const rows = itemsContainer.querySelectorAll('.item-row');
    rows.forEach(row => {
        items.push({
            garment: row.querySelector('[name="garment"]').value,
            quantity: parseInt(row.querySelector('[name="quantity"]').value),
            price_per_item: parseFloat(row.querySelector('[name="price"]').value)
        });
    });

    const payload = {
        customer_name: document.getElementById('customer_name').value,
        phone_number: document.getElementById('phone_number').value,
        items: items
    };

    try {
        const res = await fetch(`${API_BASE}/orders`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (res.ok) {
            showToast('Order created successfully!', 'success');
            createOrderForm.reset();
            resetItemsList();
            updateFormTotal();
            switchTab('dashboard');
            fetchStats();
            fetchOrders();
        } else {
            const data = await res.json();
            let errorMsg = 'Failed to create order';
            if (data.detail && Array.isArray(data.detail)) {
                // Handle Pydantic validation errors
                errorMsg = data.detail.map(err => `${err.loc[err.loc.length - 1]}: ${err.msg}`).join(', ');
            } else if (typeof data.detail === 'string') {
                errorMsg = data.detail;
            }
            showToast(errorMsg, 'error');
        }
    } catch (err) {
        showToast('Network error', 'error');
    }
}

async function updateOrderStatus(orderId, newStatus) {
    try {
        const res = await fetch(`${API_BASE}/orders/${orderId}/status`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: newStatus })
        });

        if (res.ok) {
            showToast(`Order ${orderId} updated to ${newStatus}`, 'success');
            fetchOrders();
            fetchStats();
            orderModal.style.display = 'none';
        }
    } catch (err) {
        showToast('Failed to update status', 'error');
    }
}

// --- UI Rendering ---
function updateDashboardUI() {
    if (!stats || typeof stats.total_orders === 'undefined') return;

    document.getElementById('stat-total-orders').textContent = stats.total_orders;
    
    const revenue = stats.total_revenue || 0;
    document.getElementById('stat-total-revenue').textContent = `₹${revenue.toLocaleString('en-IN', {minimumFractionDigits: 2})}`;
    
    const orders_by_status = stats.orders_by_status || {};
    const processing = orders_by_status['PROCESSING'] || 0;
    const ready = orders_by_status['READY'] || 0;
    
    document.getElementById('stat-processing').textContent = processing;
    document.getElementById('stat-ready').textContent = ready;

    // Render Status Breakdown Bars
    const breakdown = document.getElementById('status-breakdown');
    if (!breakdown) return;
    breakdown.innerHTML = '';
    
    const statuses = ['RECEIVED', 'PROCESSING', 'READY', 'DELIVERED'];
    const colors = ['#6366f1', '#f59e0b', '#10b981', '#64748b'];

    statuses.forEach((s, idx) => {
        const count = orders_by_status[s] || 0;
        const pct = stats.total_orders > 0 ? (count / stats.total_orders) * 100 : 0;
        
        const item = document.createElement('div');
        item.className = 'status-item';
        item.innerHTML = `
            <div class="status-label-row">
                <span>${s}</span>
                <span>${count} (${Math.round(pct)}%)</span>
            </div>
            <div class="status-bar-bg">
                <div class="status-bar-fill" style="width: ${pct}%; background-color: ${colors[idx]}"></div>
            </div>
        `;
        breakdown.appendChild(item);
    });
}

function renderOrders() {
    ordersList.innerHTML = '';
    if (orders.length === 0) {
        ordersList.innerHTML = '<tr><td colspan="7" style="text-align:center; padding: 2rem;">No orders found.</td></tr>';
        return;
    }

    orders.forEach(order => {
        const tr = document.createElement('tr');
        const date = new Date(order.created_at).toLocaleDateString('en-IN', {
            day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit'
        });

        tr.innerHTML = `
            <td><strong>${order.order_id}</strong></td>
            <td>${order.customer_name}</td>
            <td>${order.phone_number}</td>
            <td>₹${order.total_amount.toFixed(2)}</td>
            <td><span class="badge badge-${order.status.toLowerCase()}">${order.status}</span></td>
            <td class="text-muted">${date}</td>
            <td>
                <button class="btn-icon" onclick="viewOrder('${order.order_id}')">
                    <i class="fas fa-eye"></i>
                </button>
            </td>
        `;
        ordersList.appendChild(tr);
    });
}

function renderRecentActivity() {
    const list = document.getElementById('recent-activity');
    list.innerHTML = '';
    
    const recent = orders.slice(0, 5);
    recent.forEach(order => {
        const initials = order.customer_name.split(' ').map(n => n[0]).join('').toUpperCase().substring(0, 2);
        const item = document.createElement('div');
        item.className = 'activity-item';
        
        const timeAgo = getTimeAgo(new Date(order.created_at));
        
        item.innerHTML = `
            <div class="activity-avatar">${initials}</div>
            <div class="activity-details">
                <p><strong>${order.customer_name}</strong> placed an order for <strong>₹${order.total_amount}</strong></p>
                <p class="time">${timeAgo} • ${order.order_id}</p>
            </div>
        `;
        list.appendChild(item);
    });
}

function viewOrder(orderId) {
    const order = orders.find(o => o.order_id === orderId);
    if (!order) return;

    const itemsHtml = order.items.map(item => `
        <div class="modal-item-row">
            <span>${item.garment} x ${item.quantity}</span>
            <span>₹${(item.quantity * item.price_per_item).toFixed(2)}</span>
        </div>
    `).join('');

    const statusOptions = ['RECEIVED', 'PROCESSING', 'READY', 'DELIVERED'];
    const statusBtns = statusOptions.map(s => `
        <button class="btn-status ${order.status === s ? 'active' : ''}" 
                onclick="updateOrderStatus('${order.order_id}', '${s}')">${s}</button>
    `).join('');

    modalBody.innerHTML = `
        <div class="order-detail-header">
            <span class="badge badge-${order.status.toLowerCase()}">${order.status}</span>
            <h2>Order ${order.order_id}</h2>
            <p class="text-muted">Placed on ${new Date(order.created_at).toLocaleString()}</p>
        </div>
        
        <div class="detail-row">
            <span>Customer</span>
            <span>${order.customer_name}</span>
        </div>
        <div class="detail-row">
            <span>Contact</span>
            <span>${order.phone_number}</span>
        </div>
        
        <div class="modal-items">
            <h4>Garment Details</h4>
            ${itemsHtml}
            <div class="detail-row" style="margin-top: 1rem; border-top: 1px dashed var(--border); padding-top: 0.5rem;">
                <strong>Total Amount</strong>
                <strong>₹${order.total_amount.toFixed(2)}</strong>
            </div>
        </div>

        <div class="status-change-section">
            <h4>Update Status</h4>
            <div class="status-buttons">
                ${statusBtns}
            </div>
        </div>
    `;

    orderModal.style.display = 'block';
}

// --- Helpers ---
function addItemRow() {
    const div = document.createElement('div');
    div.className = 'item-row';
    div.innerHTML = `
        <div class="form-group">
            <label>Garment Type</label>
            <input type="text" name="garment" required placeholder="e.g. Shirt">
        </div>
        <div class="form-group">
            <label>Qty</label>
            <input type="number" name="quantity" min="1" value="1" required>
        </div>
        <div class="form-group">
            <label>Price/Unit</label>
            <input type="number" name="price" step="0.1" min="0" required placeholder="0.00">
        </div>
        <button type="button" class="btn-remove-item">
            <i class="fas fa-times"></i>
        </button>
    `;
    
    div.querySelector('.btn-remove-item').addEventListener('click', () => {
        div.remove();
        updateFormTotal();
    });
    
    itemsContainer.appendChild(div);
}

function resetItemsList() {
    itemsContainer.innerHTML = '';
    addItemRow();
}

function updateFormTotal() {
    let total = 0;
    const rows = itemsContainer.querySelectorAll('.item-row');
    rows.forEach(row => {
        const qty = parseInt(row.querySelector('[name="quantity"]').value) || 0;
        const price = parseFloat(row.querySelector('[name="price"]').value) || 0;
        total += qty * price;
    });
    document.getElementById('form-total-amount').textContent = `₹${total.toFixed(2)}`;
}

function showToast(msg, type = 'success') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    const icon = type === 'success' ? 'fa-check-circle' : 'fa-exclamation-circle';
    toast.innerHTML = `<i class="fas ${icon}"></i> <span>${msg}</span>`;
    
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(20px)';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

function getTimeAgo(date) {
    const seconds = Math.floor((new Date() - date) / 1000);
    let interval = seconds / 31536000;
    if (interval > 1) return Math.floor(interval) + " years ago";
    interval = seconds / 2592000;
    if (interval > 1) return Math.floor(interval) + " months ago";
    interval = seconds / 86400;
    if (interval > 1) return Math.floor(interval) + " days ago";
    interval = seconds / 3600;
    if (interval > 1) return Math.floor(interval) + " hours ago";
    interval = seconds / 60;
    if (interval > 1) return Math.floor(interval) + " minutes ago";
    return "just now";
}

// Expose functions to global scope for inline onclicks
window.viewOrder = viewOrder;
window.updateOrderStatus = updateOrderStatus;
