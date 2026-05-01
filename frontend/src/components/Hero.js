import { useRef, useEffect, useState } from "react";
import { ArrowRight, Instagram, Twitter, Globe } from "lucide-react";

export default function Hero() {
  const videoRef = useRef(null);
  const fadingOutRef = useRef(false);
  const rafRef = useRef(null);
  const startTimeRef = useRef(null);
  const fromOpacityRef = useRef(0);

  const fadeTo = (targetOpacity, duration = 500) => {
    const video = videoRef.current;
    if (!video) return;

    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current);
    }

    fromOpacityRef.current = parseFloat(video.style.opacity) || 0;
    startTimeRef.current = null;

    const animate = (timestamp) => {
      if (!startTimeRef.current) startTimeRef.current = timestamp;
      const elapsed = timestamp - startTimeRef.current;
      const progress = Math.min(elapsed / duration, 1);
      const current = fromOpacityRef.current + (targetOpacity - fromOpacityRef.current) * progress;
      video.style.opacity = String(current);

      if (progress < 1) {
        rafRef.current = requestAnimationFrame(animate);
      }
    };

    rafRef.current = requestAnimationFrame(animate);
  };

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const handleLoadedData = () => {
      video.style.opacity = "0";
      fadeTo(1, 500);
    };

    const handleTimeUpdate = () => {
      if (!video.duration) return;
      const timeRemaining = video.duration - video.currentTime;
      if (timeRemaining <= 0.55 && !fadingOutRef.current) {
        fadingOutRef.current = true;
        fadeTo(0, 500);
      }
    };

    const handleEnded = () => {
      fadingOutRef.current = false;
      if (rafRef.current) {
        cancelAnimationFrame(rafRef.current);
      }
      video.style.opacity = "0";
      setTimeout(() => {
        video.currentTime = 0;
        video.play().catch(() => {});
        fadeTo(1, 500);
      }, 100);
    };

    video.addEventListener("loadeddata", handleLoadedData);
    video.addEventListener("timeupdate", handleTimeUpdate);
    video.addEventListener("ended", handleEnded);

    return () => {
      video.removeEventListener("loadeddata", handleLoadedData);
      video.removeEventListener("timeupdate", handleTimeUpdate);
      video.removeEventListener("ended", handleEnded);
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, []);

  const [email, setEmail] = useState("");
  const [subscribed, setSubscribed] = useState(false);

  const handleEmailSubmit = (e) => {
    e.preventDefault();
    if (!email.trim()) return;
    console.log("Newsletter subscription:", email);
    setSubscribed(true);
    setEmail("");
    setTimeout(() => setSubscribed(false), 4000);
  };

  const handleManifesto = () => {
    fadingOutRef.current = false;
    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current);
    }
    video.style.opacity = "0";
    setTimeout(() => {
      video.currentTime = 0;
      video.play().catch(() => {});
      fadeTo(1, 500);
    }, 100);
  };

  return (
    <>
      <video
        ref={videoRef}
        className="absolute inset-0 w-full h-full object-cover translate-y-[17%]"
        src="https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260328_115001_bcdaa3b4-03de-47e7-ad63-ae3e392c32d4.mp4"
        muted
        autoPlay
        loop
        playsInline
        style={{ opacity: 0 }}
      />

      <div className="relative z-10 flex-1 flex flex-col items-center justify-center px-6 py-12 text-center -translate-y-[20%]">
        <h1
          className="text-5xl md:text-6xl lg:text-7xl text-white mb-8 tracking-tight whitespace-nowrap"
          style={{ fontFamily: "'Instrument Serif', serif" }}
        >
          Built for the curious
        </h1>

        <div className="max-w-xl w-full space-y-4">
          <form onSubmit={handleEmailSubmit} className="liquid-glass rounded-full pl-6 pr-2 py-2 flex items-center gap-3">
            <input
              type="email"
              placeholder="Enter your email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="flex-1 bg-transparent text-white placeholder:text-white/40 text-base outline-none border-none"
            />
            <button type="submit" className="bg-white rounded-full p-3 text-black hover:bg-white/90 transition-colors">
              <ArrowRight size={20} />
            </button>
          </form>
          {subscribed && (
            <p className="text-green-400 text-xs text-center" role="status">Thanks for subscribing!</p>
          )}

          <p className="text-white text-sm leading-relaxed px-4">
            Stay updated with the latest news and insights. Subscribe to our newsletter today and never miss out on exciting updates.
          </p>

          <button className="liquid-glass rounded-full px-8 py-3 text-white text-sm font-medium hover:bg-white/5 transition-colors" onClick={handleManifesto}>
            Manifesto
          </button>
        </div>
      </div>

      <div className="relative z-10 flex justify-center gap-4 pb-12">
        <a
          href="#"
          aria-label="Instagram"
          className="liquid-glass rounded-full p-4 text-white/80 hover:text-white hover:bg-white/5 transition-all"
        >
          <Instagram size={20} />
        </a>
        <a
          href="#"
          aria-label="Twitter"
          className="liquid-glass rounded-full p-4 text-white/80 hover:text-white hover:bg-white/5 transition-all"
        >
          <Twitter size={20} />
        </a>
        <a
          href="#"
          aria-label="Website"
          className="liquid-glass rounded-full p-4 text-white/80 hover:text-white hover:bg-white/5 transition-all"
        >
          <Globe size={20} />
        </a>
      </div>
    </>
  );
}
