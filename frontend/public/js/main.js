/* LexGuard AI — Landing interactions */
(() => {
    'use strict';

    document.addEventListener('DOMContentLoaded', () => {
    const themeBtn = document.getElementById('theme-toggle');
    if (!themeBtn) return;
    themeBtn.addEventListener('click', (e) => {
        if (!document.startViewTransition) {
            document.documentElement.classList.toggle('dark');
            return;
        }
        const transition = document.startViewTransition(() => {
            document.documentElement.classList.toggle('dark')<
        });
        transition.ready.then(() => {
            const r = Math.hypot(Math.max(e.clientX, innerWidth - e.clientX), Math.max(e.clientY, innerHeight - e.clientY));
            document.documentElement.animate({
                clipPath: [
                    `circle(0px at ${e.clientX}px ${e.clientY}px)`,
                    `circle(${r}px at ${e.clientX}px ${e.clientY}px)`
                ]
            }, {
                duration: 400,
                easing: 'ease-in-out',
                pseudoElement: '::view-transition-new(root)'
            });
        });
    });
});
