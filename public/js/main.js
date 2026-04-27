/* LexGuard AI — Landing interactions */
(() => {
    'use strict';

    // --- Supabase Early Init ---------------------------------------
    const SUPABASE_URL = window.ENV_SUPABASE_URL || '';
    const SUPABASE_ANON_KEY = window.ENV_SUPABASE_ANON_KEY || '';
    let supabaseClient = null;

    if (typeof supabase !== 'undefined' && SUPABASE_URL && SUPABASE_URL !== 'YOUR_SUPABASE_URL' && SUPABASE_URL !== '') {
        console.log('[LexGuard] Initializing Supabase client early...');
        supabaseClient = supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
        window.__LG_SUPABASE__ = supabaseClient;
    }

    // --- Nav dark state (over hero constellation) ---------------
    // Runs immediately — this script is loaded at end of <body>,
    // so all DOM elements above are already available.
    const navEl  = document.querySelector('.nav');
    const heroEl = document.querySelector('.hero');
    if (navEl && heroEl) {
        navEl.classList.add('nav--dark');
        const navObs = new IntersectionObserver(([e]) => {
            navEl.classList.toggle('nav--dark', e.isIntersecting);
        }, { threshold: 0.05 });
        navObs.observe(heroEl);
    }

    // --- Modal & Auth Logic (Immediate) ----------------------------
    const authModal = document.getElementById('auth-modal');
    const authForm = document.getElementById('auth-form');
    const authTabs = document.querySelectorAll('[data-auth-tab]');
    const authTitle = document.getElementById('auth-title');
    const authSubtitle = document.getElementById('auth-subtitle');
    const authSubmitBtn = document.getElementById('auth-submit-btn');
    const BACKEND = (window.__LEXGUARD_BACKEND__ || '').replace(/\/+$/, '');
    const API = (BACKEND ? BACKEND : '') + '/api';
    const DASHBOARD_URL = window.ENV_DASHBOARD_URL || 'https://lexguard-ai-a8kv79qhvngwsute9api2n.streamlit.app/';
    const createAuthHandoffCode = async (accessToken) => {
        if (!accessToken) return null;
        try {
            const response = await fetch(`${API}/auth/handoff`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${accessToken}` },
            });
            if (!response.ok) return null;
            const data = await response.json();
            return data?.handoff_code || null;
        } catch (_err) {
            return null;
        }
    };
    const buildDashboardUrl = async (session) => {
        const url = new URL(DASHBOARD_URL);
        url.searchParams.set('src', 'landing');
        if (session && session.access_token) {
            const handoffCode = await createAuthHandoffCode(session.access_token);
            if (handoffCode) {
                url.searchParams.set('handoff_code', handoffCode);
            }
        }
        return url.toString();
    };

    const setAuthMode = (mode) => {
        if (!authModal) return;
        const isSignIn = mode === 'signin';
        authTabs.forEach(tab => {
            tab.classList.toggle('active', tab.dataset.authTab === mode);
        });
        if (authTitle) authTitle.textContent = isSignIn ? 'Welcome to LexGuard' : 'Create an Account';
        if (authSubtitle) authSubtitle.textContent = isSignIn ? 'Sign in to your secure workspace.' : 'Join the enterprise compliance engine.';
        if (authSubmitBtn) authSubmitBtn.querySelector('span').textContent = isSignIn ? 'Sign In' : 'Sign Up';
        
        const switchText = document.getElementById('auth-switch-text');
        if (switchText) {
            switchText.innerHTML = isSignIn
                ? 'Don\'t have an account? <a href="#" id="auth-switch-link">Sign Up</a>'
                : 'Already have an account? <a href="#" id="auth-switch-link">Sign In</a>';
            
            const newLink = document.getElementById('auth-switch-link');
            if (newLink) {
                newLink.addEventListener('click', (e) => {
                    e.preventDefault();
                    setAuthMode(isSignIn ? 'signup' : 'signin');
                });
            }
        }
    };

    const closeAuthModal = () => {
        if (authModal) {
            authModal.classList.remove('open');
            document.body.style.overflow = '';
        }
    };

    // --- Unified Modal Trigger (Immediate) ---
    document.addEventListener('click', (e) => {
        const btn = e.target.closest('[data-open-modal]');
        if (!btn) return;

        const modalId = btn.dataset.openModal;
        if (modalId === 'auth') {
            e.preventDefault();
            const mode = btn.dataset.authMode || 'signin';
            if (authModal) {
                authModal.classList.add('open');
                setAuthMode(mode);
                document.body.style.overflow = 'hidden';
            }
        } else if (modalId === 'pilot') {
            e.preventDefault();
            const pilotModal = document.getElementById('pilot-modal');
            if (pilotModal) {
                pilotModal.classList.add('open');
                document.body.style.overflow = 'hidden';
            }
        }
    });

    // Close on backdrop
    document.addEventListener('click', (e) => {
        if (e.target.matches('[data-close-modal]') || e.target.closest('[data-close-modal]')) {
            closeAuthModal();
            const pilotModal = document.getElementById('pilot-modal');
            if (pilotModal) pilotModal.classList.remove('open');
            document.body.style.overflow = '';
        }
    });

    // Close on Escape
    window.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeAuthModal();
            const pilotModal = document.getElementById('pilot-modal');
            if (pilotModal) pilotModal.classList.remove('open');
            document.body.style.overflow = '';
        }
    });

    document.addEventListener('DOMContentLoaded', () => {

        // --- Scroll reveal -----------------------------------------
        const revealables = document.querySelectorAll(
            '.hero-left, .hero-right, .bento-card, .step, .stat, .section-head, .ribbon-inner, .final-inner'
        );
        revealables.forEach(el => el.classList.add('reveal'));

        if ('IntersectionObserver' in window) {
            const io = new IntersectionObserver(entries => {
                entries.forEach(e => {
                    if (e.isIntersecting) {
                        e.target.classList.add('in');
                        io.unobserve(e.target);
                    }
                });
            }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });
            revealables.forEach(el => io.observe(el));
        } else {
            revealables.forEach(el => el.classList.add('in'));
        }

        // --- Smooth anchor scrolling (native handles most) ---------
        document.querySelectorAll('a[href^="#"]').forEach(a => {
            a.addEventListener('click', evt => {
                const id = a.getAttribute('href');
                if (id.length > 1 && document.querySelector(id)) {
                    evt.preventDefault();
                    const target = document.querySelector(id);
                    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    // If the target is the live widget, also focus the textarea so
                    // users on desktop (where the widget is already in view) get
                    // immediate visible feedback.
                    if (id === '#try-it-widget' || id === '#try-it') {
                        setTimeout(() => {
                            const ta = document.getElementById('lg-input');
                            if (ta && !ta.hidden) {
                                ta.focus({ preventScroll: true });
                                // Flash the widget border briefly
                                const widget = document.getElementById('lg-widget');
                                if (widget) {
                                    widget.classList.add('lg-widget-flash');
                                    setTimeout(() => widget.classList.remove('lg-widget-flash'), 900);
                                }
                            }
                        }, 400);
                    }
                }
            });
        });

        // --- Mobile menu toggle ------------------------------------
        const menuBtn = document.querySelector('.menu-btn');
        const navLinks = document.querySelector('.nav-links');
        if (menuBtn && navLinks) {
            menuBtn.addEventListener('click', () => {
                const isOpen = navLinks.classList.toggle('open');
                menuBtn.classList.toggle('open', isOpen);
                menuBtn.setAttribute('aria-expanded', isOpen);
                // Prevent body scroll when menu is open
                document.body.style.overflow = isOpen ? 'hidden' : '';
            });

            // Close menu when a link is clicked
            navLinks.querySelectorAll('a').forEach(link => {
                link.addEventListener('click', () => {
                    navLinks.classList.remove('open');
                    menuBtn.classList.remove('open');
                    menuBtn.setAttribute('aria-expanded', 'false');
                    document.body.style.overflow = '';
                });
            });
        }

        // --- Animate hero meter bars when in view ------------------
        const meterBars = document.querySelectorAll('.visual-meter .tick');
        meterBars.forEach((bar, i) => {
            const h = bar.style.getPropertyValue('--h');
            bar.style.height = '0%';
            bar.style.transition = `height .9s cubic-bezier(.2,.8,.2,1) ${80 * i}ms`;
            if ('IntersectionObserver' in window) {
                const obs = new IntersectionObserver(es => {
                    es.forEach(e => { if (e.isIntersecting) { bar.style.height = h; obs.unobserve(bar); } });
                }, { threshold: 0.4 });
                obs.observe(bar);
            } else {
                bar.style.height = h;
            }
        });

        // --- Subtle parallax on footer mega word -------------------
        const mega = document.querySelector('.footer-mega');
        if (mega) {
            window.addEventListener('scroll', () => {
                const rect = mega.getBoundingClientRect();
                if (rect.top < window.innerHeight && rect.bottom > 0) {
                    const p = (window.innerHeight - rect.top) / (window.innerHeight + rect.height);
                    mega.style.transform = `translateX(${(p - 0.5) * 40}px)`;
                }
            }, { passive: true });
        }
        // --- Pilot modal + form -----------------------------------
        const modal = document.getElementById('pilot-modal');
        const form = document.getElementById('pilot-form');
        const success = modal && modal.querySelector('.modal-success');

        const openModal = () => {
            if (!modal) return;
            modal.classList.add('open');
            modal.setAttribute('aria-hidden', 'false');
            document.body.style.overflow = 'hidden';
            // Focus first field
            setTimeout(() => {
                const first = form && form.querySelector('input, select, textarea');
                if (first) first.focus();
            }, 50);
        };

        const closeModal = () => {
            if (!modal) return;
            modal.classList.remove('open');
            modal.setAttribute('aria-hidden', 'true');
            document.body.style.overflow = '';
            // Reset state so next open shows the form, not success
            if (form && success) {
                setTimeout(() => {
                    form.style.display = '';
                    success.classList.remove('show');
                    form.reset();
                    form.querySelectorAll('.invalid').forEach(el => el.classList.remove('invalid'));
                }, 200);
            }
        };

        document.querySelectorAll('[data-open-modal="pilot"]').forEach(btn => {
            btn.addEventListener('click', evt => {
                evt.preventDefault();
                openModal();
            });
        });

        document.querySelectorAll('[data-close-modal]').forEach(el => {
            el.addEventListener('click', evt => {
                evt.preventDefault();
                closeModal();
            });
        });

        document.addEventListener('keydown', evt => {
            if (evt.key === 'Escape' && modal && modal.classList.contains('open')) {
                closeModal();
            }
        });

        // Form submit — composes a pre-filled mailto and shows success state.
        // To switch to Formspree: replace this handler with a fetch() POST to your
        // endpoint and set <form action="..." method="POST"> in the HTML.
        if (form) {
            // Clear invalid state as the user corrects their input
            form.querySelectorAll('input, select, textarea').forEach(el => {
                el.addEventListener('input', () => el.classList.remove('invalid'));
                el.addEventListener('change', () => el.classList.remove('invalid'));
            });

            form.addEventListener('submit', evt => {
                evt.preventDefault();
                let valid = true;
                form.querySelectorAll('input, select, textarea').forEach(el => {
                    el.classList.remove('invalid');
                    if (el.hasAttribute('required') && !el.value.trim()) {
                        el.classList.add('invalid');
                        valid = false;
                    }
                });
                const email = form.querySelector('#pilot-email');
                if (email && email.value && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.value)) {
                    email.classList.add('invalid');
                    valid = false;
                }
                if (!valid) {
                    const firstInvalid = form.querySelector('.invalid');
                    if (firstInvalid) firstInvalid.focus();
                    return;
                }

                const data = new FormData(form);
                const name = data.get('name') || '';
                const emailVal = data.get('email') || '';
                const company = data.get('company') || '';
                const role = data.get('role') || '';
                const size = data.get('size') || '';
                const message = data.get('message') || '';

                const subject = `LexGuard AI — Pilot Request from ${name} (${company})`;
                const body =
                    `Hi Sujal,

I'd like to explore a LexGuard AI pilot.

— Name: ${name}
— Work email: ${emailVal}
— Company: ${company}
— Role: ${role}
— Company size: ${size}

${message ? 'First agreements to audit:\n' + message + '\n\n' : ''}Looking forward to connecting.

Sent from lexguard-ai landing page.
`;

                const mailto = `mailto:meenasujal60@gmail.com?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
                window.location.href = mailto;

                // Swap to success state
                form.style.display = 'none';
                if (success) success.classList.add('show');
            });
        }

        // --- Scroll reveal includes new sections ------------------
        document.querySelectorAll('.voice-card').forEach(el => {
            if (!el.classList.contains('reveal')) {
                el.classList.add('reveal');
                if ('IntersectionObserver' in window) {
                    const o = new IntersectionObserver(es => {
                        es.forEach(e => { if (e.isIntersecting) { e.target.classList.add('in'); o.unobserve(e.target); } });
                    }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });
                    o.observe(el);
                } else {
                    el.classList.add('in');
                }
            }
        });

    // --- Auth Form Submit Logic (Immediate) ---
    if (authForm) {
        authForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const email = document.getElementById('auth-email').value;
            const password = document.getElementById('auth-password').value;
            const mode = authTabs[0].classList.contains('active') ? 'signin' : 'signup';

            if (!supabaseClient) {
                alert('Supabase is not configured. Please add your URL and Key to js/main.js');
                return;
            }

            if (authSubmitBtn) {
                authSubmitBtn.disabled = true;
                authSubmitBtn.querySelector('span').textContent = 'Processing...';
            }

            try {
                let result;
                if (mode === 'signin') {
                    result = await supabaseClient.auth.signInWithPassword({ email, password });
                } else {
                    result = await supabaseClient.auth.signUp({ email, password });
                }

                if (result.error) throw result.error;

                if (mode === 'signup' && !result.data.session) {
                    alert('Signup successful! Please check your email for verification.');
                } else {
                    window.location.href = await buildDashboardUrl(result.data.session);
                }
            } catch (error) {
                console.error('Auth Error:', error);
                let userFriendlyMsg = 'Authentication failed. Please check your credentials.';
                const errorMsg = error?.message || '';
                if (errorMsg.includes('Invalid login credentials')) userFriendlyMsg = 'Invalid email or password.';
                if (errorMsg.includes('Email not confirmed')) userFriendlyMsg = 'Please verify your email address.';
                alert(userFriendlyMsg);
            } finally {
                if (authSubmitBtn) {
                    authSubmitBtn.disabled = false;
                    authSubmitBtn.querySelector('span').textContent = mode === 'signin' ? 'Sign In' : 'Sign Up';
                }
            }
        });
    }

    if (authTabs) {
        authTabs.forEach(tab => {
            tab.addEventListener('click', () => setAuthMode(tab.dataset.authTab));
        });
    }

    });
})();


document.addEventListener('DOMContentLoaded', () => {
    const themeBtn = document.getElementById('theme-toggle');
    if (!themeBtn) return;
    themeBtn.addEventListener('click', (e) => {
        if (!document.startViewTransition) {
            document.documentElement.classList.toggle('dark');
            return;
        }
        const transition = document.startViewTransition(() => {
            document.documentElement.classList.toggle('dark');
        });
        transition.ready.then(() => {
            const r = Math.hypot(Math.max(e.clientX, innerWidth - e.clientX), Math.max(e.clientY, innerHeight - e.clientY));
            document.documentElement.animate({
                clipPath: [
                    `circle(0px at ${e.clientX}px ${e.clientY}px)`,
                    `circle(${r}px at ${e.clientX}px ${e.clientY}px)`
                ]
            }, {
                duration: 500,
                easing: 'ease-in-out',
                pseudoElement: '::view-transition-new(root)'
            });
        });
    });
});
