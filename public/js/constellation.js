/* ===========================================================
   Clause Constellation — LexGuard AI
   A living network of DPDP 2023 clause nodes connected by
   compliance pathways, with coloured data-particles flowing
   through the graph.
   =========================================================== */
(function () {
    'use strict';

    /* ── Real DPDP 2023 clause labels ── */
    const CLAUSE_LABELS = [
        '§4 Consent',      '§5 Notice',          '§6 Purpose',
        '§7 Data Quality',  '§8 Breach',          '§8(6) Timeline',
        '§9 Fiduciary',     '§10 Processor',      '§11 Transfer',
        '§12 Retention',    '§13 Erasure',         '§14 Grievance',
        '§15 Board',        '§16 Penalties',       '§17 Exemptions',
        'Sch.I Consent',    'Sch.II Notice',       'DPA §3.2',
        '§6(3) Consent',    '§8(1) Notify',        '§12(2) Period',
        'Audit',            'Risk Score',           'Compliance',
    ];

    /* ── Tunables ── */
    const CFG = {
        nodeCount:          28,
        connectionDist:     220,
        particleCount:      55,
        nodeSpeed:          0.25,
        particleSpeed:      1.2,
        mouseRepelRadius:   160,
        mouseRepelForce:    0.6,
        labelFont:          '10px "Satoshi", ui-sans-serif, system-ui, sans-serif',
        /* Klein-blue primary */
        pri:  [0, 47, 167],
        /* Particle palette */
        grn:  [74, 222, 128],
        amb:  [251, 191, 36],
        red:  [248, 113, 113],
    };

    let canvas, ctx;
    let W, H, dpr;
    let nodes = [], particles = [];
    let mouse = { x: -9999, y: -9999 };
    let raf, t = 0;

    /* ═══════════════════════════════════
       Node
       ═══════════════════════════════════ */
    class Node {
        constructor() {
            this.x  = Math.random() * W;
            this.y  = Math.random() * H;
            this.z  = Math.random() * 180 - 90;          // parallax depth
            this.vx = (Math.random() - 0.5) * CFG.nodeSpeed;
            this.vy = (Math.random() - 0.5) * CFG.nodeSpeed;
            this.label = CLAUSE_LABELS[Math.floor(Math.random() * CLAUSE_LABELS.length)];
            this.r  = 2.5 + Math.random() * 2.5;
            this.phase = Math.random() * Math.PI * 2;
            this.baseOpacity = 0.25 + Math.random() * 0.35;
        }
        update() {
            /* mouse repulsion */
            const dx = this.x - mouse.x;
            const dy = this.y - mouse.y;
            const d  = Math.sqrt(dx * dx + dy * dy);
            if (d < CFG.mouseRepelRadius && d > 0) {
                const f = (CFG.mouseRepelRadius - d) / CFG.mouseRepelRadius * CFG.mouseRepelForce;
                this.vx += (dx / d) * f;
                this.vy += (dy / d) * f;
            }
            this.vx *= 0.992;
            this.vy *= 0.992;
            this.x += this.vx;
            this.y += this.vy;

            /* wrap */
            if (this.x < -60) this.x = W + 60;
            if (this.x > W + 60) this.x = -60;
            if (this.y < -60) this.y = H + 60;
            if (this.y > H + 60) this.y = -60;

            this.cr = this.r + Math.sin(t * 0.018 + this.phase) * 1.4;
        }
        draw() {
            const scale = 1 + this.z * 0.0008;
            const px = this.x * scale;
            const py = this.y * scale;
            const op = this.baseOpacity;

            /* outer glow */
            const g = ctx.createRadialGradient(px, py, 0, px, py, this.cr * 5);
            g.addColorStop(0, `rgba(${CFG.pri}, ${op * 0.25})`);
            g.addColorStop(1, 'rgba(0,0,0,0)');
            ctx.beginPath();
            ctx.arc(px, py, this.cr * 5, 0, Math.PI * 2);
            ctx.fillStyle = g;
            ctx.fill();

            /* core */
            ctx.beginPath();
            ctx.arc(px, py, this.cr, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(${CFG.pri}, ${op + 0.25})`;
            ctx.fill();

            /* label */
            ctx.font = CFG.labelFont;
            ctx.fillStyle = `rgba(255,255,255,${op * 0.55})`;
            ctx.textAlign = 'left';
            ctx.fillText(this.label, px + this.cr + 7, py + 3.5);
        }
    }

    /* ═══════════════════════════════════
       Particle  (flowing data packet)
       ═══════════════════════════════════ */
    class Particle {
        constructor() { this.spawn(); }
        spawn() {
            /* start near a random node */
            const src = nodes.length
                ? nodes[Math.floor(Math.random() * nodes.length)]
                : { x: Math.random() * W, y: Math.random() * H };
            this.x  = src.x + (Math.random() - 0.5) * 30;
            this.y  = src.y + (Math.random() - 0.5) * 30;
            this.vx = (Math.random() - 0.5) * CFG.particleSpeed;
            this.vy = (Math.random() - 0.5) * CFG.particleSpeed;
            this.life = 1;
            this.decay = 0.003 + Math.random() * 0.006;
            this.r = 0.8 + Math.random() * 1.4;
            /* 70 % green (compliant), 15 % amber, 15 % red */
            const roll = Math.random();
            this.color = roll < 0.70 ? CFG.grn
                       : roll < 0.85 ? CFG.amb
                       :                CFG.red;
        }
        update() {
            /* gently attract toward the nearest node */
            let minD = Infinity, closest = null;
            for (const n of nodes) {
                const d = Math.abs(n.x - this.x) + Math.abs(n.y - this.y);
                if (d < minD) { minD = d; closest = n; }
            }
            if (closest && minD < 200) {
                const dx = closest.x - this.x;
                const dy = closest.y - this.y;
                const d  = Math.sqrt(dx * dx + dy * dy) || 1;
                this.vx += (dx / d) * 0.012;
                this.vy += (dy / d) * 0.012;
            }
            this.vx *= 0.998;
            this.vy *= 0.998;
            this.x += this.vx;
            this.y += this.vy;
            this.life -= this.decay;
            if (this.life <= 0 || this.x < -30 || this.x > W + 30 || this.y < -30 || this.y > H + 30) {
                this.spawn();
            }
        }
        draw() {
            ctx.beginPath();
            ctx.arc(this.x, this.y, this.r, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(${this.color}, ${this.life * 0.45})`;
            ctx.fill();
        }
    }

    /* ═══════════════════════════════════
       Connections (thin Klein-blue lines)
       ═══════════════════════════════════ */
    function drawEdges() {
        const maxD = CFG.connectionDist;
        for (let i = 0; i < nodes.length; i++) {
            for (let j = i + 1; j < nodes.length; j++) {
                const dx = nodes[i].x - nodes[j].x;
                const dy = nodes[i].y - nodes[j].y;
                const d  = Math.sqrt(dx * dx + dy * dy);
                if (d < maxD) {
                    const a = (1 - d / maxD) * 0.14;
                    ctx.beginPath();
                    ctx.moveTo(nodes[i].x, nodes[i].y);
                    ctx.lineTo(nodes[j].x, nodes[j].y);
                    ctx.strokeStyle = `rgba(${CFG.pri}, ${a})`;
                    ctx.lineWidth = 0.6;
                    ctx.stroke();
                }
            }
        }
    }

    /* ═══════════════════════════════════
       Render loop
       ═══════════════════════════════════ */
    function frame() {
        t++;
        ctx.clearRect(0, 0, W, H);
        drawEdges();
        for (const n of nodes)     { n.update(); n.draw(); }
        for (const p of particles) { p.update(); p.draw(); }
        raf = requestAnimationFrame(frame);
    }

    /* ═══════════════════════════════════
       Sizing (retina-aware)
       ═══════════════════════════════════ */
    function resize() {
        const hero = document.querySelector('.hero');
        if (!hero || !canvas) return;
        dpr = Math.min(window.devicePixelRatio || 1, 2);
        W = hero.offsetWidth;
        H = hero.offsetHeight;
        canvas.width  = W * dpr;
        canvas.height = H * dpr;
        canvas.style.width  = W + 'px';
        canvas.style.height = H + 'px';
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    /* ═══════════════════════════════════
       Bootstrap
       ═══════════════════════════════════ */
    function init() {
        canvas = document.getElementById('constellation-canvas');
        if (!canvas) return;
        ctx = canvas.getContext('2d');

        resize();

        /* responsive tuning */
        const isMobile = W < 768;
        const nNodes     = isMobile ? 14 : CFG.nodeCount;
        const nParticles = isMobile ? 25 : CFG.particleCount;

        for (let i = 0; i < nNodes; i++)     nodes.push(new Node());
        for (let i = 0; i < nParticles; i++) particles.push(new Particle());

        /* mouse tracking (hero-relative) */
        const hero = document.querySelector('.hero');
        hero.addEventListener('mousemove', (e) => {
            const r = hero.getBoundingClientRect();
            mouse.x = e.clientX - r.left;
            mouse.y = e.clientY - r.top;
        });
        hero.addEventListener('mouseleave', () => {
            mouse.x = -9999;
            mouse.y = -9999;
        });

        let resizeTimer;
        window.addEventListener('resize', () => {
            clearTimeout(resizeTimer);
            resizeTimer = setTimeout(resize, 120);
        });

        frame();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
