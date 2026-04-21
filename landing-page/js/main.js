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
    });
})();
