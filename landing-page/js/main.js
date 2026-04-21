/* LexGuard AI — Landing interactions */
(() => {
    'use strict';

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
                    document.querySelector(id).scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
            });
        });

        // --- Mobile menu (lightweight dropdown) --------------------
        const btn = document.querySelector('.menu-btn');
        const nav = document.querySelector('.nav-links');
        if (btn && nav) {
            btn.addEventListener('click', () => {
                const open = nav.classList.toggle('open');
                Object.assign(nav.style, open ? {
                    display: 'flex', flexDirection: 'column', gap: '16px',
                    position: 'fixed', top: '64px', left: 0, right: 0,
                    background: '#fff', padding: '24px',
                    borderBottom: '1px solid rgba(0,0,0,0.08)', zIndex: 49,
                } : { display: '', flexDirection: '', gap: '', position: '', top: '', left: '', right: '', background: '', padding: '', borderBottom: '', zIndex: '' });
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
    });
})();
