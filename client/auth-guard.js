/**
 * auth-guard.js  — MySQL JWT + RBAC version
 * ─────────────────────────────────────────────────────────────
 * 1. Reads JWT from localStorage (set after MySQL login)
 * 2. Redirects to auth.html if no valid token
 * 3. Hides/shows sidebar tabs based on role:
 *    Admin  → Dashboard, Upload, Download, History, Audit Ledger
 *             + "Advanced Admin Panel" button  ← NEW
 *    User   → Upload, Download, History  (no Dashboard, no Ledger,
 *             no Admin Panel button)
 * 4. Injects user badge + logout button
 * 5. Exposes window.pbLogout() and window.pbToken()
 */

(function PhantomBoxAuthGuard() {
    'use strict';

    const AUTH_PAGE    = 'auth.html';
    const TOKEN_KEY    = 'pb_token';
    const USER_KEY     = 'pb_user';
    const LOGIN_AT_KEY = 'pb_loginAt';
    const TTL_MS       = 24 * 60 * 60 * 1000; // 24 h

    // ── 1. Read session ──────────────────────────────────────
    function getSession() {
        try {
            const token   = localStorage.getItem(TOKEN_KEY);
            const user    = JSON.parse(localStorage.getItem(USER_KEY) || 'null');
            const loginAt = parseInt(localStorage.getItem(LOGIN_AT_KEY) || '0', 10);
            if (!token || !user) return null;
            if (Date.now() - loginAt > TTL_MS) {
                clearSession();
                return null;
            }
            return { token, user };
        } catch (e) {
            return null;
        }
    }

    function clearSession() {
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem(USER_KEY);
        localStorage.removeItem('pb_role');
        localStorage.removeItem(LOGIN_AT_KEY);
    }

    // ── 2. Redirect if not logged in ─────────────────────────
    const session = getSession();
    if (!session) {
        window.location.replace(AUTH_PAGE);
        return;
    }

    const { token, user } = session;
    const isAdmin = user.role === 'Admin';

    // ── 3. Expose globals ────────────────────────────────────
    window.pbToken   = () => token;
    window.pbUser    = () => user;
    window.pbIsAdmin = () => isAdmin;

    window.pbLogout = function () {
        clearSession();
        window.location.replace(AUTH_PAGE);
    };

    // ── 4. RBAC — hide/show nav items ───────────────────────
    function applyRBAC() {
        const navItems = document.querySelectorAll('.nav-item');
        navItems.forEach(btn => {
            const text = btn.textContent.trim().toLowerCase();

            if (!isAdmin) {
                // User: hide Dashboard and Audit Ledger
                if (text.includes('dashboard') || text.includes('ledger') || text.includes('audit')) {
                    btn.style.display = 'none';
                }
            }
        });

        // If User, default landing page should be Upload not Dashboard
        if (!isAdmin) {
            const dashSection   = document.getElementById('view-dashboard');
            const uploadSection = document.getElementById('view-upload');
            if (dashSection && uploadSection) {
                dashSection.classList.remove('active');
                uploadSection.classList.add('active');
                const navItems = document.querySelectorAll('.nav-item');
                navItems.forEach(btn => {
                    btn.classList.remove('active');
                    if (btn.textContent.trim().toLowerCase().includes('upload')) {
                        btn.classList.add('active');
                    }
                });
            }
        }
    }

    // ── 5. Inject user badge ─────────────────────────────────
    function injectUserBadge() {
        const sidebar = document.querySelector('.sidebar');
        if (!sidebar || document.getElementById('pb-user-badge')) return;

        const initial   = (user.first_name || user.email || '?')[0].toUpperCase();
        const shortName = user.first_name || user.email.split('@')[0];
        const roleColor = isAdmin ? '#f5a623' : '#2a7de1';
        const roleLabel = isAdmin ? '🛡️ Admin' : '👤 User';

        const badge = document.createElement('div');
        badge.id = 'pb-user-badge';
        badge.style.cssText = 'margin-top:auto;padding-top:1.25rem;border-top:1px solid rgba(255,255,255,0.07);';
        badge.innerHTML = `
            <div style="display:flex;align-items:center;gap:.75rem;padding:.85rem 1rem;
                        background:rgba(42,125,225,0.08);border:1px solid rgba(42,125,225,0.15);
                        border-radius:12px;margin-bottom:.75rem;">
                <div style="width:36px;height:36px;background:linear-gradient(135deg,${roleColor},${isAdmin?'#c47d00':'#1a5cb0'});
                            border-radius:10px;display:flex;align-items:center;justify-content:center;
                            font-weight:700;font-size:.95rem;color:white;flex-shrink:0;">
                    ${initial}
                </div>
                <div style="flex:1;overflow:hidden;min-width:0;">
                    <div style="font-weight:600;font-size:.88rem;color:#e8edf5;
                                white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
                        ${shortName}
                        <span style="font-size:.7rem;margin-left:.35rem;padding:.1rem .4rem;
                                     background:${roleColor}22;color:${roleColor};border-radius:4px;">
                            ${roleLabel}
                        </span>
                    </div>
                    <div style="font-size:.72rem;color:#64748b;white-space:nowrap;
                                overflow:hidden;text-overflow:ellipsis;font-family:monospace;">
                        ${user.email}
                    </div>
                </div>
            </div>
            <button onclick="window.pbLogout()" style="
                width:100%;padding:.7rem 1rem;background:transparent;
                border:1px solid rgba(240,75,75,0.25);border-radius:10px;
                color:#f87171;font-family:'Syne','Inter',sans-serif;font-size:.83rem;
                font-weight:600;cursor:pointer;display:flex;align-items:center;
                justify-content:center;gap:.6rem;transition:all .3s;"
                onmouseover="this.style.background='rgba(240,75,75,0.1)'"
                onmouseout="this.style.background='transparent'">
                <i class="fa-solid fa-right-from-bracket"></i> Sign Out
            </button>
        `;
        sidebar.appendChild(badge);
    }

    // ── 6. NEW: Advanced Admin Panel button (Admin only) ─────
    function injectAdminPanelButton() {
        // Guard: only inject once and only for admins
        if (!isAdmin) return;
        if (document.getElementById('pb-admin-panel-btn')) return;

        const navMenu = document.querySelector('.nav-menu');
        if (!navMenu) return;

        // Thin separator line above the button
        const sep = document.createElement('div');
        sep.style.cssText = [
            'height:1px',
            'background:rgba(255,255,255,0.07)',
            'margin:0.75rem 0 0.5rem 0',
        ].join(';');
        navMenu.appendChild(sep);

        // Section label (same pattern as other sidebar sections if you had them)
        const label = document.createElement('div');
        label.style.cssText = [
            'font-size:0.65rem',
            'font-family:monospace',
            'letter-spacing:1.5px',
            'text-transform:uppercase',
            'color:#64748b',
            'padding:0 0.5rem',
            'margin-bottom:0.4rem',
        ].join(';');
        label.textContent = 'Admin Tools';
        navMenu.appendChild(label);

        // The button itself — reuses .nav-item for consistent sizing,
        // but overrides colours to the amber/warning palette
        const btn = document.createElement('button');
        btn.id = 'pb-admin-panel-btn';
        btn.className = 'nav-item';
        btn.setAttribute('title', 'Open the Advanced Admin Control Panel');
        btn.style.cssText = [
            'border:1px solid rgba(245,158,11,0.3)',
            'color:#f5a623',
            'background:rgba(245,158,11,0.08)',
            'transition:background 0.25s ease,border-color 0.25s ease,transform 0.25s ease',
            'font-weight:600',
        ].join(';');

        btn.innerHTML = `
            <i class="fa-solid fa-user-shield"
               style="color:#f5a623;font-size:1.05rem;width:20px;text-align:center;flex-shrink:0"></i>
            <span style="flex:1;text-align:left">Advanced Admin Panel</span>
            <i class="fa-solid fa-arrow-up-right-from-square"
               style="font-size:0.65rem;opacity:0.55;flex-shrink:0"></i>
        `;

        // Hover: brighter amber tint + slide right (matches other nav-item hover)
        btn.addEventListener('mouseenter', () => {
            btn.style.background  = 'rgba(245,158,11,0.18)';
            btn.style.borderColor = 'rgba(245,158,11,0.55)';
            btn.style.transform   = 'translateX(5px)';
            btn.style.color       = '#fbbf24';
        });
        btn.addEventListener('mouseleave', () => {
            btn.style.background  = 'rgba(245,158,11,0.08)';
            btn.style.borderColor = 'rgba(245,158,11,0.3)';
            btn.style.transform   = 'translateX(0)';
            btn.style.color       = '#f5a623';
        });

        // Navigate to /admin (same tab — no URL typing needed)
        btn.addEventListener('click', () => {
            window.location.href = '/admin';
        });

        navMenu.appendChild(btn);
    }

    // ── 7. Override switchView to enforce RBAC ───────────────
    function patchSwitchView() {
        const original = window.switchView;
        if (!original) return;
        window.switchView = function(viewId) {
            // Block non-admin from dashboard and ledger
            if (!isAdmin && (viewId === 'dashboard' || viewId === 'ledger')) {
                console.warn(`[RBAC] ${user.role} cannot access "${viewId}"`);
                return;
            }
            original(viewId);
        };
    }

    // ── 8. Apply when DOM is ready ───────────────────────────
    function onReady() {
        applyRBAC();
        injectUserBadge();
        patchSwitchView();
        if (isAdmin) injectAdminPanelButton();   // ← Admin-only button
        console.log(`✅ PhantomBox RBAC: ${user.email} [${user.role}]`);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', onReady);
    } else {
        onReady();
        setTimeout(onReady, 200); // retry for async-loaded nav
    }

})();