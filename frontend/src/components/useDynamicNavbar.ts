import { useEffect, useState } from 'react';

export function useDynamicNavbarClass() {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    let ticking = false;

    function updateNavbar() {
      setScrolled(window.scrollY > 18);
      ticking = false;
    }

    function handleScroll() {
      if (!ticking) {
        window.requestAnimationFrame(updateNavbar);
        ticking = true;
      }
    }

    window.addEventListener('scroll', handleScroll, { passive: true });
    updateNavbar();

    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  return scrolled ? 'navbar-scrolled' : '';
}
